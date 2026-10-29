import pytest
import importlib.util
import json
import urllib.parse
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
nightcity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightcity)


def ep(season, episode, playcount=0, position=0.0):
    return {'episodeid': season * 100 + episode, 'season': season, 'episode': episode,
            'playcount': playcount, 'resume': {'position': position, 'total': 3000.0}}


def pick(episodes):
    found = nightcity.pick_next_episode(episodes)
    return found and (found['season'], found['episode'])


def test_pick_resumable_first():
    assert pick([ep(1, 1), ep(1, 4, playcount=1), ep(1, 5, position=300), ep(1, 6)]) == (1, 5)


def test_pick_first_unwatched_regular():
    assert pick([ep(0, 1), ep(1, 1, 1), ep(1, 2, 1), ep(1, 3), ep(1, 4)]) == (1, 3)


def test_pick_ignores_order_of_input():
    assert pick([ep(2, 1), ep(1, 2), ep(1, 1, 1)]) == (1, 2)


def test_pick_all_watched():
    assert pick([ep(1, 2, 1), ep(1, 1, 1), ep(2, 1, 1)]) == (1, 1)


def test_pick_only_specials():
    assert pick([ep(0, 2), ep(0, 1)]) == (0, 1)


def test_pick_empty():
    assert nightcity.pick_next_episode([]) is None


def test_index_of_gap():
    items = [ep(1, 1), ep(1, 2), ep(1, 4), ep(1, 5)]
    assert nightcity.index_of(items, 'episodeid', 104) == 2


def test_index_of_missing():
    assert nightcity.index_of([ep(1, 1)], 'episodeid', 999) == 0


def test_top_genres():
    counts = {'Drama': (3, 10), 'Action': (1, 10), 'Comedy': (2, 4), 'Horror': (4, 7)}
    assert nightcity.top_genres(counts) == [(1, 'Action'), (3, 'Drama'), (4, 'Horror')]


def test_top_genres_special_chars():
    counts = {'Action & Adventure': (7, 5), 'Science Fiction': (8, 2)}
    assert nightcity.top_genres(counts, 1) == [(7, 'Action & Adventure')]


def test_genre_counts():
    genres = [{'genreid': 1, 'label': 'Drama'}, {'genreid': 2, 'label': 'Action'}, {'genreid': 3, 'label': 'Empty'}]
    movies = [{'genre': ['Drama', 'Action']}, {'genre': ['Drama']}, {'genre': []}]
    assert nightcity.genre_counts(movies, genres) == {'Drama': (1, 2), 'Action': (2, 1)}


def test_genre_counts_unknown_label():
    assert nightcity.genre_counts([{'genre': ['Ghost']}], [{'genreid': 1, 'label': 'Drama'}]) == {}


def test_find_index_skips_all_seasons_item():
    # the season list starts with "* All seasons" (season -1) when Kodi shows all items
    assert nightcity.find_index(['-1', '1', '2'], '2') == 2


def test_find_index_missing():
    assert nightcity.find_index(['1', '2'], '5') is None


def test_player_open_params_resume_episode():
    assert nightcity.player_open_params('episode', '7', 'resume') == {
        'item': {'episodeid': 7}, 'options': {'resume': True}}


def test_player_open_params_from_start_movie():
    assert nightcity.player_open_params('movie', '3', 'noresume') == {
        'item': {'movieid': 3}, 'options': {'resume': False}}


class FakeXbmc:
    """Stands in for the xbmc module: conditions in `true` hold, labels come from `labels`."""

    def __init__(self, true, labels):
        self.true, self.labels, self.builtins = true, labels, []

    def getCondVisibility(self, condition):
        return condition in self.true

    def getInfoLabel(self, label):
        return self.labels.get(label, '')

    def executebuiltin(self, command):
        self.builtins.append(command)

    class Monitor:
        def waitForAbort(self, timeout):
            return True


def test_select_episode_leaves_focus_alone_after_close(monkeypatch):
    fake = FakeXbmc({'Integer.IsGreater(Container(5200).NumItems,0)',
                     'String.IsEqual(Container(5100).ListItemAbsolute(0).Season,1)'},
                    {'ListItem.Season': '1', 'ListItem.Episode': '2', 'Container(5200).NumItems': '1',
                     'Container(5200).ListItemAbsolute(0).Season': '1', 'Container(5100).NumItems': '2',
                     'Container(5100).ListItemAbsolute(0).Episode': '1',
                     'Container(5100).ListItemAbsolute(1).Episode': '2'})
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    nightcity._select_episode()
    assert not any(b.startswith('SetFocus') for b in fake.builtins), fake.builtins


def test_player_open_params_without_dbid():
    assert nightcity.player_open_params('episode', '', 'resume') is None


AUDIO = [{'index': 0, 'language': 'ger', 'name': 'Deutsch - AAC-LC stereo', 'channels': 2},
         {'index': 1, 'language': 'eng', 'name': '', 'channels': 6}]
SUBS = [{'index': 0, 'language': 'ger', 'name': '', 'isforced': False, 'isimpaired': False},
        {'index': 1, 'language': 'eng', 'name': 'Signs', 'isforced': True, 'isimpaired': True}]
NAMES = {'ger': 'German', 'eng': 'English'}.get


def test_audio_rows_mark_current():
    rows = nightcity.audio_rows(AUDIO, {'index': 1}, NAMES)
    assert rows == [{'label': 'Deutsch - AAC-LC stereo', 'tag': 'GER', 'current': ''},
                    {'label': 'English 5.1', 'tag': 'ENG', 'current': '1'}]


def test_subtitle_rows_name_flags_and_off():
    rows = nightcity.subtitle_rows(SUBS, {'index': 1}, True, NAMES)
    assert rows == [{'label': 'German', 'tag': 'GER', 'current': ''},
                    {'label': 'English · Signs · forced · SDH', 'tag': 'ENG', 'current': '1'}]
    assert all(not r['current'] for r in nightcity.subtitle_rows(SUBS, {'index': 1}, False, NAMES))


def test_unknown_language_falls_back_to_code_or_number():
    rows = nightcity.audio_rows([{'index': 3, 'language': '', 'name': '', 'channels': 1}], {}, NAMES)
    assert rows == [{'label': '#4 mono', 'tag': '', 'current': ''}]


WORDS = {'off': 'off', 'more': 'all settings'}


