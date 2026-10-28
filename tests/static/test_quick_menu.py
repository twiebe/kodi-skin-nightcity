"""Quick menu (Custom_1170_QuickMenu.xml): a small panel that slides in at the top right over
whatever is on screen, with the clock, the weather, the power commands and links to the settings
and the system page. Kodi's power menu (shutdownmenu: the S key, power and sleep keys) leads
there, so does a long press on Home (the skin's keymap) and the icon next to the clock in the
top line of Home. It replaces the power page of Home."""
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
    items = list(controls(parse(ROOT / '1080i' / WINDOW))['1220'].iter('item'))
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
    items = list(controls(parse(ROOT / '1080i' / WINDOW))['1220'].iter('item'))
    timer = next(i for i in items if any('AlarmClock' in a for _, a in actions(i)))
    assert actions(timer) == [('!System.HasAlarm(shutdowntimer)', 'AlarmClock(shutdowntimer,Shutdown())'),
                              ('System.HasAlarm(shutdowntimer)', 'CancelAlarm(shutdowntimer)')]
    assert len(items) == 6


def test_weather_or_how_to_get_it():
    """With a weather add-on: temperature, conditions and place, OK opens Kodi's weather. Without
    one the tile says so and OK opens the weather settings."""
    weather = controls(parse(ROOT / '1080i' / WINDOW))['1210']
    # Kodi opens no window while a modal dialog is open
    assert actions(weather) == [('', 'Dialog.Close(1170,true)'), ('Weather.IsFetched', 'ActivateWindow(weather)'),
                                ('!Weather.IsFetched', 'ActivateWindow(servicesettings,weather)')]
    text = (ROOT / '1080i' / WINDOW).read_text(encoding='utf-8')
    for label in ('Weather.Temperature', 'Weather.Conditions', 'Weather.Location', '$LOCALIZE[31321]'):
        assert label in text


def test_links_to_settings_and_system():
    """Static items, so more links (later the user's own) are one item more."""
    links = controls(parse(ROOT / '1080i' / WINDOW))['1230']
    items = links.findall('content/item')
    clicks = [[a for _, a in actions(i)] for i in items]
    assert clicks[0][0] == 'Dialog.Close(1170,true)' and clicks[0][-1] == 'ActivateWindow(settings)'
    assert clicks[1] == ['Dialog.Close(1170,true)', 'SetProperty(nc.page,system,home)', 'ActivateWindow(Home)',
                         'SetFocus(9105)']


def test_rows_lead_into_each_other():
    c = controls(load(WINDOW))
    assert c['1210'].findtext('ondown') == '1220'
    assert c['1220'].findtext('onup') == '1210' and c['1220'].findtext('ondown') == '1230'
    assert c['1230'].findtext('onup') == '1220'


def test_kodis_power_menu_leads_here():
    """Like Arctic Fuse: the power menu closes at once and opens the quick menu, or closes it when
    it is open, so the same key opens and closes it."""
    root = parse(ROOT / '1080i' / 'DialogButtonMenu.xml')
    assert actions(root, 'onload') == [('', 'Close'), ('!Window.IsActive(1170)', 'ActivateWindow(1170)'),
                                       ('Window.IsActive(1170)', 'Dialog.Close(1170)')]
    assert not list(root.iter('control'))


def test_icon_next_to_the_clock_opens_it():
    home = controls(load('Home.xml'))
    anchor = home['9109']
    assert actions(anchor) == [('', 'ActivateWindow(1170)')]
    assert anchor.findtext('onleft') == '9100'
    assert home['9100'].findtext('onright') == '9109'
    row = home['9190']
    assert row.get('type') == 'grouplist' and row.findtext('align') == 'right'
    assert [c.get('id') for c in row.findall('control')][0] == '9109'


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
        ('radiobutton', None), ('image', 'Weather.IsFetched'), ('label', 'Weather.IsFetched'), ('label', None)]
    icon, temperature, clock = parts[1:]
    assert icon.find('texture').text == 'ui/qm_weather.png'
    assert icon.find('texture').get('colordiffuse') == clock.findtext('textcolor')
    assert temperature.findtext('label') == '$INFO[Weather.Temperature]'
    assert temperature.findtext('font') == clock.findtext('font') == 'font_num'
    assert clock.findtext('label') == '$INFO[System.Time]'
