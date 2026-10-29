import pytest
import re

from conftest import ROOT, layout_files, parse

VAR = re.compile(r'\$VAR\[([^\],]+)')
ART = re.compile(r'Art\(')


def defined_includes():
    return {el.get('name') for p in layout_files() for el in parse(p).iter('include') if el.get('name')}


def used_includes():
    for p in layout_files():
        for el in parse(p).iter('include'):
            if el.get('name') or el.get('file'):
                continue
            name = el.get('content') or (el.text or '').strip()
            if name:
                yield p.name, name


def test_include_references_resolve():
    defined = defined_includes()
    # content="$PARAM[...]" names an include passed in as a parameter
    assert not [u for u in used_includes() if u[1] not in defined and not u[1].startswith('$PARAM[')]


def test_variable_references_resolve():
    defined = {el.get('name') for f in layout_files() for el in parse(f).iter('variable')}
    used = {(p.name, m) for p in layout_files() for m in VAR.findall(p.read_text())}
    assert not [u for u in used if u[1] not in defined]


def test_artwork_not_tinted():
    bad = []
    for p in layout_files():
        for el in parse(p).iter('control'):
            if el.get('type') != 'image':
                continue
            texture = el.findtext('texture') or ''
            if (el.findtext('description') or '') == 'fanart backdrop':
                continue  # the dimmed background fanart is tinted on purpose (FanartBackdrop)
            if ART.search(texture) and (el.find('colordiffuse') is not None
                                        or 'colordiffuse' in (el.find('texture').attrib if el.find('texture') is not None else {})):
                bad.append((p.name, texture))
    assert not bad


CONDITION_TAGS = ('visible', 'selected', 'enable', 'usealttexture', 'autoscroll', 'start', 'stop', 'reset')


def test_no_var_in_conditions():
    """Kodi cannot parse $VAR[...] inside boolean expressions ("Misplaced [")."""
    bad = []
    for p in layout_files():
        for el in parse(p).iter():
            texts = [el.get('condition') or '']
            if el.tag in CONDITION_TAGS:
                texts.append(el.text or '')
            bad += [(p.name, el.tag, t) for t in texts if '$VAR[' in t]
    assert not bad


PULSING_TYPES = ('button', 'togglebutton', 'radiobutton', 'edit', 'spincontrolex', 'sliderex', 'colorbutton')


def test_focused_controls_do_not_pulse():
    """Kodi pulses the focus texture of every focused button by default, which marks it dirty on
    every frame and keeps the whole screen redrawing (Home idled at ~750% CPU in kodi-dev)."""
    defaults = {el.get('type'): el.findtext('pulseonselect')
                for p in layout_files() for el in parse(p).iter('default')}
    assert {t: defaults.get(t) for t in PULSING_TYPES} == {t: 'false' for t in PULSING_TYPES}


def test_widget_focus_frame_not_clipped():
    """A list clips its items to its own rectangle; the focus glow reaches 24px past the card."""
    home = parse(ROOT / '1080i' / 'Includes_Home.xml')
    row = next(el for el in home.iter('include') if el.get('name') == 'RowBox')
    layout = row.find('.//focusedlayout')
    card = layout.find('control')
    assert card.get('type') == 'group'
    assert int(card.findtext('left')) >= 24 and int(card.findtext('top')) >= 24
    assert int(layout.get('height')) >= int(card.findtext('top')) + 276 + 24 + 14


NETRUNNER = ('Background', 'FanartBackdrop', 'PathLine', 'Kicker', 'GlitchTitle', 'Tag', 'PillButton', 'ProgressLine',
             'RowHeader', 'CutCard', 'TabButton')
REMOVED = ('Box', 'BoxTitle', 'BoxCounter', 'Chip', 'GradientBar', 'RatingMeter')
# files rebuilt in the netrunner look: all of 1080i
MIGRATED = {p.name for p in (ROOT / '1080i').glob('*.xml')}


def include(name):
    for p in layout_files():
        for el in parse(p).iter('include'):
            if el.get('name') == name:
                return el
    return None




