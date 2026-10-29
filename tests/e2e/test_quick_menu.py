"""Quick menu (Custom_1170_QuickMenu.xml) with real key events: Home held (the skin's keymap),
Kodi's power menu (S key), the icon next to the clock; Back or the same key closes it."""
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

OPEN = 'Window.IsActive(1170)'
ON_HOME_PAGE = ('Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),home) + '
                'Control.HasFocus(9101) + !System.HasActiveModalDialog')
MOVIE_ID = 1


def is_open():
    return cond(OPEN)[OPEN]


def press(button='homepage', keymap='KB', hold=0):
    """A key through Kodi's keymaps; a hold over Kodi's threshold (500 ms) is a long press."""
    rpc('Input.ButtonEvent', {'button': button, 'keymap': keymap, 'holdtime': hold})


def open_menu():
    builtin('ActivateWindow(1170)')
    wait_for('Control.HasFocus(1220)')
    time.sleep(0.3)  # a key in the first moment after opening gets lost


def closed():
    wait_for('!' + OPEN + ' + !Window.IsActive(shutdownmenu)')


@pytest.fixture
def quick(home):
    builtin('NotifyAll(nightcity,home_keymap)')
    builtin('ClearProperty(nc.quick.from,home)')
    time.sleep(1)
    yield
    if is_open():
        action('back', delay=0.5)
    closed()


PANEL = 'Control.IsVisible(9180)'
START = 9010  # where `home` leaves the focus


def on_panel(cid):
    """On Home the keys use the panel of Home, not the dialog."""
    return 'Control.HasFocus({}) + {} + !{}'.format(cid, PANEL, OPEN)


@pytest.mark.parametrize('button', ['homepage', 'browser_home', 'home'])
def test_home_held_opens_and_closes(quick, button):
    """Home keys go by several names: IR remotes on CoreELEC are keyboards, some send home. On
    Home the key goes to the icon next to the clock, which shows the menu; the same key again
    goes back to where the focus was."""
    press(button, hold=1500)
    wait_for(on_panel(9109))
    time.sleep(0.5)
    screenshot('quick-menu')
    press(button, hold=1500)
    wait_for('Control.HasFocus({}) + !{}'.format(START, PANEL))
    assert not is_open()


def test_home_short_still_goes_home(quick):
    builtin('SetFocus(9102)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),movies)')
    press()
    wait_for(ON_HOME_PAGE, timeout=5)
    assert not is_open()


def test_power_menu_toggles(quick):
    """Kodi's power menu leads here, again closes it (as an add-on or the power key opens it)."""
    rpc('GUI.ActivateWindow', {'window': 'shutdownmenu'})
    wait_for(on_panel(9109))
    rpc('GUI.ActivateWindow', {'window': 'shutdownmenu'})
    wait_for('Control.HasFocus({}) + !{}'.format(START, PANEL))


def test_s_key(quick):
    press('s')
    wait_for(on_panel(9109))
    press('s')
    wait_for('Control.HasFocus({}) + !{}'.format(START, PANEL))


@pytest.mark.parametrize('entry, page', [(9102, 'movies'), (9103, 'shows'), (9104, 'search')])
def test_keys_on_every_home_page(quick, entry, page):
    """The icon is on every page of Home: the keys use the panel there too."""
    builtin('SetFocus({})'.format(entry))
    wait_for('String.IsEqual(Window(Home).Property(nc.page),{})'.format(page))
    press('s')
    wait_for(on_panel(9109))
    press('s')
    wait_for('Control.HasFocus({}) + !{}'.format(entry, PANEL))


def test_key_on_the_icon_reached_by_hand_goes_to_the_page(quick):
    """With the menu shown because the cursor went to the icon, the key goes to the shown page's
    entry of the top menu: nothing to go back to."""
    builtin('SetFocus(9103)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),shows)')
    builtin('SetFocus(9109)')
    wait_for(on_panel(9109))
    press('s')
    wait_for('Control.HasFocus(9103) + !' + PANEL)


def closed_on(cid):
    """Back closed the menu: back where it was opened from, the panel hidden."""
    return 'Control.HasFocus({}) + !{} + !{}'.format(cid, PANEL, OPEN)


def test_back_goes_back_where_the_key_came_from(quick):
    press(hold=1500)
    wait_for(on_panel(9109))
    action('down', 'down')
    wait_for(on_panel(1220))
    action('back')
    wait_for(closed_on(START))
    assert info('Window(Home).Property(nc.page)')['Window(Home).Property(nc.page)'] == 'home'


