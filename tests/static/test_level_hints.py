"""Key hints (DESIGN.md, Key hints): where a key leads to another level and the screen does not
show it, one quiet line names the key, a glyph in the dimmed blue of a hint, and the level it
leads to, muted. All of them come from the LevelHint include, in a few places: the way back
centred on the path line of a page (top 30), the player's way up on its top edge (top 140) and
its way on on the bottom edge (top 1030), a dialog's at its bottom, a row's keys under it.

Player levels: the seek bar over the bare video (OK opens the controls; Up and Down skip
chapters there), the controls (Down: the chapter row), a panel above a button (Down: back to
the controls), the chapter row (Down: the cast row, Up: the controls), the cast row (Up: the
chapter row). The info pages leave by Up from their buttons and say so on their path line,
while the buttons have the focus."""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT, layout_files, parse
from navigation import load, with_look

BOTTOM, TOP, PATH = '1030', '140', '30'
CAST = 'VideoPlayer.Content(movies) | VideoPlayer.Content(episodes)'
CHAPTERS = '$VAR[PlayerChaptersLevel]'
CONTROLS = '$LOCALIZE[31478]'
CATEGORIES = '$LOCALIZE[31176]'
KEYS = ('↑', '↓', '←', '→', '⏎', '↑↓')
GLYPHS = re.compile('[↑↓←→⏎]')
KEY = '[COLOR state_text]{}[/COLOR]'
COLOURED_KEY = re.compile(r'\[COLOR state_text\][↑↓←→⏎]+\[/COLOR\]')
LABEL = re.compile(r'^\[UPPERCASE\]\[COLOR state_text\](\S+)\[/COLOR\] (.+)\[/UPPERCASE\]$')


def _controls(name):
    return {c.get('id'): c for c in load(name).iter('control') if c.get('id')}


def _hint(name, cid):
    """(key, label, top, visible) of the hint `cid` in window `name`."""
    group = _controls(name)[cid]
    (line,) = group.findall('control')
    assert line.get('type') == 'label', cid
    key, label = LABEL.match(line.findtext('label')).groups()
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


def _all_hints():
    """Every LevelHint of the skin's windows: (file, params)."""
    found = []
    for path in layout_files():
        for inc in parse(path).iter('include'):
            if inc.get('content') == 'LevelHint':
                found.append((path.name, {p.get('name'): p.get('value') for p in inc.findall('param')}))
    return found


def test_hint_look():
    """The key in the dimmed blue of a hint, the label muted, one line of small caps; a shadow
    keeps it readable over bright video. Centred across the screen by default, on its bottom
    edge; it fades out, then in."""
    include = next(i for i in parse(ROOT / '1080i' / 'Includes_Base.xml').iter('include')
                   if i.get('name') == 'LevelHint')
    defaults = {p.get('name'): p.get('default') for p in include.findall('param')}
    assert (defaults['top'], defaults['left'], defaults['width'], defaults['align']) == (BOTTOM, '0', '1920', 'center')
    group = with_look(include).find('definition/control')
    assert group.get('type') == 'group'
    # out before in: two hints taking turns in one place never stand on each other; a still
    # effect starts the animation at once, the delayed fade holds 0 until it runs
    anims = {a.get('type'): (a.get('condition'), [(e.get('start'), e.get('end'), e.get('time'), e.get('delay'))
                                                  for e in a.findall('effect')]) for a in group.findall('animation')}
    assert anims == {'Visible': ('$PARAM[animate]', [('100', '100', '150', None), ('0', '100', '150', '150')]),
                     'Hidden': ('$PARAM[animate]', [('100', '0', '150', None)])}
    assert defaults['animate'] == 'true'  # the player's hints fade over the video
    (label,) = group.findall('control')
    assert label.get('type') == 'label'
    assert (label.findtext('width'), label.findtext('align')) == ('$PARAM[width]', '$PARAM[align]')
    assert label.findtext('font') == 'font_caps_small'
    assert label.findtext('textcolor') == 'text_mute'
    assert label.findtext('shadowcolor') == 'bg'
    assert label.findtext('label') == '[UPPERCASE]{} $PARAM[label][/UPPERCASE]'.format(KEY.format('$PARAM[key]'))
    assert not list(include.iter('texture')) and 'cut_btn' not in ET.tostring(include, encoding='unicode')


