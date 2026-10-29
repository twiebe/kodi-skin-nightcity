"""Quick menu (Custom_1170_QuickMenu.xml): a small panel that slides in at the top right over
whatever is on screen, with the clock, the weather, the power commands and links to the settings
and the system page. Kodi's power menu (shutdownmenu: the S key, power and sleep keys) leads
there, so does a long press on Home (the skin's keymap) and the icon next to the clock in the
top line of Home. It replaces the power page of Home."""
import xml.etree.ElementTree as ET

from conftest import ROOT, parse
from navigation import load

WINDOW = 'Custom_1170_QuickMenu.xml'
POWER = [('Powerdown', 'System.CanPowerDown'), ('Reboot', 'System.CanReboot'),
         ('Suspend', 'System.CanSuspend'), ('RestartApp', 'System.Platform.Windows | System.Platform.Linux'),
         ('Quit', None)]


def controls(root):
    return {c.get('id'): c for c in root.iter('control') if c.get('id')}


def actions(el, tag='onclick'):
    return [(a.get('condition') or '', a.text) for a in el.findall(tag)]


def test_window_is_a_dialog_with_focus_on_power_off():
    root = parse(ROOT / '1080i' / WINDOW)
    assert (root.get('type'), root.get('id')) == ('dialog', '1170')
    assert root.findtext('defaultcontrol') == '1220'
    assert root.find('defaultcontrol').get('always') == 'true'


def test_opening_starts_no_script():
    """Two Python interpreters starting at once can crash Kodi: the menu runs none at all."""
    assert 'RunScript' not in (ROOT / '1080i' / WINDOW).read_text(encoding='utf-8')


def test_slides_in_from_the_top_right():
    root = load(WINDOW)
    panel = controls(root)['1200']
    assert int(panel.findtext('left')) + int(panel.findtext('width')) == 1920 - 48
    assert panel.findtext('top') == '96'
    opens = [a for a in panel.iter('animation') if (a.get('type') or a.text) == 'WindowOpen']
    assert {a.get('effect') for a in opens} == {'slide', 'fade'}
    slide = next(a for a in opens if a.get('effect') == 'slide')
    x, y = (int(v) for v in slide.get('start').split(','))
    assert x > 0 and y < 0  # from up and right


def test_power_tiles_act_at_once_or_say_why_not():
    """No "are you sure" and no script: each tile runs its builtin where the device can do it,
    else Kodi notes that it cannot. Tiles the device cannot do are dimmed (property can)."""
    items = list(controls(load(WINDOW))['1220'].iter('item'))
    by_command = {}
    for item in items:
        for condition, action in actions(item):
            by_command.setdefault(action.split('(')[0], (item, condition))
    for command, condition in POWER:
        item, cond = by_command[command]
        if condition is None:
            assert cond == '' and item.findtext("property[@name='can']") == '1'
        else:
            assert cond == condition
            assert ('!' + condition if '|' not in condition else '![' + condition + ']',
                    'Notification($LOCALIZE[31089],$LOCALIZE[31154])') in actions(item)
            assert item.findtext("property[@name='can']") == '$VAR[QuickCan{}]'.format(command)
    assert not [i for i in items if i.find('visible') is not None]  # Kodi clicks by position


def test_shutdown_timer_tile_sets_and_cancels():
    items = list(controls(load(WINDOW))['1220'].iter('item'))
    timer = next(i for i in items if any('AlarmClock' in a for _, a in actions(i)))
    assert actions(timer) == [('!System.HasAlarm(shutdowntimer)', 'AlarmClock(shutdowntimer,Shutdown())'),
                              ('System.HasAlarm(shutdowntimer)', 'CancelAlarm(shutdowntimer)')]
    assert len(items) == 6


def test_weather_or_how_to_get_it():
    """With a weather add-on: temperature, conditions and place, OK opens Kodi's weather. Without
    one the tile says so and OK opens the weather settings."""
    weather = controls(load(WINDOW))['1210']
    # Kodi opens no window while a modal dialog is open
    # on Home the focus goes to the icon first: Back from the weather lands there, menu shown
    assert actions(weather) == [('', 'Dialog.Close(1170,true)'), ('!Window.IsActive(1170)', 'SetFocus(9109)'),
                                ('Weather.IsFetched', 'ActivateWindow(weather)'),
                                ('!Weather.IsFetched', 'ActivateWindow(servicesettings,weather)')]
    text = ET.tostring(load(WINDOW), encoding='unicode')
    for label in ('Weather.Temperature', 'Weather.Conditions', 'Weather.Location', '$LOCALIZE[31321]'):
        assert label in text


