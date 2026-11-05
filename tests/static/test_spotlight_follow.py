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
    """Only with Home opening: the page fades run on a page change, the swap itself is instant."""
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
    for hero, item in (('MovieHero', 'Container(9000)'), ('ShowHero', 'Container(9001)')):
        body = _include(hero)
        assert re.search(r'<control type="group">\s*<visible>!\$EXP\[SpotlightFollows\]</visible>\s*'
                         r'<include content="HeroBody">\s*<param name="item" value="{}\.ListItem"/>'.format(re.escape(item)),
                         body), hero


def test_pills_chevrons_and_progress_hide_while_following():
    """Play and Info there act on the spotlight's own title. The real buttons stay, Up from a row
    reaches them."""
    for hero in ('MovieHero', 'ShowHero'):
        body = _include(hero)
        pills = re.search(r'<control type="grouplist">(.*?)<include content="SpotlightPill">', body, re.S).group(1)
        assert '<visible>!$EXP[SpotlightFollows]</visible>' in pills, hero
    assert '<param name="visible" value="Container(9000).ListItem.IsResumable + !$EXP[SpotlightFollows]"/>' in _include('MovieHero')
    assert 'SpotlightFollows' not in re.search(r'<control type="group" id="9050">(.*?)</control>\s*<control type="grouplist">', _include('MovieHero'), re.S).group(1)
