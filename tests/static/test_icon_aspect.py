"""Icons keep their shape on any screen.

The skin is laid out on a 1920 x 1080 grid and Kodi scales that grid to the whole screen: on a
screen that is not 16:9 (a 3:2 or 16:10 laptop) it scales x and y apart. An image with an
<aspectratio> of keep, scale or center is drawn corrected by the pixel ratio (GUITexture.cpp,
GetScalingPixelRatio); one without it (stretch) fills its rect and is distorted with it.

So every icon image says keep (or center). An icon is an image or multiimage that draws one of the
skin's own textures (a path under ui/, the weather glyphs too) or an icon Kodi hands over
(ListItem.Icon, a notification's icon), unless the texture is a 9-slice (border) or one of the
fills in STRETCH, which have to fill their rect. A new texture under ui/ counts as an icon until it
is put in STRETCH, with its reason.

Kodi keeps the radio textures of a radiobutton itself (GUIRadioButtonControl.cpp sets AR_KEEP)
and the nib of a slider. The arrows of a spin control, the textures of a button or a mover and
the head of a progress bar have no aspect in Kodi: they stretch, whatever the skin says."""
import re
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from conftest import ROOT
from navigation import with_look

# textures under ui/ that fill their rect: drawn stretched on purpose
STRETCH = {
    'white.png': 'a plain fill (backgrounds, scrims, lines, bars, the pointer)',
    'clear.png': 'an empty fill',
    'petrol_glow.png': 'the glow of the whole background',
    'fade_t.png': 'a fade over the width of the screen',
    'fade_b.png': 'a fade over the width of the screen',
    'fade_r.png': 'a fade over the height of its area',
    'line_pad.png': 'the separator line of a settings list, as wide as the list',
    'page_wash.png': 'the wash of a whole page (Confuse)',
    'info_fade.png': 'the fade of the info page (Confuse)',
    'hero_scrim.png': 'the scrim over the hero picture (Confuse)',
}
# icons Kodi hands over as an info label
ICON_INFO = ('ListItem.Icon', 'Control.GetLabel(400)')
KEEPS = {'keep', 'center'}
TOLERANCE = 0.02


def _skins():
    return [pytest.param('nightcity', id='nightcity'), pytest.param('confuse', id='confuse')]


def _root(skin, request):
    return ROOT if skin == 'nightcity' else request.getfixturevalue('confuse_root')


def images(root):
    """(file, control, texture element or imagepath, texture path) of every image and multiimage,
    with the look includes expanded as Kodi builds them."""
    layout = root / '1080i'
    out = []
    for path in sorted(layout.glob('*.xml')):
        if path.name == 'Font.xml':
            continue
        tree = with_look(ET.parse(path).getroot(), layout)
        for control in tree.iter('control'):
            kind = control.get('type')
            if kind == 'image':
                tex = control.find('texture')
            elif kind == 'multiimage':
                tex = control.find('imagepath')
            else:
                continue
            if tex is None or not (tex.text or '').strip():
                continue
            out.append((path.name, control, tex, tex.text.strip()))
    return out


def is_icon(tex, text):
    if tex.get('border'):
        return False
    if any(info in text for info in ICON_INFO):
        return True
    return text.startswith('ui/') and text.rsplit('/', 1)[-1] not in STRETCH


def aspect(control):
    return (control.findtext('aspectratio') or 'stretch').strip()


def describe(name, control, text):
    return '{}: {} {}x{}'.format(name, text, control.findtext('width'), control.findtext('height'))


def texture_file(root, text, kind):
    """The file a texture path names; a weather glyph by its fallback, a multiimage by its first
    frame. None when Kodi fills it in at run time."""
    if kind == 'multiimage':
        frames = sorted((root / 'media' / text).glob('*.png'))
        return frames[0] if frames else None
    if '$' in text:
        return None
    return root / 'media' / text


@pytest.mark.parametrize('skin', _skins())
def test_every_icon_keeps_its_aspect(skin, request):
    root = _root(skin, request)
    bad = sorted({describe(name, c, text) for name, c, tex, text in images(root)
                  if is_icon(tex, text) and aspect(c) not in KEEPS})
    assert not bad, 'icons without <aspectratio>keep</aspectratio>, stretched on a screen that is not 16:9:\n' + '\n'.join(bad)


@pytest.mark.parametrize('skin', _skins())
def test_icon_box_has_the_ratio_of_its_texture(skin, request):
    """keep changes nothing on 16:9 only when the box has the texture's ratio."""
    root = _root(skin, request)
    bad = set()
    for name, c, tex, text in images(root):
        if not is_icon(tex, text):
            continue
        width, height = c.findtext('width'), c.findtext('height')
        if width is None or height is None:
            continue
        if width == height:
            box = 1.0
        elif re.fullmatch(r'\d+', width) and re.fullmatch(r'\d+', height):
            box = int(width) / int(height)
        else:
            continue
        path = texture_file(root, tex.get('fallback') or text, c.get('type'))
        if path is None:
            continue
        assert path.exists(), describe(name, c, text)
        w, h = Image.open(path).size
        if abs(box / (w / h) - 1) > TOLERANCE:
            bad.add('{} has a {}x{} texture'.format(describe(name, c, text), w, h))
    assert not bad, '\n'.join(sorted(bad))


@pytest.mark.parametrize('skin', _skins())
def test_fills_and_frames_stretch(skin, request):
    """A 9-slice or a fill has to cover its rect: no keep there."""
    root = _root(skin, request)
    bad = sorted({describe(name, c, text) for name, c, tex, text in images(root)
                  if not is_icon(tex, text) and (tex.get('border') or text.rsplit('/', 1)[-1] in STRETCH)
                  and aspect(c) != 'stretch'})
    assert not bad, '\n'.join(bad)


def test_every_stretch_texture_exists():
    """STRETCH names only textures one of the skins has."""
    names = {p.name for p in (ROOT / 'media' / 'ui').glob('*.png')}
    names |= {p.name for p in (ROOT / 'skins' / 'confuse' / 'media' / 'ui').glob('*.png')}
    assert set(STRETCH) <= names, set(STRETCH) - names
