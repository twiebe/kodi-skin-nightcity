"""Home pages in the skin settings (SkinSettings.xml, categories Home, Movies, Shows, Menu) end
to end: defaults, picking, swapping, moving, options, spotlight off and empty slots, each checked
on Home after the change; the page itself walks like Kodi's settings pages."""
import pytest

from conftest import action, builtin, cond, info, screenshot, wait_for

pytestmark = pytest.mark.e2e

PAGES = ('home', 'movies', 'shows')
CATALOGUE_HOME = ['none', 'continue', 'nextup', 'newmovies', 'newepisodes', 'genres', 'random',
                  'unwatched', 'toprated', 'favourites', 'trending', 'recent', 'move']


def skin(name):
    key = 'Skin.String({})'.format(name)
    return info(key)[key]


def true(condition):
    return cond(condition)[condition]


def reset():
    names = ['SpotlightSource', 'SpotlightInterval', 'nc.movies.spotlight', 'nc.shows.spotlight',
             'nc.shows.interval', 'nc.search.forget']
    names += ['nc.{}.slot{}{}'.format(p, n, o) for p in PAGES for n in range(1, 9) for o in ('', '.opt')]
    for name in names:
        builtin('Skin.Reset({})'.format(name))


@pytest.fixture
def settings(home):
    reset()
    open_category(9002, 'home')
    yield
    builtin('Dialog.Close(all,true)')
    reset()
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')


def open_category(cid, tab):
    builtin('ActivateWindow(SkinSettings)')
    wait_for('Window.IsActive(skinsettings)')
    builtin('SetFocus({})'.format(cid))
    wait_for('Control.HasFocus({}) + String.IsEqual(Window.Property(nc.hp.tab),{})'.format(cid, tab))


def back_home():
    builtin('Dialog.Close(all,true)')
    action('back', delay=1)
    wait_for('Window.IsActive(home)')


def pick(slot_id, value):
    builtin('SetFocus({})'.format(slot_id))
    wait_for('Control.HasFocus({})'.format(slot_id))
    action('select', delay=0.5)
    wait_for('Window.IsActive(selectdialog)', timeout=15)
    builtin('SetFocus(6,{},absolute)'.format(CATALOGUE_HOME.index(value)))
    action('select', delay=0.5)
    wait_for('!Window.IsActive(selectdialog)')


def test_defaults_are_todays_pages(home):
    reset()
    builtin('ReplaceWindow(Home)')
    wait_for('Integer.IsGreater(Container(9202).NumItems,0)')  # new movies, slot 2
    wait_for('Integer.IsGreater(Container(9203).NumItems,0)')  # new episodes, slot 3
    assert not true('Control.IsVisible(9205)')
    builtin('SetFocus(9102)')
    wait_for('Integer.IsGreater(Container(9401).NumItems,0)')  # movies: new movies first
    wait_for('Integer.IsGreater(Container(9403).NumItems,0)')  # unwatched third
    screenshot('hs-default-movies')
    builtin('SetFocus(9103)')
    wait_for('Integer.IsGreater(Container(9502).NumItems,0)')  # shows: new episodes second
    builtin('SetFocus(9101)')


def test_page_fills_defaults_and_labels(settings):
    assert [skin('nc.home.slot{}'.format(n)) for n in range(1, 9)] == \
        ['continue', 'newmovies', 'newepisodes', 'nextup', 'none', 'none', 'none', 'none']
    assert skin('nc.movies.slot4') == 'genres' and skin('nc.movies.spotlight') == 'all'
    assert skin('nc.shows.interval') == '15'
    assert 'Continue watching' in info('Control.GetLabel(221)')['Control.GetLabel(221)']
    screenshot('hs-settings-home')


def test_choose_a_section(settings):
    pick(225, 'random')
    assert skin('nc.home.slot5') == 'random'
    screenshot('hs-settings-picked')
    back_home()
    wait_for('Integer.IsGreater(Container(9205).NumItems,0)')
    screenshot('hs-home-random')


def test_choose_a_used_section_swaps(settings):
    pick(225, 'newmovies')
    assert skin('nc.home.slot5') == 'newmovies' and skin('nc.home.slot2') == 'none'
    pick(221, 'newmovies')
    assert skin('nc.home.slot1') == 'newmovies' and skin('nc.home.slot5') == 'continue'


def test_move_a_slot(settings):
    pick(221, 'move')
    wait_for('String.IsEqual(Window.Property(nc.hp.grab),home.1)')
    screenshot('hs-settings-grab')
    action('down', 'down')
    wait_for('Control.HasFocus(223)')
    assert [skin('nc.home.slot{}'.format(n)) for n in (1, 2, 3)] == ['newmovies', 'newepisodes', 'continue']
    action('select')
    wait_for('String.IsEmpty(Window.Property(nc.hp.grab))')
    action('up')
    wait_for('Control.HasFocus(222)')
    assert skin('nc.home.slot2') == 'newepisodes'  # without a grab up only moves the focus
    back_home()
    wait_for('Integer.IsGreater(Container(9201).NumItems,0)')  # new movies now in slot 1
    screenshot('hs-home-moved')


