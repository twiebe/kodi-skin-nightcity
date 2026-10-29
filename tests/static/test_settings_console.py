"""Settings console (concept B): five group tiles on the system page, Settings.xml as a rail of
all entries under the group headings with a preview of the focused entry (information only), and
an event log window."""
import re

from conftest import ROOT, parse
from navigation import load

# Kodi 21.3 system/settings/settings.xml: window -> [(category id, label id)] of the categories a
# user can see (no internal level 4, no visible false), in Kodi's order
CATEGORIES = {
    'PlayerSettings': [('videoplayer', 14215), ('musicplayer', 14216), ('discs', 14087),
                       ('pictures', 14217), ('language', 14218), ('subtitles', 287)],
    'MediaSettings': [('library', 14202), ('filelists', 16000), ('video', 14215), ('music', 14216),
                      ('pictures', 14217)],
    'PVRSettings': [('pvrmanager', 128), ('pvrmenu', 14301), ('epg', 22020), ('pvrplayback', 19177),
                    ('pvrrecord', 19043), ('pvrreminders', 19215), ('pvrpowermanagement', 14095),
                    ('pvrparental', 19259), ('pvrclient', 19279)],
    'InterfaceSettings': [('skin', 166), ('regional', 14222), ('screensaver', 360),
                          ('masterlock', 12360), ('other', 14224)],
    'SystemSettings': [('display', 14220), ('audio', 14221), ('input', 14125), ('network', 798),
                       ('powermanagement', 14095), ('addons', 24001), ('logging', 14092)],
    'ServiceSettings': [('general', 16000), ('control', 14223), ('upnp', 20187), ('airplay', 1273),
                        ('smb', 1200), ('nfs', 1201), ('filecache', 37101), ('weather', 8)],
}

# rail button id -> (Kodi label id, window it opens); group = second digit
RAIL = {
    '9211': (14200, 'PlayerSettings'), '9212': (14211, 'MediaSettings'), '9213': (14204, 'PVRSettings'),
    '9221': (14206, 'InterfaceSettings'), '9222': (166, 'SkinSettings'), '9223': (13200, 'Profiles'),
    '9231': (24001, 'AddonBrowser'), '9232': (10003, 'FileManager'),
    '9241': (13000, 'SystemSettings'), '9242': (14036, 'ServiceSettings'),
    '9251': (10007, 'SystemInfo'), '9252': (14111, 'EventLog'),
}
HUB_TARGETS = {'playersettings', 'mediasettings', 'interfacesettings', 'servicesettings',
               'systemsettings', 'profiles', 'addonbrowser', 'skinsettings', 'filemanager',
               'systeminfo', 'eventlog'}
ACTIVATE = re.compile(r'ActivateWindow\(([^,)]+)(?:,([^,)]+))?')


def console():
    return load('Settings.xml')


def controls(root):
    return {c.get('id'): c for c in root.iter('control') if c.get('id')}


def rail():
    return controls(console())['9200']


def rail_buttons():
    return [c for c in rail().iter('control') if c.get('type') == 'button']


def clicks(el):
    return [(o.text or '').strip() for o in el.findall('onclick')]


def home_include(name):
    root = parse(ROOT / '1080i' / 'Includes_Home.xml')
    return next(i for i in root.iter('include') if i.get('name') == name)


def test_system_page_has_five_group_tiles():
    """The system page holds one tile per group; OK remembers the group and opens the console."""
    tiles = home_include('SystemWidgets').find(".//control[@id='9601']")
    items = tiles.find('content').findall('item')
    assert len(items) == 5
    for n, item in enumerate(items, 1):
        assert clicks(item) == ['SetProperty(nc.settings.group,{},home)'.format(n), 'ActivateWindow(settings)']
        assert item.find('visible') is None  # a static list clicks by position