def test_textures_exist():
    from PIL import Image
    ui = ROOT / 'media' / 'ui'
    for name in ('cut.png', 'cut_fill.png', 'cut_btn.png', 'cut_btn_fill.png', 'cut_glow.png', 'petrol_glow.png',
                 'fade_b.png', 'fade_t.png', 'tick.png', 'seek_head.png', 'seek_track.png'):
        assert (ui / name).is_file(), name
    assert Image.open(ui / 'cut.png').size == (64, 64)
    assert Image.open(ui / 'petrol_glow.png').size == (1920, 1080)
    bottom = Image.open(ui / 'fade_b.png')
    assert bottom.size == (4, 256)
    assert bottom.getpixel((0, 0))[3] == 0 and bottom.getpixel((0, 255))[3] == 255  # opaque at the bottom








def test_osd_buttons_are_pills():
    osd = parse(ROOT / '1080i' / 'VideoOSD.xml')
    buttons = [i.get('content') for i in osd.iter('include') if i.get('content') in ('Button', 'PillButton')]
    assert buttons and set(buttons) == {'PillButton'}


def params(inc):
    return {p.get('name'): p.get('default') for p in inc.findall('param')}


def test_netrunner_includes_exist():
    assert [n for n in NETRUNNER if include(n) is None] == []


def test_migrated_files_have_no_framed_labels():
    for name in MIGRATED:
        path = ROOT / '1080i' / name
        used = {i.get('content') or (i.text or '').strip() for i in parse(path).iter('include') if not i.get('name')}
        assert not used & set(REMOVED), (name, used & set(REMOVED))
        assert '┤' not in path.read_text() and '├' not in path.read_text(), name


def test_pill_button_fill_only_on_focus():
    """Only the focused button is filled; an unfocused primary button is an accent outline."""
    button = include('PillButton').find('.//control')
    focus, nofocus = button.find('texturefocus'), button.find('texturenofocus')
    assert focus.text == 'ui/cut_btn_fill.png' and focus.get('colordiffuse') == 'focus'
    assert nofocus.text == 'ui/cut_btn.png' and nofocus.get('colordiffuse') == '$PARAM[color]'
    assert button.findtext('textcolor') == '$PARAM[textcolor]'
    assert button.findtext('focusedcolor') == 'focus_text'
    assert params(include('PillButton'))['color'] == 'border_dim'
    for path in layout_files():
        text = path.read_text()
        assert 'name="nofocus"' not in text, path.name  # the old always-filled primary button


def test_glitch_title_layers_match():
    labels = [c for c in include('GlitchTitle').iter('control') if c.get('type') == 'label']
    assert len(labels) == 3
    keys = ('width', 'height', 'font', 'scroll', 'wrapmultiline', 'label', 'align')
    assert len({tuple(l.findtext(k) for k in keys) for l in labels}) == 1
    colors = [l.findtext('textcolor') for l in labels]
    assert colors[:2] == ['glitch_a', 'glitch_b'] and colors[2] == 'text'
    lefts = [l.findtext('left') for l in labels]
    assert lefts == ['-2', '2', '0']


def test_background_without_fanart():
    """Without fanart the page is the dark background with the petrol glow, never a hole."""
    images = [c for c in include('Background').iter('control') if c.get('type') == 'image']
    textures = [(i.findtext('texture'), i.find('texture').get('colordiffuse'), i.find('visible')) for i in images]
    assert ('ui/white.png', 'bg', None) in textures
    assert ('ui/petrol_glow.png', 'petrol', None) in textures
    fanart = include('FanartBackdrop').find('.//control')
    assert fanart.findtext('visible') == '!String.IsEmpty($PARAM[art])'
    assert fanart.find('texture').get('fallback', '') == ''
    assert fanart.find('texture').get('colordiffuse') == 'fanart'
    assert fanart.findtext('description') == 'fanart backdrop'


def test_info_page_fanart_backdrop():
    """The info page puts the item's fanart behind the page through FanartBackdrop, which hides
    the image while the art is empty (Control.IsVisible cannot see into dialogs over JSON-RPC)."""
    info = parse(ROOT / '1080i' / 'DialogVideoInfo.xml')
    arts = [p.get('value') for i in info.iter('include') if i.get('content') == 'FanartBackdrop'
            for p in i.findall('param') if p.get('name') == 'art']
    assert arts and all('Art(fanart)' in a for a in arts)


def test_seekbar_layers():
    """Thin line with buffer, position and chapter marks."""
    bar = include('PlayerBar')
    controls = [c for c in bar.iter('control') if c.get('type') in ('progress', 'ranges')]
    by_info = {c.findtext('info'): c for c in controls}
    assert by_info['Player.ProgressCache'].get('type') == 'progress'
    assert by_info['Player.SeekBar'].get('type') in ('progress', 'ranges')
    assert by_info['Player.Chapters'].get('type') == 'ranges'
    for info in ('Player.ProgressCache', 'Player.SeekBar'):  # the head is a taller layer of its own
        assert min(int(c.findtext('height')) for c in controls if c.findtext('info') == info) <= 6, info


