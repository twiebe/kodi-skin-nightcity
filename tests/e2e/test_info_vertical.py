"""The info page walked level by level with Up and Down, end to end.

Shows page, a show card, its episode's info page, down to the episode's cast and crew, then up
row by row, out of the page to the card, the spotlight and the menu. A movie page leaves with Up
from the button row, a TMDb page steps one page back in the chain.

Needs TMDb Helper, internet access for TMDb, Breaking Bad (at least S01E01 and S01E02) and The
Matrix in the library; without them the tests are skipped.

Control.* booleans over JSON-RPC look at the window below a dialog, so these tests read
System.CurrentControlId, which finds the topmost dialog.
"""
import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

SHOW = 'Breaking Bad'
RUNNING = '!String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
IDLE = 'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'


def _label(name):
    return info(name)[name]


def _true(condition):
    return cond(condition)[condition]


def _focus_is(cid, timeout=10):
    wait_for('Integer.IsEqual(System.CurrentControlId,{})'.format(cid), timeout=timeout)


def _up(cid, timeout=10):
    action('up', delay=0.6)
    _focus_is(cid, timeout)


def _down(cid, timeout=10):
    action('down', delay=0.6)
    _focus_is(cid, timeout)


def _leave_chain():
    if _true(RUNNING):
        builtin('SetProperty(TMDbHelper.Command,exit,home)')
        wait_for(IDLE, timeout=20)


def _tmdb_helper():
    addons = rpc('Addons.GetAddons', {'type': 'xbmc.python.pluginsource', 'enabled': True})['addons']
    if 'plugin.video.themoviedb.helper' not in [a['addonid'] for a in addons]:
        pytest.skip('TMDb Helper not installed')


@pytest.fixture
def breaking_bad(home):
    _tmdb_helper()
    shows = rpc('VideoLibrary.GetTVShows', {'filter': {'field': 'title', 'operator': 'is', 'value': SHOW}})
    if not shows.get('tvshows'):
        pytest.skip(SHOW + ' not in the library')
    tvshowid = shows['tvshows'][0]['tvshowid']
    episodes = rpc('VideoLibrary.GetEpisodes', {'tvshowid': tvshowid, 'properties': ['season', 'episode']})['episodes']
    for e in episodes:
        rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': e['episodeid'], 'playcount': 0,
                                               'resume': {'position': 0, 'total': 0}})
    yield tvshowid
    _leave_chain()
    builtin('Dialog.Close(all,true)')


@pytest.fixture
def matrix(home):
    _tmdb_helper()
    movies = rpc('VideoLibrary.GetMovies', {'filter': {'field': 'title', 'operator': 'is', 'value': 'The Matrix'}})
    if not movies.get('movies'):
        pytest.skip('The Matrix not in the library')
    yield movies['movies'][0]['movieid']
    _leave_chain()
    builtin('Dialog.Close(all,true)')


def _show_card():
    """Shows page, Down into the rows until the card of SHOW has the focus; returns the row."""
    builtin('SetFocus(9103)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),shows)')
    # Down needs the spotlight filled: a library update after the test before reloads it
    wait_for('Integer.IsGreater(Container(9001).NumItems,0) + !Container(9001).IsUpdating', timeout=20)
    _down(9551)
    for _ in range(8):
        action('down', delay=0.8)
        row = _label('System.CurrentControlId')
        for _ in range(30):
            if _label('Container({}).ListItem.Label'.format(row)) == SHOW:
                return int(row)
            action('right', delay=0.2)
        builtin('SetFocus({},0,absolute)'.format(row))
    raise AssertionError(SHOW + ' not on the shows page')


def _episode_credits_loaded():
    wait_for('String.IsEqual(Window(Home).Property(nc.info.ep.id),Container(5100).ListItem.DBID)', timeout=20)
    # the cast of this episode, not of the page before: Down waits for a stale row (rows-focus)
    wait_for('Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating + '
             'String.IsEqual(Container(5500).ListItem(0).Property(param.season),Container(5100).ListItem.Season) + '
             'String.IsEqual(Container(5500).ListItem(0).Property(param.episode),Container(5100).ListItem.Episode)',
             timeout=45)


def test_episode_walk_down_to_the_credits_and_up_to_the_menu(breaking_bad):
    row = _show_card()
    screenshot('vertical-0-shows-row')
    action('select')
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.info.ready))', timeout=20)
    assert _label('ListItem.DBType') == 'episode'
    _focus_is(9001)
    _episode_credits_loaded()
    screenshot('vertical-1-episode-top')

    _down(5100)  # past the season tabs (DESIGN.md)
    screenshot('vertical-2-episodes')
    _down(5500)
    time.sleep(0.5)
    screenshot('vertical-3-episode-cast')
    # the guest stars of the pilot are there, not only the main cast
    roles = [_label('Container(5500).ListItemAbsolute({}).Label2'.format(i)) for i in range(int(_label('Container(5500).NumItems')))]
    assert len(roles) > 5
    action('down', delay=0.6)
    _focus_is(5500)  # the deepest row: Down stays

    _up(5521)  # the cast tab of the tab row 5520
    _up(5100)
    _up(5200)
    _up(9001)
    screenshot('vertical-4-back-at-the-top')
    action('up', delay=1)
    wait_for('!Window.IsActive(movieinformation)', timeout=10)
    _focus_is(row)
    assert _label('Container({}).ListItem.Label'.format(row)) == SHOW
    screenshot('vertical-5-back-on-the-card')
    # up through the rows above, the spotlight and the menu
    for _ in range(6):
        if _label('System.CurrentControlId') == '9551':
            break
        action('up', delay=0.8)
    _focus_is(9551)
    screenshot('vertical-6-spotlight')
    _up(9103)
    screenshot('vertical-7-menu')


