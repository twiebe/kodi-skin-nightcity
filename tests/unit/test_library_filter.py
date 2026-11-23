"""The filter of the library grid (scripts/nightcity.py lib_filter): which groups a library has, the
smart playlist rules a choice makes and the line the header shows. The rules are the ones Kodi's
SmartPlayList.cpp knows; the e2e test runs them against a real library."""
import importlib.util
import json
import pathlib
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
nightcity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightcity)

HDR = ['hdr10', 'hdr10plus', 'dolbyvision', 'hlg']


def _xsp(path):
    base, _, query = path.partition('?')
    assert query.startswith('xsp=')
    return base, json.loads(urllib.parse.unquote(query[len('xsp='):]))


def test_movies_have_every_group_shows_genre_and_studio():
    """Kodi keeps stream details per file: a show has none, and a stream rule on tvshows is an SQL
    error (tvshow_view has no idFile). The watched state comes first, then the genre: the most
    asked for."""
    assert nightcity.lib_filter_groups('movies') == ['watched', 'genre', 'res', 'hdr', 'audio', 'channels', 'studio']
    assert nightcity.lib_filter_groups('tvshows') == ['watched', 'genre', 'studio']


def test_nothing_chosen_is_the_plain_library():
    assert nightcity.lib_filter_path('movies', {}) == ''
    assert nightcity.lib_filter_path('movies', {'res': [], 'studio': []}) == ''
    assert nightcity.lib_filter_label('movies', {}) == ''


def test_one_group_is_one_rule_its_values_or():
    base, xsp = _xsp(nightcity.lib_filter_path('movies', {'res': ['2160', '1080']}))
    assert base == 'videodb://movies/titles/'
    assert xsp == {'type': 'movies', 'rules': {'and': [
        {'field': 'videoresolution', 'operator': 'is', 'value': ['2160', '1080']}]}}


def test_groups_and():
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'res': ['2160'], 'audio': ['truehd'], 'channels': ['8']}))
    assert xsp['rules']['and'] == [
        {'field': 'videoresolution', 'operator': 'is', 'value': ['2160']},
        {'field': 'audiocodec', 'operator': 'is', 'value': ['truehd']},
        {'field': 'audiochannels', 'operator': 'is', 'value': ['8']}]


def test_hdr_is_the_umbrella_of_every_hdr_type():
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'hdr': ['hdr']}))
    assert xsp['rules']['and'] == [{'field': 'hdrtype', 'operator': 'is', 'value': HDR}]
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'hdr': ['dolbyvision', 'hdr']}))
    assert xsp['rules']['and'] == [{'field': 'hdrtype', 'operator': 'is', 'value': HDR}]


def test_sdr_is_no_hdr_type():
    """Kodi drops an empty value, so SDR cannot be hdrtype is "": it is none of the HDR types."""
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'hdr': ['sdr']}))
    assert xsp['rules']['and'] == [{'field': 'hdrtype', 'operator': 'isnot', 'value': HDR}]


def test_sdr_and_an_hdr_type_or():
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'hdr': ['sdr', 'hdr10']}))
    assert xsp['rules']['and'] == [{'or': [
        {'field': 'hdrtype', 'operator': 'isnot', 'value': HDR},
        {'field': 'hdrtype', 'operator': 'is', 'value': ['hdr10']}]}]


def test_an_audio_format_names_every_codec_kodi_files_it_under():
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'audio': ['dtshd', 'dts']}))
    assert xsp['rules']['and'] == [
        {'field': 'audiocodec', 'operator': 'is', 'value': ['dtshd_ma', 'dtshd_hra', 'dca', 'dts']}]


