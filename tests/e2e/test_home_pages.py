import time

import pytest

from conftest import action, builtin, cond, info, screenshot, wait_for

pytestmark = pytest.mark.e2e

PAGES = {'home': (9101, 9010), 'movies': (9102, 9010), 'shows': (9103, 9551), 'system': (9105, 9601)}
VIEWPORTS = {'home': 9210, 'movies': 9410, 'shows': 9510, 'system': 9610}


def page():
    return info('Window(Home).Property(nc.page)')['Window(Home).Property(nc.page)'] or 'home'


def visible(control_id):
    key = 'Control.IsVisible({})'.format(control_id)
    return cond(key)[key]


def focused(control_id):
    key = 'Control.HasFocus({})'.format(control_id)
    return cond(key)[key]


def focus(control_id):
    builtin('SetFocus({})'.format(control_id))
    wait_for('Control.HasFocus({})'.format(control_id))


@pytest.fixture
def home_page(home):
    yield
    focus(9101)


def test_focus_switches_page(home_page):
    focus(9102)
    assert page() == 'movies'
    assert visible(9410)
    assert not visible(9210)


def test_fast_switching(home_page):
    focus(9101)
    action('right', 'right', 'right', 'right', delay=0.15)
    wait_for('Control.HasFocus(9105)')
    assert page() == 'system'
    assert visible(9610)


def test_search_is_a_page(home_page):
    focus(9104)
    assert page() == 'search' and visible(9750)


@pytest.mark.parametrize('name', list(PAGES))
def test_down_from_menu(home_page, name):
    tab, target = PAGES[name]
    focus(tab)
    action('down')
    wait_for('Control.HasFocus({})'.format(target))
    screenshot('{}-dplus'.format(name))


@pytest.mark.parametrize('spotlight,first,last,tab', [(9000, 9010, 9012, 9102), (9001, 9551, 9553, 9103)])
def test_spotlight_prev_next(home_page, spotlight, first, last, tab):
    focus(tab)
    wait_for('Integer.IsGreater(Container({}).NumItems,2)'.format(spotlight))
    total = int(info('Container({}).NumItems'.format(spotlight))['Container({}).NumItems'.format(spotlight)])
    key = 'Container({}).CurrentItem'.format(spotlight)
    focus(first)
    page_spotlight(key, 'left', lambda n: (n - 2) % total + 1)
    focus(last)
    page_spotlight(key, 'right', lambda n: n % total + 1)


def page_spotlight(key, direction, expected):
    """Press direction and wait for the spotlight to move one item. The spotlight also scrolls on
    its own every 10 s, so a scroll between reading and pressing gets another try."""
    for _ in range(3):
        start = int(info(key)[key])
        action(direction)
        try:
            wait_for('Integer.IsEqual({},{})'.format(key, expected(start)), timeout=3)
            return
        except AssertionError:
            continue
    raise AssertionError('spotlight did not move {}'.format(direction))

def test_manual_move_restarts_autoscroll(home_page):
    """After a manual move the next automatic change waits a full 15 s again."""
    focus(9102)
    wait_for('Integer.IsGreater(Container(9000).NumItems,2)')
    focus(9012)
    key = 'Container(9000).CurrentItem'
    start = info(key)[key]
    wait_for('!Integer.IsEqual({},{})'.format(key, start), timeout=17)  # an automatic change
    time.sleep(9)
    action('right', delay=0.5)
    moved = info(key)[key]
    time.sleep(10)
    assert info(key)[key] == moved


def test_rows_one_at_a_time(home_page):
    focus(9202)
    action('down')
    wait_for('Control.HasFocus(9203)')
    assert visible(9213)
    action('up')
    wait_for('Control.HasFocus(9202)')



GENRE_ROW, GENRE_TABS, GENRE_PICK = 9404, (9431, 9432, 9433), 9434


def prop(name):
    key = 'Window(Home).Property({})'.format(name)
    return info(key)[key]


def test_genre_tabs_filled(home_page):
    focus(9102)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.genre.3.label))')
    for n in (1, 2, 3):
        assert prop('nc.genre.{}.label'.format(n))
    wait_for('Integer.IsGreater(Container({}).NumItems,0)'.format(GENRE_ROW))


def test_genre_tab_switches_row(home_page):
    focus(9102)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.genre.2.id))')
    focus(GENRE_TABS[1])
    assert prop('nc.genre.id') == prop('nc.genre.2.id')
    label = prop('nc.genre.2.label')
    wait_for('String.Contains(Container({}).ListItem(0).Genre,{})'.format(GENRE_ROW, label))
    screenshot('genre-row')


def test_genre_row_navigation(home_page):
    focus(9102)
    wait_for('Integer.IsGreater(Container({}).NumItems,0)'.format(GENRE_ROW))
    focus(9403)
    action('down')
    wait_for('ControlGroup(9430).HasFocus()')
    action('down')
    wait_for('Control.HasFocus({})'.format(GENRE_ROW))
    action('up')
    wait_for('ControlGroup(9430).HasFocus()')
    action('up')
    wait_for('Control.HasFocus(9403)')


def test_genre_pick_dialog(home_page):
    focus(9102)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.genre.id))')
    before = prop('nc.genre.id')
    focus(GENRE_PICK)
    action('select')
    wait_for('Window.IsActive(selectdialog)')
    action('back')
    wait_for('!Window.IsActive(selectdialog)')
    assert prop('nc.genre.id') == before


TITLES = {'home': 9020, 'movies': 9020, 'shows': 9560, 'system': 9660}


@pytest.mark.parametrize('name', list(PAGES))
def test_home_netrunner_look(home_page, name):
    tab = PAGES[name][0]
    focus(tab)
    wait_for('Control.IsVisible({})'.format(TITLES[name]))
    screenshot('home-{}'.format(name))
    key = 'Control.GetLabel({})'.format(tab)
    label = info(key)[key]
    assert label and (label == label.upper() or '[UPPERCASE]' in label), label