def test_links_to_settings_and_files():
    """Static items, so more links (later the user's own) are one item more. One settings link:
    the settings page of Home (nc.page system), which holds the machine facts and Kodi's settings
    groups; Kodi's own settings window and a system page beside it were one too many."""
    links = controls(load(WINDOW))['1230']
    items = links.findall('content/item')
    clicks = [[a for _, a in actions(i)] for i in items]
    # through the Home key window: it closes an info page, the OSD or a TMDb chain first, the
    # link alone would open its window under a dialog
    assert clicks == [['Dialog.Close(1170,true)', 'SetProperty(nc.go,{},home)'.format(go), 'ActivateWindow(1160)']
                      for go in ('system', 'files')]
    assert (items[0].findtext('label'), items[0].findtext('icon')) == ('$LOCALIZE[5]', 'ui/qm_settings.png')
    assert (items[1].findtext('label'), items[1].findtext('icon')) == ('$LOCALIZE[744]', 'ui/qm_files.png')
    assert (ROOT / 'media' / 'ui' / 'qm_files.png').exists()
    # the links fill the row
    assert int(links.findtext('width')) == 192 * len(items)


def test_rows_lead_into_each_other():
    c = controls(load(WINDOW))
    assert c['1210'].findtext('ondown') == '1220'
    assert c['1220'].findtext('onup') == '1210' and c['1220'].findtext('ondown') == '1230'
    assert c['1230'].findtext('onup') == '1220'


def test_up_from_the_top_goes_to_the_hamburger():
    """Up on the top row leaves the menu (DESIGN.md), onto the icon it opens from when Home is
    behind it; over another window it just closes."""
    weather = controls(load(WINDOW))['1210']
    assert actions(weather, 'onup') == [('', 'Dialog.Close(1170,true)'), ('Window.IsActive(home)', 'SetFocus(9109)')]


def test_kodis_power_menu_leads_here():
    """Like Arctic Fuse: the power menu closes at once and opens the quick menu, or closes it when
    it is open, so the same key opens and closes it."""
    root = parse(ROOT / '1080i' / 'DialogButtonMenu.xml')
    assert actions(root, 'onload') == [('', 'Close'), ('!Window.IsActive(1170)', 'ActivateWindow(1170)'),
                                       ('Window.IsActive(1170)', 'Dialog.Close(1170)')]
    assert not list(root.iter('control'))


def test_icon_next_to_the_clock_shows_it():
    """Focus applies, OK goes (DESIGN.md): with the cursor on the icon the menu shows on Home,
    Down or OK go into it, Left and Right leave it. A panel of Home, not the dialog: a modal
    dialog would take the focus from the icon."""
    home = controls(load('Home.xml'))
    anchor = home['9109']
    assert actions(anchor) == [('', 'SetFocus(1210)')]
    assert anchor.findtext('ondown') == '1210'
    assert home['9100'].findtext('onright') == '9109'
    row = home['9190']
    assert row.get('type') == 'grouplist' and row.findtext('align') == 'right'
    assert row.findall('control')[0].find('control').get('id') == '9109'
    panel = home['9180']
    assert panel.findtext('visible') == 'Control.HasFocus(9109) | ControlGroup(9180).HasFocus'
    # inside the menu the icon stays marked in the accent colour: Up and Back lead there
    assert anchor.findtext('selected') == 'ControlGroup(9180).HasFocus'
    assert anchor.find('textureradioonnofocus').get('colordiffuse') == 'accent'


def test_same_menu_on_home_and_as_dialog():
    """One body (QuickMenuBody) for both: the panel of Home and the dialog that the held Home
    key, the S key and the power menu open over any window."""
    def body(group):
        return [(c.tag, c.get('type'), c.get('id'), c.findtext('label')) for c in group.iter()
                if c.tag == 'control']
    dialog = controls(load(WINDOW))['1200']
    panel = controls(load('Home.xml'))['9180']
    assert body(dialog)[1:] == body(panel)[1:]
    for el in (dialog, panel):
        assert [el.findtext(k) for k in ('left', 'top', 'width', 'height')] == ['1232', '96', '640', '788']


