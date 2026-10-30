"""Where the ratings line takes its ratings from (docs/media-info-af3.md, "Ratings source").

A Ratings category in the skin settings: only TMDb Helper's ratings (on by default, the skin
bool nc.ratings.library stores off), the spotlight's ratings loaded without focus (off by
default, nc.ratings.spotlight), and one toggle per source. The heroes on Home read the ratings the skin service kept for
their current title (nc.hero.<container>.*), so they stay once fetched; the service also sets
TMDbHelper.WidgetContainer, the skin no longer does.
"""
import json
import re

import pytest

import navigation
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
STRINGS = ROOT / 'language' / 'resource.language.en_gb' / 'strings.po'
SOURCES = ['IMDb_Rating', 'TMDb_Rating', 'RottenTomatoes_Rating', 'RottenTomatoes_UserMeter',
           'MetaCritic_Rating', 'Trakt_Rating', 'Letterboxd_Rating', 'MDBList_Rating']
LIBRARY = 'Skin.HasSetting(nc.ratings.library)'
HEROES = [pytest.param('9000', '9030', id='movies'), pytest.param('9001', '9561', id='shows')]


def _string(number):
    text = STRINGS.read_text(encoding='utf-8')
    match = re.search(r'msgctxt "#{}"\nmsgid "([^"]*)"'.format(number), text)
    assert match, number
    return match.group(1)


def _control(window, cid):
    found = [c for c in window.iter('control') if c.get('id') == cid]
    assert len(found) == 1, cid
    return found[0]


def _visible(control):
    return ' + '.join(v.text for v in control.findall('visible'))


def _labels(line):
    return [(c.findtext('label') or '', _visible(c)) for c in line.iter('control') if c.get('type') == 'label']


def _lines():
    """Every ratings line of the skin: the heads of the info page, the two heroes."""
    info = navigation.load('DialogVideoInfo.xml')
    home = navigation.load('Home.xml')
    return [_control(info, '9046'), _control(info, '9043'), _control(home, '9030'), _control(home, '9561')]


def _toggle(cid):
    return _control(navigation.load('SkinSettings.xml'), cid)


def test_only_tmdb_helper_ratings_is_a_toggle_on_by_default():
    toggle = _toggle('621')
    assert toggle.get('type') == 'radiobutton'
    assert toggle.findtext('label') == '$LOCALIZE[31441]'
    assert toggle.findtext('selected') == '!' + LIBRARY
    assert 'Skin.ToggleSetting(nc.ratings.library)' in [a.text for a in toggle.findall('onclick')]


def test_spotlight_ratings_without_focus_is_a_toggle_off_by_default():
    toggle = _toggle('622')
    assert toggle.get('type') == 'radiobutton'
    assert toggle.findtext('label') == '$LOCALIZE[31443]'
    assert toggle.findtext('selected') == 'Skin.HasSetting(nc.ratings.spotlight)'
    assert 'Skin.ToggleSetting(nc.ratings.spotlight)' in [a.text for a in toggle.findall('onclick')]


# (toggle id, label, skin bool, on by default: the bool stores off)
TOGGLES = [('631', 31450, 'nc.ratings.hide.imdb', True), ('632', 31451, 'nc.ratings.show.tmdb', False),
           ('633', 31452, 'nc.ratings.hide.rt', True), ('634', 31453, 'nc.ratings.show.rtu', False),
           ('635', 31454, 'nc.ratings.show.mc', False), ('636', 31455, 'nc.ratings.show.trakt', False),
           ('637', 31456, 'nc.ratings.show.lb', False), ('638', 31457, 'nc.ratings.show.mdb', False)]
# the rating property of each toggle, in the order of the line
TOGGLE_SOURCES = ['IMDb_Rating', 'TMDb_Rating', 'RottenTomatoes_Rating', 'RottenTomatoes_UserMeter',
                  'MetaCritic_Rating', 'Trakt_Rating', 'Letterboxd_Rating', 'MDBList_Rating']


def _enabled(setting, on):
    return ('!' if on else '') + 'Skin.HasSetting({})'.format(setting)


