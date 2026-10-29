"""Configurable home pages: 8 slots per page (Home, Movies, Shows) filled from a fixed catalogue
(scripts/nightcity.py CATALOGUE), the spotlight per page, the main menu entries, and the skin
settings (SkinSettings.xml, categories Home, Movies, Shows and Menu) that edit them. Home builds
only the chosen rows through conditional includes, so these tests build the window for given
skin settings."""
import importlib.util
import itertools
import random
import re
import sys

import pytest

from conftest import ROOT, layout_files, parse
from navigation import dead_ends, evaluate, load, unreachable

_spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
nightcity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightcity)

PAGES = {'home': '92', 'movies': '94', 'shows': '95'}  # page -> id base of its rows
PL = 'special://skin/playlists/{}.xsp'
HERO_UP = {'home': '9050', 'movies': '9050', 'shows': '9550'}
SPOTLIGHT = {'home': 'SpotlightSource', 'movies': 'nc.movies.spotlight', 'shows': 'nc.shows.spotlight'}
SETTINGS_BASE = {'home': 200, 'movies': 300, 'shows': 400}


def controls(window):
    return {c.get('id'): c for c in window.iter('control') if c.get('id')}


def rows(page, skin=None):
    """[(list id, [content paths])] of the rows the page's grouplist holds, empty slots as
    (group id, None)."""
    base = PAGES[page]
    grouplist = controls(load('Home.xml', skin))[base + '10']
    found = []
    for group in grouplist.findall('control'):
        lst = next((c for c in group.iter('control') if c.get('type') == 'list'), None)
        if lst is None:
            assert group.findtext('visible') == 'false', group.get('id')
            found.append((group.get('id'), None))
        else:
            found.append((lst.get('id'), [c.text for c in lst.findall('content') if c.text]))
    return found


def slot_skin(page, n, key, opt=''):
    return {'nc.{}.slot{}'.format(page, n): key, 'nc.{}.slot{}.opt'.format(page, n): opt}


# --- Home: rows per slot ---------------------------------------------------------------------

def test_defaults_are_todays_rows():
    """Without any setting each page shows the rows it had before, under the same ids."""
    genre = 'videodb://movies/genres/$INFO[Window(Home).Property(nc.genre.id)]/'
    assert rows('home') == [
        ('9201', [PL.format('WidgetInProgressMovies'), PL.format('WidgetInProgressEpisodes')]),
        ('9202', [PL.format('WidgetNewMovies')]), ('9203', [PL.format('WidgetNewShows')]),
        ('9204', [PL.format('WidgetContinueShows')]),
        ('9215', None), ('9216', None), ('9217', None), ('9218', None)]
    assert rows('movies')[:4] == [
        ('9401', [PL.format('WidgetNewMovies')]), ('9402', [PL.format('WidgetInProgressMovies')]),
        ('9403', [PL.format('WidgetUnwatchedMovies')]), ('9404', [genre])]
    assert rows('shows')[:4] == [
        ('9501', [PL.format('WidgetContinueShows')]), ('9502', [PL.format('WidgetNewShows')]),
        ('9503', [PL.format('WidgetInProgressEpisodes')]), ('9504', [PL.format('WidgetUnwatchedShows')])]
    assert [r[1] for r in rows('movies')[4:] + rows('shows')[4:]] == [None] * 8


def variants():
    for page, sections in nightcity.CATALOGUE.items():
        for key, opts in sections:
            for opt in [o for o, _ in opts] or ['']:
                yield page, key, opt


@pytest.mark.parametrize('page,key,opt', list(variants()))
def test_every_section_builds_in_any_slot(page, key, opt):
    base = PAGES[page]
    stored = '' if opt == next(iter([o for o, _ in dict(nightcity.CATALOGUE[page])[key]]), '') else opt
    skin = {'nc.{}.slot{}'.format(page, n): 'none' for n in range(1, 9)}
    skin.update(slot_skin(page, 6, key, stored))
    found = rows(page, skin)
    assert found[5][0] == base + '06' and found[5][1], (page, key, opt)
    window = load('Home.xml', skin)
    ids = [c.get('id') for c in window.iter('control') if c.get('id') not in (None, '0')]
    assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]


