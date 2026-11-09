"""The list of all movies and all shows: the sort by runtime, the details a row shows (chosen per
library in a dialog, scripts/nightcity.py lib_details), the genre filter and the keys of the skin's
select dialogs. The rows stay light for the box: what a row shows is decided by conditions that
read skin strings only, Kodi works them out once a frame and not per row."""
import importlib.util
import itertools
import re
import xml.etree.ElementTree as ET

from conftest import ROOT, parse
from navigation import _evaluate

WINDOW = 'Custom_1110_Library.xml'
SHOWS = 'String.IsEqual(Window(Home).Property(nc.library),tvshows)'
SELECT_FLAG = 'Window(Home).Property(nc.select.ok)'


def _nightcity():
    spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _root():
    return parse(ROOT / '1080i' / WINDOW)


def _pill(cid):
    return next(i for i in _root().iter('include') if i.get('content') == 'PillButton'
                and any(p.get('name') == 'id' and p.get('value') == cid for p in i.findall('param')))


def _params(call):
    return {p.get('name'): p.get('value') for p in call.findall('param')}


def _expressions():
    found = {}
    for path in (ROOT / '1080i').glob('Includes*.xml'):
        for e in parse(path).iter('expression'):
            found[e.get('name')] = e.text.strip()
    return found


def _variable(name):
    for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable'):
        if v.get('name') == name:
            return [(value.get('condition'), value.text or '') for value in v.findall('value')]
    raise AssertionError(name)


CONTAINS = re.compile(r'String\.Contains\(Skin\.String\(([^)]+)\),([^)]+)\)')


def holds(condition, skin):
    """A condition of skin strings and Home properties, $EXP and String.Contains of a skin string too."""
    expressions = _expressions()
    while '$EXP[' in condition:
        condition = re.sub(r'\$EXP\[(\w+)\]', lambda m: '[' + expressions[m.group(1)] + ']', condition)
    condition = CONTAINS.sub(lambda m: 'true' if m.group(2) in skin.get(m.group(1), '') else 'false', condition)
    return _evaluate(condition, tuple(sorted(skin.items())))


# --- the sort by runtime ---------------------------------------------------------------------------

def _next_sort(library, sort):
    """What OK on the sort button makes of nc.sort: Kodi checks every condition before it runs one."""
    skin = {'nc.sort': sort, 'Window(Home).Property(nc.library)': library}
    clicks = [(c.get('condition'), c.text) for c in _pill('5101').findall('onclick')]
    done = [text for condition, text in clicks if condition and text.startswith('Skin.SetString(nc.sort,') and holds(condition, skin)]
    assert len(done) == 1, (library, sort, done)
    return done[0][len('Skin.SetString(nc.sort,'):-1]


def test_movies_cycle_through_runtime():
    """time is Kodi's name of the sort by duration (SortUtils.cpp), the runtime of a movie."""
    order, sort = [], ''
    for _ in range(6):
        sort = _next_sort('movies', sort)
        order.append(sort)
    assert order == ['year', 'dateadded', 'rating', 'time', 'sorttitle', 'year']


def test_shows_have_no_runtime_to_sort_by():
    """Kodi keeps no runtime of a show: the shows skip it, and a sort by runtime chosen for the movies
    is the title for them."""
    order, sort = [], ''
    for _ in range(5):
        sort = _next_sort('tvshows', sort)
        order.append(sort)
    assert order == ['year', 'dateadded', 'rating', 'sorttitle', 'year']
    assert _next_sort('tvshows', 'time') == 'year'
    method = _variable('LibrarySortMethod')
    shows = {'nc.sort': 'time', 'Window(Home).Property(nc.library)': 'tvshows'}
    assert next(text for condition, text in method if condition is None or holds(condition, shows)) == 'sorttitle'
    label = _variable('LibrarySortLabel')
    assert next(text for condition, text in label if condition is None or holds(condition, shows)) == '$LOCALIZE[31118]'
    movies = {'nc.sort': 'time'}
    assert next(text for condition, text in method if condition is None or holds(condition, movies)) == '$INFO[Skin.String(nc.sort)]'
    assert next(text for condition, text in label if condition is None or holds(condition, movies)) == '$LOCALIZE[31600]'


def test_the_bar_groups_the_runtime_by_half_hours():
    nc = _nightcity()
    assert nc.BAR_INFO['time'] == ('Duration(mins)', nc.bar_runtime)


# --- the details of a row --------------------------------------------------------------------------

