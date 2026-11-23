"""The e2e run and the Kodi of its pool: a pool of Kodi 22 is tested only when the run asks for it
(--kodi 22), and a test can be bound to the Kodi whose behaviour it checks (marker kodi)."""
import importlib.util
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e2e_conftest_kodi', ROOT / 'tests' / 'e2e' / 'conftest.py')
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)


def _pool(tmp_path, monkeypatch, version=None):
    folder = tmp_path / 'instances' / 'k22' / 'data'
    folder.mkdir(parents=True)
    if version:
        (folder / 'kodi.version').write_text(version + '\n')
    monkeypatch.setattr(e2e, 'KODI_DEV', tmp_path)


def test_a_pool_from_before_kdev_kodi_is_21(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch)
    assert e2e.pool_kodi('k22') == '21'
    e2e.check_pool_kodi('k22', '21')


def test_a_22_pool_runs_only_when_asked_for(tmp_path, monkeypatch):
    _pool(tmp_path, monkeypatch, '22')
    with pytest.raises(pytest.exit.Exception) as stop:
        e2e.check_pool_kodi('k22', '21')
    assert 'pass --kodi 22' in str(stop.value)
    e2e.check_pool_kodi('k22', '22')


class _Item:
    def __init__(self, *versions, **kwargs):
        self.marker = pytest.mark.kodi(*versions, **kwargs).mark if versions else None
        self.added = []

    def get_closest_marker(self, name):
        return self.marker

    def add_marker(self, marker):
        self.added.append(marker)


def test_a_test_bound_to_a_kodi_skips_on_the_other():
    only21, both, free = _Item(21, reason='the selection dialog'), _Item(21, 22), _Item()
    e2e.skip_other_kodi([only21, both, free], '22')
    assert len(only21.added) == 1 and 'the selection dialog' in only21.added[0].kwargs['reason']
    assert both.added == [] and free.added == []
    e2e.skip_other_kodi([only21], '21')
    assert len(only21.added) == 1
