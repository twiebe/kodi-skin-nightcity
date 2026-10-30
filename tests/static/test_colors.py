import re

from conftest import ROOT, layout_files, parse

NAMES = {'bg', 'bg_alt', 'petrol', 'surface', 'surface_alt', 'border', 'border_dim', 'text', 'text_dim',
         'text_mute', 'accent', 'accent2', 'accent3', 'focus', 'focus_text', 'glow', 'glitch_a', 'glitch_b',
         'fanart', 'ok', 'warn', 'error', 'scrim', 'state', 'state_text', 'state_fade', 'state_faint'}
PALETTES = ['defaults.xml', 'tokyonight.xml', 'catppuccin.xml']
HEX = re.compile(r'^[0-9A-Fa-f]{8}$')
COLOR_TAGS = ('textcolor', 'focusedcolor', 'disabledcolor', 'shadowcolor', 'selectedcolor',
              'colordiffuse', 'color', 'invalidcolor', 'disabledcolor')


def palette(name):
    return {c.get('name'): (c.text or '').strip() for c in parse(ROOT / 'colors' / name).iter('color')}


def layout_color_values():
    for path in layout_files():
        for el in parse(path).iter():
            for tag in COLOR_TAGS:
                if el.tag == tag and el.text:
                    yield path.name, el.text.strip()
                if tag in el.attrib:
                    yield path.name, el.attrib[tag].strip()


def test_palettes_define_same_names():
    for name in PALETTES:
        assert set(palette(name)) == NAMES, name


def test_color_values_format():
    for name in PALETTES:
        for color, value in palette(name).items():
            assert HEX.match(value), (name, color, value)


def test_no_hex_in_layouts():
    bad = [(f, v) for f, v in layout_color_values() if HEX.match(v)]
    assert not bad


def test_layout_colors_defined():
    defined = set(palette('defaults.xml'))
    used = {(f, v) for f, v in layout_color_values() if not v.startswith('$')}
    assert not [(f, v) for f, v in used if v not in defined]


def test_netrunner_palette():
    p = palette('defaults.xml')
    expected = {'bg': 'FF05080C', 'petrol': 'FF0C2A33', 'accent': 'FF5FD8E8', 'accent2': 'FFFF2A6D',
                'text': 'FFD6F6FA', 'text_dim': 'FFA9C7CC', 'text_mute': 'FF7FA3A8'}
    assert {k: p[k].upper() for k in expected} == expected
    assert p['focus'] == p['accent']


def luminance(argb):
    def channel(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(argb[i:i + 2], 16) for i in (2, 4, 6))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_text_contrast():
    """Readable from the sofa: text and dim text 4.5:1, muted text 3:1, focused text on focus 4.5:1."""
    for name in PALETTES:
        p = palette(name)
        assert contrast(p['text'], p['bg']) >= 4.5, name
        assert contrast(p['text_dim'], p['bg']) >= 4.5, name
        assert contrast(p['text_mute'], p['bg']) >= 3.0, name
        assert contrast(p['focus_text'], p['focus']) >= 4.5, name


def test_no_scanlines():
    for path in list((ROOT / '1080i').glob('*.xml')) + list(ROOT.glob('language/*/strings.po')):
        if True:
            text = path.read_text(encoding='utf-8')
            assert 'FX_Scanlines' not in text and 'scanline' not in text.lower(), path
    assert not (ROOT / 'media' / 'fx' / 'scanline.png').exists()


def over(top, base):
    """Colour of `top` (with its alpha) drawn over the opaque `base`, as FFRRGGBB."""
    a = int(top[:2], 16) / 255
    mix = [round(int(top[i:i + 2], 16) * a + int(base[i:i + 2], 16) * (1 - a)) for i in (2, 4, 6)]
    return 'FF' + ''.join('{:02X}'.format(c) for c in mix)


def test_text_contrast_over_fanart():
    """Worst case behind text: the petrol glow at full strength and a white fanart pixel tinted
    by `fanart`. Dim text keeps 4.5:1, muted text 3:1."""
    for name in PALETTES:
        p = palette(name)
        back = over(p['fanart'], over(p['petrol'], p['bg']))
        assert contrast(p['text_dim'], back) >= 4.5, (name, back)
        assert contrast(p['text_mute'], back) >= 3.0, (name, back)


def test_glitch_copies_at_original_strength():
    """The pink and cyan copies behind glitch titles: alpha 88 (about half). AA and 99 were
    both too thick."""
    for path in (ROOT / 'colors').glob('*.xml'):
        colors = {c.get('name'): c.text for c in parse(path).iter('color')}
        for name in ('glitch_a', 'glitch_b'):
            assert colors[name][:2] == '88', (path.name, name)


def test_state_is_border_dim_made_opaque():
    """Dark blue for state (the shown tab, the current value, counters): border_dim over the page,
    opaque, so a thin line looks the same on any background."""
    for name in PALETTES:
        p = palette(name)
        assert p['state'] == over(p['border_dim'], p['bg']), name


def test_state_text_is_a_readable_state():
    """Text in the state colour: the same hue lighter, as state itself is too dark to read. It is
    border over the page at the least strength from 60 % on that reads at 4.5:1."""
    for name in PALETTES:
        p = palette(name)
        mixes = [over('{:02X}'.format(a) + p['border'][2:], p['bg']) for a in range(0x99, 0x100)]
        assert p['state_text'] == next(c for c in mixes if contrast(c, p['bg']) >= 4.5), name
        assert contrast(p['state'], p['bg']) < 3.0, name
        assert contrast(p['state_text'], p['bg']) >= 4.5, name


def test_pink_only_for_titles():
    """Pink (accent2) is for titles only: the kicker line over the title of a movie or episode
    (and of every other page with one). State and decoration take the dark blue."""
    uses = []
    for path in layout_files():
        text = re.sub(r'<!--.*?-->', '', path.read_text(encoding='utf-8'), flags=re.S)
        uses += [path.name for _ in re.finditer('accent2', text)]
    assert uses == ['Includes_Base.xml']
    assert 'accent2' not in (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    kicker = next(i for i in parse(ROOT / '1080i' / 'Includes_Base.xml').iter('include') if i.get('name') == 'Kicker')
    assert kicker.find('.//textcolor').text == 'accent2'


def counters(path):
    return [c for c in parse(path).iter('control') if c.get('type') == 'label'
            and '.CurrentItem]/$INFO[' in (c.findtext('label') or '')]


def test_counters_in_state_text():
    """"3/12" over a row or the episodes of a season: state, readable."""
    found = [c for path in layout_files() for c in counters(path)]
    assert len(found) >= 6
    assert {c.findtext('textcolor') for c in found} == {'state_text'}
