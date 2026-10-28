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


def page_blocks(page, skin=None):
    home = load('Home.xml', skin)
    return [(c, anc) for c, anc in walk(home.find('controls'))
            if on_page(c, page) and fade_in(c, 'Visible')]


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
    delays = {fade_in(c, 'Visible')[0] for c, _ in blocks}
    assert len(delays) >= 3, (page, delays)
    rows = next(c for c, _ in blocks if c.get('id') == ROWS[page])
    assert fade_in(rows, 'Visible')[0] == max(delays)
    for c, _ in blocks:
        delay, time = fade_in(c, 'Visible')
        assert delay + time <= 350, (page, c.get('id'), delay, time)


@pytest.mark.parametrize('page', ('home', 'movies', 'shows'))
def test_rows_without_spotlight_come_first(page):
    """Without a spotlight the rows are the page: they start at once."""
    rows = next(c for c, _ in page_blocks(page, SPOTLIGHT_OFF) if c.get('id') == ROWS[page])
    assert fade_in(rows, 'Visible')[0] == 0


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
    """The fanart behind Home fades over when the page or the focused part changes."""
    home = load('Home.xml')
    groups = [c for c, _ in walk(home.find('controls'))
              if c.get('type') == 'group' and is_backdrop(c)]
    assert len(groups) >= 3
    for g in groups[:3]:
        assert fade_in(g, 'Visible'), visible(g)
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
            assert fade_in(c, 'WindowOpen') == fade_in(c, 'Visible'), (page, c.get('id'))


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
