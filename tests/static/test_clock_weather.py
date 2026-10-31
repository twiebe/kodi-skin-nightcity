"""The weather (icon and temperature) stands left of every clock at the top right: the Home top
line and the path lines of the other windows, at the size of their line (TopWeather). Not in the
quick menu, whose clock has the weather tile under it, and not on the startup screen, which comes
before the weather is fetched. A path line with a counter (12/240) instead of the clock has no
weather."""
import re

from conftest import ROOT

SKIN = ROOT / '1080i'


def _include(name):
    for path in sorted(SKIN.glob('Includes*.xml')):
        match = re.search(r'<include name="{}">.*?\n    </include>'.format(name),
                          path.read_text(encoding='utf-8'), re.S)
        if match:
            return match.group(0)
    raise AssertionError(name)


def _uses(name):
    """Every <include content="name">...</include> in the skin, with its file."""
    for path in sorted(SKIN.glob('*.xml')):
        for match in re.finditer(r'<include content="{}">.*?</include>'.format(name),
                                 path.read_text(encoding='utf-8'), re.S):
            yield path.name, match.group(0)


def test_top_weather_is_white_icon_and_temperature_once_fetched():
    weather = _include('TopWeather')
    assert '<texture colordiffuse="text">ui/qm_weather.png</texture>' in weather
    assert '<label>$INFO[Weather.Temperature]</label>' in weather
    assert '<textcolor>text</textcolor>' in weather
    assert weather.count('Weather.IsFetched') == 2
    # the font and the size follow the line it stands on
    assert '<font>$PARAM[font]</font>' in weather
    assert '<width>$PARAM[icon]</width>' in weather
    assert '<aligny>$PARAM[aligny]</aligny>' in weather


def test_home_clock_has_the_weather_left_of_it_at_its_size():
    top = _include('HomeTop')
    weather = top.index('<include content="TopWeather">')
    assert weather < top.index('$INFO[System.Time]')
    use = re.search(r'<include content="TopWeather">.*?</include>', top, re.S).group(0)
    assert '<param name="font" value="font_num"/>' in use
    assert '<param name="icon" value="28"/>' in use
    assert '<param name="height" value="44"/>' in use
    assert '<param name="icontop" value="8"/>' in use
    assert '<param name="aligny" value="center"/>' in use
    # no second weather of its own any more
    assert top.count('Weather.Temperature') == 0


def test_path_line_clock_has_the_weather_left_of_it_in_its_font():
    line = _include('PathLine')
    assert '<param name="weather" default="true"/>' in line
    group = re.search(r'<control type="grouplist">.*?</control>\s*</definition>', line, re.S)
    assert group, 'the counter and the weather share a right-aligned row'
    group = group.group(0)
    assert '<align>right</align>' in group
    weather = re.search(r'<include content="TopWeather">.*?</include>', group, re.S).group(0)
    assert '<param name="font" value="$PARAM[counterfont]"/>' in weather
    assert '<param name="visible" value="$PARAM[weather]"/>' in weather
    # level with the clock, which is top aligned in the line
    assert '<param name="aligny" value="top"/>' in weather
    assert group.index('TopWeather') < group.index('<label>$PARAM[counter]</label>')


def test_status_bar_passes_the_weather_on():
    bar = _include('StatusBar')
    assert '<param name="weather" default="true"/>' in bar
    assert '<param name="weather" value="$PARAM[weather]"/>' in bar


def test_weather_only_where_the_clock_is():
    """A window whose path line shows a counter turns the weather off; one with the clock
    keeps it."""
    found = 0
    for name, use in [*_uses('PathLine'), *_uses('StatusBar')]:
        if name == 'Includes_Base.xml':
            continue  # StatusBar itself
        found += 1
        counter = re.search(r'<param name="counter" value="([^"]*)"/>', use)
        clock = counter is None or 'System.Time' in counter.group(1)
        assert ('<param name="weather" value="false"/>' not in use) == clock, name
    assert found >= 15


def test_every_top_right_clock_has_the_weather():
    """Every clock in the skin is one of the known ones; a new clock needs the weather or a
    reason here."""
    clocks = []
    for path in sorted(SKIN.glob('*.xml')):
        for line in path.read_text(encoding='utf-8').splitlines():
            if 'System.Time' in line:
                clocks.append(path.name)
    assert sorted(clocks) == sorted([
        'Includes_Home.xml',   # HomeTop: TopWeather
        'Includes_Home.xml',   # QuickMenuBody: the weather tile is under it
        'Includes_Base.xml',   # PathLine: TopWeather
        'Includes_Base.xml',   # StatusBar, the same PathLine
        'Startup.xml',         # before the weather is fetched
    ])