def test_audio_panel_rows_and_actions():
    props = {'audiostreams': AUDIO, 'currentaudiostream': {'index': 1}}
    rows = nightcity.panel('audio', props, NAMES, WORDS)
    assert [r['action'] for r in rows] == [('audio', 0), ('audio', 1), ('settings', 'osdaudiosettings')]
    assert rows[-1]['label'] == '… all settings'
    assert nightcity.current_position(rows) == 1


def test_subtitle_panel_starts_with_off():
    props = {'subtitles': SUBS, 'currentsubtitle': {'index': 0}, 'subtitleenabled': False}
    rows = nightcity.panel('sub', props, NAMES, WORDS)
    assert [r['action'] for r in rows] == [('subtitle', 'off'), ('subtitle', 0), ('subtitle', 1),
                                           ('settings', 'osdsubtitlesettings')]
    assert nightcity.current_position(rows) == 0
    props['subtitleenabled'] = True
    assert nightcity.current_position(nightcity.panel('sub', props, NAMES, WORDS)) == 1


def test_subtitle_panel_without_tracks_is_off():
    rows = nightcity.panel('sub', {'subtitles': [], 'subtitleenabled': True}, NAMES, WORDS)
    assert rows[0]['current'] == '1' and len(rows) == 2


def test_search_paths_escape_term():
    paths = nightcity.search_paths('Blade, "Runner" & co')
    rule = json.loads(urllib.parse.unquote(paths['movies'].split('?xsp=', 1)[1]))
    assert rule == {'rules': {'and': [{'field': 'title', 'operator': 'contains', 'value': ['Blade, "Runner" & co']}]},
                    'type': 'movies'}
    assert paths['movies'].startswith('videodb://movies/titles/?xsp=')
    assert paths['tvshows'].startswith('videodb://tvshows/titles/?xsp=')
    assert paths['episodes'].startswith('videodb://tvshows/titles/-1/-1/?xsp=')
    assert paths['tmdb_movies'] == ('plugin://plugin.video.themoviedb.helper/?info=search&tmdb_type=movie'
                                    '&query=Blade%2C%20%22Runner%22%20%26%20co')
    assert 'tmdb_type=tv&' in paths['tmdb_tvshows']
    assert ',' not in paths['movies'] and ',' not in paths['tmdb_movies']


def test_search_paths_empty_term():
    assert set(nightcity.search_paths('').values()) == {''}


def test_remember_puts_term_first_once():
    assert nightcity.remember(['dune', 'alien', 'heat'], 'Alien') == ['Alien', 'dune', 'heat']
    assert nightcity.remember(['a', 'b', 'c', 'd', 'e'], 'f') == ['f', 'a', 'b', 'c', 'd']
    assert nightcity.remember(['a'], '  ') == ['a']


def _many(n):
    return [{'index': i, 'language': 'eng', 'name': 'Track {}'.format(i), 'channels': 2,
             'isforced': False, 'isimpaired': False} for i in range(n)]


WORDS = {'off': 'off', 'more': 'all settings'}


def test_panel_caps_long_subtitle_lists():
    """The panel has PANEL_SLOTS rows: long lists keep "off", the playing track and the
    settings row."""
    props = {'subtitles': _many(20), 'currentsubtitle': {'index': 17}, 'subtitleenabled': True}
    rows = nightcity.panel('sub', props, NAMES, WORDS)
    assert len(rows) == nightcity.PANEL_SLOTS
    assert rows[0]['action'] == ('subtitle', 'off') and rows[-1]['action'][0] == 'settings'
    assert [r['action'] for r in rows if r['current']] == [('subtitle', 17)]


def test_panel_caps_long_audio_lists():
    props = {'audiostreams': _many(20), 'currentaudiostream': {'index': 0}}
    rows = nightcity.panel('audio', props, NAMES, WORDS)
    assert len(rows) == nightcity.PANEL_SLOTS and rows[-1]['action'][0] == 'settings'
    assert [r['action'] for r in rows if r['current']] == [('audio', 0)]


def test_playback_over_waits_longer_after_an_end():
    """A stop ends the playback at once; after a file ended, the next episode may take a while
    to start (NAS spin-up, plugin, refresh-rate switch)."""
    assert nightcity.playback_over(idle=0.1, stopped=True)
    assert not nightcity.playback_over(idle=5.0, stopped=False)
    assert nightcity.playback_over(idle=15.0, stopped=False)


def test_power_runs_in_the_quick_menu_without_script():
    """The power commands run as builtins in the quick menu (Custom_1170_QuickMenu.xml)."""
    assert 'power' not in nightcity.COMMANDS and not hasattr(nightcity, 'POWER_CONDITIONS')


def test_audio_rows_without_channels_or_with_title():
    """No "Nonech" for a missing channel count; a title keeps the layout."""
    streams = [{'index': 0, 'language': 'eng', 'name': ''},
               {'index': 1, 'language': 'eng', 'name': 'Commentary', 'channels': 2},
               {'index': 2, 'language': 'eng', 'name': 'Main 5.1', 'channels': 6}]
    labels = [r['label'] for r in nightcity.audio_rows(streams, {}, NAMES)]
    assert labels == ['English', 'Commentary · stereo', 'Main 5.1']


def test_row_is_current_out_of_range():
    """The stream list may shrink between the panel and the click."""
    rows = [{'current': ''}, {'current': '1'}]
    assert nightcity.row_is_current(rows, 2)
    assert not nightcity.row_is_current(rows, 1)
    assert not nightcity.row_is_current(rows, 5)


def follow(steps, dbid=1):
    """Feed (seconds, has_media, has_video, is_episode, playing_dbid, stopped) steps."""
    follower = nightcity.EpisodeFollower(dbid)
    result = 'follow'
    for seconds, media, video, episode, playing, stopped in steps:
        for _ in range(int(seconds / 0.5)):
            result = follower.tick(media, video, episode, playing, stopped, 0.5)
            if result != 'follow':
                return result, follower.last
    return result, follower.last


def test_follower_stop_returns_to_last_episode():
    assert follow([(5, True, True, True, '7', False), (2, False, False, False, '', True)]) == ('done', 7)


def test_follower_survives_intro_before_episode():
    """Jellyfin intros or a trailer play first: not an episode, but the episode comes."""
    steps = [(6, True, True, False, '', False), (5, True, True, True, '8', False), (2, False, False, False, '', True)]
    assert follow(steps) == ('done', 8)


def test_follower_survives_stop_while_next_starts():
    """A plugin path stops its placeholder and starts the resolved file; media stays loaded."""
    steps = [(3, True, True, True, '7', False), (3, True, False, False, '', True), (4, True, True, True, '9', False),
             (2, False, False, False, '', True)]
    assert follow(steps) == ('done', 9)


