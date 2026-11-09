#!/usr/bin/env python3
"""Render the white UI textures in media/ui (coloured in the skin with colordiffuse).

python tools/make_textures.py
"""
import math
import pathlib

from PIL import Image, ImageChops, ImageDraw, ImageFilter

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
    """Triangle in the bottom right corner of a card (the unwatched mark)."""
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


def cut_glow(size, corner, pad, blur, strength=1.0):
    """Soft glow around a cut shape: the shape inset by `pad`, blurred by `blur` px, `strength`
    of full alpha (the skin colours it with the full focus colour)."""
    mask = Image.new('L', (size, size), 0)
    inner = cut(size - 2 * pad, corner).getchannel('A')
    mask.paste(inner, (pad, pad))
    mask = mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda a: round(a * strength))
    image = Image.new('RGBA', (size, size), (255, 255, 255, 0))
    image.putalpha(mask)
    return image


# px around a focused button for its glow (fill_glow)
GLOW_PAD = 10


def padded(image, pad):
    """`image` with `pad` px of clear margin on every side."""
    out = Image.new('RGBA', (image.width + 2 * pad, image.height + 2 * pad), (255, 255, 255, 0))
    out.paste(image, (pad, pad))
    return out


def fill_glow(size, corner, pad, corners=('tr', 'bl'), strength=0.8, blur=4):
    """A cut fill inset by `pad` with a soft halo in the margin, the glow of a focused button.
    Kodi draws a button's textures only inside the button, so a button that glows is `pad` px
    larger on each side and its texture border `pad` px wider. One colordiffuse colours fill
    and halo: the halo has `strength` of the fill's alpha, a little stronger than the cards' glow."""
    fill = padded(cut(size, corner, corners=corners), pad)
    alpha = fill.getchannel('A')
    halo = alpha.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(blur))
    halo = halo.point(lambda a: round(a * strength))
    fill.putalpha(ImageChops.lighter(alpha, halo))
    return fill


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
CARD_SIZES = [(200, 300), (240, 360), (290, 435), (360, 540), (320, 180), (160, 220), (200, 200), (280, 280), (360, 360)]


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


# --- quick menu power icons (qm_*): white line drawings, one stroke, drawn SCALE times and
# scaled down; 64 px, the tile shows them at 40

ICON = 64
ICON_STROKE = 3.6  # px at 64 (2.25 px as the tile shows it, 40 px)


def _icon_canvas():
    big = Image.new('L', (ICON * SCALE, ICON * SCALE), 0)
    return big, ImageDraw.Draw(big)


def _icon_done(big):
    image = Image.new('RGBA', (ICON, ICON), (255, 255, 255, 0))
    image.putalpha(big.resize((ICON, ICON), Image.LANCZOS))
    return image


def _round_line(draw, a, b, w):
    draw.line([a, b], fill=255, width=w)
    for x, y in (a, b):
        draw.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=255)


def _arc(draw, c, r, start, end, w, cy=None):
    """A round-capped arc from START to END degrees (clockwise, 0 = right) round C (and CY)."""
    cy = c if cy is None else cy
    draw.arc([c - r, cy - r, c + r, cy + r], start, end, fill=255, width=w)
    for angle in (start, end):
        a = math.radians(angle)
        x, y = c + (r - w / 2) * math.cos(a), cy + (r - w / 2) * math.sin(a)
        draw.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=255)


def _head(draw, c, r, angle, w, clockwise=True, cy=None):
    """An arrow head on the arc of radius R at ANGLE, pointing along it."""
    cy = c if cy is None else cy
    a = math.radians(angle)
    rm = r - w / 2
    px, py = c + rm * math.cos(a), cy + rm * math.sin(a)
    sign = 1 if clockwise else -1
    tx, ty = -math.sin(a) * sign, math.cos(a) * sign  # along the arc
    nx, ny = math.cos(a), math.sin(a)                 # out of the circle
    length, half = 3.4 * w, 2.0 * w
    tip = (px + tx * length * 0.75, py + ty * length * 0.75)
    back = (px - tx * length * 0.25, py - ty * length * 0.25)
    draw.polygon([tip, (back[0] + nx * half, back[1] + ny * half), (back[0] - nx * half, back[1] - ny * half)], fill=255)


