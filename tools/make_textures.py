#!/usr/bin/env python3
"""Render the white UI textures in media/ui (coloured in the skin with colordiffuse).

python tools/make_textures.py
"""
import math
import pathlib

from PIL import Image, ImageDraw, ImageFilter

UI = pathlib.Path(__file__).resolve().parents[1] / 'media' / 'ui'
SCALE = 8


def fade(width, height, reverse=False):
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    for x in range(width):
        a = round(255 * x / (width - 1))
        for y in range(height):
            image.putpixel((width - 1 - x if reverse else x, y), (255, 255, 255, a))
    return image


def cut_points(width, height, cut, corners):
    w, h = width - 1, height - 1
    points = [(0, 0)]
    points += [(w - cut, 0), (w, cut)] if 'tr' in corners else [(w, 0)]
    points += [(w, h)]
    points += [(cut, h), (0, h - cut)] if 'bl' in corners else [(0, h)]
    return points


def cut(size, corner, line=None, corners=('tr', 'bl'), height=None):
    """A white rectangle with 45 degree cut corners (top right, bottom left), outline or filled.
    `height` makes it non-square (masks sized like a poster or a thumb)."""
    height = height or size
    big = Image.new('L', (size * SCALE, height * SCALE), 0)
    draw = ImageDraw.Draw(big)
    points = cut_points(size * SCALE, height * SCALE, corner * SCALE, corners)
    if line:
        draw.polygon(points, outline=255, width=line * SCALE)
    else:
        draw.polygon(points, fill=255)
    image = Image.new('RGBA', (size, height), (255, 255, 255, 0))
    image.putalpha(big.resize((size, height), Image.LANCZOS))
    return image


def dogear(size):
    """Triangle in the bottom right corner of a card (the unwatched mark), legs as long as the
    frame's cut."""
    big = Image.new('L', (size * SCALE, size * SCALE), 0)
    s = size * SCALE
    ImageDraw.Draw(big).polygon([(s, 0), (s, s), (0, s)], fill=255)
    image = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    image.putalpha(big.resize((size, size), Image.LANCZOS))
    return image

def check(size, corner):
    """The toggle box of a setting that is on: a cut outline with a check mark inside."""
    image = cut(size, corner, line=2, corners=('tr',))
    big = Image.new('L', (size * SCALE, size * SCALE), 0)
    s = size * SCALE
    ImageDraw.Draw(big).line([(0.24 * s, 0.52 * s), (0.42 * s, 0.70 * s), (0.76 * s, 0.30 * s)],
                             fill=255, width=3 * SCALE, joint='curve')
    mark = big.resize((size, size), Image.LANCZOS)
    alpha = Image.composite(mark, image.getchannel('A'), mark)
    image.putalpha(alpha)
    return image


def sign_mask(size, plus):
    big = Image.new('L', (size * SCALE, size * SCALE), 0)
    s = size * SCALE
    draw = ImageDraw.Draw(big)
    draw.line([(0.28 * s, 0.5 * s), (0.72 * s, 0.5 * s)], fill=255, width=3 * SCALE)
    if plus:
        draw.line([(0.5 * s, 0.28 * s), (0.5 * s, 0.72 * s)], fill=255, width=3 * SCALE)
    return big.resize((size, size), Image.LANCZOS)


def sign(size, plus):
    """The - and + of a setting with a value range (spin control): a white sign with a dark rim.
    Kodi draws the sign that is not selected with this texture on the dark row and on the cyan
    focus row alike: the sign shows on the dark one, the rim on the cyan one."""
    mark = sign_mask(size, plus)
    rim = Image.new('RGBA', (size, size), (5, 8, 12, 0))
    rim.putalpha(mark.filter(ImageFilter.MaxFilter(5)))
    white = Image.new('RGBA', (size, size), (255, 255, 255, 255))
    white.putalpha(mark)
    return Image.alpha_composite(rim, white)


