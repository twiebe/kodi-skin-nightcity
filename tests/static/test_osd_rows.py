"""The track panels of the OSD (subtitles 651, audio 652, video 653) show while their button or
the panel has the focus. The chapter and cast rows below the controls open as dialogs over the
OSD, which keeps its focus on the button: the panels hide with the controls then."""
import pytest

from navigation import load

ROWS_HIDDEN = ('!Window.IsActive(videobookmarks)', '!Window.IsActive(1141)')


def panel_group(panel):
    """The outer group of the panel (TrackPanel, VideoPanel): the one holding the panel's list."""
    osd = load('VideoOSD.xml')
    return next(c for c in osd.find('controls').findall('control')
                if any(k.get('id') == str(panel) for k in c.iter('control')))


@pytest.mark.parametrize('panel', [651, 652, 653])
def test_panel_hides_while_a_row_is_open(panel):
    visible = ' + '.join(v.text for v in panel_group(panel).findall('visible'))
    for part in ROWS_HIDDEN:
        assert part in visible, (panel, visible)
