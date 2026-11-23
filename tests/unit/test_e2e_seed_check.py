"""The e2e run's seed check: a pool made from an older kdev seed (no libraries, no music) stops the
run at once instead of failing test by test with KeyError."""
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e2e_conftest_seed', ROOT / 'tests' / 'e2e' / 'conftest.py')
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)

CURRENT = {'admin': {'token': 't', 'api_key': 'k'}, 'users': {'tester': {'id': 'u'}},
           'libraries': {'Movies': 'm', 'Shows': 's', 'Music': 'a'},
           'items': {'Kdev Alpha': '1', 'Blue Satellite': '2'}}
OLD = {'admin': {'token': 't', 'api_key': 'k'}, 'users': {'tester': {'id': 'u'}},
       'items': {'Kdev Alpha': '1'}}


def test_a_current_seed_has_all_the_tests_read():
    assert e2e.seed_missing(CURRENT) == []


def test_an_old_seed_lacks_the_libraries_and_the_album():
    assert e2e.seed_missing(OLD) == ['libraries.Movies', 'items.Blue Satellite']


def _pool(tmp_path, monkeypatch, seed, where='edge-0'):
    folder = tmp_path / 'instances' / where / 'data'
    folder.mkdir(parents=True)
    (folder / 'seed.json').write_text(json.dumps(seed))
    monkeypatch.setattr(e2e, 'KODI_DEV', tmp_path)


def test_a_stale_pool_stops_the_run_with_how_to_fix_it(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch, OLD)
    with pytest.raises(pytest.exit.Exception) as stop:
        e2e.check_pool_seed('edge')
    assert 'pool edge' in str(stop.value) and 'libraries.Movies' in str(stop.value)
    assert 'KDEV_POOL=edge kdev pool remove --yes' in str(stop.value)


def test_the_template_counts_before_the_first_worker_exists(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch, OLD, where='edge')
    with pytest.raises(pytest.exit.Exception):
        e2e.check_pool_seed('edge')


def test_a_current_pool_runs(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch, CURRENT)
    e2e.check_pool_seed('edge')


def test_a_pool_not_made_yet_is_not_checked(tmp_path, monkeypatch):
    monkeypatch.setattr(e2e, 'KODI_DEV', tmp_path)
    e2e.check_pool_seed('edge')
