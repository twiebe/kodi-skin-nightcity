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
    time.sleep(1)
    yield
    if is_open():
        action('back', delay=0.5)
    closed()


def test_home_held_opens_and_closes(quick):
    press(hold=1500)
    wait_for(OPEN)
    wait_for('Control.HasFocus(1220)')
    time.sleep(0.5)
    screenshot('quick-menu')
    press(hold=1500)
    closed()


def test_home_short_still_goes_home(quick):
    builtin('SetFocus(9102)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),movies)')
    press()
    wait_for(ON_HOME_PAGE, timeout=5)
    assert not is_open()


def test_power_menu_toggles(quick):
    """Kodi's power menu leads here, again closes it (as an add-on or the power key opens it)."""
    rpc('GUI.ActivateWindow', {'window': 'shutdownmenu'})
    wait_for(OPEN)
    rpc('GUI.ActivateWindow', {'window': 'shutdownmenu'})
    closed()


def test_s_key(quick):
    press('s')
    wait_for(OPEN)
    press('s')
    closed()


def test_back_closes(quick):
    press(hold=1500)
    wait_for(OPEN)
    action('back')
    closed()
    assert cond('Window.IsActive(home)')['Window.IsActive(home)']


def test_icon_next_to_the_clock(quick):
    builtin('SetFocus(9105)')
    wait_for('Control.HasFocus(9105)')
    action('right')
    wait_for('Control.HasFocus(9109)')
    screenshot('quick-anchor')
    action('left')
    wait_for('Control.HasFocus(9105)')
    action('right')
    wait_for('Control.HasFocus(9109)')
    action('select')
    wait_for(OPEN)


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


def test_system_link(quick):
    open_menu()
    action('down', 'down', 'right', delay=0.3)
    wait_for('Integer.IsEqual(Container(1230).CurrentItem,2)')
    action('select')
    closed()
    wait_for('Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),system) + '
             'Control.HasFocus(9105)')
    time.sleep(1)
    screenshot('system-page')


def test_settings_link(quick):
    open_menu()
    action('down', 'down', 'select', delay=0.4)
    wait_for('Window.IsActive(settings)')
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
