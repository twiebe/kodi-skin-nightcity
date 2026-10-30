"""Media info of a movie or episode beside title and plot: resolution, HDR, audio, runtime,
"ends at" and every rating TMDb Helper or Kodi has (docs/media-info-af3.md).

The heads of the info page and the home heroes share HeroBody, so these tests read the windows
as Kodi builds them (navigation.load) and look at what ends up on screen.
"""
import re

import pytest

import navigation
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
TH = 'Window(Home).Property(TMDbHelper.ListItem.{})'
EPISODE = 'Container(5100).ListItem'


def _variable(name):
    var = next(v for v in parse(SKIN / 'Variables.xml').iter('variable') if v.get('name') == name)
    return [(v.get('condition'), v.text) for v in var.iter('value')]


def _head(episode):
    """The movie or episode head of the info page, expanded."""
    want = 'String.IsEqual(ListItem.DBType,episode)'
    for group in navigation.load('DialogVideoInfo.xml').find('controls'):
        visible = group.findtext('visible') or ''
        plot = [c for c in group.iter('control') if '.Plot]' in (c.findtext('label') or '')]
        if plot and (visible == want if episode else visible.startswith('!' + want + ' +')):
            return group
    raise AssertionError('no head')


def _movie_hero():
    for group in navigation.load('Home.xml').iter('control'):
        if group.get('id') == '9030':
            return group
    raise AssertionError('no movie hero rating line')


def _labels(el):
    return [(c.findtext('label') or '', _visible(c), c) for c in el.iter('control')
            if c.get('type') in ('label', 'button')]


def _visible(control):
    """Kodi shows a control while all its visible conditions hold."""
    return ' + '.join(v.text for v in control.findall('visible'))


def _with(el, text):
    found = [(label, visible) for label, visible, _ in _labels(el) if text in label]
    assert found, text
    return found


HEADS = [pytest.param(False, 'ListItem', id='movie'), pytest.param(True, EPISODE, id='episode')]


# Tags row: resolution, HDR and audio on both heads

@pytest.mark.parametrize('episode, item', HEADS)
def test_info_heads_show_resolution_hdr_and_audio(episode, item):
    head = _head(episode)
    prefix = 'InfoEpisode' if episode else 'Item'
    assert _with(head, '$VAR[{}Resolution]$VAR[{}Hdr, ,]'.format(prefix, prefix))
    assert _with(head, '$VAR[{}Audio]'.format(prefix))


@pytest.mark.parametrize('prefix, item', [('Item', 'ListItem'), ('InfoEpisode', EPISODE),
                                          ('Spotlight', 'Container(9000).ListItem')])
def test_audio_names_codec_and_layout_like_the_player(prefix, item):
    """DD+ 5.1 instead of EAC3 6CH, the names the OSD gives the playing track."""
    for part in ('AudioCodec', 'AudioChannels'):
        assert _variable(prefix + part) == [
            (c and c.replace('VideoPlayer.', item + '.'), t.replace('VideoPlayer.', item + '.'))
            for c, t in _variable('Player' + part)]
    assert _variable(prefix + 'Audio') == [(None, '$VAR[{0}AudioCodec]$VAR[{0}AudioChannels, ,]'.format(prefix))]


def test_audio_codec_names_cover_jellyfin():
    """Jellyfin calls DTS dts (Kodi's own scraper dca)."""
    conditions = [c for c, _ in _variable('PlayerAudioCodec')]
    assert 'String.IsEqual(VideoPlayer.AudioCodec,dts)' in conditions
    assert 'String.IsEqual(VideoPlayer.AudioCodec,opus)' in conditions


@pytest.mark.parametrize('name', ['ItemResolution', 'InfoEpisodeResolution', 'SpotlightResolution'])
def test_resolutions_name_8k(name):
    """Kodi says 8K, not 8000: without a value of its own it read 8Kp."""
    assert any(c and c.endswith('VideoResolution,8K)') and t == '8K' for c, t in _variable(name))


def test_movie_head_drops_the_genre_tag_for_the_tech_tags():
    """The genre is the kicker above the title already."""
    head = _head(False)
    genre = [visible for label, visible, c in _labels(head)
             if c.get('type') == 'button' and label == '[UPPERCASE]$INFO[ListItem.Genre][/UPPERCASE]']
    assert genre and all(visible.startswith('!true + ') for visible in genre)


@pytest.mark.parametrize('episode, item', HEADS)
def test_info_heads_keep_runtime_in_minutes(episode, item):
    assert _with(_head(episode), '$INFO[{}.Duration(mins)] $LOCALIZE[31012]'.format(item))


# Ends at

def _ends(el, item):
    resume = _with(el, '$LOCALIZE[31059] $INFO[{}.EndTimeResume]'.format(item))
    finish = [(label, visible) for label, visible in _with(el, '$LOCALIZE[31059] $INFO[Player.FinishTime]')
              if visible.startswith('[String.IsEqual({}.DBType,movie)'.format(item))]
    assert len(resume) == 1 and len(finish) == 1
    return resume[0][1], finish[0][1]


