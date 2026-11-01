"""A focused button or row glows like a focused card: a soft halo in its fill colour around the
fill (DESIGN.md, What the colours say).

Kodi draws a button's textures only inside the button, and a grouplist or a list clips what it
holds to its own rect. So a control that glows is GLOW px larger on each side and draws a padded
texture: the fill (or the outline when it has no focus) inset by GLOW, the halo in the margin.
A grouplist of such controls is GLOW px larger on each side too and puts them 2 * GLOW px
closer, so the visible pills and rows stay where they were."""
import xml.etree.ElementTree as ET

import pytest
from PIL import Image

from conftest import ROOT, layout_files, parse

GLOW = 10
UI = ROOT / 'media' / 'ui'
FOCUS = {'focus', 'accent', '$VAR[HomePagesFocusColor]'}
# plain texture: its padded twin and the plain one's border
PADDED = {'ui/cut_btn_fill.png': ('ui/cut_btn_glow.png', 12),
          'ui/cut_fill.png': ('ui/cut_fill_glow.png', 16),
          'ui/cut_btn.png': ('ui/cut_btn_pad.png', 12),
          'ui/cut.png': ('ui/cut_pad.png', 16)}
# a fill that does not glow (the shown settings category) in a padded control
PLAIN_PAD = 'ui/cut_btn_fill_pad.png'
PADDED_NAMES = {padded for padded, _ in PADDED.values()} | {PLAIN_PAD}
TEXTURE_TAGS = ('texture', 'texturefocus', 'texturenofocus', 'alttexturefocus', 'alttexturenofocus')

# Grouplists of glowing entries as they were before the glow: (left, top, width, height,
# itemgap). Now each is GLOW px further out on every side with the gap 2 * GLOW smaller.
# '#n' is the n-th grouplist of a file without id.
BEFORE = {
    ('AddonBrowser.xml', '9000'): ('1440', '100', '400', '600', '0'),
    ('Custom_1110_Library.xml', '5100'): ('1480', '108', '380', '200', '16'),
    ('DialogAddonInfo.xml', '9000'): ('40', '760', '1520', '54', '16'),
    ('DialogAddonSettings.xml', '3'): ('40', '84', '400', '720', '0'),
    ('DialogAddonSettings.xml', '5'): ('480', '84', '1080', '720', '0'),
    ('DialogAddonSettings.xml', '9002'): ('40', '0', '1320', '54', '24'),
    ('DialogConfirm.xml', '9000'): ('40', '336', '920', '54', '24'),
    ('DialogContextMenu.xml', '996'): ('20', '24', '640', 'auto', '0'),
    ('DialogKeyboard.xml', '9001'): ('40', '150', '1000', '54', '8'),
    ('DialogKeyboard.xml', '9002'): ('40', '210', '1000', '54', '8'),
    ('DialogKeyboard.xml', '9003'): ('40', '270', '1000', '54', '8'),
    ('DialogKeyboard.xml', '9004'): ('40', '330', '1000', '54', '8'),
    ('DialogKeyboard.xml', '9005'): ('40', '390', '1000', '54', '8'),
    ('DialogKeyboard.xml', '9006'): ('40', '460', '1000', '54', '24'),
    ('DialogMediaSource.xml', '9000'): ('940', '84', '320', '400', '12'),
    ('DialogMediaSource.xml', '9001'): ('40', '676', '1220', '54', '24'),
    ('DialogMusicInfo.xml', '9000'): ('384', '490', '1000', '54', '16'),
    ('DialogNumeric.xml', '9010'): ('40', '160', '400', '56', '20'),
    ('DialogNumeric.xml', '9011'): ('40', '228', '400', '56', '20'),
    ('DialogNumeric.xml', '9012'): ('40', '296', '400', '56', '20'),
    ('DialogNumeric.xml', '9013'): ('40', '364', '400', '56', '20'),
    ('DialogNumeric.xml', '9014'): ('480', '160', '180', '300', '20'),
    ('DialogSelect.xml', '9001'): ('40', '740', '1020', '54', '24'),
    ('DialogSettings.xml', '5'): ('40', '84', '1320', '640', '0'),
    ('DialogSettings.xml', '9002'): ('40', '0', '1320', '54', '24'),
    ('DialogSubtitles.xml', '9003'): ('40', '712', '420', '52', None),
    ('DialogVideoInfo.xml', '9000'): ('384', '490', '1000', '54', '16'),
    ('DialogVideoManager.xml', '9000'): ('1040', '84', '320', '600', '12'),
    ('EventLog.xml', '9000'): ('1440', '100', '400', '600', '0'),
    ('FileBrowser.xml', '9000'): ('40', '820', '1320', '54', '24'),
    ('Includes_Home.xml', '#3'): ('384', '490', '1400', '54', '16'),
    ('Includes_Home.xml', '#4'): ('384', '490', '1400', '54', '16'),
    ('Includes_Home.xml', '9100'): ('-18', '22', '1500', '44', '0'),
    ('Includes_Music.xml', '9850'): ('384', '490', '1400', '54', '16'),
    ('Includes_Player.xml', '#2'): ('12', '56', '576', '364', '0'),
    ('Includes_Settings.xml', '$PARAM[id]'): ('560', '100', '1240', '$PARAM[height]', '0'),
    ('MusicOSD.xml', '600'): ('64', '590', '1000', '54', '12'),
    ('MusicOSD.xml', '620'): ('1056', '590', '800', '54', '12'),
    ('MyMusicNav.xml', '9060'): ('1440', '880', '400', '176', '0'),
    ('MyVideoNav.xml', '9060'): ('1440', '880', '400', '176', '0'),
    ('Settings.xml', '9200'): ('64', '90', '520', '900', '0'),
    ('SettingsCategory.xml', '3'): ('120', '100', '400', '840', '0'),
    ('SettingsCategory.xml', '5'): ('560', '100', '1240', '800', '0'),
    ('SettingsCategory.xml', '9003'): ('120', '960', '400', '52', None),
    ('SettingsProfile.xml', '9000'): ('1200', '100', '600', '200', '0'),
    ('SettingsSystemInfo.xml', '9000'): ('120', '100', '400', '700', '0'),
    ('SkinSettings.xml', '9000'): ('120', '100', '400', '840', '0'),
    ('SmartPlaylistEditor.xml', '9001'): ('40', '84', '860', '420', '0'),
    ('SmartPlaylistEditor.xml', '9002'): ('940', '84', '420', '760', '12'),
    ('SmartPlaylistRule.xml', '9001'): ('40', '84', '920', '200', '0'),
    ('SmartPlaylistRule.xml', '9000'): ('40', '360', '920', '54', '24'),
    ('VideoOSD.xml', '600'): ('64', '952', '760', '54', '12'),
    ('VideoOSD.xml', '620'): ('856', '952', '1000', '54', '12'),
    ('VideoOSDBookmarks.xml', '9000'): ('856', '486', '1000', '54', '12'),
}
# The top line of Home only grows up and down: its entries keep their widths and gap (a glow
# image in the icon's group, the pill of what plays moved by its own left, HomeTop)
TALLER = {('Includes_Home.xml', '9190'): ('64', '22', '1792', '44', '16')}