def test_follower_waits_after_an_end():
    steps = [(3, True, True, True, '7', False), (6, False, False, False, '', False), (3, True, True, True, '8', False),
             (16, False, False, False, '', False)]
    assert follow(steps) == ('done', 8)


def test_follower_gives_up_on_a_movie():
    assert follow([(3, True, True, True, '7', False), (15, True, True, False, '', False)]) == ('abort', 7)


def test_search_batches_start_tmdb_one_after_the_other():
    """Two TMDb Helper searches starting at once start two Python interpreters at once, which
    crashes Kodi: the tv search comes in a second batch."""
    paths = nightcity.search_paths('dune')
    first, second = nightcity.search_batches('dune')
    assert first == dict(paths, tmdb_tvshows='')
    assert second == {'tmdb_tvshows': paths['tmdb_tvshows']}


def test_info_claimed_while_another_script_opens_one():
    """A script opening an info page claims it for a few seconds: two info pages opening at once
    crash Kodi, so the return after a stop stands back."""
    assert nightcity.info_claimed('100.0', now=102.0)
    assert not nightcity.info_claimed('100.0', now=100.0 + nightcity.INFO_CLAIM)
    assert not nightcity.info_claimed('', now=100.0)
    assert not nightcity.info_claimed('junk', now=100.0)


class FakeWindow:
    def __init__(self):
        self.props = {}

    def setProperty(self, key, value):
        self.props[key] = value


def _startup_env(monkeypatch, done=False, rpc_error=False, profile='/nonexistent'):
    fake = FakeXbmc({'Skin.HasSetting(nc.selectaction.done)'} if done else set(), {})
    window = FakeWindow()
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    xbmcvfs = __import__('types').SimpleNamespace(
        translatePath=lambda p: p.replace('special://profile', str(profile)))
    monkeypatch.setitem(__import__('sys').modules, 'xbmcvfs', xbmcvfs)
    monkeypatch.setattr(nightcity, '_home', lambda: window)

    def rpc(method, **params):
        if rpc_error:
            raise RuntimeError(method)
    monkeypatch.setattr(nightcity, '_rpc', rpc)
    fake.keymaps = 0

    def home_keymap():
        fake.keymaps += 1
    monkeypatch.setattr(nightcity, 'home_keymap', home_keymap)
    return fake, window


def test_startup_applies_the_home_keymap(monkeypatch):
    """Startup writes the Home key keymap (or removes it when switched off), in its own run."""
    fake, _ = _startup_env(monkeypatch, done=True)
    nightcity.startup()
    assert fake.keymaps == 1


RETROWAVE_SETTINGS = """<settings>
    <setting id="rw.menu.hide.shows" type="bool">true</setting>
    <setting id="rw.menu.hide.search" type="bool">false</setting>
    <setting id="rw.home.slot1" type="string">genres,movies</setting>
    <setting id="rw.home.slot2" type="string">say "hi" \\ there</setting>
    <setting id="rw.home.slot3" type="string"></setting>
    <setting id="glowoff" type="bool">true</setting>
</settings>"""


def test_retrowave_settings_as_builtins():
    """The skin was skin.retrowave before 0.4.45, its settings were rw.*: the same values as
    nc.*, other names as they are. Unset settings stay at their default."""
    assert nightcity.old_settings_builtins(RETROWAVE_SETTINGS) == [
        'Skin.SetBool(nc.menu.hide.shows)',
        'Skin.SetString(nc.home.slot1,"genres,movies")',
        'Skin.SetString(nc.home.slot2,"say \\"hi\\" \\\\ there")',
        'Skin.SetBool(glowoff)']


def test_broken_retrowave_settings_take_nothing():
    assert nightcity.old_settings_builtins('<settings><setting') == []


def test_startup_takes_the_retrowave_settings_once(monkeypatch, tmp_path):
    old = tmp_path / 'addon_data' / 'skin.retrowave' / 'settings.xml'
    old.parent.mkdir(parents=True)
    old.write_text(RETROWAVE_SETTINGS)
    fake, _ = _startup_env(monkeypatch, done=True, profile=tmp_path)
    nightcity.startup()
    taken = [b for b in fake.builtins if 'menu.hide' in b or 'nc.migrated' in b]
    assert taken == ['Skin.SetBool(nc.menu.hide.shows)', 'Skin.SetBool(nc.migrated)']
    fake.true.add('Skin.HasSetting(nc.migrated)')
    fake.builtins.clear()
    nightcity.startup()
    assert not [b for b in fake.builtins if 'menu.hide' in b or 'nc.migrated' in b]


def test_startup_without_retrowave_marks_nothing_to_take(monkeypatch):
    fake, _ = _startup_env(monkeypatch, done=True)
    nightcity.startup()
    assert 'Skin.SetBool(nc.migrated)' in fake.builtins


def test_startup_signals_ready(monkeypatch):
    fake, window = _startup_env(monkeypatch)
    nightcity.startup()
    assert 'Skin.SetBool(nc.selectaction.done)' in fake.builtins
    assert window.props == {'nc.startup.ready': '1'}


def test_startup_signals_ready_when_already_done(monkeypatch):
    _, window = _startup_env(monkeypatch, done=True)
    nightcity.startup()
    assert window.props == {'nc.startup.ready': '1'}


def test_startup_signals_ready_after_an_error(monkeypatch):
    """Startup waits for the flag: a failing setting must not keep it up until the timeout."""
    _, window = _startup_env(monkeypatch, rpc_error=True)
    try:
        nightcity.startup()
    except RuntimeError:
        pass
    assert window.props == {'nc.startup.ready': '1'}


# Home pages: catalogue, defaults and the section dialog

def test_catalogue_per_page():
    keys = {page: [key for key, _ in sections] for page, sections in nightcity.CATALOGUE.items()}
    assert keys == {
        'home': ['continue', 'nextup', 'newmovies', 'newepisodes', 'genres', 'random', 'unwatched',
                 'toprated', 'favourites', 'trending', 'recent'],
        'movies': ['continue', 'newmovies', 'unwatched', 'random', 'toprated', 'genres', 'sets', 'trending'],
        'shows': ['nextup', 'newepisodes', 'inprogress', 'unwatched', 'genres', 'trending'],
    }
    options = {key: [value for value, _ in opts] for key, opts in nightcity.CATALOGUE['home']}
    assert options['continue'] == ['both', 'movies', 'shows']
    assert options['unwatched'] == ['movies', 'shows', 'both']
    assert options['recent'] == ['both', 'movies', 'shows']
    assert options['newmovies'] == options['random'] == ['all', 'unwatched']
    assert options['genres'] == options['toprated'] == options['trending'] == ['movies', 'shows']
    assert options['nextup'] == options['favourites'] == []
    for page, sections in nightcity.CATALOGUE.items():
        for key, _ in sections:
            assert key in nightcity.SECTIONS, (page, key)


