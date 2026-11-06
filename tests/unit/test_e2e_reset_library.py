"""reset_library of the e2e run: only rows of tests go, whatever ids the library has reached. In a
long-lived library real rows pass 1000 (The Matrix: movie 1003, file 17230); once its files row was
gone Kodi no longer listed it and every test on it was skipped."""
import importlib.util
import pathlib
import sqlite3

ROOT = pathlib.Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location('e2e_conftest', ROOT / 'tests' / 'e2e' / 'conftest.py')
e2e = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(e2e)

MATRIX = (1003, 17230, 'The Matrix')


def _library(tmp_path, monkeypatch):
    folder = tmp_path / 'kodi' / 'userdata' / 'Database'
    folder.mkdir(parents=True)
    database = folder / 'MyVideos131.db'
    connection = sqlite3.connect(str(database))
    connection.executescript("""
        CREATE TABLE movie (idMovie INTEGER, idFile INTEGER, c00 TEXT);
        CREATE TABLE files (idFile INTEGER);
        CREATE TABLE videoversion (idFile INTEGER);
        CREATE TABLE tvshow (idShow INTEGER, c00 TEXT);
        CREATE TABLE episode (idEpisode INTEGER, idShow INTEGER);
    """)
    bulk = e2e.BULK_FROM
    connection.executemany('INSERT INTO movie VALUES (?, ?, ?)',
                           [(1, 7, 'Kdev Alpha'), MATRIX, (3, 15417, 'Bulk 0000'), (bulk, bulk, 'Bulk a')])
    connection.executemany('INSERT INTO files VALUES (?)', [(7,), (MATRIX[1],), (15417,), (bulk,)])
    connection.executemany('INSERT INTO videoversion VALUES (?)', [(7,), (MATRIX[1],), (bulk,)])
    connection.executemany('INSERT INTO tvshow VALUES (?, ?)', [(1, 'Kdev Show'), (2, 'BulkShow 00')])
    connection.executemany('INSERT INTO episode VALUES (?, ?)', [(1, 1), (2, 2)])
    connection.commit()
    connection.close()
    monkeypatch.setattr(e2e, '_data', lambda: tmp_path)
    monkeypatch.setattr(e2e, 'rpc', lambda method, params=None: {})
    return database


def _rows(database, query):
    connection = sqlite3.connect(str(database))
    rows = connection.execute(query).fetchall()
    connection.close()
    return rows


def test_real_rows_stay_whatever_their_id(tmp_path, monkeypatch):
    database = _library(tmp_path, monkeypatch)
    e2e.reset_library()
    assert _rows(database, 'SELECT idMovie, idFile, c00 FROM movie ORDER BY idMovie') == [(1, 7, 'Kdev Alpha'), MATRIX]
    assert (MATRIX[1],) in _rows(database, 'SELECT idFile FROM files')
    assert (MATRIX[1],) in _rows(database, 'SELECT idFile FROM videoversion')
    assert _rows(database, 'SELECT c00 FROM tvshow') == [('Kdev Show',)]
    assert _rows(database, 'SELECT idEpisode FROM episode') == [(1,)]


def test_rows_of_tests_go(tmp_path, monkeypatch):
    database = _library(tmp_path, monkeypatch)
    e2e.reset_library()
    for table, key in (('movie', 'idMovie'), ('files', 'idFile'), ('videoversion', 'idFile')):
        assert _rows(database, 'SELECT {0} FROM {1} WHERE {0} >= {2}'.format(key, table, e2e.BULK_FROM)) == []


def test_every_bulk_row_of_the_video_library_is_above_real_ids():
    """A test with a limit of its own would delete real files rows like reset_library did."""
    assert e2e.BULK_FROM >= 1000000
    for name in ('test_library_bar.py', 'test_widgets.py'):
        source = (ROOT / 'tests' / 'e2e' / name).read_text(encoding='utf-8')
        assert 'BULK_FROM' in source and 'BULK_FROM = ' not in source, name
        assert '>= 2000' not in source and 'range(2000' not in source, name
