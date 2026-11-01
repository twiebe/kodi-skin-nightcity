"""Video calibration (SettingsScreenCalibration.xml): Kodi drives the window by control id
(GUIWindowSettingsScreenCalibration.cpp); without the file the settings entry opened nothing."""
from PIL import Image

from conftest import ROOT, parse

WINDOW = ROOT / '1080i' / 'SettingsScreenCalibration.xml'
# id: (type, texture) Kodi moves 8-11 itself and goes from one to the next with OK
CONTROLS = {'8': ('mover', 'ui/cal_tl.png'), '9': ('mover', 'ui/cal_br.png'), '10': ('mover', 'ui/cal_sub.png'),
            '11': ('resize', 'ui/cal_ratio.png'), '12': ('mover', 'ui/cal_reset.png')}


def _controls():
    return {c.get('id'): c for c in parse(WINDOW).iter('control') if c.get('id')}


def test_window_has_the_controls_kodi_drives():
    root = parse(WINDOW)
    assert root.findtext('defaultcontrol') == '8'
    c = _controls()
    for cid, (kind, texture) in CONTROLS.items():
        assert c[cid].get('type') == kind, cid
        assert c[cid].findtext('texturefocus') == texture and c[cid].findtext('texturenofocus') == texture, cid
        assert c[cid].find('texturefocus').get('colordiffuse') == 'focus', cid
    for cid in ('2', '3', '4'):  # resolution, help, value
        assert c[cid].get('type') == 'label', cid
    # the movers move in the directions Kodi reads (8, 9 all four, 10 up and down, 11 left and right)
    dirs = {cid: sorted(e.get('type') for e in c[cid].iter('eventconfig')) for cid in ('8', '9', '10', '11')}
    assert dirs == {'8': ['down', 'left', 'right', 'up'], '9': ['down', 'left', 'right', 'up'],
                    '10': ['down', 'up'], '11': ['left', 'right']}
    assert '$LOCALIZE[214]' in WINDOW.read_text(encoding='utf-8')  # Kodi's "Video calibration"


def test_calibration_textures_come_from_the_texture_tool():
    tool = (ROOT / 'tools' / 'make_textures.py').read_text(encoding='utf-8')
    for _, texture in CONTROLS.values():
        assert "'{}'".format(texture.split('/')[1]) in tool, texture
        assert (ROOT / 'media' / texture).exists(), texture


def test_pixel_ratio_target_is_a_square():
    """The ratio is right when the target looks square, as Kodi's help says: as wide as tall."""
    alpha = Image.open(ROOT / 'media' / 'ui' / 'cal_ratio.png').getchannel('A')
    assert alpha.width == alpha.height
    left, top, right, bottom = alpha.getbbox()
    assert right - left == bottom - top


def test_subtitle_bar_keeps_kodis_margins():
    """Kodi takes 40 px clear above and below the bar of the subtitle mover (Estuary's note)."""
    alpha = Image.open(ROOT / 'media' / 'ui' / 'cal_sub.png').getchannel('A')
    seen = alpha.point(lambda a: 255 if a > 32 else 0)  # the faint fringe of the scaling aside
    top, bottom = seen.getbbox()[1], seen.getbbox()[3]
    assert top >= 40 and alpha.height - bottom >= 40


def test_texts_stay_above_the_pixel_ratio_target():
    """Kodi centres the target (500 px from 290): title, resolution and help end above it, the
    value starts below it."""
    c = _controls()
    assert int(c['3'].findtext('top')) + int(c['3'].findtext('height')) <= 280
    # and the value below it (Kodi draws it to about 810)
    assert int(c['4'].findtext('top')) >= 820