def test_default_slots_are_todays_rows():
    assert nightcity.default_slots('home') == ['continue', 'newmovies', 'newepisodes', 'nextup'] + ['none'] * 4
    assert nightcity.default_slots('movies') == ['newmovies', 'continue', 'unwatched', 'genres'] + ['none'] * 4
    assert nightcity.default_slots('shows') == ['nextup', 'newepisodes', 'inprogress', 'unwatched'] + ['none'] * 4


def test_slot_values_fill_defaults():
    raw = [('', ''), ('none', ''), ('toprated', 'shows'), ('bogus', 'x')] + [('', '')] * 4
    slots = nightcity.slot_values('home', raw)
    assert slots[:4] == [('continue', ''), ('none', ''), ('toprated', 'shows'), ('none', '')]
    assert slots[4:] == [('none', '')] * 4


def home_slots():
    return nightcity.slot_values('home', [('', '')] * 8)


def test_section_rows_mark_used_slots():
    rows = nightcity.section_rows('home', home_slots(), 1)
    assert rows[0] == ('none', None) and rows[-1] == ('move', None)
    used = dict(rows)
    assert used['continue'] is None  # the slot itself
    assert used['newmovies'] == 2 and used['nextup'] == 4
    assert used['favourites'] is None
    assert [k for k, _ in rows[1:-1]] == [k for k, _ in nightcity.CATALOGUE['home']]


def test_pick_free_section_resets_option():
    slots = home_slots()
    slots[0] = ('continue', 'shows')
    assert nightcity.apply_pick(slots, 1, 'favourites') == {1: ('favourites', '')}


def test_pick_used_section_swaps():
    slots = home_slots()
    slots[0] = ('continue', 'movies')
    assert nightcity.apply_pick(slots, 1, 'nextup') == {1: ('nextup', ''), 4: ('continue', 'movies')}


def test_pick_empty_and_same():
    slots = home_slots()
    assert nightcity.apply_pick(slots, 2, 'none') == {2: ('none', '')}
    assert nightcity.apply_pick(slots, 2, 'newmovies') == {}
    assert nightcity.apply_pick(slots, 5, 'none') == {}


def test_pick_into_empty_slot_from_used_one_leaves_empty_behind():
    slots = home_slots()
    assert nightcity.apply_pick(slots, 6, 'newmovies') == {6: ('newmovies', ''), 2: ('none', '')}

def test_chain_paths():
    """Pages pushed into TMDb Helper's window manager: library items by database id (the manager
    builds them itself, no script.skinvariables needed), others by TMDb id."""
    assert nightcity.chain_path('episode', 7) == 'plugin://script.skinvariables/?info=get_dbitem_episode_details&dbid=7'
    assert nightcity.chain_path('movie', '3') == 'plugin://script.skinvariables/?info=get_dbitem_movie_details&dbid=3'


class ChainWindow(FakeWindow):
    def __init__(self, running):
        super().__init__()
        if running:
            self.props['TMDbHelper.Instance'] = 'True'

    def getProperty(self, key):
        return self.props.get(key, '')

    def clearProperty(self, key):
        self.props.pop(key, None)


def test_chain_running():
    assert nightcity.chain_running(ChainWindow(True))
    assert not nightcity.chain_running(ChainWindow(False))


def test_next_episode_joins_a_running_chain(monkeypatch):
    """While the manager runs it owns the info dialog: the episode goes onto its stack instead of
    a second info dialog of our own."""
    window = ChainWindow(True)
    monkeypatch.setattr(nightcity, '_home', lambda: window)
    monkeypatch.setattr(nightcity, '_rpc', lambda method, **params: {'episodes': [
        {'episodeid': 9, 'season': 1, 'episode': 1, 'playcount': 0, 'resume': {}, 'file': 'f', 'title': 't'}]})
    monkeypatch.setitem(__import__('sys').modules, 'xbmcgui', None)  # Dialog().info must not run
    nightcity.next_episode('4')
    assert window.props['TMDbHelper.Path.To.Add'] == nightcity.chain_path('episode', 9)


def test_return_after_stop_leaves_a_running_chain_alone(monkeypatch):
    """After playback the script reopens the episode's info page, not while a chain runs."""
    window = ChainWindow(True)
    fake = FakeXbmc({'Window.IsActive(home) | Window.IsActive(videos)'}, {})
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    monkeypatch.setattr(nightcity, '_wait', lambda condition, timeout=5.0: True)
    opened = []
    monkeypatch.setattr(nightcity, '_episode_info', opened.append)
    monkeypatch.setattr(nightcity, '_claim_info', lambda: None)
    monkeypatch.setattr(nightcity, '_log', lambda message: None)

    class Done:
        last = 5

        def tick(self, *args):
            return 'done'
    monkeypatch.setattr(nightcity, 'EpisodeFollower', lambda dbid: Done())

    class Monitor:
        def waitForAbort(self, timeout):
            return False
    assert not nightcity._follow(5, Monitor(), type('P', (), {'stopped': True})(), window)
    assert opened == []


def test_play_ends_a_running_chain_first(monkeypatch):
    """Play on a page of the chain asks the manager to exit and waits until it has, so the info
    dialog it closes is not mistaken for a Back press."""
    window = ChainWindow(True)
    calls = []
    monkeypatch.setattr(nightcity, '_home', lambda: window)
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', FakeXbmc(set(), {}))

    def wait(condition, timeout=5.0):
        calls.append(('wait', condition))
        if 'TMDbHelper.Instance' in condition:
            assert window.props.get('TMDbHelper.Command') == 'exit'
        return False  # playback never starts in the test
    monkeypatch.setattr(nightcity, '_wait', wait)
    monkeypatch.setattr(nightcity, '_rpc', lambda method, **params: calls.append((method, params)))
    monkeypatch.setattr(nightcity, '_log', lambda message: None)
    nightcity.play('movie', '3', 'resume')
    assert calls[0] == ('wait', 'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))')
    assert calls[1][0] == 'Player.Open'