EXPECTED_PATHS = {
    ('home', 'continue', 'movies'): [PL.format('WidgetInProgressMovies')],
    ('home', 'continue', 'shows'): [PL.format('WidgetInProgressEpisodes')],
    ('home', 'newmovies', 'unwatched'): [PL.format('WidgetNewMoviesUnwatched')],
    ('home', 'newepisodes', 'unwatched'): [PL.format('WidgetNewShowsUnwatched')],
    ('home', 'genres', 'shows'): ['videodb://tvshows/genres/$INFO[Window(Home).Property(nc.tvgenre.id)]/'],
    ('home', 'random', 'all'): [PL.format('WidgetRandomMovies')],
    ('home', 'random', 'unwatched'): [PL.format('WidgetRandomMoviesUnwatched')],
    ('home', 'unwatched', 'both'): [PL.format('WidgetUnwatchedMovies'), PL.format('WidgetUnwatchedShows')],
    ('home', 'toprated', 'movies'): [PL.format('WidgetTopRatedMovies')],
    ('home', 'toprated', 'shows'): [PL.format('WidgetTopRatedShows')],
    ('home', 'favourites', ''): ['favourites://'],
    ('home', 'trending', 'movies'): ['$VAR[TmdbTrendingHomeMovies]'],
    ('home', 'trending', 'shows'): ['$VAR[TmdbTrendingHomeShows]'],
    ('home', 'recent', 'both'): [PL.format('WidgetRecentMovies'), PL.format('WidgetRecentEpisodes')],
    ('movies', 'sets', ''): ['videodb://movies/sets/'],
    ('movies', 'trending', ''): ['$VAR[TmdbTrendingMoviesMovies]'],
    ('shows', 'unwatched', ''): [PL.format('WidgetUnwatchedShows')],
    ('shows', 'genres', ''): ['videodb://tvshows/genres/$INFO[Window(Home).Property(nc.tvgenre.id)]/'],
    ('shows', 'trending', ''): ['$VAR[TmdbTrendingShowsShows]'],
}


@pytest.mark.parametrize('variant', list(EXPECTED_PATHS))
def test_section_contents(variant):
    page, key, opt = variant
    first = next(iter([o for o, _ in dict(nightcity.CATALOGUE[page])[key]]), '')
    found = rows(page, slot_skin(page, 2, key, '' if opt == first else opt))
    assert found[1][1] == EXPECTED_PATHS[variant]


def test_empty_slots_and_stray_values():
    skin = dict(slot_skin('home', 1, 'none'), **slot_skin('home', 3, 'bogus'))
    found = rows('home', skin)
    assert found[0] == ('9211', None) and found[2] == ('9213', None)
    assert found[1][0] == '9202' and found[3][0] == '9204'
    skin = {'nc.home.slot{}'.format(n): 'none' for n in range(1, 9)}
    assert rows('home', skin) == [('92{}'.format(10 + n), None) for n in range(1, 9)]


def test_option_values_without_meaning_fall_back_to_the_first():
    assert rows('home', slot_skin('home', 1, 'continue', 'bogus'))[0][1] == rows('home')[0][1]


def test_rows_wire_up_and_down_through_empty_slots():
    """A row moves up and down to the neighbouring slot's group; empty slots are hidden groups,
    which pass the move on, the first slot moves up to the hero."""
    window = load('Home.xml', slot_skin('home', 2, 'none'))
    c = controls(window)
    assert c['9201'].findtext('onup') == '9050' and c['9201'].findtext('ondown') == '9212'
    assert c['9212'].findtext('visible') == 'false'
    assert c['9203'].findtext('onup') == '9212' and c['9204'].findtext('ondown') == '9215'
    assert c['9208'] if '9208' in c else True


def test_genre_row_focuses_its_tabs_from_above():
    for page, base, prop in (('movies', '94', 'nc.genre'), ('home', '92', 'nc.tvgenre')):
        skin = {} if page == 'movies' else slot_skin('home', 4, 'genres', 'shows')
        c = controls(load('Home.xml', skin))
        group = c[base + '14']
        assert group.findtext('defaultcontrol') == base + '30'
        assert group.find('defaultcontrol').get('always') == 'true'
        tabs = c[base + '30']
        assert tabs.findtext('ondown') == base + '04' and tabs.findtext('onup') == base + '13'
        labels = ''.join(t.findtext('label') or '' for t in tabs.iter('control'))
        assert prop + '.1.label' in labels


