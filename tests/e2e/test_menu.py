import time
import pytest

from conftest import action, builtin, cond, info, wait_for

pytestmark = pytest.mark.e2e

MENU = 9100
TABS = {'home': 9101, 'movies': 9102, 'shows': 9103, 'search': 9104, 'system': 9105}


def focus_tab(name):
    builtin('SetFocus({})'.format(TABS[name]))
    wait_for('Control.HasFocus({})'.format(TABS[name]))


def open_menu_item(name):
    focus_tab(name)
    action('select')


def page():
    return info('Window(Home).Property(nc.page)')['Window(Home).Property(nc.page)'] or 'home'


def test_menu_reachable_with_menu_key(home):
    builtin('SetFocus(9202)')
    action('menu')
    wait_for('ControlGroup({}).HasFocus()'.format(MENU))


def test_up_from_spotlight_reaches_menu(home):
    builtin('SetFocus(9010)')
    wait_for('Control.HasFocus(9010)')
    action('up')
    wait_for('ControlGroup({}).HasFocus()'.format(MENU))


@pytest.mark.parametrize('name', ['movies', 'shows', 'search', 'system', 'home'])
def test_menu_focus_switches_page(home, name):
    focus_tab(name)
    assert page() == name


def test_menu_search(home):
    """A click on search goes to the search field, a click there opens the keyboard, which
    stays open (it closed again at once on the first click after Home loaded)."""
    open_menu_item('search')
    wait_for('Control.HasFocus(9750)')
    action('select')
    try:
        wait_for('Window.IsActive(virtualkeyboard)')
        time.sleep(2)
        assert cond('Window.IsActive(virtualkeyboard)')['Window.IsActive(virtualkeyboard)'], 'the keyboard closed'
    finally:
        action('back')




def test_search_page_finds_library_titles(home):
    focus_tab('search')
    builtin('NotifyAll(nightcity,search:Bulk 09)')
    wait_for('String.IsEqual(Window(Home).Property(nc.search),Bulk 09)')
    wait_for('Integer.IsGreater(Container(9701).NumItems,0)', timeout=15)
    assert info('Window(Home).Property(nc.search.recent.1)')['Window(Home).Property(nc.search.recent.1)'] == 'Bulk 09'
    builtin('SetFocus(9750)')
    action('down')
    wait_for('Control.HasFocus(9771)')
    action('down')
    wait_for('Control.HasFocus(9701)')
    from conftest import screenshot
    screenshot('search-page')


def test_search_rows_load_only_on_search_page(home):
    """The last term stays, but its rows (TMDb runs a plugin each) only load on the search page."""
    focus_tab('search')
    builtin('NotifyAll(nightcity,search:Bulk 09)')
    wait_for('Integer.IsGreater(Container(9701).NumItems,0)', timeout=15)
    focus_tab('movies')
    builtin('ReloadSkin()')
    wait_for('Window.IsActive(home)', timeout=20)
    time.sleep(3)
    assert info('Container(9721).NumItems')['Container(9721).NumItems'] in ('', '0')
    focus_tab('search')
    wait_for('Integer.IsGreater(Container(9701).NumItems,0)', timeout=15)


def test_search_recent_tab_searches_again(home):
    focus_tab('search')
    builtin('NotifyAll(nightcity,search:Kdev)')
    builtin('NotifyAll(nightcity,search:Bulk 09)')
    wait_for('String.IsEqual(Window(Home).Property(nc.search.recent.2),Kdev)')
    builtin('SetFocus(9772)')
    wait_for('Control.HasFocus(9772)')
    action('select')
    wait_for('String.IsEqual(Window(Home).Property(nc.search),Kdev)')
    wait_for('Integer.IsGreater(Container(9702).NumItems,0)', timeout=15)


def test_system_page_opens_settings(home):
    focus_tab('system')
    action('down')
    wait_for('Control.HasFocus(9601)')
    action('select')
    wait_for('Window.IsActive(settings) | Window.IsActive(playersettings)')
    action('back', delay=1)
    wait_for('Window.IsActive(home)')
    assert page() == 'system'


def test_keyboard_rows_reachable(home):
    """Review C1: down from the first key row walks through all rows to done/cancel."""
    open_menu_item('search')
    wait_for('Control.HasFocus(9750)')
    action('select')
    try:
        wait_for('Window.IsActive(virtualkeyboard)')
        action('down', 'down', 'down', 'down', 'down')
        assert info('System.CurrentControlId')['System.CurrentControlId'] == '300'
    finally:
        action('back')
