import pytest

from conftest import window_files
from navigation import dead_ends, unreachable

# Controls a D-pad never needs: off-screen data lists, hidden setting templates Kodi clones,
# and controls Kodi focuses itself.
EXPECTED = {
    'Home.xml': {'9000', '9001', '9221', '9224', '9422', '9521', '9523', '9721', '9722', '9723', '9724', '9725', '9002', '9822'},  # spotlight data lists (info parks focus there), loaders
    'DialogSettings.xml': {str(i) for i in range(7, 16)},
    'DialogAddonSettings.xml': {str(i) for i in range(7, 16)},
    'SettingsCategory.xml': {str(i) for i in range(7, 16)},
    'SettingsSystemInfo.xml': {'99', '101'},  # PVR and donate, hidden
    'DialogAddonInfo.xml': {'50'},  # screenshots, not shown
    'FileBrowser.xml': {'451'},  # thumbs view, not used
    'DialogVideoInfo.xml': {'5901', '9006', '9098'},  # off-screen library copy, invisible TMDb menu list of a TMDb title (Timers.xml focuses 9006), stand-in on the way back in a chain
    'Custom_1141_OSDCast.xml': {'6599'},  # off-screen biography of the focused person
    'VideoOSD.xml': {'699'},  # off-screen stand-in that opens the chapter row after a chain
}


def windows_with_focus():
    return [p.name for p in window_files() if '<defaultcontrol' in p.read_text() or '<menucontrol' in p.read_text()]


@pytest.mark.parametrize('name', windows_with_focus())
def test_every_control_reachable_by_remote(name):
    assert set(unreachable(name)) - EXPECTED.get(name, set()) == set()


@pytest.mark.parametrize('name', windows_with_focus())
def test_no_dead_ends(name):
    assert dead_ends(name) == []