def test_loaders_for_rows_that_refill():
    """Rows that can empty and fill again (started, next up, recently watched) and the TMDb rows
    take their visibility from an off-screen loader with the same content."""
    for page, key, opt, n in (('home', 'continue', '', 1), ('home', 'nextup', '', 4),
                              ('movies', 'continue', '', 2), ('shows', 'nextup', '', 1),
                              ('home', 'recent', '', 3), ('home', 'trending', 'shows', 5)):
        skin = slot_skin(page, n, key, opt)
        c = controls(load('Home.xml', skin))
        base = PAGES[page]
        loader, lst = c['{}2{}'.format(base, n)], c['{}0{}'.format(base, n)]
        assert [x.text for x in loader.findall('content') if x.text] == \
               [x.text for x in lst.findall('content') if x.text]
        assert 'Container({}2{}).NumItems'.format(base, n) in lst.findtext('visible')


def test_tmdb_rows_wait_for_the_page_timer():
    """A TMDb row runs a plugin: it loads only on its page, 2 s after the page came up, so it
    never starts next to Home's own script or another page's TMDb row."""
    variables = {v.get('name'): v for v in parse(ROOT / '1080i' / 'Includes_Sections.xml').iter('variable')}
    timers = {t.findtext('name'): t for t in parse(ROOT / '1080i' / 'Timers.xml').iter('timer')}
    for page in PAGES:
        timer = timers['nc_{}_page'.format(page)]
        assert 'nc.page' in timer.findtext('start') and timer.find('start').get('reset') == 'true'
        for kind, tmdb in (('Movies', 'movie'), ('Shows', 'tv')):
            var = variables.get('TmdbTrending{}{}'.format(page.capitalize(), kind))
            if var is None:
                continue
            value = var.find('value')
            assert 'Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_{}_page),2)'.format(page) in value.get('condition')
            assert value.text == 'plugin://plugin.video.themoviedb.helper/?info=trending_week&tmdb_type=' + tmdb


