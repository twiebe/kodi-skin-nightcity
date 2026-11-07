"""Confuse's fonts and textures: what it needs to draw without boxes, jumping digits, text that spills
out of its button or square corners. Everything is read from the assembled skin (confuse_root)."""
import math
import re
import xml.etree.ElementTree as ET

import pytest
from fontTools.ttLib import TTFont
from PIL import Image, ImageFont

from conftest import ROOT, parse

OVERLAY = ROOT / 'skins' / 'confuse'
FONT_BUDGET = 400_000
MAX_FONT_FILES = 4
TEXTURE_SIDE = 512
FADE_SIDE = 1024
MASK_SIDE = 540  # a mask is as large as its card, the largest being 360 x 540
CARD_RADIUS = 12  # 8 px at 1280 x 720 on a 1920 x 1080 grid; a mask is shown at its own size
HERO_TEXTURES = ('mask_hero', 'hero_scrim')  # half the size of the hero on screen
LOCALIZE = re.compile(r'\$LOCALIZE\[(\d+)\]')


# Kodi's own fonts (media/Fonts), for the fontset a language the skin fonts lack is shown in
KODI_FONTS = ROOT.parent / 'xbmc' / 'media' / 'Fonts'
FONTSET = {'ja_jp': 'Arial'}  # language -> fontset, Default for the others


def fontset_of(lang):
    return FONTSET.get(lang, 'Default')


def font_defs(root, fontset='Default'):
    """name -> (file, size) of a fontset."""
    return {f.findtext('name'): (f.findtext('filename'), int(f.findtext('size')))
            for f in parse(root / '1080i' / 'Font.xml').find("fontset[@id='{}']".format(fontset)).iter('font')}


def font_file(root, filename):
    """The skin's font, else Kodi's of that name; a test skips when Kodi's sources are not at hand."""
    if (root / 'fonts' / filename).is_file():
        return root / 'fonts' / filename
    if not (KODI_FONTS / filename).is_file():
        pytest.skip('Kodi fonts not at {}'.format(KODI_FONTS))
    return KODI_FONTS / filename


def font_names(root):
    return set(font_defs(root))


def used_fonts(root):
    return sorted({root / 'fonts' / name for name, _ in font_defs(root).values()})


LANGUAGES = ('en_gb', 'de_de', 'fr_fr', 'es_es', 'it_it', 'pt_br', 'pl_pl', 'ja_jp')


