"""What the info page shows only on Kodi 22 (KodiPiers): Kodi 21 keeps its page as it was."""
from conftest import ROOT, parse

ICON = '$EXP[KodiPiers] + !String.IsEmpty(ListItem.ParentalRatingIcon)'


def _info():
    return parse(ROOT / '1080i' / 'DialogVideoInfo.xml')


def _details(key):
    for inc in _info().iter('include'):
        params = dict((p.get('name'), p.get('value')) for p in inc.iter('param'))
        if params.get('key') == key:
            yield inc.get('content'), params


def test_the_rating_shows_kodi_22s_icon_and_the_code_without_it():
    """ListItem.ParentalRatingIcon (Kodi 22, items with a rating icon such as PVR ones): the icon
    after the key; Kodi 21 and items without an icon keep the code as text (ListItem.Mpaa)."""
    shown = dict(_details('$LOCALIZE[31136]'))
    assert shown['InfoDetail'] == {'key': '$LOCALIZE[31136]', 'value': 'ListItem.Mpaa',
                                   'visible': '![{}]'.format(ICON)}
    assert shown['InfoDetailIcon'] == {'key': '$LOCALIZE[31136]', 'icon': 'ListItem.ParentalRatingIcon',
                                       'visible': ICON}


def test_the_icon_line_has_the_height_of_a_text_line():
    inc = next(i for i in parse(ROOT / '1080i' / 'Includes_Info.xml').iter('include')
               if i.get('name') == 'InfoDetailIcon')
    group = inc.find('definition/control')
    assert (group.findtext('width'), group.findtext('height')) == ('456', '40')
    image = group.find("control[@type='image']")
    assert image.findtext('texture') == '$INFO[$PARAM[icon]]' and image.findtext('aspectratio') == 'keep'


def _hero_body(head_visible):
    for group in _info().iter('control'):
        if group.findtext('visible') == head_visible:
            inc = group.find("include[@content='HeroBody']")
            if inc is not None:
                return group, dict((p.get('name'), p.get('value')) for p in inc.iter('param'))


def _variable(name):
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable') if v.get('name') == name)
    return [(v.get('condition'), v.text) for v in var.iter('value')]


def test_a_shows_page_opens_its_plot_with_the_tagline_on_kodi_22():
    """Kodi 22 keeps a tag line for TV shows: in italics over the plot of a show's page."""
    _, params = _hero_body('!String.IsEqual(ListItem.DBType,episode) + !String.IsEqual(ListItem.Property(tmdb_type),person)')
    assert params['plotprefix'] == '$VAR[InfoShowTagline]'
    assert _variable('InfoShowTagline') == [
        ('$EXP[KodiPiers] + String.IsEqual(ListItem.DBType,tvshow) + !String.IsEmpty(ListItem.Tagline)',
         '[I]$INFO[ListItem.Tagline][/I][CR]')]


def test_the_hero_body_takes_a_plot_prefix_and_its_visibility():
    inc = next(i for i in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('include') if i.get('name') == 'HeroBody')
    defaults = dict((p.get('name'), p.get('default')) for p in inc.findall('param'))
    assert defaults['plotprefix'] == '' and defaults['plotvisible'] == 'true'
    box = next(c for c in inc.iter('control') if c.get('id') == '$PARAM[plotid]')
    assert box.findtext('label') == '$PARAM[plotprefix]$INFO[$PARAM[item].Plot]'
    assert box.findtext('visible') == '$PARAM[plotvisible]'


def test_the_season_tabs_show_the_seasons_plot_on_kodi_22():
    """Kodi 22 keeps a plot per season: with the focus on the season tabs (5200) it stands where
    the episode's plot was, as wide and high; Kodi 21 keeps the episode's."""
    group, params = _hero_body('String.IsEqual(ListItem.DBType,episode)')
    assert params['plotvisible'] == '!$EXP[InfoSeasonPlot]'
    expressions = {e.get('name'): e.text for e in parse(ROOT / '1080i' / 'Includes_Info.xml').iter('expression')}
    assert expressions['InfoSeasonPlot'] == \
        '$EXP[KodiPiers] + Control.HasFocus(5200) + !String.IsEmpty(Container(5200).ListItem.Plot)'
    box = next(c for c in group.findall('control') if c.get('id') == '9053')
    assert box.get('type') == 'textbox' and box.findtext('visible') == '$EXP[InfoSeasonPlot]'
    assert box.findtext('label') == '$INFO[Container(5200).ListItem.Plot]'
    assert [box.findtext(k) for k in ('left', 'top', 'width', 'height')] == ['64', '367', '1176', '116']
