"""Key hints (DESIGN.md, Key hints): where a key leads to another level and the screen does not
show it, one quiet line names the key, a glyph in the dimmed blue of a hint, and the level it
leads to, muted. Where it stands follows its key: Up at the top (the path line, top 30; the
player's top edge, top 140), Left up the left edge, written bottom to top (LevelHintLeft), Down
and OK in the footer line at the bottom (left 64, top 1030), where the keys of the focused row
may stand together.

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
CHAPTERS = '$VAR[PlayerChaptersLevel]'
CONTROLS = '$LOCALIZE[31478]'
CATEGORIES = '$LOCALIZE[31176]'
KEYS = ('↑', '↓', '←', '→', '⏎', '↑↓', '←→')
GLYPHS = re.compile('[↑↓←→⏎]')
KEY = '[COLOR state_text]{}[/COLOR]'
COLOURED_KEY = re.compile(r'\[COLOR state_text\][↑↓←→⏎]+\[/COLOR\]')
LABEL = re.compile(r'^\[UPPERCASE\]\[COLOR state_text\](\S+)\[/COLOR\] (.+)\[/UPPERCASE\]$')
# a Left hint: the middle of the screen's left edge, or a dialog's (just outside its frame)
LEFT_EDGE = ('-276', '525')
HINTS = ('LevelHint', 'LevelHintLeft')


def _controls(name):
    return {c.get('id'): c for c in load(name).iter('control') if c.get('id')}


def _turned(group):
    return any(a.get('effect') == 'rotate' for a in group.findall('animation'))


def _hint(name, cid):
    """(key, label, top, visible) of the hint `cid` in window `name`; a turned line's ↑ is a ←
    on the screen."""
    group = _controls(name)[cid]
    (line,) = group.findall('control')
    assert line.get('type') == 'label', cid
    key, label = LABEL.match(line.findtext('label')).groups()
    if _turned(group):
        assert key == '↑', (name, cid)
        key = '←'
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
                found.append((path.name, inc.get('content'), params))
    return found


def test_hint_look():
    """The key in the dimmed blue of a hint, the label muted, one line of small caps; a shadow
    keeps it readable over bright video. By default in the footer line, left at the margin; it
    fades out, then in."""
    include = _include('LevelHint')
    defaults = {p.get('name'): p.get('default') for p in include.findall('param')}
    assert (defaults['top'], defaults['left'], defaults['width'], defaults['align']) == (BOTTOM, '64', '1792', 'left')
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


def _keys(params):
    """The keys of a hint: its key, and the coloured keys in its label and in the Hint variables
    it names."""
    text = params['label']
    for name in re.findall(r'\$VAR\[(Hint\w+)\]', text):
        text += ' '.join(v or '' for _, v in _variable(name))
    return [params.get('key', '↓')] + [k[len('[COLOR state_text]'):-len('[/COLOR]')] for k in COLOURED_KEY.findall(text)]


def test_every_hint_is_a_glyph():
    """Keys are glyphs, no key words."""
    hints = _all_hints()
    assert len(hints) >= 25
    for name, _, params in hints:
        assert params.get('key', '↓') in KEYS, (name, params)
        assert not GLYPHS.search(COLOURED_KEY.sub('', params['label'])), (name, params)


# where a hint's container does not start at the top of the screen: the episodes' footer lies
# in the info page's lower grouplist (5400, top 619)
OFFSET = {('DialogVideoInfo.xml', '5190'): 619}
# the dialogs' Left hints: just outside the frame (centre x -22), on the dialog's middle
DIALOG_LEFT = {'DialogSelect.xml': ('-322', str(820 // 2 - 15)), 'DialogAddonSettings.xml': ('-322', str(940 // 2 - 15))}


def test_where_a_hint_stands_follows_its_key():
    """Up at the top, centred; Left up the left edge (LevelHintLeft), never in a line of its own
    kind; Down and OK in the footer line, left at the margin, where the keys of the focused row
    may stand together (the episodes: ←→ episode, ↑ season, ↓ cast, ⏎ select)."""
    for name, include, params in _all_hints():
        hid = params['id']
        key = params.get('key', '↓')
        if include == 'LevelHintLeft':
            want = DIALOG_LEFT.get(name, LEFT_EDGE)
            assert (params.get('left', LEFT_EDGE[0]), params.get('top', LEFT_EDGE[1])) == want, (name, hid)
            continue
        assert key != '←', (name, hid)
        top = int(params.get('top', BOTTOM)) + OFFSET.get((name, hid), 0)
        if key == '↑':
            assert top <= int(TOP) and params.get('align') == 'center', (name, hid, top)
        else:
            assert key in ('↓', '⏎', '←→', '↑↓'), (name, hid)
            assert top == int(BOTTOM), (name, hid, top)
            assert (params.get('left', '64'), params.get('align', 'left')) == ('64', 'left'), (name, hid)


def test_glyphs_only_in_hints():
    """An arrow or ⏎ is a key hint: the key of a LevelHint, a coloured key in its label or in a
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
    """The footers of keys acting on the spot: each key a glyph in the dimmed blue of a hint, in
    every language; no key word left (OK, Back, Left...)."""
    langs = [p.name.split('.')[-1] for p in (ROOT / 'language').iterdir()]
    for num in FOOTERS:
        english = _string(num)
        keys = re.findall(r'\[COLOR state_text\](.*?)\[/COLOR\]', english)
        assert keys and all(k in KEYS for k in keys), (num, english)
        assert not WORDS.search(re.sub(r'\[[^\]]*\]', '', english)), (num, english)
        for lang in langs:
            assert re.findall(r'\[COLOR state_text\](.*?)\[/COLOR\]', _string(num, lang)) == keys, (lang, num)
    assert _string('31178') == KEY.format('⏎') + ' open'
    assert _string('31260') == KEY.format('⏎') + ' choose   ' + KEY.format('→') + ' option'
    assert _string('31261') == KEY.format('↑↓') + ' move   ' + KEY.format('⏎') + ' drop'