def _settings_page():
    open_menu()
    action('down', 'down', delay=0.3)
    wait_for('Integer.IsEqual(Container(1230).CurrentItem,1)')
    action('select')
    closed()
    wait_for('Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),system) + '
             'Control.HasFocus(9601)')
    time.sleep(0.5)


@pytest.mark.parametrize('inside', [True, False], ids=['in-the-menu', 'on-the-icon'])
def test_back_on_the_settings_page(quick, inside):
    """Up from a settings row to the icon (and Down into the menu): Back lands on that row, the
    settings page still shown."""
    _settings_page()
    action('up')
    wait_for(on_panel(9109))
    if inside:
        action('down')
        wait_for(on_panel(1210))
    action('back')
    wait_for(closed_on(9601))
    assert info('Window(Home).Property(nc.page)')['Window(Home).Property(nc.page)'] == 'system'


@pytest.mark.parametrize('entry, way, inside', [(9101, 'left', True), (9104, 'right', False)])
def test_back_to_the_top_menu(quick, entry, way, inside):
    """Left off the first entry of the top menu, Right off the last: Back returns to it."""
    builtin('SetFocus({})'.format(entry))
    wait_for('Control.HasFocus({})'.format(entry))
    time.sleep(0.5)
    action(way)
    wait_for(on_panel(9109))
    if inside:
        action('down')
        wait_for(on_panel(1210))
    action('back')
    wait_for(closed_on(entry))




def test_icon_next_to_the_clock(quick):
    """The cursor on the icon shows the menu on Home (no dialog), Left and Right off it hide it,
    OK goes in."""
    builtin('SetFocus(9104)')
    wait_for('Control.HasFocus(9104) + !' + PANEL)
    action('right')
    wait_for('Control.HasFocus(9109) + ' + PANEL)
    assert not is_open()
    time.sleep(0.5)
    screenshot('quick-anchor')
    action('left')
    wait_for('Control.HasFocus(9104) + !' + PANEL)
    action('right')
    wait_for('Control.HasFocus(9109) + ' + PANEL)
    action('right')
    wait_for('Control.HasFocus(9101) + !' + PANEL)
    action('left')
    wait_for('Control.HasFocus(9109)')
    action('select')
    wait_for('Control.HasFocus(1210) + ' + PANEL)
    assert not is_open()


def test_menu_on_home_by_focus(quick):
    """Down goes into the menu, Up from its top comes out onto the icon, the menu still shown,
    Back closes it; the rows lead into each other as in the dialog."""
    builtin('SetFocus(9109)')
    wait_for('Control.HasFocus(9109) + ' + PANEL)
    action('down')
    wait_for('Control.HasFocus(1210)')
    action('down')
    wait_for('Control.HasFocus(1220) + ' + PANEL)
    time.sleep(0.5)
    screenshot('quick-panel-inside')
    action('down', 'down')  # two rows of tiles
    wait_for('Control.HasFocus(1230)')
    action('back')  # reached by no way that remembers: the shown page's own entry
    wait_for(closed_on(9101))
    builtin('SetFocus(9109)')
    wait_for('Control.HasFocus(9109) + ' + PANEL)
    action('down', 'down')
    wait_for('Control.HasFocus(1220)')
    builtin('SetFocus(1220,0,absolute)')
    action('up')
    wait_for('Control.HasFocus(1210)')
    action('up')
    wait_for('Control.HasFocus(9109) + ' + PANEL)
    assert not is_open()


def test_weather_tile_on_home_comes_back_to_the_icon(quick):
    """OK on the weather tile of the panel opens the weather (or its settings); Back lands on the
    icon with the menu shown, Back again where the menu was opened from."""
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101)')
    time.sleep(0.5)
    action('left')
    wait_for('Control.HasFocus(9109)')
    action('down')
    wait_for('Control.HasFocus(1210)')
    action('select')
    wait_for('Window.IsActive(weather) | Window.IsActive(servicesettings)')
    time.sleep(0.5)
    action('back', delay=1)
    wait_for('Window.IsActive(home) + Control.HasFocus(9109) + ' + PANEL)
    action('back')  # where the menu was opened from before
    wait_for(closed_on(9101))


def test_tiles_and_rows(quick):
    open_menu()
    assert info('Container(1220).NumItems')['Container(1220).NumItems'] == '6'
    for pos, condition in ((0, 'System.CanPowerDown'), (1, 'System.CanReboot'), (2, 'System.CanSuspend')):
        can = info('Container(1220).ListItemAbsolute({}).Property(can)'.format(pos))
        assert (list(can.values())[0] == '1') == cond(condition)[condition], condition
    action('up')
    wait_for('Control.HasFocus(1210)')
    screenshot('quick-weather')
    action('down', 'down', 'down')  # two rows of tiles
    wait_for('Control.HasFocus(1230)')
    action('right')
    wait_for('Control.HasFocus(1230) + Integer.IsEqual(Container(1230).CurrentItem,2)')
    screenshot('quick-links')


