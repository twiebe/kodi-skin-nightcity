"""Page changes build up: the blocks of a Home page fade in one after another (backdrop and hero
first, the rows last), the settings windows fade their content in when they open. Fades and a
few pixels of slide only, short, and in one place to tune (constants in the includes)."""
import pytest

from conftest import ROOT, layout_files, parse
from navigation import load

PAGES = ('home', 'movies', 'shows', 'system', 'search')
ROWS = {'home': '9210', 'movies': '9410', 'shows': '9510', 'system': '9610', 'search': '9710'}
SETTINGS_WINDOWS = ('Settings.xml', 'SettingsCategory.xml', 'SkinSettings.xml', 'SettingsSystemInfo.xml',
                    'EventLog.xml', 'AddonBrowser.xml', 'FileManager.xml', 'SettingsProfile.xml')
SPOTLIGHT_OFF = {'SpotlightSource': 'off', 'nc.movies.spotlight': 'off', 'nc.shows.spotlight': 'off'}


def constants():
    return {el.get('name'): el.text.strip() for p in layout_files() for el in parse(p).iter('constant')}


def ms(value):
    return int(constants().get(value, value))


def animations(control, kind):
    return [a for a in control.findall('animation')
            if (a.get('type') or a.text or '').strip().lower() == kind.lower()]


def effects(anim):
    """(type, start, end, delay, time) of each effect, old or new layout."""
    nodes = anim.findall('effect') or [anim]
    return [(e.get('type') or e.get('effect'), e.get('start'), e.get('end'), ms(e.get('delay') or '0'),
             ms(e.get('time') or '0')) for e in nodes]


def fade_in(control, kind):
    """The fade-in effect of the control's `kind` animation: (delay, time), else None."""
    for anim in animations(control, kind):
        for kind_, start, end, delay, time in effects(anim):
            if kind_ == 'fade' and start == '0':
                return delay, time
    return None


def walk(el, ancestors=()):
    for c in el.findall('control'):
        yield c, ancestors
        yield from walk(c, ancestors + (c,))
    for tag in ('itemlayout', 'focusedlayout'):
        for layout in el.findall(tag):
            yield from walk(layout, ancestors + (layout,))


def visible(control):
    return ' + '.join(v.text or '' for v in control.findall('visible'))


def on_page(control, page):
    return 'Property(nc.page),{})'.format(page) in visible(control)


def names_page(condition, page):
    return 'Property(nc.page),{})'.format(page) in (condition or '')


def page_fade(control, page):
    """The fade-in that runs when `page` comes up: the Visible animation, or for a block that two
    pages share (it stays visible between them) the Conditional animation of that page."""
    for anim in animations(control, 'Conditional'):
        if names_page(anim.get('condition'), page) and not [
                p for p in PAGES if p != page and names_page(anim.get('condition'), p)]:
            for kind_, start, end, delay, time in effects(anim):
                if kind_ == 'fade' and start == '0':
                    return delay, time
    return fade_in(control, 'Visible')


def page_blocks(page, skin=None):
    home = load('Home.xml', skin)
    return [(c, anc) for c, anc in walk(home.find('controls'))
            if on_page(c, page) and page_fade(c, page)]


def test_fade_timings_in_one_place():
    """Short fades: a block fades in 150 to 200 ms, the next starts 40 to 60 ms later, the
    whole page stands within 350 ms."""
    const = constants()
    time = int(const['FadeTime'])
    steps = [0] + [int(const['FadeStep{}'.format(i)]) for i in (1, 2, 3)]
    assert 150 <= time <= 200
    assert all(40 <= b - a <= 60 for a, b in zip(steps, steps[1:])), steps
    assert steps[-1] + time <= 350
    assert 100 <= int(const['WindowFadeTime']) <= 200


