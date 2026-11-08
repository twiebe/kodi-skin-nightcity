"""The home page can be hidden like the other pages of the main menu (movies, shows, music, search),
and the last page shown cannot: its switch is off limits. Where Kodi opens Home without a page
(startup, the Home key, the icon next to the clock wrapping round) the first page shown takes the
place of home. Checked for every combination of hidden pages, with and without music."""
import itertools
import re

import pytest

from conftest import ROOT, parse
from navigation import evaluate

PAGES = ('home', 'movies', 'shows', 'music', 'search')  # in the order of the menu
TABS = {'home': '9101', 'movies': '9102', 'shows': '9103', 'music': '9107', 'search': '9104'}
TOGGLES = {'home': '510', 'movies': '511', 'shows': '512', 'music': '516', 'search': '513'}


def expressions():
    out = {}
    for path in (ROOT / '1080i').glob('Includes*.xml'):
        for el in parse(path).iter('expression'):
            out[el.get('name')] = el.text
    return out


def resolve(condition):
    """$EXP[...] spelled out, the music library as a skin bool the evaluator knows."""
    exps = expressions()
    for _ in range(5):
        condition = re.sub(r'\$EXP\[(\w+)\]', lambda m: '[' + exps[m.group(1)] + ']', condition)
    return condition.replace('Library.HasContent(music)', 'Skin.HasSetting(test.music)')


def states():
    for hidden in itertools.product((False, True), repeat=len(PAGES)):
        for music in (True, False):
            skin = {'nc.menu.hide.' + p: h for p, h in zip(PAGES, hidden)}
            skin['test.music'] = music
            shown = [p for p, h in zip(PAGES, hidden) if not h and (p != 'music' or music)]
            if shown:
                yield skin, shown


def holds(condition, skin):
    """No music plays (Player.HasAudio) in these states."""
    if not condition:
        return True
    return evaluate(resolve(condition).replace('Player.HasAudio', 'Skin.HasSetting(test.audio)'), skin)


def first_focus(actions, skin):
    """The id of the first focus action whose condition holds (Kodi moves to the first)."""
    for el in actions:
        if holds(el.get('condition'), skin) and re.fullmatch(r'\d+|SetFocus\(\d+\)', el.text.strip()):
            return re.search(r'\d+', el.text).group(0)


def main_menu():
    return next(i for i in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('include') if i.get('name') == 'MainMenu')


def test_every_page_has_a_switch_home_first():
    area = next(c for c in parse(ROOT / '1080i' / 'SkinSettings.xml').iter('include')
                if c.get('content') == 'SkinSettingsArea' and any(p.get('value') == '500' for p in c.findall('param')))
    toggles = [{p.get('name'): p.get('value') for p in t.findall('param')}
               for t in area.findall('include') if t.get('content') == 'SkinSettingsToggle']
    pages = [t for t in toggles if t['setting'].startswith('nc.menu.hide.')]
    assert [t['setting'] for t in pages] == ['nc.menu.hide.' + p for p in PAGES]
    assert [t['id'] for t in pages] == [TOGGLES[p] for p in PAGES]
    assert pages[0]['label'] == '$LOCALIZE[31477]'


@pytest.mark.parametrize('page', PAGES)
def test_the_last_page_shown_cannot_be_hidden(page):
    area = parse(ROOT / '1080i' / 'SkinSettings.xml')
    toggle = next(t for t in area.iter('include') if t.get('content') == 'SkinSettingsToggle'
                  and any(p.get('value') == 'nc.menu.hide.' + page for p in t.findall('param')))
    enable = {p.get('name'): p.get('value') for p in toggle.findall('param')}['enable']
    for skin, shown in states():
        others = [p for p in shown if p != page]
        assert holds(enable, skin) == (page not in shown or bool(others)), (page, skin)


def test_tabs_show_with_their_page():
    params = {i.find("param[@name='id']").get('value'): {p.get('name'): p.get('value') for p in i.findall('param')}
              for i in main_menu().iter('include') if i.get('content') == 'MenuButton'}
    for skin, shown in states():
        visible = [p for p in PAGES if holds(params[TABS[p]].get('visible'), skin)]
        assert visible == shown, skin


def test_gaps_stay_even_without_home():
    """One gap between two tabs, never two: the leading gaps, then tab, gap, tab ... and the
    trailing one."""
    items = [(i.get('content'), {p.get('name'): p.get('value') for p in i.findall('param')})
             for i in main_menu().find('control').findall('include') if i.get('content') in ('MenuButton', 'TabGap')]
    for skin, shown in states():
        seq = ['gap' if kind == 'TabGap' else 'tab' for kind, p in items if holds(p.get('visible'), skin)]
        inner = ''.join('g' if s == 'gap' else 't' for s in seq).strip('g')
        assert 'gg' not in inner and inner.count('t') == len(shown), (skin, seq)
        assert seq[:3] == ['gap'] * 3 and seq[3] == 'tab' and seq[-1] == 'gap' and seq[-2] == 'tab', (skin, seq)


def test_first_page_expressions():
    exps = expressions()
    for skin, shown in states():
        firsts = [p for p in PAGES if holds(exps['PageFirst' + p.capitalize()], skin)]
        assert firsts == [shown[0]], skin


def test_home_key_goes_to_the_first_page():
    window = parse(ROOT / '1080i' / 'Custom_1160_HomeKey.xml')
    for skin, shown in states():
        assert first_focus(window.findall('onload'), skin) == TABS[shown[0]], skin


def test_home_without_a_page_opens_the_first_page():
    """Startup and a hidden page leave Home without a page shown: the first page takes it."""
    window = parse(ROOT / '1080i' / 'Home.xml')
    for skin, shown in states():
        loads = window.findall('onload')
        if shown[0] == 'home':
            assert first_focus(loads, skin) is None, skin  # the window's own default stays
        else:
            assert first_focus(loads, skin) == TABS[shown[0]], skin
            assert any(holds(el.get('condition'), skin) and el.text == 'SetProperty(nc.page,{},home)'.format(shown[0])
                       for el in loads), skin


def test_the_icon_wraps_round_to_the_first_page():
    icon = next(c for c in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('control') if c.get('id') == '9109')
    for skin, shown in states():
        assert first_focus(icon.findall('onright'), skin) == TABS[shown[0]], skin
        assert first_focus(icon.findall('onleft'), skin) == TABS[shown[-1]], skin