def grouplists():
    """{(file, id or '#n'): grouplist}"""
    found = {}
    for path in layout_files():
        n = 0
        for el in parse(path).iter('control'):
            if el.get('type') == 'grouplist':
                n += 1
                found[(path.name, el.get('id') or '#{}'.format(n))] = el
    return found


def definitions():
    defs = {}
    for path in layout_files():
        for el in parse(path).iter('include'):
            if el.get('name'):
                defs[el.get('name')] = el
    return defs


def holds_padded(el, defs, depth=0):
    """Whether el draws a padded texture, through its includes; not into lists and grouplists,
    which clip their own content."""
    if depth > 12:
        return False
    for child in el:
        if child.tag == 'control' and child.get('type') in ('list', 'panel', 'grouplist', 'fixedlist', 'wraplist'):
            continue
        if child.tag in TEXTURE_TAGS and (child.text or '').strip() in PADDED_NAMES:
            return True
        if child.tag == 'include' and not child.get('name'):
            name = child.get('content') or (child.text or '').strip()
            if name in defs and holds_padded(defs[name], defs, depth + 1):
                return True
        if holds_padded(child, defs, depth + 1):
            return True
    return False


def geometry(el):
    return tuple(el.findtext(k) for k in ('left', 'top', 'width', 'height', 'itemgap'))


def grown(before):
    def out(value, by):
        return value if value is None or not value.lstrip('-').isdigit() else str(int(value) + by)
    left, top, width, height, gap = before
    return (out(left, -GLOW), out(top, -GLOW), out(width, 2 * GLOW), out(height, 2 * GLOW), out(gap, -2 * GLOW))


def textures(path):
    """(tag, texture, border) of every texture in a layout file, include params with a texture
    and a colour as well."""
    root = parse(path)
    for el in root.iter():
        if el.tag in TEXTURE_TAGS:
            yield el.tag, (el.text or '').strip(), el.get('border'), el.get('colordiffuse')
    for inc in root.iter('include'):
        args = {p.get('name'): p.get('value') for p in inc.findall('param')}
        if 'texture' in args and 'color' in args:
            yield 'param', args['texture'], None, args['color']


