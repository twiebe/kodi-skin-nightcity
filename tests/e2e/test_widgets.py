import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

ON_DECK, NEW_MOVIES, NEW_SHOWS, CONTINUE = 9201, 9202, 9203, 9204


def num_items(container):
    key = 'Container({}).NumItems'.format(container)
    return int(info(key)[key] or 0)


def visible(control_id):
    key = 'Control.IsVisible({})'.format(control_id)
    return cond(key)[key]


def clear_progress():
    for movie in rpc('VideoLibrary.GetMovies', {'filter': {'field': 'inprogress', 'operator': 'true', 'value': ''}}).get('movies', []):
        rpc('VideoLibrary.SetMovieDetails', {'movieid': movie['movieid'], 'resume': {'position': 0, 'total': 0}})
    for ep in rpc('VideoLibrary.GetEpisodes', {'filter': {'field': 'inprogress', 'operator': 'true', 'value': ''}}).get('episodes', []):
        rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': ep['episodeid'], 'resume': {'position': 0, 'total': 0}})
    for ep in rpc('VideoLibrary.GetEpisodes', {'filter': {'field': 'playcount', 'operator': 'greaterthan', 'value': '0'}}).get('episodes', []):
        rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': ep['episodeid'], 'playcount': 0})


def kdev_show_episodes():
    shows = rpc('VideoLibrary.GetTVShows', {'filter': {'field': 'title', 'operator': 'is', 'value': 'Kdev Show'}})['tvshows']
    episodes = rpc('VideoLibrary.GetEpisodes', {'tvshowid': shows[0]['tvshowid'], 'properties': ['season', 'episode'],
                                                'sort': {'method': 'episode'}})['episodes']
    return shows[0]['tvshowid'], episodes


@pytest.fixture
def progress():
    clear_progress()
    rpc('VideoLibrary.SetMovieDetails', {'movieid': 1, 'resume': {'position': 120, 'total': 600}})
    yield
    clear_progress()


def reload_home():
    # Changing library data over JSON-RPC does not refresh a list that was empty before (Kodi
    # only listens for library updates once a list has video items; in real use the player's
    # OnStop refreshes it), so rebuild the skin.
    builtin('Dialog.Close(all,true)')
    builtin('ReloadSkin()')
    wait_for('Window.IsActive(home)')
    time.sleep(4)


def test_widgets_filled(home, progress):
    reload_home()
    assert num_items(ON_DECK) >= 1
    assert num_items(NEW_MOVIES) >= 1
    assert num_items(NEW_SHOWS) >= 1
    screenshot('home-widgets')


def test_widget_limits(home):
    """Review focus 5: the big kodi-dev library is cut to 25 items per row."""
    reload_home()
    assert num_items(NEW_MOVIES) == 25


def test_new_shows_order(home):
    reload_home()
    newest = rpc('VideoLibrary.GetEpisodes', {'properties': ['showtitle', 'dateadded'],
                                              'sort': {'method': 'dateadded', 'order': 'descending'},
                                              'limits': {'end': 1}})['episodes'][0]
    key = 'Container({}).ListItemAbsolute(0).TVShowTitle'.format(NEW_SHOWS)
    label = 'Container({}).ListItemAbsolute(0).Label'.format(NEW_SHOWS)
    labels = info(key, label)
    assert newest['showtitle'] in (labels[key], labels[label])


def test_empty_row_hidden(home):
    """Review focus 2: nothing in progress, so On Deck disappears and focus skips it."""
    clear_progress()
    reload_home()
    assert num_items(ON_DECK) == 0
    assert not visible(9211)
    builtin('SetFocus(9010)')
    action('down')
    assert cond('Control.HasFocus({})'.format(NEW_MOVIES))['Control.HasFocus({})'.format(NEW_MOVIES)]


def test_continue_opens_next_episode(home):
    """A show in "continue watching" opens the info page of its next episode."""
    clear_progress()
    _, episodes = kdev_show_episodes()
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodes[0]['episodeid'], 'playcount': 1,
                                           'lastplayed': time.strftime('%Y-%m-%d %H:%M:%S')})
    try:
        reload_home()
        assert num_items(CONTINUE) >= 1
        builtin('SetFocus({},0,absolute)'.format(CONTINUE))
        wait_for('Control.HasFocus({})'.format(CONTINUE))
        action('select')
        wait_for('Window.IsActive(movieinformation)')
        labels = info('ListItem.Episode', 'ListItem.Season')
        assert (labels['ListItem.Season'], labels['ListItem.Episode']) == ('1', '2'), labels
        screenshot('continue-next-episode')
    finally:
        clear_progress()
        builtin('Dialog.Close(all,true)')
