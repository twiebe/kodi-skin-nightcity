"""The position bar in the music library (MyMusicNav.xml): the same bar as in the library grid
(test_library_bar.py), for whichever of the two views shows, on the levels with a sort it can name."""
import importlib.util

from conftest import ROOT, parse

WINDOW = 'MyMusicNav.xml'
BAR = '5200'
READY = '!String.IsEmpty(Window(Home).Property(nc.lib.bar))'
TO_MENU = [(None, 'NotifyAll(nightcity,music_bar:prepare)'), (None, '9060')]


def _root():
    return parse(ROOT / '1080i' / WINDOW)


def _controls():
    return {c.get('id'): c for c in _root().iter('control') if c.get('id')}


def _call():
    return next(i for i in _root().iter('include') if i.get('content') == 'PillButton'
                and any(p.get('name') == 'id' and p.get('value') == BAR for p in i.findall('param')))


def _actions(element, tag):
    return [(e.get('condition'), (e.text or '').strip()) for e in element.findall(tag)]


def _nightcity():
    spec = importlib.util.spec_from_file_location('nightcity', ROOT / 'scripts' / 'nightcity.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_keys_of_the_bar():
    call = _call()
    assert _actions(call, 'onup') == [(None, 'NotifyAll(nightcity,music_bar:step:-1)')]
    assert _actions(call, 'ondown') == [(None, 'NotifyAll(nightcity,music_bar:step:1)')]
    assert _actions(call, 'onleft') == [(None, '9060')]
    assert _actions(call, 'onright') == [(None, 'noop')]
    assert _actions(call, 'onback') == [(None, 'NotifyAll(nightcity,music_bar:cancel)'),
                                        ('Control.IsVisible(51)', '51'), (None, '50')]
    params = {p.get('name'): p.get('value') for p in call.findall('param')}
    assert params['onclick'] == 'NotifyAll(nightcity,music_bar:ok)'
    assert params['onfocus'] == 'NotifyAll(nightcity,music_bar:enter)'
    assert params['visible'] == READY
    assert params['color'] == params['textcolor'] == '00FFFFFF'


def test_both_views_go_to_the_menu_and_show_on_the_rail():
    controls = _controls()
    for view in ('50', '51'):
        assert _actions(controls[view], 'onright') == TO_MENU
        assert controls[view].findtext('pagecontrol') == '5900'
    assert _actions(controls['9060'], 'onright') == [(READY, BAR)]


def test_the_menu_tells_the_service_about_a_new_sort():
    changed = 'NotifyAll(nightcity,music_bar:changed)'
    assert changed in [o.text for o in _root().findall('onload')]
    for cid in ('2', '3'):
        call = next(i for i in _root().iter('include') if i.get('content') == 'ListButton'
                    and any(p.get('name') == 'id' and p.get('value') == cid for p in i.findall('param')))
        assert {p.get('name'): p.get('value') for p in call.findall('param')}['onclick'] == changed
    assert changed in [e.text for e in _controls()['4'].findall('onclick')]


def test_the_column_makes_way_for_the_widest_cursor():
    nc = _nightcity()
    column = next(c for c in _root().iter('control')
                  if c.get('type') == 'group' and c.findtext('description') == 'column')
    ids = {c.get('id') for c in column.iter('control')}
    assert '9060' in ids and BAR not in ids and '50' not in ids
    animation = next(a for a in column.findall('animation') if a.text == 'Conditional')
    assert animation.get('condition') == 'Control.HasFocus({})'.format(BAR)
    scale = int(animation.get('end')) / 100
    center = int(animation.get('center').split(',')[0])
    menu = _controls()['9060']
    left, right = int(menu.findtext('left')), int(menu.findtext('left')) + int(menu.findtext('width'))
    assert center + (right - center) * scale <= nc.BAR_RIGHT - nc.bar_width('2026')
    panel = _controls()['51']
    assert center + (left - center) * scale >= int(panel.findtext('left')) + int(panel.findtext('width'))


def test_every_back_key_reaches_the_bar_and_leaves_the_window_elsewhere():
    """In the music library these keys leave the window, Back only goes up a folder. The service
    decides, so that they stay what they were everywhere but on the bar."""
    keymap = _nightcity().BACK_KEYMAP
    section = keymap[keymap.index('<music>'):keymap.index('</music>')]
    for key in ('escape', 'back', 'rightclick'):
        assert '<{0}>NotifyAll(nightcity,music_bar:escape)</{0}>'.format(key) in section


def test_the_service_knows_the_command():
    assert 'music_bar' in _nightcity().COMMANDS