def test_the_audio_names_match_the_info_page():
    """ItemAudioCodec in Variables.xml names the codecs; the filter offers the same names."""
    variables = (ROOT / '1080i' / 'Variables.xml').read_text(encoding='utf-8')
    for _, label, values in nightcity.LIB_FILTER_OPTIONS['audio']:
        if label == 'PCM':
            assert 'String.StartsWith(ListItem.AudioCodec,pcm)">PCM<' in variables
            assert all(v.startswith('pcm') for v in values)
        else:  # DTS-HD stands for DTS-HD MA and DTS-HD HRA
            assert 'String.IsEqual(ListItem.AudioCodec,{})">{}'.format(values[0], label) in variables, label


def test_studios_for_movies_and_shows():
    base, xsp = _xsp(nightcity.lib_filter_path('tvshows', {'studio': ['AMC', 'HBO']}))
    assert base == 'videodb://tvshows/titles/'
    assert xsp == {'type': 'tvshows', 'rules': {'and': [{'field': 'studio', 'operator': 'is', 'value': ['AMC', 'HBO']}]}}


def test_a_shows_filter_has_no_stream_rules():
    """A stale choice of the movies' groups never reaches the shows."""
    assert nightcity.lib_filter_path('tvshows', {'res': ['2160']}) == ''


def test_the_path_is_one_label_kodi_can_read():
    path = nightcity.lib_filter_path('movies', {'studio': ['Warner Bros., Inc', 'A&B "C"']})
    assert ',' not in path and '"' not in path and ' ' not in path and '&' not in path.partition('?')[2]
    _, xsp = _xsp(path)
    assert xsp['rules']['and'][0]['value'] == ['Warner Bros., Inc', 'A&B "C"']


def test_the_label_names_the_choice_in_the_order_of_the_dialog():
    label = nightcity.lib_filter_label('movies', {'studio': ['HBO'], 'hdr': ['dolbyvision', 'sdr'], 'res': ['1080', '2160']})
    assert label == '4K, 1080p  ·  SDR, Dolby Vision  ·  HBO'


def test_the_option_order_is_kept_for_studios_as_chosen():
    assert nightcity.lib_filter_label('tvshows', {'studio': ['Zeta', 'AMC']}) == 'Zeta, AMC'


def test_unknown_keys_are_left_out():
    assert nightcity.lib_filter_path('movies', {'res': ['999'], 'nonsense': ['x']}) == ''
    assert nightcity.lib_filter_label('movies', {'res': ['999']}) == ''


def test_the_choice_survives_its_property():
    choice = {'res': ['2160'], 'studio': ['HBO']}
    assert nightcity.lib_filter_load(nightcity.lib_filter_dump(choice)) == choice
    assert nightcity.lib_filter_load('') == {}
    assert nightcity.lib_filter_load('not json') == {}
    assert nightcity.lib_filter_load('[1]') == {}


def test_no_dashes_in_the_labels():
    for options in nightcity.LIB_FILTER_OPTIONS.values():
        for _, label, _ in options:
            assert isinstance(label, int) or ('\u2013' not in label and '\u2014' not in label)


# --- the watched state ----------------------------------------------------------------------------

def _localized(monkeypatch):
    import sys
    import types
    monkeypatch.setitem(sys.modules, 'xbmc', types.SimpleNamespace(getLocalizedString=lambda n: 's{}'.format(n)))


def test_the_watched_state_is_kodis_play_count_and_resume_point():
    """Kodi's own rules (SmartPlayList.cpp): a play count of 0 is unwatched (Kodi counts a NULL as
    0), a resume point in progress; inprogress is a boolean field, its operator takes no value.
    The path needs no Kodi: the e2e tests build it outside."""
    for library in ('movies', 'tvshows'):
        expected = {'unwatched': {'field': 'playcount', 'operator': 'is', 'value': ['0']},
                    'inprogress': {'field': 'inprogress', 'operator': 'true'},
                    'watched': {'field': 'playcount', 'operator': 'greaterthan', 'value': ['0']}}
        for key, rule in expected.items():
            base, xsp = _xsp(nightcity.lib_filter_path(library, {'watched': [key]}))
            assert base == 'videodb://{}/titles/'.format(library)
            assert xsp == {'type': library, 'rules': {'and': [rule]}}