def _descriptions():
    var = next(v for v in parse(SKIN / 'Variables.xml').iter('variable') if v.get('name') == 'SkinSettingsDesc')
    return [(v.get('condition'), v.text) for v in var.iter('value')]


def test_ratings_have_a_category_of_their_own():
    """Two settings and eight sources do not fit under the main menu rows: a Ratings category
    before Player."""
    window = navigation.load('SkinSettings.xml')
    categories = [c for c in _control(window, '9000') if c.get('type') == 'togglebutton']
    ids = [c.get('id') for c in categories]
    assert ids[-2:] == ['9007', '9006']
    ratings = categories[-2]
    assert ratings.findtext('label') == '$LOCALIZE[31445]'
    assert _string(31445) == 'Ratings'
    assert 'SetProperty(nc.hp.tab,ratings)' in [a.text for a in ratings.findall('onfocus')]
    area = _control(window, '800')
    assert 'String.IsEqual(Window.Property(nc.hp.tab),ratings)' in _visible(area)
    assert area.findtext('onleft') == '9007'
    assert [c.get('id') for c in area if c.tag == 'control'] == ['621', '622', '630']
    rights = [(a.get('condition'), a.text) for a in _control(window, '9000').findall('onright')]
    assert ('String.IsEqual(Window.Property(nc.hp.tab),ratings)', '800') in rights
    # the main menu keeps only its own rows and the look
    assert not [c for c in _control(window, '500').iter('control') if c.get('id') in ('620', '621', '622')]


def test_sources_are_toggles_in_the_lines_order():
    """IMDb and Rotten Tomatoes critics on by default, the others off."""
    window = navigation.load('SkinSettings.xml')
    group = _control(window, '630')
    assert any(c.findtext('label') == '$LOCALIZE[31446]' for c in group.iter('control') if c.get('type') == 'label')
    assert _string(31446) == 'Sources'
    toggles = [c for c in group.iter('control') if c.get('type') == 'radiobutton']
    assert [t.get('id') for t in toggles] == [t[0] for t in TOGGLES]
    names = ['IMDb', 'TMDb', 'Rotten Tomatoes critics', 'Rotten Tomatoes audience', 'Metacritic', 'Trakt',
             'Letterboxd', 'MDbList']
    for toggle, (cid, label, setting, on), name in zip(toggles, TOGGLES, names):
        assert toggle.findtext('label') == '$LOCALIZE[{}]'.format(label)
        assert _string(label) == name
        assert toggle.findtext('selected') == _enabled(setting, on)
        assert 'Skin.ToggleSetting({})'.format(setting) in [a.text for a in toggle.findall('onclick')]
        assert toggle.findtext('onleft') == '9007'
    # rows in a group have no grouplist neighbours: their own ways up and down
    assert toggles[0].findtext('onup') == '622'
    for above, below in zip(toggles, toggles[1:]):
        assert above.findtext('ondown') == below.get('id')
        assert below.findtext('onup') == above.get('id')


def test_rating_toggles_explain_themselves():
    """The description says what the spotlight setting costs, and where a source comes from."""
    values = dict(_descriptions())
    conditions = [c for c, _ in _descriptions()]
    for cid, desc in [('621', 31442), ('622', 31444), ('9007', 31447)] + [
            (t[0], 31460 + i) for i, t in enumerate(TOGGLES)]:
        key = 'Control.HasFocus({})'.format(cid)
        assert values.get(key) == '$LOCALIZE[{}]'.format(desc), cid
        assert conditions.index(key) < next(i for i, c in enumerate(conditions) if c and 'ControlGroup(500)' in c)
    assert 'online requests' in _string(31444)
    assert 'focus' in _string(31444)
    trakt, metacritic, mdblist = _string(31465), _string(31464), _string(31467)
    assert 'Trakt account' in trakt and 'not MDbList' in trakt
    assert 'weighted average' in metacritic and 'critic' in metacritic
    assert 'average' in mdblist
    assert 'Top 250' in _string(31460)
    for number in list(range(31441, 31448)) + list(range(31450, 31458)) + list(range(31460, 31468)):
        assert not re.search('[\\u2013\\u2014]', _string(number)), number


