"""Player controls that hide by themselves: the skin settings' Player category holds a switch
(on by default: the skin bool nc.osd.autohide.off switches it off) and a slider for the delay, 3 to 30 s, 8 s by default
(nc.osd.hide.secs; the script also writes nc.osd.hide.wait and the nib's span
nc.osd.hide.from, nc.osd.hide.to). The timer
nc_osd_hide (Timers.xml) closes the OSD and its rows once no key was pressed for that long while
the video plays. The same category switches the plot under the title in the player
(nc.osd.plot.off)."""
import re

import pytest

from conftest import ROOT, parse
from navigation import ATOM, dead_ends, load, unreachable

ROWS = ('videobookmarks', '1141')
ELAPSED = 'Skin.TimerElapsedSecs(nc_osd_hide)'


def timer():
    timers = parse(ROOT / '1080i' / 'Timers.xml')
    return next(t for t in timers.iter('timer') if t.findtext('name') == 'nc_osd_hide')


def truth(condition, true):
    """Value of a Kodi condition with the atoms in `true` holding and every other one not."""
    expr, pos = [], 0
    for m in ATOM.finditer(condition):
        expr.append(condition[pos:m.start()])
        expr.append(' {} '.format(m.group(0) in true))
        pos = m.end()
    expr.append(condition[pos:])
    text = ''.join(expr).replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return bool(eval(text, {}))


PLAYING = {'Player.HasVideo', 'Window.IsActive(fullscreenvideo)',
           'Window.IsModalDialogTopmost(videoosd)'}


def test_timer_runs_while_the_osd_is_up_over_a_playing_video():
    start = timer().find('start')
    assert start.get('reset') == 'true'
    assert truth(start.text, PLAYING)


@pytest.mark.parametrize('row', ROWS)
def test_timer_does_not_run_in_the_rows_below_the_controls(row):
    """Down from the controls into the chapter row (videobookmarks) or the cast row (1141, its
    tabs and biography): the OSD stays until the user is back on the controls."""
    state = PLAYING - {'Window.IsModalDialogTopmost(videoosd)'} | {'Window.IsModalDialogTopmost({})'.format(row)}
    assert not truth(timer().find('start').text, state)


@pytest.mark.parametrize('change', [
    # switched off
    PLAYING | {'Skin.HasSetting(nc.osd.autohide.off)'},
    # paused: the countdown starts again once playback goes on
    PLAYING | {'Player.Paused'},
    # a dialog opened over the OSD (track settings, subtitle search, keyboard, select) is on top
    PLAYING - {'Window.IsModalDialogTopmost(videoosd)'},
    PLAYING - {'Window.IsActive(fullscreenvideo)'},
    PLAYING - {'Player.HasVideo'},
    # in a track panel of the OSD (subtitles, audio, video): groups in VideoOSD, so the OSD stays
    # the topmost dialog; the cursor on the panel's button alone is plain OSD use
    PLAYING | {'Control.HasFocus(651)'},
    PLAYING | {'Control.HasFocus(652)'},
    PLAYING | {'Control.HasFocus(653)'},
])
def test_timer_does_not_run(change):
    assert not truth(timer().find('start').text, change)


def test_any_key_restarts_the_countdown():
    """Kodi resets a timer while its reset condition holds: until a second passed without input,
    which is why the wait is the delay less that second."""
    assert timer().findtext('reset') == '!System.IdleTime(1)'


def _stop(condition, elapsed, wait):
    """Evaluate the stop condition with the timer at `elapsed` s and nc.osd.hide.wait `wait`
    ('' when never set)."""
    def atom(m):
        text = m.group(0)
        if text == 'String.IsEmpty(Skin.String(nc.osd.hide.wait))':
            return str(wait == '')
        cmp = re.match(r'Integer\.IsGreaterOrEqual\(' + re.escape(ELAPSED) + r',([^()]+(?:\([^()]*\))?)\)$', text)
        if cmp:
            limit = cmp.group(1)
            if limit == 'Skin.String(nc.osd.hide.wait)':
                limit = wait or '0'
            return str(elapsed >= int(limit))
        return str(text in PLAYING)
    text = ATOM.sub(lambda m: ' {} '.format(atom(m)), condition)
    text = text.replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return bool(eval(text, {}))


