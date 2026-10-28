import time

import pytest

from conftest import _data, action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

MOVIE_ID = 3  # "Bulk 0000", a 10 minute test clip


def stop():
    if rpc('Player.GetActivePlayers'):
        rpc('Player.Stop', {'playerid': 1})
        time.sleep(1)


@pytest.fixture
def playing(home):
    rpc('Player.Open', {'item': {'movieid': MOVIE_ID}})
    wait_for('Player.HasVideo', timeout=20)
    wait_for('Window.IsActive(fullscreenvideo)')
    yield
    stop()
    rpc('VideoLibrary.SetMovieDetails', {'movieid': MOVIE_ID, 'resume': {'position': 0, 'total': 0}})


def test_fullscreen_after_play(playing):
    assert cond('Window.IsActive(fullscreenvideo)')['Window.IsActive(fullscreenvideo)']


def test_osd_opens(playing):
    action('osd', delay=1)
    try:
        wait_for('Window.IsActive(VideoOSD.xml)')
        screenshot('osd')
    finally:
        action('back', delay=1)


def test_seekbar(playing):
    action('stepforward')
    wait_for('Window.IsVisible(DialogSeekBar.xml)')
    screenshot('seekbar')


def test_no_scanlines_while_playing(playing):
    assert not cond('Control.IsVisible(9900)')['Control.IsVisible(9900)']


def test_stop_returns(playing):
    stop()
    wait_for('!Window.IsActive(fullscreenvideo)')
    wait_for('Window.IsActive(home)')


def test_osd_shows_player_bar(playing):
    action('osd', delay=1)
    try:
        wait_for('Window.IsActive(VideoOSD.xml)')
        wait_for('Window.IsVisible(DialogSeekBar.xml)')
    finally:
        action('back', delay=1)


@pytest.mark.parametrize('window', ['osdaudiosettings', 'osdsubtitlesettings', 'osdvideosettings'])
def test_osd_settings_have_rows(playing, window):
    """The OSD settings dialogs list their settings and focus the first one (they were empty)."""
    builtin('ActivateWindow({})'.format(window))
    try:
        wait_for('Window.IsActive({})'.format(window))
        wait_for('!String.IsEmpty(System.CurrentControlId)', timeout=5)
        screenshot(window)
    finally:
        action('back', delay=1)


def test_osd_finish_time(playing):
    action('osd', delay=1)
    try:
        wait_for('Window.IsActive(VideoOSD.xml)')
        finish = info('Player.FinishTime')['Player.FinishTime']
        assert finish and finish in info('Control.GetLabel(650)')['Control.GetLabel(650)']
    finally:
        action('back', delay=1)


def test_fullscreen_info(playing):
    action('info', delay=1)
    try:
        wait_for('Window.IsActive(fullscreeninfo)')
        screenshot('fullscreeninfo')
    finally:
        action('back', delay=1)




@pytest.fixture
def tracks(home):
    """A clip with two audio tracks, two subtitles and three chapters (tools/make_tracks_clip.py)."""
    import pathlib
    import subprocess
    import sys
    clip = _data() / 'kodi' / 'media' / 'nc-tracks.mkv'  # this Kodi's, also on a pool worker
    if not clip.is_file():
        clip.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([sys.executable, str(pathlib.Path(__file__).parents[2] / 'tools' / 'make_tracks_clip.py'),
                        str(clip)], check=True)
    rpc('Player.Open', {'item': {'file': '/home/kodi/.kodi/media/nc-tracks.mkv'}})
    wait_for('Player.HasVideo', timeout=20)
    wait_for('Window.IsActive(fullscreenvideo)')
    action('osd', delay=1)
    wait_for('Window.IsActive(VideoOSD.xml)')
    yield
    stop()


def streams():
    return rpc('Player.GetProperties', {'playerid': 1, 'properties': [
        'currentaudiostream', 'currentsubtitle', 'subtitleenabled']})


def enter_panel(button, panel, kind):
    """Focus the button, wait for the script to fill its panel, go up into it: the cursor lands
    on the current row."""
    builtin('SetFocus({})'.format(button))
    wait_for('Control.HasFocus({})'.format(button))
    wait_for('!String.IsEmpty(Window(Home).Property(nc.{}.pos))'.format(kind))
    pos = int(info('Window(Home).Property(nc.{}.pos)'.format(kind))['Window(Home).Property(nc.{}.pos)'.format(kind)])
    action('up')
    wait_for('Control.HasFocus({})'.format(panel))
    wait_for('Integer.IsEqual(Container({}).CurrentItem,{})'.format(panel, pos + 1))
    return pos


def pick(panel, position):
    builtin('SetFocus({},{},absolute)'.format(panel, position))
    wait_for('Integer.IsEqual(Container({}).CurrentItem,{})'.format(panel, position + 1))
    action('select', delay=1.5)


def test_audio_panel_switches_track(tracks):
    pos = enter_panel(606, 652, 'audio')
    screenshot('osd-audio-panel')
    other = 1 - pos
    pick(652, other)
    assert streams()['currentaudiostream']['index'] == other
    wait_for('String.IsEqual(Window(Home).Property(nc.audio.{}.current),1)'.format(other + 1))


def test_panel_follows_switch_outside(tracks):
    """A track switched elsewhere (remote key, JSON-RPC) moves the marker while the panel is open."""
    pos = enter_panel(606, 652, 'audio')
    other = 1 - pos
    rpc('Player.SetAudioStream', {'playerid': 1, 'stream': other})
    wait_for('String.IsEqual(Window(Home).Property(nc.audio.{}.current),1)'.format(other + 1), timeout=5)
    assert cond('Control.HasFocus(652)')['Control.HasFocus(652)']


def test_subtitle_panel_off_and_on(tracks):
    enter_panel(605, 651, 'sub')
    pick(651, 0)  # off
    assert not streams()['subtitleenabled']
    pick(651, 2)  # second subtitle
    s = streams()
    assert s['subtitleenabled'] and s['currentsubtitle']['index'] == 1
    wait_for('String.IsEqual(Window(Home).Property(nc.sub.3.current),1)')
    screenshot('osd-subtitle-panel')


def test_panel_more_opens_full_settings(tracks):
    enter_panel(606, 652, 'audio')
    pick(652, 2)
    try:
        wait_for('Window.IsActive(osdaudiosettings)')
    finally:
        action('back', delay=1)


def test_down_opens_chapter_list(tracks):
    action('down')
    try:
        wait_for('Window.IsActive(videobookmarks)')
        wait_for('Control.HasFocus(11)')  # the chapters, not add bookmark
        screenshot('osd-chapters')
    finally:
        action('back', delay=1)