def test_startup_switches_chapter_thumbnails_on_once(monkeypatch):
    """The chapter row shows thumbnails only with Kodi's setting myvideos.extractchapterthumbs;
    switched on once, a user who turns it off again keeps it off."""
    fake = FakeXbmc(set(), {})
    calls = []
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    monkeypatch.setattr(nightcity, '_home', lambda: FakeWindow())
    monkeypatch.setattr(nightcity, '_rpc', lambda method, **params: calls.append(params))
    monkeypatch.setattr(nightcity, 'home_keymap', lambda: None)
    monkeypatch.setattr(nightcity, 'take_old_settings', lambda: None)
    nightcity.startup()
    assert {'setting': 'myvideos.extractchapterthumbs', 'value': True} in calls
    assert 'Skin.SetBool(nc.chapterthumbs.done)' in fake.builtins
    fake = FakeXbmc({'Skin.HasSetting(nc.selectaction.done)', 'Skin.HasSetting(nc.chapterthumbs.done)'}, {})
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    calls.clear()
    nightcity.startup()
    assert calls == []


def test_home_keymap_maps_every_home_key():
    """Kodi's own Home keys: homepage on keyboards, IR and Bluetooth remotes, rootmenu on CEC and
    MCE remotes. Global only: window sections (the player's rootmenu = OSD) keep theirs."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(nightcity.HOME_KEYMAP)
    assert root.find('global/keyboard/homepage').text == 'ActivateWindow(1160)'
    assert root.find('global/remote/rootmenu').text == 'ActivateWindow(1160)'
    assert [w.tag for w in root] == ['global']


def test_home_keymap_long_press_opens_the_quick_menu():
    """Home held: Kodi's power menu, which the skin turns into its quick menu (and closes it when
    it is open). Kodi knows long presses only in the keyboard section (keyboards, IR and Bluetooth
    remotes); a short press then acts when the key is released."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(nightcity.HOME_KEYMAP)
    held = [k for k in root.find('global/keyboard') if k.get('mod') == 'longpress']
    assert [(k.tag, k.text) for k in held] == [(key, 'ActivateWindow(shutdownmenu)')
                                               for key in ('homepage', 'browser_home', 'home')]
    short = [k for k in root.find('global/keyboard') if k.get('mod') is None]
    assert [(k.tag, k.text) for k in short] == [('homepage', 'ActivateWindow(1160)'),
                                                ('browser_home', 'ActivateWindow(1160)')]


def test_home_keymap_loads_before_the_users_own():
    """Kodi loads userdata keymaps in name order, later ones win: the user's own keymaps
    (keymap editor: gen.xml) override the skin's."""
    name = nightcity.HOME_KEYMAP_NAME
    assert name < 'gen.xml' and name < 'keyboard.xml' and name < 'remote.xml'


@pytest.mark.parametrize('off, before, after, changed', [
    (False, None, 'map', True), (False, 'map', 'map', False), (False, 'old', 'map', True),
    (True, 'map', None, True), (True, None, None, False)])
def test_write_home_keymap(tmp_path, off, before, after, changed):
    """Writes the keymap unless switched off, removes it when off, and reports a change only
    when the file changed (Kodi then reloads its keymaps)."""
    path = tmp_path / 'keymaps' / nightcity.HOME_KEYMAP_NAME
    content = {'map': nightcity.HOME_KEYMAP, 'old': '<keymap/>'}
    if before:
        path.parent.mkdir()
        path.write_text(content[before])
    assert nightcity.write_home_keymap(str(path), off) == changed
    assert (path.read_text() if path.exists() else None) == (content[after] if after else None)


@pytest.mark.parametrize('off', [False, True])
def test_home_keymap_reloads_keymaps_on_change(monkeypatch, tmp_path, off):
    import types
    ran = []
    xbmc = types.SimpleNamespace(getCondVisibility=lambda c: off, executebuiltin=ran.append)
    xbmcvfs = types.SimpleNamespace(translatePath=lambda p: str(tmp_path / p.split('//')[1]))
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', xbmc)
    monkeypatch.setitem(__import__('sys').modules, 'xbmcvfs', xbmcvfs)
    if off:
        (tmp_path / 'profile' / 'keymaps').mkdir(parents=True)
        (tmp_path / 'profile' / 'keymaps' / nightcity.HOME_KEYMAP_NAME).write_text('x')
    nightcity.home_keymap()
    assert ran == ['Action(reloadkeymaps)']
    nightcity.home_keymap()
    assert ran == ['Action(reloadkeymaps)']


def test_home_keymap_removes_the_keymaps_of_retrowave(monkeypatch, tmp_path):
    """The skin was skin.retrowave before: its keymaps outlive it in the profile and would map
    the same keys again."""
    import types
    ran = []
    xbmc = types.SimpleNamespace(getCondVisibility=lambda c: False, executebuiltin=ran.append)
    xbmcvfs = types.SimpleNamespace(translatePath=lambda p: str(tmp_path / p.split('//')[1]))
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', xbmc)
    monkeypatch.setitem(__import__('sys').modules, 'xbmcvfs', xbmcvfs)
    keymaps = tmp_path / 'profile' / 'keymaps'
    keymaps.mkdir(parents=True)
    for name in ('0_skin.retrowave.xml', '0_skin.retrowave.back.xml', 'keyboard.xml'):
        (keymaps / name).write_text('x')
    nightcity.home_keymap()
    assert sorted(p.name for p in keymaps.iterdir()) == sorted(
        [nightcity.HOME_KEYMAP_NAME, nightcity.BACK_KEYMAP_NAME, 'keyboard.xml'])
    assert ran == ['Action(reloadkeymaps)']


