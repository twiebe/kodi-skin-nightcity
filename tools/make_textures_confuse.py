#!/usr/bin/env python3
"""Render the white, rounded UI textures of Confuse into skins/confuse/media/ui (coloured in the skin
with colordiffuse). Nightcity's textures in media/ui stay as they are.

Same names as Nightcity's cut-corner textures (cut*.png) with the same sizes and padding, so a
control that still names one gets the rounded twin: radius 12 where the border is 12 or 22 (buttons)
and for cut.png, the card ring (border 16, radius 12 like the masks), 16 where it is 16 or 26
(panels). The check boxes and the selected spin signs have rounded twins too. The pill, chip, dot,
card ring and menu line are new, and fade_r.png is the mask of the fanart (FanartBackdrop).
Sizes are 1080 px grid pixels, drawn 1:1: a mask of a 290 x 435 card is shown at 290 x 435, so its
radius is the radius on screen. The design gives cards 8 px at 1280 x 720, so 12 px here (x 1.5).

python tools/make_textures_confuse.py
"""
import math
import pathlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

UI = pathlib.Path(__file__).resolve().parents[1] / 'skins' / 'confuse' / 'media' / 'ui'
SYNE = pathlib.Path(__file__).resolve().parent / 'fonts' / 'Syne[wght].ttf'
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


def fanart_mask(width, height):
    """What stays of the fanart at each place, so a white picture over the base colour looks like the
    draft's two fades (Glut, Main) over it, without a second full screen layer: to the left .94 at
    the edge, .76 at 48 % of the width, .24 at the right edge; up from the bottom .97 to 0 at 58 %
    of the height. Small, since Kodi scales it up smoothly to the full screen."""
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    for y in range(height):
        up = 1 - y / (height - 1)
        bottom = 0.97 * max(0, 1 - up / 0.58)
        for x in range(width):
            across = x / (width - 1)
            left = 0.94 - 0.18 * across / 0.48 if across < 0.48 else 0.76 - 0.52 * (across - 0.48) / 0.52
            image.putpixel((x, y), (255, 255, 255, round(255 * (1 - left) * (1 - bottom))))
    return image


def dot_shade(size):
    """A soft round spot under the dot of an unwatched title."""
    big = Image.new('L', (size * SCALE, size * SCALE), 0)
    inset = size * SCALE // 4
    ImageDraw.Draw(big).ellipse([inset, inset, size * SCALE - inset - 1, size * SCALE - inset - 1], fill=255)
    return finish(big.filter(ImageFilter.GaussianBlur(3 * SCALE)), (size, size))


def info_fade(width, height):
    """Over the fanart mask, what brings the fanart to the Info draft (.46 instead of .58 of the
    picture and its fade to the left, .95, .8 at the middle, .6 at the right edge): one direction, as
    the fade from the bottom is the same in both."""
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    for x in range(width):
        across = x / (width - 1)
        left = 0.94 - 0.18 * across / 0.48 if across < 0.48 else 0.76 - 0.52 * (across - 0.48) / 0.52
        info = 0.95 - 0.15 * across / 0.5 if across < 0.5 else 0.8 - 0.2 * (across - 0.5) / 0.5
        alpha = 1 - (0.46 / 0.58) * (1 - info) / (1 - left)
        for y in range(height):
            image.putpixel((x, y), (255, 255, 255, round(255 * alpha)))
    return image


def player_fade(height, stops):
    """A fade up and down in a 4 px wide image, between (place, alpha) stops, both from 0 to 1."""
    image = Image.new('RGBA', (4, height), (255, 255, 255, 0))
    for y in range(height):
        place = y / (height - 1)
        for (a, va), (b, vb) in zip(stops, stops[1:]):
            if a <= place <= b:
                alpha = va + (vb - va) * (place - a) / (b - a)
                break
        for x in range(4):
            image.putpixel((x, y), (255, 255, 255, round(255 * alpha)))
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


def line_texture(width, height, thick, bottom, inset):
    """A line in a texture as high as its button, which Kodi stretches over the whole button: the
    round ends stay with a border of inset + thick / 2 (the look's includes), `bottom` px clear below."""
    big = Image.new('L', (width * SCALE, height * SCALE), 0)
    top = height - bottom - thick
    ImageDraw.Draw(big).rounded_rectangle(
        [inset * SCALE, top * SCALE, (width - inset) * SCALE - 1, (height - bottom) * SCALE - 1],
        radius=thick / 2 * SCALE, fill=255)
    return finish(big, (width, height))


def line_glow(width, height, thick, bottom, inset, blur, boost=2.2):
    """The same line with the focus: the shape stays, a soft glow comes around it. The border of the
    look has to hold the blur past the round ends too, or Kodi stretches a part that still changes."""
    big = Image.new('L', (width * SCALE, height * SCALE), 0)
    top = height - bottom - thick
    ImageDraw.Draw(big).rounded_rectangle(
        [inset * SCALE, top * SCALE, (width - inset) * SCALE - 1, (height - bottom) * SCALE - 1],
        radius=thick / 2 * SCALE, fill=255)
    halo = big.filter(ImageFilter.GaussianBlur(blur * SCALE)).point(lambda v: min(255, round(v * boost)))
    return finish(ImageChops.lighter(big, halo), (width, height))


