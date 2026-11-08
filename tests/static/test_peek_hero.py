"""A page whose spotlight stands still (interval "still") keeps its hero and its buttons, but shows
no title of the spotlight's own: it shows the title Down would land on, the current title of the
row that had the cursor last, before any the first row with titles. The buttons act on that title,
Left and Right only move between them, Down lands on it. On a title card the hero shows the card.
The generated parts are in Includes_Sections.xml (tools/make_sections.py peek_parts)."""
import re

import pytest

from conftest import ROOT, parse
from navigation import load

PAGES = {'home': '92', 'movies': '94', 'shows': '95'}
SOURCE = {'home': 'SpotlightSource', 'movies': 'nc.movies.spotlight', 'shows': 'nc.shows.spotlight'}
INTERVAL = {'home': 'SpotlightInterval', 'movies': 'nc.movies.interval', 'shows': 'nc.shows.interval'}
STILL = {'SpotlightInterval': 'off', 'nc.movies.interval': 'off', 'nc.shows.interval': 'off'}
# the hero's buttons per page: play, info, all movies or all shows
BUTTONS = {'home': ('9010', '9011'), 'movies': ('9010', '9011', '9012'), 'shows': ('9551', '9552', '9553')}
PEEK = {'home': 9360, 'movies': 9370, 'shows': 9380}


def expressions():
    return {e.get('name'): e.text for name in ('Includes_Sections.xml', 'Includes_Home.xml')
            for e in parse(ROOT / '1080i' / name).iter('expression')}


def value(condition, atoms, exps):
    """Evaluate with $EXP spelled out and every other atom looked up in `atoms` (missing: False)."""
    for _ in range(6):
        condition = re.sub(r'\$EXP\[(\w+)\]', lambda m: '[' + exps[m.group(1)] + ']' if m.group(1) in exps else m.group(0), condition)
    atom = re.compile(r'\$EXP\[\w+\]|[A-Za-z][\w.]*\((?:[^()]|\([^()]*\))*\)(?:\.\w+(?:\(\))?)*|\btrue\b|\bfalse\b')
    out = atom.sub(lambda m: ' {} '.format(atoms.get(m.group(0), m.group(0) == 'true')), condition)
    out = out.replace('[', '(').replace(']', ')').replace('+', ' and ').replace('|', ' or ').replace('!', ' not ')
    return bool(eval(out, {}))


def atoms_for(page, titles, kept, follows=False, still=True, off=False, types=None):
    """The page is shown, its spotlight still (or turning, or off); `titles`: the slots whose row
    has a title now; `kept`: the slot the row property names (None: not set); `types`: the
    DBType of the slots' current titles (default movie)."""
    base = PAGES[page]
    shown = {'home': 'String.IsEmpty(Window(Home).Property(nc.page))'}.get(page, 'String.IsEqual(Window(Home).Property(nc.page),{})'.format(page))
    a = {shown: True, 'String.IsEqual(Skin.String({}),off)'.format(SOURCE[page]): off,
         'String.IsEqual(Skin.String({}),off)'.format(INTERVAL[page]): still,
         'ControlGroup({}10).HasFocus()'.format(base): follows, 'String.IsEqual(ListItem.DBType,movie)': follows}
    for n in range(1, 9):
        row = '{}0{}'.format(base, n)
        has = n in titles
        kind = (types or {}).get(n, 'movie')
        a.update({'Control.IsVisible({})'.format(row): has, 'Integer.IsGreater(Container({}).NumItems,0)'.format(row): has,
                  'String.IsEqual(Container({}).ListItem.DBType,{})'.format(row, kind): has,
                  'String.IsEqual(Window(Home).Property(nc.peek.{}),{})'.format(page, row): kept == n})
    return a


def shown_rows(page, atoms, exps):
    return [n for n in range(1, 9) if value('$EXP[PeekRow{}0{}]'.format(PAGES[page], n), atoms, exps)]


def controls(skin):
    return {c.get('id'): c for c in load('Home.xml', skin).iter('control') if c.get('id')}


def fired(control, tag, atoms, exps):
    """The actions of `tag` whose condition holds."""
    return [a.text for a in control.findall(tag) if not a.get('condition') or value(a.get('condition'), atoms, exps)]


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
def test_no_row_title_while_the_spotlight_turns_or_is_off(page):
    exps = expressions()
    assert shown_rows(page, atoms_for(page, {1, 2}, 2, still=False), exps) == []
    assert shown_rows(page, atoms_for(page, {1, 2}, 2, off=True), exps) == []


