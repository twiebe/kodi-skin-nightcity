"""The skin service (scripts/nightcity.py service): the skin starts the script once and sends
it its commands with NotifyAll(nightcity,command:arg:...), so no second interpreter starts."""
import re
import sys

from conftest import ROOT, parse

sys.path.insert(0, str(ROOT / 'scripts'))
import nightcity  # noqa: E402

SKIN = ROOT / '1080i'
SCRIPT = 'special://skin/scripts/nightcity.py'


def _actions():
    """(file, element, action text) of every action and param value in the skin's XML."""
    for path in sorted(SKIN.glob('*.xml')):
        for el in parse(path).iter():
            for text in [el.text or ''] + [v for k, v in el.attrib.items() if k == 'value']:
                if 'nightcity' in text or SCRIPT in text:
                    yield path.name, el, text.strip()


def test_the_script_starts_only_as_the_service():
    starts = sorted((name, el.tag, el.get('condition'), text) for name, el, text in _actions()
                    if 'RunScript(' + SCRIPT in text)
    assert starts == [
        ('Home.xml', 'onload', 'String.IsEmpty(Window(Home).Property(nc.service)) + '
         'String.IsEmpty(Window(Home).Property(TMDbHelper.Instance))', 'RunScript({},service,home)'.format(SCRIPT)),
        ('Timers.xml', 'onstop', 'Window.IsActive(startup) + String.IsEmpty(Window(Home).Property(nc.service))',
         'RunScript({},service,startup)'.format(SCRIPT))]


def test_every_message_is_a_command_of_the_service():
    messages = [text for _, _, text in _actions() if 'NotifyAll(nightcity,' in text]
    assert len(messages) > 40
    for text in messages:
        message = re.fullmatch(r'NotifyAll\(nightcity,(.+)\)', text).group(1)
        assert ',' not in message, text  # arguments go with colons
        command = message.split(':')[0]
        assert command.startswith('$PARAM[') or nightcity.parse_message('nightcity', 'Other.' + command), text


def test_picks_send_their_arguments_with_colons():
    picks = {p.get('value') for path in SKIN.glob('Includes*.xml') for p in parse(path).iter('param')
             if p.get('name') == 'pick' and p.get('value')}
    assert picks and all(',' not in p and p.split(':')[0] in nightcity.COMMANDS for p in picks)


def test_the_startup_timer_starts_one_service():
    """The timer would start again while the Startup screen stays up: once a service runs, it
    neither starts nor runs again."""
    timer = next(t for t in parse(SKIN / 'Timers.xml').iter('timer') if t.findtext('name') == 'nc_startup_script')
    assert timer.findtext('start') == 'Window.IsActive(startup) + String.IsEmpty(Window(Home).Property(nc.service))'
