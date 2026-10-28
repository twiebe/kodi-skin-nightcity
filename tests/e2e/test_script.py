import time

import pytest

from conftest import builtin, info, rpc, wait_for

pytestmark = pytest.mark.e2e



def kdev_show():
    show = rpc('VideoLibrary.GetTVShows', {'filter': {'field': 'title', 'operator': 'is', 'value': 'Kdev Show'}})['tvshows'][0]
    episodes = rpc('VideoLibrary.GetEpisodes', {'tvshowid': show['tvshowid'], 'properties': ['season', 'episode'],
                                                'sort': {'method': 'episode'}})['episodes']
    return show['tvshowid'], episodes


def reset(episodes):
    for e in episodes:
        rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': e['episodeid'], 'playcount': 0,
                                               'resume': {'position': 0, 'total': 0}})


@pytest.fixture
def show(home):
    tvshowid, episodes = kdev_show()
    reset(episodes)
    yield tvshowid, episodes
    reset(episodes)
    builtin('Dialog.Close(all,true)')


def test_next_episode_opens_info(show):
    tvshowid, episodes = show
    rpc('VideoLibrary.SetEpisodeDetails', {'episodeid': episodes[0]['episodeid'], 'playcount': 1})
    builtin('NotifyAll(nightcity,next_episode:{})'.format(tvshowid))
    wait_for('Window.IsActive(movieinformation)')
    labels = info('ListItem.Episode', 'ListItem.TvShowDBID', 'ListItem.Plot')
    assert labels['ListItem.Episode'] == '2', labels
    assert labels['ListItem.TvShowDBID'] == str(tvshowid), labels


@pytest.fixture
def selectaction():
    old = rpc('Settings.GetSettingValue', {'setting': 'myvideos.selectaction'})['value']
    rpc('Settings.SetSettingValue', {'setting': 'myvideos.selectaction', 'value': 1})
    builtin('Skin.Reset(nc.selectaction.done)')
    yield
    rpc('Settings.SetSettingValue', {'setting': 'myvideos.selectaction', 'value': old})


def test_startup_sets_selectaction(home, selectaction):
    builtin('NotifyAll(nightcity,startup)')
    time.sleep(2)
    assert rpc('Settings.GetSettingValue', {'setting': 'myvideos.selectaction'})['value'] == 3
