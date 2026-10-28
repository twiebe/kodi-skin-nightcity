import time

import pytest

from conftest import action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e


def visible(control_id):
    key = 'Control.IsVisible({})'.format(control_id)
    return cond(key)[key]


def test_spotlight_has_items(home):
    wait_for('Integer.IsGreater(Container(9000).NumItems,0)')
    assert info('Container(9000).ListItem.Title')['Container(9000).ListItem.Title']
    screenshot('home-spotlight')


def test_spotlight_rotates(home):
    wait_for('Integer.IsGreater(Container(9000).NumItems,0)')
    first = info('Container(9000).ListItem.Title')['Container(9000).ListItem.Title']
    end = time.time() + 25
    while time.time() < end:
        if info('Container(9000).ListItem.Title')['Container(9000).ListItem.Title'] != first:
            return
        time.sleep(1)
    pytest.fail('spotlight did not rotate away from {!r}'.format(first))


def test_logo_fallback(home):
    """Review focus 1: the kodi-dev movies have no clearlogo, the title text takes its place."""
    wait_for('Integer.IsGreater(Container(9000).NumItems,0)')
    assert not info('Container(9000).ListItem.Art(clearlogo)')['Container(9000).ListItem.Art(clearlogo)']
    assert visible(9020)
    assert not visible(9021)


def test_rating_slot_hidden_without_data(home):
    """Review focus 3: the kodi-dev movies have neither a library rating nor TMDb data."""
    wait_for('Integer.IsGreater(Container(9000).NumItems,0)')
    labels = info('Container(9000).ListItem.Rating', 'Window(Home).Property(TMDbHelper.ListItem.tmdb_rating)')
    assert labels['Container(9000).ListItem.Rating'] in ('', '0.0')
    assert not labels['Window(Home).Property(TMDbHelper.ListItem.tmdb_rating)']
    assert not visible(9030)


def test_play_from_spotlight(home):
    wait_for('Integer.IsGreater(Container(9000).NumItems,0)')
    builtin('SetFocus(9010)')
    wait_for('Control.HasFocus(9010)')
    action('select')
    try:
        wait_for('Player.HasVideo', timeout=20)
    finally:
        if rpc('Player.GetActivePlayers'):
            rpc('Player.Stop', {'playerid': 1})


def test_tmdbhelper_service_switched_on(home):
    """Review I2: TMDb Helper's poller only fills ListItem properties with this skin bool set."""
    builtin('Skin.Reset(TMDbHelper.Service)')
    builtin('ReplaceWindow(Settings)')  # Home's onload runs only when Home is (re)opened
    wait_for('Window.IsActive(settings)')
    builtin('ReplaceWindow(Home)')
    wait_for('Skin.HasSetting(TMDbHelper.Service)')


def seconds_between_changes():
    key = 'Container(9000).CurrentItem'
    wait_for('Integer.IsGreater(Container(9000).NumItems,2)')
    start = info(key)[key]
    wait_for('!Integer.IsEqual({},{})'.format(key, start), timeout=70)
    changed, t0 = info(key)[key], time.time()
    wait_for('!Integer.IsEqual({},{})'.format(key, changed), timeout=70)
    return time.time() - t0


def reopen_home():
    builtin('ReplaceWindow(Settings)')  # Home reloads its spotlight includes when reopened
    wait_for('Window.IsActive(settings)')
    builtin('ReplaceWindow(Home)')
    wait_for('Window.IsActive(home)')


def test_spotlight_changes_every_15_seconds_by_default(home):
    assert 14 <= seconds_between_changes() <= 17


def test_spotlight_interval_from_skin_settings(home):
    """The change row of the Home category in the skin settings cycles 15, 30, 60 s, still,
    10 s; Home picks the new interval up."""
    builtin('ActivateWindow(SkinSettings)')
    wait_for('Window.IsActive(skinsettings)')
    try:
        builtin('SetFocus(9002)')
        wait_for('Control.IsVisible(212)')
        builtin('SetFocus(212)')
        wait_for('Control.HasFocus(212)')
        values = []
        for _ in range(5):
            action('select', delay=0.5)
            values.append(info('Skin.String(SpotlightInterval)')['Skin.String(SpotlightInterval)'])
        assert values == ['30', '60', 'off', '10', '']
        builtin('Skin.SetString(SpotlightInterval,10)')
        reopen_home()
        assert 9 <= seconds_between_changes() <= 12
    finally:
        builtin('Skin.Reset(SpotlightInterval)')
        reopen_home()
