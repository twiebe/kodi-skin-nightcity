"""All movies and all shows as posters or as a list, remembered per library, with a filter by format
and studio (scripts/nightcity.py lib_filter). The grid stays the grid: one panel, two pairs of
layouts, so the bar, the click and the counter work in both."""
import importlib.util
import re

from conftest import ROOT, parse

WINDOW = 'Custom_1110_Library.xml'
READY = '$EXP[LibraryLayoutReady]'
AS_LIST = READY + ' + $EXP[LibraryAsList]'
AS_POSTERS = READY + ' + !$EXP[LibraryAsList]'


def _root():
    return parse(ROOT / '1080i' / WINDOW)


def _controls():
    return {c.get('id'): c for c in _root().iter('control') if c.get('id')}


def _pill(cid):
    return next(i for i in _root().iter('include') if i.get('content') == 'PillButton'
                and any(p.get('name') == 'id' and p.get('value') == cid for p in i.findall('param')))


def _params(call):
    return {p.get('name'): p.get('value') for p in call.findall('param')}


def _nightcity():
    spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _variables():
    return (ROOT / '1080i' / 'Variables.xml').read_text(encoding='utf-8')


def _expression(name):
    for path in (ROOT / '1080i').glob('Includes*.xml'):
        for e in parse(path).iter('expression'):
            if e.get('name') == name:
                return e.text.strip()
    raise AssertionError(name)


def test_the_view_is_remembered_per_library():
    expression = _expression('LibraryAsList')
    assert 'String.IsEqual(Skin.String(nc.libview.movies),list)' in expression
    assert 'String.IsEqual(Skin.String(nc.libview.tvshows),list)' in expression
    assert 'Window(Home).Property(nc.library),tvshows' in expression


def test_every_layout_carries_its_condition():
    """Kodi only notices a change of the condition of the layout it uses (GUIBaseContainer.cpp
    UpdateVisibility), and only then lets go of the layouts its items drew with. The panel keeps
    its items over closing the window and picks its layout on the way back without asking them
    (AllocResources): the rows drew as posters after a view chosen while it was closed. So an
    empty layout comes first until the service says the window is up; its condition changing on
    screen draws every item anew, posters or rows."""
    grid = _controls()['5000']
    for tag in ('itemlayout', 'focusedlayout'):
        layouts = grid.findall(tag)
        assert [layout.get('condition') for layout in layouts] == ['!' + READY, AS_POSTERS, AS_LIST], tag
        waiting, posters, rows = layouts
        assert len(waiting) == 0 and (waiting.get('width'), waiting.get('height')) == ('228', '340')
        assert (posters.get('width'), posters.get('height')) == ('228', '340')
        assert any(i.get('content') == 'CutCard' for i in posters.iter('include'))
        # one row as wide as the panel: the panel makes one column of it
        assert rows.get('width') == grid.findtext('width')
        assert not [c for c in rows.iter('control') if c.get('type') == 'image' and 'Art(' in (c.findtext('texture') or '')]
    assert _expression('LibraryLayoutReady') == '!String.IsEmpty(Window(Home).Property(nc.lib.layout))'
    root = _root()
    assert 'NotifyAll(nightcity,lib_layout)' in [o.text for o in root.findall('onload')]
    assert 'ClearProperty(nc.lib.layout,home)' in [o.text for o in root.findall('onunload')]
    assert 'lib_layout' in _nightcity().COMMANDS


def test_a_row_names_year_runtime_and_format():
    rows = [layout for layout in _controls()['5000'] if layout.get('condition') == AS_LIST]
    base = parse(ROOT / '1080i' / 'Includes_Base.xml')
    row = next(i for i in base.iter('include') if i.get('name') == 'LibraryRow')
    for layout in rows:
        assert [i.get('content') for i in layout.iter('include') if i.get('content')] == ['LibraryRow']
        labels = ' '.join(c.findtext('label') or '' for c in row.iter('control'))
        assert '$INFO[ListItem.Label]' in labels
        assert '$VAR[LibraryRight]' in labels  # year and runtime, watched episodes of a show
        assert '$VAR[LibraryFormat]' in labels
    variable = re.search(r'<variable name="LibraryFormat">(.*?)</variable>', _variables(), re.S).group(1)
    # the formatting of the info page and the heroes, not a new one
    assert '$VAR[ItemResolution]' in variable and '$VAR[ItemHdr,' in variable and '$VAR[ItemAudio,' in variable


