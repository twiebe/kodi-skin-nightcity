"""The clock is white (the text colour) everywhere: the Home top line, the quick menu, the
startup screen and the path lines of the other windows. Counters next to it stay dark blue."""
import re

from conftest import ROOT

SKIN = ROOT / '1080i'


def _clock_labels():
    for path in sorted(SKIN.glob('*.xml')):
        text = path.read_text(encoding='utf-8')
        for match in re.finditer(r'<control type="label"[^>]*>(?:(?!</control>).)*?System\.Time(?:(?!</control>).)*?</control>',
                                 text, re.S):
            yield path.name, match.group(0)


def test_every_clock_label_is_white():
    found = list(_clock_labels())
    assert len(found) >= 3
    for name, control in found:
        assert '<textcolor>text</textcolor>' in control, name


def test_path_line_clock_is_white_but_counters_are_not():
    text = (SKIN / 'Includes_Base.xml').read_text(encoding='utf-8')
    defaults = re.findall(r'<param name="counter" default="([^"]*)"/>', text)
    assert defaults
    for default in defaults:
        assert default == '[COLOR text]$INFO[System.Time][/COLOR]'
    path_line = re.search(r'<include name="PathLine">.*?\n    </include>', text, re.S).group(0)
    assert '<textcolor>state_text</textcolor>' in path_line
