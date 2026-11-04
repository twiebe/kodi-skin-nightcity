"""The plot of an info page stands still and opens in full from a button.

A textbox that scrolls by itself (autoscroll) changes on screen every few seconds for as long as
it shows, and Kodi's dirty-region solver then redraws the whole screen: a long TMDb biography kept
kodi-dev at 458 % CPU with nothing playing, 2 % without the autoscroll. So no textbox scrolls by
itself. The text takes no focus: a button in the row opens it whole in Kodi's text viewer, always
at the same place, and Up from the row leaves the page at once, one key less on every level of a
chain. Kodi tells a textbox longer than its box by Container(id).HasNext (it has a second page):
only then three dots say it goes on.
"""
import pytest

from conftest import ROOT, layout_files, parse
from focus import Page, State
from test_tmdb_dead_ends import EXTRA

INFO = 'DialogVideoInfo.xml'
EPISODE = 'String.IsEqual(ListItem.DBType,episode)'
PERSON = 'String.IsEqual(ListItem.Property(tmdb_type),person)'
BUTTON = '9063'
DOTS = 24  # px right of the text for the three dots
# page kind: (its textbox, info prefix of the text, condition of that head)
PLOTS = {
    'movie': ('9050', 'ListItem', '!{} + !{}'.format(EPISODE, PERSON)),
    'episode': ('9051', 'Container(5100).ListItem', EPISODE),
    'person': ('9052', 'ListItem', PERSON),
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
    extra.update({'Container({}).HasNext'.format(box): text == 'long' for box, _, _ in PLOTS.values()})
    extra.update({'String.IsEmpty({}.Plot)'.format(item): text == 'empty' for _, item, _ in PLOTS.values()})
    containers = {'5500': 'items', '5510': 'items' if kind == 'person' else 'empty', '50': 'empty',
                  '5300': 'empty', '5901': 'empty', '5100': 'items' if kind == 'episode' else 'empty',
                  '5200': 'items' if kind == 'episode' else 'empty'}
    props = {'TMDbHelper.Instance': chain or ('True' if kind == 'person' else ''),
             'nc.info.ep.query': 'season=1&episode=1' if kind == 'episode' else ''}
    return State(containers=containers, props=props, extra=extra, **KINDS[kind])


@pytest.fixture(scope='module')
def info_page():
    return Page(INFO)


def test_no_textbox_scrolls_by_itself():
    scrolling = set()
    for path in layout_files():
        for c in parse(path).iter('control'):
            if c.get('type') == 'textbox' and c.find('autoscroll') is not None:
                scrolling.add((path.name, c.get('id') or c.findtext('label')))
    assert scrolling == SCROLLS_ON_PURPOSE


@pytest.mark.parametrize('kind', sorted(PLOTS))
def test_each_head_names_its_text(info_page, kind):
    box, item, _ = PLOTS[kind]
    textbox = info_page.controls[box]
    assert textbox.get('type') == 'textbox'
    assert textbox.findtext('label') == '$INFO[{}.Plot]'.format(item)


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('kind', sorted(KINDS))
def test_up_from_the_buttons_leaves_at_once(info_page, kind, text):
    """No stop on the text: one level up, or one page back in a chain, with a long, short or no text."""
    state = _state(kind, text)
    assert info_page.move(info_page.start(state), 'onup', state) == (None, ['Action(Back)'])


@pytest.mark.parametrize('text', TEXTS)
@pytest.mark.parametrize('kind', sorted(KINDS))
@pytest.mark.parametrize('chain', ['', 'True'])
def test_the_page_leaves_no_dead_end(info_page, kind, text, chain):
    if kind == 'person' and not chain:
        return  # a person page only opens in a chain
    assert info_page.report(_state(kind, text, chain=chain), offscreen={'5901', '9098', '9099'}) == []


def test_the_text_takes_no_focus(info_page):
    """The cursor frame around the text is gone with its stop, so are the stops themselves."""
    for cid in ('9060', '9061', '9062'):
        assert cid not in info_page.controls
    page = (ROOT / '1080i' / INFO).read_text(encoding='utf-8')
    assert 'PlotFocus' not in page and 'ui/cut.png' not in page


def _row():
    return next(c for c in parse(ROOT / '1080i' / INFO).iter('control') if c.get('id') == '9000')


def _in_row():
    """The row's children in order, by id: an include names it in its id param."""
    ids = []
    for child in _row():
        if child.tag == 'control' and child.get('id'):
            ids.append(child.get('id'))
        elif child.tag == 'include':
            ids += [p.get('value') for p in child.findall('param') if p.get('name') == 'id']
    return ids


def test_the_row_starts_on_play_whatever_had_the_focus_last():
    """A grouplist keeps its last focused child over closing the page: leaving by a button further
    right opened the next page on that button."""
    default = _row().find('defaultcontrol')
    assert (default.text, default.get('always')) == ('9001', 'true')


def test_the_button_stands_left_of_the_more_button():
    ids = _in_row()
    assert ids.index(BUTTON) == ids.index('9003') - 1
    assert ids.index('9003') < ids.index('9005') == len(ids) - 1


@pytest.mark.parametrize('kind', sorted(KINDS))
@pytest.mark.parametrize('text', ['long', 'short'])
def test_the_button_is_there_whenever_there_is_a_text(info_page, kind, text):
    """Long or short alike: it is always in the same place, also when the box shows the whole text."""
    assert info_page.can_focus(BUTTON, _state(kind, text))


@pytest.mark.parametrize('kind', sorted(KINDS))
def test_no_button_without_a_text(info_page, kind):
    """Nothing to open: "No description" stands in the box."""
    assert not info_page.can_focus(BUTTON, _state(kind, 'empty'))


@pytest.mark.parametrize('kind', sorted(KINDS))
def test_ok_opens_the_whole_text(info_page, kind):
    clicks = [c for c in info_page.clicks(BUTTON, _state(kind, 'long')) if c != 'noop']
    assert clicks == ['NotifyAll(nightcity,plot:{})'.format(_plot(kind)[1])]


def test_the_button_names_what_it_opens(info_page):
    assert '$VAR[InfoPlotLabel]' in info_page.controls[BUTTON].findtext('label')
    var = next(v for v in parse(ROOT / '1080i' / 'Variables.xml').iter('variable')
               if v.get('name') == 'InfoPlotLabel')
    values = [(v.get('condition'), v.text) for v in var.findall('value')]
    assert values == [(PERSON, '$LOCALIZE[31474]'), (None, '$LOCALIZE[31473]')]


def test_the_button_guards_the_chain_like_its_row():
    call = next(c for c in _row().findall('include') if any(
        p.get('name') == 'id' and p.get('value') == BUTTON for p in c.findall('param')))
    assert call.find('include').text == 'ChainBackGuard'


def test_dots_say_the_text_goes_on():
    """When the text is longer than its box, three muted dots right of its last line say so.
    A hint "OK read more" on the button row read as if it were about the focused button."""
    root = parse(ROOT / '1080i' / 'Includes_Info.xml')
    inc = next(i for i in root.iter('include') if i.get('name') == 'PlotHints')
    [dots] = [c for c in inc.iter('control') if c.get('type') == 'label' and c.findtext('label') == '…']
    assert (dots.findtext('visible'), dots.findtext('textcolor')) == ('$PARAM[more]', 'text_mute')
    assert (dots.findtext('left'), dots.findtext('top')) == ('$PARAM[moreleft]', '$PARAM[moretop]')
    page = parse(ROOT / '1080i' / INFO)
    calls = [i for i in page.iter('include') if i.get('content') == 'PlotHints']
    assert len(calls) == len(PLOTS)
    for call in calls:
        params = {p.get('name'): p.get('value') for p in call.findall('param')}
        assert int(params['hintleft']) + int(params['hintwidth']) - DOTS <= int(params['moreleft']), params
        assert int(params['moretop']) > int(params['texttop']), params
    # no hint on the button row any more, nor its string
    for path in (ROOT / '1080i').glob('*.xml'):
        assert '31468' not in path.read_text(encoding='utf-8'), path.name


@pytest.mark.parametrize('kind', sorted(PLOTS))
def test_no_plot_shows_a_placeholder(info_page, kind):
    box, item, head = PLOTS[kind]
    expected = '{} + String.IsEmpty({}.Plot)'.format(head, item)
    [empty] = [c for c in info_page.window.iter('control') if c.get('type') == 'label'
               and c.findtext('label') == '$LOCALIZE[31469]' and c.findtext('visible') == expected]
    assert (empty.findtext('font'), empty.findtext('textcolor')) == ('font_body', 'text_mute')
    textbox = info_page.controls[box]
    shift = -320 if kind == 'episode' else 0
    assert (int(empty.findtext('left')), empty.findtext('top')) == \
        (int(textbox.findtext('left')) + shift, textbox.findtext('top'))


def test_strings():
    text = (ROOT / 'language' / 'resource.language.en_gb' / 'strings.po').read_text(encoding='utf-8')
    assert 'msgctxt "#31468"' not in text  # the hint "OK read more" is gone (three dots instead)
    assert 'msgctxt "#31469"\nmsgid "No description"\n' in text
    assert 'msgctxt "#31473"\nmsgid "description"\n' in text
    assert 'msgctxt "#31474"\nmsgid "biography"\n' in text


def test_player_plot_is_cut_off():
    """The plot over the playing video stays a plain text: cut off, no stop, no viewer."""
    box = next(c for c in parse(ROOT / '1080i' / 'Includes_Player.xml').iter('control') if c.get('id') == '420')
    assert box.find('autoscroll') is None
    assert box.get('type') == 'textbox'