def test_power_off_unavailable_says_so(quick):
    if cond('System.CanPowerDown')['System.CanPowerDown']:
        pytest.skip('this Kodi can power off')
    open_menu()
    action('select', delay=1)
    wait_for('Window.IsActive(notification)')
    assert not cond('Window.IsActive(yesnodialog)')['Window.IsActive(yesnodialog)']
    screenshot('quick-cannot')


def test_timer_sets_and_cancels(quick):
    open_menu()
    action('right', 'right', 'down', delay=0.3)
    wait_for('Integer.IsEqual(Container(1220).CurrentItem,6)')
    action('select')
    wait_for('Window.IsActive(numericinput)')
    action('back', delay=0.5)  # no minutes: no timer
    wait_for(OPEN)
    builtin('AlarmClock(shutdowntimer,Shutdown(),30,silent)')
    try:
        wait_for('System.HasAlarm(shutdowntimer)')
        time.sleep(1.2)
        screenshot('quick-timer')
        action('select')
        wait_for('!System.HasAlarm(shutdowntimer)')
    finally:
        builtin('CancelAlarm(shutdowntimer,true)')


def test_weather_without_addon_opens_its_settings(quick):
    if cond('Weather.IsFetched')['Weather.IsFetched']:
        pytest.skip('a weather add-on is set up')
    open_menu()
    action('up')
    wait_for('Control.HasFocus(1210)')
    action('select')
    wait_for('Window.IsActive(servicesettings)')
    time.sleep(1)
    screenshot('quick-weather-settings')
    action('back', delay=1)


def test_up_from_the_top_to_the_icon(quick):
    """Up from the weather tile goes onto the icon next to the clock, also when the held Home key
    showed the menu from a row."""
    builtin('SetFocus(9101)')
    wait_for('Control.HasFocus(9101)')
    press(hold=1500)
    wait_for(on_panel(9109))
    action('down')
    wait_for('Control.HasFocus(1210)')
    action('up')
    wait_for(on_panel(9109))


def test_settings_link(quick):
    """The settings page, on its first settings group; Up goes to the quick menu icon."""
    open_menu()
    action('down', 'down', delay=0.3)
    wait_for('Integer.IsEqual(Container(1230).CurrentItem,1)')
    action('select')
    closed()
    wait_for('Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),system) + '
             'Control.HasFocus(9601)')
    time.sleep(1)
    screenshot('settings-page')
    action('up')
    wait_for('Control.HasFocus(9109)')
    assert info('Window(Home).Property(nc.page)')['Window(Home).Property(nc.page)'] == 'system'


def _over_the_info_page():
    builtin('ActivateWindow(movieinformation,videodb://movies/titles/{}/,return)'.format(MOVIE_ID))
    wait_for('Window.IsActive(movieinformation)')
    time.sleep(0.5)
    press(hold=1500)
    wait_for(OPEN)
    wait_for('Control.HasFocus(1220)')
    time.sleep(0.3)


@pytest.mark.parametrize('item, target', [
    (0, 'Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),system) + Control.HasFocus(9601)'),
    (1, 'Window.IsActive(filemanager)')])
def test_links_over_the_info_page(quick, item, target):
    """The info page is a modal dialog: the link closes it, the target window opens in front."""
    _over_the_info_page()
    builtin('SetFocus(1230,{},absolute)'.format(item))
    wait_for('Integer.IsEqual(Container(1230).CurrentItem,{})'.format(item + 1))
    action('select')
    closed()
    wait_for(target + ' + !Window.IsActive(movieinformation)', timeout=5)
    assert not info('Window(Home).Property(nc.go)')['Window(Home).Property(nc.go)']
    if item != 1:
        action('back', delay=1)


def test_over_the_player(quick):
    rpc('Player.Open', {'item': {'movieid': MOVIE_ID}})
    try:
        wait_for('Player.HasVideo', timeout=20)
        wait_for('Window.IsActive(fullscreenvideo)')
        time.sleep(1)
        press(hold=1500)
        wait_for(OPEN)
        time.sleep(0.5)
        screenshot('quick-player')
        action('back')
        closed()
        assert cond('Window.IsActive(fullscreenvideo)')['Window.IsActive(fullscreenvideo)']
    finally:
        rpc('Player.Stop', {'playerid': 1})
        time.sleep(1)
        rpc('VideoLibrary.SetMovieDetails', {'movieid': MOVIE_ID, 'resume': {'position': 0, 'total': 0}})
