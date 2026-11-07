"""Confuse's glitches: now and then something stumbles for a blink. Each is rare, runs only while
LookGlitch holds (the skin setting cf.glitch.off, off by default, switches them off), and the
animations of one type that make a twitch add up to nothing in the end. Nightcity has none."""
import importlib.util
import re

from PIL import Image, ImageChops

from conftest import ROOT, parse

OVERLAY = ROOT / 'skins' / 'confuse'
UI = OVERLAY / 'media' / 'ui'


def textures_module():
    spec = importlib.util.spec_from_file_location('make_textures_confuse', ROOT / 'tools' / 'make_textures_confuse.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def look(root=OVERLAY):
    return parse(root / '1080i' / 'Includes_Look.xml')


def include(name, root=OVERLAY):
    return next(i for i in look(root).findall('include') if i.get('name') == name)


def expression(name, root=OVERLAY):
    return next(e.text for e in look(root).findall('expression') if e.get('name') == name)


def slides(animations):
    return sum(int(a.get('end').split(',')[0]) - int(a.get('start').split(',')[0])
               for a in animations if a.get('effect') == 'slide' and a.get('start') != a.get('end')) + \
        sum(int(a.get('start').split(',')[0]) for a in animations if a.get('effect') == 'slide' and a.get('start') == a.get('end'))


def test_the_setting_switches_them():
    assert expression('LookGlitch') == '!Skin.HasSetting(cf.glitch.off)'
    assert expression('LookGlitchSetting') == 'true'
    assert expression('LookGlitch', ROOT) == 'false' and expression('LookGlitchSetting', ROOT) == 'false'
    row = next(c for c in parse(ROOT / '1080i' / 'SkinSettings.xml').iter('control') if c.get('id') == '603')
    assert row.findtext('onclick') == 'Skin.ToggleSetting(cf.glitch.off)'
    assert row.findtext('selected') == '!Skin.HasSetting(cf.glitch.off)'
    assert row.findtext('visible') == '$EXP[LookGlitchSetting]'


def test_nightcity_hooks_are_empty():
    for name in ('LookHomeLogo', 'LookCardTwitch'):
        assert include(name, ROOT).find('definition') is not None
        assert len(include(name, ROOT).find('definition')) == 0, name


def test_spinner_frames_follow_the_sequence():
    """Kodi shows a multiimage's files in the order of their names: frame n is the spinner with
    its light on head n of the sequence, and the loop closes without a jump."""
    heads = textures_module().glitch_sequence()
    frames = sorted((UI / 'spinner_glitch').glob('*.png'))
    assert len(frames) == len(heads)
    for path, head in zip(frames, heads):
        a = Image.open(path).convert('RGBA')
        b = Image.open(UI / 'spinner' / '{:02d}.png'.format(head)).convert('RGBA')
        assert ImageChops.difference(a, b).getbbox() is None, path.name
    steps = [(b - a) % 12 for a, b in zip(heads, heads[1:] + heads[:1])]
    assert set(steps) <= {0, 1, 11, 5}  # on, held, back, and the skip after the dropout
    assert steps.count(5) == 1 and steps.count(11) >= 12
    assert heads.index(3) < 20 and heads[14:22] == [2, 3] * 4  # the record skip comes in the first 2 s


def test_twitch_and_ghosts_end_where_they_started():
    twitch = include('LookCardTwitch').find('definition').findall('animation')
    assert len(twitch) == 6 and slides(twitch) == 0
    # on focus, as the item's focused layout gets it, and only for some titles
    assert all(a.text == 'Focus' and a.get('condition') == '$PARAM[glitch] + String.EndsWith($PARAM[item].DBID,7)' for a in twitch)
    # Kodi plays a Visible animation on the control that turns visible: each copy has the condition
    ghosts = [g for g in include('LookHomeLogo').iter('control') if g.findtext('visible', '').startswith('$PARAM[glitch]')]
    assert len(ghosts) == 2 and all(g.get('type') == 'image' for g in ghosts)
    for image in ghosts:
        assert slides(image.findall('animation')) in (-2, 2)
    bands = [b for b in include('LookHomeFanart').iter('control') if '$PARAM[tear]' in b.findtext('visible', '')]
    assert len(bands) == 3 and all(b.find('animation') is not None for b in bands)


def test_each_glitch_waits_for_the_setting():
    text = (OVERLAY / '1080i' / 'Includes_Look.xml').read_text(encoding='utf-8')
    assert 'ui/spinner_glitch' in text and 'logo_mark_230_back' in text
    home = (ROOT / '1080i' / 'Home.xml').read_text(encoding='utf-8')
    tears = re.findall(r'<param name="tear" value="([^"]+)"', home)
    assert len(tears) == 2 and all(t.startswith('$EXP[LookGlitch] + ') for t in tears)
    assert (UI / 'logo_mark_230_back.png').is_file()