def test_every_hint_is_a_glyph_in_its_place():
    """Keys are glyphs, no key words; a hint centred across the screen stands on the path line or
    on the player's edges, any other one in a dialog or under a row."""
    hints = _all_hints()
    assert len(hints) >= 25
    for name, params in hints:
        assert params.get('key', '↓') in KEYS, (name, params)
        assert not GLYPHS.search(COLOURED_KEY.sub('', params['label'])), (name, params)
        if params.get('width', '1920') == '1920':
            assert params.get('align', 'center') == 'center', (name, params)
            assert params.get('top', BOTTOM) in (PATH, TOP, BOTTOM), (name, params)
        else:
            assert params.get('align', 'center') in ('left', 'center'), (name, params)


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
    # a variable may hold a part of a hint, its keys coloured
    for var in parse(ROOT / '1080i' / 'Variables.xml').iter('variable'):
        for value in var.iter('value'):
            if GLYPHS.search(value.text or ''):
                assert var.get('name').startswith('Hint'), var.get('name')
                assert not GLYPHS.search(COLOURED_KEY.sub('', value.text)), var.get('name')
        allowed = set()
        for inc in root.iter('include'):
            if inc.get('content') == 'LevelHint':
                allowed |= set(inc.findall('param'))
        for param in root.iter('param'):
            if GLYPHS.search(param.get('value') or ''):
                assert param in allowed and param.get('name') in ('key', 'label'), (path.name, param.get('value'))


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
    for name, params in _all_hints():
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
    """Under the episodes while they have the focus: Up the season tabs, Down cast and crew, OK
    selects; no hint for moving along the row."""
    key, label, top, visible = _hint('DialogVideoInfo.xml', '5190')
    assert key == '↑'
    assert label == '$LOCALIZE[31603]$VAR[HintEpisodeDown]   {} $LOCALIZE[31135]'.format(KEY.format('⏎'))
    assert visible == 'Control.HasFocus(5100)'
    assert _controls('DialogVideoInfo.xml')['5100'].findtext('onup') == '5200'


# window: [(hint id, key, label, visible)], each on the path line, the title left of it
MODAL = '!System.HasActiveModalDialog'
PATH_HINTS = {
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


def test_window_hints_on_the_path_line():
    """A full window shows its way back on the path line, for the focused side: Left from a
    settings page's rows to its categories, from the categories out of the page; Left from the
    library's menu to its titles, from the bar to the menu."""
    for name, hints in PATH_HINTS.items():
        controls = _controls(name)
        assert int(controls['9026'].findtext('width')) <= 780, name
        for cid, key_want, label_want, visible_want in hints:
            key, label, top, visible = _hint(name, cid)
            # not over a dialog on top, the select dialog of the library's filter say: the
            # window keeps its focus under it
            want = MODAL if visible_want == 'true' else '{} + {}'.format(MODAL, visible_want)
            assert [key, label, visible] == [key_want, label_want, want], (name, cid)
            assert top == PATH, (name, cid)
            # a page does not blend over a playing video
            animations = controls[cid].findall('animation')
            assert animations and all(a.get('condition') == '!Player.HasVideo' for a in animations), (name, cid)


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
    """Dialogs have their hint left in the button row (the buttons stand right): Left from an
    add-on's settings to its categories; in the skin's select dialogs Left goes one level up,
    in a group of the library filter to its groups, else onto the library."""
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
    lies over, centred under the panel."""
    controls = _controls('Custom_1170_QuickMenu.xml')
    key, label, top, visible = _hint('Custom_1170_QuickMenu.xml', '1290')
    assert (key, label, visible) == ('↑', '$VAR[HintQuickMenuBack]', 'Control.HasFocus(1210)')
    panel, group = controls['1200'], controls['1290']
    assert group.findtext('left') == panel.findtext('left')
    assert int(top) >= int(panel.findtext('top')) + int(panel.findtext('height'))
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