def pill_buttons(path):
    for inc in parse(path).iter('include'):
        if inc.get('content') == 'PillButton':
            args = {p.get('name'): p.get('value') for p in inc.findall('param')}
            args['onclicks'] = [args.get('onclick', '')] + [o.text for o in inc.findall('onclick')]
            yield args


def test_osd_buttons():
    buttons = list(pill_buttons(ROOT / '1080i' / 'VideoOSD.xml'))
    clicks = {c: b for b in buttons for c in b['onclicks'] if c}
    for action in ('PlayerControl(Previous)', 'PlayerControl(Play)', 'PlayerControl(Next)',
                   'PlayerControl(Stop)'):
        assert action in clicks, action
    next_episode = next(b for b in buttons if '31137' in b['label'])
    assert 'Playlist.HasNext' in next_episode.get('visible', '')
    assert any(b['label'] == '…' for b in buttons)


def test_settings_dialog_has_no_category_template():
    """With a category button template (id 10) Kodi builds category tabs and gives up when the
    window has no category list (id 3): the OSD audio/subtitle/video settings came up empty."""
    templates = include('SettingsTemplates')
    assert not [c for c in templates.iter('control') if c.get('id') == '10']
    for path in layout_files():
        text = path.read_text()
        if 'SettingsCategoryTemplate' in text and path.name != 'Includes_Dialogs.xml':
            assert 'id="3"' in text, path.name


def test_seek_bubble_only_while_seeking():
    bubbles = include('SeekBubbles').find('control')
    assert 'Player.Seeking' in bubbles.findtext('visible')


OLD_TEXTURES = ('box.png', 'box_fill.png', 'box_small.png', 'box_small_fill.png', 'frame', 'segment', 'glow.png')


def test_compat_includes_gone():
    assert not (ROOT / '1080i' / 'Includes_Compat.xml').exists()
    assert [n for n in REMOVED if include(n) is not None] == []


def test_old_textures_gone():
    ui = ROOT / 'media' / 'ui'
    assert not [f.name for f in ui.iterdir() if f.name.startswith(OLD_TEXTURES)]
    for path in layout_files():
        text = path.read_text()
        assert not re.findall(r'ui/(?:box|frame|segment)\w*\.png|ui/glow\.png', text), path.name


def layout(list_include, tag):
    return list_include.find('.//' + tag)


def test_select_marks_current_value():
    """The current value of a list (DialogSelect, settings dropdowns) is an accent row with
    a ◢ in front, whether or not the cursor is on it."""
    lst = include('DialogList')
    for tag in ('itemlayout', 'focusedlayout'):
        marked = [c for c in layout(lst, tag).iter('control')
                  if c.get('type') == 'label' and '◢' in (c.findtext('label') or '')]
        assert marked, tag
        for c in marked:
            visible = c.findtext('visible') or ''
            assert 'ListItem.IsSelected' in visible and '!ListItem.IsSelected' not in visible, (tag, visible)
    selected = [c for c in layout(lst, 'itemlayout').iter('control') if c.get('type') == 'label'
                and (c.findtext('visible') or '').startswith('ListItem.IsSelected')]
    assert selected and all(c.findtext('textcolor') == 'accent' for c in selected)


def test_list_labels_keep_colour_when_selected():
    """Kodi draws a label of a selected item (ListItem.IsSelected) in its selectedcolor, which
    defaults to nothing visible: without it the current value of a dropdown is a blank row."""
    for path in layout_files():
        for lay in [e for e in parse(path).iter() if e.tag in ('itemlayout', 'focusedlayout')]:
            for c in lay.iter('control'):
                if c.get('type') == 'label' and c.find('textcolor') is not None:
                    assert c.findtext('selectedcolor') == c.findtext('textcolor'), (path.name, c.findtext('label'))


def test_dialog_frame_is_opaque():
    """The settings behind a dialog must not show through its panel."""
    first = include('DialogFrame').find('control')
    assert first.find('texture').get('colordiffuse') == 'bg'


