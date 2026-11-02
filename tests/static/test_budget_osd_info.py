"""Budget and box office on a movie's info page, and an info button in the player's controls."""
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
NOT_ZERO = '!String.IsEqual({0},$0)'


def _details():
    row = None
    for g in parse(SKIN / 'DialogVideoInfo.xml').iter('control'):
        if g.get('type') == 'grouplist' and g.findtext('left') == '1400' and g.findtext('top') == '116':
            row = g
    assert row is not None
    return [{p.get('name'): p.get('value') for p in i.findall('param')} for i in row.findall('include')
            if i.get('content') == 'InfoDetail']


def test_budget_and_box_office_after_the_age_rating():
    """TMDb Helper has both, formatted ($63,000,000): a TMDb page carries them on its item, for a
    library movie its service has them for the page (TMDbHelper.ListItem.*, as the ratings line).
    Shown only with a value other than $0."""
    rows = _details()
    keys = [r['key'] for r in rows]
    assert keys[:5] == ['$LOCALIZE[31126]', '$LOCALIZE[31127]', '$LOCALIZE[31128]', '$LOCALIZE[31129]', '$LOCALIZE[31136]']
    for key, prop, service in (('$LOCALIZE[31471]', 'ListItem.Property(budget)', 'Window(Home).Property(TMDbHelper.ListItem.Budget)'),
                               ('$LOCALIZE[31472]', 'ListItem.Property(revenue)', 'Window(Home).Property(TMDbHelper.ListItem.Revenue)')):
        own, theirs = [r for r in rows if r['key'] == key]
        assert own['value'] == prop and theirs['value'] == service, key
        assert own['visible'] == '!String.IsEmpty({0}) + {1}'.format(prop, NOT_ZERO.format(prop)), key
        assert theirs['visible'].startswith('String.IsEmpty({0}) + !String.IsEmpty({1}) + {2}'.format(
            prop, service, NOT_ZERO.format(service))), key
    assert keys[5:] == ['$LOCALIZE[31471]'] * 2 + ['$LOCALIZE[31472]'] * 2


def test_strings():
    po = (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    assert 'msgctxt "#31471"\nmsgid "budget"\n' in po and 'msgctxt "#31472"\nmsgid "box office"\n' in po


def test_info_button_in_the_player_left_of_subtitles():
    """Info opens the page of what plays (scripts/nightcity.py player_info): a library movie or
    episode, else TMDb Helper's page of the title it recognised. Shown when there is one."""
    row = next(g for g in parse(SKIN / 'VideoOSD.xml').iter('control') if g.get('id') == '620')
    pills = [i for i in row.findall('include') if i.get('content') == 'PillButton']
    params = [{p.get('name'): p.get('value') for p in i.findall('param')} for i in pills]
    assert [p['id'] for p in params][:2] == ['612', '605']
    info = params[0]
    assert info['label'] == '$LOCALIZE[31011]'
    assert info['onclick'] == 'NotifyAll(nightcity,player_info)'
    assert info['visible'] == ('String.IsEmpty(Window(Home).Property(nc.osd.more)) + [Integer.IsGreater(VideoPlayer.DBID,0)'
                               ' | !String.IsEmpty(Window(Home).Property(TMDbHelper.Player.TMDb_ID))'
                               ' | !String.IsEmpty(Window(Home).Property(TMDbHelper.Player.TVShow.TMDb_ID))]')


def test_service_values_only_for_the_page_they_belong_to():
    """TMDb Helper's service follows the page a moment late: going from one film to the next its
    values were the film's before for a while. They show once they belong to the page: its
    library id (TMDbHelper.ListItem.base_dbid), or its title without one."""
    rows = _details()
    guard = ('[[Integer.IsGreater(ListItem.DBID,0) + String.IsEqual(Window(Home).Property(TMDbHelper.ListItem.base_dbid),ListItem.DBID)]'
             ' | [String.IsEmpty(ListItem.DBID) + String.IsEqual(Window(Home).Property(TMDbHelper.ListItem.base_label),ListItem.Label)]]')
    for row in rows:
        if 'TMDbHelper.ListItem' in row['value']:
            assert row['visible'].endswith(' + ' + guard), row['key']
