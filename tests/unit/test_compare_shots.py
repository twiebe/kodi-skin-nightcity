"""tools/compare_shots.py: two folders of screenshots, per picture the mean deviation against a
threshold, what shows the time left out."""
import pathlib
import subprocess
import sys

import pytest
from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

import compare_shots  # noqa: E402

SIZE = (1920, 1080)


def picture(path, color=(40, 40, 40), box=None, box_color=(255, 255, 255)):
    image = Image.new('RGB', SIZE, color)
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=box_color)
    path.parent.mkdir(exist_ok=True)
    image.save(path)


def run(*args):
    return subprocess.run([sys.executable, str(ROOT / 'tools' / 'compare_shots.py'), *map(str, args)],
                          capture_output=True, text=True)


def test_same_pictures_pass(tmp_path):
    for folder in ('a', 'b'):
        picture(tmp_path / folder / '01-home.png')
    done = run(tmp_path / 'a', tmp_path / 'b')
    assert done.returncode == 0, done.stdout + done.stderr
    assert '01-home.png' in done.stdout


def test_a_different_picture_fails_with_name_and_value(tmp_path):
    picture(tmp_path / 'a' / '01-home.png')
    picture(tmp_path / 'b' / '01-home.png', color=(50, 50, 50))
    done = run(tmp_path / 'a', tmp_path / 'b')
    assert done.returncode == 1
    assert '01-home.png' in done.stdout and '10.0' in done.stdout


def test_threshold_decides(tmp_path):
    picture(tmp_path / 'a' / '01-home.png')
    picture(tmp_path / 'b' / '01-home.png', color=(50, 50, 50))
    assert run(tmp_path / 'a', tmp_path / 'b', '--threshold', '11').returncode == 0
    assert run(tmp_path / 'a', tmp_path / 'b', '--threshold', '9').returncode == 1


def test_default_threshold_is_above_the_noise():
    assert compare_shots.parse_args(['a', 'b']).threshold == 3


def test_clock_weather_and_date_are_masked(tmp_path):
    """Every region of MASKS may change as it likes."""
    for name, boxes in compare_shots.MASKS.items():
        for box in boxes:
            picture(tmp_path / 'a' / name)
            picture(tmp_path / 'b' / name, box=box)
            assert compare_shots.deviation(tmp_path / 'a' / name, tmp_path / 'b' / name) == 0, (name, box)


def test_a_small_change_outside_the_masks_counts(tmp_path):
    """A focus frame is a thin line: it must not drown in the mean of a whole screen. The value is
    the worst tile of the picture, not the mean of all of it."""
    picture(tmp_path / 'a' / '01-home.png')
    picture(tmp_path / 'b' / '01-home.png', box=(400, 500, 440, 540))
    assert compare_shots.deviation(tmp_path / 'a' / '01-home.png', tmp_path / 'b' / '01-home.png') > 2


def test_a_picture_only_on_one_side_fails(tmp_path):
    picture(tmp_path / 'a' / '01-home.png')
    picture(tmp_path / 'a' / '02-movies.png')
    picture(tmp_path / 'b' / '01-home.png')
    done = run(tmp_path / 'a', tmp_path / 'b')
    assert done.returncode == 1
    assert '02-movies.png' in done.stdout


def test_empty_folders_fail(tmp_path):
    (tmp_path / 'a').mkdir()
    (tmp_path / 'b').mkdir()
    assert run(tmp_path / 'a', tmp_path / 'b').returncode == 1


@pytest.mark.parametrize('size', [(1280, 720)])
def test_another_size_fails(tmp_path, size):
    picture(tmp_path / 'a' / '01-home.png')
    (tmp_path / 'b').mkdir()
    Image.new('RGB', size, (40, 40, 40)).save(tmp_path / 'b' / '01-home.png')
    assert run(tmp_path / 'a', tmp_path / 'b').returncode == 1


def test_values_are_not_rounded_away(tmp_path):
    """One changed pixel is a difference, however small the tile's mean."""
    picture(tmp_path / 'a' / '02-movies.png')
    picture(tmp_path / 'b' / '02-movies.png', box=(400, 500, 400, 500))
    value = compare_shots.deviation(tmp_path / 'a' / '02-movies.png', tmp_path / 'b' / '02-movies.png')
    assert 0 < value < 0.1
