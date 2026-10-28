"""The info page: season tabs and episode list with the opened episode preselected, play and
resume buttons, cast, and for movies the cast and similar-movie rows.

Control.* booleans over JSON-RPC look at the window below a dialog, so these tests read
Container(id).* and System.CurrentControlId, which find the topmost dialog.
"""
import json
import re
import time

import pytest

from conftest import action, builtin, cond, info, kdev, rpc, screenshot, seed, wait_for

pytestmark = pytest.mark.e2e



def show(title):
    tvshowid = rpc('VideoLibrary.GetTVShows', {'filter': {'field': 'title', 'operator': 'is', 'value': title}})['tvshows'][0]['tvshowid']
    episodes = rpc('VideoLibrary.GetEpisodes', {'tvshowid': tvshowid, 'properties': ['season', 'episode', 'title'],
                                                'sort': {'method': 'episode'}})['episodes']
    return tvshowid, episodes


def reset(episodes):
    for e in episodes:
        rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': e['episodeid'], 'playcount': 0,
                                               'resume': {'position': 0, 'total': 0}})


def server_position(item, seconds):
    """Set the resume position on the Jellyfin server: jellyfin-kodi resolves playback with the
    server's position, so Kodi's own resume point alone does not move the start."""
    data = seed()
    path = '/UserItems/{}/UserData?userId={}'.format(data['items'][item], data['users'][data['user']]['id'])
    kdev('jf', 'POST', path, json.dumps({'PlaybackPositionTicks': int(seconds * 10_000_000)}))


def label(name):
    return info(name)[name]


def stop():
    if rpc('Player.GetActivePlayers'):
        rpc('Player.Stop', {'playerid': 1})
        time.sleep(1)


@pytest.fixture
def kdev_show(home):
    tvshowid, episodes = show('Kdev Show')
    reset(episodes)
    yield tvshowid, episodes
    stop()
    reset(episodes)
    builtin('Dialog.Close(all,true)')


def open_episode_info(tvshowid):
    """next_episode opens the info page of the first unwatched episode."""
    builtin('ClearProperty(nc.info.ready,home)')
    builtin('NotifyAll(nightcity,next_episode:{})'.format(tvshowid))
    wait_for('Window.IsActive(movieinformation)')
    # info_select preselects the episode and puts focus back on play; wait until it is done
    wait_for('!String.IsEmpty(Window(Home).Property(nc.info.ready))')


def test_episode_info_preselects(kdev_show):
    tvshowid, episodes = kdev_show
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodes[0]['episodeid'], 'playcount': 1})
    open_episode_info(tvshowid)
    wait_for('String.IsEqual(Container(5100).ListItem.Episode,2)', timeout=5)
    assert label('Container(5200).ListItem.Season') == '1'
    screenshot('info-episode')


def test_episode_focus_updates_head(kdev_show):
    tvshowid, episodes = kdev_show
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodes[0]['episodeid'], 'playcount': 1})
    open_episode_info(tvshowid)
    wait_for('String.IsEqual(Container(5100).ListItem.Episode,2)', timeout=5)
    builtin('SetFocus(5100)')
    action('right')
    wait_for('String.Contains(Control.GetLabel(9020),Third)')


TAGS = re.compile(r'\[/?[A-Z]+[^\]]*\]')


def plain(control_id):
    """Text of a label without formatting tags, upper case (labels are set in [UPPERCASE])."""
    return TAGS.sub('', label('Control.GetLabel({})'.format(control_id))).upper()


def test_info_netrunner_episode(kdev_show):
    tvshowid, episodes = kdev_show
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodes[0]['episodeid'], 'playcount': 1})
    open_episode_info(tvshowid)
    wait_for('String.IsEqual(Container(5100).ListItem.Episode,2)', timeout=5)
    path = plain(9026)
    assert 'KDEV SHOW' in path and 'S01 E02' in path, path
    assert 'KDEV SHOW' in plain(9025)
    screenshot('info-episode')


def test_info_without_fanart(kdev_show):
    """Review focus: an episode without fanart shows the plain background, no empty image."""
    tvshowid, episodes = kdev_show
    open_episode_info(tvshowid)
    assert not label('Container(5100).ListItem.Art(fanart)')
    assert not label('ListItem.Art(fanart)')
    screenshot('info-no-fanart')


