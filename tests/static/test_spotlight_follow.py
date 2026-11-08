"""The spotlight follows the focused row title: on a movie, show or episode card of a row the hero
shows that title and the rotation stands; elsewhere the spotlight is its random self again."""
import re

from conftest import ROOT

SKIN = ROOT / '1080i'
HOME = (SKIN / 'Includes_Home.xml').read_text(encoding='utf-8')


def _include(name):
    match = re.search(r'<include name="{}">(.*?)\n    </include>'.format(name), HOME, re.S)
    assert match, name
    return match.group(1)


def _expression():
    match = re.search(r'<expression name="SpotlightFollows">(.*?)</expression>', HOME, re.S)
    assert match
    return match.group(1)


def test_follows_on_the_rows_of_a_page_with_its_spotlight_on():
    """Without spotlight the preview shows the focused card itself (test_peek_hero.py): one hero
    from the menu onto the card, no swap."""
    expression = _expression()
    for group, setting in ((9210, 'SpotlightSource'), (9410, 'nc.movies.spotlight'), (9510, 'nc.shows.spotlight')):
        assert '[ControlGroup({}).HasFocus() + !String.IsEqual(Skin.String({}),off)]'.format(group, setting) in expression


def test_follows_only_title_cards():
    types = re.findall(r'String\.IsEqual\(ListItem\.DBType,(\w+)\)', _expression())
    assert sorted(types) == ['episode', 'movie', 'season', 'tvshow']


def test_the_music_page_does_not_follow():
    assert '9810' not in _expression()


def test_rotation_stands_while_following():
    """Kodi starts the interval over when the condition comes back. $EXP is not resolved in an
    autoscroll tag, so it reads the group that has the expression."""
    autoscroll = re.search(r'<autoscroll[^>]*>(.*?)</autoscroll>', _include('SpotlightAutoscroll')).group(1)
    assert '!Control.IsVisible(9302)' in autoscroll


def test_followed_hero_is_a_group_of_its_own_on_home():
    body = _include('FollowHero')
    assert re.search(r'<control type="group" id="9302">\s*<visible>\$EXP\[SpotlightFollows\]</visible>', body)
    assert '<include>FollowHero</include>' in (SKIN / 'Home.xml').read_text(encoding='utf-8')


def test_followed_hero_reads_the_focused_card():
    body = _include('FollowHero')
    assert '<param name="item" value="ListItem"/>' in body
    assert '$VAR[CardArt]' in body  # an episode shows the poster of its show
    assert '<param name="kicker" value="$VAR[FollowKicker]"/>' in body
    assert '$VAR[ItemResolution]$VAR[ItemHdr, ,]' in body  # the Spotlight variables hold one list
    assert '$VAR[ItemAudio]' in body
    assert 'nc.kept.follow.' in body


def test_followed_hero_does_not_fade_on_every_move():
    """The group fades when it comes up and with Home opening; a move along a row leaves it up."""
    body = _include('FollowHero')
    assert 'type="Visible"' not in body and 'PageFade' not in body
    assert '<param name="fade"' not in body
    assert 'type="WindowOpen"' in body


def test_kicker_names_the_show_and_number_of_an_episode():
    text = (SKIN / 'Variables.xml').read_text(encoding='utf-8')
    kicker = re.search(r'<variable name="FollowKicker">(.*?)</variable>', text, re.S).group(1)
    assert '$INFO[ListItem.TVShowTitle]' in kicker and '$VAR[FollowSeasonNum]$VAR[FollowEpisodeNum]' in kicker
    assert '$INFO[ListItem.Genre]' in kicker
    assert '$LOCALIZE[31100]' not in kicker  # "Spotlight": this title was picked by the cursor


def test_own_heroes_hide_while_following_without_touching_their_fades():
    """The hidden state sits on a group around HeroBody: Kodi does not update the children of a
    hidden group, so coming back runs no page fade."""
    for hero, item in (('MovieHeroBody', 'Container($PARAM[list])'), ('ShowHero', 'Container(9001)')):
        body = _include(hero)
        assert re.search(r'<control type="group">\s*<visible>!\$EXP\[SpotlightFollows\]</visible>\s*'
                         r'<include>HeroSwapFade</include>\s*<include content="HeroBody">\s*<param name="item" value="{}\.ListItem"/>'.format(re.escape(item)),
                         body), hero


