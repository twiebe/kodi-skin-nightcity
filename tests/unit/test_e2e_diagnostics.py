"""What the e2e run keeps and does when a test's setup fails: a Kodi stuck in a state no setup gets
out of failed every following test on it (30 setup errors in a run), and the summary cut the
messages that would have said why."""
import importlib.util
import pathlib
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e2e_conftest_diag', ROOT / 'tests' / 'e2e' / 'conftest.py')
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)


def test_a_streak_of_setup_errors_starts_kodi_anew():
    streak, reset = e2e.setup_streak(0, True)
    assert (streak, reset) == (1, False)
    assert e2e.setup_streak(streak, True) == (0, True)


def test_a_setup_that_works_ends_the_streak():
    assert e2e.setup_streak(1, False) == (0, False)
    assert e2e.setup_streak(0, False) == (0, False)


def test_started_scripts_once_each_in_order():
    log = '\n'.join([
        'debug <general>: CPythonInvoker(4, special://skin/scripts/nightcity.py): start processing',
        'debug <general>: CPythonInvoker(4, special://skin/scripts/nightcity.py): the source file to load is x',
        'debug <general>: CPythonInvoker(7, /home/kodi/.kodi/addons/x/service.py): start processing',
        'debug <general>: CPythonInvoker(9, special://skin/scripts/nightcity.py): start processing',
    ])
    assert e2e.started_scripts(log) == ['special://skin/scripts/nightcity.py', '/home/kodi/.kodi/addons/x/service.py']


def test_the_summary_has_every_setup_error_whole():
    message = 'AssertionError: timed out waiting for Control.HasFocus(9010)' + ' and more' * 20
    run = {'setup': [('tests/e2e/test_library_bar.py::test_a', 'gw2', message, '/kept/pool-2-x')],
           'reset': [('tests/e2e/test_library_bar.py::test_b', 'Kodi of pool-2 started anew after 2 setup errors in a row')]}
    lines = e2e.run_report_lines(run)
    assert lines[0] == 'setup errors: 1'
    assert lines[1].endswith(message) and '[gw2]' in lines[1]
    assert lines[2] == '    kept: /kept/pool-2-x'
    assert 'started anew' in lines[3]


def test_the_controller_collects_setup_errors_and_resets(monkeypatch):
    monkeypatch.delenv('PYTEST_XDIST_WORKER', raising=False)
    monkeypatch.setattr(e2e, '_run_report', {'setup': [], 'reset': []})
    crash = SimpleNamespace(message='AssertionError: timed out waiting for Control.HasFocus(9010)')
    report = SimpleNamespace(when='setup', failed=True, nodeid='t::a', longrepr=SimpleNamespace(reprcrash=crash),
                             node=SimpleNamespace(gateway=SimpleNamespace(id='gw2')),
                             user_properties=[('kept', '/k'), ('reset', 'Kodi of pool-2 started anew')])
    e2e.pytest_runtest_logreport(report)
    assert e2e._run_report['setup'] == [('t::a', 'gw2', crash.message, '/k')]
    assert e2e._run_report['reset'] == [('t::a', 'Kodi of pool-2 started anew')]
