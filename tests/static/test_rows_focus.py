"""The focus never lands in a TMDb list that still shows the page before (TmdbFresh<id>,
test_stale_lists.py), and it never waits for an extra key once a list is in.

A move or a tab's OK towards a list that is not ready yet (stale, loading or empty) does not
enter it: it notes the list in nc.info.enter and the control the focus was on in
nc.info.enter.from (Home). The skin timer nc_info_enter moves the focus into the list once it
is fresh and has items, as long as the focus stayed where it was."""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT, parse

SKIN = ROOT / '1080i'
LISTS = ('5500', '5510', '5300')


def _ready(cid):
    return '$EXP[TmdbFresh{0}] + !Container({0}).IsUpdating + Integer.IsGreater(Container({0}).NumItems,0)'.format(cid)


def _info():
    return {c.get('id'): c for c in parse(SKIN / 'DialogVideoInfo.xml').iter('control') if c.get('id')}


def _include(name):
    for path in SKIN.glob('Includes*.xml'):
        for el in parse(path).iter('include'):
            if el.get('name') == name:
                return el
    raise AssertionError(name)


def _actions(control, tag):
    return [((a.get('condition') or ''), (a.text or '').strip()) for a in control.findall(tag)]


def _moves_into(control, tag):
    """(condition, target) of every move or SetFocus of `control` into a TMDb list."""
    found = []
    for condition, action in _actions(control, tag):
        target = re.fullmatch(r'(?:SetFocus\()?(\d+)\)?', action)
        if target and target.group(1) in LISTS:
            found.append((condition, target.group(1)))
    return found


def test_moves_into_a_tmdb_list_wait_until_it_is_ready():
    controls = _info()
    moves = []
    for cid, control in controls.items():
        for tag in ('onup', 'ondown', 'onleft', 'onright', 'onclick'):
            moves += [(cid, tag, c, t) for c, t in _moves_into(control, tag)]
    assert moves, 'no moves found'
    for cid, tag, condition, target in moves:
        assert _ready(target) in condition, (cid, tag, condition)


def test_a_move_towards_a_list_that_is_not_ready_waits_for_it():
    """Down from the tabs, from the credits row to similar titles, from Kodi's own cast."""
    controls = _info()
    for source, target in (('5520', '5500'), ('5520', '5510'), ('5500', '5300'), ('50', '5300')):
        downs = _actions(controls[source], 'ondown')
        notes = [c for c, a in downs if a == 'SetProperty(nc.info.enter,{},home)'.format(target)]
        froms = [c for c, a in downs if a == 'SetProperty(nc.info.enter.from,$INFO[System.CurrentControlId],home)']
        assert len(notes) == 1, (source, target, downs)
        assert notes[0] in froms, (source, target)
        assert '![' + _ready(target) + ']' in notes[0], (source, target, notes[0])


def test_ok_on_a_tab_enters_its_list_once_it_is_in():
    """OK on another tab used to leave the focus on the tab: one more Down once the list was in."""
    tab = _include('CreditsTab').find('definition/control')
    clicks = _actions(tab, 'onclick')
    assert ('!Container($PARAM[list]).IsUpdating', 'SetProperty($PARAM[property],$PARAM[value],home)') in clicks
    now = '[$PARAM[active]] + $EXP[TmdbFresh$PARAM[list]] + !Container($PARAM[list]).IsUpdating + Integer.IsGreater(Container($PARAM[list]).NumItems,0)'
    assert (now, 'SetFocus($PARAM[list])') in clicks
    # also while the list loads: the focus on the tab started it (DESIGN.md: focus applies)
    wait = '![' + now + ']'
    assert (wait, 'SetProperty(nc.info.enter,$PARAM[list],home)') in clicks
    assert (wait, 'SetProperty(nc.info.enter.from,$PARAM[id],home)') in clicks


def _expression(name):
    for path in SKIN.glob('Includes*.xml'):
        for el in parse(path).iter('expression'):
            if el.get('name') == name:
                return el.text.strip()
    raise AssertionError(name)


def _written_out(condition):
    """Kodi registers timer conditions as they are (CSkinTimerManager): no $EXP[...]."""
    return re.sub(r'\$EXP\[(\w+)\]', lambda m: '[' + _expression(m.group(1)) + ']', condition)


def _timer(name):
    for timer in parse(SKIN / 'Timers.xml').iter('timer'):
        if timer.findtext('name') == name:
            return timer
    raise AssertionError(name)


def test_the_timer_moves_the_focus_once_the_list_is_in():
    timer = _timer('nc_info_enter')
    assert timer.findtext('start') == '!String.IsEmpty(Window(Home).Property(nc.info.enter))'
    stop = timer.findtext('stop')
    stayed = 'String.IsEqual(System.CurrentControlId,Window(Home).Property(nc.info.enter.from))'
    assert '!' + stayed in stop  # the focus moved on: forget it
    assert '!Window.IsActive(movieinformation)' in stop
    onstop = [(a.get('condition') or '', a.text) for a in timer.findall('onstop')]
    for cid in LISTS:
        ready = _written_out(_ready(cid))
        assert ('String.IsEqual(Window(Home).Property(nc.info.enter),{}) + {} + {}'.format(cid, ready, stayed),
                'SetFocus({})'.format(cid)) in onstop
        assert 'String.IsEqual(Window(Home).Property(nc.info.enter),{}) + {}'.format(cid, ready) in stop
    assert '$EXP' not in ET.tostring(timer, encoding='unicode')
    assert onstop[-2:] == [('', 'ClearProperty(nc.info.enter,home)'), ('', 'ClearProperty(nc.info.enter.from,home)')]


def test_a_new_page_forgets_a_waiting_move():
    onloads = [o.text for o in parse(SKIN / 'DialogVideoInfo.xml').findall('onload')]
    assert 'ClearProperty(nc.info.enter,home)' in onloads
