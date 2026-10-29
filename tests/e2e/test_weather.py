"""Weather page (MyWeather.xml) with fixed weather: the fake add-on in fixtures/ is installed
into this Kodi and chosen as its weather service for the module, then the old service is back."""
import pathlib
import shutil
import time

import pytest

from conftest import _data, action, builtin, cond, info, rpc, screenshot, wait_for

pytestmark = pytest.mark.e2e

ADDON = 'weather.nightcity.fake'
FIXTURE = pathlib.Path(__file__).parent / 'fixtures' / ADDON
PAGE = 'Window.IsActive(weather)'


def installed():
    try:
        return rpc('Addons.GetAddonDetails', {'addonid': ADDON, 'properties': ['enabled']})['addon']
    except RuntimeError:
        return None


@pytest.fixture(scope='module')
def weather():
    target = _data() / 'kodi' / 'addons' / ADDON
    shutil.copytree(FIXTURE, target, dirs_exist_ok=True)
    builtin('UpdateLocalAddons')
    end = time.time() + 20
    while not installed() and time.time() < end:
        time.sleep(0.5)
    rpc('Addons.SetAddonEnabled', {'addonid': ADDON, 'enabled': True})
    before = rpc('Settings.GetSettingValue', {'setting': 'weather.addon'})['value']
    rpc('Settings.SetSettingValue', {'setting': 'weather.addon', 'value': ADDON})
    try:
        wait_for('Weather.IsFetched + String.IsEqual(Weather.Location,Neon Harbor)', timeout=30)
        yield
    finally:
        rpc('Settings.SetSettingValue', {'setting': 'weather.addon', 'value': before})
        rpc('Addons.SetAddonEnabled', {'addonid': ADDON, 'enabled': False})
        shutil.rmtree(target, ignore_errors=True)
        builtin('UpdateLocalAddons')
        if not before:
            wait_for('!Weather.IsFetched', timeout=30)


@pytest.fixture
def page(weather):
    """The weather page, opened like a user does: quick menu, up to the weather tile, OK. From
    Home, but not `home`: the page needs no library, so no focus in Home's rows either."""
    # after a restart: the skin's startup screen, then Home, then jellyfin-kodi's "Resume the
    # previous sync?" a few seconds later; back answers no (as in `home`)
    wait_for('!Window.IsActive(startup)', timeout=30)
    builtin('Dialog.Close(all,true)')
    builtin('ReplaceWindow(Home)')
    clear, end = 0, time.time() + 30
    while clear < 6 and time.time() < end:
        if cond('System.HasActiveModalDialog')['System.HasActiveModalDialog']:
            action('back', delay=1)
            clear = 0
        else:
            clear += 1
            time.sleep(0.5)
    wait_for('Window.IsActive(home) + !System.HasActiveModalDialog')
    builtin('ActivateWindow(1170)')
    wait_for('Control.HasFocus(1220)')
    time.sleep(0.3)  # a key in the first moment after opening gets lost
    action('up')
    wait_for('Control.HasFocus(1210)')
    action('select')
    wait_for(PAGE + ' + Control.HasFocus(500)')
    yield
    if cond(PAGE)[PAGE]:
        action('back', delay=0.5)


def test_current_conditions_and_the_next_days(page):
    current = info('Weather.Location', 'Weather.Conditions', 'Weather.Temperature',
                   'Window(Weather).Property(Current.Humidity)', 'Window(Weather).Property(Current.FanartCode)',
                   'Container(500).NumItems')
    assert current['Weather.Location'] == 'Neon Harbor'
    assert current['Weather.Conditions'] == 'Partly Cloudy'
    assert current['Weather.Temperature'] in ('18°C', '64°F')  # the add-on gives Celsius
    assert current['Window(Weather).Property(Current.Humidity)'] == '64%'
    assert current['Window(Weather).Property(Current.FanartCode)'] == '30'
    assert current['Container(500).NumItems'] == '7'
    days = [info(*('Container(500).ListItemAbsolute({}).{}'.format(i, f) for f in ('Label', 'Property(code)', 'Property(outlook)')))
            for i in range(7)]
    assert [list(d.values())[0] for d in days] == ['Thursday', 'Friday', 'Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday']
    assert [list(d.values())[1] for d in days] == ['30', '11', '4', '32', '26', '16', '20']
    assert list(days[1].values())[2] == 'Showers'
    time.sleep(0.5)  # fade-in
    screenshot('weather')
    action('right', 'right')
    wait_for('Integer.IsEqual(Container(500).CurrentItem,3)')
    time.sleep(0.3)
    screenshot('weather-day')


def test_a_day_without_forecast_has_no_card(page):
    builtin('ClearProperty(Day6.Title,weather)')
    try:
        wait_for('Integer.IsEqual(Container(500).NumItems,6)')
    finally:
        builtin('SetProperty(Day6.Title,Wednesday,weather)')
    wait_for('Integer.IsEqual(Container(500).NumItems,7)')


@pytest.mark.parametrize('key', ['back', 'up'])
def test_back_and_up_return_home(page, key):
    action(key)
    wait_for('Window.IsActive(home) + !' + PAGE)


def test_opens_on_today(page):
    action('right', 'right', 'right')
    wait_for('Integer.IsEqual(Container(500).CurrentItem,4)')
    action('back')
    wait_for('Window.IsActive(home)')
    builtin('ActivateWindow(weather)')
    wait_for(PAGE + ' + Control.HasFocus(500)')
    assert cond('Integer.IsEqual(Container(500).CurrentItem,1)')['Integer.IsEqual(Container(500).CurrentItem,1)']
