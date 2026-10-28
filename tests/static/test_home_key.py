from conftest import ROOT, parse

HOME_KEY = 'ActivateWindow(1160)'


def _window():
    return parse(ROOT / '1080i' / 'Custom_1160_HomeKey.xml')


def test_home_key_window_is_an_empty_dialog():
    """The Home key opens an empty dialog: Kodi opens a dialog even over the info page, where it
    refuses ActivateWindow(Home), and no Python starts (two interpreters at once crash Kodi)."""
    window = _window()
    assert window.get('type') == 'dialog'
    assert window.get('id') == '1160'
    assert not list(window.iter('control'))


CHAIN = '!String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'
NO_CHAIN = 'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))'


def test_home_key_window_closes_dialogs_and_focuses_home():
    """Closes every dialog (itself, the info page, the OSD) at once, opens Home and focuses its
    tab, which shows the home page."""
    loads = [(o.get('condition'), o.text) for o in _window().iter('onload')]
    assert [t for c, t in loads if c == NO_CHAIN] == [
        'Dialog.Close(all,true)', 'ActivateWindow(Home)', 'SetFocus(9101)']


def test_home_key_in_a_chain_lets_the_manager_end_it():
    """Closing the info page under a running chain looks like Back to TMDb Helper's manager when
    it polls before the chain window is gone: it opened the page before again, over Home. The
    key asks the manager to exit instead (a command it reads before it looks at the windows),
    keeps a chain over video from reopening the OSD, and closes only itself; nc_home_key goes
    Home a second after the manager ended, when no interpreter starts with Home's script."""
    loads = [(o.get('condition'), o.text) for o in _window().iter('onload')]
    assert [t for c, t in loads if c == CHAIN] == [
        'SetProperty(nc.home.key,1,home)', 'ClearProperty(nc.chain.return,home)',
        'SetProperty(TMDbHelper.Command,exit,home)', 'Dialog.Close(1160,true)']
    timer = next(t for t in parse(ROOT / '1080i' / 'Timers.xml').iter('timer') if t.findtext('name') == 'nc_home_key')
    assert timer.findtext('start') == '!String.IsEmpty(Window(Home).Property(nc.home.key)) + ' + NO_CHAIN
    assert timer.find('start').get('reset') == 'true'
    assert timer.findtext('stop') == 'Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_home_key),1)'
    assert [o.text for o in timer.findall('onstop')] == ['ClearProperty(nc.home.key,home)', 'ActivateWindow(1160)']


def test_home_tab_is_9101():
    includes = (ROOT / '1080i' / 'Includes_Home.xml').read_text()
    assert '<param name="id" value="9101"/>\n                <param name="label" value="$LOCALIZE[31006]"/>' in includes


def test_skin_settings_switch_off_the_home_key():
    """A row in the skin settings switches the keymap off; the script applies it at once."""
    text = (ROOT / '1080i' / 'SkinSettings.xml').read_text()
    assert '<param name="setting" value="nc.homekey.off"/>' in text
    assert '<param name="onclick" value="NotifyAll(nightcity,home_keymap)"/>' in text
    toggle = (ROOT / '1080i' / 'Includes_Settings.xml').read_text()
    assert '<onclick>Skin.ToggleSetting($PARAM[setting])</onclick>\n                <onclick>$PARAM[onclick]</onclick>' in toggle