def test_generated_includes_are_current():
    spec = importlib.util.spec_from_file_location('make_sections', ROOT / 'tools' / 'make_sections.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert (ROOT / '1080i' / 'Includes_Sections.xml').read_text(encoding='utf-8') == module.render()


# --- spotlight per page ----------------------------------------------------------------------

def test_spotlight_off_removes_the_hero_and_lifts_the_rows():
    on = controls(load('Home.xml'))
    assert on['9210'].findtext('top') == '612' and on['9210'].findtext('onup') == '9050'
    off = controls(load('Home.xml', {'SpotlightSource': 'off', 'nc.movies.spotlight': 'off', 'nc.shows.spotlight': 'off'}))
    for gone in ('9000', '9001', '9050', '9550', '9300'):
        assert gone not in off
    for page in PAGES:
        rows_ = off[PAGES[page] + '10']
        assert int(rows_.findtext('top')) < 200 and int(rows_.findtext('height')) >= 2 * 468
        assert rows_.findtext('onup') == '9100'
        assert off[PAGES[page] + '01'].findtext('onup') == '9100'
    window = load('Home.xml', {'SpotlightSource': 'off'})
    assert window.findtext('defaultcontrol') == '9101'
    assert '9000' in controls(window)  # still needed by the movies page
    assert load('Home.xml').findtext('defaultcontrol') == '9010'


def test_menu_moves_down_past_a_missing_hero():
    menu = controls(load('Home.xml'))['9100']
    downs = [(d.get('condition') or '', d.text) for d in menu.findall('ondown')]
    for page, rows_ in (('movies', '9410'), ('shows', '9510')):
        cond = next(c for c, t in downs if t == rows_)
        assert 'nc.page),{}'.format(page) in cond and SPOTLIGHT[page] in cond
    cond = next(c for c, t in downs if t == '9210')
    assert 'SpotlightSource),off' in cond
    assert downs.index(next(d for d in downs if d[1] == '9510')) < downs.index(next(d for d in downs if d[1] == '9550'))
    assert downs[-1] == ('', '9050')


def autoscroll_times(list_id, skin):
    lst = controls(load('Home.xml', skin))[list_id]
    return [a.get('time') for a in lst.findall('autoscroll')]


def test_spotlight_intervals_per_page():
    """Home and movies share the movie spotlight and its interval; shows has its own, empty
    follows home (as before the setting existed)."""
    assert autoscroll_times('9000', {}) == ['15000'] and autoscroll_times('9001', {}) == ['15000']
    assert autoscroll_times('9000', {'SpotlightInterval': '30'}) == ['30000']
    assert autoscroll_times('9001', {'SpotlightInterval': '30'}) == ['30000']
    assert autoscroll_times('9001', {'SpotlightInterval': '30', 'nc.shows.interval': '10'}) == ['10000']
    assert autoscroll_times('9001', {'nc.shows.interval': 'off'}) == []
    assert autoscroll_times('9001', {'SpotlightInterval': 'off', 'nc.shows.interval': '15'}) == ['15000']
    assert autoscroll_times('9000', {'SpotlightInterval': 'off'}) == []


def test_spotlight_sources():
    variables = {v.get('name'): v for f in layout_files() for v in parse(f).iter('variable')}
    movies = [(v.get('condition') or '', v.text) for v in variables['SpotlightPath'].findall('value')]
    assert any('nc.movies.spotlight),unwatched' in c and t.endswith('SpotlightUnwatched.xsp') for c, t in movies)
    shows = [(v.get('condition') or '', v.text) for v in variables['SpotlightShowsPath'].findall('value')]
    assert shows[-1] == ('', PL.format('SpotlightShows'))
    assert any('nc.shows.spotlight),unwatched' in c and t == PL.format('SpotlightShowsUnwatched') for c, t in shows)


# --- main menu -------------------------------------------------------------------------------

def test_menu_entries_can_be_hidden():
    c = controls(load('Home.xml'))
    for tab, name in (('9102', 'movies'), ('9103', 'shows'), ('9104', 'search')):
        assert c[tab].findtext('visible') == '!Skin.HasSetting(nc.menu.hide.{})'.format(name)
    for tab in ('9101', '9105'):
        assert c[tab].findtext('visible') == 'true'
    home = parse(ROOT / '1080i' / 'Home.xml')
    loads = [(o.get('condition') or '', o.text) for o in home.findall('onload')]
    for name in ('movies', 'shows', 'search'):
        assert ('String.IsEqual(Window(Home).Property(nc.page),{0}) + Skin.HasSetting(nc.menu.hide.{0})'.format(name),
                'SetProperty(nc.page,home,home)') in loads


# --- navigation for any combination ----------------------------------------------------------

def combos():
    yield {}
    yield {'SpotlightSource': 'off', 'nc.movies.spotlight': 'off', 'nc.shows.spotlight': 'off'}
    yield {'nc.{}.slot{}'.format(p, n): 'none' for p in PAGES for n in range(1, 9)}
    rnd = random.Random(7)
    for _ in range(12):
        skin = {}
        for page in PAGES:
            keys = [k for k, _ in nightcity.CATALOGUE[page]]
            chosen = rnd.sample(keys + ['none'] * 4, 8)
            for n, key in enumerate(chosen, 1):
                skin['nc.{}.slot{}'.format(page, n)] = key
            skin[SPOTLIGHT[page]] = rnd.choice(['', 'unwatched', 'off'])
        yield skin


LOADERS = {'9000', '9001', '9721', '9722', '9723', '9724', '9725'} | \
          {'{}2{}'.format(b, n) for b in PAGES.values() for n in range(1, 9)}


@pytest.mark.parametrize('skin', list(combos()))
def test_home_navigation_for_any_combination(skin):
    assert set(unreachable('Home.xml', skin)) - LOADERS == set()
    assert dead_ends('Home.xml', skin) == []


# --- settings page ---------------------------------------------------------------------------

# category button -> (label, tab, first control on the right)
CATEGORIES = {'9005': (31264, 'menu', '500'), '9002': (10000, 'home', '200'), '9003': (342, 'movies', '300'),
              '9004': (20343, 'shows', '400')}
CATEGORY = {'home': '9002', 'movies': '9003', 'shows': '9004'}


def page_window(skin=None):
    return load('SkinSettings.xml', skin)


def slot_button(page, n):
    return controls(page_window())[str(SETTINGS_BASE[page] + 20 + n)]


INFO = re.compile(r'\$INFO\[(Skin\.String|Window\.Property)\(([^)]+)\)\]')


def run(control, tag, state):
    """Run the actions of `tag` like Kodi: conditions first, then each builtin in order with its
    $INFO resolved when it runs. state: Skin.String names and 'Window.Property(x)' keys."""
    def value(m):
        key = m.group(2) if m.group(1) == 'Skin.String' else 'Window.Property({})'.format(m.group(2))
        return state.get(key, '')
    chosen = [a.text for a in control.findall(tag)
              if not a.get('condition') or evaluate(a.get('condition'), state)]
    target = None
    for action in chosen:
        if action.isdigit():
            target = target or action
            continue
        action = INFO.sub(value, action)
        m = re.match(r'(Skin\.SetString|SetProperty|Skin\.Reset|ClearProperty)\(([^,)]+)(?:,([^,)]*))?', action)
        if not m:
            continue
        name, key, arg = m.groups()
        if name == 'Skin.SetString':
            state[key] = arg or ''
        elif name == 'Skin.Reset':
            state[key] = ''
        elif name == 'SetProperty':
            state['Window.Property({})'.format(key)] = arg or ''
        else:
            state['Window.Property({})'.format(key)] = ''
    return target


def test_skin_settings_look_like_kodis_settings_pages():
    """As SettingsCategory.xml: categories on the left (x 120, w 400), the rows of the focused
    category on the right (x 560, w 1240), the description at the bottom right; no window 1111."""
    assert not (ROOT / '1080i' / 'Custom_1111_HomePages.xml').exists()
    c = controls(page_window())
    cats = c['9000']
    assert cats.get('type') == 'grouplist'
    assert [cats.findtext(t) for t in ('left', 'top', 'width', 'height')] == ['120', '100', '400', '840']
    assert [b.get('id') for b in cats.findall('control')] == list(CATEGORIES)
    for cid, (label, tab, _) in CATEGORIES.items():
        button = c[cid]
        assert button.get('type') == 'togglebutton'
        assert button.findtext('label') == '$LOCALIZE[{}]'.format(label)
        assert button.findtext('onfocus') == 'SetProperty(nc.hp.tab,{})'.format(tab)
        assert button.findtext('usealttexture') == 'String.IsEqual(Window.Property(nc.hp.tab),{})'.format(tab)
    assert '9001' not in c
    for area, tab in (('200', 'home'), ('300', 'movies'), ('400', 'shows'), ('500', 'menu')):
        assert c[area].findtext('left') == '560' and c[area].findtext('width') == '1240', area
        assert c[area].findtext('visible') == 'String.IsEqual(Window.Property(nc.hp.tab),{})'.format(tab)
    desc = c['6']
    assert [desc.findtext(t) for t in ('left', 'top', 'width', 'height', 'font')] == ['560', '920', '1240', '120', 'font_tiny']
    for page in SETTINGS_BASE:
        assert slot_button(page, 1).findtext('width') == '1240'


def test_left_and_right_between_the_columns():
    """Left on the categories leaves the page; right enters the rows of the category, left in
    the rows comes back to it (except while a slot is grabbed)."""
    c = controls(page_window())
    assert c['9000'].findtext('onleft') == 'Action(Back)'
    for cid, (_, tab, area) in CATEGORIES.items():
        assert run(c['9000'], 'onright', {'Window.Property(nc.hp.tab)': tab}) == area
        assert run(c[area], 'onleft', {}) == cid
    for page, cat in CATEGORY.items():
        for cid in (SETTINGS_BASE[page] + 11, SETTINGS_BASE[page] + 12):
            assert run(c[str(cid)], 'onleft', {}) == cat
        for n in (1, 5, 8):
            button = slot_button(page, n)
            assert run(button, 'onleft', {}) == cat
            grabbed = {'Window.Property(nc.hp.grab)': '{}.{}'.format(page, n)}
            assert run(button, 'onleft', grabbed) == str(SETTINGS_BASE[page] + 20 + n)


def test_opens_on_the_main_menu_category():
    """The console has one entry for the skin; a second one for the home pages only opened the
    same page on another category."""
    assert '9224' not in controls(load('Settings.xml'))
    root = parse(ROOT / '1080i' / 'SkinSettings.xml')
    assert root.findtext('defaultcontrol') == '9000'
    onloads = [(o.get('condition'), o.text) for o in root.findall('onload')]
    assert (None, 'SetProperty(nc.hp.tab,menu)') in onloads
    # the categories keep their last focus otherwise, under the rows of the main menu
    assert (None, 'SetFocus(9005)') in onloads
    assert not [o for o in onloads if 'nc.ss.open' in o[1] or 'nc.ss.open' in (o[0] or '')]
    texts = ''.join(o.text or '' for o in root.iter('onclick'))
    assert 'ActivateWindow(1111)' not in texts


def test_main_menu_category_holds_the_look_under_appearance():
    """The look gets no category of its own: colour scheme and glow sit at the end of the main
    menu category, under a separator and an Appearance heading."""
    area = controls(page_window())['500']
    labels = [k.findtext('label') for k in area.iter('control') if k.get('type') == 'label']
    assert '$LOCALIZE[480]' in labels
    ids = [k.get('id') for k in area.iter('control') if k.get('id')]
    assert ids[-1] == '601'
    c = controls(page_window())
    glow = c['601']
    assert glow.get('type') == 'radiobutton' and glow.findtext('width') == '1240'
    assert glow.findtext('onclick') == 'Skin.ToggleSetting(GlowOff)'
    assert glow.findtext('selected') == '!Skin.HasSetting(GlowOff)'


def test_main_menu_category_picks_the_colour_scheme():
    """Kodi keeps the colour scheme under Interface: a row above the glow picks it (script
    colours) and shows the current one."""
    c = controls(page_window())
    row = c['602']
    assert row.findtext('onclick') == 'NotifyAll(nightcity,colours)'
    assert row.findtext('label2') == '$VAR[ColourSchemeLabel]'
    assert [row.findtext(d) for d in ('onup', 'ondown', 'onleft')] == ['521', '601', '9005']
    assert c['601'].findtext('onup') == '602'


def test_settings_page_fills_the_defaults_on_load():
    """Moving and swapping copy values between slots, so every slot gets its effective value
    when the page opens; a user who never opens it keeps the defaults of the XML."""
    window = page_window()
    state = {'SpotlightSource': 'unwatched', 'SpotlightInterval': '30', 'nc.home.slot2': 'toprated'}
    for onload in window.findall('onload'):
        if not onload.get('condition') or evaluate(onload.get('condition'), state):
            run_one(onload.text, state)
    assert [state['nc.home.slot{}'.format(n)] for n in range(1, 9)] == \
           ['continue', 'toprated', 'newepisodes', 'nextup', 'none', 'none', 'none', 'none']
    assert state['nc.movies.slot4'] == 'genres' and state['nc.shows.slot3'] == 'inprogress'
    assert state['nc.movies.spotlight'] == 'unwatched'
    assert state['nc.shows.interval'] == '30'


def run_one(action, state):
    holder = parse_actions('<x><a>{}</a></x>'.format(action))
    run(holder, 'a', state)


def parse_actions(text):
    import xml.etree.ElementTree as ET
    return ET.fromstring(text)


def test_slot_click_opens_the_section_dialog():
    for page in SETTINGS_BASE:
        for n in (1, 8):
            button = slot_button(page, n)
            clicks = [(a.get('condition') or '', a.text) for a in button.findall('onclick')]
            assert ('!String.IsEqual(Window.Property(nc.hp.grab),{}.{})'.format(page, n),
                    'NotifyAll(nightcity,section_pick:{}:{})'.format(page, n)) in clicks


def test_right_cycles_the_option():
    button = slot_button('home', 3)
    state = {'nc.home.slot3': 'continue', 'nc.home.slot3.opt': ''}
    seen = []
    for _ in range(3):
        run(button, 'onright', state)
        seen.append(state['nc.home.slot3.opt'])
    assert seen == ['movies', 'shows', '']
    state = {'nc.home.slot3': 'nextup', 'nc.home.slot3.opt': ''}
    run(button, 'onright', state)
    assert state['nc.home.slot3.opt'] == ''
    state = {'nc.movies.slot2': 'newmovies'}
    run(slot_button('movies', 2), 'onright', state)
    assert state['nc.movies.slot2.opt'] == 'unwatched'
    state = {'nc.home.slot3': 'continue', 'Window.Property(nc.hp.grab)': 'home.3'}
    run(button, 'onright', state)
    assert state.get('nc.home.slot3.opt', '') == ''


def test_move_carries_the_slot():
    """While a slot is grabbed (nc.hp.grab = page.n) up/down swap it with its neighbour and
    the grab moves along; OK drops it. Without a grab up/down only move the focus."""
    state = {'nc.home.slot{}'.format(n): k for n, k in enumerate(nightcity.default_slots('home'), 1)}
    state['nc.home.slot1.opt'] = 'shows'
    state['Window.Property(nc.hp.grab)'] = 'home.1'
    target = run(slot_button('home', 1), 'ondown', state)
    assert target == '222'
    assert state['nc.home.slot1'] == 'newmovies' and state['nc.home.slot2'] == 'continue'
    assert state['nc.home.slot2.opt'] == 'shows' and state['nc.home.slot1.opt'] == ''
    assert state['Window.Property(nc.hp.grab)'] == 'home.2'
    target = run(slot_button('home', 2), 'onup', state)
    assert target == '221' and state['nc.home.slot1'] == 'continue'
    assert run(slot_button('home', 1), 'onup', state) == '221'  # stays at the top
    state['Window.Property(nc.hp.grab)'] = 'home.8'
    assert run(slot_button('home', 8), 'ondown', state) == '228'
    run(slot_button('home', 8), 'onclick', state)
    assert state['Window.Property(nc.hp.grab)'] == ''
    before = dict(state)
    assert run(slot_button('home', 4), 'onup', state) == '223'
    assert state == before
    assert run(slot_button('home', 1), 'onup', state) == '212'


def test_grab_turns_the_slot_pink():
    variables = {v.get('name'): v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable')}
    values = [(v.get('condition') or '', v.text) for v in variables['HomePagesFocusColor'].findall('value')]
    assert values == [('!String.IsEmpty(Window.Property(nc.hp.grab))', 'accent2'), ('', 'focus')]
    button = slot_button('home', 1)
    assert button.find('texturefocus').get('colordiffuse') == '$VAR[HomePagesFocusColor]'


def test_header_rows():
    """Spotlight source and change interval: OK and right step forward, the interval row hides
    while the spotlight is off. Movies shares the interval with home."""
    c = controls(page_window())
    source, interval = c['211'], c['212']
    for tag in ('onright', 'onclick'):
        state = {}
        seen = []
        for _ in range(3):
            run(source, tag, state)
            seen.append(state.get('SpotlightSource', ''))
        assert seen == ['unwatched', 'off', '']
    assert interval.findtext('visible') == '!String.IsEqual(Skin.String(SpotlightSource),off)'
    state = {}
    seen = []
    for _ in range(5):
        run(interval, 'onright', state)
        seen.append(state.get('SpotlightInterval', ''))
    assert seen == ['30', '60', 'off', '10', '']
    run(c['311'], 'onright', {'nc.movies.spotlight': 'all'})
    assert 'SpotlightInterval' in ''.join(a.text for a in c['312'].findall('onright'))
    state = {'nc.shows.interval': '15'}
    run(c['412'], 'onright', state)
    assert state['nc.shows.interval'] == '30'


def test_menu_category_toggles_the_entries():
    c = controls(page_window())
    for cid, name in (('511', 'movies'), ('512', 'shows'), ('513', 'search')):
        assert c[cid].get('type') == 'radiobutton' and c[cid].findtext('width') == '1240'
        assert c[cid].findtext('onclick') == 'Skin.ToggleSetting(nc.menu.hide.{})'.format(name)
        assert c[cid].findtext('selected') == '!Skin.HasSetting(nc.menu.hide.{})'.format(name)


@pytest.mark.parametrize('skin', [{}, {'SpotlightSource': 'off', 'nc.movies.spotlight': 'off'}])
@pytest.mark.parametrize('tab', ['home', 'movies', 'shows', 'menu'])
def test_settings_page_navigation(skin, tab):
    skin = dict(skin, **{'Window.Property(nc.hp.tab)': tab})
    assert dead_ends('SkinSettings.xml', skin) == []
    shown = {'home': '2', 'movies': '3', 'shows': '4', 'menu': '5'}[tab]
    assert [i for i in unreachable('SkinSettings.xml', skin) if i[0] == shown] == []


# --- playlists and strings -------------------------------------------------------------------

def rules(name):
    pl = parse(ROOT / 'playlists' / (name + '.xsp'))
    return pl.get('type'), [(r.get('field'), r.get('operator'), [v.text for v in r.iter('value')]) for r in pl.iter('rule')], \
        pl.findtext('order')


def test_new_playlists():
    assert rules('WidgetTopRatedMovies') == ('movies', [('rating', 'greaterthan', ['6.99'])], 'rating')
    assert rules('WidgetTopRatedShows') == ('tvshows', [('rating', 'greaterthan', ['6.99'])], 'rating')
    assert rules('WidgetRandomMovies') == ('movies', [], 'random')
    assert rules('WidgetRandomMoviesUnwatched') == ('movies', [('playcount', 'is', ['0'])], 'random')
    assert rules('WidgetNewMoviesUnwatched') == ('movies', [('playcount', 'is', ['0'])], 'dateadded')
    assert rules('WidgetNewShowsUnwatched') == ('tvshows', [('playcount', 'is', ['0'])], 'dateadded')
    assert rules('WidgetRecentMovies')[0] == 'movies' and rules('WidgetRecentEpisodes')[0] == 'episodes'
    for name in ('WidgetRecentMovies', 'WidgetRecentEpisodes'):
        assert rules(name)[2] == 'lastplayed'
    assert rules('SpotlightShowsUnwatched') == ('tvshows', [('playcount', 'is', ['0'])], 'random')


def po_ids(lang):
    text = (ROOT / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
    return {int(i): s for i, s in re.findall(r'msgctxt "#(\d+)"\nmsgid "(?:[^"\\]|\\.)*"\nmsgstr "((?:[^"\\]|\\.)*)"', text)}


def test_skin_strings_exist_in_english():
    """English only for now: the skin keeps Kodi's language files, a translation can follow."""
    assert [p.name for p in (ROOT / 'language').iterdir()] == ['resource.language.en_gb']
    used = set()
    for path in list(layout_files()) + [ROOT / 'scripts' / 'nightcity.py']:
        used |= {int(i) for i in re.findall(r'LOCALIZE\[(31\d{3})\]', path.read_text(encoding='utf-8'))}
    for name, desc in nightcity.SECTIONS.values():
        used |= {i for i in (name, desc) if i >= 30000}
    en = po_ids('en_gb')
    assert used - set(en) == set()
    for i in range(31222, max(en) + 1):
        assert '–' not in en.get(i, '') and '—' not in en.get(i, ''), i


def test_menu_category_switches_search_history():
    c = controls(page_window())
    toggle = c['514']
    assert toggle.findtext('selected') == '!Skin.HasSetting(nc.search.forget)'
    assert [a.text for a in toggle.findall('onclick')] == ['Skin.ToggleSetting(nc.search.forget)',
                                                          'NotifyAll(nightcity,search_forget)']
    clear = c['515']
    assert clear.get('type') == 'button' and clear.findtext('width') == '1240'
    assert clear.findtext('onclick') == 'NotifyAll(nightcity,search_clear)'
    assert clear.findtext('visible') == '!String.IsEmpty(Window(Home).Property(nc.search.recent.1))'