@pytest.mark.parametrize('page', PAGES)
def test_on_a_card_the_hero_is_the_card(page):
    """The row names itself when it gets the focus: on its card the hero shows that row's current
    title, the card; the hero that follows a card stays out (no swap, no fade)."""
    exps = expressions()
    assert shown_rows(page, atoms_for(page, {1, 2}, 2, follows=True), exps) == [2]
    assert not value('$EXP[SpotlightFollows]', atoms_for(page, {1, 2}, 2, follows=True), exps)
    assert value('$EXP[SpotlightFollows]', atoms_for(page, {1, 2}, 2, follows=True, still=False), exps)


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
    # its own item: at onfocus Kodi's ListItem is still the control the focus came from, so a bare
    # ListItem never named the row (the hero stuck on the first row)
    assert focus.get('condition').count('Container($PARAM[id]).ListItem.DBType') == 4 and ' ListItem.DBType' not in focus.get('condition')


def test_only_the_shown_backdrop_draws():
    """A still page draws a backdrop per row; each look shows only its own (`shown`), else all
    rows' pictures lay over each other (Nightcity drew them all)."""
    for look in (ROOT / '1080i' / 'Includes_Look.xml', ROOT / 'skins' / 'confuse' / '1080i' / 'Includes_Look.xml'):
        inc = next(i for i in parse(look).iter('include') if i.get('name') == 'LookHomeFanart')
        uses = [v.text for v in inc.iter('visible')] + [p.get('value') for p in inc.iter('param') if p.get('name') == 'shown']
        assert '$PARAM[shown]' in uses, look
    text = (ROOT / '1080i' / 'Includes_Sections.xml').read_text(encoding='utf-8')
    for page, base in PAGES.items():
        assert '<param name="peek" value="SetProperty(nc.peek.{},{}0$PARAM[n],home)"/>'.format(page, base) in text


def test_the_hero_is_the_follow_hero_for_a_row():
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


def test_still_is_what_the_lists_and_the_includes_read():
    """The include conditions of Home.xml spell out SpotlightStill<page> (Kodi builds the window
    before any expression), an empty interval of movies or shows follows home's."""
    exps = expressions()
    home = (ROOT / '1080i' / 'Home.xml').read_text(encoding='utf-8')
    for page in PAGES:
        still = exps['SpotlightStill' + page.capitalize()]
        for part in ('PeekHeroes', 'PeekFanarts'):
            assert '<include condition="{}">{}{}</include>'.format(still, part, page.capitalize()) in home
        assert '!String.IsEqual(Skin.String({}),off)'.format(SOURCE[page]) in still
    follows = {'String.IsEmpty(Skin.String(nc.movies.interval))': True, 'String.IsEmpty(Skin.String(nc.shows.interval))': True,
               'String.IsEqual(Skin.String(SpotlightInterval),off)': True}
    assert value(exps['SpotlightStillMovies'], follows, exps) and value(exps['SpotlightStillShows'], follows, exps)


def test_built_only_for_a_still_page():
    """The 24 copies cost: Home builds a page's only while it stands still, and no spotlight list
    for it."""
    turning = controls({})
    assert not [i for i in turning if i[:3] in ('936', '937', '938')]
    still = controls(STILL)
    for page in PAGES:
        assert str(PEEK[page] + 1) in still
    for gone in ('9000', '9001', '9003', '9304', '9305', '9306'):
        assert gone not in still
    only_home = controls({'SpotlightInterval': 'off', 'nc.movies.interval': '15', 'nc.shows.interval': '15'})
    assert '9361' in only_home and '9371' not in only_home and '9381' not in only_home
    assert '9003' in only_home and '9001' in only_home and '9000' not in only_home
    # the movies and shows pages follow home's interval while theirs is empty
    follow = controls({'SpotlightInterval': 'off'})
    assert '9371' in follow and '9381' in follow
    off = controls(dict(STILL, SpotlightSource='off', **{'nc.movies.spotlight': 'off', 'nc.shows.spotlight': 'off'}))
    assert not [i for i in off if i[:3] in ('936', '937', '938')]


@pytest.mark.parametrize('page', PAGES)
def test_the_buttons_stay(page):
    still = controls(STILL)
    for button in BUTTONS[page] + ('9050' if page != 'shows' else '9550',):
        assert button in still


