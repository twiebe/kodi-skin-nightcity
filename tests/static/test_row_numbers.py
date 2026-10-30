"""Row numbers on the pages of Home (DESIGN.md, pink: order): every row heading of the home,
movies, shows and music pages starts with a two-digit pink number like the rail numbers of the
settings. The spotlight counts as 00 and has no heading, so the first row shown is 01, also on a
page without spotlight. The numbers count the rows that are shown: a hidden row (an empty slot, a
row without items) takes no number. Each row's number is a variable whose values test, by
Control.IsVisible, how many of the rows above it are shown (tools/make_sections.py)."""
import itertools
import re
import xml.etree.ElementTree as ET

import pytest

from conftest import ROOT, parse
from navigation import load

# page -> grouplist of its rows and the group ids of its rows, top to bottom
PAGES = {'home': ('9210', ['921{}'.format(n) for n in range(1, 9)]),
         'movies': ('9410', ['941{}'.format(n) for n in range(1, 9)]),
         'shows': ('9510', ['951{}'.format(n) for n in range(1, 9)]),
         'music': ('9810', ['981{}'.format(n) for n in range(1, 6)])}
NUMBER = re.compile(r'^\[COLOR accent2\]\$VAR\[([^\]]+)\]\[/COLOR\](?:  \[UPPERCASE\].*\[/UPPERCASE\])?$')
SPOTLIGHT_OFF = {'SpotlightSource': 'off', 'nc.movies.spotlight': 'off', 'nc.shows.spotlight': 'off'}
# every section in a slot, so the genre rows (tabs instead of a title) are there too
FULL = {'nc.movies.slot5': 'genres', 'nc.shows.slot5': 'genres', 'nc.home.slot5': 'genres',
        'nc.home.slot6': 'favourites', 'nc.movies.slot6': 'sets', 'nc.shows.slot6': 'trending'}


def definitions():
    variables, expressions = {}, {}
    for path in sorted((ROOT / '1080i').glob('*.xml')):
        for el in parse(path):
            if el.tag == 'variable':
                variables[el.get('name')] = [(v.get('condition'), v.text or '') for v in el.findall('value')]
            elif el.tag == 'expression':
                expressions[el.get('name')] = el.text
    return variables, expressions


VARIABLES, EXPRESSIONS = definitions()


def flatten(condition):
    """The condition with every $EXP replaced by its expression, as Kodi does on load."""
    while '$EXP[' in condition:
        condition = re.sub(r'\$EXP\[([^\]]+)\]', lambda m: '[{}]'.format(EXPRESSIONS[m.group(1)]), condition)
    return condition


def holds(condition, shown):
    text = re.sub(r'Control\.IsVisible\((\d+)\)', lambda m: ' {} '.format(m.group(1) in shown), flatten(condition))
    assert not re.search(r'[A-Za-z]+\.', text), text
    text = text.replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return bool(eval(text, {}))


def number(variable, shown):
    for condition, value in VARIABLES[variable]:
        if condition is None or holds(condition, shown):
            return value
    return ''


def headings(page, skin=None):
    """[(group id, variable of its number, label)] of the rows the page's grouplist holds."""
    grouplist = next(c for c in load('Home.xml', skin).iter('control') if c.get('id') == PAGES[page][0])
    found = []
    for group in grouplist.findall('control'):
        if group.findtext('visible') == 'false':
            continue
        labels = [c for c in group.iter('control') if c.get('type') == 'label' and NUMBER.match(c.findtext('label') or '')]
        assert len(labels) == 1, (page, group.get('id'))
        found.append((group.get('id'), NUMBER.match(labels[0].findtext('label')).group(1), labels[0]))
    return found


@pytest.mark.parametrize('skin', [{}, SPOTLIGHT_OFF, FULL], ids=['defaults', 'spotlight-off', 'all-sections'])
@pytest.mark.parametrize('page', PAGES)
def test_every_row_heading_has_a_pink_number(page, skin):
    """Like the rail headings of the settings: pink number, two spaces, the caps title."""
    rail = next(i for i in parse(ROOT / '1080i' / 'Includes_Settings.xml') if i.get('name') == 'SettingsRailHeading')
    rail = rail.find('definition/control')
    found = headings(page, skin)
    assert found
    for group, variable, label in found:
        assert variable == 'RowNumber_{}_{}'.format(page, PAGES[page][1].index(group) + 1)
        # a number alone stands before tabs and takes their font (test_genre_row_...)
        if not label.findtext('label').endswith('[/COLOR]'):
            assert label.findtext('font') == rail.findtext('font')
        assert label.findtext('textcolor') == rail.findtext('textcolor')


@pytest.mark.parametrize('page', PAGES)
def test_numbers_count_the_shown_rows(page):
    """For every combination of shown and hidden rows the shown ones read 01, 02, ... in order;
    with the spotlight on or off alike (it is 00 and has no heading)."""
    groups = PAGES[page][1]
    for mask in itertools.product((False, True), repeat=len(groups)):
        shown = {g for g, on in zip(groups, mask) if on}
        got = [number('RowNumber_{}_{}'.format(page, n), shown) for n, g in enumerate(groups, 1) if g in shown]
        assert got == ['{:02d}'.format(i) for i in range(1, len(shown) + 1)], (page, sorted(shown))


def test_genre_row_puts_its_number_before_the_tabs():
    """A genre row has tabs where the title would be: the number stands in front of them, the
    tabs start where the title of a row starts after its number. The number sits on the line
    of the tab labels: same font, top, height and vertical alignment as a tab."""
    for page, base in (('movies', '94'), ('shows', '95')):
        group = next(g for g in load('Home.xml', FULL).iter('control') if g.get('id') == base + '15')
        tabs = next(c for c in group.iter('control') if c.get('id') == base + '30')
        label = next(c for c in group.iter('control') if NUMBER.match(c.findtext('label') or ''))
        assert label.findtext('label').endswith('[/COLOR]')
        assert int(label.findtext('left')) == 64
        assert int(tabs.findtext('left')) > 64
        tab = next(c for c in tabs.iter('control') if c.get('id') == base + '31')
        assert int(label.findtext('top')) == int(tabs.findtext('top')) + int(tab.findtext('top') or 0)
        for tag in ('height', 'font', 'aligny'):
            assert label.findtext(tag) == tab.findtext(tag), (page, tag)