def test_chapters_level_name():
    """The row below the bar lists the chapters, or only the bookmark buttons without chapters."""
    assert _variable('PlayerChaptersLevel') == [
        ('Integer.IsGreater(Player.ChapterCount,0)', '$LOCALIZE[31140]'), (None, '$LOCALIZE[31056]')]


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
    assert (key, label, top) == ('⏎', CONTROLS, BOTTOM)
    assert visible == '!Window.IsVisible(videoosd) + !Window.IsActive(playerprocessinfo)'


def test_visualisation_hint():
    key, label, top, visible = _hint('MusicVisualisation.xml', '9090')
    assert (key, label, top, visible) == ('⏎', CONTROLS, BOTTOM, '!Window.IsActive(musicosd)')


def test_osd_hint():
    """The bar: Down opens the chapter row. Hidden while a panel above a button has the focus
    (Down goes back to the button there) and while a lower level is up."""
    key, label, top, visible = _hint('VideoOSD.xml', '690')
    assert (key, label, top) == ('↓', CHAPTERS, BOTTOM)
    assert visible == ('!Window.IsActive(videobookmarks) + !Window.IsActive(1141)'
                       ' + !Control.HasFocus(651) + !Control.HasFocus(652) + !Control.HasFocus(653)')
    controls = _controls('VideoOSD.xml')
    for row in ('600', '620'):
        assert controls[row].findtext('ondown') == 'ActivateWindow(videobookmarks)', row


def test_osd_panel_hint():
    """A panel above a button (subtitles, audio, video): Down goes back to the controls; the hint
    stands where the bar's does."""
    key, label, top, visible = _hint('VideoOSD.xml', '691')
    assert (key, label, top) == ('↓', CONTROLS, BOTTOM)
    assert visible == 'Control.HasFocus(651) | Control.HasFocus(652) | Control.HasFocus(653)'
    player = parse(ROOT / '1080i' / 'Includes_Player.xml')
    for name in ('TrackPanel', 'VideoPanel'):
        inc = next(i for i in player.iter('include') if i.get('name') == name)
        assert '$PARAM[button]' in [d.text for d in inc.iter('ondown')], name