def test_toggle_settings_use_check():
    """Kodi's toggle settings (template 8) and the skin's own share one look."""
    template = next(c for c in include('SettingsTemplates').iter('control') if c.get('id') == '8')
    assert template.findtext('include') == 'SettingsToggleLook'
    radio = include('SettingsToggleLook')
    assert radio.findtext('textureradioonnofocus') == 'ui/check_on.png'
    assert radio.findtext('textureradiooffnofocus') == 'ui/check_off.png'
    assert (ROOT / 'media' / 'ui' / 'check_on.png').is_file()


def test_dialog_heading_above_content():
    heading = include('DialogHeading')
    assert [c for c in heading.iter('control') if c.get('id') == '$PARAM[id]'][0].get('type') == 'label'
    assert int(heading.find('.//control').findtext('top') or 0) >= 0  # inside the frame, not on its line


def test_tab_focus_differs_from_active():
    """A menu or tab entry that is focused looks different from the active (shown) one: the
    focus draws a line, the active mark is only the pink ◢ and leaves the label colour alone."""
    tab = include('TabButton').find('.//control')
    assert tab.find('texturefocus').text and tab.find('alttexturefocus').text
    assert not tab.find('texturenofocus').text and not tab.find('alttexturenofocus').text
    assert '[COLOR accent]' not in tab.findtext('altlabel')


def test_hero_titles_fit_long_names():
    """A hero title takes about 30 characters (Everything Everywhere All at Once): width per
    pixel of font size of at least 16."""
    sizes = {f.findtext('name'): int(f.findtext('size')) for f in parse(ROOT / '1080i' / 'Font.xml').iter('font')}
    hero = include('HeroBody')
    defaults = {p.get('name'): p.get('default') for p in hero.findall('param')}
    for path in layout_files():
        for call in parse(path).iter('include'):
            if call.get('content') != 'HeroBody':
                continue
            args = dict(defaults, **{p.get('name'): p.get('value') for p in call.findall('param')})
            assert int(args['titlewidth']) / sizes[args['titlefont']] >= 16, (path.name, args['titlewidth'], args['titlefont'])



def test_spotlight_rests_behind_dialogs():
    """The spotlight does not rotate (and load fanart) while a dialog such as the info page covers
    Home."""
    for path in layout_files():
        for c in parse(path).iter('control'):
            auto = c.find('autoscroll')
            if auto is not None and c.get('type') != 'textbox':
                assert 'Window.IsActive(movieinformation)' in auto.text and 'System.HasActiveModalDialog' in auto.text, path.name


def test_movie_hero_kicker_names_genre():
    call = next(c for c in include('MovieHero').iter('include') if c.get('content') == 'HeroBody')
    kicker = next(p.get('value') for p in call.findall('param') if p.get('name') == 'kicker')
    assert 'ListItem.Genre' in kicker


def test_row_title_leaves_heading_room():
    """The focused title on the right of a row header starts right of the heading."""
    row = include('RowBox')
    title = next(c for c in row.iter('control') if c.get('type') == 'label' and 'ListItem.Label' in (c.findtext('label') or ''))
    assert int(title.findtext('left')) >= 560


def test_no_dead_definitions():
    """Every variable and include is used, every texture in media/ui is referenced."""
    texts = '\n'.join(p.read_text(encoding='utf-8') for p in layout_files())
    for path in layout_files():
        for el in parse(path).iter():
            name = el.get('name')
            if el.tag == 'variable':
                assert re.search(r'\$VAR\[' + name + r'[\],]', texts), name
            elif el.tag == 'include' and name and el.get('content') is None and path.name != 'Includes.xml':
                # also passed by name to an include that has content="$PARAM[...]"
                assert texts.count('>' + name + '<') + texts.count('content="' + name + '"') + \
                    texts.count('value="' + name + '"') >= 1, name
    for png in (ROOT / 'media' / 'ui').glob('*.png'):
        assert 'ui/' + png.name in texts or png.name in texts, png.name