@pytest.mark.parametrize('page', PAGES)
def test_the_buttons_act_on_the_shown_title(page):
    """Play plays a movie or an episode (resuming), a show opens its next episode as on its card,
    anything else opens its page; info opens the page of the title, back returns to the button."""
    exps, c = expressions(), controls(STILL)
    play, info = (c[b] for b in BUTTONS[page][:2])
    row = '{}02'.format(PAGES[page])
    item = 'Container({}).ListItem.DBID'.format(row)
    cases = {'movie': ['NotifyAll(nightcity,play:movie:$INFO[{}]:resume:home)'.format(item)],
             'episode': ['NotifyAll(nightcity,play:episode:$INFO[{}]:resume:home)'.format(item)],
             'tvshow': ['NotifyAll(nightcity,next_episode:$INFO[{}])'.format(item)],
             'season': ['SetProperty(nc.spot.back,{},home)'.format(play.get('id')), 'SetFocus({})'.format(row), 'Action(Info)']}
    for kind, actions in cases.items():
        atoms = atoms_for(page, {1, 2}, 2, types={2: kind})
        atoms['String.IsEmpty({})'.format(item)] = False
        assert [a for a in fired(play, 'onclick', atoms, exps) if a != 'noop'] == actions, kind
        assert [a for a in fired(info, 'onclick', atoms, exps) if a != 'noop'] == [
            'SetProperty(nc.spot.back,{},home)'.format(info.get('id')), 'SetFocus({})'.format(row), 'Action(Info)'], kind
    # a card without a library id (TMDb's trending titles): its page, as OK on it
    atoms = atoms_for(page, {1, 2}, 2)
    atoms['String.IsEmpty({})'.format(item)] = True
    assert [a for a in fired(play, 'onclick', atoms, exps) if a != 'noop'] == cases['season']


@pytest.mark.parametrize('page', PAGES)
def test_left_and_right_only_move_between_the_buttons(page):
    exps, c = expressions(), controls(STILL)
    atoms = atoms_for(page, {1, 2}, 2)
    buttons = BUTTONS[page]
    for i, button in enumerate(buttons):
        left = fired(c[button], 'onleft', atoms, exps)
        right = fired(c[button], 'onright', atoms, exps)
        assert left == ([buttons[i - 1]] if i else []), (button, left)
        assert right == ([buttons[i + 1]] if i + 1 < len(buttons) else []), (button, right)


@pytest.mark.parametrize('page', PAGES)
def test_down_from_the_buttons_lands_on_the_shown_title(page):
    exps, c = expressions(), controls(STILL)
    rows = '{}10'.format(PAGES[page])
    for button in BUTTONS[page]:
        downs = fired(c[button], 'ondown', atoms_for(page, {1, 3}, 3), exps)
        assert downs == ['SetFocus({}03)'.format(PAGES[page])], (button, downs)
        assert fired(c[button], 'ondown', atoms_for(page, set(), None), exps) == [rows], button
    # up from the rows to the buttons, as with a spotlight
    assert c[rows].findtext('onup') == ('9550' if page == 'shows' else '9050')


@pytest.mark.parametrize('page', PAGES)
def test_a_turning_spotlight_keeps_its_ways(page):
    """With an interval the buttons step the spotlight and Down goes to the rows as before."""
    exps, c = expressions(), controls({})
    atoms = atoms_for(page, {1, 2}, 2, still=False)
    first, last = BUTTONS[page][0], BUTTONS[page][-1]
    lists = {'home': '9000', 'movies': '9003', 'shows': '9001'}
    assert 'Control.Move({},-1)'.format(lists[page]) in fired(c[first], 'onleft', atoms, exps)
    assert 'Control.Move({},1)'.format(lists[page]) in fired(c[last], 'onright', atoms, exps)
    assert fired(c[first], 'ondown', atoms, exps) == ['{}10'.format(PAGES[page])]


def test_the_pills_say_what_play_does():
    """The play pill of a still page names what its button does with the shown title."""
    variables = {v.get('name'): v for f in ('Variables.xml', 'Includes_Sections.xml')
                 for v in parse(ROOT / '1080i' / f).iter('variable')}
    exps = expressions()
    label = variables['PeekPlayLabel']
    for page in PAGES:
        row = '{}02'.format(PAGES[page])
        for kind, text in (('tvshow', '▶ $LOCALIZE[31106]'), ('movie', '▶ $LOCALIZE[31010]')):
            atoms = atoms_for(page, {2}, 2, types={2: kind})
            shown = next(v.text for v in label.findall('value') if not v.get('condition') or value(v.get('condition'), atoms, exps))
            assert shown == text, (page, kind)
        atoms = atoms_for(page, {2}, 2)
        atoms['Container({}).ListItem.IsResumable'.format(row)] = True
        shown = next(v.text for v in label.findall('value') if not v.get('condition') or value(v.get('condition'), atoms, exps))
        assert shown == '▶ $LOCALIZE[31043] $INFO[Container({}).ListItem.PercentPlayed]%'.format(row)
    for name in ('SpotlightPlayLabel', 'ShowSpotlightPlayLabel'):
        first = variables[name].find('value')
        assert first.text == '$VAR[PeekPlayLabel]' and 'PeekAny' in first.get('condition'), name


def test_no_chevrons_on_a_still_page():
    """The chevrons say Right moves the spotlight on: not on a still page."""
    more = next(i for i in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('include') if i.get('name') == 'SpotlightMore')
    assert more.find('.//visible').text == '!$EXP[SpotlightStillShown]'