def test_chapter_row_hints():
    """The chapter row: Down opens the cast row (library movies and episodes only), Up goes back
    to the controls."""
    controls = _controls('VideoOSDBookmarks.xml')
    key, label, top, visible = _hint('VideoOSDBookmarks.xml', '91')
    assert (key, label, top) == ('↓', '$LOCALIZE[31124]', BOTTOM)
    assert visible == '!Window.IsActive(1141) + [{}]'.format(CAST)
    assert (CAST, 'ActivateWindow(1141)') in _actions(controls['11'], 'ondown')
    key, label, top, visible = _hint('VideoOSDBookmarks.xml', '92')
    assert (key, label, top) == ('↑', CONTROLS, TOP)
    assert visible == '!Window.IsActive(1141)'
    assert _actions(controls['9000'], 'onup') == [('', 'Dialog.Close(videobookmarks)')]


def test_cast_row_hint():
    """The cast row: Up from the tabs goes back to the chapter row; nothing lies below."""
    key, label, top, visible = _hint('Custom_1141_OSDCast.xml', '6590')
    assert (key, label, top, visible) == ('↑', CHAPTERS, TOP, 'true')
    controls = _controls('Custom_1141_OSDCast.xml')
    assert controls['6520'].findtext('onup') == 'Dialog.Close(1141)'
    assert controls['6501'].findtext('ondown') == 'noop'


INFO_PAGES = ('DialogVideoInfo.xml', 'DialogMusicInfo.xml')


def test_info_page_hint():
    """An info page leaves by Up from its buttons, its top: "↑" and where that leads, centred on
    the path line, while the buttons have the focus (Up from a row below only goes to the row
    above)."""
    for name in INFO_PAGES:
        controls = _controls(name)
        key, label, top, visible = _hint(name, '9059')
        assert (key, label, visible) == ('↑', '$VAR[HintInfoBack]', 'ControlGroup(9000).HasFocus()'), name
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
        KEY.format('↑'), KEY.format('⏎'))
    assert visible == 'Control.HasFocus(5100)'
    assert int(top) + OFFSET[('DialogVideoInfo.xml', '5190')] == int(BOTTOM)
    assert _controls('DialogVideoInfo.xml')['5100'].findtext('onup') == '5200'


# window: [(hint id, key, label, visible)]; Left up the left edge, the bar's way back to its menu
# too; Up (the weather) on the path line
MODAL = '!System.HasActiveModalDialog'
WINDOW_HINTS = {
    'Settings.xml': [('9059', '←', '$LOCALIZE[31033]', 'true')],
    'SettingsCategory.xml': [
        ('9059', '←', '$VAR[HintWindowBack]', '!ControlGroup(5).HasFocus()'),
        ('9058', '←', CATEGORIES, 'ControlGroup(5).HasFocus()')],
    'SkinSettings.xml': [
        ('9059', '←', '$VAR[HintWindowBack]', 'ControlGroup(9000).HasFocus()'),
        ('9058', '←', CATEGORIES, '!ControlGroup(9000).HasFocus()')],
    'SettingsProfile.xml': [
        ('9059', '←', '$VAR[HintWindowBack]', 'Control.HasFocus(2)'),
        ('9058', '←', '$LOCALIZE[13200]', 'ControlGroup(9000).HasFocus()')],
    'EventLog.xml': [
        ('9059', '←', '$VAR[HintWindowBack]', 'Control.HasFocus(50)'),
        ('9058', '←', '$LOCALIZE[14111]', 'ControlGroup(9000).HasFocus()')],
    'AddonBrowser.xml': [('9058', '←', '$INFO[Container.FolderName]', 'ControlGroup(9000).HasFocus()')],
    'SettingsSystemInfo.xml': [('9059', '←', '$VAR[HintWindowBack]', 'true')],
    'MyWeather.xml': [('9059', '↑', '$VAR[HintWindowBack]', 'true')],
    'Custom_1110_Library.xml': [
        ('9059', '←', '$VAR[HintLibrary]', 'ControlGroup(5100).HasFocus()'),
        ('9058', '←', '$LOCALIZE[31232]', 'Control.HasFocus(5200)')],
    'MyVideoNav.xml': [('9059', '←', '$INFO[Container.FolderName]', 'ControlGroup(9060).HasFocus()')],
    'MyMusicNav.xml': [
        ('9059', '←', '$INFO[Container.FolderName]', 'ControlGroup(9060).HasFocus()'),
        ('9058', '←', '$LOCALIZE[31232]', 'Control.HasFocus(5200)')],
}


