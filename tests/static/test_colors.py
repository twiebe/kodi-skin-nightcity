import re

import pytest

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


def _uses(word):
    """{file name: number of uses} of the colour WORD in the layouts, comments left out."""
    uses = {}
    for path in layout_files():
        text = re.sub(r'<!--.*?-->', '', path.read_text(encoding='utf-8'), flags=re.S)
        n = len(re.findall(r'\b{}\b'.format(word), text))
        if n:
            uses[path.name] = n
    return uses


def _include(path, name):
    return next(i for i in parse(ROOT / '1080i' / path).iter('include') if i.get('name') == name)


def _control(path, cid):
    return next(c for c in parse(ROOT / '1080i' / path).iter('control') if c.get('id') == cid)


# the headings Kodi sets in its own dialogs (label ids), pink
DIALOG_HEADINGS = [('DialogVideoManager.xml', '2'), ('DialogSlider.xml', '10'), ('DialogExtendedProgressBar.xml', '30'),
                   ('DialogKeyboard.xml', '311'), ('DialogSubtitles.xml', '100')]


def test_pink_is_order_and_identity():
    """Pink (accent2) names or numbers something and never changes with input (DESIGN.md "What
    the colours say"): the kicker over a title, dialog headings, the settings rail numbers, the
    system tile numbers, the add-on news heading, the heading of a notification."""
    assert _uses('accent2') == {'Includes_Base.xml': 1, 'Includes_Settings.xml': 1, 'Includes_Home.xml': 1,
                                'Variables.xml': 1, 'DialogVideoManager.xml': 1, 'DialogSlider.xml': 1,
                                'DialogExtendedProgressBar.xml': 1, 'DialogKeyboard.xml': 1,
                                'DialogSubtitles.xml': 1, 'DialogAddonInfo.xml': 1, 'DialogNotification.xml': 1}
    assert 'accent2' not in (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    assert _include('Includes_Base.xml', 'Kicker').find('.//textcolor').text == 'accent2'
    rail = _include('Includes_Settings.xml', 'SettingsRailHeading').find('.//label').text
    assert rail.startswith('[COLOR accent2]$PARAM[num][/COLOR]')
    tile = {p.get('name'): p.get('default') for p in _include('Includes_Home.xml', 'SystemTile').findall('param')}
    assert tile['numcolor'] == 'accent2'
    for path, cid in DIALOG_HEADINGS:
        assert _control(path, cid).findtext('textcolor') == 'accent2', path
    assert '[COLOR accent2]news[/COLOR]' in (ROOT / '1080i' / 'DialogAddonInfo.xml').read_text(encoding='utf-8')


def _variable(name):
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable') if v.get('name') == name)
    return [(v.get('condition') or '', v.text) for v in var.findall('value')]


def test_system_tile_numbers_are_pink():
    assert _variable('SystemTileNumColor') == [('Control.HasFocus(9601)', 'focus_text'), ('', 'accent2')]


def test_yellow_only_warns():
    """Yellow (warn) only on a notification that warns: Kodi gives a warning or an error toast
    without a picture of its own DefaultIconWarning.png or DefaultIconError.png (id 400), the
    others are pink. A colour variable is evaluated outside the dialog and cannot see its icon,
    so a yellow copy of the heading shows instead. accent3 is not used any more."""
    assert _uses('accent3') == {}
    assert _uses('warn') == {'DialogNotification.xml': 1}
    warns = 'String.IsEqual(Control.GetLabel(400),DefaultIconWarning.png) | String.IsEqual(Control.GetLabel(400),DefaultIconError.png)'
    expressions = {e.get('name'): e.text for e in parse(ROOT / '1080i' / 'Includes_Dialogs.xml').iter('expression')}
    assert expressions['NotificationWarns'] == warns
    toast = parse(ROOT / '1080i' / 'DialogNotification.xml')
    headings = [c for c in toast.iter('control') if c.get('type') == 'label' and c.findtext('top') == '18']
    assert [(c.get('id'), c.findtext('textcolor'), c.findtext('label'), c.findtext('visible')) for c in headings] == [
        ('401', 'accent2', None, '!$EXP[NotificationWarns]'),
        (None, 'warn', '$INFO[Control.GetLabel(401)]', '$EXP[NotificationWarns]')]


def test_pointer_is_cyan():
    """The mouse pointer is a cursor: cyan in every state."""
    pointer = parse(ROOT / '1080i' / 'Pointer.xml')
    assert {c.find('texture').get('colordiffuse') for c in pointer.iter('control')} == {'accent'}


def test_stars_and_keys_are_grey():
    for path in ('Includes_Info.xml', 'MusicVisualisation.xml', 'DialogMusicInfo.xml'):
        assert '[COLOR text_dim]★[/COLOR]' in (ROOT / '1080i' / path).read_text(encoding='utf-8'), path
    assert 'keycolor' not in (ROOT / '1080i' / 'DialogPlayerProcessInfo.xml').read_text(encoding='utf-8')


STATE_NOT_CYAN = [
    # (file, xpath-ish check) of what shows state, which is dark blue, not the cursor's cyan
    ('Variables.xml', '[COLOR accent]●'), ('Variables.xml', '[COLOR accent]◄◄'),
    ('Variables.xml', '[COLOR accent]▶▶'), ('Variables.xml', '[COLOR accent]❚❚'),
    ('Includes_Info.xml', '[COLOR accent]$VAR[EpisodeCardNum]'),
]


@pytest.mark.parametrize('path, text', STATE_NOT_CYAN)
def test_state_is_not_cyan(path, text):
    assert text not in (ROOT / '1080i' / path).read_text(encoding='utf-8')


def test_key_hints_are_state():
    """The keys named in a hint line (OK open, Back close) are hints: dark blue, not cyan."""
    text = (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    assert '[COLOR accent]' not in text
    assert '[COLOR state_text]OK[/COLOR] open   [COLOR state_text]Back[/COLOR] close' in text


def test_on_marks_and_shown_page_are_state():
    """A check box that is on, the shown page of the top menu and the context menu's top line:
    state, not the cursor. Cyan stays on the quick menu's icon (the latent cursor: Up and Back
    lead there) and on the search field's outline (the primary input, as the Play pill)."""
    cyan = [(path.name, el.tag, el.text) for path in layout_files() for el in parse(path).iter()
            if el.tag in ('textureradioonnofocus', 'alttexturenofocus', 'texturenofocus')
            and el.get('colordiffuse') == 'accent']
    assert cyan == [('Includes_Home.xml', 'textureradioonnofocus', 'ui/qm_menu.png'),
                    ('Includes_Home.xml', 'texturenofocus', 'ui/cut_btn.png')]
    menu = parse(ROOT / '1080i' / 'DialogContextMenu.xml')
    assert 'accent' not in {t.get('colordiffuse') for t in menu.iter('texture')}
def counters(path):
    return [c for c in parse(path).iter('control') if c.get('type') == 'label'
            and '.CurrentItem]/$INFO[' in (c.findtext('label') or '')]


def test_counters_in_state_text():
    """"3/12" over a row or the episodes of a season: state, readable."""
    found = [c for path in layout_files() for c in counters(path)]
    assert len(found) >= 6
    assert {c.findtext('textcolor') for c in found} == {'state_text'}


def test_tags_are_white():
    """Tags are content: the spotlight's resolution and audio tags as the others, not cyan."""
    tags = [c for c in parse(ROOT / '1080i' / 'Includes_Home.xml').iter('include') if c.get('content') == 'Tag']
    assert tags and not [t for t in tags if any(p.get('name') == 'color' for p in t.findall('param'))]


def test_track_numbers_are_state():
    """Numbers before the tracks of the music queue: dark blue, the cursor's in cyan."""
    params = {p.get('name'): p.get('default') for p in _include('Includes_Music.xml', 'MusicQueueRow').findall('param')}
    assert params['number'] == 'state_text'


def test_notification_icons_are_in_the_skin():
    """Kodi asks for DefaultIconInfo/Warning/Error.png by bare name; without them the icon 400
    stays empty and the notification cannot tell a warning (test_yellow_only_warns). Not tinted:
    a toast with a picture of its own (an add-on icon) shows it in 400 too."""
    from PIL import Image
    for kind in ('Info', 'Warning', 'Error'):
        assert Image.open(ROOT / 'media' / 'DefaultIcon{}.png'.format(kind)).size == (80, 80), kind
    assert _control('DialogNotification.xml', '400').find('colordiffuse') is None
