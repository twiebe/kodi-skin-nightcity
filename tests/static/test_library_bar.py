"""The position bar of the library grid: a faint rail at the far right with a mark of where the
grid stands; Right from the menu makes it a cursor that names the group, one press a group.
Up and Down move it and the grid follows, OK goes there, Left goes there by way of the menu, Back
goes back to the card it came from."""
import importlib.util

from conftest import ROOT, parse

WINDOW = 'Custom_1110_Library.xml'
BAR = '5200'


def _controls():
    return {c.get('id'): c for c in parse(ROOT / '1080i' / WINDOW).iter('control') if c.get('id')}


def _call():
    return next(i for i in parse(ROOT / '1080i' / WINDOW).iter('include') if i.get('content') == 'PillButton'
                and any(p.get('name') == 'id' and p.get('value') == BAR for p in i.findall('param')))


def _nightcity():
    spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _actions(element, tag):
    return [(e.get('condition'), (e.text or '').strip()) for e in element.findall(tag)]


def test_keys_of_the_bar():
    call = _call()
    assert _actions(call, 'onup') == [(None, 'NotifyAll(nightcity,lib_bar:step:-1)')]
    assert _actions(call, 'ondown') == [(None, 'NotifyAll(nightcity,lib_bar:step:1)')]
    assert _actions(call, 'onleft') == [(None, '5100')]
    assert _actions(call, 'onright') == [(None, 'noop')]
    # the second is what keeps the window open: without a control to go to Kodi takes Back as unhandled
    assert _actions(call, 'onback') == [(None, 'NotifyAll(nightcity,lib_bar:cancel)'), (None, '5000')]
    params = {p.get('name'): p.get('value') for p in call.findall('param')}
    assert params['onclick'] == 'NotifyAll(nightcity,lib_bar:ok)'
    assert params['onfocus'] == 'NotifyAll(nightcity,lib_bar:enter)'


def test_the_order_is_grid_menu_bar():
    """Right goes one step at a time and Left comes back the same way."""
    controls = _controls()
    assert _actions(controls['5000'], 'onright') == [(None, '5101')]
    menu = controls['5100']
    assert _actions(menu, 'onleft') == [(None, '5000')]
    assert _actions(menu, 'onright') == [('!String.IsEmpty(Window(Home).Property(nc.lib.bar))', BAR)]


def test_without_enough_groups_the_bar_takes_no_focus():
    params = {p.get('name'): p.get('value') for p in _call().findall('param')}
    assert params['visible'] == '!String.IsEmpty(Window(Home).Property(nc.lib.bar))'


def test_the_menu_tells_the_service_about_the_sort():
    call = [i for i in parse(ROOT / '1080i' / WINDOW).iter('include') if i.get('content') == 'PillButton']
    for cid in ('5101', '5102'):
        button = next(i for i in call if any(p.get('name') == 'id' and p.get('value') == cid for p in i.findall('param')))
        params = {p.get('name'): p.get('value') for p in button.findall('param')}
        assert params['onfocus'] == 'NotifyAll(nightcity,lib_bar:prepare)'
        clicks = [e.text for e in button.findall('onclick')]
        assert clicks[-1] == 'NotifyAll(nightcity,lib_bar:changed)', cid
    assert 'NotifyAll(nightcity,lib_bar:changed)' in [o.text for o in parse(ROOT / '1080i' / WINDOW).findall('onload')]


def test_the_rail_is_always_there_with_the_grids_scrollbar_as_its_mark():
    controls = _controls()
    assert controls['5000'].findtext('pagecontrol') == '5900'
    mark = controls['5900']
    assert mark.get('type') == 'scrollbar'
    assert mark.findtext('enable') == 'false'  # a mark, the remote never lands on it
    assert mark.findtext('visible') == '!Control.HasFocus({})'.format(BAR)
    rail = next(c for c in parse(ROOT / '1080i' / WINDOW).iter('control')
                if c.get('type') == 'image' and c.findtext('description') == 'rail')
    assert rail.find('visible') is None
    nc = _nightcity()
    for control in (mark, rail):
        assert (int(control.findtext('top')), int(control.findtext('height'))) == (nc.BAR_TOP, nc.BAR_HEIGHT)
    assert int(rail.findtext('left')) + int(rail.findtext('width')) <= nc.BAR_RIGHT


def test_the_bar_lies_at_the_far_right_inside_the_screen():
    nc = _nightcity()
    assert nc.BAR_RIGHT <= 1920
    assert nc.BAR_TOP + nc.BAR_HEIGHT + nc.BAR_BUTTON // 2 <= 1080


def test_the_service_knows_the_command():
    assert 'lib_bar' in _nightcity().COMMANDS


def test_the_window_outlives_its_controls():
    """A temporary xbmcgui.Window frees its controls with it: the next call on a control of
    Window(id).getControl(n) crashes Kodi. So never in one expression."""
    source = (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')
    assert '_window().getControl' not in source and 'Window(LIB_WINDOW_PYTHON).getControl' not in source


def test_the_grids_position_comes_from_its_info_label():
    """ControlList.getSelectedPosition answers -1 for a list of the skin: it looks at the items
    the script gave it."""
    assert 'getSelectedPosition' not in (ROOT / 'scripts' / 'nightcity.py').read_text(encoding='utf-8')


def test_every_back_key_reaches_the_bar():
    """Esc, a gamepad's back button and a right click send PreviousMenu, which <onback> never sees."""
    keymap = _nightcity().BACK_KEYMAP
    section = keymap[keymap.index('<window1110>'):keymap.index('</window1110>')]
    assert '<escape>Back</escape>' in section
    assert '<back>Back</back>' in section
    assert '<rightclick>Back</rightclick>' in section


def test_the_bar_is_invisible_without_the_focus():
    """Colour 0 is "no colour" to Kodi, which then draws the texture white (GUITexture.cpp): the
    bar left a white frame where the cursor had been. Alpha 0 with any other colour is see-through."""
    params = {p.get('name'): p.get('value') for p in _call().findall('param')}
    assert params['color'] == params['textcolor'] == '00FFFFFF'


def test_no_colour_of_the_skin_is_zero():
    for path in (ROOT / '1080i').glob('*.xml'):
        text = path.read_text(encoding='utf-8')
        assert '"00000000"' not in text and '>00000000<' not in text, path.name