@pytest.mark.parametrize('episode, item', HEADS)
def test_ends_at_counts_from_the_resume_point(episode, item):
    resume, _ = _ends(_head(episode), item)
    assert 'String.IsEqual({}.DBType,movie)'.format(item) in resume
    assert 'String.IsEqual({}.DBType,episode)'.format(item) in resume
    # without a runtime Kodi's EndTimeResume is the current time
    assert '!String.IsEmpty({}.Duration)'.format(item) in resume


def _playing(item):
    """The condition of 99010ae (Arctic Fuse 3) for 'item is the one playing'."""
    return [
        'String.IsEqual({}.FileNameAndPath,Player.FileNameAndPath)'.format(item),
        'Integer.IsEqual({}.DBID,VideoPlayer.DBID)'.format(item),
        'String.IsEqual({}.FileName,Player.Filename)'.format(item),
        'String.StartsWith({}.FileNameAndPath,plugin://plugin.video.themoviedb.helper/)'.format(item),
        'String.IsEqual({}.IMDBNumber,VideoPlayer.IMDBNumber)'.format(item),
        'String.IsEqual({}.UniqueID(tmdb),Window(Home).Property(TMDbHelper.Player.TMDb_ID))'.format(item),
        'String.IsEqual({}.UniqueID(tvshow.tmdb),Window(Home).Property(TMDbHelper.Player.TVShow.TMDb_ID))'.format(item),
        'Integer.IsEqual({}.Season,VideoPlayer.Season)'.format(item),
        'Integer.IsEqual({}.Episode,VideoPlayer.Episode)'.format(item),
    ]


@pytest.mark.parametrize('episode, item', HEADS)
def test_ends_at_of_the_playing_item_is_the_players(episode, item):
    """The item that plays ends when the player says, not at its stored resume point."""
    resume, finish = _ends(_head(episode), item)
    for part in _playing(item):
        assert part in finish, part
        assert part in resume, part
    assert 'Player.HasVideo' in finish and '!VideoPlayer.Content(livetv)' in finish
    # one or the other: the resume one carries the playing condition negated
    match = re.search(r'!\[(Player\.HasVideo \+ !VideoPlayer\.Content\(livetv\) \+ .*)\]$', resume)
    assert match, resume
    assert match.group(1) in finish
    assert '!String.IsEmpty(Player.FinishTime)' in finish


def test_ends_at_stays_out_of_item_layouts():
    """In an item layout Kodi reads Player.FileNameAndPath and VideoPlayer.* from the list
    item itself, so every item there would count as playing."""
    for path in navigation.LAYOUT.glob('*.xml'):
        if path.name.startswith('Includes') or path.name in ('Font.xml', 'Variables.xml'):
            continue
        window = navigation.load(path.name)
        for layout in [*window.iter('itemlayout'), *window.iter('focusedlayout')]:
            for label, _, _ in _labels(layout):
                assert 'EndTimeResume' not in label and 'Player.FinishTime' not in label, path.name


def test_movie_hero_shows_ends_at_too():
    hero = navigation.load('Home.xml')
    _ends(hero, 'Container(9000).ListItem')


# Ratings

SOURCES = ['IMDb_Rating', 'TMDb_Rating', 'RottenTomatoes_Rating', 'RottenTomatoes_UserMeter',
           'MetaCritic_Rating', 'Trakt_Rating', 'Letterboxd_Rating', 'MDBList_Rating']


def _ratings(episode):
    head = _head(episode)
    lines = [c for c in head.iter('control') if c.get('id') == ('9043' if episode else '9046')]
    assert len(lines) == 1
    return lines[0]


@pytest.mark.parametrize('episode', [False, True])
def test_ratings_line_has_every_source_tmdb_helper_knows(episode):
    line = _ratings(episode)
    shown = [label for label, _, _ in _labels(line)]
    order = []
    for source in SOURCES:
        hits = [i for i, label in enumerate(shown) if TH.format(source) in label]
        assert hits, source
        order.append(hits[0])
    assert order == sorted(order), 'IMDb, TMDb, Rotten Tomatoes, Metacritic, Trakt, Letterboxd, MDbList'


@pytest.mark.parametrize('episode, item', HEADS)
def test_ratings_fall_back_to_kodis_own(episode, item):
    line = _ratings(episode)
    for source, name in (('IMDb_Rating', 'imdb'), ('TMDb_Rating', 'themoviedb'), ('TMDb_Rating', 'tmdb')):
        own = _with(line, '$INFO[{}.Rating({})]'.format(item, name))
        assert len(own) == 1
        # only while TMDb Helper has none
        assert '!String.IsEmpty({})'.format(TH.format(source)) in own[0][1]
    # the plain rating without a source only when no named one shows
    plain = [(label, visible) for label, visible, _ in _labels(line) if '$INFO[{}.Rating]'.format(item) in label]
    assert len(plain) == 1
    for source in SOURCES:
        assert TH.format(source) in plain[0][1], source
    assert '!String.IsEqual({}.Rating,0.0)'.format(item) in plain[0][1]


