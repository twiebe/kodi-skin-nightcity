import time

import pytest
from PIL import Image

from conftest import builtin, cond, kodi_log, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e


def setting(name):
    return rpc('Settings.GetSettingValue', {'setting': name})['value']


def set_setting(name, value):
    rpc('Settings.SetSettingValue', {'setting': name, 'value': value})
    time.sleep(2)
    wait_for('Window.IsActive(home)', timeout=20)


def test_active_skin(home):
    # The setting alone is not enough: when the skin is disabled at startup Kodi falls back to
    # Estuary but keeps reporting skin.nightcity. The home rows viewport 9210 only exists in this skin.
    assert setting('lookandfeel.skin') == 'skin.nightcity'
    wait_for('Control.IsVisible(9210)')


def test_home_active(home):
    assert cond('Window.IsActive(home)')['Window.IsActive(home)']


def test_palette_switch(home):
    pixels = {}
    try:
        for palette in ('catppuccin', 'tokyonight', 'SKINDEFAULT'):
            set_setting('lookandfeel.skincolors', palette)
            # status bar background, left of the title text
            pixels[palette] = Image.open(screenshot('palette-' + palette)).convert('RGB').getpixel((10, 10))
    finally:
        set_setting('lookandfeel.skincolors', 'SKINDEFAULT')
    assert len(set(pixels.values())) == 3, pixels


def test_fonts_load(home):
    assert setting('lookandfeel.font') == 'Default'
    screenshot('fonts')
    assert not kodi_log('Font.*(error|failed|Unable)').strip()
