import re

from fontTools.ttLib import TTFont

from conftest import ROOT, layout_files, parse

NAMES = {'font_tiny', 'font_small', 'font_body', 'font_label', 'font_title', 'font_hero', 'font_wordmark',
         'font_caps', 'font_caps_small', 'font_num', 'font_num_small', 'font_clock', 'font_temp', 'font10', 'font12', 'font13', 'font14'}
UI_FONTS = ['RetroUI-Medium.ttf', 'RetroUI-SemiBold.ttf', 'RetroUI-Bold.ttf',
            'RetroUIWide-SemiBold.ttf', 'RetroUIWide-Bold.ttf']
MONO_FONT = 'ShareTechMono-Regular.ttf'
# info tags, formatting tags and placeholders carry no glyphs of their own
TAGS = re.compile(r'\$(INFO|ESCINFO|LOCALIZE|VAR|PARAM|ADDON|NUMBER)\[[^\]]*\]|\[/?[A-Z]+[^\]]*\]|%[0-9]*\$?[a-z]')


def fontsets():
    return {fs.get('id'): fs for fs in parse(ROOT / '1080i' / 'Font.xml').iter('fontset')}


def font_files_by_name():
    return {f.findtext('name'): f.findtext('filename') for f in fontsets()['Default'].iter('font')}


def test_fontsets_same_names():
    sets = fontsets()
    assert set(sets) == {'Default'}
    assert set(font_files_by_name()) == NAMES


def test_font_files_exist():
    for name in set(font_files_by_name().values()):
        assert (ROOT / 'fonts' / name).is_file(), name


def cmap(name, cache={}):
    if name not in cache:
        cache[name] = TTFont(ROOT / 'fonts' / name).getBestCmap()
    return cache[name]


def glyphs(text):
    return {c for c in TAGS.sub('', text or '') if not c.isspace()}


def skin_texts():
    """Every literal text that can end up in a label: labels, label params, variable values."""
    for path in layout_files():
        if path.name == 'Font.xml':
            continue
        for el in parse(path).iter():
            if el.tag in ('label', 'label2', 'value', 'altlabel'):
                yield path.name, el.text
            if el.tag == 'param' and el.get('name') in ('label', 'label2', 'kicker', 'path'):
                yield path.name, el.get('value')


def po_texts():
    for po in ROOT.glob('language/*/strings.po'):
        for m in re.finditer(r'^msgstr "(.*)"$', po.read_text(encoding='utf-8'), re.M):
            yield po.parent.name, m.group(1)


def test_label_glyph_coverage():
    """No label shows a missing-glyph box: every character is in every UI font."""
    chars = set()
    for _, text in list(skin_texts()) + list(po_texts()):
        chars |= glyphs(text)
    chars |= set('ÄÖÜäöüß')
    for name in UI_FONTS:
        missing = sorted(c for c in chars if ord(c) not in cmap(name))
        assert not missing, (name, missing)


def test_mono_labels_glyph_coverage():
    """Labels set in Share Tech Mono (numbers, times, clock) only use characters it has."""
    mono = {n for n, f in font_files_by_name().items() if f == MONO_FONT}
    for path in layout_files():
        for control in parse(path).iter('control'):
            if (control.findtext('font') or '').strip() in mono:
                for el in control.iter('label'):
                    missing = sorted(c for c in glyphs(el.text) if ord(c) not in cmap(MONO_FONT))
                    assert not missing, (path.name, el.text, missing)


def test_wide_font_is_tracked():
    wide, normal = TTFont(ROOT / 'fonts' / 'RetroUIWide-SemiBold.ttf'), TTFont(ROOT / 'fonts' / 'RetroUI-SemiBold.ttf')
    w_adv = wide['hmtx'][wide.getBestCmap()[ord('A')]][0]
    n_adv = normal['hmtx'][normal.getBestCmap()[ord('A')]][0]
    assert w_adv >= n_adv * 1.08
    for font in (wide, normal):
        family = font['name'].getDebugName(1)
        assert 'RetroUI' in family and 'Rajdhani' not in family, family


def test_layout_fonts_defined():
    defined = set(font_files_by_name())
    used = {(p.name, el.text.strip()) for p in layout_files() if p.name != 'Font.xml'
            for el in parse(p).iter('font') if el.text and not el.text.startswith('$')}
    used |= {(p.name, el.get('value')) for p in layout_files()
             for el in parse(p).iter('param') if el.get('name') == 'font' and not el.get('value', '$').startswith('$')}
    assert not [u for u in used if u[1] not in defined]


def test_fallback_fonts_for_addon_dialogs():
    """Add-on dialogs (jellyfin-kodi) use Estuary's font names; Kodi only falls back to font13."""
    assert {'font10', 'font12', 'font13', 'font14'} <= set(font_files_by_name())


def test_titles_in_other_scripts():
    """Greek, Cyrillic and Vietnamese titles render without boxes."""
    for name in UI_FONTS:
        missing = [c for c in 'ΩαβЖжЯяБДệờượ' if ord(c) not in cmap(name)]
        assert not missing, (name, missing)


def test_wide_composites_shift_once():
    """Tracking moves a composite glyph like its components: by half the tracking, not twice."""
    wide, normal = TTFont(ROOT / 'fonts' / 'RetroUIWide-SemiBold.ttf'), TTFont(ROOT / 'fonts' / 'RetroUI-SemiBold.ttf')
    composites = [n for n in normal.getGlyphOrder() if normal['glyf'][n].isComposite()]
    assert composites
    for name in composites:
        wg, ng = wide['glyf'][name], normal['glyf'][name]
        wg.recalcBounds(wide['glyf'])
        ng.recalcBounds(normal['glyf'])
        assert wg.xMin - ng.xMin == 50, name


def test_bullet_is_a_round_dot_on_the_middle_of_the_text():
    """• marks the current value of a list: round and big enough to see at a glance (Rajdhani's
    own is a narrow sliver, Noto Sans Symbols 2's is taken), centred between baseline and cap
    height."""
    for name in UI_FONTS:
        font = TTFont(ROOT / 'fonts' / name)
        glyph = font['glyf'][font.getBestCmap()[0x2022]]
        width, height = glyph.xMax - glyph.xMin, glyph.yMax - glyph.yMin
        assert width >= 300 and abs(width - height) <= 20, (name, width, height)
        cap = font['glyf'][font.getBestCmap()[ord('H')]].yMax
        assert abs((glyph.yMin + glyph.yMax) / 2 - cap / 2) <= 10, (name, glyph.yMin, glyph.yMax, cap)