def test_back_keymap_turns_previous_menu_into_back_on_info_pages():
    """Esc, a gamepad's back button and a right click send PreviousMenu, which <onback> never
    sees: on an info page in a TMDb chain it closed the page before TMDb Helper's manager saw it,
    and the chain hung 30 s (ChainBackGuard, Includes_Tmdb.xml). On info pages they are Back."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(nightcity.BACK_KEYMAP)
    assert [w.tag for w in root] == ['movieinformation']
    keys = {(device.tag, key.tag): key.text for device in root.find('movieinformation') for key in device}
    assert keys == {('keyboard', 'escape'): 'Back', ('gamepad', 'back'): 'Back', ('mouse', 'rightclick'): 'Back'}
    name = nightcity.BACK_KEYMAP_NAME
    assert name < 'gen.xml' and name < 'keyboard.xml' and name != nightcity.HOME_KEYMAP_NAME


@pytest.mark.parametrize('off', [False, True])
def test_back_keymap_is_written_whatever_the_home_key_setting(monkeypatch, tmp_path, off):
    import types
    xbmc = types.SimpleNamespace(getCondVisibility=lambda c: off, executebuiltin=lambda c: None)
    xbmcvfs = types.SimpleNamespace(translatePath=lambda p: str(tmp_path / p.split('//')[1]))
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', xbmc)
    monkeypatch.setitem(__import__('sys').modules, 'xbmcvfs', xbmcvfs)
    nightcity.home_keymap()
    keymaps = tmp_path / 'profile' / 'keymaps'
    assert (keymaps / nightcity.BACK_KEYMAP_NAME).read_text() == nightcity.BACK_KEYMAP
    assert (keymaps / nightcity.HOME_KEYMAP_NAME).exists() != off


def test_video_start_waits_while_the_info_page_is_open():
    """Kodi can take a minute before the player even has media (a busy box, a slow server,
    a 2160p file over HTTPS and the jump to the resume point): the info page waits for the
    video as long as it is open, instead of staying over the video after 60 s."""
    assert nightcity.video_start(fullscreen=True, info_open=True, seconds=0.5) == 'up'
    assert nightcity.video_start(fullscreen=False, info_open=True, seconds=90) == 'wait'
    assert nightcity.video_start(fullscreen=True, info_open=True, seconds=90) == 'up'


def test_video_start_stops_when_the_info_page_is_closed():
    """Closed by the user (Back, another page): nothing left to close, stop waiting."""
    assert nightcity.video_start(fullscreen=False, info_open=False, seconds=2) == 'failed'


def test_video_start_gives_up_at_last():
    assert nightcity.video_start(fullscreen=False, info_open=True, seconds=nightcity.LOAD_TIMEOUT) == 'failed'
    assert nightcity.LOAD_TIMEOUT >= 300


class PropWindow:
    def __init__(self, props):
        self.props = dict(props)

    def getProperty(self, key):
        return self.props.get(key, '')

    def setProperty(self, key, value):
        self.props[key] = value

    def clearProperty(self, key):
        self.props.pop(key, None)


def test_follower_steps_aside_for_a_newer_playback(monkeypatch):
    """Every play from an info page starts a follower. An older one still following (another
    episode started meanwhile) stops as soon as a newer one took over (nc.follow): followers
    piled up, opened the info page twice at the stop and crashed Kodi (SQL "bad parameter or
    other API misuse", several interpreters at once)."""
    fake = FakeXbmc({'Player.HasMedia', 'Player.HasVideo', 'VideoPlayer.Content(episodes)'}, {})
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    monkeypatch.setattr(nightcity, '_wait', lambda condition, timeout=5.0: True)
    opened = []
    monkeypatch.setattr(nightcity, '_episode_info', opened.append)
    logs = []
    monkeypatch.setattr(nightcity, '_log', logs.append)
    window = PropWindow({'nc.follow': 'newer', 'nc.returning': '1'})
    ticks = []

    class Monitor:
        def waitForAbort(self, timeout):
            ticks.append(timeout)
            return len(ticks) > 50
    result = nightcity._follow(5, Monitor(), type('P', (), {'stopped': False})(), window, token='older')
    assert result is None
    assert len(ticks) == 1
    assert opened == []
    assert window.props['nc.returning'] == '1'  # the newer follower's
    assert any('newer playback' in line for line in logs)


def test_return_to_episode_claims_the_follow(monkeypatch):
    """The newest follower writes its token to nc.follow before it follows."""
    fake = FakeXbmc(set(), {})

    class Player:
        def __init__(self):
            pass
    fake.Player = Player
    fake.Monitor = type('Monitor', (), {})
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    window = PropWindow({'nc.follow': 'older'})
    monkeypatch.setattr(nightcity, '_home', lambda: window)
    seen = []
    monkeypatch.setattr(nightcity, '_follow',
                        lambda dbid, monitor, player, home, token=None: seen.append((token, home.props['nc.follow'])))
    nightcity._return_to_episode(5)
    assert seen and seen[0][0] == seen[0][1] != 'older'


def test_follower_steps_aside_after_the_wait_for_dialogs(monkeypatch):
    """A newer playback that starts while the old follower waits for dialogs after its stop
    takes over there too: the old one does not open the info page."""
    window = PropWindow({'nc.follow': 'older'})
    fake = FakeXbmc({'Window.IsActive(home) | Window.IsActive(videos)'}, {})
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)

    def wait(condition, timeout=5.0):
        if 'HasActiveModalDialog' in condition:
            window.props['nc.follow'] = 'newer'
        return True
    monkeypatch.setattr(nightcity, '_wait', wait)
    opened = []
    monkeypatch.setattr(nightcity, '_episode_info', opened.append)
    monkeypatch.setattr(nightcity, '_log', lambda message: None)

    class Done:
        last = 5

        def tick(self, *args):
            return 'done'
    monkeypatch.setattr(nightcity, 'EpisodeFollower', lambda dbid: Done())

    class Monitor:
        def waitForAbort(self, timeout):
            return False
    assert nightcity._follow(5, Monitor(), type('P', (), {'stopped': True})(), window, token='older') is None
    assert opened == []


class PropWindow:
    def __init__(self, props=None):
        self.props = dict(props or {})

    def setProperty(self, key, value):
        self.props[key] = value

    def getProperty(self, key):
        return self.props.get(key, '')

    def clearProperty(self, key):
        self.props.pop(key, None)


ITEM = '7c2aa04a180f4a1528fb14b1e6632830'


def test_chapter_source_reads_jellyfin_streams():
    """JellyCon and Jellyfin for Kodi (add-on mode) play /Videos/<id>/stream or master.m3u8
    from the server; the server address may have a path."""
    assert nightcity.chapter_source(
        'http://jellyfin:8096/Videos/{}/stream?static=True&MediaSourceId=x'.format(ITEM)) == ('http://jellyfin:8096', ITEM)
    assert nightcity.chapter_source(
        'https://host.example/jf/Videos/{}/master.m3u8?a=1'.format(ITEM)) == ('https://host.example/jf', ITEM)
    assert nightcity.chapter_source('smb://nas/movies/{}.mkv'.format(ITEM)) is None
    assert nightcity.chapter_source('http://other.example/video.mp4') is None
    assert nightcity.chapter_source('') is None