def test_manual_spotlight_move_resets_timer():
    """Moving the spotlight by hand starts a short hold timer; while it runs the autoscroll
    condition is false, which resets Kodi's autoscroll delay, so the next automatic change comes
    a full interval later."""
    timers = parse(ROOT / '1080i' / 'Timers.xml')
    timer = next(t for t in timers.iter('timer') if t.findtext('name') == 'nc_spot_hold')
    assert 'Skin.TimerElapsedSecs(nc_spot_hold)' in timer.findtext('stop')
    auto = include('SpotlightAutoscroll').find('.//autoscroll').text
    assert '!Skin.TimerIsRunning(nc_spot_hold)' in auto
    text = (ROOT / '1080i' / 'Includes_Home.xml').read_text(encoding='utf-8')
    for group in [c for c in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('control')
                  if any('Control.Move(900' in (e.text or '') for e in c.findall('onleft') + c.findall('onright'))]:
        actions = [e.text for e in group.findall('onleft') + group.findall('onright')]
        assert actions.count('Skin.TimerStart(nc_spot_hold)') == 2, group.get('id')


def test_conditional_fades_name_start():
    """A conditional fade without start reverses to alpha 0 once its condition turns false again
    (cards of a row vanished after the focus left the row)."""
    for path in layout_files():
        for anim in parse(path).iter('animation'):
            if anim.get('effect') == 'fade' and (anim.text or '').strip() == 'Conditional':
                assert anim.get('start') is not None, (path.name, anim.attrib)


def test_button_rows_fit_buttons():
    """A grouplist clips its children: rows of 54 px buttons must be at least 54 high, or the
    bottom line of each button is cut off."""
    for path in layout_files():
        for row in parse(path).iter('control'):
            if row.get('type') != 'grouplist' or row.findtext('orientation') != 'horizontal':
                continue
            if any(c.get('content') in ('PillButton', 'Button') for c in row.findall('include')):
                assert int(row.findtext('height')) >= 54, (path.name, row.get('id'))


def _menu_tab(tab_id):
    menu = include('MainMenu')
    call = next(c for c in menu.iter('include') if c.get('content') == 'MenuButton'
                and any(p.get('value') == tab_id for p in c.findall('param')))
    return {p.get('name'): p.get('value') for p in call.findall('param')}


def test_search_is_a_page():
    """Search switches the page on focus like the other menu entries."""
    for tab_id, page, target in (('9104', 'search', '9750'),):
        tab = _menu_tab(tab_id)
        assert tab['onfocus'] == 'SetProperty(nc.page,{},home)'.format(page)
        assert page in tab['active'] and tab['onclick'] == 'SetFocus({})'.format(target)
    home = (ROOT / '1080i' / 'Home.xml').read_text(encoding='utf-8')
    for rows in ('9710',):
        assert 'value="{}"'.format(rows) in home
    assert 'NotifyAll(nightcity,home)' in home  # genres and search history