def test_focus_fills_glow():
    """No fill in a focus colour without its glow: the focused button, row, tile and pill all
    take the padded fill."""
    plain = [(path.name, tag, texture) for path in layout_files() for tag, texture, _, color in textures(path)
             if texture in ('ui/cut_btn_fill.png', 'ui/cut_fill.png') and color in FOCUS]
    assert plain == []
    glowing = [path.name for path in layout_files() for _, texture, _, color in textures(path)
               if texture in ('ui/cut_btn_glow.png', 'ui/cut_fill_glow.png') and color in FOCUS]
    assert len(glowing) >= 30


def test_padded_textures_have_a_wider_border():
    """The margin is part of the texture's border, so the corner keeps its size."""
    border = {padded: str(plain + GLOW) for padded, plain in PADDED.values()}
    border[PLAIN_PAD] = str(12 + GLOW)
    bad = [(path.name, texture, b) for path in layout_files() for tag, texture, b, _ in textures(path)
           if tag != 'param' and texture in border and b != border[texture]]
    assert bad == []
    include = definitions()['MorePill']
    assert include.find('.//texture').get('border') == str(12 + GLOW)


def test_padded_controls_have_no_plain_texture():
    """A control that grows by the margin draws its outline and alternative textures with the
    same margin: a plain outline would stand GLOW px off the fill."""
    bad = []
    for path in layout_files():
        for control in parse(path).iter('control'):
            names = {(el.text or '').strip() for el in control if el.tag in TEXTURE_TAGS}
            if names & PADDED_NAMES and names & set(PADDED):
                bad.append((path.name, control.get('id'), sorted(names)))
    assert bad == []


@pytest.mark.parametrize('plain', sorted(PADDED))
def test_padded_textures_are_the_plain_ones_inset(plain):
    padded, _ = PADDED[plain]
    small = Image.open(ROOT / 'media' / plain).convert('RGBA')
    big = Image.open(ROOT / 'media' / padded).convert('RGBA')
    assert big.size == (small.width + 2 * GLOW, small.height + 2 * GLOW)
    inner = big.crop((GLOW, GLOW, GLOW + small.width, GLOW + small.height)).getchannel('A')
    alpha = small.getchannel('A')
    # the shape itself: where the plain texture is opaque, the padded one is too
    assert all(b == 255 for a, b in zip(alpha.tobytes(), inner.tobytes()) if a == 255)
    edge = big.getchannel('A')
    mid = big.height // 2
    if 'fill' in plain:
        # a halo next to the fill, fading out to the edge of the margin
        assert 40 <= edge.getpixel((GLOW - 1, mid)) <= 128
        assert edge.getpixel((0, mid)) < 16
    else:
        assert edge.getpixel((GLOW - 1, mid)) == 0


def test_grouplists_of_glowing_entries_keep_them_in_place():
    lists, defs = grouplists(), definitions()
    for key, before in BEFORE.items():
        assert geometry(lists[key]) == grown(before), key
    for key, before in TALLER.items():
        left, top, width, height, gap = before
        assert geometry(lists[key]) == (left, str(int(top) - GLOW), width, str(int(height) + 2 * GLOW), gap)
    # every grouplist of padded entries is one of them
    holding = {key for key, el in lists.items() if holds_padded(el, defs)}
    assert holding - set(BEFORE) - set(TALLER) == set()


def control_of(name):
    return definitions()[name].find('.//control')


def test_pills_grow_by_the_margin():
    """Visible pill sizes as before (54 and 44 px high, text inset 24 and 16), now with the
    margin around them."""
    pill = control_of('PillButton')
    assert pill.findtext('height') == str(54 + 2 * GLOW)
    params = {p.get('name'): p.get('default') for p in definitions()['PillButton'].iter('param')}
    assert params['textoffsetx'] == str(24 + GLOW)
    menu = control_of('MenuButton')
    assert (menu.findtext('height'), menu.findtext('textoffsetx')) == (str(44 + 2 * GLOW), str(16 + GLOW))
    row = control_of('ListButton')
    assert (row.findtext('height'), row.findtext('textoffsetx')) == (str(52 + 2 * GLOW), str(20 + GLOW))
    look = definitions()['SpotlightPillLook'].find('definition')
    assert (look.findtext('height'), look.findtext('textoffsetx')) == (str(54 + 2 * GLOW), str(24 + GLOW))


def test_more_pill_list_grows_by_the_margin():
    """The … pill of the info page is a one-item list in the button row: as large as a padded
    pill, so it sits in the row like the others."""
    more = next(c for c in parse(ROOT / '1080i' / 'DialogVideoInfo.xml').iter('control') if c.get('id') == '9003')
    assert (more.findtext('width'), more.findtext('height')) == (str(96 + 2 * GLOW), str(54 + 2 * GLOW))
    for layout in more.findall('itemlayout') + more.findall('focusedlayout'):
        assert (layout.get('width'), layout.get('height')) == (str(96 + 2 * GLOW), str(54 + 2 * GLOW))
