"""Key hints (DESIGN.md, Key hints): where a key leads to another level and the screen does not
show it, one quiet line names the key, an arrow or OK in the dimmed blue of a hint, and the level it
leads to, muted. Where it stands follows its key: Up at the top (the path line, top 30; the
player's top edge, top 140), Left up the left edge, written bottom to top (LevelHintLeft), Down
and OK in the footer line at the bottom (centred, top 1030), where the keys of the focused row
may stand together.

A hint belongs to its page, not to the focused element: it says where its key leads from the
page's outermost element towards its edge, wherever the focus is, and an edge whose outermost
element does nothing with that key has none. The one exception is the episodes' footer, which
shows the keys of the focused row.

Player levels: the seek bar over the bare video (OK opens the controls; Up and Down skip
chapters there), the controls (Down: the chapter row), a panel above a button (Down: back to
the controls), the chapter row (Down: the cast row, Up: the controls), the cast row (Up: the
chapter row). The info pages leave by Up from their buttons and say so on their path line,
while the buttons have the focus."""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT, layout_files, parse
from navigation import load

BOTTOM, TOP, PATH = '1030', '140', '30'
CAST = 'VideoPlayer.Content(movies) | VideoPlayer.Content(episodes)'
CONTROLS = '$LOCALIZE[31478]'
# OK is the word on the remote's key, as on Kodi's own dialogs; the arrows are glyphs
OK = 'OK'
KEYS = ('↑', '↓', '←', '→', OK, '↑↓', '←→')
GLYPHS = re.compile('[↑↓←→⏎]')
KEY = '[COLOR state_text]{}[/COLOR]'
COLOURED_KEY = re.compile(r'\[COLOR state_text\](?:[↑↓←→]+|OK)\[/COLOR\]')
LABEL = re.compile(r'^\[UPPERCASE\]\[COLOR state_text\](\S+)\[/COLOR\] (.+)\[/UPPERCASE\]$')
# a Left hint: the middle of the screen's left edge, in a dialog too (DESIGN.md: a hint stands at the
# screen's edge of its key, not at the dialog's frame)
LEFT_EDGE = ('-276', '525')
# a Right hint: LevelHintLeft mirrored, the middle of the screen's right edge
RIGHT_EDGE = ('1596', '525')
HINTS = ('LevelHint', 'LevelHintLeft', 'LevelHintRight')
# in a dialog ← and → stand inside its frame, along its inner edges, centred on them: (file, id):
# (left, top) in the dialog's group, the frame's width and height
FRAME_HINTS = {('DialogSelect.xml', '9059'): ('-276', '395', 1156, 820),
               ('DialogSelect.xml', '9058'): ('832', '395', 1156, 820),
               ('DialogAddonSettings.xml', '9058'): ('1332', '455', 1656, 940)}


def _controls(name):
    return {c.get('id'): c for c in load(name).iter('control') if c.get('id')}


def _turned(group):
    return any(a.get('effect') == 'rotate' for a in group.findall('animation'))


def _turn(group):
    return next(a.get('end') for a in group.findall('animation') if a.get('effect') == 'rotate')


def _hint(name, cid):
    """(key, label, top, visible) of the hint `cid` in window `name`; a turned line's ↑ is a ←
    on the screen."""
    group = _controls(name)[cid]
    (line,) = group.findall('control')
    assert line.get('type') == 'label', cid
    key, label = LABEL.match(line.findtext('label')).groups()
    if _turned(group):
        assert key == '↑', (name, cid)
        key = '→' if _turn(group) == '-90' else '←'
    return key, label, group.findtext('top'), group.findtext('visible')


def _actions(control, tag):
    return [(a.get('condition') or '', a.text) for a in control.findall(tag)]