def sign_focus(size, plus, pad=0):
    """The selected - or +: a filled box with the sign cut out; `pad` px of air around it keeps
    it off the other sign (Kodi puts both side by side)."""
    box = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    box.paste(cut(size - 2 * pad, 6, corners=('tr',)), (pad, pad))
    alpha = Image.composite(Image.new('L', (size, size), 0), box.getchannel('A'), sign_mask(size, plus))
    box.putalpha(alpha)
    return box


def cut_glow(size, corner, pad, blur):
    """Soft glow around a cut shape: the shape inset by `pad`, blurred by `blur` px."""
    mask = Image.new('L', (size, size), 0)
    inner = cut(size - 2 * pad, corner).getchannel('A')
    mask.paste(inner, (pad, pad))
    mask = mask.filter(ImageFilter.GaussianBlur(blur))
    image = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    image.putalpha(mask)
    return image


def radial_glow(width, height, cx, cy, radius):
    """White radial glow (alpha falls off from the centre), rendered small and scaled up."""
    w, h = width // 10, height // 10
    small = Image.new('L', (w, h), 0)
    for x in range(w):
        for y in range(h):
            d = (((x - cx * w) / (radius * w)) ** 2 + ((y - cy * h) / (radius * w)) ** 2) ** 0.5
            small.putpixel((x, y), round(255 * max(0.0, 1 - d) ** 2))
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    image.putalpha(small.resize((width, height), Image.BICUBIC))
    return image


# sizes of the CutCard artwork: poster, big poster, hero poster, episode still, cast photo
CARD_SIZES = [(200, 300), (280, 420), (360, 540), (320, 180), (160, 220), (200, 200), (280, 280), (360, 360)]


def hamburger(size, bar=5, gap=8):
    """The quick menu icon: three bars of the same length."""
    img = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    left, right = size * 10 // 64, size - size * 10 // 64 - 1
    top = (size - 3 * bar - 2 * gap) // 2
    for n in range(3):
        y = top + n * (bar + gap)
        draw.rectangle((left, y, right, y + bar - 1), fill=(255, 255, 255, 255))
    return img


def chevron(width, height, stroke):
    """The arrow after the spotlight buttons: a narrow chevron pointing right, as tall as the
    buttons, its arms `stroke` px wide measured across."""
    w, h = width * SCALE, height * SCALE
    big = Image.new('L', (w, h), 0)
    t = stroke * SCALE
    ImageDraw.Draw(big).polygon([(0, 0), (t, 0), (w, h / 2), (t, h), (0, h), (w - t, h / 2)], fill=255)
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    image.putalpha(big.resize((width, height), Image.LANCZOS))
    return image


def notification_icon(size, kind):
    """Kodi's icons of a notification without a picture of its own (DefaultIcon<kind>.png): thin
    outlines in the classic shapes, a circle around an i (info), a triangle around a ! (warning),
    an octagon around an x (error). No cut box: the toast's frame has the cut corner."""
    s = size * SCALE
    big = Image.new('L', (s, s), 0)
    draw = ImageDraw.Draw(big)
    line, stroke = round(0.035 * s), 0.075 * s
    c = s / 2

    def dot(x, y, r):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=255)

    def bar(x0, y0, x1, y1):
        draw.line([(x0, y0), (x1, y1)], fill=255, width=round(stroke))
        dot(x0, y0, stroke / 2)
        dot(x1, y1, stroke / 2)

    if kind == 'info':
        r = 0.46 * s
        draw.ellipse((c - r, c - r, c + r, c + r), outline=255, width=line)
        dot(c, c - 0.21 * s, stroke * 0.65)
        bar(c, c - 0.06 * s, c, c + 0.21 * s)
    elif kind == 'warning':
        r = 0.5 * s
        corners = [(c, c - 0.92 * r), (c + 0.98 * r, c + 0.78 * r), (c - 0.98 * r, c + 0.78 * r)]
        draw.line(corners + corners[:2], fill=255, width=line, joint='curve')
        top = c + 0.08 * s
        bar(c, top - 0.18 * s, c, top + 0.05 * s)
        dot(c, top + 0.18 * s, stroke * 0.65)
    else:
        r = 0.47 * s
        corners = [(c + r * math.cos(math.radians(22.5 + 45 * k)), c + r * math.sin(math.radians(22.5 + 45 * k)))
                   for k in range(8)]
        draw.line(corners + corners[:2], fill=255, width=line, joint='curve')
        a = 0.165 * s
        bar(c - a, c - a, c + a, c + a)
        bar(c - a, c + a, c + a, c - a)
    image = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    image.putalpha(big.resize((size, size), Image.LANCZOS))
    return image


