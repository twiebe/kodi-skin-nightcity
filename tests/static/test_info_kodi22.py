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

