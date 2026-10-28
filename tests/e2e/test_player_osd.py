"""Player OSD: skip forward, panels that step along the button row, the video panel, the seek
delta while stepping and the OSD on pause. Uses the tracks clip (three chapters)."""
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for
from test_playback import tracks  # noqa: F401 (fixture)

pytestmark = pytest.mark.e2e


def focus(control):
    builtin('SetFocus({})'.format(control))
    wait_for('Control.HasFocus({})'.format(control))


def close_osd():
    # Dialog.Close through kodi-send hung here while the OSD's track watcher ran; back closes it
    action('back')
    wait_for('!Window.IsActive(videoosd)')


def test_skip_forward_goes_to_the_next_chapter(tracks):
    chapter = int(info('Player.Chapter')['Player.Chapter'])
    focus(611)
    action('select', delay=1)
    wait_for('Integer.IsGreater(Player.Chapter,{})'.format(chapter))


def test_panels_step_along_the_button_row(tracks):
    focus(605)
    action('up')
    wait_for('Control.HasFocus(651)')
    action('left')
    wait_for('Control.HasFocus(611)')
    focus(605)
    action('up')
    wait_for('Control.HasFocus(651)')
    action('right')
    wait_for('Control.HasFocus(606)')
    wait_for('Control.IsVisible(652)')
    action('up')
    wait_for('Control.HasFocus(652)')
    action('right')
    wait_for('Control.HasFocus(607)')
    wait_for('Control.IsVisible(653)')
    action('up')
    wait_for('Control.HasFocus(653)')
    action('right')
    wait_for('Control.HasFocus(610)')  # no chapters button: the chapter row is Down from the bar


def test_video_panel_opens_video_settings(tracks):
    focus(607)
    wait_for('Control.IsVisible(653)')
    action('up')
    wait_for('Control.HasFocus(653)')
    screenshot('osd-video-panel')
    action('down')
    wait_for('Control.HasFocus(607)')
    action('select')
    wait_for('Control.HasFocus(653)')
    action('select', delay=1)
    try:
        wait_for('Window.IsActive(osdvideosettings)')
    finally:
        action('back', delay=1)


def test_seek_delta_while_stepping(tracks):
    """The step size is there while the steps come in, before the seek runs; only the seek line
    shows, not the OSD."""
    close_osd()
    rpc('Player.Seek', {'playerid': 1, 'value': {'seconds': 0}})
    time.sleep(1)
    for _ in range(2):
        rpc('Input.ExecuteAction', {'action': 'stepforward'})
    seeking = info('Player.SeekStepSize')['Player.SeekStepSize']
    assert seeking.startswith('+')
    assert cond('Player.Seeking')['Player.Seeking']
    assert not cond('Window.IsActive(videoosd)')['Window.IsActive(videoosd)']
    screenshot('seek-stepping')


def test_pause_opens_the_osd_once(tracks):
    close_osd()
    action('pause')
    wait_for('Window.IsActive(videoosd)')
    wait_for('Control.HasFocus(602)')
    screenshot('pause-osd')
    # closed by hand while paused, it stays closed
    action('back', delay=1.5)
    assert not cond('Window.IsActive(videoosd)')['Window.IsActive(videoosd)']
    assert cond('Player.Paused')['Player.Paused']
    action('pause')
    wait_for('!Player.Paused')
    wait_for('String.IsEmpty(Window(Home).Property(nc.osd.paused))')
    # opened by the pause, it closes again when playback goes on
    action('pause')
    wait_for('Window.IsActive(videoosd)')
    action('pause')
    wait_for('!Player.Paused')
    wait_for('!Window.IsActive(videoosd)')
