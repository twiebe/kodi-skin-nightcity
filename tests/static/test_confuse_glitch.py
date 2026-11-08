"""Confuse's loading screen glitches: the startup spinner sticks, skips and runs back, the startup
logo points backwards for a blink. Always on, no setting. The other glitches (the Home logo's
ghost, the spotlight's tear, the twitching cards) and their switch are gone. Nightcity has none."""
import importlib.util

from PIL import Image, ImageChops

from conftest import ROOT, parse

OVERLAY = ROOT / 'skins' / 'confuse'
UI = OVERLAY / 'media' / 'ui'
LANGUAGES = sorted(ROOT.glob('language/*/strings.po'))


def textures_module():
    spec = importlib.util.spec_from_file_location('make_textures_confuse', ROOT / 'tools' / 'make_textures_confuse.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def look(root=OVERLAY):
    return parse(root / '1080i' / 'Includes_Look.xml')


def include(name, root=OVERLAY):
    return next(i for i in look(root).findall('include') if i.get('name') == name)


def windows():
    paths = list((ROOT / '1080i').glob('*.xml')) + list((OVERLAY / '1080i').glob('*.xml'))
    return {p: p.read_text(encoding='utf-8') for p in paths}


def test_no_setting_and_no_switch():
    for path, text in windows().items():
        for gone in ('LookGlitch', 'cf.glitch', 'LookSettingsLookHeight', '31475', '31476', 'LookCardTwitch'):
            assert gone not in text, (path.name, gone)
    ids = [c.get('id') for c in parse(ROOT / '1080i' / 'SkinSettings.xml').iter('control')]
    assert '603' not in ids
    assert len(LANGUAGES) == 8
    for po in LANGUAGES:
        text = po.read_text(encoding='utf-8')
        assert 'msgctxt "#31475"' not in text and 'msgctxt "#31476"' not in text, po.parent.name


def test_startup_always_glitches():
    """The shared Startup.xml passes no glitch params; Confuse always shows its glitch spinner and
    the logo's backwards blink."""
    startup = (ROOT / '1080i' / 'Startup.xml').read_text(encoding='utf-8')
    assert 'name="glitch"' not in startup and 'name="calm"' not in startup
    for name in ('LookStartupWordmark', 'LookStartupTrack'):
        for root in (ROOT, OVERLAY):
            params = [p.get('name') for p in include(name, root).findall('param')]
            assert 'glitch' not in params and 'calm' not in params, (name, root.name)
    text = (OVERLAY / '1080i' / 'Includes_Look.xml').read_text(encoding='utf-8')
    assert '$PARAM[glitch]' not in text and '$PARAM[calm]' not in text
    spinners = [c for c in include('LookStartupTrack').iter('control') if c.get('type') == 'multiimage']
    assert [s.findtext('imagepath') for s in spinners] == ['ui/spinner_glitch']
    assert spinners[0].find('visible') is None
    back = [c for c in include('LookStartupWordmark').iter('control') if c.findtext('texture') == 'ui/logo_mark_230_back.png']
    assert len(back) == 1
    assert (UI / 'logo_mark_230_back.png').is_file()


def test_home_logo_and_spotlight_hold_still():
    home = (ROOT / '1080i' / 'Home.xml').read_text(encoding='utf-8')
    assert 'name="tear"' not in home
    for root in (ROOT, OVERLAY):
        assert [p.get('name') for p in include('LookHomeLogo', root).findall('param')] == []
        assert 'tear' not in [p.get('name') for p in include('LookHomeFanart', root).findall('param')]
    assert '$PARAM[tear]' not in (OVERLAY / '1080i' / 'Includes_Look.xml').read_text(encoding='utf-8')
    assert len([c for c in include('LookHomeLogo').iter('control') if c.get('type') == 'image']) == 2
    assert '<include>LookHomeLogo</include>' in (ROOT / '1080i' / 'Includes_Home.xml').read_text(encoding='utf-8')


def test_nightcity_hooks_are_empty():
    assert len(include('LookHomeLogo', ROOT).find('definition')) == 0


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