def test_window_hints():
    """A full window shows its way back for the focused side: Left from a settings page's rows to
    its categories, from the categories out of the page; Left from the library's menu to its
    titles, from the bar to the menu, all up the left edge; Up out of the weather on the path
    line, the title kept left of it."""
    for name, hints in WINDOW_HINTS.items():
        controls = _controls(name)
        for cid, key_want, label_want, visible_want in hints:
            key, label, top, visible = _hint(name, cid)
            # not over a dialog on top, the select dialog of the library's filter say: the
            # window keeps its focus under it
            want = MODAL if visible_want == 'true' else '{} + {}'.format(MODAL, visible_want)
            assert [key, label, visible] == [key_want, label_want, want], (name, cid)
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
            ('SettingsCategory.xml', '5', 'onleft', '3'),
            ('SkinSettings.xml', '9000', 'onleft', 'Action(Back)'),
            ('SettingsProfile.xml', '2', 'onleft', 'Action(Back)'),
            ('SettingsProfile.xml', '9000', 'onleft', '2'),
            ('EventLog.xml', '50', 'onleft', 'Action(Back)'),
            ('EventLog.xml', '9000', 'onleft', '50'),
            ('AddonBrowser.xml', '9000', 'onleft', '50'),
            ('SettingsSystemInfo.xml', '9000', 'onleft', 'Action(Back)'),
            ('MyWeather.xml', '500', 'onup', 'Action(Back)'),
            ('Custom_1110_Library.xml', '5100', 'onleft', '5000'),
            ('Custom_1110_Library.xml', '5200', 'onleft', '5100'),
            ('MyMusicNav.xml', '5200', 'onleft', '9060')):
        assert action in [a for _, a in _actions(_controls(name)[cid], tag)], (name, cid)
    for name in ('MyVideoNav.xml', 'MyMusicNav.xml'):
        assert _actions(_controls(name)['9060'], 'onleft')[-1] == ('', '50'), name


def test_dialog_hints():
    """A dialog's Left hint runs up its own left edge, just outside the frame, centred on it:
    Left from an add-on's settings to its categories; in the skin's select dialogs Left goes one
    level up, in a group of the library filter to its groups, else onto the library."""
    for name, (left, top) in DIALOG_LEFT.items():
        group = _controls(name)['9059']
        assert _turned(group) and (group.findtext('left'), group.findtext('top')) == (left, top), name
        assert int(left) + 300 < 0  # the line's middle lies outside the frame
    key, label, top, visible = _hint('DialogAddonSettings.xml', '9059')
    assert (key, label, visible) == ('←', CATEGORIES, 'ControlGroup(5).HasFocus() + Control.IsVisible(3)')
    assert _controls('DialogAddonSettings.xml')['5'].findtext('onleft') == '3'
    key, label, top, visible = _hint('DialogSelect.xml', '9059')
    assert (key, label) == ('←', '$VAR[HintSelectBack]')
    assert visible == '!String.IsEmpty(Window(Home).Property(nc.select.ok)) + [Control.HasFocus(3) | Control.HasFocus(6)]'
    values = _variable('HintSelectBack')
    assert values[0] == ('Control.IsVisible(5) + !String.IsEmpty(Window(Home).Property(nc.select.groups))', '$LOCALIZE[31502]')
    assert ('Window.IsActive(1110)', '$VAR[HintLibrary]') in values
    script = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    assert "_home().setProperty('nc.select.groups', '1')" in script


def test_quick_menu_hint():
    """The quick menu dialog: Up from the weather, its top, closes it; the hint names what it
    lies over, centred on the panel's top edge, above it."""
    controls = _controls('Custom_1170_QuickMenu.xml')
    key, label, top, visible = _hint('Custom_1170_QuickMenu.xml', '1290')
    assert (key, label, visible) == ('↑', '$VAR[HintQuickMenuBack]', 'Control.HasFocus(1210)')
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
