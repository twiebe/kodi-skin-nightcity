"""Confuse after the TV check: Ember as default with the other palettes as colour themes, a burning
fuse on the loading page, one line for shown and focused in the menu and tabs, a glow on the focused
card. Read from the assembled skin (confuse_root) and the overlay."""
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
              'focus_text': 'FF160804', 'spark': 'FFFFD166', 'card_glow': 'CCFF5B35'}
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


def test_menu_has_one_shape(confuse_root):
    """Shown and focused are the same line, the focus adds a glow. No pill to jump to."""
    textures = look_includes()['LookMenuTextures']
    assert textures.findtext('alttexturenofocus') == 'ui/menu_line.png'
    for tag in ('texturefocus', 'alttexturefocus'):
        assert textures.findtext(tag) == 'ui/menu_glow.png', tag
    assert not textures.findtext('texturenofocus')
    line, glow = alpha(confuse_root, 'menu_line.png'), alpha(confuse_root, 'menu_glow.png')
    assert line.size == glow.size
    middle = line.width // 2
    solid = [y for y in range(line.height) if line.getpixel((middle, y)) == 255]
    assert solid and all(glow.getpixel((middle, y)) == 255 for y in solid)
    above = solid[0] - 4
    assert line.getpixel((middle, above)) == 0 and glow.getpixel((middle, above)) > 40


def test_menu_text_with_the_focus_is_bright(confuse_root):
    """No fill under the text any more, so not the dark text of a filled button."""
    assert look_includes()['LookMenuText'].findtext('.//focusedcolor') == 'text'


def test_card_glow_has_room_in_the_row():
    """A list cuts what lies past it: the glow ends before the edge at the zoom of the focus."""
    c = constants()
    zoom = c['LookCardFocusZoom'] / 100
    assert c['LookRowItemLeft'] >= CARD[0] * (zoom - 1) / 2 + SHADOW_PAST_CARD * zoom
    assert c['LookRowItemTop'] >= CARD[1] * (zoom - 1) / 2 + SHADOW_PAST_CARD * zoom


def test_card_glow_is_coloured_by_the_theme(confuse_root):
    image = look_includes()['LookCardFocus'].find('.//control')
    texture = image.find('texture')
    assert texture.text == 'ui/card_halo.png' and texture.get('colordiffuse') == 'card_glow'
    halo = alpha(confuse_root, 'card_halo.png')
    middle = halo.height // 2
    assert halo.getpixel((SHADOW_PAST_CARD - 1, middle)) > 200  # against the card
    assert halo.getpixel((SHADOW_PAST_CARD // 2, middle)) > 40  # halfway out
    assert all(halo.getpixel((x, middle)) < 8 for x in range(2))  # gone before the list cuts it
    assert int(texture.get('border')) * 2 <= halo.width


def test_wordmark_is_a_texture_in_two_colours(confuse_root):
    """con in the mute colour, fuse in the accent: themed, and side by side around the screen's middle."""
    wordmark = look_includes()['LookStartupWordmark']
    images = [c for c in wordmark.iter('control') if 'word_' in (c.findtext('texture') or '')]
    assert [i.find('texture').get('colordiffuse') for i in images] == ['text_mute', 'accent']
    assert [i.findtext('texture') for i in images] == ['ui/word_con.png', 'ui/word_fuse.png']
    con, fuse = images
    for image in images:
        size = alpha(confuse_root, image.findtext('texture')[3:]).size
        assert (int(image.findtext('width')), int(image.findtext('height'))) == size
    assert int(con.findtext('left')) + int(con.findtext('width')) == int(fuse.findtext('left'))
    assert int(con.findtext('left')) == 1920 - int(fuse.findtext('left')) - int(fuse.findtext('width'))


def test_loading_page_has_nothing_of_nightcity(confuse_root):
    from navigation import load
    window = load('Startup.xml', layout=confuse_root / '1080i')
    labels = [c.findtext('label') for c in window.iter('control') if c.get('type') == 'label']
    assert '_' not in labels  # the blinking cursor
    assert not any('31157' in (label or '') or '31158' in (label or '') for label in labels)  # Booting, Online
    assert not any('$VAR[SkinTitle]' in (label or '') for label in labels)  # the wordmark is a texture
    assert not any(c.findtext('font') == 'font_num_small' for c in window.iter('control'))


def test_fuse_burns_while_waiting_and_ends_when_online(confuse_root):
    """The same two states as the shared track: a running spark, then the whole line."""
    from navigation import load
    window = load('Startup.xml', layout=confuse_root / '1080i')
    waiting = [c for c in window.iter('control') if c.findtext('visible') == '!$EXP[StartupOnline]']
    online = [c for c in window.iter('control') if c.findtext('visible') == '$EXP[StartupOnline]']
    assert any(c.findtext('texture') == 'ui/fuse_trail.png' for c in waiting)
    assert any(a.get('loop') == 'true' for c in waiting for a in c.iter('animation'))
    assert any(c.findtext('texture') == 'ui/white.png' for c in online)
    used = {c.findtext('texture') for c in window.iter('control')}
    assert {'ui/spark_halo.png', 'ui/spark_core.png'} <= used


def test_spark_has_a_visible_halo(confuse_root):
    halo = alpha(confuse_root, 'spark_halo.png')
    middle = halo.width // 2
    assert halo.getpixel((middle, middle)) > 200
    assert halo.getpixel((middle - 12, middle)) > 60
    assert halo.getpixel((0, 0)) == 0


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


def test_wordmark_font_is_lexend_with_its_licence():
    """tools/fonts holds the font of the wordmark and its licence, nothing else."""
    assert sorted(p.name for p in (ROOT / 'tools' / 'fonts').iterdir()) == ['Lexend-OFL.txt', 'Lexend[wght].ttf']


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


BLUR = 'Window(Home).Property(TMDbHelper.ListItem.BlurImage'


def test_backdrop_is_blurred_once_the_helper_has_that_picture(confuse_root):
    """One of two shows: the helper's blurred picture when it was made from this art, the sharp one
    until then and where the helper follows another item. The same mask and colour for both."""
    from navigation import load
    window = load('MyVideoNav.xml', layout=confuse_root / '1080i')
    images = [c for c in window.iter('control') if c.findtext('description') == 'fanart backdrop']
    assert len(images) == 2
    match = 'String.IsEqual({}.Original),ListItem.Art(fanart))'.format(BLUR)
    sharp, blurred = images
    assert sharp.findtext('texture') == '$INFO[ListItem.Art(fanart)]'
    assert blurred.findtext('texture') == '$INFO[{})]'.format(BLUR)
    assert match in blurred.findtext('visible') and '!' + match in sharp.findtext('visible')
    for image in images:
        texture = image.find('texture')
        assert (texture.get('colordiffuse'), texture.get('diffuse')) == ('fanart', 'ui/fade_r.png')
        assert '!String.IsEmpty(ListItem.Art(fanart))' in image.findtext('visible')
        assert image.find('animation') is not None


def test_nightcity_backdrop_stays_sharp():
    from navigation import load
    window = load('MyVideoNav.xml', layout=ROOT / '1080i')
    images = [c for c in window.iter('control') if c.findtext('description') == 'fanart backdrop']
    assert [i.findtext('texture') for i in images] == ['$INFO[ListItem.Art(fanart)]']
    assert images[0].findtext('visible') == '!String.IsEmpty(ListItem.Art(fanart))'
