import pytest

from conftest import action, builtin, cond, kodi_log, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

WINDOWS = ['settings', 'skinsettings', 'systeminfo', 'addonbrowser', 'filemanager', 'eventlog']


def active(window):
    key = 'Window.IsActive({})'.format(window)
    return cond(key)[key]


@pytest.mark.parametrize('window', WINDOWS)
def test_dialogs_open(home, window):
    rpc('GUI.ActivateWindow', {'window': window})
    try:
        wait_for('Window.IsActive({})'.format(window))
        screenshot('window-' + window)
    finally:
        action('back', delay=1)


@pytest.fixture
def movie_list(home):
    builtin('ActivateWindow(Videos,videodb://movies/titles/,return)')
    wait_for('Window.IsActive(videos)')
    wait_for('Integer.IsGreater(Container.NumItems,0)')
    builtin('SetFocus(50,1,absolute)')
    yield
    for _ in range(3):
        if not cond('System.HasActiveModalDialog')['System.HasActiveModalDialog']:
            break
        action('back', delay=1)


def test_contextmenu(movie_list):
    action('contextmenu', delay=1)
    wait_for('Window.IsActive(contextmenu)')
    screenshot('contextmenu')


def test_yesno(movie_list):
    action('delete', delay=1)
    wait_for('Window.IsActive(yesnodialog)')
    screenshot('yesno')
    action('back', delay=1)
    assert not active('yesnodialog')


def test_notification(home):
    rpc('GUI.ShowNotification', {'title': 'test', 'message': 'nightcity'})
    wait_for('Window.IsVisible(notification)')
    screenshot('notification')


LOG_ERRORS = ['Skin has invalid include', 'Unable to load', 'failed to load', 'CGUIWindowManager::Activate']


@pytest.mark.parametrize('pattern', LOG_ERRORS)
def test_no_skin_errors_in_log(pattern):
    # kdev log -g is a case-insensitive substring match over the current Kodi run
    found = kodi_log(pattern)
    assert not found.strip(), found


def test_keyboard(home):
    builtin('VideoLibrary.Search')
    try:
        wait_for('Window.IsActive(virtualkeyboard)')
        screenshot('keyboard')
    finally:
        action('back', delay=1)


def test_settings_dropdown_marks_value(home):
    """Open a list setting (interface colours): the select dialog puts the cursor on the current
    value, and that row is marked."""
    builtin('ActivateWindow(interfacesettings)')
    try:
        wait_for('Window.IsActive(interfacesettings)')
        action('right', delay=0.5)
        for _ in range(12):
            if cond('String.Contains(System.CurrentControl,Colours)')['String.Contains(System.CurrentControl,Colours)']:
                break
            action('down', delay=0.4)
        else:
            raise AssertionError('no Colours setting')
        action('select', delay=1)
        wait_for('Window.IsActive(selectdialog)')
        wait_for('Container(3).ListItem.IsSelected')
        screenshot('select-current')
    finally:
        for _ in range(3):
            action('back', delay=0.8)