def test_menu_on_home_over_the_page():
    """Drawn after the top line and the rows: over everything of Home but the backdrop that hides
    Home while an episode's info page comes back."""
    root = load('Home.xml').find('controls')
    ids = [c.get('id') for c in root.findall('control')]
    assert ids.index('9180') == len(ids) - 2
    assert ids.index('9190') < ids.index('9180')


def test_back_in_the_menu_on_home_goes_to_the_icon():
    """Back inside the panel of Home: the icon, menu still shown. In the dialog Back closes it as
    always (the condition does not hold there, so Kodi's own Back runs)."""
    for window in ('Home.xml', WINDOW):
        c = controls(load(window))
        for cid in ('1210', '1220', '1230'):
            assert actions(c[cid], 'onback') == [('!Window.IsActive(1170)', '9109')], (window, cid)


def test_power_page_is_gone():
    for name in ('Home.xml', 'Includes_Home.xml', 'Variables.xml'):
        text = (ROOT / '1080i' / name).read_text(encoding='utf-8')
        assert 'nc.page),power)' not in text and 'PowerWidgets' not in text and 'PowerHero' not in text, name
    assert '9106' not in controls(load('Home.xml'))


def test_weather_beside_the_clock():
    """With a weather service set up: its icon and the temperature left of the clock, in the
    clock's colour; without one nothing, the clock stays where it is."""
    row = controls(load('Home.xml'))['9190']
    parts = row.findall('control')
    assert [(c.get('type'), c.findtext('visible')) for c in parts] == [
        ('group', None), ('image', 'Weather.IsFetched'), ('label', 'Weather.IsFetched'), ('label', None)]
    icon, temperature, clock = parts[1:]
    assert icon.find('texture').text == 'ui/qm_weather.png'
    assert icon.find('texture').get('colordiffuse') == clock.findtext('textcolor')
    assert temperature.findtext('label') == '$INFO[Weather.Temperature]'
    assert temperature.findtext('font') == clock.findtext('font') == 'font_num'
    assert clock.findtext('label') == '$INFO[System.Time]'


def test_top_menu_wraps_around():
    """Left on home reaches the icon next to the clock, right on the icon home again; left on the
    icon goes to the last menu entry shown, not to the page that had the focus last."""
    from focus import Page, State
    page = Page('Home.xml')
    hidden = {'Skin.HasSetting(nc.menu.hide.{})'.format(n): False for n in ('movies', 'shows', 'search')}
    state = State(extra=hidden)
    assert page.move('9101', 'onleft', state)[0] == '9109'
    assert page.move('9109', 'onright', state)[0] == '9101'
    assert page.move('9109', 'onleft', state)[0] == '9104'
    assert page.move('9104', 'onright', state)[0] == '9109'
    hidden['Skin.HasSetting(nc.menu.hide.search)'] = True
    assert page.move('9109', 'onleft', State(extra=hidden))[0] == '9103'
    hidden.update({'Skin.HasSetting(nc.menu.hide.{})'.format(n): True for n in ('movies', 'shows', 'search')})
    assert page.move('9109', 'onleft', State(extra=hidden))[0] == '9101'


def test_settings_page_only_from_the_quick_menu():
    """The settings page is not in the top menu: the quick menu leads there."""
    home = controls(load('Home.xml'))
    assert '9105' not in home and '9118' not in home
    # up from the page: the icon it is reached from, the page stays
    assert home['9601'].findtext('onup') == '9109'


def test_menu_icon_is_a_hamburger():
    """Three bars of the same length, without the knobs of a slider."""
    from PIL import Image
    alpha = Image.open(ROOT / 'media' / 'ui' / 'qm_menu.png').split()[-1]
    width, height = alpha.size
    rows = [[x for x in range(width) if alpha.getpixel((x, y)) > 128] for y in range(height)]
    bars, spans = [], set()
    for y, row in enumerate(rows):
        if row:
            spans.add((row[0], row[-1]))
            if not rows[y - 1]:
                bars.append(y)
    assert len(bars) == 3
    assert len(spans) == 1, spans
    assert not (ROOT / 'media' / 'ui' / 'qm_anchor.png').exists()
    assert 'ui/qm_menu.png' in (ROOT / '1080i' / 'Includes_Home.xml').read_text(encoding='utf-8')
