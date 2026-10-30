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


def test_spotlight_more_is_three_chevrons_fading_to_the_right():
    """Three small drawn chevrons close together, like a direction hint in a racing game, each a
    step darker to the right, centred on the buttons, the usual button gap before them."""
    body = _include('SpotlightMore')
    images = re.findall(r'<control type="image">(.*?)</control>', body, re.S)
    assert len(images) == 3
    colours = [re.search(r'colordiffuse="(\w+)">ui/spot_more.png<', i).group(1) for i in images]
    assert colours == ['state_text', 'state_fade', 'state_faint']
    lefts = [int(re.search(r'<left>(\d+)</left>', i).group(1)) for i in images]
    assert lefts[0] == 0 and lefts[1] - lefts[0] == lefts[2] - lefts[1] == 11
    for image in images:
        assert '<top>12</top>' in image and '<height>30</height>' in image
    assert '<height>54</height>' in body  # the group, as tall as the buttons


def test_chevron_fades_are_state_text_with_less_alpha():
    for scheme in ('defaults', 'catppuccin', 'tokyonight'):
        root = ET.parse(ROOT / 'colors' / '{}.xml'.format(scheme)).getroot()
        colours = {c.get('name'): c.text for c in root.iter('color')}
        assert colours['state_fade'] == 'A0' + colours['state_text'][2:], scheme
        assert colours['state_faint'] == '50' + colours['state_text'][2:], scheme


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