def test_console_focuses_the_chosen_group():
    root = parse(ROOT / '1080i' / 'Settings.xml')
    default = root.find('defaultcontrol')
    assert default.text == '9211' and default.get('always') != 'true'  # Back keeps the rail focus
    onloads = [(o.get('condition'), o.text) for o in root.findall('onload')]
    for n in range(1, 6):
        assert ('String.IsEqual(Window(Home).Property(nc.settings.group),{})'.format(n),
                'SetFocus(92{}1)'.format(n)) in onloads
    assert onloads[-1] == (None, 'ClearProperty(nc.settings.group,home)')
    assert not [o for o in onloads if 'RunScript' in o[1]]


def test_rail_lists_every_entry_under_its_group():
    """Full rail: five headings, each followed by its entries, labels from Kodi's strings."""
    children = rail().findall('control')
    headings = [c.get('id') for c in children if c.get('type') == 'label']
    assert headings == ['9201', '9202', '9203', '9204', '9205']
    order = [c.get('id') for c in children]
    assert order == ['9201', '9211', '9212', '9213', '9202', '9221', '9222', '9223', '9203', '9231',
                     '9232', '9204', '9241', '9242', '9205', '9251', '9252']
    for button in rail_buttons():
        label, window = RAIL[button.get('id')]
        assert button.findtext('label') == '$LOCALIZE[{}]'.format(label)
        assert 'ActivateWindow({})'.format(window) in clicks(button)


def test_live_tv_only_with_a_pvr_client():
    buttons = {b.get('id'): b for b in rail_buttons()}
    assert buttons['9213'].findtext('visible') == 'System.HasPVRAddon'
    assert [b for b in buttons.values() if b.findtext('visible') not in (None, 'true')] == [buttons['9213']]


def test_nothing_reachable_today_gets_lost():
    targets = set()
    for button in rail_buttons():
        for click in clicks(button):
            m = ACTIVATE.match(click)
            if m:
                targets.add(m.group(1).lower())
    assert HUB_TARGETS <= targets


def preview_lists():
    found = controls(console())
    return {rid: found.get('93' + rid[2:]) for rid in RAIL}


def test_preview_lists_show_kodi_categories():
    """Each preview lists the categories of its section, with the label of Kodi 21.3 and in
    Kodi's order."""
    lists = preview_lists()
    for rid, (_, window) in RAIL.items():
        if window not in CATEGORIES:
            continue
        rows = lists[rid].find('content').findall('item')
        assert [r.findtext('label') for r in rows] == ['$LOCALIZE[{}]'.format(label) for _, label in CATEGORIES[window]]


def test_previews_are_information_only():
    """Level 2 (the console) picks on the left only: the cursor never enters a preview, and its
    rows do nothing. Kodi's page then opens with the cursor in its categories (level 3)."""
    for lst in preview_lists().values():
        if lst is None:
            continue
        assert lst.findtext('enable') == 'false'
        assert not [i for i in lst.iter('item') if clicks(i)]
    previews = {l.get('id') for l in preview_lists().values() if l is not None}
    for button in rail_buttons():
        assert button.findtext('onright') in (None, 'noop')
    for el in console().iter():
        for tag in ('onleft', 'onright', 'onup', 'ondown', 'onback', 'onclick', 'onload'):
            for a in el.findall(tag):
                assert not [p for p in previews if p in (a.text or '')], (tag, a.text)


def test_preview_lists_have_no_hidden_rows():
    for lst in preview_lists().values():
        if lst is not None:
            assert not [i for i in lst.iter('item') if i.find('visible') is not None]


def test_rail_is_one_include_per_group():
    """Switching to a rail with only the chosen group stays cheap: each group is one include."""
    root = parse(ROOT / '1080i' / 'Settings.xml')
    grouplist = next(c for c in root.iter('control') if c.get('id') == '9200')
    names = [i.get('content') or i.text for i in grouplist.findall('include')]
    assert names == ['SettingsRailGroup1', 'SettingsRailGroup2', 'SettingsRailGroup3',
                     'SettingsRailGroup4', 'SettingsRailGroup5']