def strings(root, lang='en_gb'):
    """number -> text in a language: the msgid for English (its msgstr is empty), the msgstr else."""
    text = (root / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
    return {int(m.group(1)): m.group(3) if lang != 'en_gb' else m.group(2)
            for m in re.finditer(r'msgctxt "#(\d+)"\nmsgid "(.*)"\nmsgstr "(.*)"', text)}


def variables(root):
    return {v.get('name'): [val.text or '' for val in v.findall('value')]
            for v in parse(root / '1080i' / 'Variables.xml').iter('variable')}


def texts_of(label, root, texts):
    """Every fixed text a label can show: $LOCALIZE as the string, $VAR as each of its values. A label
    with an info ($INFO) shows what only the player knows: no fixed text, an empty list."""
    label = re.sub(r'\$NUMBER\[(\d+)\]', r'\1', label)  # a number as text (tools/build.py)
    label = LOCALIZE.sub(lambda m: texts.get(int(m.group(1)), m.group(0)), label)
    match = re.search(r'\$VAR\[(\w+)\]', label)
    if match:
        return [t for value in variables(root)[match.group(1)]
                for t in texts_of(label[:match.start()] + value + label[match.end():], root, texts)]
    return [] if '$' in label else [label.replace('\\"', '"')]


def text_width(root, font_name, text, fontset='Default'):
    """Widest of the text as written and in Title Case (Confuse shows titles as written, the
    sources are not all cased the same), at the font's size in Font.xml."""
    filename, size = font_defs(root, fontset)[font_name]
    font = ImageFont.truetype(str(font_file(root, filename)), size)
    return max(font.getlength(text), font.getlength(text.title()))


def look_font(root, include):
    """Font name a Look include sets, and its textoffsetx (None when a parameter sets it)."""
    for inc in parse(root / '1080i' / 'Includes_Look.xml').iter('include'):
        if inc.get('name') == include:
            offset = inc.findtext('.//textoffsetx')
            return inc.findtext('.//font'), int(offset) if offset.isdigit() else None
    raise AssertionError(include)


def params(include):
    return {p.get('name'): p.get('value') for p in include.findall('param')}


def test_font_names_match_nightcity(confuse_root):
    assert font_names(confuse_root) == font_names(ROOT)


def test_every_glyph_the_skin_uses_exists(confuse_root):
    texts = [p.read_text(encoding='utf-8') for p in (confuse_root / '1080i').glob('*.xml')]
    texts += [p.read_text(encoding='utf-8') for p in confuse_root.glob('language/*/strings.po')
              if fontset_of(p.parent.name.split('.')[-1]) == 'Default']
    texts.append((confuse_root / 'scripts' / 'nightcity.py').read_text(encoding='utf-8'))
    chars = {c for text in texts for c in text if ord(c) > 127} | set('ÄÖÜäöüßΩαβЖжЯяБДệờượ')
    assert chars
    for path in used_fonts(confuse_root):
        cmap = TTFont(path).getBestCmap()
        missing = sorted(c for c in chars if ord(c) not in cmap)
        assert not missing, (path.name, missing)


@pytest.mark.parametrize('lang', sorted(FONTSET))
def test_a_language_beyond_the_skin_fonts_has_its_glyphs(confuse_root, lang):
    """A language the skin fonts lack is read in its own fontset: every character of its strings and
    of the skin's own labels is in each file of that fontset, but the underline font, which only
    draws bars."""
    po = (confuse_root / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
    chars = {c for c in ''.join(re.findall(r'^msgstr "(.*)"$', po, re.M)) if ord(c) > 127}
    assert chars
    assert set(font_defs(confuse_root, FONTSET[lang])) == font_names(confuse_root)
    for filename in {f for f, _ in font_defs(confuse_root, FONTSET[lang]).values() if 'Line' not in f}:
        cmap = TTFont(font_file(confuse_root, filename)).getBestCmap()
        assert not sorted(c for c in chars if ord(c) not in cmap), filename


def test_digits_have_one_width(confuse_root):
    for path in used_fonts(confuse_root):
        font = TTFont(path)
        cmap = font.getBestCmap()
        assert len({font['hmtx'][cmap[ord(d)]][0] for d in '0123456789'}) == 1, path.name


def test_font_budget(confuse_root):
    fonts = used_fonts(confuse_root)
    assert all(p.is_file() and p.stat().st_size < FONT_BUDGET for p in fonts), [(p.name, p.stat().st_size) for p in fonts]
    assert len(fonts) <= MAX_FONT_FILES


# fixed-width keys that hold one arrow glyph: the glyph is centred in a pill 20 px narrower than the
# control and has room there, the 34 px text offset of the generic rule is what it does not meet
ARROW_KEYS = {('DialogKeyboard.xml', '◄'), ('DialogKeyboard.xml', '►')}


def fixed_width_buttons(root, lang='en_gb'):
    """(file, label text, width, textoffsetx, font name) of every button of fixed width: a Button or
    PillButton include (Button's width is 220 unless set), and a raw button or radiobutton control."""
    texts = strings(root, lang)
    pill_font, _ = look_font(root, 'LookPillText')
    for path in sorted((root / '1080i').glob('*.xml')):
        tree = parse(path)
        for inc in tree.iter('include'):
            if inc.get('content') in ('Button', 'PillButton'):
                p = params(inc)
                width = p.get('width', '220' if inc.get('content') == 'Button' else 'auto')
                if width.isdigit():
                    for label in texts_of(p.get('label', ''), root, texts):
                        yield path.name, label, int(width), int(p.get('textoffsetx', 34)), pill_font
        for control in tree.iter('control'):
            if control.get('type') in ('button', 'radiobutton') and (control.findtext('width') or '').isdigit():
                offset = (control.findtext('textoffsetx') or '0').strip()
                for label in texts_of(control.findtext('label') or '', root, texts):
                    yield (path.name, label, int(control.findtext('width')),
                           int(offset) if offset.isdigit() else 0, (control.findtext('font') or 'font13').strip())


@pytest.mark.parametrize('lang', LANGUAGES)
def test_fixed_width_labels_fit(confuse_root, lang):
    """A button of fixed width: each text its label can show, plus both text offsets, fits in the
    width, in every language."""
    checked = []
    for name, label, width, offset, font in fixed_width_buttons(confuse_root, lang):
        if not label.strip() or (name, label) in ARROW_KEYS:
            continue
        need = text_width(confuse_root, font, label, fontset_of(lang)) + 2 * offset
        checked.append((name, label))
        assert need <= width, (name, label, round(need), width)
    assert len(checked) >= 40
    if lang == 'en_gb':
        assert ('Custom_1110_Library.xml', 'Sort: Year') in checked and ('DialogKeyboard.xml', 'space') in checked


@pytest.mark.parametrize('lang', LANGUAGES)
def test_main_menu_fits(confuse_root, lang):
    """Every entry of the top menu, shown at once, with the gaps between them: within the list."""
    font_name, offset = look_font(confuse_root, 'LookMenuText')
    texts = strings(confuse_root, lang)
    menu = next(el for el in parse(confuse_root / '1080i' / 'Includes_Home.xml').iter('include') if el.get('name') == 'MainMenu')
    group = next(g for g in menu.iter('control') if g.get('id') == '9100')
    items = [inc for inc in group.findall('include') if inc.get('content') in ('MenuButton', 'TabGap')]
    widths = []
    for inc in items:
        p = params(inc)
        if inc.get('content') == 'TabGap':
            widths.append(int(p['width']))
        else:
            label = texts_of(p['label'], confuse_root, texts)
            assert len(label) == 1, p['label']
            widths.append(text_width(confuse_root, font_name, label[0], fontset_of(lang)) + 2 * offset)
    total = sum(widths) + int(group.findtext('itemgap')) * (len(widths) - 1)
    assert total <= constants()[group.findtext('width')], (round(total), group.findtext('width'))


def overlay_textures():
    return sorted((OVERLAY / 'media' / 'ui').glob('*.png'))


def test_textures_are_white_and_small():
    textures = overlay_textures()
    assert textures
    for path in textures:
        image = Image.open(path).convert('RGBA')
        limit = FADE_SIDE if path.stem in HERO_TEXTURES or 'fade' in path.stem else MASK_SIDE if path.stem.startswith('mask_') else TEXTURE_SIDE
        assert max(image.size) <= limit, (path.name, image.size)
        if path.stem == 'page_wash':  # opaque grey, multiplied by the ground's colour
            assert image.getchannel('A').getextrema() == (255, 255)
            continue
        colours = {rgba[:3] for _, rgba in image.getcolors(image.width * image.height) if rgba[3]}
        assert colours <= {(255, 255, 255)}, path.name


def has_cut_corner(path):
    """A straight 45 degree cut at the top right of the opaque part: the transparent run at the right
    end of the first rows grows by one pixel per row. (A round corner grows by 2 px, then 1.8, ...)"""
    alpha = Image.open(path).convert('RGBA').getchannel('A')
    box = alpha.point(lambda a: 255 if a >= 128 else 0).getbbox()
    if not box or min(box[2] - box[0], box[3] - box[1]) < 16:
        return False
    runs = []
    for y in range(box[1], box[1] + 4):
        run = 0
        while run < box[2] - box[0] and alpha.getpixel((box[2] - 1 - run, y)) < 128:
            run += 1
        runs.append(run)
    diffs = [a - b for a, b in zip(runs, runs[1:])]
    return runs[0] >= 4 and all(0.8 <= d <= 1.2 for d in diffs)


def test_no_cut_corner_texture_left(confuse_root):
    """Each texture of the tree with a cut corner (cut*, check boxes, spin signs, ...) is the overlay's
    rounded twin, never Nightcity's: a root texture with a cut corner has a twin of its name."""
    cut = sorted({p.name for p in (ROOT / 'media' / 'ui').glob('*.png') if has_cut_corner(p)}
                 | {p.name for p in (ROOT / 'media' / 'ui').glob('cut*.png')})  # the glowing ones are blurred
    assert {'cut.png', 'cut_btn.png', 'check_on_pad.png', 'spin_plus_focus.png'} <= set(cut)
    for name in cut:
        twin = OVERLAY / 'media' / 'ui' / name
        assert twin.is_file(), name
        assert not has_cut_corner(twin), name
        assert (confuse_root / 'media' / 'ui' / name).read_bytes() == twin.read_bytes(), name


def test_masks_have_round_corners(confuse_root):
    masks = sorted((confuse_root / 'media' / 'ui').glob('mask_*.png'))
    assert {p.name for p in masks} >= {p.name for p in (ROOT / 'media' / 'ui').glob('mask_*.png')}
    # the first half-covered pixel of the top row of a circle of the radius
    expected = CARD_RADIUS - math.sqrt(CARD_RADIUS ** 2 - (CARD_RADIUS - 0.5) ** 2) - 0.5
    for path in masks:
        alpha = Image.open(path).convert('RGBA').getchannel('A')
        w, h = alpha.size
        if path.stem in HERO_TEXTURES:
            continue
        assert '{}x{}'.format(w, h) in path.name
        assert [alpha.getpixel(c) for c in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))] == [0] * 4, path.name
        assert alpha.getpixel((w // 2, h // 2)) == 255
        assert alpha.getpixel((w // 2, 0)) == 255 and alpha.getpixel((0, h // 2)) == 255
        first = next(x for x in range(w) if alpha.getpixel((x, 0)) >= 128)
        assert abs(first - expected) <= 1.5, (path.name, first)


def test_fonts_carry_no_kerning_table(confuse_root):
    """Kodi 21 takes only the offsets of HarfBuzz's result and the advance of each glyph alone
    (GUIFontTTF.cpp:591, 657, 1058), and Manrope's kerning is advance only: GPOS never reaches the
    screen, so it stays out of the fonts."""
    for path in used_fonts(confuse_root):
        assert 'GPOS' not in TTFont(path), path.name


def test_only_licences_of_fonts_used_ship(confuse_root):
    """ConfuseUI holds Manrope, Noto Sans Symbols 2 and JetBrains Mono glyphs: those licences ship, the
    Nightcity-only ones (Rajdhani, Share Tech Mono) do not."""
    shipped = {p.name for p in (confuse_root / 'fonts').glob('*OFL.txt')}
    assert shipped == {'OFL.txt', 'JetBrainsMono-OFL.txt', 'NotoSansSymbols2-OFL.txt'}


def test_confuse_never_draws_the_line_font_as_text(confuse_root):
    """font_caps_line is Nightcity's font of bars: Nightcity draws a label in it over the same label in
    font_caps to underline it. In Confuse it is the text font, so such a label would paint over the
    text. No layout file draws it; the season tab's line is a texture."""
    for path in sorted((confuse_root / '1080i').glob('*.xml')):
        if path.name == 'Font.xml':
            continue
        used = [el for el in parse(path).iter() if (el.text or '').strip() == 'font_caps_line' or el.get('value') == 'font_caps_line']
        assert not used, path.name


def test_look_includes_have_the_form_kodi_accepts():
    """Kodi drops an include that has <param> but no <definition> (GUIIncludes.cpp:223-226) and logs
    it at every call, and the test of the log fails on that. The tests' own expansion (navigation.py)
    is more lenient. An include without content is written <definition/>."""
    for path in (ROOT / '1080i' / 'Includes_Look.xml', OVERLAY / '1080i' / 'Includes_Look.xml'):
        for inc in parse(path).iter('include'):
            if not inc.get('name'):
                continue
            has_definition = inc.find('definition') is not None
            assert has_definition or inc.find('param') is None, (path.parent.parent.name, inc.get('name'), 'param without definition')
            if len(inc) == 0:
                raise AssertionError((path.parent.parent.name, inc.get('name'), 'empty include, use <definition/>'))


# --- the look of the cut through: Home, grid, info page, player ---------------------------------

CUT_WINDOWS = ('Home.xml', 'Custom_1110_Library.xml', 'MyVideoNav.xml', 'DialogVideoInfo.xml', 'VideoOSD.xml',
               'DialogSeekBar.xml', 'VideoFullScreen.xml')
CARD = (200, 300)  # the card of a row of Home
SHADOW_PAST_CARD = 24  # px of LookCardFocus's texture past the card, before the zoom


def look_includes(root=OVERLAY):
    return {inc.get('name'): inc for inc in parse(root / '1080i' / 'Includes_Look.xml').iter('include') if inc.get('name')}


def constants(root=OVERLAY):
    return {c.get('name'): float(c.text) for c in parse(root / '1080i' / 'Includes_Look.xml').iter('constant')}


def colours(root):
    return {c.get('name'): c.text for c in parse(root / 'colors' / 'defaults.xml').iter('color')}


def channel(c):
    c /= 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    return 0.2126 * channel(rgb[0]) + 0.7152 * channel(rgb[1]) + 0.0722 * channel(rgb[2])


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def rgb(argb):
    return tuple(int(argb[i:i + 2], 16) for i in (2, 4, 6))


def windows_expanded(root):
    from navigation import load
    for name in CUT_WINDOWS:
        yield name, load(name, layout=root / '1080i')


def test_text_stays_readable_on_a_white_fanart(confuse_root):
    """The fanart is drawn through the mask of FanartBackdrop, in the alpha of the palette: a white
    picture gives this over the base colour. Page text (x 0 to 900, y 300 to 1080) keeps 4.5:1."""
    palette = colours(confuse_root)
    text, bg = rgb(palette['text']), rgb(palette['bg'])
    fanart_alpha = int(palette['fanart'][:2], 16) / 255
    mask = Image.open(confuse_root / 'media' / 'ui' / 'fade_r.png').convert('RGBA').getchannel('A')
    worst = 99
    for y in range(300, 1080, 10):
        for x in range(0, 900, 10):
            alpha = fanart_alpha * mask.getpixel((x * mask.width // 1920, y * mask.height // 1080)) / 255
            back = tuple(255 * alpha + c * (1 - alpha) for c in bg)
            worst = min(worst, contrast(text, back))
    assert worst >= 4.5, worst


def test_info_page_stays_readable_on_a_white_fanart(confuse_root):
    """With its fade over the mask: 4.5:1 for text across the page, 3:1 for the muted keys of the
    facts at the right (x 1400 to 1860, y 120 to 420)."""
    palette = colours(confuse_root)
    text, mute, bg = rgb(palette['text']), rgb(palette['text_mute']), rgb(palette['bg'])
    fanart_alpha = int(palette['fanart'][:2], 16) / 255
    mask = Image.open(confuse_root / 'media' / 'ui' / 'fade_r.png').convert('RGBA').getchannel('A')
    fade = Image.open(confuse_root / 'media' / 'ui' / 'info_fade.png').convert('RGBA').getchannel('A')

    def back(x, y):
        alpha = fanart_alpha * mask.getpixel((x * mask.width // 1920, y * mask.height // 1080)) / 255
        over = [255 * alpha + c * (1 - alpha) for c in bg]
        cover = fade.getpixel((x * fade.width // 1920, 0)) / 255
        return tuple(c * cover + o * (1 - cover) for c, o in zip(bg, over))

    assert min(contrast(text, back(x, y)) for x in range(0, 1920, 20) for y in range(0, 1080, 20)) >= 4.5
    assert min(contrast(mute, back(x, y)) for x in range(1400, 1860, 20) for y in range(120, 420, 20)) >= 3


def test_player_text_stays_readable_on_a_white_picture(confuse_root):
    """Over a white video frame the text block of the player, from y 440 down. The fade is light by
    choice (after the test on the box): large and bold text there, 3:1 is the bar."""
    palette = colours(confuse_root)
    scrim, text = palette['scrim'], rgb(palette['text'])
    fade = Image.open(confuse_root / 'media' / 'ui' / 'fade_b.png').convert('RGBA').getchannel('A')
    worst = 99
    for y in range(440, 1080, 10):
        place = (y - 340) / 740
        alpha = int(scrim[:2], 16) / 255 * fade.getpixel((0, round(place * (fade.height - 1)))) / 255
        back = tuple(c * alpha + 255 * (1 - alpha) for c in rgb(scrim))
        worst = min(worst, contrast(text, back))
    assert worst >= 3, worst


def test_player_fades_end_clear(confuse_root):
    """Where the two images end there is no step over the video."""
    for name, end in (('fade_b.png', 0), ('fade_t.png', -1)):
        fade = Image.open(confuse_root / 'media' / 'ui' / name).convert('RGBA').getchannel('A')
        assert fade.getpixel((0, range(fade.height)[end])) == 0, name


def test_fanart_mask_follows_the_draft(confuse_root):
    """The draft's scrim, as what stays of the picture: .24 of the fade left at the right edge and
    nothing from the bottom in the upper part, so the picture keeps 76 % top right, and it is gone
    at the bottom left."""
    mask = Image.open(confuse_root / 'media' / 'ui' / 'fade_r.png').convert('RGBA').getchannel('A')
    w, h = mask.size
    assert abs(mask.getpixel((w - 1, 0)) / 255 - 0.76) < 0.02
    assert abs(mask.getpixel((0, 0)) / 255 - 0.06) < 0.02
    assert mask.getpixel((0, h - 1)) < 5
    assert abs(mask.getpixel((w * 48 // 100, 0)) / 255 - 0.24) < 0.02


def test_background_without_fanart_is_the_base_colour():
    """Under everything one opaque picture: lighter at the top, at the bottom the base colour."""
    images = look_includes()['LookBackground'].findall('control')
    assert [i.get('type') for i in images] == ['image']
    assert images[0].find('texture').get('colordiffuse') == 'surface'
    assert images[0].findtext('texture') == 'ui/page_wash.png'
    wash = Image.open(OVERLAY / 'media' / 'ui' / 'page_wash.png').convert('RGB')
    assert wash.getpixel((0, 0))[0] == 255
    assert abs(wash.getpixel((0, wash.height - 1))[0] * 0x1A / 255 - 0x0B) <= 1


def test_card_has_a_placeholder(confuse_root):
    """A round surface under the poster on either state: no artwork leaves a card, not a hole. A
    9-slice and no mask, so an unfocused card has one masked quad, its artwork. Its corner is the
    corner of the mask, so the plate does not show past the artwork."""
    images = list(look_includes()['LookCardFrame'].iter('control'))
    assert [i.findtext('visible') for i in images] == [None]
    texture = images[0].find('texture')
    assert texture.get('colordiffuse') == 'surface'
    assert texture.get('diffuse') is None
    assert texture.get('border') == str(CARD_RADIUS)
    plate = Image.open(confuse_root / 'media' / texture.text).convert('RGBA').getchannel('A')
    mask = Image.open(confuse_root / 'media' / 'ui' / 'mask_200x300.png').convert('RGBA').getchannel('A')
    for y in range(CARD_RADIUS):
        for x in range(CARD_RADIUS):
            assert abs(plate.getpixel((x, y)) - mask.getpixel((x, y))) <= 8, (x, y)


def test_card_art_is_round_in_both_states():
    """Round corners for every card, without the look of the crop moving the mask."""
    for name in ('LookCardArt', 'LookCardArtFocused'):
        include = look_includes()[name]
        assert include.find('.//texture').get('diffuse') == '$PARAM[mask]', name
        assert include.find('.//aspectratio').get('scalediffuse') == 'false', name


def test_fullscreen_alpha_budget(confuse_root):
    """After resolving, at most two full screen images with alpha over the ground per window. All the
    backdrops of a window count as one: they are for different pages or titles, one shows at a time."""
    palette = colours(confuse_root)
    for name, window in windows_expanded(confuse_root):
        layers = 0
        fanart = False
        for image in window.iter('control'):
            if image.get('type') != 'image' or image.findtext('width') != '1920' or image.findtext('height') != '1080':
                continue
            texture = image.find('texture')
            if texture is None:
                continue
            if image.findtext('description') == 'fanart backdrop':
                fanart = True
                continue
            colour = palette.get(texture.get('colordiffuse'), 'FFFFFFFF')
            if texture.text in ('ui/white.png', 'ui/page_wash.png') and colour.startswith('FF'):
                continue
            layers += 1
        assert layers + fanart <= 2, (name, layers, fanart)


def test_no_endless_animation():
    for name, include in look_includes().items():
        text = ET.tostring(include, encoding='unicode').lower()
        assert 'pulse' not in text and 'loop=' not in text, name


def test_card_focus_keeps_the_row_layout(confuse_root):
    """The card grows by animation only, so the row does not move and no focus target changes."""
    c = constants()
    assert c['LookCardFocusZoom'] == 108
    assert c['LookCardFocusTime'] == 120
    for inc in parse(confuse_root / '1080i' / 'Includes_Home.xml').iter('control'):
        item, focused = inc.find('itemlayout'), inc.find('focusedlayout')
        if item is not None and focused is not None:
            assert (item.get('width'), item.get('height')) == (focused.get('width'), focused.get('height'))


def test_row_constants_add_up():
    """Constants cannot add up in Kodi, so the pairs are written out; they keep the card where the
    shared layout has it, and the room under it. The padding holds the zoomed card and its shadow."""
    c, n = constants(), constants(ROOT)
    assert c['LookRowListLeft'] + c['LookRowItemLeft'] == n['LookRowListLeft'] + n['LookRowItemLeft'] == 64
    assert c['LookRowListTop'] + c['LookRowItemTop'] == n['LookRowListTop'] + n['LookRowItemTop'] == 78
    assert c['LookRowListLeft'] + c['LookRowListWidth'] == 1920
    assert c['LookRowListTop'] + c['LookRowListHeight'] == n['LookRowListTop'] + n['LookRowListHeight'] == 468
    assert c['LookRowListHeight'] - c['LookRowItemTop'] == n['LookRowListHeight'] - n['LookRowItemTop']
    zoom = c['LookCardFocusZoom'] / 100
    assert c['LookRowItemTop'] >= CARD[1] * (zoom - 1) / 2 + SHADOW_PAST_CARD * zoom


def test_row_shows_no_strip_of_the_card_before(confuse_root):
    """The list starts where the card before ends: seen on the shot, a wider ItemLeft leaves a hard
    cut strip of it. The cards stand 44 px apart for the room of the glow, posters and wide cards."""
    c = constants()
    assert (c['LookRowListLeft'], c['LookRowItemLeft'], c['LookRowListWidth']) == (20, 44, 1900)
    assert c['LookRowItemLeft'] + CARD[0] == c['LookRowItemWidth']
    assert c['LookRowItemLeft'] + 400 == c['LookRowWideItemWidth']


def test_shadow_margin_matches_its_texture(confuse_root):
    """LookCardFocus draws cut_glow.png 24 px past the card, at its fixed offset: card + 48 from the
    callers. Its border holds the rounded part and the blur, and it fades out before its own edge."""
    focus = look_includes()['LookCardFocus']
    image = focus.find('.//control')
    assert (image.findtext('left'), image.findtext('top')) == ('-24', '-24')
    assert (image.findtext('width'), image.findtext('height')) == ('$PARAM[glowwidth]', '$PARAM[glowheight]')
    texture = Image.open(confuse_root / 'media' / image.findtext('texture')).convert('RGBA').getchannel('A')
    assert all(texture.getpixel(c) < 3 for c in ((0, 0), (texture.width - 1, 0), (0, texture.height - 1)))
    assert int(image.find('texture').get('border')) * 2 <= texture.width


def test_focus_ring_is_four_to_five_px_on_screen(confuse_root):
    """Measured on the texture at the middle of an edge, times the zoom."""
    ring = look_includes()['LookCardFocusRing'].find('.//texture')
    alpha = Image.open(confuse_root / 'media' / ring.text).convert('RGBA').getchannel('A')
    thick = sum(alpha.getpixel((x, alpha.height // 2)) / 255 for x in range(alpha.width // 2))
    assert 4 <= thick * constants()['LookCardFocusZoom'] / 100 <= 5, thick


def test_information_marks_keep_their_condition(confuse_root):
    """The dot stands where Nightcity has its dog-ear, under the same condition, in every window. On
    Home the hero has no poster here, so its dot is gone with it; the cards keep theirs."""
    from navigation import load
    from conftest import window_files
    found = 0
    for path in window_files():
        marks = [[el.findtext('visible') for el in load(path.name, layout=layout).iter('control')
                  if el.get('type') == 'image' and el.findtext('texture') == texture]
                 for layout, texture in ((ROOT / '1080i', 'ui/dogear.png'), (confuse_root / '1080i', 'ui/dot.png'))]
        if path.name == 'Home.xml':
            assert marks[1] and set(marks[1]) <= set(marks[0])
        else:
            assert marks[0] == marks[1], path.name
        found += len(marks[0])
    assert found >= 20


def test_unwatched_dot_keeps_inside_the_rounded_corner():
    """Warm white, not the focus colour, inset so it does not touch the round corner of the card."""
    dot = list(look_includes()['LookCardUnwatched'].iter('control'))[-1]
    assert dot.findtext('visible') == '$PARAM[visible]'
    assert dot.find('texture').get('colordiffuse') == 'text'
    assert int(dot.findtext('right')) >= 8 and int(dot.findtext('bottom')) >= 8


def test_waiting_cursor_shows_nothing_without_the_focus(confuse_root):
    """The position bar's cursor lies at the corner of the window until it has the focus. A look that
    ignores a button's colour still has to honour this: the pill showed on the shot."""
    from navigation import load
    for name in ('Custom_1110_Library.xml', 'MyMusicNav.xml'):
        for root in (confuse_root, ROOT):
            cursor = next(c for c in load(name, layout=root / '1080i').iter('control') if c.get('id') == '5200')
            assert cursor.find('texturenofocus').get('colordiffuse') == '00FFFFFF', (name, root)


def test_episode_mark_clears_the_focused_ring():
    """Seen on the shot: a focused still reaches 18 px over its place, the mark must stay above."""
    mark = look_includes()['LookEpisodeMark'].find('.//control')
    assert int(mark.findtext('top')) + int(mark.findtext('height')) <= -18


def test_decoration_is_gone(confuse_root):
    for name, window in windows_expanded(confuse_root):
        names = {el.text for el in window.iter() if el.text} | {v for el in window.iter() for v in el.attrib.values()}
        words = ' '.join(names)
        for gone in ('glitch_a', 'glitch_b', 'petrol_glow', 'spot_more', 'dogear'):
            assert gone not in words, (name, gone)


def test_rows_have_no_numbers():
    label = look_includes()['LookNumberedRowLabel'].findtext('.//label')
    assert 'PARAM[num]' not in label and 'accent2' not in label
    assert look_includes()['LookNumberedRowLabel'].findtext('.//font') == 'font_caps'
    assert len(look_includes()['LookRowNumber'].find('definition')) == 0


def test_buttons_are_pills(confuse_root):
    """Unfocused a pill of white at .15, focused filled in the accent with dark text; borders hold the full
    round end of the 54 px pill and its 10 px padding."""
    palette = colours(confuse_root)
    fill = look_includes()['LookButtonFill'].find('texturefocus')
    outline = look_includes()['LookButtonOutline'].find('.//texturenofocus')
    assert fill.get('colordiffuse') == 'focus' and palette['focus'] == 'FFFF5B35'
    assert (fill.text, outline.text) == ('ui/pill_halo.png', 'ui/pill_pad.png')
    assert fill.get('border') == outline.get('border') == '37'
    assert palette[outline.get('colordiffuse')] == '26FFFFFF'
    assert look_includes()['LookPillText'].findtext('.//focusedcolor') == 'focus_text'


def test_tab_focus_differs_from_the_shown_tab(confuse_root):
    """A tab takes the focus and shows its page at once, so the alt state has to tell them apart: the
    shown tab has the line, with the focus the same line glows. No plate, one shape."""
    textures = look_includes()['LookTabTextures']
    for tag in ('texturefocus', 'alttexturefocus'):
        assert textures.findtext(tag) == 'ui/tab_glow.png', tag
    assert textures.findtext('alttexturenofocus') == 'ui/tab_line.png'
    for tag in ('texturefocus', 'alttexturefocus', 'alttexturenofocus'):
        assert textures.find(tag).get('colordiffuse') == 'accent', tag
    line = Image.open(confuse_root / 'media' / 'ui' / 'tab_line.png').convert('RGBA').getchannel('A')
    assert 4 <= sum(line.getpixel((line.width // 2, y)) / 255 for y in range(line.height)) <= 5
    glow = Image.open(confuse_root / 'media' / 'ui' / 'tab_glow.png').convert('RGBA').getchannel('A')
    assert glow.height == line.height
    assert glow.getpixel((glow.width // 2, 2)) == 0
    assert glow.getpixel((glow.width // 2, line.height - 10)) > 20
    assert glow.getpixel((glow.width // 2, line.height - 4)) == 255


def test_tab_text_with_the_focus_is_readable_white(confuse_root):
    """White over the glow behind the text, on the base colour and on the brightest a white fanart gets
    under a row's tabs (x up to 900, y from 300)."""
    tab = look_includes()['LookTabText']
    assert tab.findtext('.//focusedcolor') == 'text'
    assert '[COLOR text]' in tab.findtext('.//altlabel') and '[B]' not in tab.findtext('.//altlabel')
    palette = colours(confuse_root)
    text, bg, amber = rgb(palette['text']), rgb(palette['bg']), rgb(palette['accent'])
    plate = Image.open(confuse_root / 'media' / 'ui' / 'tab_glow.png').convert('RGBA').getchannel('A')
    cover = plate.getpixel((plate.width // 2, plate.height // 2)) / 255
    mask = Image.open(confuse_root / 'media' / 'ui' / 'fade_r.png').convert('RGBA').getchannel('A')
    alpha = int(palette['fanart'][:2], 16) / 255 * max(
        mask.getpixel((x * mask.width // 1920, y * mask.height // 1080))
        for x in range(0, 900, 20) for y in range(300, 1080, 20)) / 255
    for back in (bg, tuple(255 * alpha + c * (1 - alpha) for c in bg)):
        assert contrast(text, tuple(a * cover + b * (1 - cover) for a, b in zip(amber, back))) >= 4.5


def test_tab_lines_keep_their_round_ends(confuse_root):
    """Kodi stretches what lies between the borders: with a round end there, the line turns into a
    lens, seen on the shot. Between the borders every column is the same."""
    for name, include, tag in (('tab_line.png', 'LookTabTextures', 'alttexturenofocus'),
                               ('tab_glow.png', 'LookTabTextures', 'alttexturefocus')):
        border = int(look_includes()[include].find(tag).get('border').split(',')[0])
        alpha = Image.open(confuse_root / 'media' / 'ui' / name).convert('RGBA').getchannel('A')
        assert alpha.width > 2 * border, name
        columns = [[alpha.getpixel((x, y)) for y in range(alpha.height)] for x in range(border, alpha.width - border)]
        assert all(abs(a - b) <= 2 for column in columns for a, b in zip(column, columns[0])), name


def test_every_tab_has_the_look_of_a_tab():
    """Tabs with a behaviour of their own (the credits of the info page) still take the Look."""
    tab = next(el for el in parse(ROOT / '1080i' / 'Includes_Tmdb.xml').iter('include') if el.get('name') == 'CreditsTab')
    used = {inc.get('content') or inc.text for inc in tab.iter('include')}
    assert {'LookTabText', 'LookTabTextures'} <= used


def test_season_tab_tells_focus_from_shown(confuse_root):
    """Like the other tabs: the shown season has the line and white text, with the focus the same line
    glows. The glow first, it must not lie over the text. The list starts
    10 px further left and the text 10 px in, as a list cuts what lies left of it."""
    from navigation import load
    window = load('DialogVideoInfo.xml', layout=confuse_root / '1080i')
    seasons = next(c for c in window.iter('control') if c.get('id') == '5200')
    plate, text, line = seasons.find('focusedlayout').findall('control')
    assert plate.findtext('texture') == 'ui/tab_glow.png' and plate.findtext('visible') == 'Control.HasFocus(5200)'
    assert text.get('type') == 'label' and text.findtext('textcolor') == 'text'
    assert line.findtext('texture') == 'ui/tab_line.png' and line.findtext('visible') == '!Control.HasFocus(5200)'
    assert plate.find('texture').get('colordiffuse') == line.find('texture').get('colordiffuse') == 'accent'
    assert (plate.findtext('width'), plate.findtext('left') or '0') == (line.findtext('width'), line.findtext('left') or '0')
    assert text.findtext('left') == '10'
    assert seasons.findtext('left') == 'LookSeasonListLeft'
    assert constants()['LookSeasonListLeft'] + int(text.findtext('left')) == 64
    unshown = seasons.find('itemlayout').find('control')
    assert unshown.findtext('left') == '10' and unshown.findtext('textcolor') == 'text_mute'
    assert constants(ROOT)['LookSeasonListLeft'] == 64


def test_genre_tabs_start_over_the_cards(confuse_root):
    """No row number in front of them in this look: the text of the first tab (behind its 24 px gap
    and 10 px of padding) stands over the first card. Nightcity keeps its number's room."""
    from navigation import load
    assert constants(ROOT)['LookGenreTabsLeft'] == 73
    window = load('Home.xml', layout=confuse_root / '1080i')
    tabs = [c for c in window.iter('control') if c.get('type') == 'grouplist' and c.findtext('left') == 'LookGenreTabsLeft']
    assert tabs
    for grouplist in tabs:
        gap, tab = grouplist.findall('control')[:2]
        assert constants()['LookGenreTabsLeft'] + int(gap.findtext('width')) + int(tab.findtext('textoffsetx')) == 64
    assert 'name="left" value="73"' not in (ROOT / '1080i' / 'Includes_Sections.xml').read_text(encoding='utf-8')


def test_cut_decoration_textures_are_removed(confuse_root):
    for name in ('petrol_glow.png', 'dogear.png'):
        assert not (confuse_root / 'media' / 'ui' / name).exists(), name
    for path in sorted((confuse_root / '1080i').glob('*.xml')):
        text = path.read_text(encoding='utf-8')
        assert 'petrol_glow' not in text and 'dogear.png' not in text, path.name