@pytest.mark.parametrize('wait, elapsed, stops', [
    ('2', 1, False), ('2', 2, True), ('29', 28, False), ('29', 29, True),
    # never set (the page writes it when it opens): the default 8 s
    ('', 6, False), ('', 7, True),
])
def test_timer_stops_after_the_delay(wait, elapsed, stops):
    assert _stop(timer().findtext('stop'), elapsed, wait) is stops


def test_timer_stops_when_its_start_no_longer_holds():
    t = timer()
    assert t.findtext('stop').startswith('![{}] | '.format(t.find('start').text))


def test_timer_closes_the_osd():
    """It only runs with the OSD on top, so there are no rows to close."""
    t = timer()
    onstops = t.findall('onstop')
    assert [o.text for o in onstops] == ['Dialog.Close(videoosd)']
    # only when the time is up, not when a pause or a dialog stopped the timer
    for o in onstops:
        assert _stop(o.get('condition'), 7, '7')
        assert not _stop(o.get('condition'), 6, '7')
        assert o.get('condition').startswith(t.find('start').text + ' + ')


# --- skin settings ---------------------------------------------------------------------------

def controls(window):
    return {c.get('id'): c for c in window.iter('control') if c.get('id')}


def page(skin=None):
    return load('SkinSettings.xml', skin)


def test_player_category():
    c = controls(page())
    cat = c['9006']
    assert cat.get('type') == 'togglebutton'
    assert cat.findtext('label') == '$LOCALIZE[14200]'
    assert cat.findtext('onfocus') == 'SetProperty(nc.hp.tab,player)'
    assert [b.get('id') for b in c['9000'].findall('control')][-1] == '9006'
    assert c['9000'].findall('onright')[-1].text == '500'
    rights = [(o.get('condition'), o.text) for o in c['9000'].findall('onright')]
    assert ('String.IsEqual(Window.Property(nc.hp.tab),player)', '700') in rights
    area = c['700']
    assert area.findtext('visible') == 'String.IsEqual(Window.Property(nc.hp.tab),player)'
    assert area.findtext('onleft') == '9006'


@pytest.mark.parametrize('cid, name', [('711', 'autohide'), ('713', 'plot')])
def test_switches_are_on_by_default(cid, name):
    """Skin bools start unset: the switches store being off."""
    switch = controls(page())[cid]
    assert switch.get('type') == 'radiobutton' and switch.findtext('width') == '1240'
    assert switch.findtext('selected') == '!Skin.HasSetting(nc.osd.{}.off)'.format(name)
    assert [o.text for o in switch.findall('onclick')][0] == 'Skin.ToggleSetting(nc.osd.{}.off)'.format(name)


def test_player_rows_in_order():
    area = controls(page())['700']
    assert [k.get('id') for k in area.findall('control')] == ['711', '720', '713']


def test_plot_in_the_player_follows_its_switch():
    root = parse(ROOT / '1080i' / 'Includes_Player.xml')
    details = next(i for i in root.iter('include') if i.get('name') == 'PlayerDetails')
    plot = next(t for t in details.iter('control') if t.get('type') == 'textbox')
    assert plot.findtext('label') == '$VAR[PlayerPlot]' and plot.get('id') == '420'
    assert plot.findtext('visible') == '!Skin.HasSetting(nc.osd.plot.off)'


def test_delay_row_shows_only_while_switched_on():
    c = controls(page())
    row = c['720']
    assert row.get('type') == 'group'
    assert row.findtext('visible') == '!Skin.HasSetting(nc.osd.autohide.off)'
    assert [k.get('id') for k in row.iter('control') if k.get('id')] == ['720', '712']


