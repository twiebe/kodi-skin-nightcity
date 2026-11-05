"""The album spotlight of the Music page follows the focused album or artist card and stands still
meanwhile (Includes_Music.xml MusicFollowHero). Rows: 9801 to 9803 albums, 9804 artists, 9805
genres. kodi-dev's music comes with the seed."""
import time

import pytest

from conftest import action, builtin, cond, info, screenshot, wait_for

pytestmark = pytest.mark.e2e

INTERVAL = 10  # s, the shortest the settings have
FOLLOWS = 'Control.IsVisible(9303)'


def true(condition):
    return cond(condition)[condition]


def label(key):
    return info(key)[key]


def reopen_home():
    builtin('ReplaceWindow(Settings)')  # Home reads the interval when opened
    wait_for('Window.IsActive(settings)')
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')


def open_page():
    builtin('SetFocus(9107)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),music)')
    wait_for('Integer.IsGreater(Container(9002).NumItems,1)', timeout=30)


def focus_row(row):
    wait_for('Integer.IsGreater(Container({}).NumItems,0)'.format(row), timeout=30)
    builtin('SetFocus({})'.format(row))
    wait_for('Control.HasFocus({})'.format(row))


@pytest.fixture
def music_page(home):
    open_page()
    if not true('Integer.IsGreater(Container(9801).NumItems,0)'):
        pytest.skip('no music in this Kodi')
    yield
    builtin('SetFocus(9101)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),home)')


@pytest.fixture
def short_interval(home):
    builtin('Skin.SetString(SpotlightInterval,{})'.format(INTERVAL))
    reopen_home()
    open_page()
    yield
    builtin('Skin.Reset(SpotlightInterval)')
    reopen_home()
    builtin('SetFocus(9101)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),home)')


def test_spotlight_itself_does_not_follow(music_page):
    builtin('SetFocus(9852)')
    wait_for('Control.HasFocus(9852)')
    assert not true(FOLLOWS)
    assert label('Container(9002).ListItem.Label').upper() in label('Control.GetLabel(9860)').upper()


def test_follows_an_album_with_what_the_spotlight_shows(music_page):
    focus_row(9801)
    assert label('ListItem.DBType') == 'album'
    album, artist = label('ListItem.Label'), label('ListItem.Artist')
    wait_for(FOLLOWS)
    assert album.upper() in label('Control.GetLabel(9330)').upper()
    assert artist.upper() in label('Control.GetLabel(9332)').upper()
    screenshot('music-follow-album')
    action('right')
    wait_for('!String.IsEqual(ListItem.Label,{})'.format(album))
    assert label('ListItem.Label').upper() in label('Control.GetLabel(9330)').upper()


def test_follows_on_every_album_row(music_page):
    for row in (9802, 9803):
        if true('Integer.IsGreater(Container({}).NumItems,0)'.format(row)):
            focus_row(row)
            wait_for(FOLLOWS)
            assert label('ListItem.Label').upper() in label('Control.GetLabel(9330)').upper()


def test_follows_an_artist(music_page):
    focus_row(9804)
    assert label('ListItem.DBType') == 'artist'
    wait_for(FOLLOWS)
    assert label('ListItem.Label').upper() in label('Control.GetLabel(9330)').upper()
    screenshot('music-follow-artist')


def test_genre_card_leaves_the_spotlight(music_page):
    focus_row(9805)
    assert label('ListItem.DBType') == 'genre'
    assert not true(FOLLOWS)
    assert label('Container(9002).ListItem.Label').upper() in label('Control.GetLabel(9860)').upper()
    screenshot('music-follow-genre')


def test_up_from_a_row_reaches_the_buttons(music_page):
    focus_row(9801)
    wait_for(FOLLOWS)
    action('up')
    wait_for('ControlGroup(9850).HasFocus()')
    assert not true(FOLLOWS)
    time.sleep(0.5)
    screenshot('music-follow-back-on-buttons')


def test_buttons_are_hidden_but_kept_while_following(music_page):
    """The row's Up needs them: not hidden for Kodi, only faded out."""
    focus_row(9801)
    wait_for(FOLLOWS)
    assert true('Control.IsVisible(9850)')


def test_timer_stands_while_following_and_starts_over(short_interval):
    key = 'Container(9002).CurrentItem'
    focus_row(9801)
    wait_for(FOLLOWS)
    position, title = label(key), label('Container(9002).ListItem.Label')
    time.sleep(INTERVAL + 4)
    assert label(key) == position
    builtin('SetFocus(9852)')
    wait_for('Control.HasFocus(9852)')
    back = time.time()
    assert not true(FOLLOWS)
    assert label('Container(9002).ListItem.Label') == title
    time.sleep(INTERVAL - 3)
    assert label(key) == position  # the interval started anew
    wait_for('!Integer.IsEqual({},{})'.format(key, position), timeout=8)
    assert time.time() - back >= INTERVAL - 1


def test_no_online_lookup_for_music(music_page):
    focus_row(9801)
    wait_for(FOLLOWS)
    for _ in range(12):  # longer than the video pages' 1.5 s
        assert not label('Window(Home).Property(TMDbHelper.WidgetContainer)')
        time.sleep(0.25)