def test_chapter_thumbs_count_from_zero():
    """Kodi numbers chapters from 1, the server's chapter images from 0."""
    assert nightcity.chapter_thumbs(('http://s', 'abc'), 2) == [
        'http://s/Items/abc/Images/Chapter/0', 'http://s/Items/abc/Images/Chapter/1']


def test_server_chapter_images_for_a_jellyfin_stream():
    home = PropWindow()
    asked = []
    url = 'http://jellyfin:8096/Videos/{}/stream?static=True'.format(ITEM)
    nightcity.set_chapter_thumbs(home, url, 3, lambda u: asked.append(u) or True)
    assert asked == ['http://jellyfin:8096/Items/{}/Images/Chapter/0'.format(ITEM)]  # one request
    assert home.props == {
        'nc.chapters.remote': '1',
        'nc.chapter.1': 'http://jellyfin:8096/Items/{}/Images/Chapter/0'.format(ITEM),
        'nc.chapter.2': 'http://jellyfin:8096/Items/{}/Images/Chapter/1'.format(ITEM),
        'nc.chapter.3': 'http://jellyfin:8096/Items/{}/Images/Chapter/2'.format(ITEM)}


def test_a_stream_without_server_images_gets_compact_chapters():
    """Kodi cuts no chapter thumbnails from http streams: without server images the row shows
    compact cards (nc.chapters.remote, no nc.chapter.N)."""
    home = PropWindow({'nc.chapter.1': 'old', 'nc.chapter.5': 'old'})
    nightcity.set_chapter_thumbs(home, 'http://jellyfin:8096/Videos/{}/stream'.format(ITEM), 3, lambda u: False)
    assert home.props == {'nc.chapters.remote': '1'}
    home = PropWindow()
    nightcity.set_chapter_thumbs(home, 'https://cdn.example/clip.mp4', 3, lambda u: True)
    assert home.props == {'nc.chapters.remote': '1'}


def test_local_files_keep_kodis_chapter_thumbnails():
    home = PropWindow({'nc.chapters.remote': '1', 'nc.chapter.2': 'old'})
    nightcity.set_chapter_thumbs(home, 'smb://nas/movies/a.mkv', 3, lambda u: True)
    nightcity.set_chapter_thumbs(home, '/storage/a.mkv', 3, lambda u: True)
    assert home.props == {}


def test_server_chapter_images_stop_at_the_skins_limit():
    home = PropWindow()
    nightcity.set_chapter_thumbs(home, 'http://s/Videos/{}/stream'.format(ITEM), 80, lambda u: True)
    assert sorted(k for k in home.props if k.startswith('nc.chapter.')) == sorted(
        'nc.chapter.{}'.format(n) for n in range(1, nightcity.CHAPTER_THUMBS + 1))


class PlayingXbmc(FakeXbmc):
    """FakeXbmc with a player that plays `playing['file']` (nothing: getPlayingFile raises)."""

    def __init__(self, playing, labels):
        super().__init__(set(), labels)
        outer = playing

        class Player:
            def getPlayingFile(self):
                if not outer.get('file'):
                    raise RuntimeError('Kodi is not playing any file')
                return outer['file']
        self.Player = Player


def test_chapter_images_once_per_stream(monkeypatch):
    """The OSD opens many times during one film: the server is asked once per stream."""
    url = 'http://jellyfin:8096/Videos/{}/stream?PlaySessionId=1'.format(ITEM)
    playing = {'file': url}
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', PlayingXbmc(playing, {'Player.ChapterCount': '03'}))
    asked = []
    monkeypatch.setattr(nightcity, '_image_exists', lambda u: asked.append(u) or True)
    home = PropWindow()
    nightcity.chapter_images(home)
    nightcity.chapter_images(home)
    assert len(asked) == 1
    assert home.props['nc.chapter.3'].endswith('/Images/Chapter/2')
    playing['file'] = url.replace('=1', '=2')  # played again: a new session
    nightcity.chapter_images(home)
    assert len(asked) == 2
    playing['file'] = ''  # playback ended
    nightcity.chapter_images(home)
    assert len(asked) == 2


# --- the skin service: one interpreter for all of the skin's commands -------------------------

def test_skin_message_is_a_command_with_args():
    """NotifyAll(nightcity,play:movie:12:resume) arrives as method Other.play:movie:12:resume."""
    assert nightcity.parse_message('nightcity', 'Other.play:movie:12:resume') == ('play', ['movie', '12', 'resume'])
    assert nightcity.parse_message('nightcity', 'Other.home') == ('home', [])
    assert nightcity.parse_message('nightcity', 'Other.play:movie::resume') == ('play', ['movie', '', 'resume'])


def test_other_messages_are_no_commands():
    assert nightcity.parse_message('xbmc', 'Other.home') is None
    assert nightcity.parse_message('nightcity', 'Player.OnPlay') is None
    assert nightcity.parse_message('nightcity', 'Other.nosuchcommand') is None
    assert nightcity.parse_message('nightcity', 'Other.service') is None  # one service only


class ServiceMonitor:
    """xbmc.Monitor of a Kodi that sends MESSAGES and then aborts."""
    messages = []

    def __init__(self):
        self.waits = 0

    def waitForAbort(self, timeout):
        if self.waits < len(self.messages):
            self.onNotification(*self.messages[self.waits], "null")
        self.waits += 1
        return self.waits > len(self.messages)

    def abortRequested(self):
        return False


def _service_env(monkeypatch, messages, skin='skin.nightcity'):
    import types
    ServiceMonitor.messages = messages
    xbmc = types.SimpleNamespace(Monitor=ServiceMonitor, getSkinDir=lambda: skin, log=lambda *a: None,
                                 LOGERROR=4)
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', xbmc)
    monkeypatch.setattr(nightcity, 'QUIT', __import__('threading').Event())
    window = FakeWindow()
    window.getProperty = lambda key: window.props.get(key, '')
    window.clearProperty = lambda key: window.props.pop(key, None)
    monkeypatch.setattr(nightcity, '_home', lambda: window)
    ran = []
    monkeypatch.setitem(nightcity.COMMANDS, 'home', lambda *a: ran.append(('home',) + a))
    monkeypatch.setitem(nightcity.COMMANDS, 'play', lambda *a: ran.append(('play',) + a))
    monkeypatch.setitem(nightcity.COMMANDS, 'startup', lambda *a: ran.append(('startup',) + a))
    return window, ran


