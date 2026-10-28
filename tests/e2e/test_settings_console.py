"""Settings console: group tiles on the system page, the rail, previews, levels 2 and 3, Back."""
import pytest

from conftest import action, builtin, cond, info, screenshot, wait_for

pytestmark = pytest.mark.e2e

FIRST_ENTRY = {1: 9211, 2: 9221, 3: 9231, 4: 9241, 5: 9251}


def label(name):
    return info(name)[name]


def system_tile(n):
    """Focus group tile n on the system page with the remote: down from the menu, then right."""
    builtin('SetFocus(9105)')
    wait_for('String.IsEqual(Window(Home).Property(nc.page),system)')
    builtin('SetFocus(9601,0,absolute)')
    builtin('SetFocus(9105)')
    action('down')
    wait_for('Control.HasFocus(9601)')
    action(*['right'] * (n - 1))


def settings_level(name):
    builtin('ActivateWindow(PlayerSettings)')
    wait_for('Window.IsActive(playersettings)')
    builtin('SetFocus(20)')
    for _ in range(4):
        if label('Control.GetLabel(20)') == name:
            break
        action('settingslevelchange', delay=0.8)
    assert label('Control.GetLabel(20)') == name
    action('back', delay=1)


@pytest.mark.parametrize('group', [1, 2, 3, 4, 5])
def test_group_tile_opens_console_at_its_first_entry(home, group):
    system_tile(group)
    action('select')
    wait_for('Window.IsActive(settings)')
    wait_for('Control.HasFocus({})'.format(FIRST_ENTRY[group]))
    screenshot('console-group-{}'.format(group))
    action('back', delay=1)
    wait_for('Window.IsActive(home)')
    wait_for('Control.HasFocus(9601)')


def test_levels_pick_on_the_left_only(home):
    """OK opens Kodi's page (level 3) with the cursor in its categories, on the first one. Back
    returns to the entry, Back to the system page."""
    system_tile(1)
    action('select')
    wait_for('Control.HasFocus(9211)')
    action('down')
    wait_for('Control.HasFocus(9212)')
    screenshot('console-level-2')
    action('select', delay=1)
    wait_for('Window.IsActive(mediasettings)')
    wait_for('ControlGroup(3).HasFocus()')
    assert label('System.CurrentControl') == 'Library'
    screenshot('console-level-3')
    action('back', delay=1)
    wait_for('Control.HasFocus(9212)')
    action('back', delay=1)
    wait_for('Window.IsActive(home)')


def test_right_and_left_walk_the_levels(home):
    """Right on a rail entry opens its page (level 3, cursor in the categories), Left there goes
    back to the entry (level 2), Left again back to the system page (level 1)."""
    system_tile(1)
    action('select')
    wait_for('Control.HasFocus(9211)')
    action('down')
    wait_for('Control.HasFocus(9212)')
    action('right', delay=1)
    wait_for('Window.IsActive(mediasettings)')
    wait_for('ControlGroup(3).HasFocus()')
    action('left', delay=1)
    wait_for('Window.IsActive(settings)')
    wait_for('Control.HasFocus(9212)')
    action('left', delay=1)
    wait_for('Window.IsActive(home)')
    wait_for('Control.HasFocus(9601)')


ENTRY_WINDOWS = [('9211', 'playersettings'), ('9221', 'interfacesettings'), ('9222', 'skinsettings'),
                 ('9223', 'profiles'), ('9231', 'addonbrowser'), ('9232', 'filemanager'),
                 ('9241', 'systemsettings'), ('9242', 'servicesettings'), ('9251', 'systeminfo'),
                 ('9252', 'eventlog')]


@pytest.mark.parametrize('entry,window', ENTRY_WINDOWS)
def test_right_in_left_out_on_every_entry(home, entry, window):
    builtin('ActivateWindow(settings)')
    wait_for('Window.IsActive(settings)')
    builtin('SetFocus({})'.format(entry))
    wait_for('Control.HasFocus({})'.format(entry))
    action('right', delay=1)
    wait_for('Window.IsActive({})'.format(window))
    action('left', delay=1)
    wait_for('Window.IsActive(settings)')
    wait_for('Control.HasFocus({})'.format(entry))
    builtin('ReplaceWindow(Home)')


def test_rail_skips_headings(home):
    builtin('SetProperty(nc.settings.group,1,home)')
    builtin('ActivateWindow(settings)')
    wait_for('Control.HasFocus(9211)')
    entries = ['9211', '9212', '9213', '9221', '9222', '9224', '9223', '9231', '9232', '9241', '9242', '9251', '9252']
    if not cond('System.HasPVRAddon')['System.HasPVRAddon']:
        entries.remove('9213')  # live TV only with a PVR client
    seen = []
    for _ in entries:
        seen.append(label('System.CurrentControlID'))
        action('down')
    assert seen == entries
    assert cond('Control.HasFocus(9252)')['Control.HasFocus(9252)']  # no wrap at the end


def test_event_log_from_the_rail(home):
    system_tile(5)
    action('select')
    wait_for('Control.HasFocus(9251)')
    action('down', 'select', delay=0.6)
    wait_for('Window.IsActive(eventlog)')
    screenshot('eventlog')
    action('right')
    wait_for('Control.HasFocus(21)')
    assert label('Control.GetLabel(21)').startswith('Level')
    action('back', delay=1)
    wait_for('Control.HasFocus(9252)')


def test_logging_link_lands_in_its_category(home):
    """Runs last: the button row of the event log keeps the logging button focused."""
    builtin('ActivateWindow(eventlog)')
    wait_for('Window.IsActive(eventlog)')
    builtin('SetFocus(9001)')
    action('select', delay=1)
    wait_for('Window.IsActive(systemsettings)')
    wait_for('ControlGroup(3).HasFocus() + String.IsEqual(System.CurrentControl,Logging)')
    builtin('ReplaceWindow(Home)')