def test_pills_chevrons_and_progress_hide_while_following():
    """Play and Info there act on the spotlight's own title. The real buttons stay, Up from a row
    reaches them."""
    for hero in ('MovieHero', 'ShowHero'):
        body = _include(hero)
        assert re.search(r'<visible>!\$EXP\[SpotlightFollows\]</visible>\s*<include>HeroSwapFade</include>\s*'
                         r'<control type="grouplist">', body), hero
    assert re.search(r'<include>HeroSwapFade</include>\s*<control type="grouplist">.*?'
                     r'<param name="info" value="Container\(9000\)\.ListItem\.PercentPlayed"/>',
                     _include('MovieHero'), re.S)
    assert 'SpotlightFollows' not in re.search(r'<control type="group" id="9050">(.*?)</control>\s*<!-- they act', _include('MovieHero'), re.S).group(1)


def test_kept_ratings_guard_names_the_card_with_or_without_a_library_id():
    home = (ROOT / '1080i' / 'Includes_Home.xml').read_text()
    guard = re.search(r'<expression name="FollowKeptIsCard">(.*?)</expression>', home).group(1)
    for part in ('nc.kept.follow.dbid', 'nc.kept.follow.dbtype', 'nc.kept.follow.label', 'nc.kept.follow.year',
                 'String.IsEmpty(ListItem.DBID)'):
        assert part in guard
    assert '<param name="tmdb" value="$EXP[FollowKeptIsCard]"/>' in home


BASE = (SKIN / 'Includes_Base.xml').read_text(encoding='utf-8')


def _base_include(name):
    match = re.search(r'<include name="{}">(.*?)\n    </include>'.format(name), BASE, re.S)
    assert match, name
    return match.group(1)


def test_swap_fades_take_as_long_as_the_spotlights_own_crossfade():
    assert re.search(r'<constant name="HeroSwapTime">400</constant>', BASE)
    both = _base_include('HeroSwapFade')
    assert re.search(r'type="Visible"[^>]*>\s*<effect type="fade" start="0" end="100" time="HeroSwapTime"/>', both)
    assert re.search(r'type="Hidden"[^>]*>\s*<effect type="fade" start="100" end="0" time="HeroSwapTime"/>', both)


def test_spotlight_fades_out_and_in_around_a_card():
    for hero in ('MovieHero MovieHeroBody', 'ShowHero'):
        body = ''.join(_include(name) for name in hero.split())
        wrappers = re.findall(r'<visible>!\$EXP\[SpotlightFollows\]</visible>\s*<include>HeroSwapFade</include>', body)
        assert len(wrappers) == 2, hero  # the hero's text and poster, its pills
        assert '<visible>!$EXP[SpotlightFollows]</visible>\n                <include content="SpotlightPill">' not in body


def test_followed_hero_only_fades_in():
    """Its content is the unqualified ListItem: once the focus left the row that is whatever has
    the focus now, nothing to fade out with."""
    body = _include('FollowHero')
    head = body[:body.index('an episode has the poster')]
    assert '<include>HeroSwapIn</include>' in head and 'Hidden' not in head
    assert 'reversible="false"' in _base_include('HeroSwapIn')  # Kodi would run it backwards, with 9302 up


def test_backdrop_of_hero_and_rows_fade_as_long_as_the_swap():
    window = (SKIN / 'Home.xml').read_text(encoding='utf-8')
    # the card's backdrop where the hero follows the card (CardBackdrop), else the hero's own
    assert re.search(r'<visible>!\$EXP\[CardBackdrop\]</visible>\s*<include>HeroSwapFade</include>', window)
    assert re.search(r'<visible>\$EXP\[CardBackdrop\]</visible>\s*<include>HeroSwapFade</include>', window)



MUSIC = (SKIN / 'Includes_Music.xml').read_text(encoding='utf-8')


def _music_include(name):
    match = re.search(r'<include name="{}">(.*?)\n    </include>'.format(name), MUSIC, re.S)
    assert match, name
    return match.group(1)


def test_music_follows_albums_and_artists_of_its_rows_only():
    expression = re.search(r'<expression name="MusicFollows">(.*?)</expression>', MUSIC).group(1)
    assert 'ControlGroup(9810).HasFocus()' in expression
    assert 'String.IsEqual(ListItem.DBType,album)' in expression
    assert 'String.IsEqual(ListItem.DBType,artist)' in expression
    assert 'genre' not in expression


