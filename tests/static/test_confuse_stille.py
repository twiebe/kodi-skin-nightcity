"""Confuse in the design Stille Mitte: logo, loading page, tabs in the middle, the hero as a large
rounded picture and wide rows. Nightcity keeps every value, the expansion of its windows does not change."""
import re
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
            colours.setdefault(c.find('texture').get('colordiffuse'), name)
        # the logo itself; the glitches' copies come after it (test_confuse_glitch.py)
        assert {'accent', 'focus_text'} <= set(colours)
        assert 'plate' in colours['accent'] and 'mark' in colours['focus_text']
    assert found == 8


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
    spinners = [c for c in window.iter('control') if c.get('type') == 'multiimage']
    # calm, or with the glitches of the setting (test_confuse_glitch.py)
    assert [s.findtext('imagepath') for s in spinners] == ['ui/spinner', 'ui/spinner_glitch']
    for spinner in spinners:
        assert spinner.find('imagepath').get('colordiffuse') == 'text'
        assert (spinner.findtext('fadetime'), spinner.findtext('loop')) == ('0', 'true')


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


def test_hero_plot_stays_readable_on_a_white_picture():
    """The worst case: a white picture under the fade, in the colour bg of Ember. The fade starts low
    and stays light, as asked after the test on the box: the plot over its full width still reads,
    the lines above it are left to the picture (the tags have their own plates)."""
    from test_confuse_look import contrast, rgb
    scrim = ui('hero_scrim.png').getchannel('A')
    bg = (0x0B, 0x0B, 0x10)
    c = constants()
    top, height, left, width = 116, 554, 64, 1792
    for line_top, colour, wide in ((c['LookHeroPlotTop'] + 20, (0xD4, 0xD4, 0xDC), 980),):
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


def test_hero_fade_leaves_the_upper_part_light():
    scrim = ui('hero_scrim.png').getchannel('A')
    column = [scrim.getpixel((0, y)) / 255 for y in range(scrim.height)]
    assert max(column[:round(scrim.height * 0.3)]) < 0.05
    assert max(column) < 0.8


def test_tab_glow_fades_out_before_the_bottom_edge():
    """A tab has 2 px below its line: the glow there ends at the edge instead of being cut by it."""
    glow = ui('tab_glow.png').getchannel('A')
    middle = glow.width // 2
    assert glow.getpixel((middle, glow.height - 1)) < 40
    line = ui('tab_line.png').getchannel('A')
    solid = [y for y in range(line.height) if line.getpixel((line.width // 2, y)) == 255]
    assert all(glow.getpixel((middle, y)) == 255 for y in solid)


def test_what_plays_on_is_wide_and_names_its_title():
    card = look_includes()['LookRowWideCard']
    args = {p.get('name'): p.get('value') for p in next(i for i in card.iter('include') if i.get('content') == 'CutCard').findall('param')}
    assert (args['width'], args['height'], args['mask']) == ('400', '225', 'ui/mask_400x225.png')
    assert (args['glowwidth'], args['glowheight']) == ('448', '273')
    assert any(l.findtext('label') == '$INFO[ListItem.Label]' for l in card.iter('control') if l.get('type') == 'label')
    assert ui('mask_400x225.png').size == (400, 225)


def test_other_rows_show_posters():
    card = look_includes()['LookRowCard']
    cut = next(i for i in card.iter('include') if i.get('content') == 'CutCard')
    assert {p.get('name') for p in cut.findall('param')} == {'image', 'dim', 'focused'}  # CutCard's poster size


def variable(name):
    root = parse(OVERLAY / '1080i' / 'Includes_Look.xml')
    return [v.text for v in next(v for v in root.iter('variable') if v.get('name') == name).findall('value')]


def test_wide_art_is_the_film_or_show_never_a_still():
    """Fanart and wide art are 16:9: nothing is cut. The still of an episode looked like a chapter
    picture on the box."""
    order = variable('LookRowWideArt')
    assert not any('Art(thumb)' in v for v in order)
    assert order.index('$INFO[ListItem.Art(landscape)]') < order.index('$INFO[ListItem.Art(fanart)]') < order.index('$INFO[ListItem.Art(poster)]')
    assert order[-1] == '$INFO[ListItem.Art(poster)]'
    assert variable('LookRowArt') == ['$INFO[ListItem.Art(tvshow.poster)]', '$INFO[ListItem.Art(poster)]']


def test_only_continue_and_next_up_are_wide():
    text = (ROOT / '1080i' / 'Includes_Sections.xml').read_text(encoding='utf-8')
    rows = re.findall(r'<include content="RowBox".*?</include>', text, re.S)
    wide = [r for r in rows if 'LookRowWideCard' in r]
    assert len(wide) == 6
    assert all('$LOCALIZE[31233]' in r or '$LOCALIZE[31234]' in r for r in wide)
    assert all('$VAR[LookRowWideArt]' in r and 'LookRowWideItemWidth' in r for r in wide)


def test_logo_stays_bright_under_the_quick_menu():
    assert 'QuickMenuFade' not in ET.tostring(look_includes()['LookHomeLogo'], encoding='unicode')


def test_a_focused_card_glows():
    texture = next(c for c in look_includes()['LookCardFocus'].iter('control')).find('texture')
    assert texture.text == 'ui/card_halo.png' and texture.get('colordiffuse') == 'card_glow'


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
