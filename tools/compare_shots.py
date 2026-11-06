#!/usr/bin/env python3
"""Compare two folders of screenshots: python tools/compare_shots.py A B [--threshold 1] [--pixels 16]

For the PNGs of tools/screenshots.py --png, 1920x1080, same names on both sides. Per picture it
prints, for its worst tile of TILE x TILE px, the mean deviation (per colour channel, 0 to 255) and
the number of pixels off by more than DELTA in a channel, then the mean of the whole picture.

Two rules decide, per tile. The mean finds a change over an area, however faint. The count finds a
thin line: a missing outline changes few pixels by much and hardly moves the mean of its tile, while
a paused video frame changes many pixels by at most 6. What shows the time (clock, weather, date,
MASKS) is left out.

Exit 0 if every picture stays under both limits, else 1. A picture on one side only or of another
size is a difference too.
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageChops, ImageDraw, ImageStat

TILE = 64
DELTA = 8  # above the video noise of the player shot (6), below any outline of the palette (22 up)
# file: boxes (left, top, right, bottom) that change with the time, not with the skin
TOP_RIGHT = (1300, 0, 1920, 90)  # weather and clock
ENDS_AT = (590, 275, 1130, 320)  # the "ends at" tag and the tags it pushes along
MASKS = {
    '01-home.png': [TOP_RIGHT, ENDS_AT],
    '02-movies.png': [TOP_RIGHT, ENDS_AT],
    '03-info.png': [TOP_RIGHT, ENDS_AT],
    '04-person.png': [TOP_RIGHT],
    # "ends at" and how far the player has buffered ahead of the paused position
    '05-player.png': [TOP_RIGHT, (1640, 885, 1920, 925), (782, 866, 1920, 880)],
    '06-music.png': [TOP_RIGHT],
    '07-settings.png': [TOP_RIGHT],
    '08-quick-menu.png': [TOP_RIGHT, ENDS_AT, (1260, 130, 1600, 248)],  # clock and date of the panel
}


def difference(a, b):
    """The picture of per-channel differences of files A and B, the boxes of MASKS black."""
    first, second = Image.open(a).convert('RGB'), Image.open(b).convert('RGB')
    if first.size != second.size:
        raise ValueError('{} against {}'.format(first.size, second.size))
    diff = ImageChops.difference(first, second)
    draw = ImageDraw.Draw(diff)
    for box in MASKS.get(pathlib.Path(a).name, []):
        draw.rectangle(box, fill=(0, 0, 0))
    return diff


def _mean(image):
    values = ImageStat.Stat(image).mean
    return sum(values) / len(values)


def _tiles(image):
    width, height = image.size
    return (image.crop((x, y, min(x + TILE, width), min(y + TILE, height)))
            for x in range(0, width, TILE) for y in range(0, height, TILE))


def worst_tile(diff):
    """Mean deviation of the worst TILE x TILE tile of a difference picture."""
    return max(_mean(tile) for tile in _tiles(diff))


def worst_count(diff):
    """The most pixels off by more than DELTA in a channel within one tile."""
    red, green, blue = diff.split()
    strongest = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    return max(sum(tile.histogram()[DELTA + 1:]) for tile in _tiles(strongest))


def deviation(a, b):
    return worst_tile(difference(a, b))


def compare(a, b, threshold, pixels):
    """Lines of the report and whether all pictures pass."""
    names_a, names_b = ({p.name for p in pathlib.Path(d).glob('*.png')} for d in (a, b))
    lines, ok = [], bool(names_a | names_b)
    if not ok:
        lines.append('no PNGs in {} and {}'.format(a, b))
    for name in sorted(names_a | names_b):
        if name not in names_a or name not in names_b:
            lines.append('{}: only in {}'.format(name, a if name in names_a else b))
            ok = False
            continue
        try:
            diff = difference(pathlib.Path(a) / name, pathlib.Path(b) / name)
        except ValueError as error:
            lines.append('{}: size {}'.format(name, error))
            ok = False
            continue
        worst, count = worst_tile(diff), worst_count(diff)
        passed = worst < threshold and count < pixels
        ok = ok and passed
        lines.append('{}: {:.3f} worst tile, {} pixels over {}, {:.4f} whole picture{}'.format(
            name, worst, count, DELTA, _mean(diff), '' if passed else '  DIFFERENT'))
    return lines, ok


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('a')
    parser.add_argument('b')
    parser.add_argument('--threshold', type=float, default=1, help='limit of the mean of a tile')
    parser.add_argument('--pixels', type=int, default=16, help='limit of the pixels over DELTA in a tile')
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    lines, ok = compare(args.a, args.b, args.threshold, args.pixels)
    print('\n'.join(lines))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