def test_category_page_starts_in_the_categories():
    """Level 3 (Kodi's settings page) opens with the cursor on the left, on the first category
    or on the one a link named."""
    root = parse(ROOT / '1080i' / 'SettingsCategory.xml')
    default = root.find('defaultcontrol')
    assert default.text == '3' and default.get('always') == 'true'
    ids = sorted(int(c.get('id')) for c in root.iter('control') if c.get('id'))
    assert ids == [2, 3, 5, 6, 9003]


def test_no_deep_link_hint_left():
    for path in list((ROOT / '1080i').glob('*.xml')):
        assert 'nc.deeplink' not in path.read_text(encoding='utf-8'), path.name
    for po in ROOT.glob('language/*/strings.po'):
        assert 'msgctxt "#31180"' not in po.read_text(encoding='utf-8'), po.parent.name


def test_event_log_window():
    """Kodi 21 opens EventLog.xml (GUIWindowEventLog.cpp): view 50, clear 20, level 21, level
    only 22."""
    path = ROOT / '1080i' / 'EventLog.xml'
    root = load('EventLog.xml')
    assert parse(path).findtext('views') == '50'
    found = controls(root)
    assert found['50'].get('type') == 'list'
    assert found['20'].get('type') == 'button' and found['21'].get('type') == 'button'
    assert found['22'].get('type') == 'radiobutton'


def test_duplicate_settings_strings_gone():
    gone = ['#{}'.format(i) for i in list(range(31060, 31071)) + list(range(31107, 31116))]
    for po in ROOT.glob('language/*/strings.po'):
        text = po.read_text(encoding='utf-8')
        assert not [g for g in gone if 'msgctxt "{}"'.format(g) in text], po.parent.name
    for p in (ROOT / '1080i').glob('*.xml'):
        text = p.read_text(encoding='utf-8')
        assert not [g for g in gone if '$LOCALIZE[{}]'.format(g[1:]) in text], p.name


def test_console_hint_offers_no_way_right():
    """The key hint under the preview names OK and Back only, there is nothing to the right."""
    hint = [c for c in console().iter('control') if 'SettingsConsoleHint' in (c.findtext('label') or '')
            or '31178' in (c.findtext('label') or '')]
    assert [c.findtext('label') for c in hint] == ['[UPPERCASE]$LOCALIZE[31178][/UPPERCASE]']
    for po in ROOT.glob('language/*/strings.po'):
        text = po.read_text(encoding='utf-8')
        assert 'msgctxt "#31177"' not in text and 'msgctxt "#31179"' not in text, po.parent.name


def test_left_and_right_walk_the_levels():
    """Right on a rail entry opens it like OK (level 2 to 3); Left goes back one level, on the
    rail (2 to 1) and in the left column of Kodi's settings page (3 to 2)."""
    rail_list = rail()
    assert rail_list.findtext('onright') == 'Action(Select)'
    assert rail_list.findtext('onleft') == 'Action(Back)'
    assert not [b.get('id') for b in rail_buttons() if b.findtext('onright') or b.findtext('onleft')]
    page = controls(parse(ROOT / '1080i' / 'SettingsCategory.xml'))
    for cid in ('3', '9003'):
        assert page[cid].findtext('onleft') == 'Action(Back)', cid


# window opened from the console -> its leftmost control
LEFT_COLUMN = {'SkinSettings.xml': '9000', 'AddonBrowser.xml': '50', 'FileManager.xml': '20',
               'SettingsSystemInfo.xml': '9000', 'EventLog.xml': '50', 'SettingsProfile.xml': '2'}


def test_left_leaves_every_level_3_window():
    """Every page the console opens goes back one level with Left from its left column, as
    Kodi's settings pages do (in the add-on browser and the file manager that is one folder up,
    and out at the top)."""
    for name, cid in LEFT_COLUMN.items():
        assert controls(load(name))[cid].findtext('onleft') == 'Action(Back)', name
