"""Timers.xml: Kodi reads it on its own (CSkinTimerManager), not through the skin's includes, so
an $EXP, $VAR or $PARAM in it stays as written and the condition never parses."""
import re

from conftest import ROOT


def test_timers_use_no_skin_expressions():
    text = (ROOT / '1080i' / 'Timers.xml').read_text(encoding='utf-8')
    body = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    assert not re.findall(r'\$(?:EXP|VAR|PARAM)\[', body)


def test_the_twin_timer_reads_whether_the_title_plays_from_the_info_page():
    timers = (ROOT / '1080i' / 'Timers.xml').read_text(encoding='utf-8')
    info = (ROOT / '1080i' / 'DialogVideoInfo.xml').read_text(encoding='utf-8')
    assert 'Control.IsVisible(9096)' in timers
    assert re.search(r'<control type="group" id="9096">\s*<visible>\$EXP\[InfoPlaying\]</visible>', info)