def _details_button():
    return _pill('5105')


def test_the_details_button_opens_the_dialog_in_the_list_only():
    params = _params(_details_button())
    assert params['onclick'] == 'NotifyAll(nightcity,lib_details)'
    assert params['label'] == '$LOCALIZE[31602]: $INFO[Window(Home).Property(nc.libdetails.label)]'
    assert params['visible'] == '$EXP[LibraryAsList]'
    assert params['onfocus'] == 'NotifyAll(nightcity,lib_bar:prepare)'
    assert 'SetProperty(nc.lib.menu,5105,home)' in [f.text for f in _details_button().findall('onfocus')]
    assert 'lib_details' in _nightcity().COMMANDS


ROW_ORDER = ['year', 'runtime', 'rating', 'seasons', 'episodes', 'studio', 'res', 'hdr', 'audio', 'channels']


def _piece(key):
    return 'LibraryRow' + key.capitalize()


def _row():
    base = parse(ROOT / '1080i' / 'Includes_Base.xml')
    return next(i for i in base.iter('include') if i.get('name') == 'LibraryRow')


def _tags():
    """The tags of a row, left to right: (key, group)."""
    return [(g.findtext('description'), g) for g in _row().iter('control')
            if g.get('type') == 'group' and g.findtext('description') in ROW_ORDER]


def test_a_row_shows_its_details_in_a_fixed_order():
    nc = _nightcity()
    tags = _tags()
    assert [k for k, _ in tags] == ROW_ORDER
    for key, group in tags:
        labels = [c.findtext('label') for c in group.iter('control') if c.get('type') == 'label']
        assert labels == ['$VAR[{}]'.format(_piece(key))], key
        assert group.findtext('visible').startswith('$EXP[LibraryDetail{}] + '.format(key.capitalize())), key
    for library, details in nc.LIB_DETAILS.items():
        keys = [k for k, _ in details]
        assert keys == [k for k in ROW_ORDER if k in keys], library


def test_the_tags_line_up_from_row_to_row():
    """Every tag has a fixed width and ends where the next begins, less a gap, the last at the
    right edge; a tag left out slides each one before it right by its width and the gap, so the
    chosen ones sit flush right whatever the choice."""
    tags = _tags()
    sizes = [(int(g.findtext('left')), int(g.findtext('width'))) for _, g in tags]
    gap = sizes[1][0] - sum(sizes[0])
    assert gap > 0
    for (left, width), (nxt, _) in zip(sizes, sizes[1:]):
        assert left + width + gap == nxt
    right = sum(sizes[-1])
    for i, (key, group) in enumerate(tags):
        slides = {a.get('condition'): a.get('end') for a in group.findall('animation')}
        assert slides == {'!$EXP[LibraryDetail{}]'.format(k.capitalize()): '{},0'.format(w + gap)
                          for (k, _), (_, w) in zip(tags[i + 1:], sizes[i + 1:])}, key
        plate = next(inc for inc in group.iter('include') if inc.get('content') == 'LookTagImage')
        assert {p.get('name'): p.get('value') for p in plate.findall('param')} == {
            'width': str(sizes[i][1]), 'color': '$PARAM[tag]'}, key
        label = next(c for c in group.iter('control') if c.get('type') == 'label')
        assert label.findtext('width') == str(sizes[i][1]) and label.findtext('align') == 'center', key
        assert label.findtext('textcolor') == '$PARAM[tagtext]', key
    assert right == 1300


def test_the_focused_row_turns_its_tags_dark():
    row = [layout for layout in ET.parse(ROOT / '1080i' / 'Custom_1110_Library.xml').getroot().iter('focusedlayout')
           if (layout.get('condition') or '').endswith(' + $EXP[LibraryAsList]')][0]
    inc = next(i for i in row.iter('include') if i.get('content') == 'LibraryRow')
    params = {p.get('name'): p.get('value') for p in inc.findall('param')}
    assert params['tag'] == '$VAR[LibraryRowTag]' and params['tagtext'] == '$VAR[LibraryRowTagText]'
    assert _variable('LibraryRowTag') == [('Control.HasFocus(5000)', 'focus_text'), (None, 'state')]
    assert _variable('LibraryRowTagText') == [('Control.HasFocus(5000)', 'focus'), (None, 'text')]


