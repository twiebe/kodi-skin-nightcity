"""Player level hints: the seek bar shows that OK opens the OSD, the bar that Down opens the
cast row (library titles only), the cast row Up back to the controls; on subtitles, audio and
video the footer adds OK, all settings. Keys go through Kodi's remote keymap (kodi-send), as on
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
    """A clip outside the library: seek bar, bar; no cast row, so no Down hint. On subtitles the
    footer names OK, all settings, alone."""
    action('back')
    # gone, not only closing: Kodi drops a key sent during the close animation
    wait_for('!Window.IsVisible(videoosd)')
    key('right')
    hint = seek_hint_condition()
    wait_for(hint)
    shot('hint-seekbar')
    key('select')  # what the hint promises
    wait_for('Window.IsActive(videoosd)')
    assert not cond(hint)[hint]
    assert not cond('Control.IsVisible(690)')['Control.IsVisible(690)']  # no cast row for the clip
    builtin('SetFocus(605)')
    wait_for('Control.IsVisible(692)')
    assert not cond('Control.IsVisible(691)')['Control.IsVisible(691)']
    shot('hint-osd')


def test_cast_row_hints(playing):
    """A library movie: the bar points down to cast & crew, the cast row back up to the controls;
    on subtitles, audio and video "↓ cast & crew   OK all settings"; under the row the seek bar
    dialog dims the whole video, under its seek line."""
    key('select')
    wait_for('Window.IsActive(videoosd)')
    wait_for('Control.IsVisible(690)')
    shot('hint-osd-movie')
    for button in (605, 606, 607):
        builtin('SetFocus({})'.format(button))
        wait_for('Control.IsVisible(691) + !Control.IsVisible(690)')
    shot('hint-osd-video')
    builtin('SetFocus(602)')
    wait_for('Control.IsVisible(690)')
    key('down')
    wait_for('Window.IsActive(1141)')
    wait_for('Control.IsVisible(6590)')
    # the scrim lies in the seek bar dialog, without focus: its own condition and the dialog's
    wait_for('Window.IsActive(1141) + Window.IsVisible(seekbar)')
    shot('hint-cast')
    # kodi-dev has no TMDb data for this movie: the row stays empty without focus, so Back
    key('back')
    wait_for('!Window.IsVisible(1141)')
    wait_for('Control.IsVisible(690)')
    action('back')
    stop()


def test_chapter_panel_without_chapters_focuses_at_once(playing):
    """Kodi fills the panel while it opens: a file without chapters gets the focus on add bookmark
    right away, not after a wait in which no key does anything."""
    key('select')
    wait_for('Window.IsActive(videoosd)')
    builtin('SetFocus(608)')
    # the panel shows with the focus on the button, as a track panel
    wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(90)', timeout=5)
    key('up')
    wait_for('Window.IsActive(videobookmarks)')
    wait_for('Control.HasFocus(2)', timeout=0.6)



def test_cast_row_from_the_chapters_button_returns_to_its_panel(playing):
    """Down from the chapters button (its panel up) opens the cast row of a library title; Back
    there closes it and the button's panel shows again, the focus on the button."""
    key('select')
    wait_for('Window.IsActive(videoosd)')
    builtin('SetFocus(608)')
    wait_for('Window.IsActive(videobookmarks) + Control.HasFocus(90)', timeout=5)
    time.sleep(0.3)
    key('down')
    wait_for('Window.IsActive(1141) + !Window.IsVisible(videobookmarks)', timeout=5)
    key('back')
    wait_for('Window.IsActive(videobookmarks) + !Window.IsVisible(1141) + Control.HasFocus(90)', timeout=5)
    action('back')
    stop()