@pytest.mark.parametrize('page', PAGES)
def test_home_page_builds_up_block_by_block(page):
    """Each page fades in in at least three steps (hero head, hero rest, rows); the rows come
    last."""
    blocks = page_blocks(page)
    delays = {page_fade(c, page)[0] for c, _ in blocks}
    assert len(delays) >= 3, (page, delays)
    rows = next(c for c, _ in blocks if c.get('id') == ROWS[page])
    assert page_fade(rows, page)[0] == max(delays)
    for c, _ in blocks:
        delay, time = page_fade(c, page)
        assert delay + time <= 350, (page, c.get('id'), delay, time)


@pytest.mark.parametrize('page', ('home', 'movies', 'shows'))
def test_rows_without_spotlight_come_first(page):
    """Without a spotlight the rows are the page: they start at once."""
    rows = next(c for c, _ in page_blocks(page, SPOTLIGHT_OFF) if c.get('id') == ROWS[page])
    assert page_fade(rows, page)[0] == 0


@pytest.mark.parametrize('page', PAGES)
def test_fading_blocks_are_not_inside_the_page(page):
    """Kodi does not update the children of a hidden control: a block inside a group that hides
    with its page would never run its Visible animation again. Every block carries the page
    condition itself, under parents that stay."""
    for c, ancestors in page_blocks(page):
        assert not [a for a in ancestors if 'nc.page' in visible(a)], (page, c.get('id'))


def home_and_settings_animations():
    for name in ('Home.xml',) + SETTINGS_WINDOWS:
        for c, ancestors in walk(load(name).find('controls')):
            for kind in ('Visible', 'Hidden', 'WindowOpen', 'WindowClose'):
                for anim in animations(c, kind):
                    yield name, c, ancestors, kind, anim
            # the page fades of shared blocks; other Conditional animations are not page fades
            for anim in animations(c, 'Conditional'):
                if 'nc.page' in (anim.get('condition') or ''):
                    yield name, c, ancestors, 'Conditional', anim


@pytest.mark.parametrize('page', PAGES)
def test_shared_blocks_fade_in_on_every_page_change(page):
    """A block on two pages (the movie hero of home and movies) stays visible when the menu
    switches between them, so Kodi would not run its Visible animation and the hero would just
    stand, even with the same title on both pages. It fades in on a Conditional animation per
    page instead, which starts whenever that page comes up, and has no Visible fade on top (the
    two would multiply)."""
    for c, _ in walk(load('Home.xml').find('controls')):
        pages = [p for p in PAGES if on_page(c, p)]
        if page not in pages or len(pages) < 2 or not page_fade(c, page):
            continue
        conditional = [a for a in animations(c, 'Conditional') if names_page(a.get('condition'), page)
                       and not [p for p in pages if p != page and names_page(a.get('condition'), p)]]
        assert conditional, (page, c.get('id'), 'no fade of its own for this page')
        assert all(a.get('reversible') == 'false' for a in conditional), (page, c.get('id'))
        assert not fade_in(c, 'Visible'), (page, c.get('id'))


def test_movie_hero_fades_on_both_of_its_pages():
    """The movie hero (poster, text, buttons) is the shared block of home and movies."""
    home = load('Home.xml')
    shared = [c for c, _ in walk(home.find('controls')) if on_page(c, 'home') and on_page(c, 'movies')
              and animations(c, 'Conditional')]
    assert len(shared) >= 3, [c.get('id') for c in shared]
    assert '9300' in [c.get('id') for c in shared]


def test_page_fades_do_not_hold_focus():
    """Kodi keeps a control unfocusable while its animation waits for its delay: each page and
    window animation starts an effect at once, so focus and keys work during the build-up."""
    for name, c, _, kind, anim in home_and_settings_animations():
        assert min(e[3] for e in effects(anim)) == 0, (name, c.get('id'), kind)


def test_page_fades_rest_while_a_video_plays():
    """No blending over a playing video (Home or settings over the player, the OSD)."""
    for name, c, _, kind, anim in home_and_settings_animations():
        assert '!Player.HasVideo' in (anim.get('condition') or ''), (name, c.get('id'), kind)


