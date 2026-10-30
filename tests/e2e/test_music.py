"""Music (docs/music-design.md): the Music page of Home, an album's page, playing from a track
and the music OSD with its queue row. Needs a music library in Kodi (skipped without one; the
kodi-dev pool has none yet)."""
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e


def holds(condition):
    return cond(condition)[condition]


@pytest.fixture
def music(home):
    if not holds('Library.HasContent(music)'):
        pytest.skip('no music library in this Kodi')
    builtin('Skin.SetBool(nc.osd.autohide.off)')  # the OSD stays while the test looks at it
    yield
    builtin('Skin.Reset(nc.osd.autohide.off)')
    # the stop closes the player screen: no album page opening again over the next test
    builtin('ClearProperty(nc.music.back,home)')
    if holds('Player.HasAudio'):
        builtin('PlayerControl(Stop)')
        wait_for('!Player.HasAudio')


def open_page():
    builtin('SetFocus(9107)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),music)')
    wait_for('Integer.IsGreater(Container(9002).NumItems,0)')


def test_music_page_tab_and_buttons(music):
    open_page()
    action('down')
    wait_for('ControlGroup(9850).HasFocus()')  # the buttons (the one focused last)
    action('down')
    wait_for('Control.HasFocus(9801)')
    action('up', 'up')
    wait_for('Control.HasFocus(9107)')
    screenshot('e2e-music-page')


def open_album():
    open_page()
    action('down')
    wait_for('ControlGroup(9850).HasFocus()')
    builtin('SetFocus(9853)')  # Info; the buttons keep the one focused last
    wait_for('Control.HasFocus(9853)')
    action('select')
    wait_for('Window.IsActive(musicinformation)')
    wait_for('Integer.IsGreater(Container(5050).NumItems,0)')


def test_album_page_opens_with_its_tracks(music):
    open_album()
    assert info('ListItem.DBType')['ListItem.DBType'] == 'album'
    wait_for('Control.HasFocus(9001)')
    action('down')
    wait_for('Control.HasFocus(5050)')
    action('up', 'up')
    wait_for('!Window.IsActive(musicinformation)')  # Up from the buttons leaves the page


def test_a_track_plays_the_album_from_there(music):
    open_album()
    action('down')
    wait_for('Control.HasFocus(5050)')
    builtin('SetFocus(5050,1,absolute)')  # the second track
    wait_for('Integer.IsEqual(Container(5050).CurrentItem,2)')
    action('select')
    wait_for('Window.IsActive(visualisation)')
    wait_for('Player.HasAudio')
    wait_for('Integer.IsEqual(MusicPlayer.PlaylistPosition,2)')
    assert not holds('Window.IsActive(musicinformation)')
    # Back: the album page again, the music plays on
    time.sleep(1)
    action('back')
    wait_for('Window.IsActive(musicinformation)')
    assert info('ListItem.DBType')['ListItem.DBType'] == 'album'
    assert holds('Player.HasAudio')


def test_osd_queue_plays_the_chosen_track(music):
    open_album()
    builtin('SetFocus(5050,0,absolute)')  # the page keeps the track chosen last on that album
    wait_for('Control.HasFocus(5050)')
    action('select')
    wait_for('Window.IsActive(visualisation)')
    wait_for('Integer.IsEqual(MusicPlayer.PlaylistPosition,1)')
    # the album page closes as the player screen opens: an OSD key before it is gone gets lost
    wait_for('!Window.IsVisible(musicinformation)')
    time.sleep(1)
    action('osd')
    wait_for('Window.IsActive(musicosd)')
    wait_for('Control.HasFocus(602)')
    action('down')
    wait_for('Control.HasFocus(700)')
    assert info('Container(700).CurrentItem')['Container(700).CurrentItem'] == '2'  # up next
    screenshot('e2e-music-osd')
    action('right', 'select')
    wait_for('Integer.IsEqual(MusicPlayer.PlaylistPosition,3)')
    wait_for('Control.HasFocus(700)')  # a busy dialog may come up while the track loads
    action('up')
    wait_for('ControlGroup(600).HasFocus()')
    action('back')
    wait_for('!Window.IsActive(musicosd)')
    assert holds('Window.IsActive(visualisation)')


def test_spotlight_play_goes_to_now_playing_and_back(music):
    open_page()
    builtin('SetFocus(9852)')
    wait_for('Control.HasFocus(9852)')
    action('select')
    wait_for('Window.IsActive(visualisation)')
    wait_for('Player.HasAudio')
    time.sleep(1)
    action('back')
    wait_for('Window.IsActive(home)')
    wait_for('Control.HasFocus(9852)')  # where it was started, the music plays on
    assert holds('Player.HasAudio')
    assert not holds('Window.IsActive(musicinformation)')


def test_library_play_goes_to_now_playing_and_back(music):
    album = rpc('AudioLibrary.GetAlbums', {'limits': {'end': 1}})['albums'][0]['albumid']
    builtin('ActivateWindow(Music,musicdb://albums/{}/,return)'.format(album))
    wait_for('Window.IsActive(music) + Integer.IsGreater(Container.NumItems,0)')
    action('down')  # past ..
    wait_for('String.IsEqual(ListItem.DBType,song)')
    action('select')
    wait_for('Window.IsActive(visualisation)', timeout=15)  # nightcity.py now_playing
    time.sleep(1)
    action('back')
    wait_for('Window.IsActive(music)')
    assert holds('Player.HasAudio')
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')


def test_now_playing_in_the_top_line(music):
    """Right from the menu, OK opens the player screen, Back comes back to it; when the music
    stops the focus goes to the shown page's tab."""
    open_page()
    builtin('SetFocus(9852)')
    action('select')
    wait_for('Window.IsActive(visualisation) + Player.HasAudio')
    time.sleep(1)
    action('back')
    wait_for('Window.IsActive(home)')
    builtin('SetFocus(9104)')  # the last tab: search
    wait_for('Control.HasFocus(9104)')
    action('right')
    wait_for('Control.HasFocus(9108)')
    screenshot('e2e-music-np-topline')
    action('right')
    wait_for('Control.HasFocus(9109)')  # the quick menu icon
    action('left')
    wait_for('Control.HasFocus(9108)')
    action('select')
    wait_for('Window.IsActive(visualisation)')
    time.sleep(1)
    action('back')
    wait_for('Window.IsActive(home) + Control.HasFocus(9108)')
    builtin('PlayerControl(Stop)')
    wait_for('!Player.HasAudio')
    wait_for('Control.HasFocus(9104)')  # gone with the music: the shown page's own tab