def test_the_focused_row_glows_in_both_looks():
    focused = [layout for layout in _controls()['5000'].findall('focusedlayout') if layout.get('condition') == AS_LIST][0]
    assert any(i.text == 'LookListFocus' for i in focused.iter('include'))


def test_the_menu_has_view_and_filter():
    menu = _controls()['5100']
    ids = [_params(i)['id'] for i in menu.iter('include') if i.get('content') == 'PillButton']
    assert ids == ['5101', '5102', '5103', '5104']
    assert _nightcity().BAR_MENU_BUTTONS == (5101, 5102, 5103, 5104)
    for cid in ('5103', '5104'):
        assert _params(_pill(cid))['onfocus'] == 'NotifyAll(nightcity,lib_bar:prepare)'
        assert _params(_pill(cid))['width'] == str(_nightcity().BAR_MENU_WIDE)


def test_the_view_button_is_a_toggle_of_the_shown_library():
    """A toggle: OK, not the focus, flips it (DESIGN.md)."""
    call = _pill('5103')
    clicks = [(e.get('condition'), e.text) for e in call.findall('onclick')]
    texts = ' '.join(t for _, t in clicks)
    assert 'Skin.SetString(nc.libview.movies,list)' in texts and 'Skin.Reset(nc.libview.movies)' in texts
    assert 'Skin.SetString(nc.libview.tvshows,list)' in texts and 'Skin.Reset(nc.libview.tvshows)' in texts
    assert clicks[-1] == (None, 'NotifyAll(nightcity,lib_bar:changed)')
    assert '$LOCALIZE[31500]' in _params(call)['label']


def test_the_filter_button_opens_the_dialog():
    call = _pill('5104')
    assert _params(call)['onclick'] == 'NotifyAll(nightcity,lib_filter)'
    assert '$LOCALIZE[31502]' in _params(call)['label']
    assert 'lib_filter' in _nightcity().COMMANDS


def test_the_filter_makes_the_path_and_the_header():
    variables = _variables()
    path = re.search(r'<variable name="LibraryPath">(.*?)</variable>', variables, re.S).group(1)
    title = re.search(r'<variable name="LibraryTitle">(.*?)</variable>', variables, re.S).group(1)
    for library in ('movies', 'tvshows'):
        assert '$INFO[Window(Home).Property(nc.libfilter.{}.path)]'.format(library) in path
        assert 'Window(Home).Property(nc.libfilter.{}.label)'.format(library) in title


def test_the_title_column_starts_below_the_menu():
    menu = _controls()['5100']
    bottom = int(menu.findtext('top')) + int(menu.findtext('height'))
    assert int(menu.findtext('height')) >= 4 * 74 - 3 * 4
    base = parse(ROOT / '1080i' / 'Includes_Base.xml')
    include = next(i for i in base.iter('include') if i.get('name') == 'LibraryTitle')
    kicker = next(i for i in include.iter('include') if i.get('content') == 'Kicker')
    assert int(_params(kicker)['top']) >= bottom
    tops = [int(c.findtext('top')) + int(c.findtext('height')) for c in include.iter('control') if c.findtext('top')]
    assert max(tops) <= 98 + 900  # the end of the rail


