"""Back held in the settings goes back to where the quick menu's settings link was chosen
(scripts/nightcity.py settings_return). Kodi forgets its windows on the way to the settings
(Custom_1160_HomeKey.xml), so the link keeps the way in nc.settings.from, and the skin forgets it
again once the settings are left another way."""
import importlib.util
import re

from conftest import ROOT, parse

_spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
nightcity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nightcity)

FROM = 'Window(Home).Property(nc.settings.from)'


def _settings_link():
    home = parse(ROOT / '1080i' / 'Includes_Home.xml')
    return next(i for i in home.iter('item') if i.findtext('label') == '$LOCALIZE[5]'
                and i.findtext('icon') == 'ui/qm_settings.png')


def test_the_settings_link_keeps_where_it_was_chosen():
    """First thing, before the menu closes: the window under it still answers."""
    clicks = [o.text for o in _settings_link().findall('onclick')]
    assert clicks[0] == 'SetProperty(nc.settings.from,"$VAR[SettingsFrom]",home)'
    assert clicks[1:] == ['Dialog.Close(1170,true)', 'SetProperty(nc.go,system,home)', 'ActivateWindow(1160)']


def test_where_it_was_chosen_in_the_form_the_script_reads():
    variables = (ROOT / '1080i' / 'Variables.xml').read_text(encoding='utf-8')
    body = re.search(r'<variable name="SettingsFrom">(.*?)</variable>', variables, re.S).group(1)
    values = re.findall(r'<value condition="([^"]*)">([^<]*)</value>', body)
    assert values == [
        ('Window.IsActive(fullscreenvideo)', 'player'),
        ('Window.IsActive(1110)', 'library|$INFO[Window(Home).Property(nc.library)]'),
        ('Window.IsActive(videos)', 'videos|$INFO[Container.FolderPath]'),
        ('Window.IsActive(music)', 'music|$INFO[Container.FolderPath]'),
        ('Window.IsActive(home)', 'home|$INFO[Window(Home).Property(nc.page)]|$INFO[Window(Home).Property(nc.quick.from)]'),
    ]


def _timer():
    timers = parse(ROOT / '1080i' / 'Timers.xml')
    return next(t for t in timers.iter('timer') if t.findtext('name') == 'nc_settings_from')


def test_the_way_back_is_forgotten_once_the_settings_are_left():
    """A second outside the settings, the settings page of Home, the quick menu and the way
    between them (1160): the way back goes. Not at once: on the way in Home shows its old page for
    a moment."""
    timer = _timer()
    start = timer.findtext('start')
    assert start.startswith('!String.IsEmpty({})'.format(FROM))
    for window in nightcity.SETTINGS_WINDOWS + ('1170', '1160'):
        assert 'Window.IsActive({})'.format(window) in start
    assert '[Window.IsActive(home) + String.IsEqual(Window(Home).Property(nc.page),system)]' in start
    assert 'ControlGroup(9180).HasFocus()' in start
    assert 'Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_settings_from),1)' in timer.findtext('stop')
    stops = [(o.get('condition'), o.text) for o in timer.findall('onstop')]
    assert stops == [(start, 'ClearProperty(nc.settings.from,home)')]
