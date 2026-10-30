"""A dim > right of the spotlight buttons, as tall as they are: Right on the last button moves
the spotlight on to the next title (movies, shows, music)."""
import re
import xml.etree.ElementTree as ET

from conftest import ROOT

SKIN = ROOT / '1080i'


def _include(name):
    text = (SKIN / 'Includes_Home.xml').read_text(encoding='utf-8')
    match = re.search(r'<include name="{}">(.*?)</include>'.format(name), text, re.S)
    assert match, name
    return match.group(1)


def test_spotlight_more_is_a_dim_arrow_as_tall_as_the_buttons():
    """A drawn chevron, narrow and smaller than the buttons, centred on them and set apart."""
    body = _include('SpotlightMore')
    assert '<control type="group">' in body and '<control type="image">' in body
    assert '<texture colordiffuse="state">ui/spot_more.png</texture>' in body
    assert '<height>54</height>' in body  # the group, as tall as the buttons
    assert '<left>24</left>' in body and '<top>12</top>' in body and '<height>30</height>' in body
    assert '&gt;' not in body
    assert (ROOT / 'media' / 'ui' / 'spot_more.png').is_file()


def test_spot_more_texture_is_a_narrow_chevron():
    from PIL import Image
    image = Image.open(ROOT / 'media' / 'ui' / 'spot_more.png')
    width, height = image.size
    assert height == 30 and width < height / 2
    alpha = image.getchannel('A')
    # the tip in the middle of the right edge, the open ends at the left top and bottom
    assert alpha.getpixel((width - 2, height // 2)) > 128
    assert alpha.getpixel((1, 1)) > 128 and alpha.getpixel((1, height - 2)) > 128
    assert alpha.getpixel((1, height // 2)) == 0


def test_every_spotlight_button_row_ends_with_the_arrow():
    rows = []
    for name in ('Includes_Home.xml', 'Includes_Music.xml'):
        root = ET.parse(SKIN / name).getroot()
        rows += [c for c in root.iter('control') if c.get('type') == 'grouplist'
                 and c.findtext('left') == '384' and c.findtext('top') == '490']
    assert len(rows) == 3, len(rows)
    for row in rows:
        last = [c for c in row if c.tag in ('include', 'control')][-1]
        assert last.tag == 'include' and last.text == 'SpotlightMore', ET.tostring(last)[:80]