def test_search_page_rows():
    """Library movies, shows and episodes, then TMDb movies and shows, from the script's paths;
    each row has its own loader so it refills when the term changes."""
    rows = include('SearchWidgets')
    calls = [{p.get('name'): p.get('value') for p in c.findall('param')}
             for c in rows.iter('include') if c.get('content') == 'RowBox']
    kinds = ['movies', 'tvshows', 'episodes', 'tmdb_movies', 'tmdb_tvshows']
    paths = ['$VAR[SearchPath_{}]'.format(k) for k in kinds]
    assert [c['content1'] for c in calls] == paths
    loaders = [c for c in include('SearchWidgetLoaders').iter('include') if c.get('content') == 'WidgetLoader']
    assert [{p.get('name'): p.get('value') for p in c.findall('param')}['content1'] for c in loaders] == paths
    variables = {v.get('name'): v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable')}
    for kind in kinds:
        # only on the search page: TMDb runs a plugin for every load
        value = variables['SearchPath_' + kind].find('value')
        assert value.get('condition').startswith('String.IsEqual(Window(Home).Property(nc.page),search)')
        assert value.text == '$INFO[Window(Home).Property(nc.search.{})]'.format(kind)
    assert len({c['loader'] for c in calls}) == 5 and all(c['loader'] != c['id'] for c in calls)
    field = next(c for c in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('control') if c.get('id') == '9750')
    assert 'search' in field.findtext('onclick')


def test_click_routing_shows_need_dbid():
    """Only library shows go to their next episode; a TMDb show has no DBID and opens its info."""
    clicks = include('ClickRouting').findall('onclick')
    show = next(c for c in clicks if 'next_episode' in c.text)
    assert '!String.IsEmpty(ListItem.DBID)' in show.get('condition')
    info = next(c for c in clicks if c.text == 'Action(Info)')
    assert 'String.IsEmpty(ListItem.DBID)' in info.get('condition')


def test_no_space_aligned_columns():
    """Rajdhani is proportional: columns padded with runs of spaces do not line up."""
    for p in layout_files():
        for el in parse(p).iter('label'):
            assert not re.search(r'\S {3,}\[/COLOR\]', el.text or ''), (p.name, el.text)


def test_system_facts_in_columns():
    """The system page holds what the power page showed: memory instead of free disk space
    (System.FreeSpace), and the CPU temperature where Kodi knows it."""
    for hero, keys in (('SystemHero', ['kodi', 'ip', 'memory', 'uptime', 'temp']),):
        calls = [c for c in include(hero).iter('include') if c.get('content') == 'FactLine']
        assert [{p.get('name'): p.get('value') for p in c.findall('param')}['key'] for c in calls] == keys


def test_main_menu_entries_are_buttons():
    """The top menu: the focused entry is a filled accent button with dark text, the shown page
    an accent outline; no underline, no ◢."""
    calls = [c for c in include('MainMenu').iter('include') if c.get('content') in ('TabButton', 'MenuButton')]
    assert calls and all(c.get('content') == 'MenuButton' for c in calls)
    button = include('MenuButton').find('.//control')
    assert button.find('texturefocus').text == 'ui/cut_btn_fill.png' and button.find('texturefocus').get('colordiffuse') == 'accent'
    assert button.find('alttexturefocus').text == 'ui/cut_btn_fill.png'
    assert button.find('alttexturenofocus').text == 'ui/cut_btn.png' and button.find('alttexturenofocus').get('colordiffuse') == 'accent'
    assert not button.find('texturenofocus').text
    assert button.findtext('focusedcolor') == 'focus_text'
    assert '◢' not in button.findtext('altlabel') and 'tab_line' not in ''.join(button.itertext())


def test_main_menu_focus_text_readable():
    """No fixed colour in the labels: the focus text colour must win on the accent fill."""
    button = include('MenuButton').find('.//control')
    assert '[COLOR' not in button.findtext('label') and '[COLOR' not in button.findtext('altlabel')


def test_search_page_starts_tmdb_rows_one_after_the_other():
    """Entering the search page loads the tv search two seconds after the movie search: two TMDb
    Helper searches starting at once crash Kodi."""
    timers = parse(ROOT / '1080i' / 'Timers.xml')
    timer = next(t for t in timers.iter('timer') if t.findtext('name') == 'nc_search_page')
    page = 'String.IsEqual(Window(Home).Property(nc.page),search)'
    assert timer.findtext('start') == page and timer.find('start').get('reset') == 'true'
    assert timer.findtext('stop') == '!' + page
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable')
               if v.get('name') == 'SearchPath_tmdb_tvshows')
    assert [v.get('condition') for v in var.iter('value')] == [
        page + ' + Skin.TimerIsRunning(nc_search_page) + Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_search_page),2)']


def test_row_loads_after_its_loader():
    """A row's list loads once its loader has items, not together with it: two plugin loads of
    the same path starting at once start two Python interpreters at once, which crashes Kodi.
    A row that is its own loader loads right away."""
    row = include('RowBox')
    lst = next(c for c in row.iter('control') if c.get('type') == 'list')
    # and once the loader holds this row's items, not those of a search before (test_stale_lists.py)
    assert lst.findtext('visible') == '!$PARAM[wait] | [Integer.IsGreater(Container($PARAM[loader]).NumItems,0) + [$PARAM[fresh]]]'
    assert next(p for p in row.findall('param') if p.get('name') == 'wait').get('default') == 'false'
    for name in ('Includes_Home.xml',):
        for call in parse(ROOT / '1080i' / name).iter('include'):
            if call.get('content') != 'RowBox':
                continue
            args = {p.get('name'): p.get('value') for p in call.findall('param')}
            assert args.get('wait', 'false') == ('true' if args['loader'] != args['id'] else 'false'), args['id']


def settings_template(control_id):
    return next(c for c in include('SettingsTemplates').iter('control') if c.get('id') == control_id)


def test_toggle_box_inside_the_row():
    """Kodi puts the toggle box at the row's left + radioposx when it is set: a negative value
    drew it left of the row, off the panel, and the toggles looked like plain buttons."""
    radio = include('SettingsToggleLook')
    assert float(radio.findtext('radioposx') or 0) >= 0
    assert int(radio.findtext('radiowidth')) >= 24


def ET_tostring(el):
    import xml.etree.ElementTree as ET
    return ET.tostring(el, encoding='unicode')