def main():
    cut(64, 14, line=2).save(UI / 'cut.png')
    cut(64, 14).save(UI / 'cut_fill.png')
    cut(48, 10, line=2, corners=('tr',)).save(UI / 'cut_btn.png')
    cut(48, 10, corners=('tr',)).save(UI / 'cut_btn_fill.png')
    cut_glow(128, 14, 24, 10).save(UI / 'cut_glow.png')
    radial_glow(1920, 1080, 0.75, 0.15, 0.6).save(UI / 'petrol_glow.png')
    # diffuse masks that cut the corners of artwork, one per card size: drawn 1:1 they keep the
    # frame's 14 px cut (a stretched mask would cut more or less than the frame)
    for width, height in CARD_SIZES:
        cut(width, 14, height=height).save(UI / 'mask_{}x{}.png'.format(width, height))
    dogear(14).save(UI / 'dogear.png')
    cut(32, 8, line=2, corners=('tr',)).save(UI / 'check_off.png')
    check(32, 8).save(UI / 'check_on.png')
    sign(34, False).save(UI / 'spin_minus.png')
    sign(34, True).save(UI / 'spin_plus.png')
    sign_focus(34, False, pad=3).save(UI / 'spin_minus_focus.png')
    sign_focus(34, True, pad=3).save(UI / 'spin_plus_focus.png')
    fade(256, 4).save(UI / 'fade_r.png')
    fade(256, 4).transpose(Image.Transpose.ROTATE_270).save(UI / 'fade_b.png')
    fade(256, 4, reverse=True).transpose(Image.Transpose.ROTATE_270).save(UI / 'fade_t.png')
    # chapter mark on the seek track's 16 rows, 1:1: 4 px over and under the 4 px line (rows 6
    # to 9), clear on the line itself, where its alpha would stack on the line's
    tick = Image.new('RGBA', (2, 16), (255, 255, 255, 0))
    tick.paste((255, 255, 255, 255), (0, 2, 2, 6))
    tick.paste((255, 255, 255, 255), (0, 10, 2, 14))
    tick.save(UI / 'tick.png')
    hamburger(64).save(UI / 'qm_menu.png')
    chevron(13, 30, 4).save(UI / 'spot_more.png')
    # Kodi's names, looked up in media/ itself: the notification tells a warning by its icon
    for kind in ('Info', 'Warning', 'Error'):
        notification_icon(80, kind.lower()).save(UI.parent / 'DefaultIcon{}.png'.format(kind))
    # underline of tab entries: clear ends of 8 px, drawn unscaled with border="8,0,8,0", so the
    # line leaves out most of the button's padding and fits the text
    line = Image.new('RGBA', (20, 44), (255, 255, 255, 0))
    line.paste((255, 255, 255, 255), (8, 40, 12, 42))
    line.save(UI / 'tab_line.png')
    # seek head on the seek track's 16 rows: 6 px over the line, the line, 6 px under it
    head = Image.new('RGBA', (4, 16), (255, 255, 255, 255))
    head.save(UI / 'seek_head.png')
    # invisible track of the seek head: Kodi scales a progress control's end texture by
    # control width / track texture width, so the track is as wide as the seek line
    Image.new('RGBA', (1792, 16), (255, 255, 255, 0)).save(UI / 'seek_track.png')
    # invisible track of the played part: without one Kodi draws the fill at its texture's own
    # height and moves it down by half of it; white.png's size, so the fill is scaled like it
    Image.new('RGBA', (8, 8), (255, 255, 255, 0)).save(UI / 'clear.png')


if __name__ == '__main__':
    main()