def test_two_watched_states_or():
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'watched': ['unwatched', 'inprogress']}))
    assert xsp['rules']['and'] == [{'or': [
        {'field': 'playcount', 'operator': 'is', 'value': ['0']},
        {'field': 'inprogress', 'operator': 'true'}]}]


def test_watched_and_unwatched_is_every_title(monkeypatch):
    """Every title is one of the two: no rule, no word in the header, the group says all."""
    _localized(monkeypatch)
    for keys in (['unwatched', 'watched'], ['unwatched', 'inprogress', 'watched']):
        assert nightcity.lib_filter_path('movies', {'watched': keys}) == ''
        assert nightcity.lib_filter_label('movies', {'watched': keys}) == ''
    _, xsp = _xsp(nightcity.lib_filter_path('movies', {'watched': ['unwatched', 'watched'], 'res': ['2160']}))
    assert xsp['rules']['and'] == [{'field': 'videoresolution', 'operator': 'is', 'value': ['2160']}]


def test_the_watched_state_ands_with_the_other_groups_and_names_itself_first(monkeypatch):
    _localized(monkeypatch)
    choice = {'genre': ['Drama'], 'watched': ['unwatched']}
    _, xsp = _xsp(nightcity.lib_filter_path('tvshows', choice))
    assert xsp['rules']['and'] == [{'field': 'playcount', 'operator': 'is', 'value': ['0']},
                                   {'field': 'genre', 'operator': 'is', 'value': ['Drama']}]
    assert nightcity.lib_filter_label('tvshows', choice) == 'S31104  ·  Drama'


