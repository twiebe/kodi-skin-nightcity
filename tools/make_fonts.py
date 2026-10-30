#!/usr/bin/env python3
"""Build the RetroUI fonts in fonts/ from Rajdhani plus symbols from Noto Sans Symbols 2 and
JetBrains Mono (arrows and box drawing, which Noto Sans Symbols 2 lacks; Greek, Cyrillic and
Vietnamese letters, which Rajdhani lacks).

RetroUI-<weight>.ttf      Rajdhani with the symbols it lacks (◢ ▶ ❚ ⏮ ⏭ ✓ ★ ⏻, box drawing, ...)
RetroUIWide-<weight>.ttf  the same, every glyph 0.1 em wider (Kodi labels have no letter spacing)
RetroUIWideLine-SemiBold.ttf  every glyph of RetroUIWide-SemiBold a bar as wide as its letter, a
                          little below the baseline: the same text in it underlines the text
                          (font_caps_line; a list layout has no auto width for an image)

All sources are OFL; the results are renamed, as the OFL asks for modified versions.

python tools/make_fonts.py
"""
import copy
import pathlib

from fontTools.ttLib import TTFont

FONTS = pathlib.Path(__file__).resolve().parents[1] / 'fonts'
SYMBOLS = ['NotoSansSymbols2-Regular.ttf', 'JetBrainsMono-Regular.ttf']  # first match wins
# codepoints taken from the symbol font when Rajdhani has none
RANGES = [(0x0180, 0x024F), (0x0300, 0x036F), (0x0370, 0x03FF), (0x0400, 0x04FF), (0x1E00, 0x1EFF),  # Latin Ext-B, accents, Greek, Cyrillic, Vietnamese
          (0x2190, 0x21FF), (0x2300, 0x23FF), (0x2500, 0x25FF), (0x2600, 0x26FF), (0x2700, 0x27BF)]
TRACKING = 100  # font units, UPM 1000
# bars of the line font, font units: below the baseline where the season tab's line was (y 44
# of its 44 px label), 2 px high at 26 px (font_caps), each reaching a little over its advance
# so neighbours overlap and the ends overhang the text
LINE_TOP, LINE_BOTTOM, LINE_OVERHANG = -485, -562, 60


def copy_glyph(src, dst, name, done):
    """Copy glyph `name` (and the components it is built from) from src into dst."""
    if name in done:
        return done[name]
    new, n = name, 0
    while new in dst.getGlyphOrder():
        n += 1
        new = 'sym{}_{}'.format(n, name)
    done[name] = new
    glyph = copy.deepcopy(src['glyf'][name])
    if glyph.isComposite():
        for comp in glyph.components:
            comp.glyphName = copy_glyph(src, dst, comp.glyphName, done)
    order = dst.getGlyphOrder() + [new]
    dst.setGlyphOrder(order)
    dst['glyf'].glyphOrder = order
    dst['glyf'][new] = glyph
    dst['hmtx'][new] = src['hmtx'][name]
    return new


def add_symbols(font, sources):
    cmap = font.getBestCmap()
    added = {}
    for symbols in sources:
        sym_cmap = symbols.getBestCmap()
        done = {}
        for lo, hi in RANGES:
            for cp in range(lo, hi + 1):
                if cp not in cmap and cp not in added and cp in sym_cmap:
                    added[cp] = copy_glyph(symbols, font, sym_cmap[cp], done)
    for table in font['cmap'].tables:
        if table.isUnicode():
            table.cmap.update({cp: g for cp, g in added.items() if table.format != 4 or cp <= 0xFFFF})
    font['maxp'].numGlyphs = len(font.getGlyphOrder())


def track(font, units):
    """Widen every glyph by `units`, half of it on each side."""
    glyf = font['glyf']
    for name in font.getGlyphOrder():
        advance, lsb = font['hmtx'][name]
        glyph = glyf[name]
        # composites follow their components, which are moved on their own
        if not glyph.isComposite() and glyph.numberOfContours > 0:
            glyph.coordinates.translate((units // 2, 0))
        glyph.recalcBounds(glyf)
        font['hmtx'][name] = (advance + units, lsb + units // 2 if glyph.numberOfContours else lsb)


def rename(font, family, style):
    full = '{} {}'.format(family, style)
    ps = '{}-{}'.format(family.replace(' ', ''), style.replace(' ', ''))
    for record in font['name'].names:
        if record.nameID in (1, 16):
            record.string = family
        elif record.nameID == 4:
            record.string = full
        elif record.nameID == 6:
            record.string = ps
        elif record.nameID == 3:
            record.string = ps + ';retrowave'


def build(weight, wide):
    font = TTFont(FONTS / 'Rajdhani-{}.ttf'.format(weight))
    add_symbols(font, [TTFont(FONTS / name) for name in SYMBOLS])
    family = 'RetroUI'
    if wide:
        track(font, TRACKING)
        family = 'RetroUI Wide'
    rename(font, family, weight)
    out = FONTS / '{}-{}.ttf'.format(family.replace(' ', ''), weight)
    font.save(out)
    return out


def cell(font):
    """Kodi's cell of a font (GUIFontTTF): top and bottom, font units; a label is centred on it."""
    head, hhea = font['head'], font['hhea']
    return max(head.yMax, hhea.ascent), min(head.yMin, hhea.descent)


def build_line(source):
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    font = TTFont(source)
    text_top, text_bottom = cell(font)
    glyf = font['glyf']
    for name in font.getGlyphOrder():
        advance = font['hmtx'][name][0]
        pen = TTGlyphPen(None)
        pen.moveTo((-LINE_OVERHANG, LINE_BOTTOM))
        pen.lineTo((-LINE_OVERHANG, LINE_TOP))
        pen.lineTo((advance + LINE_OVERHANG, LINE_TOP))
        pen.lineTo((advance + LINE_OVERHANG, LINE_BOTTOM))
        pen.closePath()
        glyf[name] = pen.glyph()
        glyf[name].recalcBounds(glyf)
        font['hmtx'][name] = (advance, -LINE_OVERHANG)
    # a cell with the same middle as the text's, so both labels share a baseline, holding the
    # bars (Kodi clips what leaves the cell)
    head = font['head']
    font.recalcBBoxes = False
    head.xMin = min(glyf[name].xMin for name in font.getGlyphOrder())
    head.xMax = max(glyf[name].xMax for name in font.getGlyphOrder())
    head.yMin = min(LINE_BOTTOM, text_bottom)
    head.yMax = text_top + text_bottom - head.yMin
    rename(font, 'RetroUI Wide Line', 'SemiBold')
    out = FONTS / 'RetroUIWideLine-SemiBold.ttf'
    font.save(out)
    return out


def main():
    for weight in ('Medium', 'SemiBold', 'Bold'):
        print(build(weight, wide=False))
    for weight in ('SemiBold', 'Bold'):
        print(build(weight, wide=True))
    print(build_line(FONTS / 'RetroUIWide-SemiBold.ttf'))


if __name__ == '__main__':
    main()
