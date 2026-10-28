"""A click on a library item opens its info page; a click on a show opens its next episode."""
import re
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e


def kdev_show():
    show = rpc('VideoLibrary.GetTVShows', {'filter': {'field': 'title', 'operator': 'is', 'value': 'Kdev Show'}})['tvshows'][0]
    episodes = rpc('VideoLibrary.GetEpisodes', {'tvshowid': show['tvshowid'], 'properties': ['season', 'episode'],
                                                'sort': {'method': 'episode'}})['episodes']
    return show['tvshowid'], episodes


def clear_progress():
    for movie in rpc('VideoLibrary.GetMovies', {'filter': {'field': 'inprogress', 'operator': 'true', 'value': ''}}).get('movies', []):
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movie['movieid'], 'resume': {'position': 0, 'total': 0}})
    for ep in rpc('VideoLibrary.GetEpisodes', {'filter': {'field': 'inprogress', 'operator': 'true', 'value': ''}}).get('episodes', []):
        rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': ep['episodeid'], 'resume': {'position': 0, 'total': 0}})
    for ep in rpc('VideoLibrary.GetEpisodes', {'filter': {'field': 'playcount', 'operator': 'greaterthan', 'value': '0'}}).get('episodes', []):
        rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': ep['episodeid'], 'playcount': 0})


def reload_home():
    # library changes over JSON-RPC do not refresh a list that was empty, so rebuild the skin
    builtin('Dialog.Close(all,true)')
    builtin('ReloadSkin()')
    wait_for('Window.IsActive(home)')
    time.sleep(4)


@pytest.fixture
def clean(home):
    clear_progress()
    yield
    builtin('Dialog.Close(all,true)')
    builtin('ReplaceWindow(Home)')
    clear_progress()


def select_first(container):
    builtin('SetFocus({},0,absolute)'.format(container))
    wait_for('Control.HasFocus({})'.format(container))
    action('select')


def no_player():
    return not rpc('Player.GetActivePlayers')


def test_movie_tile_opens_info(clean):
    wait_for('Integer.IsGreater(Container(9202).NumItems,0)')
    select_first(9202)
    wait_for('Window.IsActive(movieinformation)')
    assert info('ListItem.DBType')['ListItem.DBType'] == 'movie'
    assert no_player()


def test_episode_tile_opens_info(clean):
    _, episodes = kdev_show()
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodes[0]['episodeid'], 'resume': {'position': 60, 'total': 600}})
    reload_home()
    wait_for('Integer.IsGreater(Container(9201).NumItems,0)')
    select_first(9201)
    wait_for('Window.IsActive(movieinformation)')
    assert info('ListItem.DBType')['ListItem.DBType'] == 'episode'
    assert no_player()


def test_show_tile_opens_next_episode(clean):
    _, episodes = kdev_show()
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodes[0]['episodeid'], 'playcount': 1,
                                           'lastplayed': time.strftime('%Y-%m-%d %H:%M:%S')})
    reload_home()
    builtin('SetFocus(9103)')
    wait_for('Integer.IsGreater(Container(9501).NumItems,0)')
    assert info('Container(9501).ListItemAbsolute(0).Label')['Container(9501).ListItemAbsolute(0).Label'] == 'Kdev Show'
    select_first(9501)
    wait_for('Window.IsActive(movieinformation)')
    labels = info('ListItem.DBType', 'ListItem.Episode')
    assert labels == {'ListItem.DBType': 'episode', 'ListItem.Episode': '2'}, labels
    screenshot('show-click-next-episode')


def open_library(kind):
    builtin('SetProperty(nc.library,{},home)'.format(kind))
    builtin('ActivateWindow(1110)')
    wait_for('Window.IsActive(1110)')
    wait_for('Integer.IsGreater(Container(5000).NumItems,1)')


def test_library_window_sort(clean):
    builtin('Skin.SetString(nc.sort,year)')
    builtin('Skin.SetBool(nc.sortdesc)')
    try:
        open_library('movies')
        years = info('Container(5000).ListItemAbsolute(0).Year', 'Container(5000).ListItemAbsolute(1).Year')
        first, second = (int(years['Container(5000).ListItemAbsolute({}).Year'.format(i)]) for i in (0, 1))
        assert first >= second
        newest = rpc('VideoLibrary.GetMovies', {'properties': ['year'], 'sort': {'method': 'year', 'order': 'descending'},
                                                'limits': {'end': 1}})['movies'][0]['year']
        assert first == newest
        screenshot('library-movies')
    finally:
        builtin('Skin.Reset(nc.sort)')
        builtin('Skin.Reset(nc.sortdesc)')


def test_library_sort_button_cycles(clean):
    builtin('Skin.Reset(nc.sort)')
    open_library('movies')
    builtin('SetFocus(5101)')
    wait_for('Control.HasFocus(5101)')
    action('select')
    wait_for('!String.IsEmpty(Skin.String(nc.sort))')
    builtin('Skin.Reset(nc.sort)')


def test_library_show_click(clean):
    open_library('tvshows')
    select_first(5000)
    wait_for('Window.IsActive(movieinformation)')
    assert info('ListItem.DBType')['ListItem.DBType'] == 'episode'
    assert no_player()
    assert cond('Window.IsActive(1110)')['Window.IsActive(1110)']


def test_library_path_line(clean):
    """The window title is a path line; the n/N counter sits on its right, not in a frame line."""
    open_library('movies')
    path, counter = (info('Control.GetLabel({})'.format(i))['Control.GetLabel({})'.format(i)] for i in (9026, 9028))
    assert re.sub(r'\[/?[A-Z]+[^\]]*\]', '', path).strip(), path
    assert re.fullmatch(r'\d+/\d+', counter), counter
    screenshot('library-movies')