def test_season_switch(home):
    tvshowid, episodes = show('BulkShow 00')
    reset(episodes)
    try:
        open_episode_info(tvshowid)
        wait_for('String.IsEqual(Container(5200).ListItem.Season,1)', timeout=5)
        builtin('SetFocus(5200)')
        action('right')
        wait_for('String.IsEqual(Container(5200).ListItem.Season,2)')
        wait_for('String.IsEqual(Container(5100).ListItemAbsolute(0).Season,2)')
    finally:
        builtin('Dialog.Close(all,true)')


def seconds(text):
    total = 0
    for part in text.split(':'):
        total = total * 60 + int(part)
    return total


def close_returned_info():
    """Playback started from an info page brings it back after the stop: close it again."""
    wait_for('Window.IsActive(movieinformation)', timeout=5)
    action('back', delay=1)
    wait_for('!Window.IsActive(movieinformation)')


def resume_at(episodeid, seconds):
    """Set the resume point in Kodi until one sticks: jellyfin-kodi syncs server changes (also
    the previous test's reset to 0) into Kodi's database a moment later, rounded to its own
    value."""
    stable = 0
    for _ in range(20):
        details = rpc('VideoLibrary.GetEpisodeDetails', {'episodeid': episodeid, 'properties': ['resume']})
        if int(details['episodedetails']['resume']['position']) > 0:
            stable += 1
            if stable == 3:
                return
        else:
            stable = 0
            rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodeid,
                                                   'resume': {'position': seconds, 'total': 600}})
        time.sleep(0.5)
    raise AssertionError('resume point did not stick')


def play_with(button, tvshowid, episodes):
    server_position('Kdev Show Pilot', 120)
    resume_at(episodes[0]['episodeid'], 120)
    open_episode_info(tvshowid)
    wait_for('String.IsEqual(Container(5100).ListItem.Episode,1)', timeout=5)
    # from start shows once the list has the resume point, which jellyfin-kodi may rewrite late
    wait_for('Control.IsVisible({})'.format(button), timeout=10)
    builtin('SetFocus({})'.format(button))
    wait_for('Integer.IsEqual(System.CurrentControlId,{})'.format(button))
    action('select')
    wait_for('Player.HasVideo', timeout=20)
    time.sleep(3)
    return seconds(label('Player.Time'))


def test_resume_button(kdev_show):
    tvshowid, episodes = kdev_show
    try:
        assert play_with(9001, tvshowid, episodes) > 110
    finally:
        stop()
        close_returned_info()
        server_position('Kdev Show Pilot', 0)


def test_from_start_button(kdev_show):
    tvshowid, episodes = kdev_show
    try:
        assert play_with(9002, tvshowid, episodes) < 10
    finally:
        stop()
        close_returned_info()
        server_position('Kdev Show Pilot', 0)


def test_stop_returns_to_episode(kdev_show):
    """After playing an episode from its info page, stopping brings the info page back with the
    episode that played last selected, also when playback moved on to another episode."""
    tvshowid, episodes = kdev_show
    open_episode_info(tvshowid)
    builtin('SetFocus(9001)')
    wait_for('Integer.IsEqual(System.CurrentControlId,9001)')
    action('select')
    wait_for('Player.HasVideo', timeout=20)
    wait_for('Window.IsActive(fullscreenvideo)')
    time.sleep(2)
    second = episodes[1]
    rpc('Player.Open', {'item': {'episodeid': second['episodeid']}})
    wait_for('String.IsEqual(VideoPlayer.DBID,{})'.format(second['episodeid']), timeout=20)
    time.sleep(2)
    stop()
    wait_for('Window.IsActive(movieinformation)', timeout=15)
    wait_for('!String.IsEmpty(Window(Home).Property(nc.info.ready))')
    assert label('Container(5100).ListItem.Episode') == str(second['episode'])
    screenshot('info-after-stop')


def test_play_never_shows_home(kdev_show):
    """The info page stays until the video is up: no flash of Home while playback starts."""
    tvshowid, episodes = kdev_show
    open_episode_info(tvshowid)
    builtin('SetFocus(9001)')
    wait_for('Integer.IsEqual(System.CurrentControlId,9001)')
    action('select')
    seen = []
    end = time.time() + 15
    while time.time() < end and not cond('Player.HasVideo + !Window.IsVisible(movieinformation)')[
            'Player.HasVideo + !Window.IsVisible(movieinformation)']:
        state = cond('Window.IsVisible(movieinformation) | Window.IsActive(fullscreenvideo)')
        seen.append(list(state.values())[0])
        time.sleep(0.1)
    try:
        assert seen and all(seen)
        wait_for('Window.IsActive(fullscreenvideo) + !Window.IsVisible(movieinformation)', timeout=10)
    finally:
        stop()
        close_returned_info()


