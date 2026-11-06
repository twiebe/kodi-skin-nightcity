"""Switching between Nightcity and Confuse in a running Kodi. Both skins share scripts/nightcity.py,
and the service of the old skin must hand over: it ends and the new skin's service listens.
Needs both skins mounted (tools/kodidev_setup.py); each test ends on the skin it started on."""
import pathlib
import re
import time

import pytest

from conftest import OTHER_SKIN, SKIN_ID, _data, builtin, kodi_log, rpc, wait_for

pytestmark = pytest.mark.e2e

SERVICE = 'Window(Home).Property(nc.service)'
HOME_KEYMAP = '0_skin.nightcity.xml'
BACK_KEYMAP = '0_skin.nightcity.back.xml'
HOME_KEY_OFF = 'nc.homekey.off'


def keymap(name):
    return pathlib.Path(_data()) / 'kodi' / 'userdata' / 'keymaps' / name


def wait_for_file(path, exists, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        if path.exists() == exists:
            return
        time.sleep(0.1)
    raise AssertionError('{} still {}'.format(path, 'missing' if exists else 'there'))


def loaded_skin():
    """The skin Kodi loaded last: lookandfeel.skin changes before the skin does, and goes back when
    the skin fails to load."""
    return re.findall(r'load skin from: \S*/(skin\.[a-z]+)', kodi_log('load skin from'))[-1]


def switch_to(skin):
    """Kodi asks whether to keep a new skin and goes back to the old one if nobody answers. The
    Jellyfin add-on reloads the skin after a sync: that closes the question, which counts as no, so
    a Kodi that just started may need a second try."""
    for _ in range(3):
        rpc('Settings.SetSettingValue', {'setting': 'lookandfeel.skin', 'value': skin})
        try:
            wait_for('Window.IsActive(yesnodialog)', timeout=15)
            builtin('SendClick(yesnodialog,11)')
            wait_for('!Window.IsActive(yesnodialog)', timeout=10)
        except AssertionError:
            pass
        time.sleep(2)
        if rpc('Settings.GetSettingValue', {'setting': 'lookandfeel.skin'})['value'] == skin:
            break
    wait_for('Window.IsActive(home)', timeout=30)
    assert loaded_skin() == skin
    # the service of the skin before needs a second to notice, and clears nc.service then
    time.sleep(3)
    wait_for('!String.IsEmpty({})'.format(SERVICE), timeout=30)


def service_starts(skin):
    """How often Kodi ran a script from the folder of SKIN: the service of the skin before would
    answer as well if it stayed on."""
    return len(re.findall('entering source directory \\S*/{}/'.format(re.escape(skin)),
                          kodi_log('entering source directory')))


def service_answers():
    """A skin's NotifyAll reaches a service: home_keymap writes the back keymap again."""
    path = keymap(BACK_KEYMAP)
    path.unlink(missing_ok=True)
    builtin('NotifyAll(nightcity,home_keymap)')
    wait_for_file(path, True)


@pytest.fixture
def on_own_skin(home):
    rpc('Addons.SetAddonEnabled', {'addonid': OTHER_SKIN, 'enabled': True})
    yield
    if loaded_skin() != SKIN_ID:
        switch_to(SKIN_ID)


def test_switching_skins_leaves_a_working_service(on_own_skin):
    for skin in (OTHER_SKIN, SKIN_ID):
        before = service_starts(skin)
        switch_to(skin)
        wait_for('Control.IsVisible(9210)')  # the rows of Home
        assert service_starts(skin) > before, 'no script of {} started'.format(skin)
        service_answers()


def test_home_key_follows_the_setting_of_the_new_skin(on_own_skin):
    """Skin settings are per skin, so the keymap has to change with the skin, without a click."""
    switch_to(OTHER_SKIN)
    builtin('Skin.SetBool({})'.format(HOME_KEY_OFF))
    builtin('NotifyAll(nightcity,home_keymap)')
    wait_for_file(keymap(HOME_KEYMAP), False)
    try:
        switch_to(SKIN_ID)
        wait_for_file(keymap(HOME_KEYMAP), True)
        switch_to(OTHER_SKIN)
        wait_for_file(keymap(HOME_KEYMAP), False)
    finally:
        if loaded_skin() != OTHER_SKIN:
            switch_to(OTHER_SKIN)
        builtin('Skin.Reset({})'.format(HOME_KEY_OFF))
        switch_to(SKIN_ID)
    wait_for_file(keymap(HOME_KEYMAP), True)
