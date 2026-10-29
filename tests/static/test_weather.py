"""Weather page (MyWeather.xml, Kodi's window "weather", 12600): the quick menu's weather tile
opens it. Current conditions large on top, the next days as a row of cards below."""
import re

from conftest import ROOT, parse

WINDOW = ROOT / '1080i' / 'MyWeather.xml'
FORECAST = '500'
# ids Kodi's CGUIWindowWeather fills or clicks itself (refresh, location, labels and images of
# its old layout): a skin control with one of them would get Kodi's text or action
KODI_IDS = {2, 3, 10, 11, *range(21, 29), *range(31, 96), *range(223, 229)}
# Kodi's weather codes (the file name of an add-on's icon, FanartCode): one glyph each
CODES = [str(i) for i in range(48)] + ['na']


def window():
    return parse(WINDOW)


def text(root):
    return '\n'.join((el.text or '') + ' '.join(el.attrib.values()) for el in root.iter())


def forecast():
    return next(c for c in window().iter('control') if c.get('id') == FORECAST)


def test_window_exists_with_focus_on_the_forecast():
    root = window()
    assert root.findtext('defaultcontrol') == FORECAST
    # Kodi keeps the window in memory: open on today, not on the day focused last time
    assert 'SetFocus({},0,absolute)'.format(FORECAST) in [el.text for el in root.findall('onload')]


def test_no_ids_kodi_fills():
    ids = {int(c.get('id')) for c in window().iter('control') if c.get('id') and c.get('id').isdigit()}
    assert not ids & KODI_IDS


def test_current_conditions():
    """Place, conditions, temperature and the facts Kodi formats in the user's units."""
    body = text(window())
    for label in ('Weather.Location', 'Weather.Conditions'):
        assert '$INFO[{}]'.format(label) in body, label
    for prop in ('Current.Temperature', 'Current.FeelsLike', 'Current.Humidity', 'Current.Wind', 'Current.UVIndex',
                 'Current.DewPoint', 'Updated'):
        assert 'Window(Weather).Property({})'.format(prop) in body, prop
    # Kodi's own words: Feels like, UV index, Wind, Dew point, Humidity, Last updated
    for string in (402, 403, 404, 405, 406, 12014):
        assert '$LOCALIZE[{}]'.format(string) in body, string


def includes():
    return parse(ROOT / '1080i' / 'Includes_Weather.xml')


def facts():
    """The fact lines beside the temperature: key string to visible condition."""
    lines = [i for i in window().iter('include') if i.get('content') == 'FactLine']
    args = [{p.get('name'): p.get('value') for p in i.findall('param')} for i in lines]
    return {re.search(r'LOCALIZE\[(\d+)\]', a['key']).group(1): a.get('visible') for a in args}


def test_every_fact_line_always_shows():
    """No hiding of facts for now: Kodi replaces the add-on's values with formatted ones (a
    missing temperature 0 degrees, a missing wind "From  at 0 km/h"), so a missing value cannot
    always be told from a real one. To be revisited with real weather services."""
    assert facts() == {key: None for key in ('402', '406', '404', '403', '405', '12014')}


def test_temperature_large_and_tight():
    """A large size of the title font, "64°F" as one word: the font's degree sign stands wide
    apart from digits and letter, so number, degree sign and unit letter are labels of their
    own, pulled together. Units other than °C and °F (K) come whole."""
    row = next(c for c in window().iter('control') if c.get('id') == '510')
    assert row.get('type') == 'grouplist' and row.findtext('orientation') == 'horizontal'
    assert int(row.findtext('itemgap')) < 0
    labels = row.findall('control')
    assert [(c.get('type'), c.findtext('width'), c.findtext('font')) for c in labels] == [('label', 'auto', 'font_temp')] * 3
    assert [c.findtext('label') for c in labels] == [
        '$INFO[Window(Weather).Property(Current.Temperature)]', '°', '$VAR[WeatherUnit]']
    degrees = '[String.IsEqual(System.TemperatureUnits,°C) | String.IsEqual(System.TemperatureUnits,°F)]'
    assert labels[1].findtext('visible') == degrees
    unit = next(v for v in includes().iter('variable') if v.get('name') == 'WeatherUnit')
    assert [(v.get('condition'), v.text) for v in unit.findall('value')] == [
        ('String.IsEqual(System.TemperatureUnits,°C)', 'C'), ('String.IsEqual(System.TemperatureUnits,°F)', 'F'),
        (None, '$INFO[System.TemperatureUnits]')]
    fonts = {f.findtext('name'): (f.findtext('filename'), f.findtext('size'))
             for f in parse(ROOT / '1080i' / 'Font.xml').iter('font')}
    assert fonts['font_temp'] == ('RetroUI-Bold.ttf', '140')


def test_forecast_row_of_the_next_days():
    """Day0 to Day6 as Kodi sets them, each card only when the add-on gave that day."""
    row = forecast()
    assert row.get('type') == 'list'
    assert row.findtext('orientation') == 'horizontal'
    items = row.find('content').findall('item')
    assert len(items) == 7
    for day, item in enumerate(items):
        prefix = 'Window(Weather).Property(Day{}.'.format(day)
        assert item.findtext('visible') == '!String.IsEmpty({}Title))'.format(prefix)
        assert item.findtext('label') == '$INFO[{}Title)]'.format(prefix)
        props = {p.get('name'): p.text for p in item.findall('property')}
        assert props == {'high': '$INFO[{}HighTemp)]'.format(prefix), 'low': '$INFO[{}LowTemp)]'.format(prefix),
                         'outlook': '$INFO[{}Outlook)]'.format(prefix), 'code': '$INFO[{}FanartCode)]'.format(prefix)}


def test_up_leaves_the_page():
    """The row is the top row of the page: Up goes back (DESIGN.md), Down has nothing below."""
    row = forecast()
    assert row.findtext('onup') == 'Action(Back)'
    assert row.findtext('ondown') == 'noop'


def test_weather_glyph_per_code():
    """Line icons in the skin's style, tinted, one per weather code; unknown codes fall back."""
    folder = ROOT / 'media' / 'ui' / 'weather'
    assert [c for c in CODES if not (folder / '{}.png'.format(c)).is_file()] == []
    body = WINDOW.read_text(encoding='utf-8') + (ROOT / '1080i' / 'Includes_Weather.xml').read_text(encoding='utf-8')
    assert 'ui/weather/$INFO[Window(Weather).Property(Current.FanartCode)].png' in body
    assert 'ui/weather/$INFO[ListItem.Property(code)].png' in body
    assert len(re.findall(r'fallback="ui/weather/na.png"', body)) == 2


def test_says_how_to_get_weather_without_it():
    root = window()
    hint = [el for el in root.iter('control') if '$LOCALIZE[31321]' in (el.findtext('label') or '')]
    assert [el.findtext('visible') for el in hint] == ['!Weather.IsFetched']
