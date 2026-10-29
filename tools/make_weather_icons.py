"""Weather glyphs of the weather page (MyWeather.xml): white line icons like ui/qm_weather.png,
tinted by the skin. Kodi gives a weather code per day (FanartCode: the file name of the add-on's
icon, 0-47 or na), so each code gets a file media/ui/weather/<code>.png with its glyph.

python tools/make_weather_icons.py
"""
import math
import pathlib

from PIL import Image, ImageChops, ImageDraw

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'media' / 'ui' / 'weather'
SIZE = 128
SCALE = 4  # drawn 4x, scaled down for smooth edges
S = SIZE * SCALE
LINE = 8 * SCALE  # as thick as the lines of qm_weather.png at this size


def canvas():
    return Image.new('L', (S, S), 0)


def outline(shape):
    """The border of `shape(inset)`, LINE wide, inside the shape."""
    return ImageChops.subtract(shape(0), shape(LINE))


def disc(d, x, y, r):
    d.ellipse((x - r, y - r, x + r, y + r), fill=255)


def cloud_shape(dx=0, dy=0):
    """The cloud of qm_weather.png: three circles on a rounded base. inset shrinks every part
    (negative grows), which keeps the outline as round as the cloud."""
    def shape(inset):
        m = canvas()
        d = ImageDraw.Draw(m)
        for x, y, r in ((170, 300, 90), (260, 230, 120), (360, 300, 90)):
            disc(d, dx + x, dy + y, r - inset)
        d.rounded_rectangle((dx + 80 + inset, dy + 270 + inset, dx + 450 - inset, dy + 390 - inset),
                            radius=60 - inset, fill=255)
        return m
    return shape


def moon_shape(cx=256, cy=256, r=150):
    """A crescent: a disc with a disc cut out top right."""
    def shape(inset):
        m = canvas()
        disc(ImageDraw.Draw(m), cx, cy, r - inset)
        cut = canvas()
        disc(ImageDraw.Draw(cut), cx + r * 0.73, cy - r * 0.47, r + inset)
        return ImageChops.subtract(m, cut)
    return shape


def stroke(draw, points):
    """A line with round ends."""
    draw.line(points, fill=255, width=LINE)
    for x, y in (points[0], points[-1]):
        disc(draw, x, y, LINE / 2)


def sun(cx=256, cy=256, r=78, rays=(118, 168)):
    m = canvas()
    d = ImageDraw.Draw(m)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=255, width=LINE)
    for i in range(8):
        a = math.pi / 4 * i
        stroke(d, [(cx + rays[0] * math.cos(a), cy + rays[0] * math.sin(a)),
                   (cx + rays[1] * math.cos(a), cy + rays[1] * math.sin(a))])
    return m


def moon():
    return outline(moon_shape())


def cloud():
    return outline(cloud_shape(0, 10))


def place(mask, k, dx, dy):
    """`mask` scaled by k, its top left corner moved to dx, dy."""
    m = canvas()
    m.paste(mask.resize((round(S * k), round(S * k)), Image.Resampling.LANCZOS), (dx, dy))
    return m


def behind_cloud(back):
    """`back` (a glyph top left) behind a smaller cloud bottom right, a line's width apart."""
    front = cloud_shape()
    cover, line = place(front(-LINE), 0.82, 70, 90), place(outline(front), 0.82, 70, 90)
    return ImageChops.add(ImageChops.subtract(back, cover), line)


def partly():
    return behind_cloud(sun(190, 190, 62, (94, 134)))


def partly_night():
    return behind_cloud(outline(moon_shape(200, 190, 120)))


def with_cloud(below):
    """A cloud up top, `below(draw)` under it."""
    m = outline(cloud_shape(0, -60))
    below(ImageDraw.Draw(m))
    return m


def rain():
    def drops(d):
        for x in (170, 256, 342):
            stroke(d, [(x + 20, 380), (x - 20, 460)])
    return with_cloud(drops)


def snow():
    def flakes(d):
        r = LINE * 0.8
        for x, y in ((170, 410), (256, 410), (342, 410), (213, 475), (299, 475)):
            d.ellipse((x - r, y - r, x + r, y + r), fill=255)
    return with_cloud(flakes)


def storm():
    def bolt(d):
        d.polygon([(280, 340), (200, 430), (256, 430), (226, 500), (316, 400), (262, 400), (292, 340)], fill=255)
    return with_cloud(bolt)


def fog():
    m = canvas()
    d = ImageDraw.Draw(m)
    for y, (a, b) in zip((170, 240, 310, 380), ((100, 412), (140, 440), (80, 380), (150, 420))):
        stroke(d, [(a, y), (b, y)])
    return m


def wind():
    m = canvas()
    d = ImageDraw.Draw(m)
    for y, end, r in ((190, 330, 50), (270, 400, 46), (350, 300, 40)):
        stroke(d, [(80, y), (end, y)])
        # the line curls back over its end: up for the first two, down for the last
        if y < 300:
            d.arc((end - r, y - 2 * r, end + r, y), 180, 90, fill=255, width=LINE)
        else:
            d.arc((end - r, y, end + r, y + 2 * r), 270, 180, fill=255, width=LINE)
    return m


GLYPHS = {
    storm: [0, 1, 2, 3, 4, 37, 38, 39, 45, 47],
    snow: [5, 6, 7, 13, 14, 15, 16, 17, 18, 41, 42, 43, 46],
    rain: [8, 9, 10, 11, 12, 35, 40],
    fog: [19, 20, 21, 22],
    wind: [23, 24],
    cloud: [25, 26, 27, 28, 'na'],
    partly_night: [29],
    partly: [30, 44],
    moon: [31, 33],
    sun: [32, 34, 36],
}


def save(mask, path):
    img = Image.new('RGBA', (S, S), (255, 255, 255, 0))
    img.putalpha(mask)
    img.resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(path, optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for draw, codes in GLYPHS.items():
        mask = draw()
        for code in codes:
            save(mask, OUT / '{}.png'.format(code))


if __name__ == '__main__':
    main()
