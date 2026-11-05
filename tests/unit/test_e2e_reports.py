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
