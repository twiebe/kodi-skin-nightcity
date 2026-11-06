"""Confuse's fonts and textures: what it needs to draw without boxes, jumping digits, text that spills
out of its button or square corners. Everything is read from the assembled skin (confuse_root)."""
import math
import re
import xml.etree.ElementTree as ET

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
LOCALIZE = re.compile(r'\$LOCALIZE\[(\d+)\]')


def font_defs(root):
    """name -> (file, size) of the Default fontset."""
    return {f.findtext('name'): (f.findtext('filename'), int(f.findtext('size')))
            for f in parse(root / '1080i' / 'Font.xml').iter('font')}


def font_names(root):
    return set(font_defs(root))


def used_fonts(root):
    return sorted({root / 'fonts' / name for name, _ in font_defs(root).values()})


def strings(root):
    """number -> English text (msgid; the msgstr of en_gb is empty)."""
    text = (root / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    return {int(m.group(1)): m.group(2) for m in re.finditer(r'msgctxt "#(\d+)"\nmsgid "(.*)"', text)}


def variables(root):
    return {v.get('name'): [val.text or '' for val in v.findall('value')]
            for v in parse(root / '1080i' / 'Variables.xml').iter('variable')}


def texts_of(label, root, texts):
    """Every fixed text a label can show: $LOCALIZE as the string, $VAR as each of its values. A label
    with an info ($INFO) shows what only the player knows: no fixed text, an empty list."""
    label = LOCALIZE.sub(lambda m: texts.get(int(m.group(1)), m.group(0)), label)
    match = re.search(r'\$VAR\[(\w+)\]', label)
    if match:
        return [t for value in variables(root)[match.group(1)]
                for t in texts_of(label[:match.start()] + value + label[match.end():], root, texts)]
    return [] if '$' in label else [label.replace('\\"', '"')]


def text_width(root, font_name, text):
    """Widest of the text as written and in Title Case (Confuse shows titles as written, the
    sources are not all cased the same), at the font's size in Font.xml."""
    filename, size = font_defs(root)[font_name]
    font = ImageFont.truetype(str(root / 'fonts' / filename), size)
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
    texts += [p.read_text(encoding='utf-8') for p in confuse_root.glob('language/*/strings.po')]
    texts.append((confuse_root / 'scripts' / 'nightcity.py').read_text(encoding='utf-8'))
    chars = {c for text in texts for c in text if ord(c) > 127} | set('ÄÖÜäöüßΩαβЖжЯяБДệờượ')
    assert chars
    for path in used_fonts(confuse_root):
        cmap = TTFont(path).getBestCmap()
        missing = sorted(c for c in chars if ord(c) not in cmap)
        assert not missing, (path.name, missing)


def test_digits_have_one_width(confuse_root):
    for path in used_fonts(confuse_root):
        font = TTFont(path)
        cmap = font.getBestCmap()
        assert len({font['hmtx'][cmap[ord(d)]][0] for d in '0123456789'}) == 1, path.name


def test_font_budget(confuse_root):
    fonts = used_fonts(confuse_root)
    assert all(p.is_file() and p.stat().st_size < FONT_BUDGET for p in fonts), [(p.name, p.stat().st_size) for p in fonts]
    assert len(fonts) <= MAX_FONT_FILES


def test_fixed_width_labels_fit(confuse_root):
    """A PillButton of fixed width: each text its label can show, plus both text offsets, fits in the width."""
    font_name, _ = look_font(confuse_root, 'LookPillText')
    texts = strings(confuse_root)
    checked = []
    for path in sorted((confuse_root / '1080i').glob('*.xml')):
        for inc in parse(path).iter('include'):
            if inc.get('content') != 'PillButton':
                continue
            p = params(inc)
            if not p.get('width', '').isdigit():
                continue
            offset = int(p.get('textoffsetx', 34))
            for label in texts_of(p.get('label', ''), confuse_root, texts):
                need = text_width(confuse_root, font_name, label) + 2 * offset
                checked.append((path.name, label))
                assert need <= int(p['width']), (path.name, label, round(need), p['width'])
    assert checked


def test_main_menu_fits(confuse_root):
    """Every entry of the top menu, shown at once, with the gaps between them: within the list."""
    font_name, offset = look_font(confuse_root, 'LookMenuText')
    texts = strings(confuse_root)
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
            widths.append(text_width(confuse_root, font_name, label[0]) + 2 * offset)
    total = sum(widths) + int(group.findtext('itemgap')) * (len(widths) - 1)
    assert total <= int(group.findtext('width')), (round(total), group.findtext('width'))


def overlay_textures():
    return sorted((OVERLAY / 'media' / 'ui').glob('*.png'))


def test_textures_are_white_and_small():
    textures = overlay_textures()
    assert textures
    for path in textures:
        image = Image.open(path).convert('RGBA')
        limit = FADE_SIDE if 'fade' in path.stem else MASK_SIDE if path.stem.startswith('mask_') else TEXTURE_SIDE
        assert max(image.size) <= limit, (path.name, image.size)
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


def test_warm_fade_fades_left_and_bottom():
    """One image for both edges: opaque at the bottom left, clear at the top right, alpha changing
    along each axis."""
    alpha = Image.open(OVERLAY / 'media' / 'ui' / 'warm_fade.png').convert('RGBA').getchannel('A')
    w, h = alpha.size
    assert alpha.getpixel((0, h - 1)) == 255 and alpha.getpixel((w - 1, 0)) == 0
    along_x = [alpha.getpixel((x, h // 2)) for x in range(0, w, max(1, w // 8))]
    along_y = [alpha.getpixel((w // 2, y)) for y in range(0, h, max(1, h // 8))]
    assert along_x == sorted(along_x, reverse=True) and along_x[0] - along_x[-1] > 100
    assert along_y == sorted(along_y) and along_y[-1] - along_y[0] > 100


def test_masks_have_round_corners(confuse_root):
    masks = sorted((confuse_root / 'media' / 'ui').glob('mask_*.png'))
    assert {p.name for p in masks} >= {p.name for p in (ROOT / 'media' / 'ui').glob('mask_*.png')}
    # the first half-covered pixel of the top row of a circle of the radius
    expected = CARD_RADIUS - math.sqrt(CARD_RADIUS ** 2 - (CARD_RADIUS - 0.5) ** 2) - 0.5
    for path in masks:
        alpha = Image.open(path).convert('RGBA').getchannel('A')
        w, h = alpha.size
        assert '{}x{}'.format(w, h) in path.name
        assert [alpha.getpixel(c) for c in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))] == [0] * 4, path.name
        assert alpha.getpixel((w // 2, h // 2)) == 255
        assert alpha.getpixel((w // 2, 0)) == 255 and alpha.getpixel((0, h // 2)) == 255
        first = next(x for x in range(w) if alpha.getpixel((x, 0)) >= 128)
        assert abs(first - expected) <= 1.5, (path.name, first)