@pytest.mark.parametrize('episode', [False, True])
def test_online_ratings_wait_for_tmdb_helper(episode):
    """IMDb, Rotten Tomatoes ... come from a second thread of TMDb Helper: until it is done the
    properties still hold the ratings of the title before."""
    line = _ratings(episode)
    for source in SOURCES:
        if source == 'TMDb_Rating':
            continue
        for label, visible, _ in _labels(line):
            if TH.format(source) in label:
                assert 'String.IsEmpty(Window(Home).Property(TMDbHelper.IsUpdatingRatings))' in visible, source


def test_episode_ratings_from_tmdb_helper_only_for_the_dialogs_episode():
    """TMDb Helper watches the info page's own item, the head follows the episode list: another
    episode there shows Kodi's ratings, not those of the opened one."""
    line = _ratings(True)
    for label, visible, _ in _labels(line):
        if 'TMDbHelper.ListItem.' in label:
            assert 'Integer.IsEqual(Container(5100).ListItem.Season,ListItem.Season)' in visible
            assert 'Integer.IsEqual(Container(5100).ListItem.Episode,ListItem.Episode)' in visible


def test_movie_info_page_reads_tmdb_helper():
    """It used to hide the TMDb Helper rating (nc.none): library movies from Jellyfin showed none."""
    assert 'nc.none' not in (SKIN / 'DialogVideoInfo.xml').read_text(encoding='utf-8')
    _with(_ratings(False), TH.format('TMDb_Rating'))


def test_ratings_line_hides_without_ratings():
    """test_spotlight.test_rating_slot_hidden_without_data checks 9030 on Home. The hero reads
    the ratings the service kept for its title (tests/static/test_ratings_source.py)."""
    visible = _visible(_movie_hero())
    for source in SOURCES:
        assert 'Window(Home).Property(nc.hero.9000.{})'.format(source) in visible, source
    assert 'Container(9000).ListItem.Rating' in visible


@pytest.mark.parametrize('episode', [False, True])
def test_ratings_line_stops_before_the_right_column(episode):
    """The details (movie) and the cast (episode) start at x 1400: sources that do not fit stay
    out, the last first, instead of running into them."""
    window = navigation.load('DialogVideoInfo.xml')
    parents = {child: parent for parent in window.iter() for child in parent}
    line = next(c for c in window.iter('control') if c.get('id') == ('9043' if episode else '9046'))
    width = int(next(c for c in line.iter('control') if c.get('type') == 'grouplist').findtext('width'))
    left, node = 0, line
    while node is not None:
        left += int(node.findtext('left') or 0)
        node = parents.get(node)
    assert left + width <= 1400 - 16, (left, width)


def test_info_key_names_hdr_and_audio_like_the_osd():
    """The info key during playback (DialogFullScreenInfo) showed hdr10 and 6CH; it uses the
    OSD's names: HDR10 / SDR, DD+ 5.1."""
    tags = {label: visible for label, visible, _ in _labels(navigation.load('DialogFullScreenInfo.xml'))}
    assert tags['[UPPERCASE]$VAR[PlayerHdr][/UPPERCASE]'] == '!String.IsEmpty(VideoPlayer.VideoResolution)'
    assert tags['[UPPERCASE]$INFO[VideoPlayer.AudioLanguage,, ]$VAR[PlayerAudio][/UPPERCASE]'] == \
        '!String.IsEmpty(VideoPlayer.AudioCodec)'
    assert not [label for label in tags if 'VideoPlayer.HdrType' in label or 'AudioChannels' in label]


@pytest.mark.parametrize('episode, item', HEADS)
def test_ends_at_looks_like_the_runtime(episode, item):
    """Not pink: ends at reads with the runtime next to it, in the same colour and style."""
    head = _head(episode)
    controls = {label: c for label, _, c in _labels(head)}
    runtime = next(c for label, c in controls.items() if '$INFO[{}.Duration(mins)] $LOCALIZE[31012]'.format(item) in label)
    for text in ('$LOCALIZE[31059] $INFO[{}.EndTimeResume]'.format(item), '$LOCALIZE[31059] $INFO[Player.FinishTime]'):
        ends = next(c for label, c in controls.items() if text in label)
        for tag in ('textcolor', 'disabledcolor', 'font', 'height', 'textoffsetx'):
            assert ends.findtext(tag) == runtime.findtext(tag), (text, tag)
        for tag in ('texturenofocus', 'texturefocus'):
            assert ends.find(tag).attrib == runtime.find(tag).attrib, (text, tag)
