"""Home's footer while the focus is in the top line: Down and where it leads into the shown page,
and on the movies and shows tabs OK, all of them (HintHomeDown, HintHomeOk in Variables.xml).
The label is the first value of each variable whose condition holds, read the way Kodi reads
it."""
import os
import xml.etree.ElementTree as ET

import pytest

from conftest import builtin, cond, info, screenshot, wait_for

pytestmark = pytest.mark.e2e

SKIN = os.path.join(os.path.dirname(__file__), '..', '..', '1080i')
HINT = 9195


def _values(name):
    root = ET.parse(os.path.join(SKIN, 'Variables.xml')).getroot()
    var = next(v for v in root.iter('variable') if v.get('name') == name)
    return [(v.get('condition'), v.text) for v in var.findall('value')]


def resolved(name):
    """The value Kodi shows of variable `name`: the first whose condition holds."""
    values = _values(name)
    states = cond(*[c for c, _ in values if c])
    return next((text for c, text in values if not c or states[c]), None)


def focus(control_id):
    builtin('SetFocus({})'.format(control_id))
    wait_for('Control.HasFocus({})'.format(control_id))


@pytest.fixture
def top_line(home):
    builtin('ActivateWindow(home)')
    wait_for('Window.IsActive(home)')
    yield
    focus(9101)


# tab: (Down leads to, OK leads to) with kodi-dev's spotlights on
TABS = {9101: ('$LOCALIZE[31100]', None), 9102: ('$LOCALIZE[31100]', 'all movies'),
        9103: ('$LOCALIZE[31100]', 'all shows'), 9104: ('$LOCALIZE[31141]', None),
        9109: ('$LOCALIZE[31320]', 'settings')}


@pytest.mark.parametrize('tab', list(TABS))
def test_the_footer_names_where_down_and_ok_lead(top_line, tab):
    focus(tab)
    wait_for('Control.IsVisible({})'.format(HINT))
    down, ok = TABS[tab]
    assert resolved('HintHomeDown') == down
    ok_hint = resolved('HintHomeOk')
    if ok is None:
        assert ok_hint is None
    else:
        assert ok_hint == '   [COLOR state_text]OK[/COLOR] $LOCALIZE[{}]'.format({'all movies': 31101, 'all shows': 31102, 'settings': 5}[ok])
    screenshot('home-hint-{}'.format(tab))


def test_the_footer_leaves_with_the_top_line(top_line):
    focus(9102)
    wait_for('Control.IsVisible({})'.format(HINT))
    builtin('Action(Down)')
    wait_for('!ControlGroup(9100).HasFocus()')
    wait_for('!Control.IsVisible({})'.format(HINT))


def test_without_a_spotlight_down_leads_to_the_rows(top_line):
    """The hint follows the setting itself (Kodi rebuilds Home after a change in the settings,
    this test only reads the variable)."""
    was = info('Skin.String(nc.movies.spotlight)')['Skin.String(nc.movies.spotlight)']
    builtin('Skin.SetString(nc.movies.spotlight,off)')
    try:
        focus(9102)
        wait_for('String.IsEqual(Skin.String(nc.movies.spotlight),off)')
        assert resolved('HintHomeDown') == '$LOCALIZE[31224]'
    finally:
        builtin('Skin.SetString(nc.movies.spotlight,{})'.format(was) if was else 'Skin.Reset(nc.movies.spotlight)')
