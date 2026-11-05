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


def test_the_column_stands_clear_of_the_widest_cursor_with_no_animation():
    nc = _nightcity()
    controls = _controls()
    root = _root()
    limit = nc.BAR_RIGHT - nc.bar_width('Nov 26') + 10
    menu = controls['9060']
    panel_end = int(controls['51'].findtext('left')) + int(controls['51'].findtext('width'))
    assert int(menu.findtext('left')) >= panel_end
    assert int(menu.findtext('left')) + int(menu.findtext('width')) - 10 <= limit
    for row in menu.findall('control'):
        assert int(row.findtext('width')) == int(menu.findtext('width'))
    for call in menu.findall('include'):
        width = next(p.get('value') for p in call.findall('param') if p.get('name') == 'width')
        assert width == menu.findtext('width')
    pane = next(c for c in root.iter('control') if c.get('type') == 'group' and c.find('left') is not None
                and 'Control.IsVisible(50)' in (c.findtext('visible') or ''))
    assert int(pane.findtext('left')) + 360 <= limit
    assert not [a for a in root.iter('animation') if '5200' in (a.get('condition') or '')]


def test_every_back_key_reaches_the_bar_and_leaves_the_window_elsewhere():
    """In the music library these keys leave the window, Back only goes up a folder. The service
    decides, so that they stay what they were everywhere but on the bar."""
    keymap = _nightcity().BACK_KEYMAP
    section = keymap[keymap.index('<music>'):keymap.index('</music>')]
    for key in ('escape', 'back', 'rightclick'):
        assert '<{0}>NotifyAll(nightcity,music_bar:escape)</{0}>'.format(key) in section


def test_the_service_knows_the_command():
    assert 'music_bar' in _nightcity().COMMANDS
