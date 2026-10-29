"""The numeric dialog (PIN, numbers): Up and Down keep the column, Left and Right keep the row.
Its rows are grouplists, which otherwise hand the focus to the key that had it last."""
import pytest

from focus import Page, State

# Kodi ids: 10-19 digits, 20 previous, 22 next, 23 backspace, 21 done
GRID = (('11', '12', '13'), ('14', '15', '16'), ('17', '18', '19'), ('20', '10', '22'))


@pytest.fixture(scope='module')
def page():
    return Page('DialogNumeric.xml')


@pytest.mark.parametrize('row', [0, 1, 2])
def test_down_keeps_the_column(page, row):
    for column, src in enumerate(GRID[row]):
        assert page.move(src, 'ondown', State())[0] == GRID[row + 1][column], src


@pytest.mark.parametrize('row', [1, 2, 3])
def test_up_keeps_the_column(page, row):
    for column, src in enumerate(GRID[row]):
        assert page.move(src, 'onup', State())[0] == GRID[row - 1][column], src


def test_side_buttons_keep_the_row():
    """Backspace sits beside the first row, done beside the second and below."""
    page = Page('DialogNumeric.xml')
    assert page.move('13', 'onright', State())[0] == '23'
    for src in ('16', '19', '22'):
        assert page.move(src, 'onright', State())[0] == '21', src
    assert page.move('23', 'onleft', State())[0] == '13'
    assert page.move('21', 'onleft', State())[0] == '16'
