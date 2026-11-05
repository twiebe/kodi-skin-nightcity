"""The Jellyfin add-on starts no library scan for the echo of our own playback: Kodi announced it
already and reloaded its lists, a scan only reloads every list a second time (person page lists
read IsUpdating then, and the skin ignores a click on them). Real changes still scan.

Needs the fork's jellyfin add-on, TMDb Helper, The Matrix in the library."""
import json
import re
import time
import urllib.request

import pytest

from conftest import _data, action, builtin, rpc, seed, wait_for
from test_tmdb_chain import _list_in, _log, _log_since, _open_cast_row, _page, _play, matrix  # noqa: F401
from test_widgets import CONTINUE, ON_DECK, clear_progress, kdev_show_episodes, num_items

pytestmark = pytest.mark.e2e

SCAN = 'VideoInfoScanner: Starting scan'
FILMS = r'CDirectoryProvider\[[^]]*info=stars_in_movies[^]]*\]: refreshing'
# The add-on's writer needs a few seconds after the echo before it would scan
ECHO_AND_WRITER = 10


def _jellyfin(method, path):
    env = dict(line.split('=', 1) for line in (_data().parent / 'ports.env').read_text().split() if '=' in line)
    url = 'http://localhost:{}{}'.format(env['JELLYFIN_PORT'], path)
    request = urllib.request.Request(url, method=method, headers={'Authorization': 'MediaBrowser Token="{}"'.format(seed()['admin']['token'])})
    with urllib.request.urlopen(request, timeout=10) as response:
        body = response.read()
    return json.loads(body) if body else None


def _user_id():
    return seed()['users'][seed()['user']]['id']


def _movie_item(title):
    return _jellyfin('GET', '/Items?Recursive=true&IncludeItemTypes=Movie&searchTerm=' +
                     urllib.request.quote(title))['Items'][0]['Id']


def _stop():
    rpc('Player.Stop', {'playerid': 1})
    wait_for('!Player.HasVideo', timeout=10)


def test_a_person_page_over_a_playing_video_loads_its_films_once(matrix):
    _play(matrix)
    _open_cast_row()
    wait_for('String.IsEqual(Container(6599).ListItem.Property(tmdb_id),Container(6501).ListItem.Property(tmdb_id))', timeout=20)
    offset = _log().stat().st_size
    action('select')
    _page(1)
    _list_in('5510')
    time.sleep(ECHO_AND_WRITER)
    assert len(re.findall(FILMS, _log_since(offset))) == 1


def test_a_person_page_after_a_stop_loads_its_films_once(matrix):
    _play(matrix)
    time.sleep(3)
    _stop()
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    _list_in('5500')
    builtin('SetFocus(5500,0,absolute)')
    offset = _log().stat().st_size
    action('select')
    _page(2)
    _list_in('5510')
    time.sleep(ECHO_AND_WRITER)
    assert len(re.findall(FILMS, _log_since(offset))) == 1


def test_a_change_of_another_item_still_scans(matrix):
    other = next(m for m in rpc('VideoLibrary.GetMovies', {})['movies'] if m['movieid'] != matrix)
    item = _movie_item(other['label'])
    _play(matrix)
    time.sleep(3)
    _stop()
    time.sleep(ECHO_AND_WRITER)  # our echo is written
    offset = _log().stat().st_size
    path = '/Users/{}/PlayedItems/{}'.format(_user_id(), item)
    _jellyfin('POST', path)
    try:
        end = time.time() + 20
        while SCAN not in _log_since(offset) and time.time() < end:
            time.sleep(0.5)
        assert SCAN in _log_since(offset)
    finally:
        _jellyfin('DELETE', path)
        time.sleep(ECHO_AND_WRITER)


def test_a_resume_point_only_the_server_keeps_still_scans(matrix):
    """Stopped at 2 minutes of 10: too early for Kodi's own resume point (180 s), not for the
    server's (5 %). The add-on writes the server's, the lists must learn it."""
    clear_progress()
    _play(matrix)
    time.sleep(3)
    rpc('Player.Seek', {'playerid': 1, 'value': {'seconds': 120}})
    time.sleep(3)
    offset = _log().stat().st_size
    _stop()
    try:
        end = time.time() + 20
        while SCAN not in _log_since(offset) and time.time() < end:
            time.sleep(0.5)
        assert SCAN in _log_since(offset)
    finally:
        clear_progress()


def _comes_and_stays(row):
    wait_for('Window.IsActive(home)', timeout=10)
    end = time.time() + 15
    while num_items(row) < 1 and time.time() < end:
        time.sleep(0.5)
    assert num_items(row) >= 1
    time.sleep(ECHO_AND_WRITER)  # the echo's write must not take it away
    assert num_items(row) >= 1


def test_a_stopped_film_comes_to_its_row_on_home(matrix):
    clear_progress()
    _play(matrix)
    time.sleep(3)
    rpc('Player.Seek', {'playerid': 1, 'value': {'percentage': 50}})
    time.sleep(3)
    _stop()
    try:
        _comes_and_stays(ON_DECK)
    finally:
        clear_progress()


def test_a_finished_episode_brings_the_next_up_on_home(home):
    clear_progress()
    _, episodes = kdev_show_episodes()
    rpc('Player.Open', {'item': {'episodeid': episodes[0]['episodeid']}, 'options': {'resume': False}})
    wait_for('Player.HasVideo', timeout=20)
    time.sleep(3)
    rpc('Player.Seek', {'playerid': 1, 'value': {'percentage': 97}})
    time.sleep(3)
    _stop()
    try:
        _comes_and_stays(CONTINUE)
    finally:
        clear_progress()