def icon_power():
    """The power symbol: a ring open at the top, a bar down into it. The bar reaches above the
    ring: the ring sits 2 px low, so the whole sign is centred."""
    big, d = _icon_canvas()
    s, w = SCALE, round(ICON_STROKE * SCALE)
    c, r = ICON * s / 2, 22 * s
    _arc(d, c, r, -50, 230, w, cy=c + 2 * s)
    _round_line(d, (c, c - r - 1 * s), (c, c), w)
    return _icon_done(big)


def icon_reboot():
    """The power symbol whose ring ends in an arrow: off and on again."""
    big, d = _icon_canvas()
    s, w = SCALE, round(ICON_STROKE * SCALE)
    c, r = ICON * s / 2, 22 * s
    _arc(d, c, r, -50, 205, w, cy=c + 2 * s)
    _head(d, c, r, 212, w, cy=c + 2 * s)
    _round_line(d, (c, c - r - 1 * s), (c, c), w)
    return _icon_done(big)


def icon_suspend():
    """Asleep: the outline of a crescent moon, a disc less one moved up and right."""
    s, w = SCALE, round(ICON_STROKE * SCALE)
    n, c = ICON * s, ICON * s / 2
    moon = Image.new('L', (n, n), 0)
    d = ImageDraw.Draw(moon)
    r = 22 * s
    d.ellipse([c - r, c - r, c + r, c + r], fill=255)
    cx, cy, cr = c + 11 * s, c - 9 * s, 18 * s
    d.ellipse([cx - cr, cy - cr, cx + cr, cy + cr], fill=0)
    # the ring: the moon less the moon shrunk by the stroke (an odd filter size)
    inner = moon.filter(ImageFilter.MinFilter(2 * (w // 2) + 1))
    big = ImageChops.subtract(moon, inner)
    # centred by what is drawn
    left, top, right, bottom = big.getbbox()
    shifted = Image.new('L', (n, n), 0)
    shifted.paste(big.crop((left, top, right, bottom)), ((n - (right - left)) // 2, (n - (bottom - top)) // 2))
    return _icon_done(shifted)


def icon_restart_app():
    """Two arrows chasing round a circle: start again."""
    big, d = _icon_canvas()
    s, w = SCALE, round(ICON_STROKE * SCALE)
    c, r = ICON * s / 2, 21 * s
    for start in (200, 20):
        _arc(d, c, r, start, start + 128, w)
        _head(d, c, r, start + 136, w)
    return _icon_done(big)


def icon_quit_app():
    """Leaving: a door frame open on the right, an arrow out of it."""
    big, d = _icon_canvas()
    s, w = SCALE, round(ICON_STROKE * SCALE)
    left, top, bottom, right = 12 * s, 10 * s, 54 * s, 34 * s
    # the frame: top and bottom stop short of the arrow's way out
    _round_line(d, (right, top), (left, top), w)
    _round_line(d, (left, top), (left, bottom), w)
    _round_line(d, (left, bottom), (right, bottom), w)
    _round_line(d, (right, top), (right, 22 * s), w)
    _round_line(d, (right, bottom), (right, 42 * s), w)
    y = 32 * s
    _round_line(d, (24 * s, y), (52 * s, y), w)
    head = 9 * s
    _round_line(d, (54 * s - head, y - head), (54 * s, y), w)
    _round_line(d, (54 * s - head, y + head), (54 * s, y), w)
    return _icon_done(big)


# --- video calibration (SettingsScreenCalibration.xml): white, coloured in the skin

def _supersampled(width, height, draw_fn):
    big = Image.new('L', (width * SCALE, height * SCALE), 0)
    draw_fn(ImageDraw.Draw(big), SCALE)
    image = Image.new('RGBA', (width, height), (255, 255, 255, 0))
    image.putalpha(big.resize((width, height), Image.LANCZOS))
    return image


def cal_corner(size=128, arm=88, stroke=6, flip=False):
    """A corner bracket in the top left (or, flipped, the bottom right) of the screen."""
    def draw(d, s):
        w, a = stroke * s, arm * s
        d.rectangle([0, 0, a, w], fill=255)
        d.rectangle([0, 0, w, a], fill=255)
    image = _supersampled(size, size, draw)
    return image.rotate(180) if flip else image


def cal_ratio(size=500, stroke=6):
    """The pixel ratio target: a square with a thin cross; right when it looks square (Kodi's help
    asks for a square)."""
    def draw(d, s):
        w, n = stroke * s, size * s
        d.rectangle([0, 0, n - 1, n - 1], outline=255, width=w)
        t, c = 2 * s, n // 2
        d.rectangle([c - t // 2, n // 4, c + t // 2, 3 * n // 4], fill=255)
        d.rectangle([n // 4, c - t // 2, 3 * n // 4, c + t // 2], fill=255)
    return _supersampled(size, size, draw)


def cal_sub(width=380, height=90, bar=8, margin=40):
    """The subtitle position: a bar with end ticks, 40 px clear above and below (Kodi's)."""
    def draw(d, s):
        top, bottom = margin * s, (height - margin) * s
        mid = (top + bottom) // 2
        d.rectangle([0, mid - bar * s // 2, width * s - 1, mid + bar * s // 2], fill=255)
        # the ticks stop a pixel short of the clear margins (the scaling blurs a pixel out)
        d.rectangle([0, top + s, 4 * s, bottom - s - 1], fill=255)
        d.rectangle([width * s - 4 * s - 1, top + s, width * s - 1, bottom - s - 1], fill=255)
    return _supersampled(width, height, draw)


def cal_reset(size=100):
    """Back to the defaults: the restart arrows of the quick menu, larger."""
    return icon_restart_app().resize((size, size), Image.LANCZOS)


def main():
    cut(64, 14, line=2).save(UI / 'cut.png')
    icon_power().save(UI / 'qm_power.png')
    icon_reboot().save(UI / 'qm_reboot.png')
    icon_suspend().save(UI / 'qm_standby.png')
    icon_restart_app().save(UI / 'qm_restartapp.png')
    icon_quit_app().save(UI / 'qm_quit.png')
    cal_corner().save(UI / 'cal_tl.png')
    cal_corner(flip=True).save(UI / 'cal_br.png')
    cal_ratio().save(UI / 'cal_ratio.png')
    cal_sub().save(UI / 'cal_sub.png')
    cal_reset().save(UI / 'cal_reset.png')
    cut(64, 14).save(UI / 'cut_fill.png')
    cut(48, 10, line=2, corners=('tr',)).save(UI / 'cut_btn.png')
    cut(48, 10, corners=('tr',)).save(UI / 'cut_btn_fill.png')
    # the focused card's glow, as strong next to the card as a button's (fill_glow)
    cut_glow(128, 14, 24, 10, strength=0.9).save(UI / 'cut_glow.png')
    # the focused fills with their glow, and the outlines with the same margin, for buttons
    # that grow by GLOW_PAD on each side (border 12 + 10, 16 + 10)
    fill_glow(48, 10, GLOW_PAD, corners=('tr',)).save(UI / 'cut_btn_glow.png')
    padded(cut(48, 10, line=2, corners=('tr',)), GLOW_PAD).save(UI / 'cut_btn_pad.png')
    fill_glow(64, 14, GLOW_PAD).save(UI / 'cut_fill_glow.png')
    padded(cut(64, 14, line=2), GLOW_PAD).save(UI / 'cut_pad.png')
    # a fill that does not glow (the shown settings category) in a padded control
    padded(cut(48, 10, corners=('tr',)), GLOW_PAD).save(UI / 'cut_btn_fill_pad.png')
    # separator of the padded settings rows: the 1 px line in the middle of GLOW_PAD px above
    # and below
    sep = Image.new('RGBA', (4, 2 * GLOW_PAD + 1), (255, 255, 255, 0))
    sep.paste((255, 255, 255, 255), (0, GLOW_PAD, 4, GLOW_PAD + 1))
    sep.save(UI / 'line_pad.png')
    radial_glow(1920, 1080, 0.75, 0.15, 0.6).save(UI / 'petrol_glow.png')
    # diffuse masks that cut the corners of artwork, one per card size: drawn 1:1 they keep the
    # frame's 14 px cut (a stretched mask would cut more or less than the frame)
    for width, height in CARD_SIZES:
        cut(width, 14, height=height).save(UI / 'mask_{}x{}.png'.format(width, height))
    dogear(22).save(UI / 'dogear.png')
    # check boxes of a settings row, which is padded for its glow: Kodi puts the box 8 px from
    # the control's right edge, GLOW_PAD further out; clear on the right, the box stays put
    for name, box in (('check_off', cut(32, 8, line=2, corners=('tr',))), ('check_on', check(32, 8))):
        wide = Image.new('RGBA', (box.width + GLOW_PAD, box.height), (255, 255, 255, 0))
        wide.paste(box, (0, 0))
        wide.save(UI / '{}_pad.png'.format(name))
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
