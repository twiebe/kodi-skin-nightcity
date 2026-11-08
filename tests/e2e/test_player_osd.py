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
    # IsActive is false once the close animation starts; a key sent before it ends is dropped
    # ("ignoring action ... closing animation is running"), so wait until the OSD is gone
    wait_for('!Window.IsVisible(videoosd)')


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


def test_button_rows_wrap_around(tracks):
    """Left on the far left control lands on the far right one, Right there back on the far left."""
    focus(601)
    action('left')
    wait_for('Control.HasFocus(610)')
    action('right')
    wait_for('Control.HasFocus(601)')


def test_moving_between_the_rows_lands_on_the_neighbour(tracks):
    """Not on the button that had the focus last in the other row: Kodi's groups remember it."""
    focus(607)
    focus(611)
    action('right')
    # info shows only for a title it has a page of; then subtitles is the first of the row
    first = 612 if cond('Control.IsVisible(612)')['Control.IsVisible(612)'] else 605
    wait_for('Control.HasFocus({})'.format(first))
    focus(602)
    focus(first)
    action('left')
    wait_for('Control.HasFocus(611)')


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


def test_chapter_row_after_a_chain_focuses_the_chapters(tracks):
    """A chain from the cast row ends with the chapter row reopened and the cast row over it
    (nc.osd.ret and nc.osd.chain, set as the chain leaves them). Closing the cast row shows the
    chapters with the focus on them; it used to stay on a stand-in out of sight. The clip has no
    cast row, so the test opens and closes it itself."""
    focus(602)
    builtin('SetProperty(nc.osd.ret,1,home)')
    builtin('SetProperty(nc.osd.chain,1,home)')
    action('down')
    wait_for('Window.IsActive(1141)', timeout=5)
    builtin('Dialog.Close(1141)')
    wait_for('Window.IsActive(videobookmarks) + !Window.IsVisible(1141) + Control.HasFocus(11)', timeout=5)
    action('up')
    wait_for('Control.HasFocus(2)')


def press(button, hold=0):
    """A key through Kodi's keymaps; a hold over Kodi's threshold (500 ms) is a long press."""
    rpc('Input.ButtonEvent', {'button': button, 'keymap': 'KB', 'holdtime': hold})


def _rows(cast):
    """From the bar's skip button (not the controls' first) Down to the chapter row and, with CAST,
    on to the cast row. The clip has no cast, so the test opens that row itself. The back keymap
    (scripts/nightcity.py BACK_KEYMAP) is written anew first, as the service does at startup."""
    builtin('NotifyAll(nightcity,home_keymap)')
    time.sleep(1)
    focus(611)
    action('down')
    wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(11)', timeout=5)
    if cast:
        builtin('ActivateWindow(1141)')
        wait_for('Window.IsActive(1141)', timeout=5)
    time.sleep(0.3)  # a key in the first moment after opening gets lost


CONTROLS = ('Window.IsActive(videoosd) + !Window.IsVisible(videobookmarks) + !Window.IsVisible(1141)'
            ' + Control.HasFocus(602)')


@pytest.mark.parametrize('cast', [False, True], ids=['chapters', 'cast'])
@pytest.mark.parametrize('key', ['backspace', 'escape'])
def test_back_held_in_the_rows_goes_to_the_controls(tracks, cast, key):
    """Back held in the chapter or the cast row: the player's controls on their own first button
    (play or resume), as Back held in a chain from the cast row (back_to_start). It went one row
    up like a single Back."""
    _rows(cast)
    press(key, hold=1000)
    wait_for(CONTROLS, timeout=5)


def test_back_in_the_rows_steps_up_one_row(tracks):
    """A single Back still goes one row up: cast row, chapter row, the bar."""
    _rows(True)
    press('backspace')
    wait_for('Window.IsActive(videobookmarks) + !Window.IsVisible(1141) + Control.HasFocus(11)', timeout=5)
    time.sleep(0.3)
    press('backspace')
    wait_for('Window.IsActive(videoosd) + !Window.IsVisible(videobookmarks) + Control.HasFocus(611)', timeout=5)