def card_halo(size, pad, radius):
    """The glow of a focused card, in `pad` px around it: strong against the card, gone at the edge
    of the texture, since a list cuts what lies past it. The card covers the middle."""
    fill = rrect((size, size), pad, radius)
    near = fill.filter(ImageFilter.GaussianBlur(5 * SCALE)).point(lambda v: min(255, round(v * 2)))
    far = fill.filter(ImageFilter.GaussianBlur(10 * SCALE)).point(lambda v: min(255, round(v * 1.8)))
    return finish(ImageChops.lighter(near, far), (size, size))


def wordmark(text, height=190, baseline=146):
    """A part of the name, in the bold of Syne, the one place that font is used: as a texture it needs
    no font file in the skin. Both parts have one height and baseline, and side by side they read as
    one word. tools/fonts holds the font and its licence."""
    font = ImageFont.truetype(str(SYNE), 144 * SCALE)
    font.set_variation_by_axes([800])
    width = math.ceil(font.getlength(text) / SCALE)
    big = Image.new('L', (width * SCALE, height * SCALE), 0)
    ImageDraw.Draw(big).text((0, baseline * SCALE), text, font=font, fill=255, anchor='ls')
    return finish(big, (width, height))


def soft_dot(size, core, blur, boost=1.0):
    """A round spot: a solid core of `core` px, the rest a glow that ends inside the texture."""
    s = size * SCALE
    big = Image.new('L', (s, s), 0)
    inset = (size - core) / 2 * SCALE
    ImageDraw.Draw(big).ellipse([inset, inset, s - inset - 1, s - inset - 1], fill=255)
    halo = big.filter(ImageFilter.GaussianBlur(blur * SCALE)).point(lambda v: min(255, round(v * boost)))
    return finish(ImageChops.lighter(big, halo), (size, size))


def trail(width, height, start=0.25):
    """What a spark has burned: faint far behind it, whole at the spark."""
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    for x in range(width):
        value = round(255 * (start + (1 - start) * x / (width - 1)))
        for y in range(height):
            image.putpixel((x, y), (255, 255, 255, value))
    return image


def ember_glow(width, height):
    """The soft light around the fuse on the loading page. Small, Kodi scales it up smoothly."""
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    for y in range(height):
        for x in range(width):
            across, up = (x / (width - 1) - 0.5) * 2, (y / (height - 1) - 0.5) * 2
            value = max(0.0, 1 - math.sqrt(across * across + up * up))
            image.putpixel((x, y), (255, 255, 255, round(255 * value * value)))
    return image


def textures():
    r_btn, r_panel = 12, 16
    out = {
        # legacy names: same size and padding as Nightcity's, rounded
        'cut.png': shape(64, 64, CARD_RADIUS, line=3),
        'cut_btn.png': shape(48, 48, r_btn, line=2),
        'card_ring.png': shape(64, 64, CARD_RADIUS, line=4),  # 4.5 px on a card at 113.5 %
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
        'pill_menu.png': shape(64, 64, 22, pad=GLOW_PAD),  # the menu icon with the focus, 44 px of pill; border 32
        'chip.png': shape(24, 24, 8),  # 5 px at 1280 x 720 is 7.5; border 8
        'dot.png': dot(16),
        'dot_shade.png': dot_shade(28),
        # 4.5 px, the menu entry is 64 px, 12 px clear below for the glow; border 19,0,19,0 holds the
        # line's clear and round ends, 30,0,30,0 the glow of menu_glow.png as well
        'menu_line.png': line_texture(64, 64, 4.5, 12, 14),
        'menu_glow.png': line_glow(64, 64, 4.5, 12, 14, 5),
        # 4.5 px on the line of Nightcity's tab_line.png; border 11,0,11,0 holds the clear ends and
        # the round ends of the line, or Kodi stretches those into a lens
        'tab_line.png': line_texture(24, 44, 4.5, 2, 8),
        # a tab with the focus: the same line glows, upwards as a tab has 2 px below it; border 18,0,18,0
        'tab_glow.png': line_glow(64, 44, 4.5, 2, 8, 3),
        'card_halo.png': card_halo(128, 24, CARD_RADIUS),
        # the loading page: the name, the fuse and its spark
        'word_con.png': wordmark('con'),
        'word_fuse.png': wordmark('fuse'),
        'fuse_trail.png': trail(256, 4),
        'spark_halo.png': ember_glow(64, 64),
        'spark_core.png': dot(16),
        'ember_glow.png': ember_glow(256, 128),
        'fade_r.png': fanart_mask(384, 216),  # 16:9, stretched over the screen
        'info_fade.png': info_fade(256, 4),
        # the player's scrim, in the colour scrim (.96): y 340 to 1080 and 0 to 220 of the screen.
        # The draft, stronger at the top of the text block, which starts at 440
        'fade_b.png': player_fade(256, [(0, 0), (0.135, 0.7), (0.445, 0.875), (1, 1)]),
        'fade_t.png': player_fade(256, [(0, 0.58), (1, 0)]),
        'seek_head.png': soft_dot(16, 8, 2.2),  # the spark at the head of the seek line, on its 16 px high track
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