def test_spin_settings_show_minus_and_plus():
    """A setting with a value range (System > Display > Delay after change of refresh rate)
    shows - and + next to its value, focused or not."""
    spin = settings_template('9')
    assert int(spin.findtext('spinwidth')) >= 20 and int(spin.findtext('spinheight')) >= 20
    for tag in ('texturedown', 'texturedownfocus', 'textureup', 'textureupfocus'):
        texture = spin.findtext(tag)
        assert texture, tag
        assert (ROOT / 'media' / texture).is_file(), texture


def test_active_slider_nib_is_light():
    """Kodi draws the focus nib only while the slider is being moved, on the cyan focus row and
    its dark bar: a dark nib vanished there, pink stood alone in the settings. Light text colour."""
    slider = settings_template('13')
    assert slider.find('textureslidernibfocus').get('colordiffuse') == 'text'


def test_focused_spin_row_shows_both_signs():
    """On the cyan focus row Kodi draws the sign that is not selected with its normal texture,
    the same as on a dark row. It is a light sign with a dark rim, so it shows on both, without a
    plate. The selected one is a dark chip with the sign cut out (cyan shows through), in the
    dark ink of the focus row, not pink."""
    from PIL import Image
    spin = settings_template('9')
    for sign in ('minus', 'plus'):
        tag = 'texturedown' if sign == 'minus' else 'textureup'
        normal = spin.find(tag)
        focus = spin.find(tag + 'focus')
        assert focus.text == 'ui/spin_{}_focus.png'.format(sign)
        assert focus.get('colordiffuse') == 'focus_text'
        assert normal.get('colordiffuse') == 'text_dim'
        mark = Image.open(ROOT / 'media' / normal.text).convert('RGBA')
        assert mark.getpixel((3, 3))[3] == 0  # no plate
        mid = mark.width // 2
        assert min(mark.getpixel((mid, mid))[:3]) > 200 and mark.getpixel((mid, mid))[3] > 200
        rim = [p for p in mark.getdata() if p[3] > 200 and max(p[:3]) < 60]
        assert rim, sign
        box = Image.open(ROOT / 'media' / focus.text).convert('RGBA')
        assert box.getpixel((3, 3))[3] > 200 and box.getpixel((mid, mid))[3] < 60
        assert box.getpixel((1, 1))[3] == 0  # air to the other sign


def test_settings_rows_are_not_pink():
    for cid in ('7', '8', '9', '12', '13'):
        assert 'accent2' not in ET_tostring(settings_template(cid)), cid


def test_nothing_overlaps_a_dialog_heading():
    """The heading label of DialogHeading ends at 82 px. The path line of the file browser
    (install from zip) sat at 64 and nearly touched the heading."""
    import xml.etree.ElementTree as ET
    for path in (ROOT / '1080i').glob('*.xml'):
        for group in ET.parse(path).getroot().iter('control'):
            kids = list(group)
            heading = [k for k in kids if k.tag == 'include' and k.get('content') == 'DialogHeading']
            if not heading:
                continue
            width = int(next((p.get('value') for p in heading[0].findall('param') if p.get('name') == 'width'), 920))
            for k in kids:
                if k.tag == 'control':
                    left, top = k.findtext('left'), k.findtext('top')
                elif k.tag == 'include' and k.get('content') != 'DialogHeading':
                    params = {p.get('name'): p.get('value') for p in k.findall('param')}
                    left, top = params.get('left'), params.get('top')
                else:
                    continue
                if not (top or '').isdigit() or ((left or '0').isdigit() and int(left or 0) >= 40 + width):
                    continue
                assert int(top) >= 84, (path.name, k.get('id') or k.get('content'), top)


def test_file_browser_hides_disabled_buttons():
    """Kodi disables OK, new folder and flip when they do not apply (install from zip): a
    disabled pill showed as an empty frame."""
    import xml.etree.ElementTree as ET
    root = ET.parse(ROOT / '1080i' / 'FileBrowser.xml').getroot()
    buttons = {next(p.get('value') for p in i.findall('param') if p.get('name') == 'id'): i
               for i in root.iter('include') if i.get('content') == 'Button'}
    for bid in ('413', '415', '416'):
        visible = next((p.get('value') for p in buttons[bid].findall('param') if p.get('name') == 'visible'), None)
        assert visible == 'Control.IsEnabled({})'.format(bid), bid