def test_the_watched_labels_are_kodis_and_the_skins_strings():
    """Unwatched and in progress as the rows' options say them, watched Kodi's own; the group's
    name the skin's."""
    assert [label for _, label, _ in nightcity.LIB_FILTER_OPTIONS['watched']] == [31104, 31103, 16102]
    assert nightcity.LIB_FILTER_NAMES['watched'] == 31509
    po = (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    assert 'msgctxt "#31509"\nmsgid "watched state"' in po


# --- the genre ------------------------------------------------------------------------------------

def test_genres_are_one_rule_their_values_or():
    for library in ('movies', 'tvshows'):
        base, xsp = _xsp(nightcity.lib_filter_path(library, {'genre': ['Drama', 'Science Fiction']}))
        assert base == 'videodb://{}/titles/'.format(library)
        assert xsp['rules']['and'] == [{'field': 'genre', 'operator': 'is', 'value': ['Drama', 'Science Fiction']}]


def test_genre_and_studio_and():
    _, xsp = _xsp(nightcity.lib_filter_path('tvshows', {'studio': ['HBO'], 'genre': ['Drama']}))
    assert xsp['rules']['and'] == [{'field': 'genre', 'operator': 'is', 'value': ['Drama']},
                                   {'field': 'studio', 'operator': 'is', 'value': ['HBO']}]


def test_the_label_starts_with_the_genres():
    assert nightcity.lib_filter_label('movies', {'res': ['2160'], 'genre': ['Drama', 'Action']}) == 'Drama, Action  ·  4K'


def test_the_genres_are_the_librarys(monkeypatch):
    calls = []

    def rpc(method, **params):
        calls.append((method, params))
        return {'genres': [{'label': 'drama'}, {'label': 'Action'}, {'label': ''}]}
    monkeypatch.setattr(nightcity, '_rpc', rpc)
    assert nightcity._lib_genres('tvshows') == ['Action', 'drama']
    nightcity._lib_genres('movies')
    assert [p['type'] for _, p in calls] == ['tvshow', 'movie']
    assert {m for m, _ in calls} == {'VideoLibrary.GetGenres'}


# --- the details of a row of the list -------------------------------------------------------------

def test_the_details_each_library_offers_in_the_order_of_the_row():
    assert [k for k, _ in nightcity.LIB_DETAILS['movies']] == ['year', 'runtime', 'rating', 'res', 'hdr', 'audio', 'channels']
    assert [k for k, _ in nightcity.LIB_DETAILS['tvshows']] == ['year', 'rating', 'seasons', 'episodes', 'studio']


def test_by_default_year_and_runtime_of_a_movie_year_and_episodes_of_a_show():
    assert nightcity.lib_details_load('movies', '') == ['runtime', 'res', 'channels']
    assert nightcity.lib_details_load('tvshows', '') == ['year', 'episodes']


def test_the_details_survive_their_skin_string_in_the_rows_order():
    text = nightcity.lib_details_dump('movies', ['audio', 'year', 'res'])
    assert text == 'year.res.audio'
    assert nightcity.lib_details_load('movies', text) == ['year', 'res', 'audio']


def test_the_skin_string_has_no_comma():
    """Skin.SetString ends its value at a comma."""
    keys = [k for k, _ in nightcity.LIB_DETAILS['movies']]
    assert ',' not in nightcity.lib_details_dump('movies', keys)


def test_no_details_is_not_the_default():
    assert nightcity.lib_details_dump('movies', []) == 'none'
    assert nightcity.lib_details_load('movies', 'none') == []


def test_a_detail_of_the_other_library_is_left_out():
    assert nightcity.lib_details_load('tvshows', 'year.runtime.seasons.bogus') == ['year', 'seasons']
    assert nightcity.lib_details_dump('tvshows', ['runtime', 'studio']) == 'studio'


def test_no_key_is_part_of_another():
    """The skin tells a detail by String.Contains on the skin string."""
    keys = {k for details in nightcity.LIB_DETAILS.values() for k, _ in details} | {'none'}
    assert not [(a, b) for a in keys for b in keys if a != b and a in b]


def test_the_details_label_names_the_choice():
    names = {31119: 'year', 31600: 'runtime', 31121: 'rating', 31607: 'none'}
    assert nightcity.lib_details_label('movies', ['year', 'runtime'], names.get) == 'year, runtime'
    assert nightcity.lib_details_label('movies', [], names.get) == 'none'


# --- the genre filter of the music library --------------------------------------------------------

def test_the_music_filter_keeps_to_the_lists_of_albums_artists_and_songs():
    for node in ('albums', 'artists', 'songs'):
        assert nightcity.music_filter_parse('musicdb://{}/'.format(node)) == (node, [], [])
    for path in ('musicdb://albums/1/', 'musicdb://genres/', 'musicdb://genres/2/', 'musicdb://albums/?artistid=3',
                 'musicdb://recentlyaddedalbums/', 'videodb://movies/titles/', '', 'special://music/'):
        assert nightcity.music_filter_parse(path) is None, path


def test_the_music_filter_is_a_genre_rule_in_the_path():
    path = nightcity.music_filter_path('albums', [], ['Rock', 'Jazz'])
    base, xsp = _xsp(path)
    assert base == 'musicdb://albums/'
    assert xsp == {'type': 'albums', 'rules': {'and': [{'field': 'genre', 'operator': 'is', 'value': ['Rock', 'Jazz']}]}}
    assert nightcity.music_filter_parse(path) == ('albums', [], ['Rock', 'Jazz'])


def test_no_genre_is_the_plain_list():
    assert nightcity.music_filter_path('songs', [], []) == 'musicdb://songs/'


def test_the_music_filter_keeps_the_other_rules_of_a_path():
    """The skin opens an artist's other albums as a smart playlist (Variables.xml MusicInfoMore...)."""
    other = [{'field': 'artist', 'operator': 'is', 'value': ['Chrome Saints']}]
    xsp = json.dumps({'rules': {'and': other + [{'field': 'genre', 'operator': 'is', 'value': ['Rock']}]}, 'type': 'albums'})
    node, rules, genres = nightcity.music_filter_parse('musicdb://albums/?xsp=' + urllib.parse.quote(xsp))
    assert (node, rules, genres) == ('albums', other, ['Rock'])
    _, back = _xsp(nightcity.music_filter_path(node, rules, ['Jazz']))
    assert back['rules']['and'] == other + [{'field': 'genre', 'operator': 'is', 'value': ['Jazz']}]
    _, plain = _xsp(nightcity.music_filter_path(node, rules, []))
    assert plain['rules']['and'] == other


def test_a_path_the_filter_cannot_read_is_not_filtered():
    assert nightcity.music_filter_parse('musicdb://albums/?xsp=not%20json') is None
    xsp = json.dumps({'rules': {'or': [{'field': 'genre', 'operator': 'is', 'value': ['Rock']}]}, 'type': 'albums'})
    assert nightcity.music_filter_parse('musicdb://albums/?xsp=' + urllib.parse.quote(xsp)) is None


def test_a_details_change_redraws_every_row(monkeypatch):
    """Kodi keeps the rows a list drew until a condition of their layout changes: after the details
    change the layouts let go once (nc.lib.layout off and on), so every row shows them at once,
    not only after the cursor moved."""
    import sys
    import types
    calls, props = [], {'nc.library': 'movies', 'nc.lib.layout': '1'}
    xbmc = types.SimpleNamespace(getInfoLabel=lambda key: '', executebuiltin=calls.append,
                                 getLocalizedString=lambda n: str(n),
                                 getCondVisibility=lambda c: c == 'Window.IsActive(1110)')
    xbmcgui = types.SimpleNamespace(Dialog=lambda: types.SimpleNamespace(multiselect=lambda *a, **k: [0, 2]))

    class Home:
        def getProperty(self, key):
            return props.get(key, '')

        def setProperty(self, key, value):
            calls.append(('set', key, value))
            props[key] = value

        def clearProperty(self, key):
            calls.append(('clear', key))
            props.pop(key, None)
    monkeypatch.setitem(sys.modules, 'xbmc', xbmc)
    monkeypatch.setitem(sys.modules, 'xbmcgui', xbmcgui)
    monkeypatch.setattr(nightcity, '_home', lambda: Home())
    monkeypatch.setattr(nightcity, '_monitor', lambda: types.SimpleNamespace(waitForAbort=lambda s: False))
    nightcity.lib_details()
    written = next(i for i, c in enumerate(calls) if isinstance(c, str) and c.startswith('Skin.SetString(nc.libdetails.movies'))
    assert ('clear', 'nc.lib.layout') in calls[written:]
    assert calls.index(('set', 'nc.lib.layout', '1')) > calls.index(('clear', 'nc.lib.layout'))
    assert props['nc.lib.layout'] == '1'
    assert props['nc.libdetails.label.movies'] == '31119, 31121'


def _kodi(monkeypatch, props, conditions, skin=None):
    """nightcity against a fake Kodi: Home's PROPS, the CONDITIONS that hold, skin strings SKIN."""
    import sys
    import types
    xbmc = types.SimpleNamespace(getCondVisibility=lambda c: c in conditions,
                                 getInfoLabel=lambda key: (skin or {}).get(key, ''),
                                 getLocalizedString=lambda n: str(n))

    class Home:
        def getProperty(self, key):
            return props.get(key, '')

        def setProperty(self, key, value):
            props[key] = value
    monkeypatch.setitem(sys.modules, 'xbmc', xbmc)
    monkeypatch.setattr(nightcity, '_home', lambda: Home())


def test_the_library_window_shows_the_details_of_its_library(monkeypatch):
    _kodi(monkeypatch, {'nc.library': 'tvshows'}, {'Window.IsActive(1110)', 'Container.Content(movies)'})
    assert nightcity._lib_library() == 'tvshows'


def test_a_plugin_list_shows_the_details_of_its_content(monkeypatch):
    """JellyCon's lists in the video window: shows by the shows' choice, anything else by the movies'."""
    _kodi(monkeypatch, {'nc.library': 'movies'}, {'Container.Content(tvshows)'})
    assert nightcity._lib_library() == 'tvshows'
    _kodi(monkeypatch, {'nc.library': 'tvshows'}, {'Container.Content(movies)'})
    assert nightcity._lib_library() == 'movies'


def test_the_details_button_names_the_choice_of_each_library(monkeypatch):
    """A plugin's list loads after its window: the button picks its library's name by the content."""
    props = {}
    _kodi(monkeypatch, props, {'Window.IsActive(1110)'}, {'Skin.String(nc.libdetails.tvshows)': 'rating'})
    nightcity._lib_details_name()
    assert props['nc.libdetails.label.movies'] == '31600, 31504, 31507'
    assert props['nc.libdetails.label.tvshows'] == '31121'


def _filter_dialog(monkeypatch, props, answers):
    """lib_filter against a fake Kodi: ANSWERS are what each select returns, a callable gets the
    properties first (the Clear button sets one and closes the dialog). Returns what each select
    saw: its items' labels and whether Clear was shown."""
    import sys
    import types
    seen = []

    class Item:
        def __init__(self, label):
            self.label = label

        def setLabel2(self, label):
            pass

    def select(heading, items, **kwargs):
        assert props.get('nc.select.groups') == '1'  # the key hint of a group names the groups
        seen.append(([i.label for i in items], props.get('nc.select.clear', '')))
        answer = answers.pop(0)
        return answer(props) if callable(answer) else answer

    class Home:
        def getProperty(self, key):
            return props.get(key, '')

        def setProperty(self, key, value):
            props[key] = value

        def clearProperty(self, key):
            props.pop(key, None)
    xbmc = types.SimpleNamespace(getLocalizedString=lambda n: str(n), executebuiltin=lambda c: None,
                                 getInfoLabel=lambda key: '')
    xbmcgui = types.SimpleNamespace(ListItem=Item, Dialog=lambda: types.SimpleNamespace(select=select))
    monkeypatch.setitem(sys.modules, 'xbmc', xbmc)
    monkeypatch.setitem(sys.modules, 'xbmcgui', xbmcgui)
    monkeypatch.setattr(nightcity, '_home', lambda: Home())
    monkeypatch.setattr(nightcity, '_lib_library', lambda: 'movies')
    monkeypatch.setattr(nightcity, 'run_command', lambda *a: None)
    nightcity.lib_filter()
    return seen


def _clear_button(props):
    props['nc.select.cleared'] = '1'
    return -1  # the button closes the dialog as Back does


def test_the_clear_button_clears_the_filter_and_the_groups_stay(monkeypatch):
    props = {'nc.libfilter.movies': json.dumps({'res': ['2160']})}
    seen = _filter_dialog(monkeypatch, props, [_clear_button, -1])
    assert len(seen) == 2  # the groups again after Clear, Back then closes
    assert seen[0][1] and not seen[1][1]  # Clear only while a filter is set
    assert props['nc.libfilter.movies'] == '{}'
    assert props['nc.libfilter.movies.path'] == ''
    assert not {'nc.select.clear', 'nc.select.cleared', 'nc.select.ok', 'nc.select.groups'} & set(props)


def test_the_groups_have_no_clear_entry_of_their_own(monkeypatch):
    props = {'nc.libfilter.movies': json.dumps({'res': ['2160']})}
    seen = _filter_dialog(monkeypatch, props, [-1])
    assert seen[0][0] == [str(nightcity.LIB_FILTER_NAMES[g]) for g in nightcity.lib_filter_groups('movies')]
    assert props['nc.libfilter.movies'] == json.dumps({'res': ['2160']})  # Back keeps the filter
