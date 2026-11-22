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
    wait_for('Control.HasFocus(608)')  # chapters, right of video


def test_chapters_button_opens_the_chapter_panel(tracks):
    """OK or Up on chapters opens the chapter panel above the row on the playing chapter; Down
    closes it onto the button, Left past the first card goes to video, Right past the last card
    to stats with its setting, else round to the far left."""
    focus(608)
    action('up')
    wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(11)', timeout=5)
    assert int(info('Container(11).NumItems')['Container(11).NumItems']) == 3
    screenshot('osd-chapter-panel')
    action('down')
    wait_for('!Window.IsVisible(videobookmarks) + Control.HasFocus(608)', timeout=5)
    action('select')
    wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(11)', timeout=5)
    builtin('SetFocus(11,0,absolute)')
    wait_for('Integer.IsEqual(Container(11).CurrentItem,1)')
    action('left')
    wait_for('!Window.IsVisible(videobookmarks) + Control.HasFocus(607)', timeout=5)
    focus(608)
    action('select')
    wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(11)', timeout=5)
    builtin('SetFocus(11,2,absolute)')
    wait_for('Integer.IsEqual(Container(11).CurrentItem,3)')
    action('right')
    wait_for('!Window.IsVisible(videobookmarks) + Control.HasFocus(601)', timeout=5)


def test_chapter_panel_right_goes_to_stats_with_its_setting(tracks):
    builtin('Skin.SetBool(nc.osd.stats)')
    try:
        focus(608)
        action('up')
        wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(11)', timeout=5)
        builtin('SetFocus(11,2,absolute)')
        wait_for('Integer.IsEqual(Container(11).CurrentItem,3)')
        action('right')
        wait_for('!Window.IsVisible(videobookmarks) + Control.HasFocus(609)', timeout=5)
    finally:
        builtin('Skin.Reset(nc.osd.stats)')


@pytest.mark.parametrize('button, window', [(605, 'osdsubtitlesettings'), (606, 'osdaudiosettings'),
                                            (607, 'osdvideosettings')])
def test_ok_on_a_track_button_opens_all_settings(tracks, button, window):
    """Up goes into the panel, OK opens Kodi's settings at once; the footer says so."""
    focus(button)
    wait_for('Control.IsVisible(691) | Control.IsVisible(692)')
    action('select')
    wait_for('Window.IsActive({})'.format(window))
    action('back')
    wait_for('!Window.IsActive({})'.format(window))


def test_track_list_wraps_upward_onto_all_settings(tracks):
    """Up on the first row of the list lands on its last row, all settings."""
    focus(605)
    action('up')
    wait_for('Control.HasFocus(651)')
    builtin('SetFocus(651,0,absolute)')
    wait_for('Integer.IsEqual(Container(651).CurrentItem,1)')
    last = info('Window(Home).Property(nc.sub.count)')['Window(Home).Property(nc.sub.count)']
    action('up')
    wait_for('Integer.IsEqual(Container(651).CurrentItem,{})'.format(last))


@pytest.mark.parametrize('stats, last', [(False, 608), (True, 609)], ids=['chapters', 'stats'])
def test_button_rows_wrap_around(tracks, stats, last):
    """Left on the far left control lands on the far right one, Right there back on the far left:
    stats with its skin setting, else chapters. No "…" any more."""
    if stats:
        builtin('Skin.SetBool(nc.osd.stats)')
    try:
        wait_for('Control.IsVisible(609)' if stats else '!Control.IsVisible(609)')
        focus(601)
        action('left')
        wait_for('Control.HasFocus({})'.format(last))
        action('right')
        wait_for('Control.HasFocus(601)')
    finally:
        builtin('Skin.Reset(nc.osd.stats)')


def test_moving_between_the_rows_lands_on_the_neighbour(tracks):
    """Not on the button that had the focus last in the other row: Kodi's groups remember it."""
    focus(607)
    focus(611)
    action('right')
    first = 605
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
    action('up')
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


def test_cast_row_after_a_chain_comes_back_from_the_osd(tracks):
    """A chain from the cast row ends on the OSD, whose stand-in 699 opens the cast row again
    (nc.osd.rows); Up there goes back to the controls. The clip has no cast row: the test sets
    the properties the chain leaves and closes the OSD as the chain does."""
    close_osd()
    builtin('SetProperty(nc.osd.chain,1,home)')
    action('osd')
    wait_for('Window.IsActive(1141)', timeout=5)
    builtin('ClearProperty(nc.osd.chain,home)')
    builtin('Dialog.Close(1141)')
    wait_for('Window.IsActive(videoosd) + !Window.IsVisible(1141) + Control.HasFocus(602)', timeout=5)


def press(button, hold=0):
    """A key through Kodi's keymaps; a hold over Kodi's threshold (500 ms) is a long press."""
    rpc('Input.ButtonEvent', {'button': button, 'keymap': 'KB', 'holdtime': hold})


def _rows(panel):
    """The chapter panel (PANEL) or the cast row, opened from the bar's skip button. The clip has
    no cast, so the test opens that row itself. The back keymap (scripts/nightcity.py
    BACK_KEYMAP) is written anew first, as the service does at startup."""
    builtin('NotifyAll(nightcity,home_keymap)')
    time.sleep(1)
    focus(611)
    if panel:
        focus(608)
        action('up')
        wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(11)', timeout=5)
    else:
        builtin('ActivateWindow(1141)')
        wait_for('Window.IsActive(1141)', timeout=5)
    time.sleep(0.3)  # a key in the first moment after opening gets lost


CONTROLS = ('Window.IsActive(videoosd) + !Window.IsVisible(videobookmarks) + !Window.IsVisible(1141)'
            ' + Control.HasFocus(602)')


@pytest.mark.parametrize('panel', [True, False], ids=['chapters', 'cast'])
@pytest.mark.parametrize('key', ['backspace', 'escape'])
def test_back_held_in_the_rows_goes_to_the_controls(tracks, panel, key):
    """Back held in the chapter panel or the cast row: the player's controls on their own first
    button (play or resume), as Back held in a chain from the cast row (back_to_start)."""
    _rows(panel)
    press(key, hold=1000)
    wait_for(CONTROLS, timeout=5)


def test_back_in_the_rows_goes_back_to_the_controls(tracks):
    """A single Back closes the cast row or the chapter panel onto the controls."""
    _rows(False)
    press('backspace')
    wait_for('Window.IsActive(videoosd) + !Window.IsVisible(1141) + Control.HasFocus(611)', timeout=5)
    _rows(True)
    press('backspace')
    wait_for('Window.IsActive(videoosd) + !Window.IsVisible(videobookmarks) + Control.HasFocus(608)', timeout=5)


def test_back_over_the_bare_video_stops_it(tracks):
    """Leaving the video stops it: Back with nothing over the video (BACK_KEYMAP fullscreenvideo).
    With the OSD open Back only closes the OSD."""
    builtin('NotifyAll(nightcity,home_keymap)')
    time.sleep(1)
    close_osd()
    assert cond('Player.HasVideo')['Player.HasVideo']
    press('backspace')
    wait_for('!Player.HasVideo', timeout=10)
