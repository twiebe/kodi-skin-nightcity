#!/usr/bin/env python3
"""Render the white, rounded UI textures of Confuse into skins/confuse/media/ui (coloured in the skin
with colordiffuse). Nightcity's textures in media/ui stay as they are.

Same names as Nightcity's cut-corner textures (cut*.png) with the same sizes and padding, so a
control that still names one gets the rounded twin: radius 12 where the border is 12 or 22 (buttons)
and for cut.png, the card ring (border 16, radius 12 like the masks), 16 where it is 16 or 26
(panels). The check boxes and the selected spin signs have rounded twins too. The pill, chip, dot,
menu line and warm fade are new.
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
    """The warm fade, one image for the left edge and the bottom edge: opaque at the bottom left,
    clear at the top right. Each edge fades eased across the screen and the two combine like layers
    (1 - (1 - left) * (1 - bottom)). Small, since Kodi scales it up smoothly to the full screen."""
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    for y in range(height):
        bottom = (y / (height - 1)) ** 1.6
        for x in range(width):
            left = (1 - x / (width - 1)) ** 1.6
            image.putpixel((x, y), (255, 255, 255, round(255 * (1 - (1 - left) * (1 - bottom)))))
    return image


def check(size, radius, on):
    """The box of a toggle: an outline with a check mark inside when on, 10 px clear to the right
    (the row is padded for its glow, Kodi puts the box where it was)."""
    box = shape(size, size, radius, line=2)
    if on:
        big = Image.new('L', (size * SCALE, size * SCALE), 0)
        s = size * SCALE
        ImageDraw.Draw(big).line([(0.24 * s, 0.52 * s), (0.42 * s, 0.70 * s), (0.76 * s, 0.30 * s)],
                                 fill=255, width=3 * SCALE, joint='curve')
        mark = big.resize((size, size), Image.LANCZOS)
        box.putalpha(Image.composite(mark, box.getchannel('A'), mark))
    wide = Image.new('RGBA', (size + GLOW_PAD, size), (255, 255, 255, 0))
    wide.paste(box, (0, 0))
    return wide


def sign_focus(size, plus, pad=3, radius=6):
    """The selected - or + of a spin control: a filled rounded box with the sign cut out."""
    big = Image.new('L', (size * SCALE, size * SCALE), 0)
    s = size * SCALE
    draw = ImageDraw.Draw(big)
    draw.line([(0.28 * s, 0.5 * s), (0.72 * s, 0.5 * s)], fill=255, width=3 * SCALE)
    if plus:
        draw.line([(0.5 * s, 0.28 * s), (0.5 * s, 0.72 * s)], fill=255, width=3 * SCALE)
    box = shape(size, size, radius, pad=pad)
    box.putalpha(Image.composite(Image.new('L', (size, size), 0), box.getchannel('A'), big.resize((size, size), Image.LANCZOS)))
    return box


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
        'warm_fade.png': fade(384, 216),  # 16:9, stretched over the screen
        # twins of the check boxes and the selected spin signs, which Nightcity cuts at a corner
        'check_off_pad.png': check(32, 8, on=False),
        'check_on_pad.png': check(32, 8, on=True),
        'spin_minus_focus.png': sign_focus(34, plus=False),
        'spin_plus_focus.png': sign_focus(34, plus=True),
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