def test_episode_credits_follow_the_selected_episode(breaking_bad):
    builtin('NotifyAll(nightcity,next_episode:{})'.format(breaking_bad))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.info.ready))', timeout=20)
    _episode_credits_loaded()
    first = _label('Container(5100).ListItem.DBID')
    _down(5100)  # past the season tabs (DESIGN.md)
    # move to another episode: the credits row loads it once the selection rested
    for move in ('left', 'right'):
        action(move, delay=0.4)
        if _label('Container(5100).ListItem.DBID') != first:
            break
    second = _label('Container(5100).ListItem.DBID')
    assert second != first
    wait_for('String.IsEqual(Window(Home).Property(nc.info.ep.id),{})'.format(second), timeout=20)
    assert _label('Window(Home).Property(nc.info.ep.query)') == 'season={}&episode={}'.format(
        _label('Container(5100).ListItem.Season'), _label('Container(5100).ListItem.Episode'))
    wait_for('!Container(5500).IsUpdating + Integer.IsGreater(Container(5500).NumItems,0)', timeout=45)
    _down(5500)
    # crew tab: up to the tabs, right loads the episode's crew, OK goes down once it is in
    _up(5521)  # the cast tab of the tab row 5520
    action('right', delay=0.4)
    action('select', delay=0.5)
    wait_for('String.IsEqual(Window(Home).Property(nc.info.tab),crew)')
    wait_for('!Container(5500).IsUpdating + Integer.IsGreater(Container(5500).NumItems,0)', timeout=45)
    _focus_is(5500)
    screenshot('vertical-episode-crew')


def test_episode_person_opens_in_the_chain_and_back_returns(breaking_bad):
    builtin('NotifyAll(nightcity,next_episode:{})'.format(breaking_bad))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.info.ready))', timeout=20)
    _episode_credits_loaded()
    episode = _label('Container(5100).ListItem.DBID')
    _down(5100)  # past the season tabs (DESIGN.md)
    _down(5500)
    person = _label('Container(5500).ListItem.Label')
    action('select')
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),2)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),person)', timeout=20)
    assert _label('ListItem.Label') == person
    wait_for('Integer.IsGreater(Container(5510).NumItems,0)', timeout=30)
    screenshot('vertical-person-from-episode')
    # Up on the top of the person page: one page back, the episode
    _focus_is(9004)  # a person page has no play button: close all is the first one
    action('up', delay=1)
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),1)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.DBType,episode)', timeout=20)
    assert _label('ListItem.DBID') == episode


def test_movie_up_from_the_top_goes_back(matrix):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    # the cast of this film (a library title: by IMDb number or title), not of the page before:
    # Down waits for a stale row (rows-focus)
    wait_for('Integer.IsGreater(Container(5500).NumItems,0) + !Container(5500).IsUpdating + '
             '[String.IsEqual(Container(5500).ListItem(0).Property(param.imdb_id),ListItem.IMDBNumber) | '
             'String.IsEqual(Container(5500).ListItem(0).Property(param.query),ListItem.Title)]', timeout=45)
    _focus_is(9001)
    screenshot('vertical-movie-top')
    _down(5500)
    _up(5521)  # the cast tab of the tab row 5520
    _up(9001)
    action('up', delay=1)
    wait_for('!Window.IsActive(movieinformation)', timeout=10)
    assert _true('Window.IsActive(home)')


def test_tmdb_page_up_from_the_top_steps_back_in_the_chain(matrix):
    builtin('NotifyAll(nightcity,info:movie:{})'.format(matrix))
    wait_for('Window.IsActive(movieinformation)', timeout=20)
    wait_for('Integer.IsGreater(Container(5500).NumItems,0)', timeout=45)
    _down(5500)
    action('select')
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),2)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.Property(tmdb_type),person)', timeout=20)
    # TMDb Helper polls for the page every half second; Back before it saw the page stalls it
    time.sleep(1.5)
    _focus_is(9004)
    action('up', delay=1)
    wait_for('String.IsEqual(Window(Home).Property(TMDbHelper.Position),1)', timeout=30)
    wait_for('Window.IsActive(movieinformation) + String.IsEqual(ListItem.DBID,{})'.format(matrix), timeout=20)
