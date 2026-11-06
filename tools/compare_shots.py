#!/usr/bin/env python3
"""Compare two folders of screenshots: python tools/compare_shots.py A B [--threshold 3]

For the PNGs of tools/screenshots.py --png, 1920x1080, same names on both sides. Per picture it
prints the mean deviation (per colour channel, 0 to 255) of the whole picture and of its worst
tile of TILE x TILE px. The worst tile decides: a focus frame that went missing is a thin line and
drowns in the mean of a whole screen. What shows the time (clock, weather, date, MASKS) is left out.

Exit 0 if every picture stays under the threshold, else 1. A picture on one side only or of
another size is a difference too.
"""
import argparse
import pathlib
import sys

from PIL import Image, ImageChops, ImageDraw, ImageStat

TILE = 64
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


def worst_tile(diff):
    """Mean deviation of the worst TILE x TILE tile of a difference picture."""
    width, height = diff.size
    return max(_mean(diff.crop((x, y, min(x + TILE, width), min(y + TILE, height))))
               for x in range(0, width, TILE) for y in range(0, height, TILE))


def deviation(a, b):
    return worst_tile(difference(a, b))


def compare(a, b, threshold):
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
        worst = worst_tile(diff)
        passed = worst < threshold
        ok = ok and passed
        lines.append('{}: {:.3f} worst tile, {:.4f} whole picture{}'.format(name, worst, _mean(diff), '' if passed else '  DIFFERENT'))
    return lines, ok


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('a')
    parser.add_argument('b')
    parser.add_argument('--threshold', type=float, default=3)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    lines, ok = compare(args.a, args.b, args.threshold)
    print('\n'.join(lines))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