def test_songs_show_format_and_bitrate():
    variables = _variables()
    right = re.search(r'<variable name="MusicNavRight">(.*?)</variable>', variables, re.S).group(1)
    song = next(line for line in right.splitlines() if 'DBType,song' in line)
    assert '$VAR[MusicSongFormat' in song and 'ListItem.Duration' in song
    fmt = re.search(r'<variable name="MusicSongFormat">(.*?)</variable>', variables, re.S).group(1)
    assert 'ListItem.BitRate' in fmt and 'kbit/s' in fmt
    assert 'String.StartsWith(ListItem.FileExtension,flac)">FLAC' in fmt


# --- the bar remembers its button, the filter dialogs have one OK --------------------------------

def test_right_from_the_grid_goes_back_to_the_bars_last_button():
    """Right from the grid lands on the button of the bar that had the focus last (a filter
    changed there), on the first one when the window just opened."""
    window = parse(ROOT / '1080i' / 'Custom_1110_Library.xml')
    grid = next(c for c in window.iter('control') if c.get('id') == '5000')
    rights = [(r.get('condition'), r.text) for r in grid.findall('onright')]
    assert rights == [('!String.IsEmpty(Window(Home).Property(nc.lib.menu))', 'SetFocus($INFO[Window(Home).Property(nc.lib.menu)])'),
                      ('String.IsEmpty(Window(Home).Property(nc.lib.menu))', '5101')]
    for button in ('5101', '5102', '5103', '5104'):
        inc = next(i for i in window.iter('include') if i.find("param[@name='id']") is not None
                   and i.find("param[@name='id']").get('value') == button)
        assert 'SetProperty(nc.lib.menu,{},home)'.format(button) in [f.text for f in inc.findall('onfocus')]
    assert 'ClearProperty(nc.lib.menu,home)' in [o.text for o in window.findall('onload')]


SELECT_FLAG = 'Window(Home).Property(nc.select.ok)'


def test_marked_select_dialogs_have_one_ok_and_left_goes_up():
    """The filter dialogs (nc.select.ok): only OK, no Cancel; Left confirms one level up (a
    multi-select confirms, the list of groups closes), Right stays, Down past the end reaches OK."""
    dialog = parse(ROOT / '1080i' / 'DialogSelect.xml')
    controls = {c.get('id'): c for c in dialog.iter('control') if c.get('id')}
    for lst in ('3', '6'):
        inc = next(i for i in dialog.iter('include') if i.find("param[@name='id']") is not None
                   and i.find("param[@name='id']").get('value') == lst)
        moves = {(m.tag, m.get('condition'), m.text) for m in inc if m.tag in ('onleft', 'onright', 'ondown')}
        assert ('onright', 'String.IsEmpty({})'.format(SELECT_FLAG), '9001') in moves
        assert ('onleft', '!String.IsEmpty({}) + Control.IsVisible(5)'.format(SELECT_FLAG), 'SendClick(12000,5)') in moves
        assert ('onleft', '!String.IsEmpty({}) + !Control.IsVisible(5)'.format(SELECT_FLAG), 'Action(Back)') in moves
        assert ('ondown', '!String.IsEmpty({})'.format(SELECT_FLAG), '9001') in moves
    cancel = next(i for i in dialog.iter('include') if i.find("param[@name='id']") is not None
                  and i.find("param[@name='id']").get('value') == '7')
    assert {p.get('name'): p.get('value') for p in cancel.findall('param')}['visible'] == 'String.IsEmpty({})'.format(SELECT_FLAG)
    ok = next(i for i in dialog.iter('include') if i.find("param[@name='id']") is not None
              and i.find("param[@name='id']").get('value') == '9')
    params = {p.get('name'): p.get('value') for p in ok.findall('param')}
    assert params['visible'] == '!String.IsEmpty({}) + !Control.IsVisible(5)'.format(SELECT_FLAG)
    assert params['onclick'] == 'Action(Back)' and params['label'] == '$LOCALIZE[186]'


def test_the_script_marks_its_filter_dialogs():
    source = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    body = source[source.index('def lib_filter():'):source.index('def _bar_command(')]
    assert "setProperty('nc.select.ok', '1')" in body and "clearProperty('nc.select.ok')" in body
