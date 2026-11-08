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


def test_movies_have_every_group_shows_only_the_studio():
    """Kodi keeps stream details per file: a show has none, and a stream rule on tvshows is an SQL
    error (tvshow_view has no idFile)."""
    assert nightcity.lib_filter_groups('movies') == ['res', 'hdr', 'audio', 'channels', 'studio']
    assert nightcity.lib_filter_groups('tvshows') == ['studio']


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
            assert '\u2013' not in label and '\u2014' not in label