def _string(num, lang='en_gb'):
    text = (ROOT / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
    entry = re.search(r'msgctxt "#{}"\nmsgid "([^"]*)"\nmsgstr "([^"]*)"'.format(num), text)
    return entry.group(1) if lang == 'en_gb' else entry.group(2)


def _variable(name):
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable') if v.get('name') == name)
    return [(v.get('condition'), v.text) for v in var.findall('value')]


def _include(name):
    return next(i for i in parse(ROOT / '1080i' / 'Includes_Base.xml').iter('include') if i.get('name') == name)


def _all_hints():
    """Every key hint of the skin's windows: (file, include, params); a Left hint's key is ←."""
    found = []
    for path in layout_files():
        for inc in parse(path).iter('include'):
            if inc.get('content') in HINTS:
                params = {p.get('name'): p.get('value') for p in inc.findall('param')}
                if inc.get('content') == 'LevelHintLeft':
                    params['key'] = '←'
                if inc.get('content') == 'LevelHintRight':
                    params['key'] = '→'
                found.append((path.name, inc.get('content'), params))
    return found


def test_hint_look():
    """The key in the dimmed blue of a hint, the label muted, one line of small caps; a shadow
    keeps it readable over bright video. By default in the footer line, centred; it
    fades out, then in."""
    include = _include('LevelHint')
    defaults = {p.get('name'): p.get('default') for p in include.findall('param')}
    assert (defaults['top'], defaults['left'], defaults['width'], defaults['align']) == (BOTTOM, '0', '1920', 'center')
    assert defaults['animate'] == 'true'  # the player's hints fade over the video
    group = include.find('definition/control')
    assert group.get('type') == 'group'
    fade = group.find('include')
    assert (fade.get('content'), fade.find('param').get('value')) == ('LevelHintFade', '$PARAM[animate]')
    (label,) = group.findall('control')
    assert label.get('type') == 'label'
    assert (label.findtext('width'), label.findtext('align')) == ('$PARAM[width]', '$PARAM[align]')
    assert label.findtext('include') == 'LevelHintText'
    case = label.find("include[@content='LookLabelCase']/param")
    assert case.get('value') == '{} $PARAM[label]'.format(KEY.format('$PARAM[key]'))
    assert not list(include.iter('texture')) and 'cut_btn' not in ET.tostring(include, encoding='unicode')
    text = _include('LevelHintText')
    assert [(c.tag, c.text) for c in text] == [('aligny', 'center'), ('font', 'font_caps_small'),
                                              ('textcolor', 'text_mute'), ('shadowcolor', 'bg')]


def test_hints_fade_out_then_in():
    """Two hints taking turns in one place never stand on each other: a still effect starts the
    animation at once (test_page_fades), the delayed fade holds 0 until it runs."""
    anims = {a.get('type'): (a.get('condition'), [(e.get('start'), e.get('end'), e.get('time'), e.get('delay'))
                                                  for e in a.findall('effect')])
             for a in _include('LevelHintFade').find('definition').findall('animation')}
    assert anims == {'Visible': ('$PARAM[animate]', [('100', '100', '150', None), ('0', '100', '150', '150')]),
                     'Hidden': ('$PARAM[animate]', [('100', '0', '150', None)])}


def test_left_hint_runs_up_the_edge():
    """Left: the line turned a quarter to the left about its centre, so it reads bottom to top
    along the edge and its ↑ shows as ←. The group has its size, else Kodi turns it about its
    corner; centred on the left edge by default (its middle at x 24, y 540)."""
    include = _include('LevelHintLeft')
    defaults = {p.get('name'): p.get('default') for p in include.findall('param')}
    assert (defaults['left'], defaults['top']) == LEFT_EDGE
    group = include.find('definition/control')
    assert (group.findtext('width'), group.findtext('height')) == ('600', '30')
    assert int(defaults['left']) + 300 == 24 and int(defaults['top']) + 15 == 540
    rotate = [a for a in group.findall('animation') if a.get('effect') == 'rotate']
    assert [(a.get('end'), a.get('center'), a.get('time'), a.get('condition'), a.text) for a in rotate] == [
        ('90', 'auto', '0', 'true', 'Conditional')]
    assert group.find('include').get('content') == 'LevelHintFade'
    (label,) = group.findall('control')
    assert (label.findtext('width'), label.findtext('height'), label.findtext('align')) == ('600', '30', 'center')
    assert label.findtext('include') == 'LevelHintText'
    assert label.find("include[@content='LookLabelCase']/param").get('value') == KEY.format('↑') + ' $PARAM[label]'


def test_right_hint_runs_down_the_edge():
    """Right: LevelHintLeft mirrored, the line turned a quarter to the right, so it reads top to
    bottom along the right edge and its ↑ shows as →; its middle at x 1896, y 540."""
    left, right = _include('LevelHintLeft'), _include('LevelHintRight')
    defaults = {p.get('name'): p.get('default') for p in right.findall('param')}
    assert (defaults['left'], defaults['top']) == RIGHT_EDGE
    assert int(defaults['left']) + 300 == 1920 - 24 and int(defaults['top']) + 15 == 540
    group = right.find('definition/control')
    assert _turn(group) == '-90'
    mirrored = ET.tostring(left.find('definition'), encoding='unicode').replace('end="90"', 'end="-90"')
    assert ET.tostring(right.find('definition'), encoding='unicode') == mirrored


def _keys(params):
    """The keys of a hint: its key, and the coloured keys in its label and in the Hint variables
    it names."""
    text = params['label']
    for name in re.findall(r'\$VAR\[(Hint\w+)\]', text):
        text += ' '.join(v or '' for _, v in _variable(name))
    return [params.get('key', '↓')] + [k[len('[COLOR state_text]'):-len('[/COLOR]')] for k in COLOURED_KEY.findall(text)]


def test_every_hint_is_a_glyph():
    """Keys are glyphs, OK the one word: no other key words, no key outside the coloured
    keys."""
    hints = _all_hints()
    assert len(hints) >= 18
    for name, _, params in hints:
        assert params.get('key', '↓') in KEYS, (name, params)
        assert not GLYPHS.search(COLOURED_KEY.sub('', params['label'])), (name, params)


# where a hint's container does not start at the top of the screen: the episodes' footer lies
# in the info page's lower grouplist (5400, top 619)
OFFSET = {('DialogVideoInfo.xml', '5190'): 619}
FOCUS = re.compile(r'HasFocus|System\.CurrentControl|Container\.HasFocus')
# the hints that show the keys of the focused row (DESIGN.md: an exception, open for now)
FOCUSED_ROW = {('DialogVideoInfo.xml', '5190'),
               # Home's footer while the focus is in the top line, OK on the movies and shows tabs
               ('Home.xml', '9195'),
               # the OSD's footer names OK on subtitles, audio and video, the full settings
               ('VideoOSD.xml', '690'), ('VideoOSD.xml', '691'), ('VideoOSD.xml', '692'),
               # Right into the next column, while the focus is in the column it leads from
               ('SettingsCategory.xml', '9058'), ('SkinSettings.xml', '9058'), ('DialogAddonSettings.xml', '9058')}


def test_a_hint_does_not_follow_the_focus():
    """Per page, stable: no hint shows or names by the focused element, neither in its condition
    nor in a Hint variable of its label (the episodes' footer is the exception)."""
    for name, _, params in _all_hints():
        if (name, params['id']) in FOCUSED_ROW:
            continue
        assert not FOCUS.search(params.get('visible', '')), (name, params['id'], params.get('visible'))
        for var in re.findall(r'\$VAR\[(Hint\w+)\]', params['label']):
            assert not [c for c, _ in _variable(var) if c and FOCUS.search(c)], (name, var)


def test_no_hint_where_the_outermost_element_does_nothing():
    """Left on the library's grid and on the lists of the video and music windows does nothing,
    nor on the categories of an add-on's settings: no Left hint there."""
    for name in ('Custom_1110_Library.xml', 'MyVideoNav.xml', 'MyMusicNav.xml', 'DialogAddonSettings.xml'):
        assert not [i for i in parse(ROOT / '1080i' / name).iter('include') if i.get('content') in HINTS[:2]], name
    for name, cid in (('Custom_1110_Library.xml', '5000'), ('MyVideoNav.xml', '50'), ('MyVideoNav.xml', '51'),
                      ('MyMusicNav.xml', '50'), ('MyMusicNav.xml', '51'), ('DialogAddonSettings.xml', '3')):
        assert _controls(name)[cid].find('onleft') is None, (name, cid)


def test_where_a_hint_stands_follows_its_key():
    """Up at the top, centred; Left up the left edge (LevelHintLeft), never in a line of its own
    kind; Down and OK in the footer line, left at the margin, where the keys of the focused row
    may stand together (the episodes: ←→ episode, ↑ season, ↓ cast, OK select)."""
    for name, include, params in _all_hints():
        hid = params['id']
        key = params.get('key', '↓')
        if (name, hid) in FRAME_HINTS:
            left, top, width, height = FRAME_HINTS[(name, hid)]
            assert (params.get('left', LEFT_EDGE[0]), params['top']) == (left, top), (name, hid)
            # its middle 24 inside the frame's edge, on the frame's middle
            middle = int(left) + 300
            assert middle == (24 if include == 'LevelHintLeft' else width - 24), (name, hid)
            assert int(top) + 15 == height // 2, (name, hid)
            continue
        if include == 'LevelHintLeft':
            assert (params.get('left', LEFT_EDGE[0]), params.get('top', LEFT_EDGE[1])) == LEFT_EDGE, (name, hid)
            continue
        if include == 'LevelHintRight':
            assert (params.get('left', RIGHT_EDGE[0]), params.get('top', RIGHT_EDGE[1])) == RIGHT_EDGE, (name, hid)
            continue
        assert key not in ('←', '→'), (name, hid)
        top = int(params.get('top', BOTTOM)) + OFFSET.get((name, hid), 0)
        if key == '↑':
            assert top <= int(TOP) and params.get('align') == 'center', (name, hid, top)
        else:
            assert key in ('↓', OK, '←→', '↑↓'), (name, hid)
            assert top == int(BOTTOM), (name, hid, top)
            assert (params.get('left', '0'), params.get('width', '1920'), params.get('align', 'center')) == ('0', '1920', 'center'), (name, hid)


def test_glyphs_only_in_hints():
    """An arrow is a key hint (⏎ is no key any more): the key of a LevelHint, a coloured key in its label or in a
    Hint variable, or a footer string; never a loose label of its own."""
    for path in layout_files():
        if path.name == 'Variables.xml':
            continue
        root = parse(path)
        for el in root.iter():
            if el.tag in ('label', 'label2', 'value') and GLYPHS.search(el.text or ''):
                assert False, (path.name, el.text)
        allowed = set()
        for inc in root.iter('include'):
            if inc.get('content') in HINTS:
                allowed |= set(inc.findall('param'))
            # the defaults of LevelHint and the turned ↑ of LevelHintLeft
            if inc.get('name') in HINTS:
                allowed |= set(inc.iter('param'))
        for param in root.iter('param'):
            if GLYPHS.search(param.get('value') or param.get('default') or ''):
                assert param in allowed and param.get('name') in ('key', 'label', 'text'), (path.name, param.get('value'))
    # a variable may hold a part of a hint, its keys coloured
    for var in parse(ROOT / '1080i' / 'Variables.xml').iter('variable'):
        for value in var.iter('value'):
            if GLYPHS.search(value.text or ''):
                assert var.get('name').startswith('Hint'), var.get('name')
                assert not GLYPHS.search(COLOURED_KEY.sub('', value.text)), var.get('name')


FOOTERS = ('31178', '31260', '31261')
WORDS = re.compile(r'\b(OK|Back|Left|Right|Up|Down)\b')


def test_footer_strings_are_glyphs():
    """The footers of keys acting on the spot: each key an arrow or OK in the dimmed blue of a
    hint, in every language; no key word outside them (OK, Back, Left...)."""
    langs = [p.name.split('.')[-1] for p in (ROOT / 'language').iterdir()]
    for num in FOOTERS:
        english = _string(num)
        keys = re.findall(r'\[COLOR state_text\](.*?)\[/COLOR\]', english)
        assert keys and all(k in KEYS for k in keys), (num, english)
        assert not WORDS.search(re.sub(r'\[[^\]]*\]', '', COLOURED_KEY.sub('', english))), (num, english)
        for lang in langs:
            assert re.findall(r'\[COLOR state_text\](.*?)\[/COLOR\]', _string(num, lang)) == keys, (lang, num)
    assert _string('31178') == KEY.format(OK) + ' open'
    assert _string('31260') == KEY.format(OK) + ' choose   ' + KEY.format('→') + ' option'
    assert _string('31261') == KEY.format('↑↓') + ' move   ' + KEY.format(OK) + ' drop'


def test_the_player_controls_have_one_name():
    """The OSD bar is "controls" in every hint that leads to it; "menu" is left to the menus
    beside a list (Home's top menu, the library's)."""
    assert _string('31478') == 'controls'
    assert _string('31232') == 'menu'
    for name, _, params in _all_hints():
        if name in ('DialogSeekBar.xml', 'MusicVisualisation.xml', 'VideoOSD.xml', 'VideoOSDBookmarks.xml'):
            assert params['label'] != '$LOCALIZE[31232]', (name, params)


def test_seek_bar_hint():
    """Over the bare video Up and Down skip chapters (Kodi's keymap), OK opens the controls: the
    seek bar shows that key. The OSD and the stats dialog bring their own keys."""
    key, label, top, visible = _hint('DialogSeekBar.xml', '490')
    assert (key, label, top) == (OK, CONTROLS, BOTTOM)
    assert visible == '!Window.IsVisible(videoosd) + !Window.IsActive(playerprocessinfo)'


def test_visualisation_hint():
    key, label, top, visible = _hint('MusicVisualisation.xml', '9090')
    assert (key, label, top, visible) == (OK, CONTROLS, BOTTOM, '!Window.IsActive(musicosd)')


def test_osd_hint():
    """The controls: Down from the bar, their bottom, opens the cast row of a library title; shown
    on the whole of the controls (a panel above a button and the chapter panel too), hidden
    while the cast row is up."""
    key, label, top, visible = _hint('VideoOSD.xml', '690')
    assert (key, label, top) == ('↓', '$LOCALIZE[31702]', BOTTOM)
    assert _string('31702') == 'cast & crew' and _string('31702', 'de_de') == 'Besetzung & Crew'
    assert visible == '!Window.IsActive(1141) + [{}] + {}'.format(CAST, ' + '.join('!Control.HasFocus({})'.format(b) for b in TRACK_BUTTONS))
    assert '693' not in _controls('VideoOSD.xml')  # no hint of the panels' own
    controls = _controls('VideoOSD.xml')
    for row in ('600', '620'):
        assert _actions(controls[row], 'ondown') == [(CAST, 'ActivateWindow(1141)')], row


def test_chapter_panel_has_no_hints_of_its_own():
    """The chapter panel is a panel above a button of the controls: their hints stay, it has
    none of its own. Down from the list goes back onto its button, Up from the buttons does
    nothing."""
    controls = _controls('VideoOSDBookmarks.xml')
    assert not [i for i in parse(ROOT / '1080i' / 'VideoOSDBookmarks.xml').iter('include') if i.get('content') == 'LevelHint']
    assert _actions(controls['11'], 'ondown') == [('', '90')]
    assert _actions(controls['9000'], 'onup') == [('', 'noop')]


TRACK_BUTTONS = ('605', '606', '607')


def test_osd_hint_on_subtitles_audio_and_video():
    """While subtitles, audio or video has the focus the footer adds OK, the full settings, right
    of the standing Down to the cast row of a library title (DESIGN.md: the hint that follows
    the focus stands right): one line in the place of the Down hint, which fades out for it.
    Without a cast row OK all settings alone."""
    focus = '[' + ' | '.join('Control.HasFocus({})'.format(b) for b in TRACK_BUTTONS) + ']'
    key, label, top, visible = _hint('VideoOSD.xml', '691')
    assert (key, label, top) == ('↓', '$VAR[HintTrackSettings]', BOTTOM)
    assert visible == '!Window.IsActive(1141) + [{}] + {}'.format(CAST, focus)
    assert _variable('HintTrackSettings') == [(None, '$LOCALIZE[31702]   [COLOR state_text]OK[/COLOR] $LOCALIZE[31139]')]
    key, label, top, visible = _hint('VideoOSD.xml', '692')
    assert (key, label, top) == (OK, '$LOCALIZE[31139]', BOTTOM)
    assert visible == '!Window.IsActive(1141) + ![{}] + {}'.format(CAST, focus)
    assert _string('31139') == 'all settings'


def test_cast_row_hint():
    """The cast row: Up from the tabs goes back to the controls; nothing lies below."""
    key, label, top, visible = _hint('Custom_1141_OSDCast.xml', '6590')
    assert (key, label, top, visible) == ('↑', CONTROLS, TOP, 'true')
    controls = _controls('Custom_1141_OSDCast.xml')
    assert controls['6520'].findtext('onup') == 'Dialog.Close(1141)'
    assert controls['6501'].findtext('ondown') == 'noop'


INFO_PAGES = ('DialogVideoInfo.xml', 'DialogMusicInfo.xml')


def test_info_page_hint():
    """An info page leaves by Up from its buttons, its top row: "↑" and where that leads, centred
    on the path line, on the whole page."""
    for name in INFO_PAGES:
        controls = _controls(name)
        key, label, top, visible = _hint(name, '9059')
        assert (key, label, visible) == ('↑', '$VAR[HintInfoBack]', 'true'), name
        assert top == controls['9026'].findtext('top') == PATH, name
        assert controls['9000'].findtext('onup') == 'Action(Back)', name


def test_info_page_hint_names_where_up_leads():
    """The page before in a TMDb chain, else the window the page lies over by its name: the page
    of Home, the library, the video; "back" only where nothing tells."""
    values = _variable('HintInfoBack')
    assert values[0] == ('!String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
                         ' + Integer.IsGreater(Window(Home).Property(TMDbHelper.Position),1)', '$LOCALIZE[31479]')
    assert ('Window.IsActive(fullscreenvideo)', '$LOCALIZE[31055]') in values
    assert ('Window.IsActive(home)', '$VAR[HintHomePage]') in values
    assert ('Window.IsActive(1110)', '$VAR[HintLibrary]') in values
    assert values[-1] == (None, '$LOCALIZE[31470]')
    assert _string('31479') == 'previous page'
    pages = dict(_variable('HintHomePage'))
    assert pages['String.IsEqual(Window(Home).Property(nc.page),system)'] == '$LOCALIZE[31033]'
    assert pages[None] == '$LOCALIZE[31006]'


def test_info_page_hint_room():
    """The path on the left ends before the centre, so a long title never runs into the hint;
    the clock and the weather sit right-aligned at the far end."""
    for name in INFO_PAGES:
        path = _controls(name)['9026']
        assert int(path.findtext('left')) + int(path.findtext('width')) <= 860, name


def test_episode_keys():
    """The footer line while the episodes have the focus names the keys of the row: Left and
    Right the episode, Up the season tabs, Down cast and crew (where the page has them), OK
    selects."""
    key, label, top, visible = _hint('DialogVideoInfo.xml', '5190')
    assert key == '←→'
    assert label == '$LOCALIZE[31132]   {} $LOCALIZE[31131]$VAR[HintEpisodeDown]   {} $LOCALIZE[31135]'.format(
        KEY.format('↑'), KEY.format(OK))
    assert visible == 'Control.HasFocus(5100)'
    assert int(top) + OFFSET[('DialogVideoInfo.xml', '5190')] == int(BOTTOM)
    assert _controls('DialogVideoInfo.xml')['5100'].findtext('onup') == '5200'


# window: (hint id, key, label), one per page, shown wherever the focus is (only not under a
# dialog); Left up the left edge, Up (the weather) on the path line
MODAL = '!System.HasActiveModalDialog'
WINDOW_HINTS = {
    'Settings.xml': ('9059', '←', '$LOCALIZE[31033]'),
    'SettingsCategory.xml': ('9059', '←', '$VAR[HintWindowBack]'),
    'SkinSettings.xml': ('9059', '←', '$VAR[HintWindowBack]'),
    'SettingsProfile.xml': ('9059', '←', '$VAR[HintWindowBack]'),
    'EventLog.xml': ('9059', '←', '$VAR[HintWindowBack]'),
    'AddonBrowser.xml': ('9059', '←', '$VAR[HintAddonsBack]'),
    'FileManager.xml': ('9059', '←', '$VAR[HintFilesBack]'),
    'SettingsSystemInfo.xml': ('9059', '←', '$VAR[HintWindowBack]'),
    'MyWeather.xml': ('9059', '↑', '$VAR[HintWindowBack]'),
}


def test_window_hints():
    """A full window shows the way back of its left column (or its top row: the weather) on the
    whole page: Left from the categories of a settings page, from the list of the add-on browser,
    the file manager's left pane; one hint, the same wherever the focus is."""
    for name, (cid, key_want, label_want) in WINDOW_HINTS.items():
        controls = _controls(name)
        hints = [i for i in parse(ROOT / '1080i' / name).iter('include') if i.get('content') in HINTS[:2]]
        assert len(hints) == 1, name
        key, label, top, visible = _hint(name, cid)
        # not under a dialog on top: the window keeps its focus under it
        assert [key, label, visible] == [key_want, label_want, MODAL], (name, cid)
        group = controls[cid]
        if key == '←':
            assert _turned(group) and (group.findtext('left'), top) == LEFT_EDGE, (name, cid)
        else:
            assert top == PATH and int(controls['9026'].findtext('width')) <= 780, name
        # a page does not blend over a playing video
        fades = [a for a in group.findall('animation') if a.get('type') in ('Visible', 'Hidden')]
        assert fades and all(a.get('condition') == '!Player.HasVideo' for a in fades), (name, cid)


def test_the_keys_of_the_window_hints():
    """The hints say what the keys do there."""
    for name, cid, tag, action in (
            ('Settings.xml', '9200', 'onleft', 'Action(Back)'),
            ('SettingsCategory.xml', '3', 'onleft', 'Action(Back)'),
            ('SkinSettings.xml', '9000', 'onleft', 'Action(Back)'),
            ('SettingsProfile.xml', '2', 'onleft', 'Action(Back)'),
            ('EventLog.xml', '50', 'onleft', 'Action(Back)'),
            ('AddonBrowser.xml', '50', 'onleft', 'Action(Back)'),
            ('FileManager.xml', '20', 'onleft', 'Action(Back)'),
            ('SettingsSystemInfo.xml', '9000', 'onleft', 'Action(Back)'),
            ('MyWeather.xml', '500', 'onup', 'Action(Back)')):
        assert action in [a for _, a in _actions(_controls(name)[cid], tag)], (name, cid)


def test_dialog_hints():
    """A dialog's Left hint runs up its frame's left inner edge, centred on it, never outside the
    frame, where it stood over the window below: on the whole dialog, in the skin's select
    dialogs Left on the list goes one level up, in a group of the library filter to its groups,
    else onto the library. The dialog is wider by the hints' room, its content in by as much,
    so neither hint stands on the list."""
    dialog = load('DialogSelect.xml').find('controls/control')
    assert dialog.findtext('width') == '1156'
    (inner,) = [c for c in dialog.findall('control') if c.get('type') == 'group' and c.findtext('left') == '28']
    assert inner.findtext('width') == '1100'
    assert {c.get('id') for c in dialog.findall('control')} >= {'9058', '9059'}
    group = _controls('DialogSelect.xml')['9059']
    assert _turned(group) and (group.findtext('left'), group.findtext('top')) == ('-276', '395')
    key, label, top, visible = _hint('DialogSelect.xml', '9059')
    assert (key, label) == ('←', '$VAR[HintSelectBack]')
    assert visible == '!String.IsEmpty(Window(Home).Property(nc.select.ok))'
    values = _variable('HintSelectBack')
    assert values[0] == ('Control.IsVisible(5) + !String.IsEmpty(Window(Home).Property(nc.select.groups))', '$LOCALIZE[31502]')
    assert ('Window.IsActive(1110)', '$VAR[HintLibrary]') in values
    script = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    assert "_home().setProperty('nc.select.groups', '1')" in script


# window: (label, visible, the control Right leads from, what it does there)
RIGHT_HINTS = {
    'Settings.xml': ('$LOCALIZE[31135]', MODAL, '9200', 'Action(Select)'),
    'SettingsCategory.xml': ('$LOCALIZE[5]', '[ControlGroup(3).HasFocus() | ControlGroup(9003).HasFocus()] + ' + MODAL, '3', '5'),
    'SkinSettings.xml': ('$LOCALIZE[5]', 'ControlGroup(9000).HasFocus() + ' + MODAL, '9000', None),
    'DialogAddonSettings.xml': ('$LOCALIZE[5]', 'ControlGroup(3).HasFocus()', '3', '5'),
    'DialogSelect.xml': ('$LOCALIZE[31135]', '!String.IsEmpty(Window(Home).Property(nc.select.ok)) + !Control.IsVisible(5)',
                         '3', 'Action(Select)'),
}


def test_right_hints():
    """Right into the next column, down the screen's right edge: from the categories of a settings
    page into their settings (while the focus is in the categories), on the settings rail and in
    the skin's select dialogs a list of choices takes the focused one, as OK (not a multi-select,
    where Right stays)."""
    assert _string('31135') == 'select'
    for name, (label_want, visible_want, cid, action) in RIGHT_HINTS.items():
        hints = [i for i in parse(ROOT / '1080i' / name).iter('include') if i.get('content') == 'LevelHintRight']
        assert len(hints) == 1, name
        key, label, top, visible = _hint(name, '9058')
        assert (key, label, visible) == ('→', label_want, visible_want), name
        actions = [a for _, a in _actions(_controls(name)[cid], 'onright')]
        assert actions and (action is None or action in actions), (name, actions)


def test_quick_menu_hint():
    """The quick menu dialog: Up from the weather, its top, closes it; the hint names what it
    lies over, centred on the panel's top edge, above it, while the menu is open."""
    controls = _controls('Custom_1170_QuickMenu.xml')
    key, label, top, visible = _hint('Custom_1170_QuickMenu.xml', '1290')
    assert (key, label, visible) == ('↑', '$VAR[HintQuickMenuBack]', 'true')
    panel, group = controls['1200'], controls['1290']
    assert group.findtext('left') == panel.findtext('left')
    assert int(top) + int(group.find('control').findtext('height')) <= int(panel.findtext('top'))
    assert _actions(controls['1210'], 'onup')[0] == ('', 'Dialog.Close(1170,true)')


def test_footers_look_like_the_hints():
    """The footers of keys acting on the spot (the console's, the skin settings' page rows) are
    one line of muted small caps like a hint, their keys coloured in the strings."""
    footers = []
    for name, string in (('Settings.xml', '$LOCALIZE[31178]'), ('SkinSettings.xml', '$VAR[HomePagesHint]')):
        footers += [(name, c) for c in load(name).iter('control')
                    if c.get('type') == 'label' and string in (c.findtext('label') or '')]
    assert [name for name, _ in footers] == ['Settings.xml', 'SkinSettings.xml']
    for name, label in footers:
        assert (label.findtext('font'), label.findtext('textcolor')) == ('font_caps_small', 'text_mute'), name
        assert label.findtext('label').startswith('[UPPERCASE]'), name
    assert [v for _, v in _variable('HomePagesHint')] == ['$LOCALIZE[31261]', '$LOCALIZE[31260]']


def test_back_through_folders():
    """Where Left is Kodi's Back through folders (the add-on browser's list, the file manager's
    left pane) the hint names the folder above, "parent folder", since Kodi does not name it,
    and at the top of the folders the window before, which Back goes to there: the add-on
    browser's top is addons://, the file manager's pane shows "Root" (Kodi's 20108) over it."""
    assert _string('31480') == 'parent folder'
    assert _variable('HintAddonsBack') == [('String.IsEqual(Container.FolderPath,addons://)', '$VAR[HintWindowBack]'),
                                           (None, '$LOCALIZE[31480]')]
    assert _variable('HintFilesBack') == [('String.IsEqual(Control.GetLabel(101),$LOCALIZE[20108])', '$VAR[HintWindowBack]'),
                                          (None, '$LOCALIZE[31480]')]


def test_no_return_glyph_left():
    """OK is the word on the remote's key: no ⏎ in a window, a variable or a string."""
    for path in layout_files():
        assert '⏎' not in path.read_text(encoding='utf-8'), path.name
    for po in (ROOT / 'language').glob('*/strings.po'):
        assert '⏎' not in po.read_text(encoding='utf-8'), po.parent.name


HOME_TOP = 'ControlGroup(9100).HasFocus() | Control.HasFocus(9108) | Control.HasFocus(9109)'


def test_home_footer_while_in_the_top_line():
    """While the focus is in Home's top line (the menu, what plays, the quick menu's icon) the
    footer names where Down leads into the shown page, and right of it OK on the movies and
    shows tabs; gone once the focus is in the page."""
    key, label, top, visible = _hint('Home.xml', '9195')
    assert (key, label, top) == ('↓', '$VAR[HintHomeDown]$VAR[HintHomeOk]', BOTTOM)
    assert visible == HOME_TOP


PAGE = 'Window(Home).Property(nc.page)'


def test_home_footer_names_where_down_leads():
    """The quick menu from its icon; the spotlight where the page has one (the music page's
    album spotlight too), the rows where it is off; the search field; the settings page's
    tiles. As HomePageDown goes."""
    values = _variable('HintHomeDown')
    assert values[0] == ('Control.HasFocus(9109)', '$LOCALIZE[31320]')
    assert ('String.IsEqual({},movies) + String.IsEqual(Skin.String(nc.movies.spotlight),off)'.format(PAGE), '$LOCALIZE[31224]') in values
    assert ('String.IsEqual({},shows) + String.IsEqual(Skin.String(nc.shows.spotlight),off)'.format(PAGE), '$LOCALIZE[31224]') in values
    assert ('String.IsEqual({0},movies) | String.IsEqual({0},shows) | String.IsEqual({0},music)'.format(PAGE), '$LOCALIZE[31100]') in values
    assert ('String.IsEqual({},search)'.format(PAGE), '$LOCALIZE[31141]') in values
    assert ('String.IsEqual({},system)'.format(PAGE), '$LOCALIZE[5]') in values
    assert values[-2:] == [('String.IsEqual(Skin.String(SpotlightSource),off)', '$LOCALIZE[31224]'), (None, '$LOCALIZE[31100]')]
    assert (_string('31100'), _string('31224'), _string('31141'), _string('31320')) == (
        'spotlight', 'Rows', 'search for a title', 'quick menu')


def test_home_footer_names_ok_on_the_tabs_and_the_icon():
    """Right of Down, while its tab has the focus (DESIGN.md: the hint that follows the focus
    stands right): OK opens all movies, all shows or all albums, on the quick menu's icon the
    settings."""
    assert _variable('HintHomeOk') == [
        ('Control.HasFocus(9102)', '   {} $LOCALIZE[31101]'.format(KEY.format(OK))),
        ('Control.HasFocus(9103)', '   {} $LOCALIZE[31102]'.format(KEY.format(OK))),
        ('Control.HasFocus(9107)', '   {} $LOCALIZE[31481]'.format(KEY.format(OK))),
        ('Control.HasFocus(9109)', '   {} $LOCALIZE[5]'.format(KEY.format(OK)))]
    assert (_string('31101'), _string('31102'), _string('31481')) == ('all movies', 'all shows', 'all albums')


def test_ok_on_movies_and_shows_opens_all_of_them():
    """OK on the movies or shows tab opens the library window with all of them, on the tab of
    the shown page too (a toggle button runs its altclick then); Down goes into the page."""
    menu = {c.get('id'): c for c in load('Home.xml').iter('control') if c.get('id') in ('9101', '9102', '9103', '9104')}
    for tab, library in (('9102', 'movies'), ('9103', 'tvshows')):
        want = ['SetProperty(nc.library,{},home)'.format(library), 'ActivateWindow(1110)']
        assert [a.text for a in menu[tab].findall('onclick')] == want, tab
        assert [a.text for a in menu[tab].findall('altclick')] == want, tab
    assert [a.text for a in menu['9101'].findall('onclick')] == ['Action(Down)', 'noop']


def test_ok_on_music_opens_all_albums():
    """OK on the music tab opens the music window's albums, as the spotlight's albums button."""
    menu = {c.get('id'): c for c in load('Home.xml').iter('control') if c.get('id') in ('9107', '9854')}
    want = 'ActivateWindow(Music,musicdb://albums/,return)'
    assert [a.text for a in menu['9107'].findall('onclick')] == [want, 'noop']
    assert [a.text for a in menu['9107'].findall('altclick')] == [want, 'noop']
    assert [a.text for a in menu['9854'].findall('onclick')][0] == want
