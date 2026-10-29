"""Sets fixed weather on Kodi's weather window the way real weather add-ons do: Kodi runs this
with the location index as argument, reads Current.*, Day0-6.* and Location1 back when it ends
and converts them (Celsius and km/h in, the user's units out). Daily.* and the other extended
properties some skins read are set too.

Window(Home).Property(nc.test.weather.omit): current values to leave out, separated by | (e.g.
FeelsLike|Wind|WindDirection), as an add-on without them would. They are cleared, since Kodi
leaves its formatted values of the last fetch on the window."""
import xbmcgui

WINDOW = xbmcgui.Window(12600)
CURRENT = {
    'Location': 'Neon Harbor',
    'Condition': 'Partly Cloudy',
    'Temperature': '18',
    'FeelsLike': '16',
    'Humidity': '64',
    'Wind': '14',
    'WindDirection': 'SW',
    'UVIndex': '3',
    'DewPoint': '11',
    'OutlookIcon': '30.png',
    'FanartCode': '30',
}
# title, outlook, weather code, high, low
DAYS = [
    ('Thursday', 'Partly Cloudy', '30', '19', '11'),
    ('Friday', 'Showers', '11', '15', '9'),
    ('Saturday', 'Thunderstorms', '4', '17', '12'),
    ('Sunday', 'Sunny', '32', '22', '13'),
    ('Monday', 'Cloudy', '26', '18', '12'),
    ('Tuesday', 'Snow', '16', '2', '-3'),
    ('Wednesday', 'Foggy', '20', '9', '4'),
]


def main():
    WINDOW.setProperty('Locations', '1')
    WINDOW.setProperty('Location1', CURRENT['Location'])
    WINDOW.setProperty('WeatherProvider', 'Nightcity test weather')
    omit = xbmcgui.Window(10000).getProperty('nc.test.weather.omit').split('|')
    for key, value in CURRENT.items():
        if key in omit:
            WINDOW.clearProperty('Current.' + key)
        else:
            WINDOW.setProperty('Current.' + key, value)
    for i, (title, outlook, code, high, low) in enumerate(DAYS):
        day = 'Day{}.'.format(i)
        WINDOW.setProperty(day + 'Title', title)
        WINDOW.setProperty(day + 'Outlook', outlook)
        WINDOW.setProperty(day + 'OutlookIcon', code + '.png')
        WINDOW.setProperty(day + 'FanartCode', code)
        WINDOW.setProperty(day + 'HighTemp', high)
        WINDOW.setProperty(day + 'LowTemp', low)
        daily = 'Daily.{}.'.format(i + 1)
        WINDOW.setProperty(daily + 'ShortDay', title[:3])
        WINDOW.setProperty(daily + 'LongDay', title)
        WINDOW.setProperty(daily + 'Outlook', outlook)
        WINDOW.setProperty(daily + 'OutlookIcon', code + '.png')
        WINDOW.setProperty(daily + 'FanartCode', code)
        WINDOW.setProperty(daily + 'HighTemperature', high + '°C')
        WINDOW.setProperty(daily + 'LowTemperature', low + '°C')
    for prop in ('Current.IsFetched', 'Daily.IsFetched', 'Forecast.IsFetched'):
        WINDOW.setProperty(prop, 'true')


main()
