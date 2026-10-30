"""Music (docs/music-design.md): the Music page of Home, an album's page, playing from a track
and the music OSD with its queue row. Needs a music library in Kodi (skipped without one)."""
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


def player_screen(condition='Player.HasAudio', timeout=10):
    """Wait for the player screen with the music on and Kodi's busy dialog gone: that dialog
    takes the keys while the track loads (a Back or OSD key then gets lost). Right after the
    last test stopped its music Kodi opens its audio output again, and the busy dialog stays
    up longer than a second; it comes up a moment after the player screen, so look after it."""
    wait_for('Window.IsActive(visualisation) + {}'.format(condition), timeout=timeout)
    time.sleep(1)
    wait_for('!Window.IsActive(busydialog) + !Window.IsActive(busydialognocancel)')


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


def spotlight_moves(direction, step):
    """Press direction and wait for the album spotlight to move one album. It also scrolls on
    its own, so a scroll between reading and pressing gets another try."""
    key = 'Container(9002).CurrentItem'
    total = int(info('Container(9002).NumItems')['Container(9002).NumItems'])
    for _ in range(3):
        start = int(info(key)[key])
        action(direction)
        try:
            wait_for('Integer.IsEqual({},{})'.format(key, (start - 1 + step) % total + 1), timeout=3)
            return
        except AssertionError:
            continue
    raise AssertionError('album spotlight did not move {}'.format(direction))


def test_spotlight_prev_next_album(music):
    """Left on the first button the album before, Right on the last the next one; the chevron
    hint after the last button takes no focus."""
    open_page()
    wait_for('Integer.IsGreater(Container(9002).NumItems,2)')
    builtin('SetFocus(9852)')
    wait_for('Control.HasFocus(9852)')
    spotlight_moves('left', -1)
    assert holds('Control.HasFocus(9852)')
    builtin('SetFocus(9854)')
    wait_for('Control.HasFocus(9854)')
    spotlight_moves('right', 1)
    assert holds('Control.HasFocus(9854)')


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
    player_screen('Integer.IsEqual(MusicPlayer.PlaylistPosition,2)')
    assert not holds('Window.IsActive(musicinformation)')
    # Back: the album page again, the music plays on
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
    player_screen()
    action('osd')
    wait_for('Window.IsActive(musicosd)')
    wait_for('Control.HasFocus(602)')
    # one album: the text list, its latent cursor on the playing track (nightcity.py music_queue)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.music.queue.album))')
    wait_for('Control.IsVisible(701) + !Control.IsVisible(700)')
    wait_for('Integer.IsEqual(Container(701).CurrentItem,1)')
    screenshot('e2e-music-osd')
    action('down')
    wait_for('Control.HasFocus(701)')
    assert info('Container(701).CurrentItem')['Container(701).CurrentItem'] == '1'  # what plays
    action('down', 'select')
    wait_for('Integer.IsEqual(MusicPlayer.PlaylistPosition,2)')
    wait_for('Control.HasFocus(701)')  # a busy dialog may come up while the track loads
    # the cursor away from what plays: the bar stays on track 2, then moves to 1 by itself
    wait_for('Player.HasAudio + !Window.IsActive(busydialognocancel)')
    time.sleep(1)  # the queue reloads as the track starts, the cursor with it
    last = info('Container(701).NumItems')['Container(701).NumItems']
    builtin('SetFocus(701,{},absolute)'.format(int(last) - 1))  # the last track
    wait_for('Integer.IsEqual(Container(701).CurrentItem,{})'.format(last))
    screenshot('e2e-music-osd-playing-2')
    rpc('Player.GoTo', {'playerid': 0, 'to': 0})
    wait_for('Integer.IsEqual(MusicPlayer.PlaylistPosition,1)')
    wait_for('Control.HasFocus(701) + !Window.IsActive(busydialognocancel)')
    time.sleep(1)
    screenshot('e2e-music-osd-playing-1')
    assert info('Container(701).CurrentItem')['Container(701).CurrentItem'] == last
    builtin('SetFocus(701,0,absolute)')
    wait_for('Integer.IsEqual(Container(701).CurrentItem,1)')
    action('up')  # from the first track to the buttons
    wait_for('ControlGroup(600).HasFocus()')
    action('back')
    wait_for('!Window.IsActive(musicosd)')
    assert holds('Window.IsActive(visualisation)')


def mixed_artist():
    """An artist whose songs come from more than one album, or None."""
    songs = rpc('AudioLibrary.GetSongs', {'properties': ['albumid', 'artistid']})['songs']
    albums = {}
    for song in songs:
        for artist in song['artistid']:
            albums.setdefault(artist, set()).add(song['albumid'])
    return next((artist for artist, ids in sorted(albums.items()) if len(ids) > 1), None)


def test_osd_queue_of_several_albums_shows_covers(music):
    artist = mixed_artist()
    if artist is None:
        pytest.skip('no artist with songs on more than one album')
    builtin('NotifyAll(nightcity,music_play:artist:{}:1)'.format(artist))
    player_screen('Player.HasAudio + Integer.IsGreater(Playlist.Length(music),1)', timeout=15)
    action('osd')
    wait_for('Window.IsActive(musicosd)')
    wait_for('Control.IsVisible(700) + !Control.IsVisible(701)')
    assert holds('String.IsEmpty(Window(Home).Property(nc.music.queue.album))')
    wait_for('Integer.IsEqual(Container(700).CurrentItem,1)')  # the cursor on what plays
    screenshot('e2e-music-osd-mixed')
    action('down')
    wait_for('Control.HasFocus(700)')
    action('back')
    wait_for('!Window.IsActive(musicosd)')


def test_spotlight_play_goes_to_now_playing_and_back(music):
    open_page()
    builtin('SetFocus(9852)')
    wait_for('Control.HasFocus(9852)')
    action('select')
    player_screen()
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
    player_screen(timeout=15)  # nightcity.py now_playing
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
    player_screen()
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