def test_delay_row_has_a_slider_like_kodis():
    """As Kodi's settings slider (template 13): label left, the value, a 300 px bar at the right
    with the nib, light while the slider is taken."""
    row = controls(page())['720']
    button = row.find("control[@id='712']")
    assert button.findtext('label') == '$LOCALIZE[31362]'
    bar = row.find("control[@type='progress']")
    assert [bar.findtext(k) for k in ('left', 'top', 'width', 'height')] == ['920', '20', '300', '12']
    assert bar.findtext('info') == 'Skin.Numeric(nc.osd.hide.to)'
    assert bar.findtext('info2') == 'Skin.Numeric(nc.osd.hide.from)'
    assert bar.find('texturebg').get('colordiffuse') == 'surface_alt'
    assert bar.find('midtexture').get('colordiffuse') == '$VAR[OsdHideNibColor]'
    value = row.find("control[@type='label']")
    assert value.findtext('label') == '$VAR[OsdHideDelayLabel]'
    variables = parse(ROOT / '1080i' / 'Variables.xml')
    nib = next(v for v in variables.iter('variable') if v.get('name') == 'OsdHideNibColor')
    assert [(v.get('condition'), v.text) for v in nib.findall('value')] == [
        ('!String.IsEmpty(Window.Property(nc.hp.slide))', 'text'), (None, 'accent')]
    label = next(v for v in variables.iter('variable') if v.get('name') == 'OsdHideDelayLabel')
    assert [(v.get('condition'), v.text) for v in label.findall('value')] == [
        ('!String.IsEmpty(Skin.String(nc.osd.hide.secs))', '$INFO[Skin.String(nc.osd.hide.secs)] s'), (None, '8 s')]


def test_ok_takes_the_slider_left_and_right_move_it():
    """Kodi's way for a settings slider: OK takes it, left and right move it a second, OK or
    leaving the row lets go. Not taken, left goes back to the category."""
    button = controls(page())['712']
    clicks = [(o.get('condition'), o.text) for o in button.findall('onclick')]
    assert clicks == [('String.IsEmpty(Window.Property(nc.hp.slide))', 'SetProperty(nc.hp.slide,1)'),
                      ('!String.IsEmpty(Window.Property(nc.hp.slide))', 'ClearProperty(nc.hp.slide)')]
    taken = '!String.IsEmpty(Window.Property(nc.hp.slide))'
    step = 'NotifyAll(nightcity,osd_hide:$INFO[Skin.String(nc.osd.hide.secs)]:{})'
    # Kodi runs the actions, then moves to the first id whose condition holds: taken, the row itself
    assert [(o.get('condition'), o.text) for o in button.findall('onleft')] == [
        (taken, step.format(-1)), (taken, '712'), (None, '9006')]
    assert [(o.get('condition'), o.text) for o in button.findall('onright')] == [(taken, step.format(1)), (None, 'noop')]
    assert button.findtext('onup') == '711'
    assert button.findtext('ondown') == '713'
    assert button.findtext('onunfocus') == 'ClearProperty(nc.hp.slide)'


def test_page_writes_the_default_delay_on_load():
    root = parse(ROOT / '1080i' / 'SkinSettings.xml')
    onloads = [(o.get('condition'), o.text) for o in root.findall('onload')]
    empty = 'String.IsEmpty(Skin.String(nc.osd.hide.secs))'
    assert (empty, 'NotifyAll(nightcity,osd_hide:8:0)') in onloads
    assert (None, 'ClearProperty(nc.hp.slide)') in onloads


def test_descriptions():
    variables = parse(ROOT / '1080i' / 'Variables.xml')
    desc = next(v for v in variables.iter('variable') if v.get('name') == 'SkinSettingsDesc')
    values = {v.get('condition'): v.text for v in desc.findall('value')}
    assert values['Control.HasFocus(711)'] == '$LOCALIZE[31361]'
    assert values['Control.HasFocus(712)'] == '$LOCALIZE[31363]'
    assert values['Control.HasFocus(9006)'] == '$LOCALIZE[31364]'
    assert values['Control.HasFocus(713)'] == '$LOCALIZE[31366]'


@pytest.mark.parametrize('skin', [{}, {'nc.osd.autohide.off': '1'}])
def test_player_category_navigation(skin):
    skin = dict(skin, **{'Window.Property(nc.hp.tab)': 'player'})
    assert dead_ends('SkinSettings.xml', skin) == []
    assert [i for i in unreachable('SkinSettings.xml', skin) if i[0] == '7'] == []
