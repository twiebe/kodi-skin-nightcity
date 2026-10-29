"""Player controls that hide by themselves (skin settings, Player; Timers.xml nc_osd_hide), on by
default: with a 3 s delay the OSD closes while the video plays, stays while paused and
closes 3 s after playback goes on; switched off it stays. The delay slider in the skin settings
moves a second per left or right while taken. The plot under the title follows its switch.
Uses the tracks clip and a library movie."""
import time

import pytest
from PIL import Image

from conftest import action, builtin, cond, info, screenshot, wait_for
from test_playback import playing, tracks  # noqa: F401 (fixtures)

pytestmark = pytest.mark.e2e


def osd_up():
    return cond('Window.IsActive(videoosd)')['Window.IsActive(videoosd)']


def skin_string(name):
    return info('Skin.String({})'.format(name))['Skin.String({})'.format(name)]


@pytest.fixture
def autohide():
    builtin('Skin.Reset(nc.osd.autohide.off)')
    builtin('Skin.SetString(nc.osd.hide.secs,3)')
    builtin('Skin.SetString(nc.osd.hide.wait,2)')
    yield
    for name in ('secs', 'wait', 'from', 'to'):
        builtin('Skin.Reset(nc.osd.hide.{})'.format(name))


def test_osd_hides_while_playing_stays_while_paused(autohide, tracks):
    # a key holds it open: the delay counts from the last key
    for _ in range(3):
        start = time.time()
        action('right', delay=1.2)
        assert osd_up()
    wait_for('!Window.IsActive(videoosd)', timeout=8)
    assert 2.5 <= time.time() - start <= 5.5
    assert not cond('Window.IsActive(videobookmarks)')['Window.IsActive(videobookmarks)']
    # paused, the OSD stays (an OSD key during its close animation would close it again)
    time.sleep(0.5)
    action('osd', delay=1)
    wait_for('Window.IsActive(videoosd)')
    action('pause')
    wait_for('Player.Paused')
    time.sleep(5)
    assert osd_up()
    # playing on, it closes the delay later
    start = time.time()
    action('pause')
    wait_for('!Player.Paused')
    wait_for('!Window.IsActive(videoosd)', timeout=8)
    assert 2.5 <= time.time() - start <= 5.5


def test_osd_hides_with_its_rows(autohide, tracks):
    action('down', delay=1)
    wait_for('Window.IsActive(videobookmarks)')
    wait_for('!Window.IsActive(videoosd) + !Window.IsActive(videobookmarks)', timeout=8)


@pytest.fixture
def autohide_off():
    builtin('Skin.SetBool(nc.osd.autohide.off)')
    yield
    builtin('Skin.Reset(nc.osd.autohide.off)')


def test_osd_stays_while_switched_off(autohide_off, tracks):
    time.sleep(10)
    assert osd_up()


def changed_pixels(before, after, box):
    """Pixels that differ clearly between two screenshots within BOX (1080p coordinates)."""
    one, two = Image.open(before).convert('L'), Image.open(after).convert('L')
    scale = one.width / 1920
    box = [int(v * scale) for v in box]
    return sum(1 for a, b in zip(one.crop(box).tobytes(), two.crop(box).tobytes()) if abs(a - b) > 40)


# with the OSD up: the plot (textbox 420 of the seek bar dialog, which JSON-RPC cannot ask
# about: Control.IsVisible looks at the OSD) and the title above it
PLOT = (296, 646, 296 + 900, 646 + 116)
TITLE = (296, 520, 296 + 900, 520 + 60)


def test_plot_follows_its_switch(playing):
    assert info('VideoPlayer.Plot')['VideoPlayer.Plot']
    # paused, so only the switch changes the picture; the pause opens the OSD
    action('pause')
    wait_for('Player.Paused + Window.IsActive(videoosd)')
    time.sleep(1)
    shown = screenshot('osd-plot-on')
    builtin('Skin.SetBool(nc.osd.plot.off)')
    try:
        time.sleep(0.5)
        hidden = screenshot('osd-plot-off')
    finally:
        builtin('Skin.Reset(nc.osd.plot.off)')
    assert changed_pixels(shown, hidden, PLOT) > 300
    assert changed_pixels(shown, hidden, TITLE) < 30


def test_delay_slider(home):
    builtin('Skin.Reset(nc.osd.hide.secs)')
    try:
        builtin('ActivateWindow(SkinSettings)')
        wait_for('Window.IsActive(skinsettings)')
        # the page writes the default delay
        wait_for('String.IsEqual(Skin.String(nc.osd.hide.secs),8)')
        builtin('SetFocus(9006)')
        wait_for('Control.HasFocus(9006) + Control.IsVisible(700)')
        action('right')
        wait_for('ControlGroup(700).HasFocus()')
        builtin('SetFocus(712)')
        wait_for('Control.HasFocus(712)')
        # not taken, right does nothing and left goes back to the category
        action('right', delay=0.8)
        assert skin_string('nc.osd.hide.secs') == '8'
        action('select')
        wait_for('!String.IsEmpty(Window.Property(nc.hp.slide))')
        for _ in range(2):
            action('right', delay=0.6)
        wait_for('String.IsEqual(Skin.String(nc.osd.hide.secs),10)')
        assert [skin_string('nc.osd.hide.' + n) for n in ('wait', 'from', 'to')] == ['9', '24', '32']
        screenshot('osd-autohide-settings')
        action('left', delay=0.6)
        wait_for('String.IsEqual(Skin.String(nc.osd.hide.secs),9)')
        assert cond('Control.HasFocus(712)')['Control.HasFocus(712)']
        action('select')
        wait_for('String.IsEmpty(Window.Property(nc.hp.slide))')
        action('left')
        wait_for('Control.HasFocus(9006)')
    finally:
        for name in ('secs', 'wait', 'from', 'to'):
            builtin('Skin.Reset(nc.osd.hide.{})'.format(name))