def test_music_hero_makes_way_like_the_video_heroes():
    autoscroll = re.search(r'<autoscroll[^>]*>(.*?)</autoscroll>', _include('SpotlightAutoscroll')).group(1)
    assert '!Control.IsVisible(9303)' in autoscroll
    assert re.search(r'<visible>!\$EXP\[MusicFollows\]</visible>\s*<include>HeroSwapFade</include>', _music_include('MusicHero'))
    follow = _music_include('MusicFollowHero')
    assert re.search(r'<control type="group" id="9303">\s*<visible>\$EXP\[MusicFollows\]</visible>\s*<include>HeroSwapIn</include>', follow)
    assert '<include>MusicFollowHero</include>' in (SKIN / 'Home.xml').read_text(encoding='utf-8')


def test_music_follow_shows_what_the_spotlight_shows():
    follow = _music_include('MusicFollowHero')
    for part in ('$INFO[ListItem.Art(thumb)]', '$VAR[MusicCardLine]', '$INFO[ListItem.Label]', '$INFO[ListItem.Year]',
                 '$INFO[ListItem.Genre]', '$VAR[MusicFollowPlot]'):
        assert part in follow, part
    assert 'TMDbHelper' not in follow and 'nc.kept' not in follow  # local data only


def test_music_buttons_stay_for_up_while_following():
    """A hidden grouplist takes no focus and Up would go on to the top menu: it only fades out."""
    hero = _music_include('MusicHero')
    buttons = hero[hero.index('<control type="grouplist" id="9850">'):]
    assert '<visible>String.IsEqual(Window(Home).Property(nc.page),music)</visible>' in buttons
    assert re.search(r'<animation type="Conditional" condition="\$EXP\[MusicFollows\]">\s*'
                     r'<effect type="fade" start="100" end="0" time="HeroSwapTime"/>', buttons)


def test_hero_logo_keeps_its_distance_from_the_tags():
    """Bottom aligned, a logo that fills its height ends at top + height; the tags stand 18 px
    below it. The genre's letters end at 143 (kicker at 116), 18 px above the logo."""
    body = _include('HeroBody')
    logo = re.search(r'<control type="image" id="\$PARAM\[logoid\]">(.*?)</control>', body, re.S).group(1)
    assert '<top>$PARAM[logotop]</top>' in logo and '<height>100</height>' in logo
    assert '<param name="logotop" default="161"/>' in body and '<param name="metatop" default="279"/>' in body
    assert re.search(r'<control type="grouplist" id="\$PARAM\[metaid\]">\s*<left>\$PARAM\[textleft\]</left>\s*<top>\$PARAM\[metatop\]</top>', body)
    assert re.search(r'<param name="left" value="\$PARAM\[textleft\]"/>\s*<param name="top" value="\$PARAM\[kickertop\]"/>', body)


def test_hero_poster_ends_with_the_buttons():
    """The poster keeps 2:3 and ends where the button pills end: the padded row stands at 487,
    its pills from 497 for 54 px. The text column keeps its 40 px from the poster."""
    body = _include('HeroPoster')
    assert '<param name="width" value="290"/>' in body and '<param name="height" value="435"/>' in body
    assert 'ui/mask_290x435.png' in body
    assert 116 + 435 == 497 + 54 and 64 + 290 + 40 == 394
    home = (ROOT / '1080i' / 'Includes_Home.xml').read_text(encoding='utf-8')
    info = (ROOT / '1080i' / 'DialogVideoInfo.xml').read_text(encoding='utf-8')
    assert len(re.findall(r'<left>LookHeroPillsLeft</left>\s*<top>LookHeroPillsTop</top>', home)) == 2
    look = (ROOT / '1080i' / 'Includes_Look.xml').read_text(encoding='utf-8')
    assert '<constant name="LookHeroPillsLeft">384</constant>' in look and '<constant name="LookHeroPillsTop">487</constant>' in look
    assert 'mask_280x420' not in home and 'mask_280x420' not in info
    assert re.search(r'<control type="grouplist" id="9000">\s*<left>384</left>\s*<top>487</top>\s*<width>1472</width>', info)
