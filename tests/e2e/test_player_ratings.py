"""The ratings line in the player (docs/media-info-af3.md, "Ratings in the player").

TMDb Helper sets TMDbHelper.Player.* once a video has started; the skin service keeps them for
what plays (nc.kept.player.*), the line under the badges reads those. Music has no TMDb Helper
source: the line shows Kodi's own ratings of the song and its album.
"""
import time

import pytest

from conftest import action, builtin, info, rpc, screenshot, wait_for
from test_osd_autohide import changed_pixels
from test_ratings_source import breaking_bad  # noqa: F401 (fixture)

pytestmark = pytest.mark.e2e

# with the OSD up: the ratings line and the plot under it
LINE = (296, 592, 296 + 900, 592 + 34)
PLOT = (296, 634, 296 + 900, 634 + 192)
MUSIC_LINE = 9029
KEPT = 'Window(Home).Property(nc.kept.player.{})'


def _stop():
    for player in rpc('Player.GetActivePlayers'):
        rpc('Player.Stop', {'playerid': player['playerid']})
    wait_for('!Player.HasMedia')


@pytest.fixture
def tmdb_on(home):
    builtin('Skin.SetBool(nc.ratings.show.tmdb)')
    yield
    _stop()
    builtin('Skin.Reset(nc.ratings.show.tmdb)')


def _play_video(item):
    rpc('Player.Open', {'item': item})
    wait_for('Player.HasVideo + Window.IsActive(fullscreenvideo)', timeout=20)


def _ratings_shown(name):
    """TMDb Helper's rating of what plays is kept, and the line shows it: paused with the OSD
    up, the line's place changes when its only rating is switched off. The line is in the seek
    bar dialog, which JSON-RPC cannot ask about (Control.IsVisible looks at the OSD)."""
    wait_for('!String.IsEmpty({})'.format(KEPT.format('file')), timeout=20)
    action('pause')
    wait_for('Player.Paused + Window.IsActive(videoosd)')
    time.sleep(1)
    shown = screenshot(name)
    builtin('Skin.Reset(nc.ratings.show.tmdb)')
    time.sleep(0.5)
    hidden = screenshot(name + '-off')
    assert changed_pixels(shown, hidden, LINE) > 100
    assert changed_pixels(shown, hidden, PLOT) < 30
    return info(KEPT.format('TMDb_Rating'))[KEPT.format('TMDb_Rating')]


def test_movie_ratings_in_the_player(tmdb_on):
    movies = rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'The Matrix'}})
    if not movies.get('movies'):
        pytest.skip('The Matrix not in the library')
    _play_video({'movieid': movies['movies'][0]['movieid']})
    assert _ratings_shown('player-ratings-movie') == '8.2'


def test_episode_ratings_in_the_player(tmdb_on, breaking_bad):  # noqa: F811
    """An episode shows its own TMDb vote, not the show's."""
    pilot = next(e for e in rpc('VideoLibrary.GetEpisodes', {'tvshowid': breaking_bad,
                                                             'properties': ['season', 'episode']})['episodes']
                 if (e['season'], e['episode']) == (1, 1))
    _play_video({'episodeid': pilot['episodeid']})
    assert _ratings_shown('player-ratings-episode') == '8.5'  # the show's is 8.9


@pytest.fixture
def rated_song(home):
    songs = rpc('AudioLibrary.GetSongs', {'properties': ['albumid', 'userrating'], 'limits': {'end': 1}}).get('songs')
    if not songs:
        pytest.skip('no music library in this Kodi')
    song = songs[0]
    rpc('AudioLibrary.SetSongDetails', {'songid': song['songid'], 'userrating': 8})
    yield song
    _stop()
    rpc('AudioLibrary.SetSongDetails', {'songid': song['songid'], 'userrating': song['userrating']})


def test_music_ratings_in_the_player(rated_song):
    """The user's own rating of the song shows; TMDb Helper has nothing for music."""
    rpc('Player.Open', {'item': {'songid': rated_song['songid']}})
    wait_for('Player.HasAudio', timeout=20)
    builtin('ActivateWindow(visualisation)')
    wait_for('Window.IsActive(visualisation)')
    wait_for('String.IsEqual(MusicPlayer.UserRating,8)')
    wait_for('Control.IsVisible({})'.format(MUSIC_LINE))
    time.sleep(0.5)
    screenshot('player-ratings-music')
