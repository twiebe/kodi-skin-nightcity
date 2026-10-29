"""Player level hints: each level of the player shows, centred on its bottom edge, the key that
leads one level down and what it opens, and on its top edge where Up goes back to; a hint hides
when its level does not exist (no cast row for a clip outside the library).

Levels: the seek bar over the bare video (OK opens the OSD; Up and Down skip chapters there),
the OSD bar (Down: the chapter row), the chapter row (Down: the cast row, Up: the bar), the cast
row (Up: the chapter row)."""
import xml.etree.ElementTree as ET

from conftest import ROOT, parse
from navigation import load

BOTTOM, TOP = '1030', '140'
CAST = 'VideoPlayer.Content(movies) | VideoPlayer.Content(episodes)'
CHAPTERS = '$VAR[PlayerChaptersLevel]'
MENU = '$LOCALIZE[31232]'


def _controls(name):
    return {c.get('id'): c for c in load(name).iter('control') if c.get('id')}


def _hint(name, cid):
    """(key, label, top, visible) of the hint `cid` in window `name`."""
    group = _controls(name)[cid]
    line = group.findall('control')[-1]
    assert line.get('type') == 'label' and line.findtext('align') == 'center', cid
    text = line.findtext('label')
    assert text.startswith('[UPPERCASE]') and text.endswith('[/UPPERCASE]'), text
    key, label = text[len('[UPPERCASE]'):-len('[/UPPERCASE]')].split(' ', 1)
    return key, label, group.findtext('top'), group.findtext('visible')


def _actions(control, tag):
    return [(a.get('condition') or '', a.text) for a in control.findall(tag)]


def test_hint_look():
    """Quiet like the key hint under the episodes of an info page: one line of muted small caps,
    the key in front, no chip; a shadow keeps it readable over bright video. Centred across the
    screen, it fades in and out."""
    include = next(i for i in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('include')
                   if i.get('name') == 'LevelHint')
    group = include.find('definition/control')
    assert group.get('type') == 'group'
    assert [(a.get('effect'), a.text) for a in group.findall('animation')] == [('fade', 'VisibleChange')]
    (label,) = group.findall('control')
    assert label.get('type') == 'label'
    assert (label.findtext('width'), label.findtext('align')) == ('1920', 'center')
    assert label.findtext('font') == 'font_caps_small'
    assert label.findtext('textcolor') == 'text_mute'
    assert label.findtext('shadowcolor') == 'bg'
    assert label.findtext('label') == '[UPPERCASE]$PARAM[key] $PARAM[label][/UPPERCASE]'
    assert not list(include.iter('texture')) and 'cut_btn' not in ET.tostring(include, encoding='unicode')


def test_chapters_level_name():
    """The row below the bar lists the chapters, or only the bookmark buttons without chapters."""
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable')
               if v.get('name') == 'PlayerChaptersLevel')
    assert [(v.get('condition'), v.text) for v in var.iter('value')] == [
        ('Integer.IsGreater(Player.ChapterCount,0)', '$LOCALIZE[31140]'), (None, '$LOCALIZE[31056]')]


def test_seek_bar_hint():
    """Over the bare video Up and Down skip chapters (Kodi's keymap), OK opens the OSD: the seek
    bar shows that key. The OSD and the stats dialog bring their own keys."""
    key, label, top, visible = _hint('DialogSeekBar.xml', '490')
    assert (key, label, top) == ('⏎', MENU, BOTTOM)
    assert visible == '!Window.IsVisible(videoosd) + !Window.IsActive(playerprocessinfo)'


def test_osd_hint():
    """The bar: Down opens the chapter row. Hidden while a panel above a button has the focus
    (Down goes back to the button there) and while a lower level is up."""
    key, label, top, visible = _hint('VideoOSD.xml', '690')
    assert (key, label, top) == ('↓', CHAPTERS, BOTTOM)
    assert visible == ('!Window.IsActive(videobookmarks) + !Window.IsActive(1141)'
                       ' + !Control.HasFocus(651) + !Control.HasFocus(652) + !Control.HasFocus(653)')
    controls = _controls('VideoOSD.xml')
    for row in ('600', '620'):
        assert controls[row].findtext('ondown') == 'ActivateWindow(videobookmarks)', row


def test_chapter_row_hints():
    """The chapter row: Down opens the cast row (library movies and episodes only), Up goes back
    to the bar."""
    controls = _controls('VideoOSDBookmarks.xml')
    key, label, top, visible = _hint('VideoOSDBookmarks.xml', '91')
    assert (key, label, top) == ('↓', '$LOCALIZE[31124]', BOTTOM)
    assert visible == '!Window.IsActive(1141) + [{}]'.format(CAST)
    assert (CAST, 'ActivateWindow(1141)') in _actions(controls['11'], 'ondown')
    key, label, top, visible = _hint('VideoOSDBookmarks.xml', '92')
    assert (key, label, top) == ('↑', MENU, TOP)
    assert visible == '!Window.IsActive(1141)'
    assert _actions(controls['9000'], 'onup') == [('', 'Dialog.Close(videobookmarks)')]


def test_cast_row_hint():
    """The cast row: Up from the tabs goes back to the chapter row; nothing lies below."""
    key, label, top, visible = _hint('Custom_1141_OSDCast.xml', '6590')
    assert (key, label, top, visible) == ('↑', CHAPTERS, TOP, 'true')
    controls = _controls('Custom_1141_OSDCast.xml')
    assert controls['6520'].findtext('onup') == 'Dialog.Close(1141)'
    assert controls['6501'].findtext('ondown') == 'noop'
