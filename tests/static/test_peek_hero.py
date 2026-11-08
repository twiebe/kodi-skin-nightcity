"""A page without spotlight keeps its hero, without buttons: it previews the title the cursor would
land on. On a title card it follows the card (FollowHero); elsewhere (the menu, a genre tab) it
shows the current title of the row that had the focus last, before any the first row with titles.
Down from the menu lands on that title. The generated parts are in Includes_Sections.xml
(tools/make_sections.py peek_parts)."""
import itertools
import re

import pytest

from conftest import ROOT, parse

PAGES = {'home': '92', 'movies': '94', 'shows': '95'}


def expressions():
    return {e.get('name'): e.text for name in ('Includes_Sections.xml', 'Includes_Home.xml')
            for e in parse(ROOT / '1080i' / name).iter('expression')}


def value(condition, atoms, exps):
    """Evaluate with $EXP spelled out and every other atom looked up in `atoms` (missing: False)."""
    for _ in range(6):
        condition = re.sub(r'\$EXP\[(\w+)\]', lambda m: '[' + exps[m.group(1)] + ']' if m.group(1) in exps else m.group(0), condition)
    atom = re.compile(r'\$EXP\[\w+\]|[A-Za-z][\w.]*\((?:[^()]|\([^()]*\))*\)(?:\.\w+\(\))*|\btrue\b|\bfalse\b')
    out = atom.sub(lambda m: ' {} '.format(atoms.get(m.group(0), m.group(0) == 'true')), condition)
    out = out.replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return bool(eval(out, {}))


def atoms_for(page, titles, kept, follows=False, off=True):
    """The page is shown, its spotlight off or on; `titles`: the slots whose row has a title now;
    `kept`: the slot the row property names (None: not set)."""
    base = PAGES[page]
    shown = {'home': 'String.IsEmpty(Window(Home).Property(nc.page))'}.get(page, 'String.IsEqual(Window(Home).Property(nc.page),{})'.format(page))
    setting = {'home': 'SpotlightSource', 'movies': 'nc.movies.spotlight', 'shows': 'nc.shows.spotlight'}[page]
    a = {shown: True, 'String.IsEqual(Skin.String({}),off)'.format(setting): off,
         'ControlGroup({}10).HasFocus()'.format(base): follows, 'String.IsEqual(ListItem.DBType,movie)': follows}
    for n in range(1, 9):
        row = '{}0{}'.format(base, n)
        has = n in titles
        a.update({'Control.IsVisible({})'.format(row): has, 'Integer.IsGreater(Container({}).NumItems,0)'.format(row): has,
                  'String.IsEqual(Container({}).ListItem.DBType,movie)'.format(row): has,
                  'String.IsEqual(Window(Home).Property(nc.peek.{}),{})'.format(page, row): kept == n})
    return a


def shown_rows(page, atoms, exps):
    return [n for n in range(1, 9) if value('$EXP[PeekRow{}0{}]'.format(PAGES[page], n), atoms, exps)]


@pytest.mark.parametrize('page', PAGES)
def test_the_kept_row_else_the_first_with_titles(page):
    exps = expressions()
    for titles in ({1, 2, 3}, {3, 5}, {2}, set()):
        for kept in (None, 1, 2, 3, 5):
            rows = shown_rows(page, atoms_for(page, titles, kept), exps)
            if not titles:
                assert rows == []
            elif kept in titles:
                assert rows == [kept], (titles, kept)
            else:
                assert rows == [min(titles)], (titles, kept)


@pytest.mark.parametrize('page', PAGES)
def test_no_preview_with_a_spotlight(page):
    exps = expressions()
    assert shown_rows(page, atoms_for(page, {1, 2}, 2, off=False), exps) == []


@pytest.mark.parametrize('page', PAGES)
def test_on_a_card_the_preview_is_the_card(page):
    """The row names itself when it gets the focus: on its card the preview shows that row's
    current title, the card; the hero that follows a card stays out (no swap, no fade)."""
    exps = expressions()
    assert shown_rows(page, atoms_for(page, {1, 2}, 2, follows=True), exps) == [2]
    assert not value('$EXP[SpotlightFollows]', atoms_for(page, {1, 2}, 2, follows=True), exps)


def test_rows_swap_without_a_fade_the_page_fades():
    sections = parse(ROOT / '1080i' / 'Includes_Sections.xml')
    for page in PAGES:
        include = next(i for i in sections.iter('include') if i.get('name') == 'PeekHeroes' + page.capitalize())
        page_group = include.find('control')
        assert page_group.findtext('visible') == '$EXP[PeekAny{}]'.format(page.capitalize())
        assert [i.text for i in page_group.findall('include')] == ['HeroSwapIn']
        for row in page_group.findall('control'):
            assert row.find('animation') is None and not [i for i in row.findall('include') if not i.get('content')]


def test_a_row_names_itself_on_a_title():
    """RowBox runs `peek` when the list gets the focus on a title; each slot passes its own row."""
    box = next(i for i in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('include') if i.get('name') == 'RowBox')
    focus = box.find('.//onfocus')
    assert focus.text == '$PARAM[peek]'
    assert sorted(re.findall(r'ListItem\.DBType,(\w+)', focus.get('condition'))) == ['episode', 'movie', 'season', 'tvshow']
    text = (ROOT / '1080i' / 'Includes_Sections.xml').read_text(encoding='utf-8')
    for page, base in PAGES.items():
        assert '<param name="peek" value="SetProperty(nc.peek.{},{}0$PARAM[n],home)"/>'.format(page, base) in text


def test_the_preview_is_the_follow_hero_for_a_row():
    """Each row's copy is FollowHero with Container(row).ListItem for ListItem: nothing reads the
    focused item any more."""
    sections = parse(ROOT / '1080i' / 'Includes_Sections.xml')
    for page, base in PAGES.items():
        include = next(i for i in sections.iter('include') if i.get('name') == 'PeekHeroes' + page.capitalize())
        for n, group in enumerate(include.find('control').findall('control'), 1):
            row = '{}0{}'.format(base, n)
            text = ''.join(t for el in group.iter() for t in [el.text or ''] + list(el.attrib.values()))
            assert not re.search(r'(?<![\w).])ListItem\.', text), row
            assert 'Container({}).ListItem'.format(row) in text
            assert not [c for c in group.iter('control') if c.get('id') not in (None, '0', group.get('id'))]


def test_built_only_for_a_page_without_spotlight():
    home = (ROOT / '1080i' / 'Home.xml').read_text(encoding='utf-8')
    for page, setting in (('Home', 'SpotlightSource'), ('Movies', 'nc.movies.spotlight'), ('Shows', 'nc.shows.spotlight')):
        for part in ('PeekHeroes', 'PeekFanarts'):
            assert '<include condition="String.IsEqual(Skin.String({}),off)">{}{}</include>'.format(setting, part, page) in home