@pytest.mark.parametrize('n', range(len(TOGGLES)))
def test_lines_show_a_source_only_while_its_toggle_is_on(n):
    """Kodi's own IMDb and TMDb ratings (with "only TMDb Helper" off) follow the same toggles."""
    _, _, setting, on = TOGGLES[n]
    enabled = _enabled(setting, on)
    source = TOGGLE_SOURCES[n]
    own = {'IMDb_Rating': ['.Rating(imdb)]'], 'TMDb_Rating': ['.Rating(themoviedb)]', '.Rating(tmdb)]']}.get(source, [])
    for line in _lines():
        hits = [(label, visible) for label, visible in _labels(line)
                if re.search(r'Property\([\w.]*\.{}\)'.format(source), label)]
        assert len(hits) == 1, (line.get('id'), source, hits)
        assert enabled in hits[0][1], (line.get('id'), source)
        for text in own:
            mine = [(label, visible) for label, visible in _labels(line) if text in label]
            assert len(mine) == 1, (line.get('id'), text)
            assert enabled in mine[0][1], (line.get('id'), text)


def test_library_ratings_only_when_the_setting_allows():
    """Kodi's own ratings (the plain one Jellyfin syncs, Rating(imdb), Rating(tmdb)) only with
    "only TMDb Helper" off."""
    for line in _lines():
        own = [(label, visible) for label, visible in _labels(line) if re.search(r'ListItem\.Rating[\]()]', label)]
        assert len(own) == 4, own
        for label, visible in own:
            assert LIBRARY in visible, label
        # the line itself: no library rating keeps it up with the setting on
        assert 'ListItem.Rating,0.0) + {}]'.format(LIBRARY) in _visible(line), _visible(line)


@pytest.mark.parametrize('container, line', HEROES)
def test_heroes_read_the_ratings_kept_for_their_title(container, line):
    """The service copies TMDb Helper's ratings of the hero's title into nc.hero.<container>.*
    and keeps them: they only count while they belong to the title on screen."""
    hero = _control(navigation.load('Home.xml'), line)
    prop = 'Window(Home).Property(nc.hero.{}.{{}})'.format(container)
    key = ('Integer.IsEqual(Container({0}).ListItem.DBID,{1}) + String.IsEqual(Container({0}).ListItem.DBType,{2})'
           .format(container, prop.format('dbid'), prop.format('dbtype')))
    seen = set()
    for label, visible in _labels(hero):
        assert 'TMDbHelper.' not in label + visible, label
        for source in SOURCES:
            if prop.format(source) in label:
                assert key in visible, label
                seen.add(source)
    assert seen == set(SOURCES)
    assert 'IsUpdatingRatings' not in _visible(hero)


def test_info_page_still_reads_tmdb_helper():
    line = _control(navigation.load('DialogVideoInfo.xml'), '9046')
    assert any('Window(Home).Property(TMDbHelper.ListItem.IMDb_Rating)' in label for label, _ in _labels(line))


def test_skin_leaves_the_widget_container_to_the_service():
    """The service points TMDb Helper at the hero (scripts/nightcity.py hero_tick): on focus, or
    always with "load without focus"."""
    for path in SKIN.glob('*.xml'):
        text = path.read_text(encoding='utf-8')
        assert 'TMDbHelper.WidgetContainer' not in text, path.name


def test_show_hero_is_marked_for_the_service():
    """9301: the show hero is on screen (9300 the movie hero), the service asks for it."""
    home = navigation.load('Home.xml')
    group = _control(home, '9301')
    assert 'String.IsEqual(Window(Home).Property(nc.page),shows)' in _visible(group)
    assert any(c.get('id') == '9550' for c in group.iter('control'))


def test_ratings_line_fades_in_and_goes_at_once():
    for line in _lines():
        fades = [a for a in line.findall('animation') if a.get('effect') == 'fade']
        assert [a.text for a in fades] == ['Visible'], line.get('id')


def test_tmdb_helper_names_the_dbid_of_its_item():
    """TMDb Helper's base_dbid: the service only keeps ratings TMDb Helper has for the hero's
    title, not those of the title before."""
    extra = json.loads((ROOT / 'extras' / 'tmdbhelper' / 'baseitem.json').read_text(encoding='utf-8'))
    assert extra == {'dbid': {'infolabels': ['dbid']}}
