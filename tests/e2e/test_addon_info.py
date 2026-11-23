import pytest

from conftest import action, builtin, cond, info, screenshot, wait_for

pytestmark = pytest.mark.e2e

# the pills of DialogAddonInfo.xml's button row (Kodi's ids): configure, update, enable/disable,
# install/uninstall, dependencies, versions, open
PILLS = (9, 8, 6, 7, 14, 10, 12)
ADDON_ID = 'ListItem.Property(Addon.ID)'


@pytest.fixture
def skin_info(home):
    """The add-on dialog of the skin in use: Kodi disables some of its buttons (no uninstall nor
    disable of the skin that runs)."""
    builtin('ActivateWindow(addonbrowser,addons://user/xbmc.gui.skin/,return)')
    wait_for('Window.IsActive(addonbrowser)')
    wait_for('Integer.IsGreater(Container.NumItems,0)')
    for _ in range(20):
        if info(ADDON_ID)[ADDON_ID] == 'skin.nightcity':
            break
        action('down')
    assert info(ADDON_ID)[ADDON_ID] == 'skin.nightcity'
    action('select', delay=1)
    wait_for('Window.IsActive(addoninformation)')
    yield
    for _ in range(3):
        if not cond('Window.IsActive(addoninformation)')['Window.IsActive(addoninformation)']:
            break
        action('back', delay=1)


def test_disabled_pills_grey_out(skin_info):
    states = cond(*['Control.IsEnabled({})'.format(i) for i in PILLS])
    disabled = [i for i in PILLS if not states['Control.IsEnabled({})'.format(i)]]
    # Kodi disables some of them for the skin in use; the pills show it (text_mute, Includes_Base.xml
    # PillButton) and the focus skips them
    assert disabled
    screenshot('addon-info-disabled')
    for i in disabled:
        key = 'Control.HasFocus({})'.format(i)
        builtin('SetFocus({})'.format(i))
        assert not cond(key)[key]
