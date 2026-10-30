"""Media info on the info page: "ends at" from the resume point, the player's finish time for the
item that is playing, and the ratings line (docs/media-info-af3.md).

The ends-at tags carry no control id (a tag is a disabled button, and every button with an id
counts as focusable in the static focus checks), and Control.IsVisible over JSON-RPC looks at
the window below a dialog: so these tests take the visible conditions from the window as Kodi
builds it (tests/static/navigation.py) and ask Kodi for them.
"""
import json
import pathlib
import sys
import time

import pytest

from conftest import builtin, cond, info, kdev, rpc, screenshot, seed, wait_for

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'static'))
import navigation  # noqa: E402

pytestmark = pytest.mark.e2e

ENDS = '$LOCALIZE[31059] $INFO[ListItem.EndTimeResume]'
FINISH = '$LOCALIZE[31059] $INFO[Player.FinishTime]'
MOVIE_RATINGS = 9046


def _movie_head_tags():
    """Visible conditions of the movie head's two ends-at tags (resume based, player's)."""
    found = {}
    for c in navigation.load('DialogVideoInfo.xml').iter('control'):
        label = c.findtext('label') or ''
        visible = ' + '.join(v.text for v in c.findall('visible'))
        for key, text in (('ends', ENDS), ('finish', FINISH)):
            if text in label and visible.startswith('[String.IsEqual(ListItem.DBType,movie)'):
                found[key] = visible
    assert set(found) == {'ends', 'finish'}, found
    return found


def _visible_of(cid):
    """Visible condition of control CID of the info page, with those of the groups around it."""
    window = navigation.load('DialogVideoInfo.xml')
    parents = {child: parent for parent in window.iter() for child in parent}
    control = next(c for c in window.iter('control') if c.get('id') == str(cid))
    parts = []
    while control is not None:
        parts += ['[{}]'.format(v.text) for v in control.findall('visible')]
        control = parents.get(control)
    return ' + '.join(parts)


def _shown(condition):
    return cond(condition)[condition]


def _movie(title):
    return rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': title}})['movies'][0]['movieid']


def _server_position(item, seconds):
    """Jellyfin for Kodi plays from the server's position and syncs it back into Kodi."""
    data = seed()
    path = '/UserItems/{}/UserData?userId={}'.format(data['items'][item], data['users'][data['user']]['id'])
    kdev('jf', 'POST', path, json.dumps({'PlaybackPositionTicks': int(seconds * 10_000_000)}))


def _resume_at(movieid, seconds):
    """Set Kodi's resume point until it sticks: Jellyfin for Kodi rewrites it from the server a
    moment later."""
    stable = 0
    for _ in range(20):
        details = rpc('VideoLibrary.GetMovieDetails', {'movieid': movieid, 'properties': ['resume']})['moviedetails']
        if abs(int(details['resume']['position']) - seconds) < 5:
            stable += 1
            if stable == 3:
                return
        else:
            stable = 0
            rpc('VideoLibrary.SetMovieDetails', {'movieid': movieid, 'resume': {'position': seconds, 'total': 600}})
        time.sleep(0.5)
    raise AssertionError('resume point did not stick')


def _open_info(movieid):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(movieid))
    wait_for('Window.IsActive(movieinformation) + Integer.IsEqual(ListItem.DBID,{})'.format(movieid), timeout=10)


def _minutes(text):
    """'1:57 AM' or '13:57' as minutes of the day."""
    clock, _, half = text.partition(' ')
    hours, minutes = (int(part) for part in clock.split(':'))
    if half.upper() == 'PM' and hours < 12:
        hours += 12
    if half.upper() == 'AM' and hours == 12:
        hours = 0
    return hours * 60 + minutes


@pytest.fixture
def alpha(home):
    movieid = _movie('Kdev Alpha')
    _server_position('Kdev Alpha', 300)
    _resume_at(movieid, 300)
    yield movieid
    builtin('Dialog.Close(all,true)')
    if rpc('Player.GetActivePlayers'):
        rpc('Player.Stop', {'playerid': 1})
        time.sleep(1)
    _server_position('Kdev Alpha', 0)
    rpc('VideoLibrary.SetMovieDetails', {'movieid': movieid, 'resume': {'position': 0, 'total': 0}})


def test_ends_at_counts_from_the_resume_point(alpha):
    tags = _movie_head_tags()
    _open_info(alpha)
    wait_for(tags['ends'])
    assert not _shown(tags['finish'])
    labels = info('ListItem.EndTimeResume', 'ListItem.EndTime', 'System.Time')
    # 10 minutes from the start, 5 from the resume point
    left = (_minutes(labels['ListItem.EndTimeResume']) - _minutes(labels['System.Time'])) % (24 * 60)
    assert 4 <= left <= 6, labels
    assert (_minutes(labels['ListItem.EndTime']) - _minutes(labels['ListItem.EndTimeResume'])) % (24 * 60) in (4, 5, 6), labels
    screenshot('media-info-resume')


def test_ends_at_of_the_playing_movie_is_the_players(alpha):
    """Started from the beginning while its resume point says 5:00: the info page of the playing
    movie shows when the player ends, the one of another movie its own end."""
    tags = _movie_head_tags()
    rpc('Player.Open', {'item': {'movieid': alpha}, 'options': {'resume': False}})
    wait_for('Player.HasVideo', timeout=20)
    wait_for('Integer.IsGreater(Player.TimeRemaining(secs),0)', timeout=10)
    _open_info(alpha)
    wait_for(tags['finish'])
    assert not _shown(tags['ends'])
    labels = info('Player.FinishTime', 'ListItem.EndTimeResume', 'System.Time')
    # about 10 minutes left in the player, 5 by the stored resume point
    left = (_minutes(labels['Player.FinishTime']) - _minutes(labels['System.Time'])) % (24 * 60)
    assert left >= 8, labels
    screenshot('media-info-playing')
    other = _movie('Kdev Beta')
    _open_info(other)
    wait_for(tags['ends'])
    assert not _shown(tags['finish'])


def test_ratings_line_shows_tmdb_helpers_rating(home):
    movies = rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'The Matrix'}})
    if not movies.get('movies'):
        pytest.skip('The Matrix not in the library')
    # TMDb is the one source kodi-dev has without keys; its toggle is off by default
    builtin('Skin.SetBool(nc.ratings.show.tmdb)')
    _open_info(movies['movies'][0]['movieid'])
    try:
        wait_for('!String.IsEmpty(Window(Home).Property(TMDbHelper.ListItem.TMDb_Rating))', timeout=30)
        wait_for(_visible_of(MOVIE_RATINGS))
    finally:
        builtin('Skin.Reset(nc.ratings.show.tmdb)')
        builtin('Dialog.Close(all,true)')


def test_ratings_line_hides_without_ratings(alpha):
    """kodi-dev's own movies have neither a library rating nor TMDb data."""
    _open_info(alpha)
    wait_for('String.IsEmpty(Window(Home).Property(TMDbHelper.IsUpdating))', timeout=10)
    time.sleep(1)
    assert info('ListItem.Rating')['ListItem.Rating'] in ('', '0.0')
    assert not _shown(_visible_of(MOVIE_RATINGS))
