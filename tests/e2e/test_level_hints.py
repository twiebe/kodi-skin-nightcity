"""Player level hints: the seek bar shows that OK opens the OSD, the bar that Down opens the
chapter row, the chapter row Down to the cast row (library titles only) and Up back to the bar,
the cast row Up back to the chapter row. Keys go through Kodi's remote keymap (kodi-send), as on
a real remote."""
import os
import subprocess
import time
import xml.etree.ElementTree as ET

import pytest

from conftest import action, builtin, cond, screenshot, wait_for
from test_playback import playing, stop, tracks  # noqa: F401 (fixtures)

pytestmark = pytest.mark.e2e

SKIN = os.path.join(os.path.dirname(__file__), '..', '..', '1080i')


def key(*buttons):
    """Press remote buttons: the keymap turns them into actions, as on a real remote."""
    name = os.environ.get('KDEV_INSTANCE')
    container = 'kodi-dev-{}-kodi-1'.format(name) if name else 'kodi-dev-kodi-1'
    for button in buttons:
        subprocess.run(['docker', 'exec', container, 'kodi-send', '--keymap=R1', '--button=' + button],
                       check=True, capture_output=True)


def shot(name):
    time.sleep(0.4)  # the fades of the level that went
    screenshot(name)


def seek_hint_condition():
    """The seek bar's hint lives in a dialog without focus, which Control.IsVisible cannot see:
    evaluate its own visible condition (and the dialog's)."""
    root = ET.parse(os.path.join(SKIN, 'DialogSeekBar.xml')).getroot()
    hint = next(i for i in root.iter('include') if i.find("param[@name='id'][@value='490']") is not None)
    return '{} + Window.IsVisible(seekbar)'.format(hint.find("param[@name='visible']").get('value'))


def test_hints_lead_through_the_levels(tracks):
    """A clip outside the library: seek bar, bar, chapter row; no cast row."""
    action('back')
    wait_for('!Window.IsActive(videoosd)')
    key('right')
    hint = seek_hint_condition()
    wait_for(hint)
    shot('hint-seekbar')
    key('select')  # what the hint promises
    wait_for('Window.IsActive(videoosd)')
    wait_for('Control.IsVisible(690)')
    assert not cond(hint)[hint]
    shot('hint-osd')
    key('down')
    wait_for('Window.IsActive(videobookmarks)')
    wait_for('Control.HasFocus(11)')  # the row's timer focuses it once Kodi filled it
    wait_for('Control.IsVisible(92)')
    assert not cond('Control.IsVisible(91)')['Control.IsVisible(91)']  # no cast row for the clip
    shot('hint-chapters')
    key('up')
    wait_for('ControlGroup(9000).HasFocus()')
    key('up')
    wait_for('!Window.IsActive(videobookmarks)')
    wait_for('Control.IsVisible(690)')


def test_cast_row_hints(playing):
    """A library movie: the chapter row points down to the cast row, the cast row back up."""
    key('select')
    wait_for('Window.IsActive(videoosd)')
    wait_for('Control.IsVisible(690)')
    key('down')
    wait_for('Window.IsActive(videobookmarks)')
    wait_for('Control.HasFocus(2)')  # no chapters: the row's timer focuses add bookmark
    wait_for('Control.IsVisible(91)')
    wait_for('Control.IsVisible(92)')
    shot('hint-chapters-movie')
    key('down')
    wait_for('Window.IsActive(1141)')
    wait_for('Control.IsVisible(6590)')
    shot('hint-cast')
    # kodi-dev has no TMDb data: the row stays empty without focus, so Back instead of Up
    key('back')
    wait_for('!Window.IsActive(1141)')
    wait_for('Control.IsVisible(91)')
    action('back')
    stop()


def test_chapter_row_without_chapters_focuses_at_once(playing):
    """Kodi fills the row while it opens: a file without chapters gets the focus on add bookmark
    right away, not after a wait in which no key does anything."""
    key('select')
    wait_for('Window.IsActive(videoosd)')
    wait_for('Control.IsVisible(690)')
    key('down')
    wait_for('Window.IsActive(videobookmarks)')
    wait_for('Control.HasFocus(2)', timeout=0.6)