def test_search_hint_dark_on_focus():
    """The hint in the empty search field takes the focus text colour like every other focused
    label; only without focus it is muted."""
    import xml.etree.ElementTree as ET
    var = next(v for v in ET.parse(ROOT / '1080i' / 'Variables.xml').getroot().iter('variable')
               if v.get('name') == 'SearchFieldLabel')
    muted = [v for v in var.findall('value') if 'text_mute' in v.text]
    assert muted and all('!Control.HasFocus(9750)' in (v.get('condition') or '') for v in muted)
    assert var.findall('value')[-1].text == '$LOCALIZE[31141]'


def test_keyboard_field_plain_with_inset_text():
    """No > prompt in front of the typed text: with a label Kodi right-aligns the text, so the
    cursor hung on the right edge under the cut corner. Without it the text starts left, inset
    by textoffsetx on both sides."""
    import xml.etree.ElementTree as ET
    field = next(c for c in ET.parse(ROOT / '1080i' / 'DialogKeyboard.xml').getroot().iter('control')
                 if c.get('id') == '312')
    assert not (field.findtext('label') or '').strip()
    assert int(field.findtext('textoffsetx') or 0) >= 20


def test_keyboard_keys_fit_wide_letters():
    """A 68 px key with 24 px text offset on each side left 20 px for the letter: w and m showed
    as an ellipsis."""
    import xml.etree.ElementTree as ET
    from navigation import load
    keys = [c for c in load('DialogKeyboard.xml').iter('control')
            if c.get('type') == 'button' and c.findtext('width') == '68']
    assert keys
    for key in keys:
        assert int(key.findtext('width')) - 2 * int(key.findtext('textoffsetx')) >= 44, key.get('id')


def spotlight_autoscrolls():
    return {(i.get('condition') or ''): next(p.get('value') for p in i.findall('param') if p.get('name') == 'time')
            for i in include('SpotlightList').iter('include') if i.get('content') == 'SpotlightAutoscroll'}


def test_spotlight_interval_is_a_skin_setting():
    """15 s by default; the home pages settings offer 10, 30 and 60 s and still. Kodi reads the
    autoscroll time once, so each choice is a conditional include (Kodi reloads Home when the
    condition changes). Per list: the skin string in `interval`, `follow` when empty means home's."""
    autos = spotlight_autoscrolls()
    times = {}
    for cond, time in autos.items():
        for value in ('10', '30', '60'):
            if cond.startswith('String.IsEqual(Skin.String($PARAM[interval]),{})'.format(value)):
                times[value] = time
    assert times == {'10': '10000', '30': '30000', '60': '60000'}
    default = [t for c, t in autos.items() if c.startswith('![')]
    assert default == ['15000']
    assert 'String.IsEqual(Skin.String($PARAM[interval]),off)' in [c for c in autos if c.startswith('![')][0]
    defn = include('SpotlightAutoscroll').find('.//autoscroll')
    assert defn.get('time') == '$PARAM[time]'


def test_spotlight_preloads_next_three():
    """The spotlight list holds the focused item and the next three in view (focus at the left),
    each with the fanart, poster and logo the hero shows, so a change finds them loaded."""
    lst = include('SpotlightList').find('.//control')
    assert lst.findtext('focusposition') == '0'
    item = lst.find('itemlayout')
    assert int(lst.findtext('width')) == 4 * int(item.get('width'))
    for layout in (item, lst.find('focusedlayout')):
        art = [c.findtext('texture') for c in layout.iter('control') if c.get('type') == 'image']
        assert art == ['$INFO[ListItem.Art(fanart)]', '$INFO[ListItem.Art(poster)]', '$INFO[ListItem.Art(clearlogo)]']


def test_search_field_skips_the_recent_terms_from_above():
    """DESIGN.md: a selector is skipped from above. Down from the search field lands on the
    result rows once they show; the recent terms above them are reached with Up from there.
    Before a search (no rows) Down reaches the terms."""
    field = next(c for c in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('control') if c.get('id') == '9750')
    rows = ' | '.join('Control.IsVisible({})'.format(g) for g in range(9711, 9716))
    assert [(d.get('condition'), d.text) for d in field.findall('ondown')] == [
        ('[{}]'.format(rows), '9710'),
        ('!String.IsEmpty(Window(Home).Property(nc.search.recent.1))', '9770'),
        (None, '9710'),
    ]
