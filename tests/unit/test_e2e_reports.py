"""What the e2e run reports beyond its tests: a kept kodi.log when a file fails wholesale, and the
crashes of Kodi, which a restart hides."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e2e_conftest', ROOT / 'tests' / 'e2e' / 'conftest.py')
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)


def test_a_crash_log_of_this_run_counts():
    listing = '1000 /home/kodi/kodi_crashlog-20261105_094100.log\n2000 /home/kodi/kodi_crashlog-20261105_180000.log\n'
    assert e2e.crash_logs(listing, 1500) == ['kodi_crashlog-20261105_180000.log']


@pytest.mark.parametrize('listing', ['', 'ls: cannot access\n', '\n'])
def test_no_crash_log_is_no_crash(listing):
    assert e2e.crash_logs(listing, 0) == []


def test_the_summary_says_none_too():
    """A run that says nothing about crashes cannot be told from one that did not look."""
    assert e2e.crash_summary({'a-0': [], 'a-1': []}) == ['Kodi crashes in this run: 0 (2 workers looked at)']


def test_the_summary_names_each_crash():
    lines = e2e.crash_summary({'a-0': ['kodi_crashlog-1.log'], 'a-1': [], 'a-2': ['x.log', 'y.log']})
    assert lines == ['Kodi crashes in this run: 3 (3 workers looked at)', '  a-0: kodi_crashlog-1.log', '  a-2: x.log', '  a-2: y.log']


def test_a_worker_it_could_not_ask_is_said():
    lines = e2e.crash_summary({'a-0': [], 'a-1': None})
    assert lines == ['Kodi crashes in this run: 0 (1 workers looked at)', '  a-1: not running, its crash logs cannot be read']


def test_the_log_is_kept_once_a_file_has_failed_more_than_a_few_times():
    seen = {}
    assert [e2e.keep_log_now(seen, 'test_x.py') for _ in range(5)] == [False, False, True, False, False]
    assert e2e.keep_log_now(seen, 'test_y.py') is False


@pytest.mark.parametrize('condition,expected', [
    ('Integer.IsEqual(System.CurrentControlId,5200)', 'Integer.IsEqual(System.CurrentControlId,05200)'),
    ('Control.HasFocus(9010)', 'Control.HasFocus(09010)'),
    ('Integer.IsEqual(Container(5000).CurrentItem,3) + !Container(5000).IsUpdating', 'Integer.IsEqual(Container(05000).CurrentItem,03) + !Container(05000).IsUpdating')])
def test_a_number_can_be_written_anew_with_the_same_value(condition, expected):
    assert e2e.respelled(condition) == expected


@pytest.mark.parametrize('condition', ['Window.IsActive(home)', '!String.IsEmpty(Window(Home).Property(nc.service))',
                                       'String.IsEqual(Skin.String(nc.sort),year)', 'String.IsEqual(Window(Home).Property(a),12)'])
def test_what_has_no_number_of_its_own_stays(condition):
    """A string may not be touched: 012 is not 12 there, and "not equal" would hold by that."""
    assert e2e.respelled(condition) == condition


def test_a_stuck_condition_does_not_fail_the_test_and_is_said(monkeypatch):
    def holds(condition):
        return {condition: condition == 'Integer.IsEqual(A,05)'}
    monkeypatch.setattr(e2e, 'cond', holds)
    with pytest.warns(UserWarning, match='stuck'):
        e2e.wait_for('Integer.IsEqual(A,5)', timeout=0.1)


def test_a_condition_that_does_not_hold_still_fails(monkeypatch):
    monkeypatch.setattr(e2e, 'cond', lambda condition: {condition: False})
    with pytest.raises(AssertionError, match='timed out'):
        e2e.wait_for('Integer.IsEqual(A,5)', timeout=0.1)


class _Item:
    def __init__(self, *keywords):
        self.keywords = keywords
        self.marks = []

    def add_marker(self, mark):
        self.marks.append(mark)


def test_the_nightcity_look_is_skipped_under_another_skin_with_a_reason():
    look, plain = _Item('e2e', 'nightcity_look'), _Item('e2e')
    e2e.skip_nightcity_look([look, plain], 'skin.confuse')
    assert [mark.name for mark in look.marks] == ['skip']
    assert 'skin.confuse' in look.marks[0].kwargs['reason']
    assert plain.marks == []


def test_the_nightcity_look_runs_under_nightcity():
    look = _Item('e2e', 'nightcity_look')
    e2e.skip_nightcity_look([look], 'skin.nightcity')
    assert look.marks == []


def test_the_skin_under_test_comes_from_nc_skin(monkeypatch):
    def loaded():
        module = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(module)
        return module.SKIN_ID, module.OTHER_SKIN

    monkeypatch.delenv('NC_SKIN', raising=False)
    assert loaded() == ('skin.nightcity', 'skin.confuse')
    monkeypatch.setenv('NC_SKIN', 'confuse')
    assert loaded() == ('skin.confuse', 'skin.nightcity')


def test_a_run_assembles_confuse_once_not_per_worker(monkeypatch):
    """Kodi mounts _build/confuse: without this a run tests the overlay of the last assemble."""
    import sys
    sys.path.insert(0, str(ROOT / 'tools'))
    import build
    calls = []
    monkeypatch.setattr(build, 'assemble', lambda skin, dest: calls.append((skin, dest)))
    monkeypatch.setattr(e2e, 'POOL', None)
    monkeypatch.setenv('PYTEST_XDIST_WORKER', 'gw1')
    e2e.pytest_configure(None)
    assert calls == []
    monkeypatch.delenv('PYTEST_XDIST_WORKER')
    e2e.pytest_configure(None)
    assert calls == [('confuse', ROOT / '_build' / 'confuse')]
