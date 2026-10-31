"""The ratings line in the player (docs/media-info-af3.md, "Ratings in the player"): under the
badges of what plays, for a movie or an episode TMDb Helper's player ratings as the skin service
kept them (nc.kept.player.*), for music Kodi's own ratings of the song and its album. The block
got taller for it and for a longer plot; the text keeps its size."""
import navigation
from conftest import ROOT, parse

SKIN = ROOT / '1080i'
PLOT_LINE = 38  # font_body
GUARD = 'String.IsEqual(Player.FilenameAndPath,Window(Home).Property(nc.kept.player.file))'


def _include(name, path='Includes_Player.xml'):
    return next(i for i in parse(SKIN / path).iter('include') if i.get('name') == name)


def _params(call):
    return {p.get('name'): p.get('value') for p in call.findall('param')}


def _call(parent, name):
    return next(i for i in parent.iter('include') if i.get('content') == name)


def details():
    """The PlayerDetails group as Kodi builds it in the seek bar dialog."""
    window = navigation.load('DialogSeekBar.xml')
    return next(c for c in window.iter('control')
                if c.get('type') == 'group' and any((t.text or '') == '$VAR[PlayerPlot]' for t in c.iter('label')))


def _top(control):
    return int(control.findtext('top') or 0)


def _ratings(group):
    return next(c for c in group.findall('control') if c.get('type') == 'group'
                and any('nc.kept.player.' in (lab.text or '') for lab in c.iter('label')))


def test_player_details_have_a_ratings_line():
    params = _params(_call(_include('PlayerDetails'), 'RatingsLine'))
    assert params['item'] == 'VideoPlayer'
    assert params['prefix'] == 'nc.kept.player.'
    assert params['tmdb'] == GUARD
    assert params['wait'] == 'true'
    # VideoPlayer.Rating(name) is Kodi's default rating whatever the name: no IMDb or TMDb
    # entries from the library, only its unnamed rating
    assert params['own'] == 'false'
    # it comes in softly also over the video
    assert params['fade'] == 'true'


def test_the_line_follows_the_ratings_settings():
    """Per-source toggles and "only TMDb Helper" as everywhere: the library's rating only with it off."""
    line = _ratings(details())
    text = ' '.join(v.text or '' for v in line.iter('visible'))
    for setting in ('nc.ratings.hide.imdb', 'nc.ratings.show.tmdb', 'nc.ratings.hide.rt', 'nc.ratings.show.mdb'):
        assert setting in text, setting
    library = [lab for lab in line.iter('control') if (lab.findtext('label') or '') == '[UPPERCASE][COLOR text]$INFO[VideoPlayer.Rating][/COLOR][/UPPERCASE]']
    assert len(library) == 1
    assert 'Skin.HasSetting(nc.ratings.library)' in library[0].findtext('visible')
    named = [c for c in line.iter('control') if 'VideoPlayer.Rating(' in (c.findtext('label') or '')]
    assert len(named) == 3 and all(' + false + ' in c.findtext('visible') for c in named)
    fades = [a for a in line.findall('animation') if a.get('effect') == 'fade']
    assert [(a.text, a.get('condition'), a.get('time')) for a in fades] == [('Visible', 'true', '200')]


def test_ratings_sit_between_badges_and_plot():
    group = details()
    badges = next(c for c in group.findall('control') if c.get('type') == 'grouplist')
    line = _ratings(group)
    plot = next(c for c in group.findall('control') if c.get('type') == 'textbox')
    assert _top(line) >= _top(badges) + int(badges.findtext('height')) + 8
    assert _top(plot) >= _top(line) + 34 + 8
    assert line.findtext('left') == plot.findtext('left') == badges.findtext('left')


def test_plot_is_taller_with_the_same_font():
    """Five whole lines of font_body instead of three; longer plots are cut off, an autoscrolling
    text redraws the whole screen (test_plot_text.py)."""
    plot = next(c for c in details().findall('control') if c.get('type') == 'textbox')
    assert plot.findtext('font') == 'font_body'
    assert int(plot.findtext('height')) == 5 * PLOT_LINE + 2
    assert plot.find('autoscroll') is None


def test_block_ends_above_the_seek_line():
    """The block grew upwards: its plot ends above the seek line, with the OSD open or not."""
    seekbar = navigation.load('DialogSeekBar.xml')
    group = details()
    plot = next(c for c in group.findall('control') if c.get('type') == 'textbox')
    bar = next(c for c in seekbar.find('controls').findall('control')
               if c.get('type') == 'group' and _top(c) == 1000)
    assert _top(group) + _top(plot) + int(plot.findtext('height')) <= _top(bar) - 40
    # the dark gradient behind still starts above the block when the OSD lifts it by 130
    scrim = next(c for c in seekbar.find('controls').findall('control') if c.get('type') == 'image')
    assert _top(scrim) + int(scrim.findtext('height')) == 1080
    assert _top(scrim) <= _top(group) - 130 - 100


MUSIC_SOURCES = ('MusicPlayer.UserRating', 'MusicPlayer.Rating', 'MusicPlayer.Property(Album_Rating)')


def _music_block():
    window = navigation.load('MusicVisualisation.xml')
    return next(c for c in window.iter('control') if c.get('id') == '9100')


def test_music_player_has_a_ratings_line():
    """No TMDb Helper source for music: Kodi's own ratings, the user's own first."""
    block = _music_block()
    line = next(c for c in block.findall('control') if c.get('type') == 'group'
                and any('MusicPlayer.UserRating' in (lab.text or '') for lab in c.iter('label')))
    labels = ' '.join(lab.text or '' for lab in line.iter('label'))
    for source in MUSIC_SOURCES:
        assert '$INFO[{}]'.format(source) in labels, source
    assert labels.index('MusicPlayer.UserRating') < labels.index('MusicPlayer.Rating]')
    assert 'nc.ratings' not in ' '.join(v.text or '' for v in line.iter('visible'))
    # under the album line, above the play state and the seek line
    album = next(c for c in block.findall('control') if c.findtext('label') == '$VAR[MusicPlayerLine]')
    state = next(c for c in block.findall('control') if 'PlayerState' in (c.findtext('label') or ''))
    bar = next(c for c in block.findall('control') if c.get('type') == 'group' and c is not line
               and any(p.get('type') == 'progress' for p in c.iter('control')))
    assert _top(album) + int(album.findtext('height')) + 8 <= _top(line)
    assert _top(line) + 34 + 8 <= _top(state)
    assert _top(state) + int(state.findtext('height')) <= _top(bar)


def test_ratings_line_defaults_keep_the_other_pages():
    """Info pages and heroes: the library's IMDb and TMDb entries, no fade over a playing video."""
    defaults = {p.get('name'): p.get('default') for p in _include('RatingsLine', 'Includes_Info.xml').findall('param')}
    assert defaults['own'] == 'true'
    assert defaults['fade'] == '!Player.HasVideo'