def test_page_fades_are_cheap():
    """Fades and small slides only, nothing on single list items, no close animations (they
    hold the next window back)."""
    for name, c, ancestors, kind, anim in home_and_settings_animations():
        assert kind != 'WindowClose', name
        assert not [a for a in ancestors if a.tag in ('itemlayout', 'focusedlayout')], (name, kind)
        for kind_, start, end, delay, time in effects(anim):
            assert kind_ in ('fade', 'slide'), (name, kind_)
            assert time <= 200, (name, c.get('id'), time)
            if kind_ == 'slide':
                assert all(abs(int(v)) <= 16 for v in (start + ',' + end).split(',')), (name, start, end)


def test_backdrop_crossfades():
    """The fanart behind Home fades over when the page or the focused part changes. The movie
    spotlight's fanart stands behind home and movies alike: it fades in whenever one of the two
    comes up (SharedBackdropFade, tests/static/test_spotlight_advance.py)."""
    home = load('Home.xml')
    groups = [c for c, _ in walk(home.find('controls'))
              if c.get('type') == 'group' and is_backdrop(c)]
    assert len(groups) >= 3
    for g in groups[:3]:
        assert fade_in(g, 'Visible') or (page_fade(g, 'home') and page_fade(g, 'movies')), visible(g)
        assert animations(g, 'Hidden'), visible(g)


def is_backdrop(control):
    return any(i.findtext('description') == 'fanart backdrop' for i in control.findall('control'))


def test_page_fades_on_home_open():
    """Coming back to Home builds the page up the same way (the backdrop fades by itself as its
    image loads)."""
    for page in PAGES:
        for c, _ in page_blocks(page):
            if is_backdrop(c):
                continue
            assert fade_in(c, 'WindowOpen') == page_fade(c, page), (page, c.get('id'))


@pytest.mark.parametrize('name', SETTINGS_WINDOWS)
def test_settings_windows_fade_in(name):
    """A settings window fades its content in when it opens; background and status line stay, so
    going from one settings page to the next does not flash."""
    window = load(name)
    fading = [(c, anc) for c, anc in walk(window.find('controls')) if fade_in(c, 'WindowOpen')]
    assert fading, name
    top = window.find('controls').findall('control')
    for c, ancestors in fading:
        assert c in top, (name, 'fade on the content group')
        assert fade_in(c, 'WindowOpen') == (0, ms('WindowFadeTime'))
    background = [c for c in top if c.find('texture') is not None and 'white.png' in c.findtext('texture')]
    assert background and not fade_in(background[0], 'WindowOpen')
    assert not window.findall('animation'), 'no window level fade: it would dim the background'


# --- player ----------------------------------------------------------------------------------

def player_details():
    return load('DialogSeekBar.xml').find('controls')


def details_block():
    """The PlayerDetails group (poster, title, badges, plot) in the seek bar dialog."""
    root = player_details()
    return next(c for c in root.findall('control') if c.find("control[@type='textbox']") is not None)


@pytest.mark.parametrize('kind', ['WindowOpen', 'Visible'])
def test_player_details_fade_in_after_the_controls(kind):
    """The OSD comes up in two steps like a Home page: the controls fade in with their window
    (WindowFadeTime), then what plays (poster, title, plot) a step later; also when it comes
    back from the chapter and cast rows (Visible). The seek line comes with the controls."""
    details = details_block()
    delay, time = fade_in(details, kind)
    assert delay == ms('PlayerFadeStep') >= ms('WindowFadeTime')
    assert time == ms('FadeTime')
    for anim in animations(details, kind):
        assert 'Player.HasVideo' not in (anim.get('condition') or '')
        # the first effect starts at once (PageFade)
        assert effects(anim)[0][3] == 0
    bar = [c for c in player_details().findall('control') if c.findtext('top') == '1000']
    assert bar and fade_in(bar[0], 'WindowOpen') is None


def test_osd_controls_fade_with_their_window():
    """Controls and seek line: the first step, the windows' own fade (a fade's start is 0)."""
    for name in ('VideoOSD.xml', 'DialogSeekBar.xml'):
        [anim] = animations(parse(ROOT / '1080i' / name), 'WindowOpen')
        assert effects(anim) == [('fade', None, None, 0, 150)], name
