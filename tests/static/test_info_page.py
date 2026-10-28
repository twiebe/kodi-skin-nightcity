"""Final review fixes on the info page and the spotlight play button."""
from conftest import ROOT, parse

SKIN = ROOT / '1080i'


def control(path, cid):
    found = parse(SKIN / path).find('.//control[@id="{}"]'.format(cid))
    assert found is not None, cid
    return found


def onclicks(path, cid):
    return [(o.get('condition') or '', o.text or '') for o in control(path, cid).iter('onclick')]


def include_param(path, cid, name):
    for inc in parse(SKIN / path).iter('include'):
        params = {p.get('name'): p.get('value') for p in inc.findall('param')}
        if params.get('id') == str(cid):
            return params.get(name), [(o.get('condition') or '', o.text or '') for o in inc.iter('onclick')]
    raise AssertionError(cid)


def test_episode_play_waits_for_preselection():
    # until info_select is done, 5100 still points at the first episode of the first season tab
    for cid in (9001, 9002):
        _, clicks = include_param('DialogVideoInfo.xml', cid, 'id')
        episode = [text for _, text in clicks if 'play:episode' in text]
        assert episode and all('$VAR[InfoEpisodeDBID]' in text for text in episode), cid
        assert not any('Container(5100).ListItem.DBID' in text for _, text in clicks), cid


def test_play_falls_back_to_the_file():
    _, clicks = include_param('DialogVideoInfo.xml', 9001, 'id')
    assert any('PlayMedia($ESCINFO[ListItem.FileNameAndPath])' in text for _, text in clicks)
    # library actions only fire with a database id (the page's, or its library copy's on a TMDb
    # page), the file fallback only without one
    for cond, text in clicks:
        if 'NotifyAll(nightcity,' in text and 'Container(5901)' not in text:
            assert '!String.IsEmpty(ListItem.DBID)' in cond, text


def test_similar_row_hidden_while_loading():
    assert 'IsUpdating' not in control('DialogVideoInfo.xml', 5402).find('visible').text


def test_similar_movie_opens_in_the_chain():
    """Action(Info) would close the page; a similar movie opens its page in TMDb Helper's chain
    (test_tmdb_navigation.py)."""
    calls = [c for c in control('DialogVideoInfo.xml', 5300).iter('include') if c.get('content') == 'ChainClick']
    assert len(calls) == 1
    assert not any('Action(Info)' in text for _, text in onclicks('DialogVideoInfo.xml', 5300))


def test_spotlight_play_resumes_through_script():
    value, _ = include_param('Includes_Home.xml', 9010, 'onclick')
    assert 'NotifyAll(nightcity,play:movie:$INFO[Container(9000).ListItem.DBID]:resume)' in value


def test_episode_number_stands_beside_the_title():
    """On the still the number got lost on bright pictures: it stands before the title, in the
    accent colour, and the still stays free."""
    card = next(i for i in parse(SKIN / 'Includes_Info.xml').iter('include')
                if i.get('name') == 'EpisodeCard')
    assert not [c for c in card.iter('control') if c.findtext('font') == 'font_num_small']
    titles = [c for c in card.iter('control') if c.findtext('top') == '192']
    assert [c.findtext('label') for c in titles] == [
        '[COLOR accent]$VAR[EpisodeCardNum][/COLOR]  $INFO[ListItem.Title]',
        '$VAR[EpisodeCardNum]  $INFO[ListItem.Title]']
    var = next(v for v in parse(SKIN / 'Variables.xml').iter('variable')
               if v.get('name') == 'EpisodeCardNum')
    assert [(v.get('condition'), v.text) for v in var.findall('value')] == [
        ('Integer.IsLess(ListItem.Episode,10)', 'E0$INFO[ListItem.Episode]'),
        (None, 'E$INFO[ListItem.Episode]')]
