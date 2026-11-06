#!/usr/bin/env python3
"""Render the white, rounded UI textures of Confuse into skins/confuse/media/ui (coloured in the skin
with colordiffuse). Nightcity's textures in media/ui stay as they are.

Same names as Nightcity's cut-corner textures (cut*.png) with the same sizes and padding, so a
control that still names one gets the rounded twin: radius 12 where the border is 12 or 22 (buttons),
16 where it is 16 or 26 (panels, rings). The pill, ring, chip, dot, menu line and warm fade are new.
Sizes are 1080 px grid pixels, drawn 1:1: a mask of a 290 x 435 card is shown at 290 x 435, so its
radius is the radius on screen. The design gives cards 8 px at 1280 x 720, so 12 px here (x 1.5).

python tools/make_textures_confuse.py
"""
import pathlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter

UI = pathlib.Path(__file__).resolve().parents[1] / 'skins' / 'confuse' / 'media' / 'ui'
SCALE = 8
CARD_RADIUS = 12  # 8 px at 1280 x 720
CARD_SIZES = [(200, 300), (290, 435), (360, 540), (320, 180), (160, 220), (200, 200), (280, 280), (360, 360)]
GLOW_PAD = 10  # a padded texture keeps this much clear around its shape for the shadow


def rrect(size, pad, radius):
    """Mask (supersampled) of a rounded rectangle inset by pad."""
    width, height = size[0] * SCALE, size[1] * SCALE
    big = Image.new('L', (width, height), 0)
    box = [pad * SCALE, pad * SCALE, width - pad * SCALE - 1, height - pad * SCALE - 1]
    ImageDraw.Draw(big).rounded_rectangle(box, radius=radius * SCALE, fill=255)
    return big


def finish(mask, size):
    image = Image.new('RGBA', size, (255, 255, 255, 0))
    image.putalpha(mask.resize(size, Image.LANCZOS))
    return image


def shape(width, height, radius, pad=0, line=None, glow=None, strength=0.8, solid=True):
    """A white rounded rectangle, inset by pad: filled, or an outline `line` px thick. `glow` is the
    blur radius in px of the soft shadow around the fill (drawn in the pad); solid=False leaves out
    the fill, so only the shadow stays (a card covers the middle)."""
    size = (width, height)
    fill = rrect(size, pad, radius)
    mask = fill
    if line:
        mask = ImageChops.subtract(fill, rrect(size, pad + line, max(radius - line, 0)))
    if glow:
        halo = fill.filter(ImageFilter.GaussianBlur(glow * SCALE)).point(lambda v: round(v * strength))
        mask = ImageChops.lighter(mask, halo) if solid else halo
    return finish(mask, size)


def card_mask(width, height):
    return shape(width, height, CARD_RADIUS)


def fade(width, height):
    """Alpha 255 on the left to 0 on the right, eased: the warm fade, one image for left and bottom."""
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    for x in range(width):
        t = x / (width - 1)
        a = round(255 * (1 - t) ** 1.6)
        for y in range(height):
            image.putpixel((x, y), (255, 255, 255, a))
    return image


def dot(size):
    big = Image.new('L', (size * SCALE, size * SCALE), 0)
    ImageDraw.Draw(big).ellipse([0, 0, size * SCALE - 1, size * SCALE - 1], fill=255)
    return finish(big, (size, size))


def menu_line(width, height):
    """The line under the active menu entry, round ends; border 3,0,3,0 keeps them round."""
    return shape(width, height, height / 2)


def textures():
    r_btn, r_panel = 12, 16
    out = {
        # legacy names: same size and padding as Nightcity's, rounded
        'cut.png': shape(64, 64, CARD_RADIUS, line=3),
        'cut_btn.png': shape(48, 48, r_btn, line=2),
        'cut_btn_fill.png': shape(48, 48, r_btn),
        'cut_btn_fill_pad.png': shape(68, 68, r_btn, pad=GLOW_PAD),
        'cut_btn_glow.png': shape(68, 68, r_btn, pad=GLOW_PAD, glow=4),
        'cut_btn_pad.png': shape(68, 68, r_btn, pad=GLOW_PAD, line=2),
        'cut_fill.png': shape(64, 64, r_panel),
        'cut_fill_glow.png': shape(84, 84, r_panel, pad=GLOW_PAD, glow=4),
        'cut_glow.png': shape(128, 128, CARD_RADIUS, pad=24, glow=9, strength=0.9, solid=False),
        'cut_pad.png': shape(84, 84, r_panel, pad=GLOW_PAD, line=2),
        # new: full pills (border = half the pill height, 27 for a 54 px pill, + pad when padded)
        'pill.png': shape(54, 54, 27),
        'pill_pad.png': shape(74, 74, 27, pad=GLOW_PAD),
        'pill_glow.png': shape(74, 74, 27, pad=GLOW_PAD, glow=4),
        'chip.png': shape(24, 24, 8),  # 5 px at 1280 x 720 is 7.5; border 8
        'dot.png': dot(16),
        'menu_line.png': menu_line(20, 6),
        'warm_fade.png': fade(1024, 4),
    }
    for width, height in CARD_SIZES:
        out['mask_{}x{}.png'.format(width, height)] = card_mask(width, height)
    return out


def main():
    UI.mkdir(parents=True, exist_ok=True)
    for name, image in sorted(textures().items()):
        image.save(UI / name, optimize=True)
        print(UI / name)


if __name__ == '__main__':
    main()
