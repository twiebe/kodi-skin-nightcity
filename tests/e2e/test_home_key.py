"""The Home key (keymap 0_skin.nightcity.xml: ActivateWindow(1160)) always lands on the home
page: from another page of Home, from the info page, from the player."""
import os
import time

import pytest

from conftest import KODI_DEV, builtin, rpc, wait_for

pytestmark = pytest.mark.e2e

MOVIE_ID = 1  # "Kdev Alpha"
ON_HOME_PAGE = ('Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),home) + '
                'Control.HasFocus(9101) + !System.HasActiveModalDialog')
ON_MOVIES_PAGE = 'String.IsEqual(Window(Home).Property(nc.page),movies)'


def press_home(button='homepage', keymap='KB'):
    """A real key press through the keymap: homepage of keyboards and box remotes."""
    rpc('Input.ButtonEvent', {'button': button, 'keymap': keymap})


def _on_movies_page():
    builtin('SetFocus(9102)')
    wait_for(ON_MOVIES_PAGE)
    builtin('SetFocus(9050)')
    time.sleep(0.5)


def _stop():
    if rpc('Player.GetActivePlayers'):
        rpc('Player.Stop', {'playerid': 1})
        time.sleep(1)
    rpc('VideoLibrary.SetMovieDetails', {'movieid': MOVIE_ID, 'resume': {'position': 0, 'total': 0}})


def test_home_key_on_another_page(home):
    _on_movies_page()
    press_home()
    wait_for(ON_HOME_PAGE, timeout=5)


def test_home_key_on_the_info_page(home):
    _on_movies_page()
    builtin('ActivateWindow(movieinformation,videodb://movies/titles/{}/,return)'.format(MOVIE_ID))
    wait_for('Window.IsActive(movieinformation)')
    press_home()
    wait_for(ON_HOME_PAGE, timeout=5)


def test_home_key_in_the_player(home):
    _on_movies_page()
    rpc('Player.Open', {'item': {'movieid': MOVIE_ID}})
    try:
        wait_for('Player.HasVideo', timeout=20)
        wait_for('Window.IsActive(fullscreenvideo)')
        press_home()
        wait_for(ON_HOME_PAGE, timeout=5)
    finally:
        _stop()


def test_cec_home_key(home):
    """rootmenu: the Home key of TV remotes (CEC) and MCE remotes."""
    _on_movies_page()
    press_home('rootmenu', 'R1')
    wait_for(ON_HOME_PAGE, timeout=5)


def test_startup_writes_the_keymap():
    """Written at startup into the profile's keymaps, with the Home keys on the home dialog."""
    instance = os.environ.get('KDEV_INSTANCE')
    data = KODI_DEV / 'instances' / instance / 'data' if instance else KODI_DEV / 'data'
    keymap = data / 'kodi' / 'userdata' / 'keymaps' / '0_skin.nightcity.xml'
    assert '<homepage>ActivateWindow(1160)</homepage>' in keymap.read_text()


def test_startup_writes_the_back_keymap():
    """Esc and the other keys of PreviousMenu are Back on info pages (nightcity.BACK_KEYMAP)."""
    instance = os.environ.get('KDEV_INSTANCE')
    data = KODI_DEV / 'instances' / instance / 'data' if instance else KODI_DEV / 'data'
    keymap = data / 'kodi' / 'userdata' / 'keymaps' / '0_skin.nightcity.back.xml'
    assert '<escape>Back</escape>' in keymap.read_text()


# --- without the home page: the first page shown takes its place ------------------------------

ON_FIRST_PAGE = ('Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),movies) + '
                 'Control.HasFocus(9102) + !System.HasActiveModalDialog + !Control.IsVisible(9101)')


@pytest.fixture
def no_home_page(home):
    builtin('Skin.SetBool(nc.menu.hide.home)')
    try:
        yield
    finally:
        builtin('Skin.Reset(nc.menu.hide.home)')
        builtin('ReplaceWindow(Home)')
        wait_for('Window.IsActive(home)')
        builtin('SetFocus(9101)')
        wait_for('Control.HasFocus(9101)')


def test_home_key_without_the_home_page(no_home_page):
    builtin('SetFocus(9103)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),shows)')
    press_home()
    wait_for(ON_FIRST_PAGE, timeout=5)


def test_home_opens_on_the_first_page_without_home(no_home_page):
    """As after startup: Home opens without a page and shows the first page shown."""
    builtin('ActivateWindow(settings)')
    wait_for('Window.IsActive(settings)')
    builtin('ClearProperty(nc.page,home)')
    builtin('ReplaceWindow(Home)')
    wait_for(ON_FIRST_PAGE, timeout=5)


def test_the_icon_wraps_round_to_the_first_page_without_home(no_home_page):
    builtin('SetFocus(9109)')
    wait_for('Control.HasFocus(9109)')
    rpc('Input.Right')
    wait_for('Control.HasFocus(9102) + String.IsEqual(Window(Home).Property(nc.page),movies)', timeout=5)