def test_service_runs_the_skins_commands(monkeypatch):
    window, ran = _service_env(monkeypatch, [('nightcity', 'Other.home'),
                                             ('nightcity', 'Other.play:movie:12:resume')])
    seen = []
    monkeypatch.setitem(nightcity.COMMANDS, 'home', lambda *a: seen.append(window.props.get('nc.service')))
    nightcity.service()
    nightcity.wait_for_commands()
    assert seen == ['1']  # the skin sees the service while it runs
    assert ran == [('play', 'movie', '12', 'resume')]
    assert window.props['nc.service'] == '1'  # Kodi ends: no window calls any more


def test_service_runs_its_first_command_before_it_listens(monkeypatch):
    """The Startup screen starts the service with startup, which sets nc.startup.ready."""
    _, ran = _service_env(monkeypatch, [('nightcity', 'Other.home')])
    nightcity.service('startup')
    nightcity.wait_for_commands()
    assert ran == [('startup',), ('home',)]


def test_service_survives_a_failing_command(monkeypatch):
    _, ran = _service_env(monkeypatch, [('nightcity', 'Other.play:x'), ('nightcity', 'Other.home')])
    monkeypatch.setitem(nightcity.COMMANDS, 'play', lambda *a: 1 / 0)
    nightcity.service()
    nightcity.wait_for_commands()
    assert ran == [('home',)]


def test_service_ends_when_another_skin_is_active(monkeypatch):
    window, ran = _service_env(monkeypatch, [('nightcity', 'Other.home')] * 3, skin='skin.estuary')
    nightcity.service()
    nightcity.wait_for_commands()
    assert ran == [('home',)]  # the first wait already sees the other skin
    assert 'nc.service' not in window.props


def test_a_second_service_runs_its_command_and_leaves(monkeypatch):
    """Only one service listens: every one more would run each command once more (three
    keyboards at once closed each other)."""
    window, ran = _service_env(monkeypatch, [('nightcity', 'Other.play:movie:1:resume')])
    window.props['nc.service'] = '1'
    nightcity.service('home')
    nightcity.wait_for_commands()
    assert ran == [('home',)]
    assert window.props['nc.service'] == '1'  # the first one still runs


def test_service_leaves_the_gui_alone_when_kodi_ends(monkeypatch):
    """Kodi ending holds the GUI and waits for the scripts: a window call then blocks until Kodi
    kills the script after 5 s. Only a skin switch clears nc.service."""
    window, _ = _service_env(monkeypatch, [])
    window.clearProperty = lambda key: (_ for _ in ()).throw(AssertionError('GUI touched on abort'))
    nightcity.service()
    assert window.props['nc.service'] == '1'


def test_service_ends_when_kodi_quits(monkeypatch):
    """Kodi sends no abort to a script started by its path and kills it after 5 s on quit:
    the service ends on System.OnQuit instead."""
    _, ran = _service_env(monkeypatch, [('xbmc', 'System.OnQuit')] + [('nightcity', 'Other.home')] * 3)
    nightcity.service()
    nightcity.wait_for_commands()
    assert ran == []
    assert nightcity.QUIT.is_set()


def test_waits_end_when_kodi_quits(monkeypatch):
    """The command threads wait with their own monitors: Kodi waits for each of them on quit."""
    import threading
    import time
    import types

    class NoAbort:
        def waitForAbort(self, timeout=None):
            time.sleep(0.001)
            return False

        def abortRequested(self):
            return False

    xbmc = types.SimpleNamespace(Monitor=NoAbort, getCondVisibility=lambda c: False)
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', xbmc)
    monkeypatch.setattr(nightcity, 'QUIT', threading.Event())
    nightcity.QUIT.set()
    start = time.monotonic()
    assert nightcity._wait('Window.IsActive(home)', timeout=600) is False
    assert time.monotonic() - start < 1


def _search_env(monkeypatch, tmp_path, forget=False, history=('old',)):
    fake = FakeXbmc({'Skin.HasSetting(nc.search.forget)'} if forget else set(), {})
    monkeypatch.setitem(__import__('sys').modules, 'xbmc', fake)
    window = FakeWindow()
    window.getProperty = lambda key: window.props.get(key, '')
    monkeypatch.setattr(nightcity, '_home', lambda: window)
    path = tmp_path / 'search.json'
    if history is not None:
        path.write_text(json.dumps(list(history)))
    monkeypatch.setattr(nightcity, '_search_file', lambda: str(path))
    monkeypatch.setattr(nightcity, '_show_search', lambda home, term, h, stagger=False: shown.append((term, h)))
    shown = []
    return window, path, shown


def test_search_remembers_the_term(monkeypatch, tmp_path):
    _, path, shown = _search_env(monkeypatch, tmp_path)
    nightcity.search('matrix')
    assert json.loads(path.read_text()) == ['matrix', 'old']
    assert shown == [('matrix', ['matrix', 'old'])]


def test_search_keeps_no_terms_when_switched_off(monkeypatch, tmp_path):
    _, path, shown = _search_env(monkeypatch, tmp_path, forget=True, history=None)
    nightcity.search('matrix')
    assert not path.exists()
    assert shown == [('matrix', [])]


def test_search_clear_forgets_the_terms(monkeypatch, tmp_path):
    window, path, _ = _search_env(monkeypatch, tmp_path)
    window.props.update({'nc.search.recent.1': 'old', 'nc.search.recent.2': 'older'})
    nightcity.search_clear()
    assert not path.exists()
    assert all(not window.props.get('nc.search.recent.{}'.format(n)) for n in range(1, nightcity.RECENT + 1))


def test_switching_off_clears_the_terms(monkeypatch, tmp_path):
    _, path, _ = _search_env(monkeypatch, tmp_path, forget=True)
    nightcity.search_forget()
    assert not path.exists()


def test_switching_on_keeps_the_file_alone(monkeypatch, tmp_path):
    _, path, _ = _search_env(monkeypatch, tmp_path)
    nightcity.search_forget()
    assert path.exists()


def test_colour_choices_follow_the_colors_folder():
    """Kodi's lookandfeel.skincolors: SKINDEFAULT for defaults.xml, else the file name."""
    values, labels, current = nightcity.colour_choices(
        ['tokyonight.xml', 'defaults.xml', 'catppuccin.xml', 'notes.txt'], 'tokyonight')
    assert values == ['SKINDEFAULT', 'catppuccin', 'tokyonight']
    assert labels == ['Default', 'Catppuccin', 'Tokyonight']
    assert current == 2


def test_colour_choices_unknown_current_marks_the_default():
    assert nightcity.colour_choices(['defaults.xml'], 'gone')[2] == 0