def test_codec_and_channels_are_tags_of_their_own():
    """DTS-MA and 7.1: the names of the info page, each chosen on its own."""
    assert _variable('LibraryRowAudio') == [('$EXP[LibraryDetailAudio]', '$VAR[ItemAudioCodec]')]
    assert _variable('LibraryRowChannels') == [('$EXP[LibraryDetailChannels]', '$VAR[ItemAudioChannels]')]
    assert ('channels', 31507) in _nightcity().LIB_DETAILS['movies']


def test_each_detail_shows_only_when_chosen():
    """Every value of a piece starts with the detail's expression: nothing of it is worked out per
    row unless the detail is chosen."""
    for key in ROW_ORDER:
        expression = '$EXP[LibraryDetail{}]'.format(key.capitalize())
        values = _variable(_piece(key))
        assert values and all((c or '').startswith(expression) for c, _ in values), key
        assert 'ListItem.' not in _expressions()['LibraryDetail' + key.capitalize()], key


def test_the_details_take_the_formats_of_the_info_page():
    assert _variable('LibraryRowRes') == [('$EXP[LibraryDetailRes]', '$VAR[ItemResolution]')]
    assert _variable('LibraryRowHdr') == [('$EXP[LibraryDetailHdr]', '$VAR[ItemHdr]')]
    assert _variable('LibraryRowRuntime') == [('$EXP[LibraryDetailRuntime]', '$INFO[ListItem.Duration(mins),, min]')]
    assert _variable('LibraryRowRating') == [('$EXP[LibraryDetailRating]', '$INFO[ListItem.Rating,★ ,]')]
    episodes = _variable('LibraryRowEpisodes')
    assert episodes[0][1] == '$INFO[ListItem.Property(WatchedEpisodes)]/$INFO[ListItem.Property(TotalEpisodes)]'
    seasons = dict(_variable('LibraryRowSeasons'))
    assert '1 $LOCALIZE[31604]' in seasons.values()
    assert '$INFO[ListItem.Property(TotalSeasons)] $LOCALIZE[31605]' in seasons.values()


def _chosen(library, value):
    skin = {'Window(Home).Property(nc.library)': library, 'nc.libdetails.' + library: value}
    return [k for k in ROW_ORDER if holds('$EXP[LibraryDetail{}]'.format(k.capitalize()), skin)]


def test_the_skin_reads_the_choice_as_the_script_writes_it():
    """Every choice the dialog can make, and none (the default), shows in the rows as the script
    reads it."""
    nc = _nightcity()
    for library, details in nc.LIB_DETAILS.items():
        keys = [k for k, _ in details]
        assert _chosen(library, '') == nc.lib_details_load(library, ''), library
        for n in range(len(keys) + 1):
            for subset in itertools.combinations(keys, n):
                value = nc.lib_details_dump(library, list(subset))
                assert _chosen(library, value) == nc.lib_details_load(library, value), (library, value)


def test_the_choice_of_the_other_library_does_not_count():
    assert _chosen('tvshows', '') == ['year', 'episodes']
    skin = {'Window(Home).Property(nc.library)': 'tvshows', 'nc.libdetails.movies': 'res,hdr,audio'}
    assert [k for k in ROW_ORDER if holds('$EXP[LibraryDetail{}]'.format(k.capitalize()), skin)] == ['year', 'episodes']


def test_a_row_has_labels_and_tag_plates_but_no_art():
    row = _row()
    labels = [c.findtext('label') for c in row.iter('control') if c.get('type') == 'label']
    assert labels == ['$VAR[LibraryMark]', '$INFO[ListItem.Label]'] + ['$VAR[{}]'.format(_piece(k)) for k in ROW_ORDER]
    assert not [c for c in row.iter('control') if c.get('type') == 'image']
    assert {i.get('content') for i in row.iter('include') if i.get('content')} == {'LookTagImage'}


def test_the_script_marks_the_details_dialog():
    source = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    body = source[source.index('def lib_details():'):]
    body = body[:body.index('\ndef ')]
    assert "setProperty('nc.select.ok', '1')" in body and "clearProperty('nc.select.ok')" in body
    assert 'multiselect' in body and 'Skin.SetString(nc.libdetails.' in body


# --- the select dialog's keys ----------------------------------------------------------------------

def _dialog():
    return parse(ROOT / '1080i' / 'DialogSelect.xml')


def _list(dialog, lid):
    return next(i for i in dialog.iter('include') if i.find("param[@name='id']") is not None
                and i.find("param[@name='id']").get('value') == lid)


