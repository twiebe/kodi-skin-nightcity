"""Confuse in the design Stille Mitte: logo, loading page, tabs in the middle, the hero as a large
rounded picture and wide rows. Nightcity keeps every value, the expansion of its windows does not change."""
import xml.etree.ElementTree as ET

from PIL import Image

from conftest import ROOT, parse
from test_confuse_look import OVERLAY, constants, look_includes


def ui(name):
    return Image.open(OVERLAY / 'media' / 'ui' / name).convert('RGBA')


def textures_of(include):
    return [c.findtext('texture') for c in look_includes()[include].iter('control') if c.findtext('texture')]


def test_logo_is_a_disc_with_a_gap_that_points_forward():
    """Across the middle: disc, gap, disc. The gap's point lies right of its ends, so it reads as play."""
    mark = ui('logo_mark_230.png').getchannel('A')
    size = mark.width
    row = [mark.getpixel((x, size // 2)) for x in range(size)]
    assert row[0] == 0 and row[size // 4] == 255 and row[int(size * 0.66)] == 0 and row[int(size * 0.8)] == 255
    def gap_at(y):
        line = [mark.getpixel((x, y)) for x in range(int(size * 0.13), int(size * 0.87))]
        return line.index(min(line))
    assert gap_at(size // 2) > gap_at(int(size * 0.3))
    assert gap_at(int(size * 0.3)) == gap_at(int(size * 0.7))  # both arms alike


def test_logo_tips_are_round():
    """The sharp tip of the left piece reached x 60 of 100 across the middle; rounded it ends earlier,
    and the edges along the gap stay crisp and in place."""
    mark = ui('logo_mark_230.png').getchannel('A')
    size = mark.width
    row = [mark.getpixel((x, size // 2)) for x in range(size)]
    tip = next(x for x in range(size // 4, size) if row[x] < 128)
    assert size * 0.30 < tip <= 136  # sharp it would reach 138


def test_logo_is_drawn_at_its_own_size():
    """Kodi has no mipmaps for these textures: one drawn much smaller than it is gets rough edges."""
    found = 0
    for include in ('LookStartupWordmark', 'LookHomeLogo'):
        colours = {}
        for c in look_includes()[include].iter('control'):
            name = c.findtext('texture') or ''
            if 'logo' not in name:
                continue
            found += 1
            assert ui(name[3:]).size == (int(c.findtext('width')), int(c.findtext('height'))), name
            colours[c.find('texture').get('colordiffuse')] = name
        assert set(colours) == {'accent', 'focus_text'}
        assert 'plate' in colours['accent'] and 'mark' in colours['focus_text']
    assert found == 4


def test_icon_is_the_logo(confuse_root):
    icon = Image.open(confuse_root / 'resources' / 'icon.png').convert('RGB')
    assert icon.size == (512, 512)
    assert icon.getpixel((4, 4)) == (255, 91, 53)
    assert icon.getpixel((128, 256)) == (22, 8, 4)


def test_loading_page_is_logo_and_spinner(confuse_root):
    from navigation import load
    window = load('Startup.xml', layout=confuse_root / '1080i')
    used = {c.findtext('texture') for c in window.iter('control') if c.findtext('texture')}
    assert {'ui/logo_plate_230.png', 'ui/logo_mark_230.png'} <= used
    assert not any('word_' in t or 'ember_glow' in t for t in used)
    spinner = [c for c in window.iter('control') if c.get('type') == 'multiimage']
    assert len(spinner) == 1 and spinner[0].findtext('imagepath') == 'ui/spinner'
    assert spinner[0].find('imagepath').get('colordiffuse') == 'text'
    assert (spinner[0].findtext('fadetime'), spinner[0].findtext('loop')) == ('0', 'true')


def spinner_frames():
    return [Image.open(p).convert('RGBA').getchannel('A') for p in sorted((OVERLAY / 'media' / 'ui' / 'spinner').glob('*.png'))]


def test_spinner_does_not_turn():
    """Nothing rotates: the spokes stand in the same place in every frame, only their light differs."""
    frames = spinner_frames()
    assert len(frames) == 12
    assert 'rotate' not in ET.tostring(look_includes()['LookStartupTrack'], encoding='unicode')
    middles = {tuple(f.getpixel((f.width // 2, round(f.height * y))) > 0 for y in (0.1, 0.2)) for f in frames}
    assert middles == {(True, True)}  # the top spoke is there in every frame
    center = (frames[0].width // 2, frames[0].height // 2)
    assert all(f.getpixel(center) == 0 for f in frames)


def test_spinner_light_walks_clockwise():
    """Frame 0 lights the top spoke, frame 1 the next one clockwise; the one it left is a step fainter."""
    frames = spinner_frames()
    s = frames[0].width
    top = (s // 2, round(s * 0.16))
    next_one = (round(s / 2 + s * 0.34 * 0.5), round(s / 2 - s * 0.34 * 0.866))
    assert frames[0].getpixel(top) == 255 and frames[0].getpixel(next_one) < 80
    assert frames[1].getpixel(next_one) == 255 and 200 < frames[1].getpixel(top) < 255


def test_spinner_frames_are_white():
    for path in (OVERLAY / 'media' / 'ui' / 'spinner').glob('*.png'):
        image = Image.open(path).convert('RGBA')
        assert max(image.size) <= 112
        assert {rgba[:3] for _, rgba in image.getcolors(image.width * image.height) if rgba[3]} == {(255, 255, 255)}


def test_tabs_stand_in_the_middle():
    c = constants()
    assert c['LookMenuWidth'] == 1920
    assert look_includes()['LookMenuAlign'].findtext('align') == 'center'


def test_shown_tab_is_a_white_pill_and_the_focus_the_accent():
    textures = look_includes()['LookMenuTextures']
    assert textures.find('alttexturenofocus').get('colordiffuse') == 'text'
    assert textures.find('alttexturefocus').get('colordiffuse') == 'accent'
    assert textures.find('texturefocus').get('colordiffuse') == 'accent'
    assert not textures.findtext('texturenofocus')
    assert {textures.findtext(t) for t in ('alttexturenofocus', 'alttexturefocus', 'texturefocus')} == {'ui/pill_menu.png'}


def test_tab_text_is_dark_on_its_pill():
    text = look_includes()['LookMenuText']
    assert text.findtext('.//focusedcolor') == 'focus_text'
    assert '[COLOR bg]' in text.findtext('.//altlabel')
    assert '[B]' not in text.findtext('.//altlabel')


def test_hero_is_a_round_picture_with_room_for_its_text():
    fanart = look_includes()['LookHomeFanart']
    picture = next(c for c in fanart.iter('control') if c.findtext('description') == 'hero picture')
    assert picture.find('texture').get('diffuse') == 'ui/mask_hero.png'
    assert picture.find('aspectratio').get('scalediffuse') == 'false'
    top, height = int(picture.findtext('top')), int(picture.findtext('height'))
    c = constants()
    assert c['LookHeroKickerTop'] > top
    assert c['LookHeroPillsTop'] + 74 <= top + height
    assert c['LookHeroProgressTop'] + 4 <= top + height
    assert top + height <= c['LookPageRowsTop']
    assert len(look_includes()['LookHeroPoster'].find('definition')) == 0


def test_hero_text_block_does_not_overlap():
    c = constants()
    order = ['LookHeroKickerTop', 'LookHeroTitleTop', 'LookHeroMetaTop', 'LookHeroRatingsTop', 'LookHeroPlotTop']
    assert [c[n] for n in order] == sorted(c[n] for n in order)
    assert c['LookHeroPlotTop'] + c['LookHeroPlotHeight'] <= c['LookHeroPillsTop']
    assert c['LookHeroPillsLeft'] == c['LookHeroLeft'] - 10  # the padding of a pill


def test_hero_text_stays_readable_on_a_white_picture():
    """The worst case: a white picture under the fade, in the colour bg of Ember. Every line of text
    as far as it usually reaches: the genres of the kicker, the tags, the plot's full width."""
    from test_confuse_look import contrast, rgb
    scrim = ui('hero_scrim.png').getchannel('A')
    bg = (0x0B, 0x0B, 0x10)
    c = constants()
    top, height, left, width = 116, 554, 64, 1792
    for line_top, colour, wide in ((c['LookHeroKickerTop'] + 6, (0xFF, 0x7A, 0x57), 500), (c['LookHeroMetaTop'], (0xA9, 0xA9, 0xB6), 700), (c['LookHeroPlotTop'], (0xD4, 0xD4, 0xDC), 980)):
        for x in (c['LookHeroLeft'], c['LookHeroLeft'] + wide):
            a = scrim.getpixel((round((x - left) / width * (scrim.width - 1)), round((line_top - top) / height * (scrim.height - 1)))) / 255
            ground = tuple(255 * (1 - a) + v * a for v in bg)
            assert contrast(colour, ground) >= 3, (line_top, x, a)


def test_hero_fade_runs_down_only():
    """No corner of its own: every column the same, the top free."""
    scrim = ui('hero_scrim.png').getchannel('A')
    for y in range(scrim.height):
        assert scrim.getpixel((0, y)) == scrim.getpixel((scrim.width - 1, y)) == scrim.getpixel((scrim.width // 2, y))
    assert scrim.getpixel((0, 2)) == 0
    column = [scrim.getpixel((0, y)) for y in range(scrim.height)]
    assert column == sorted(column)


def test_music_keeps_its_soft_backdrop(confuse_root):
    """The music page has its album poster and its text on top: no room for a round picture."""
    from navigation import load
    window = load('Home.xml', layout=confuse_root / '1080i')
    backdrops = {c.findtext('texture') for c in window.iter('control') if c.findtext('description') == 'fanart backdrop'}
    assert {'$INFO[Container(9002).ListItem.Art(artist.fanart)]', '$INFO[ListItem.Art(artist.fanart)]'} <= backdrops
    pictures = {c.findtext('texture') for c in window.iter('control') if c.findtext('description') == 'hero picture'}
    assert pictures == {'$INFO[Container(9000).ListItem.Art(fanart)]', '$INFO[Container(9001).ListItem.Art(fanart)]', '$INFO[ListItem.Art(fanart)]'}


def test_row_card_is_wide_and_names_its_title():
    card = look_includes()['LookRowCard']
    args = {p.get('name'): p.get('value') for p in next(i for i in card.iter('include') if i.get('content') == 'CutCard').findall('param')}
    assert (args['width'], args['height'], args['mask']) == ('400', '225', 'ui/mask_400x225.png')
    assert (args['glowwidth'], args['glowheight']) == ('448', '273')
    assert any(l.findtext('label') == '$INFO[ListItem.Label]' for l in card.iter('control') if l.get('type') == 'label')
    assert ui('mask_400x225.png').size == (400, 225)


def test_row_top_line_has_no_title():
    """The hero and the label under the card name it already."""
    assert len(look_includes()['LookRowFocusTitle'].find('definition')) == 0
    night = {i.get('name'): i for i in parse(ROOT / '1080i' / 'Includes_Look.xml').iter('include') if i.get('name')}
    assert night['LookRowFocusTitle'].find('.//control').findtext('visible') == '$PARAM[shown]'


def test_row_art_prefers_wide_pictures():
    root = parse(OVERLAY / '1080i' / 'Includes_Look.xml')
    values = next(v for v in root.iter('variable') if v.get('name') == 'LookRowArt').findall('value')
    order = [v.text for v in values]
    assert order.index('$INFO[ListItem.Art(landscape)]') < order.index('$INFO[ListItem.Art(fanart)]') < order.index('$INFO[ListItem.Art(poster)]')
    assert order[-1] == '$INFO[ListItem.Art(poster)]'  # never an empty card when there is art at all


def test_a_focused_card_rises_on_a_shadow():
    texture = next(c for c in look_includes()['LookCardFocus'].iter('control')).find('texture')
    assert texture.text == 'ui/card_halo.png' and texture.get('colordiffuse') == 'shadow'


def test_info_page_keeps_its_poster_and_place(confuse_root):
    """Only the pages of Home take the hero from the look: the info page is a later step."""
    from navigation import load
    window = load('DialogVideoInfo.xml', layout=confuse_root / '1080i')
    text = ET.tostring(window, encoding='unicode')
    assert 'ui/mask_290x435.png' in text
    assert '<left>394</left>' in text


def test_nightcity_keeps_every_value():
    root = parse(ROOT / '1080i' / 'Includes_Look.xml')
    c = {x.get('name'): x.text for x in root.iter('constant')}
    assert (c['LookMenuLeft'], c['LookMenuWidth'], c['LookPageRowsTop'], c['LookHeroLeft']) == ('-28', '1520', '619', '394')
    include = {i.get('name'): i for i in root.iter('include') if i.get('name')}
    assert len(include['LookHomeLogo'].find('definition')) == 0
    assert len(include['LookMenuAlign'].find('definition')) == 0
