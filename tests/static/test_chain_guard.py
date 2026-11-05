from conftest import ROOT, parse


def _guard():
    return next(t for t in parse(ROOT / '1080i' / 'Timers.xml').iter('timer') if t.findtext('name') == 'nc_chain_guard')


def test_the_guard_ends_when_the_manager_saw_the_page():
    stop = _guard().findtext('stop')
    assert 'String.IsEqual(Window(Home).Property(TMDbHelper.Position.Seen),Window(Home).Property(TMDbHelper.Position))' in stop


def test_the_guard_ends_by_itself_without_the_property():
    """An older TMDb Helper publishes nothing, and a lost property must not block Back."""
    assert ' | Integer.IsGreaterOrEqual(Skin.TimerElapsedSecs(nc_chain_guard),5)' in _guard().findtext('stop')
