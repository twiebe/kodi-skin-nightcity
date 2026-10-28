"""The keyboard dialog: Up and Down keep the column. Its letter rows are grouplists, which
otherwise hand the focus to the key that had it last in the next row."""
import pytest

from focus import Page, State

# Kodi fills keys 100 + 20 * row + column and hides those without a character
# (CGUIDialogKeyboardGeneric). English QWERTY: 13, 13, 11 and 10 keys.
ROWS = (13, 13, 11, 10)
HIDDEN = {str(100 + 20 * r + c) for r, n in enumerate(ROWS) for c in range(n, 13)}


def key(row, column):
    return str(100 + 20 * row + column)


@pytest.fixture(scope='module')
def page():
    return Page('DialogKeyboard.xml')


@pytest.mark.parametrize('row', [0, 1, 2])
def test_down_keeps_the_column(page, row):
    for column in range(ROWS[row]):
        target = key(row + 1, min(column, ROWS[row + 1] - 1))
        assert page.move(key(row, column), 'ondown', State(hidden=HIDDEN))[0] == target, column


@pytest.mark.parametrize('row', [1, 2, 3])
def test_up_keeps_the_column(page, row):
    for column in range(ROWS[row]):
        target = key(row - 1, min(column, ROWS[row - 1] - 1))
        assert page.move(key(row, column), 'onup', State(hidden=HIDDEN))[0] == target, column


def test_up_from_the_top_row_reaches_the_field(page):
    assert page.move(key(0, 5), 'onup', State(hidden=HIDDEN))[0] == '312'