def test_right_enters_a_group_of_a_marked_list():
    """The list of groups of the filter (a select, no OK of Kodi's): Right is OK. In a multi-select
    Right stays."""
    dialog = _dialog()
    for lid in ('3', '6'):
        rights = [(m.get('condition'), m.text) for m in _list(dialog, lid).findall('onright')]
        assert ('!String.IsEmpty({}) + !Control.IsVisible(5)'.format(SELECT_FLAG), 'Action(Select)') in rights
        assert [c for c, _ in rights if 'Control.IsVisible(5)' in (c or '') and not c.count('!Control.IsVisible(5)')] == []


def test_up_from_the_buttons_goes_back_to_the_list():
    """Every select dialog: Up from its buttons lands on the list shown, the detailed one (6) or
    the simple one (3)."""
    buttons = next(c for c in _dialog().iter('control') if c.get('id') == '9001')
    ups = [(m.get('condition'), m.text) for m in buttons.findall('onup')]
    assert ups == [('Control.IsVisible(6)', '6'), ('!Control.IsVisible(6)', '3')]


# --- the genre filter ------------------------------------------------------------------------------

def test_the_genre_group_is_named_and_its_genres_come_from_the_library():
    nc = _nightcity()
    assert nc.LIB_FILTER_NAMES['genre'] == 31601 and nc.LIB_FILTER_FIELDS['genre'] == 'genre'
    source = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    body = source[source.index('def _lib_filter_dialogs('):source.index('def _bar_command(')]
    assert '_lib_genres(library)' in body


# --- the genre filter of the music library ---------------------------------------------------------

MUSIC = 'MyMusicNav.xml'


def _music():
    return parse(ROOT / '1080i' / MUSIC)


def _music_filter_button():
    return next(i for i in _music().iter('include') if i.get('content') == 'ListButton'
                and any(p.get('name') == 'id' and p.get('value') == '9061' for p in i.findall('param')))


def test_the_music_menu_ends_with_the_filter():
    menu = next(c for c in _music().iter('control') if c.get('id') == '9060')
    ids = [c.get('id') or _params(c).get('id') for c in menu if c.tag in ('control', 'include')]
    assert ids == ['2', '3', '4', '9061']
    params = _params(_music_filter_button())
    assert params['onclick'] == 'NotifyAll(nightcity,music_filter)'
    assert params['label'] == '$LOCALIZE[31502]: $VAR[MusicFilterLabel]'
    assert params['visible'] == '$EXP[MusicFilterable]'
    assert 'music_filter' in _nightcity().COMMANDS


def test_the_filter_shows_on_the_lists_the_script_filters():
    """The skin's condition and the script's parse agree on the paths."""
    nc = _nightcity()
    condition = _expressions()['MusicFilterable']
    paths = re.findall(r'String\.(IsEqual|StartsWith)\(Container\.FolderPath,([^)]+)\)', condition)
    assert sorted(paths) == sorted([('IsEqual', 'musicdb://{}/'.format(n)) for n in nc.MUSIC_FILTER_NODES]
                                   + [('StartsWith', 'musicdb://{}/?xsp='.format(n)) for n in nc.MUSIC_FILTER_NODES])
    assert re.sub(r'String\.(IsEqual|StartsWith)\(Container\.FolderPath,[^)]+\)', '', condition).replace('|', '').strip() == ''


def test_the_header_and_the_button_name_the_genres_while_their_path_is_shown():
    same = '!String.IsEmpty(Window(Home).Property(nc.musicfilter.path)) + String.IsEqual(Container.FolderPath,Window(Home).Property(nc.musicfilter.path))'
    assert _variable('MusicFilterLabel') == [(same, '$INFO[Window(Home).Property(nc.musicfilter.label)]'),
                                            (None, '$LOCALIZE[31503]')]
    assert _variable('MusicNavTitle') == [(same, '$INFO[Container.FolderName]$INFO[Window(Home).Property(nc.musicfilter.label),  ·  ,]'),
                                         (None, '$INFO[Container.FolderName]')]
    status = next(i for i in _music().iter('include') if i.get('content') == 'StatusBar')
    assert _params(status)['title'] == '$VAR[MusicNavTitle]'


def test_the_music_filter_is_marked_like_the_others():
    source = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    body = source[source.index('def music_filter():'):]
    body = body[:body.index('\ndef ')]
    assert "setProperty('nc.select.ok', '1')" in body and "clearProperty('nc.select.ok')" in body
    assert 'AudioLibrary.GetGenres' in body and 'Container.Update(' in body
