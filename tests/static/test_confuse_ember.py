"""Confuse after the TV check: Ember as default with the other palettes as colour themes, a burning
fuse on the loading page, one line for shown and focused in the menu and tabs, a glow on the focused
card. Read from the assembled skin (confuse_root) and the overlay."""
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from conftest import ROOT, parse
from test_confuse_look import CARD, SHADOW_PAST_CARD, constants, contrast, look_includes, rgb

THEMES = ('defaults', 'glut', 'iris', 'aurora', 'volt')


def palette(root, name):
    return {c.get('name'): c.text for c in parse(root / 'colors' / '{}.xml'.format(name)).iter('color')}


def alpha(root, name):
    return Image.open(root / 'media' / 'ui' / name).convert('RGBA').getchannel('A')


def test_ember_is_the_default(confuse_root):
    colours = palette(confuse_root, 'defaults')
    wanted = {'bg': 'FF0B0B10', 'surface': 'FF1A1A22', 'accent': 'FFFF5B35', 'focus': 'FFFF5B35',
              'focus_text': 'FF160804', 'card_glow': 'CCFF5B35'}
    assert {k: colours[k] for k in wanted} == wanted


def test_the_palettes_are_the_colour_themes_and_nothing_else(confuse_root):
    assert sorted(p.stem for p in (confuse_root / 'colors').glob('*.xml')) == sorted(THEMES)


@pytest.mark.parametrize('theme', THEMES[1:])
def test_a_theme_sets_every_colour(confuse_root, theme):
    """Kodi lays a theme over defaults.xml: a missing colour would stay Ember's."""
    assert set(palette(confuse_root, theme)) == set(palette(confuse_root, 'defaults'))


@pytest.mark.parametrize('theme', THEMES)
def test_a_theme_stays_readable(confuse_root, theme):
    colours = palette(confuse_root, theme)
    bg = rgb(colours['bg'])
    assert contrast(rgb(colours['focus_text']), rgb(colours['focus'])) >= 4.5
    assert contrast(rgb(colours['text']), bg) >= 7
    for name in ('text_dim', 'text_mute', 'accent2'):
        assert contrast(rgb(colours[name]), bg) >= 4.5, name
    assert contrast(rgb(colours['accent']), bg) >= 3


@pytest.mark.parametrize('theme', THEMES)
def test_warnings_do_not_read_as_the_accent(confuse_root, theme):
    colours = palette(confuse_root, theme)
    assert colours['error'] != colours['accent'] and colours['warn'] != colours['accent']


def test_card_glow_has_room_in_the_row():
    """A list cuts what lies past it: the glow ends before the edge at the zoom of the focus."""
    c = constants()
    zoom = c['LookCardFocusZoom'] / 100
    assert c['LookRowItemLeft'] >= CARD[0] * (zoom - 1) / 2 + SHADOW_PAST_CARD * zoom
    assert c['LookRowItemTop'] >= CARD[1] * (zoom - 1) / 2 + SHADOW_PAST_CARD * zoom


def test_loading_page_has_nothing_of_nightcity(confuse_root):
    from navigation import load
    window = load('Startup.xml', layout=confuse_root / '1080i')
    labels = [c.findtext('label') for c in window.iter('control') if c.get('type') == 'label']
    assert '_' not in labels  # the blinking cursor
    assert not any('31157' in (label or '') or '31158' in (label or '') for label in labels)  # Booting, Online
    assert not any('$VAR[SkinTitle]' in (label or '') for label in labels)  # the wordmark is a texture
    assert not any(c.findtext('font') == 'font_num_small' for c in window.iter('control'))


def test_seek_head_is_the_spark(confuse_root):
    """A solid core, the rest a glow that ends inside the 16 px of its track."""
    head = alpha(confuse_root, 'seek_head.png')
    assert head.size == (16, 16)
    assert head.getpixel((8, 8)) == 255
    assert 0 < head.getpixel((1, 8)) < 120
    assert head.getpixel((0, 0)) == 0


def test_nightcity_keeps_its_startup():
    """The same wordmark and ticker as before, only moved into the look."""
    look = {i.get('name'): i for i in parse(ROOT / '1080i' / 'Includes_Look.xml').iter('include') if i.get('name')}
    assert any(i.get('content') == 'GlitchTitle' for i in look['LookStartupWordmark'].iter('include'))
    assert any(c.findtext('font') == 'font_num_small' for c in look['LookStartupTrack'].iter('control'))


def test_a_focused_button_glows(confuse_root):
    """The fill with a glow in its 10 px of padding, gone at the edge since a grouplist cuts there."""
    for name, tag in (('LookButtonFill', 'texturefocus'), ('LookButtonFillNoFocus', 'texturenofocus')):
        texture = look_includes()[name].find(tag)
        assert texture.text == 'ui/pill_halo.png' and texture.get('colordiffuse') == 'focus', name
        assert texture.get('border') == '37'
    halo = alpha(confuse_root, 'pill_halo.png')
    assert halo.size == alpha(confuse_root, 'pill_pad.png').size
    middle = halo.height // 2
    assert halo.getpixel((middle, 10)) == 255  # the fill starts where the plain pill does
    assert halo.getpixel((middle, 7)) > 90  # against it
    assert halo.getpixel((middle, 0)) < 12  # gone before the edge


def test_the_more_pill_glows_like_the_buttons(confuse_root):
    """Unfocused the plain pill, focused the one with the glow; the caller names the colour."""
    from navigation import load
    window = load('DialogVideoInfo.xml', layout=confuse_root / '1080i')
    used = {(t.text, t.get('colordiffuse')) for t in window.iter('texture') if t.get('border') == '37' and (t.text or '').startswith('ui/more_')}
    assert ('ui/more_focus.png', 'focus') in used and ('ui/more_border_dim.png', 'border_dim') in used
    assert list(alpha(confuse_root, 'more_focus.png').getdata()) == list(alpha(confuse_root, 'pill_halo.png').getdata())
    assert list(alpha(confuse_root, 'more_border_dim.png').getdata()) == list(alpha(confuse_root, 'pill_pad.png').getdata())


def test_confuse_backdrop_is_sharp(confuse_root):
    """One picture, the art itself: the blur was struck after the test on the box."""
    from navigation import load
    window = load('MyVideoNav.xml', layout=confuse_root / '1080i')
    images = [c for c in window.iter('control') if c.findtext('description') == 'fanart backdrop']
    assert [i.findtext('texture') for i in images] == ['$INFO[ListItem.Art(fanart)]']
    assert 'nc.blur' not in ET.tostring(window, encoding='unicode')


def test_nightcity_backdrop_stays_sharp():
    from navigation import load
    window = load('MyVideoNav.xml', layout=ROOT / '1080i')
    images = [c for c in window.iter('control') if c.findtext('description') == 'fanart backdrop']
    assert [i.findtext('texture') for i in images] == ['$INFO[ListItem.Art(fanart)]']
    assert images[0].findtext('visible') == '!String.IsEmpty(ListItem.Art(fanart)) + [true]'
