"""The plot of an info page stands still and opens in full on OK.

A textbox that scrolls by itself (autoscroll) changes on screen every few seconds for as long as
it shows, and Kodi's dirty-region solver then redraws the whole screen: a long TMDb biography kept
kodi-dev at 458 % CPU with nothing playing, 2 % without the autoscroll. So no textbox scrolls by
itself. The plot of the info page is a stop of the remote instead, on every page: Up from the
button row lands on it, OK opens the whole text in Kodi's text viewer, Up leaves the page like Up
from the buttons did. Leaving takes the same keys whether the text is long, short or missing.
Kodi tells a textbox longer than its box by Container(id).HasNext (it has a second page): only
then a hint says OK reads on.
"""
import pytest

from conftest import ROOT, layout_files, parse
from focus import Page, State
from test_tmdb_dead_ends import EXTRA

INFO = 'DialogVideoInfo.xml'
EPISODE = 'String.IsEqual(ListItem.DBType,episode)'
PERSON = 'String.IsEqual(ListItem.Property(tmdb_type),person)'
# page kind: (text button, its textbox, info prefix of the text, condition of that head)
PLOTS = {
    'movie': ('9060', '9050', 'ListItem', '!{} + !{}'.format(EPISODE, PERSON)),
    'episode': ('9061', '9051', 'Container(5100).ListItem', EPISODE),
    'person': ('9062', '9052', 'ListItem', PERSON),
}
KINDS = {
    'movie': dict(dbtype='movie', dbid=True),
    'tmdb movie': dict(dbtype='movie', tmdb_type='movie'),
    'show': dict(dbtype='tvshow', dbid=True),
    'episode': dict(dbtype='episode', dbid=True),
    'person': dict(dbtype='video', tmdb_type='person'),
}
TEXTS = ('long', 'short', 'empty')
# a modal yes/no dialog lives for a moment and has to be read whole before it is answered
SCROLLS_ON_PURPOSE = {('DialogConfirm.xml', '9')}


def _plot(kind):
    return PLOTS['movie' if kind in ('movie', 'tmdb movie', 'show') else kind]


def _state(kind, text, chain=''):
    extra = dict(EXTRA)
    extra.update({'Container({}).HasNext'.format(box): text == 'long' for _, box, _, _ in PLOTS.values()})
    extra.update({'String.IsEmpty({}.Plot)'.format(item): text == 'empty' for _, _, item, _ in PLOTS.values()})
    containers = {'5500': 'items', '5510': 'items' if kind == 'person' else 'empty', '50': 'empty',
                  '5300': 'empty', '5901': 'empty', '5100': 'items' if kind == 'episode' else 'empty',
                  '5200': 'items' if kind == 'episode' else 'empty'}
    props = {'TMDbHelper.Instance': chain or ('True' if kind == 'person' else ''),
             'nc.info.ep.query': 'season=1&episode=1' if kind == 'episode' else ''}
    return State(containers=containers, props=props, extra=extra, **KINDS[kind])


@pytest.fixture(scope='module')
def info_page():
    return Page(INFO)


def _labels(info_page, kind, string):
    button = info_page.controls[PLOTS[kind][0]]
    return [c for c in info_page.parent[button].findall('control')
            if c.get('type') == 'label' and string in (c.findtext('label') or '')]


def test_no_textbox_scrolls_by_itself():
    scrolling = set()
    for path in layout_files():
        for c in parse(path).iter('control'):
            if c.get('type') == 'textbox' and c.find('autoscroll') is not None:
                scrolling.add((path.name, c.get('id') or c.findtext('label')))
    assert scrolling == SCROLLS_ON_PURPOSE


@pytest.mark.parametrize('kind', sorted(PLOTS))
def test_each_head_names_its_text(info_page, kind):
    _, box, item, _ = PLOTS[kind]
    textbox = info_page.controls[box]
    assert textbox.get('type') == 'textbox'
    assert textbox.findtext('label') == '$INFO[{}.Plot]'.format(item)


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('kind', sorted(KINDS))
def test_leaving_takes_the_same_keys_for_any_text(info_page, kind, text):
    """Buttons, Up: the text, Up: out. Long, short or no text alike."""
    button = _plot(kind)[0]
    state = _state(kind, text)
    top = info_page.start(state)
    assert info_page.move(top, 'onup', state) == (button, [])
    # Up from the text is what Up from the buttons was: one level up, or one page back in a chain
    assert info_page.move(button, 'onup', state) == (None, ['Action(Back)'])
    assert info_page.move(button, 'ondown', state)[0] == top
    assert info_page.move(button, 'onleft', state) == (None, ['noop'])
    assert info_page.move(button, 'onright', state) == (None, ['noop'])