def test_options_cycle(settings):
    builtin('SetFocus(222)')
    wait_for('Control.HasFocus(222)')
    action('right')
    wait_for('String.IsEqual(Skin.String(nc.home.slot2.opt),unwatched)')
    action('right')
    wait_for('String.IsEmpty(Skin.String(nc.home.slot2.opt))')
    action('right')
    wait_for('String.IsEqual(Skin.String(nc.home.slot2.opt),unwatched)')
    action('left')
    wait_for('Control.HasFocus(9002)')  # left goes back to the category, the option stays
    assert skin('nc.home.slot2.opt') == 'unwatched'
    back_home()
    wait_for('Integer.IsGreater(Container(9202).NumItems,0)')


def test_spotlight_off(settings):
    builtin('SetFocus(211)')
    wait_for('Control.HasFocus(211)')
    assert true('Control.IsVisible(212)')
    action('right', 'right')
    wait_for('String.IsEqual(Skin.String(SpotlightSource),off)')
    assert not true('Control.IsVisible(212)')  # no interval without spotlight
    screenshot('hs-settings-spotlight-off')
    back_home()
    assert not true('Control.IsVisible(9300)')
    wait_for('Integer.IsGreater(Container(9202).NumItems,0)')
    builtin('SetFocus(9101)')
    action('down')
    wait_for('ControlGroup(9210).HasFocus()')
    screenshot('hs-home-spotlight-off')
    builtin('SetFocus(9102)')
    wait_for('Control.IsVisible(9300)')  # movies keeps its spotlight
    builtin('SetFocus(9101)')


def test_page_with_empty_slots(settings):
    for n in (1, 2, 4):
        pick(220 + n, 'none')
    assert [skin('nc.home.slot{}'.format(n)) for n in range(1, 5)] == ['none', 'none', 'newepisodes', 'none']
    back_home()
    wait_for('Integer.IsGreater(Container(9203).NumItems,0)')
    assert not true('Control.IsVisible(9201)') and not true('Control.IsVisible(9202)')
    builtin('SetFocus(9010)')
    action('down')
    wait_for('Control.HasFocus(9203)')  # past the empty slots
    action('up')
    wait_for('Control.HasFocus(9010)')
    screenshot('hs-home-empty-slots')


def test_menu_entries_hide(settings):
    builtin('SetFocus(9005)')
    wait_for('Control.HasFocus(9005)')
    action('right')
    wait_for('Control.HasFocus(511)')
    screenshot('hs-settings-menu')
    action('select')
    wait_for('Skin.HasSetting(nc.menu.hide.movies)')
    try:
        back_home()
        assert not true('Control.IsVisible(9102)') and true('Control.IsVisible(9103)')
        screenshot('hs-home-menu')
    finally:
        builtin('Skin.Reset(nc.menu.hide.movies)')


def test_categories_walk_like_kodis_settings(settings):
    """Up/down on the categories shows their rows, right enters them, left comes back. Main menu
    comes first, the glow at the end of its rows; left on the categories goes back to the console."""
    builtin('SetFocus(9005)')
    wait_for('Control.HasFocus(9005) + Control.IsVisible(500) + Control.IsVisible(601)')
    assert not true('Control.IsVisible(200)')
    builtin('SetFocus(521)')
    wait_for('Control.HasFocus(521)')
    action('down')
    wait_for('Control.HasFocus(601)')
    screenshot('hs-settings-menu')
    action('up')
    wait_for('Control.HasFocus(521)')
    action('left')
    wait_for('Control.HasFocus(9005)')
    action('down')
    wait_for('Control.HasFocus(9002) + Control.IsVisible(200)')
    action('right')
    wait_for('Control.HasFocus(211)')
    action('left')
    wait_for('Control.HasFocus(9002)')
    action('down', 'down')
    wait_for('Control.HasFocus(9004) + Control.IsVisible(400)')
    screenshot('hs-settings-shows')
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')
    builtin('SetProperty(nc.settings.group,2,home)')
    builtin('ActivateWindow(settings)')
    builtin('SetFocus(9222)')
    wait_for('Control.HasFocus(9222)')
    action('select')
    wait_for('Window.IsActive(skinsettings) + Control.HasFocus(9005) + Control.IsVisible(500)')
    action('left')
    wait_for('Window.IsActive(settings) + Control.HasFocus(9222)')


@pytest.mark.e2e
def test_search_terms_switch_off_and_clear(settings):
    recent = '!String.IsEmpty(Window(Home).Property(nc.search.recent.1))'
    builtin('NotifyAll(nightcity,search:Matrix)')
    wait_for(recent)
    open_category(9005, 'menu')
    builtin('SetFocus(515)')
    wait_for('Control.HasFocus(515)')
    screenshot('search_terms_settings')
    action('select')
    wait_for('!' + recent)
    assert not cond('Control.IsVisible(515)')['Control.IsVisible(515)']
    builtin('SetFocus(514)')
    wait_for('Control.HasFocus(514)')
    builtin('NotifyAll(nightcity,search:Matrix)')
    wait_for(recent)
    action('select')
    wait_for('Skin.HasSetting(nc.search.forget) + !' + recent)
    builtin('NotifyAll(nightcity,search:Alien)')
    wait_for('String.IsEqual(Window(Home).Property(nc.search),Alien)')
    assert not cond(recent)[recent]