def test_stop_never_shows_home(kdev_show):
    """From the stop until the info page is back, Home shows only its cover (nc.returning)."""
    tvshowid, episodes = kdev_show
    open_episode_info(tvshowid)
    builtin('SetFocus(9001)')
    wait_for('Integer.IsEqual(System.CurrentControlId,9001)')
    action('select')
    wait_for('Window.IsActive(fullscreenvideo) + !Window.IsVisible(movieinformation)', timeout=20)
    time.sleep(2)
    rpc('Player.Stop', {'playerid': 1})
    covered = 'Window.IsActive(fullscreenvideo) | Window.IsVisible(movieinformation) | ' \
              '!String.IsEmpty(Window(Home).Property(nc.returning))'
    seen = []
    end = time.time() + 15
    while time.time() < end and not cond('Window.IsVisible(movieinformation)')['Window.IsVisible(movieinformation)']:
        seen.append(cond(covered)[covered])
        time.sleep(0.1)
    assert seen and all(seen)
    wait_for('String.IsEmpty(Window(Home).Property(nc.returning))')
    action('back', delay=1)
    assert not cond('!String.IsEmpty(Window(Home).Property(nc.returning))')[
        '!String.IsEmpty(Window(Home).Property(nc.returning))']


def test_return_skips_open_info_page(kdev_show):
    """An info page opened right after the stop is not covered by a second one."""
    tvshowid, episodes = kdev_show
    open_episode_info(tvshowid)
    builtin('SetFocus(9001)')
    wait_for('Integer.IsEqual(System.CurrentControlId,9001)')
    action('select')
    wait_for('Window.IsActive(fullscreenvideo)', timeout=20)
    time.sleep(2)
    rpc('Player.Stop', {'playerid': 1})
    builtin('NotifyAll(nightcity,next_episode:{})'.format(tvshowid))
    wait_for('Window.IsActive(movieinformation)')
    time.sleep(4)  # the stop's return would come within this
    action('back', delay=1.5)
    assert not cond('Window.IsActive(movieinformation)')['Window.IsActive(movieinformation)']


def test_movie_info_rows(home):
    wait_for('Integer.IsGreater(Container(9202).NumItems,0)')
    builtin('SetFocus(9202,0,absolute)')
    action('select')
    try:
        wait_for('Window.IsActive(movieinformation)')
        assert label('ListItem.DBType') == 'movie'
        title = label('ListItem.Title')
        wait_for('String.Contains(Control.GetLabel(9030),{})'.format(title))
        # the similar movies come from TMDb: kodi-dev's own movies have no TMDb or IMDb id and
        # get none, a movie TMDb knows (The Matrix, added for the chain tests) gets them
        details = rpc('VideoLibrary.GetMovieDetails', {'movieid': int(label('ListItem.DBID')),
                                                       'properties': ['uniqueid']})['moviedetails']
        if {'tmdb', 'imdb'} & set(details.get('uniqueid') or {}):
            wait_for('Integer.IsGreater(Container(5300).NumItems,0) + !Container(5300).IsUpdating', timeout=30)
        else:
            wait_for('!Container(5300).IsUpdating', timeout=30)
            assert label('Container(5300).NumItems') in ('', '0')
        screenshot('info-movie')
    finally:
        builtin('Dialog.Close(all,true)')


def test_info_command_replaces_info_page(home):
    movies = rpc('VideoLibrary.GetMovies', {'properties': ['title'], 'limits': {'end': 2}})['movies']
    builtin('SetFocus(9202,0,absolute)')
    action('select')
    try:
        wait_for('Window.IsActive(movieinformation)')
        other = next(m for m in movies if m['title'] != label('ListItem.Title'))
        builtin('NotifyAll(nightcity,info:movie:{})'.format(other['movieid']))
        wait_for('String.Contains(Control.GetLabel(9030),{})'.format(other['title']), timeout=10)
        wait_for('Window.IsActive(movieinformation)')
    finally:
        builtin('Dialog.Close(all,true)')


def test_spotlight_play_starts_movie(home):
    try:
        builtin('SetFocus(9010)')
        wait_for('Integer.IsEqual(System.CurrentControlId,9010)')
        action('select')
        wait_for('Player.HasVideo', timeout=20)
    finally:
        stop()