@pytest.mark.parametrize('kind', sorted(KINDS))
def test_only_the_text_of_the_page_shown_takes_the_focus(info_page, kind):
    state = _state(kind, 'short')
    assert [b for b, _, _, _ in PLOTS.values() if info_page.can_focus(b, state)] == [_plot(kind)[0]]


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('kind', sorted(KINDS))
@pytest.mark.parametrize('chain', ['', 'True'])
def test_the_text_leaves_no_dead_end(info_page, kind, text, chain):
    if kind == 'person' and not chain:
        return  # a person page only opens in a chain
    assert info_page.report(_state(kind, text, chain=chain), offscreen={'5901', '9098'}) == []


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('kind', sorted(PLOTS))
def test_ok_opens_the_whole_text(info_page, kind, text):
    button, _, item, _ = PLOTS[kind]
    clicks = info_page.clicks(button, _state(kind, text))
    # no empty viewer for a page without a plot
    assert clicks == ([] if text == 'empty' else ['NotifyAll(nightcity,plot:{})'.format(item)])


@pytest.mark.parametrize('kind', sorted(PLOTS))
def test_the_text_shows_the_cursor_of_a_card(info_page, kind):
    button, box, _, head = PLOTS[kind]
    c = info_page.controls[button]
    assert c.get('type') == 'button'
    assert c.findtext('visible') == head
    focus = c.find('texturefocus')
    assert (focus.text, focus.get('colordiffuse'), focus.get('border')) == ('ui/cut.png', 'focus', '16')
    assert c.find('texturenofocus') is not None and not (c.findtext('texturenofocus') or '').strip()
    # the frame lies around the text, 16 px out to the sides and 10 px above and below it
    textbox = info_page.controls[box]
    frame = [int(c.findtext(k)) for k in ('left', 'top', 'width', 'height')]
    text = [int(textbox.findtext(k)) for k in ('left', 'top', 'width', 'height')]
    shift = -320 if kind == 'episode' else 0  # HeroBody's shift: an episode has no poster
    assert frame == [text[0] + shift - 16, text[1] - 10, text[2] + 32, text[3] + 20]


@pytest.mark.parametrize('kind', sorted(PLOTS))
def test_a_hint_says_ok_reads_on_when_the_text_is_longer(info_page, kind):
    _, box, _, head = PLOTS[kind]
    [hint] = _labels(info_page, kind, '$LOCALIZE[31468]')
    assert hint.findtext('visible') == '{} + Container({}).HasNext'.format(head, box)
    assert hint.findtext('label') == '[UPPERCASE]$LOCALIZE[31468][/UPPERCASE]'
    assert (hint.findtext('font'), hint.findtext('textcolor')) == ('font_caps_small', 'text_mute')
    # on the button row, flush with the right edge of the text
    textbox = info_page.controls[box]
    shift = -320 if kind == 'episode' else 0
    assert hint.findtext('top') == '490' and hint.findtext('height') == '54'
    assert hint.findtext('align') == 'right'
    assert int(hint.findtext('left')) + int(hint.findtext('width')) == \
        int(textbox.findtext('left')) + shift + int(textbox.findtext('width'))


@pytest.mark.parametrize('kind', sorted(PLOTS))
def test_no_plot_shows_a_placeholder_for_the_cursor(info_page, kind):
    _, box, item, head = PLOTS[kind]
    [empty] = _labels(info_page, kind, '$LOCALIZE[31469]')
    assert empty.findtext('visible') == '{} + String.IsEmpty({}.Plot)'.format(head, item)
    assert (empty.findtext('font'), empty.findtext('textcolor')) == ('font_body', 'text_mute')
    textbox = info_page.controls[box]
    shift = -320 if kind == 'episode' else 0
    assert (int(empty.findtext('left')), empty.findtext('top')) == \
        (int(textbox.findtext('left')) + shift, textbox.findtext('top'))


def test_strings():
    text = (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    assert 'msgctxt "#31468"\nmsgid "[COLOR state_text]OK[/COLOR] read more"\n' in text
    assert 'msgctxt "#31469"\nmsgid "No description"\n' in text


def test_player_plot_is_cut_off():
    """The plot over the playing video stays a plain text: cut off, no stop, no viewer."""
    box = next(c for c in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('control') if c.get('id') == '420')
    assert box.find('autoscroll') is None
    assert box.get('type') == 'textbox'
