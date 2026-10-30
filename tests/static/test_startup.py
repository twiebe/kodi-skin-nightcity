import re

from conftest import ROOT, parse

READY = '!String.IsEmpty(Window(Home).Property(nc.startup.ready))'


def _startup():
    return parse(ROOT / '1080i' / 'Startup.xml')


def _timer(name='nc_startup'):
    timers = parse(ROOT / '1080i' / 'Timers.xml')
    return next(t for t in timers.iter('timer') if t.findtext('name') == name)


def _secs(text, name='nc_startup'):
    return [int(n) for n in re.findall(r'Skin\.TimerElapsedSecs\(' + name + r'\),(\d+)\)', text)]


def test_startup_onloads():
    """Startup still switches on the TMDb Helper service, its window manager's direct mode and
    its local widget containers, and clears the ready flag of an earlier run; the script and the
    hand-over are left to the timers."""
    onloads = [o.text for o in _startup().iter('onload')]
    assert onloads == ['Skin.SetBool(TMDbHelper.Service)', 'Skin.SetBool(TMDbHelper.DirectCallAuto)',
                       'Skin.SetBool(TMDbHelper.UseLocalWidgetContainer)', 'ClearProperty(nc.startup.ready,home)']


def test_startup_script_starts_after_services():
    """Kodi starts the service add-ons (JellyCon, Jellyfin, TMDb Helper) within a millisecond of
    Startup's onload; a script started there too crashed Kodi in kodi-dev. The startup script
    starts a second later, from a timer."""
    timer = _timer('nc_startup_script')
    idle = 'Window.IsActive(startup) + String.IsEmpty(Window(Home).Property(nc.service))'
    assert timer.find('start').text == idle
    assert timer.find('start').get('reset') == 'true'
    stop = timer.findtext('stop')
    assert '!Window.IsActive(startup)' in stop
    assert _secs(stop, 'nc_startup_script') == [1]
    onstop = timer.find('onstop')
    assert onstop.text == 'RunScript(special://skin/scripts/nightcity.py,service,startup)'
    assert onstop.get('condition') == idle


def test_startup_hands_over_to_home():
    """The timer runs while Startup is up and replaces it with Home once the startup script is
    done and a short minimum time has passed, or after a hard timeout so it never hangs."""
    timer = _timer()
    assert timer.find('start').text == 'Window.IsActive(startup)'
    assert timer.find('start').get('reset') == 'true'
    stop = timer.findtext('stop')
    assert '!Window.IsActive(startup)' in stop
    assert READY in stop
    minimum, timeout = _secs(stop)
    assert minimum == 4  # the screen stays up 4 s, also when the script is done sooner
    assert minimum < timeout <= 15
    onstop = timer.find('onstop')
    assert onstop.text == 'ReplaceWindow(Home)' and onstop.get('condition') == 'Window.IsActive(startup)'


def test_startup_script_signals_ready():
    script = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    body = script[script.index('def startup():'):script.index('COMMANDS = ')]
    assert "'nc.startup.ready'" in body and 'finally:' in body


def test_startup_shows_wordmark():
    """A NIGHTCITY wordmark from the language file, set as a centred glitch title."""
    root = _startup()
    assert 'Background' in [i.text for i in root.iter('include')]
    title = next(i for i in root.iter('include') if i.get('content') == 'GlitchTitle')
    params = {p.get('name'): p.get('value') for p in title.findall('param')}
    assert params['label'] == '$LOCALIZE[31156]' and params['align'] == 'center'
    for lang in ('en_gb',):
        po = (ROOT / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
        assert 'msgctxt "#31156"\nmsgid "Nightcity"\n' in po, lang


def test_startup_loading_indicator():
    """A ticker runs along a thin track until the script is done, then the track fills; the
    status line says which of the two it is."""
    root = _startup()
    loops = [a for a in root.iter('animation') if a.get('loop') == 'true']
    assert loops
    visibles = [v.text for v in root.iter('visible')]
    assert '$EXP[StartupOnline]' in visibles and '!$EXP[StartupOnline]' in visibles
    assert READY not in visibles and READY.replace('!', '', 1) not in visibles
    labels = ' '.join(l.text or '' for l in root.iter('label'))
    assert '$LOCALIZE[31157]' in labels and '$LOCALIZE[31158]' in labels


def test_startup_no_foreign_branding():
    """Nightcity is the skin's own name: no game branding, no signature yellow."""
    texts = [(ROOT / '1080i' / 'Startup.xml').read_text(encoding='utf-8')]
    texts += [p.read_text(encoding='utf-8') for p in ROOT.glob('language/*/strings.po')]
    for text in texts:
        assert '2077' not in text and 'cyberpunk' not in text.lower()
    startup = texts[0]
    assert 'accent3' not in startup and 'warn' not in startup


def test_startup_says_online_one_second_before_home():
    """The screen stays up its minimum time also when the script is done sooner: it says
    booting until a second before it hands over, so online does not stand there for seconds."""
    expressions = {e.get('name'): e.text for e in parse(ROOT / '1080i' / 'Includes_Base.xml').iter('expression')}
    minimum, _ = _secs(_timer().findtext('stop'))
    assert expressions['StartupOnline'] == (
        READY + ' + Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_startup),{})'.format(minimum - 1))
