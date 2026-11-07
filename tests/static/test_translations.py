"""The translations: German, French, Spanish, Italian, Brazilian Portuguese, Polish and Japanese, one
file each for both skins. Each has every English string, in the same order, with the same markup; Confuse
gives them a capital first letter like its English."""
import re

import pytest

from conftest import ROOT, parse

LANGUAGES = ('de_de', 'fr_fr', 'es_es', 'it_it', 'pt_br', 'pl_pl', 'ja_jp')
ENTRY = re.compile(r'msgctxt "#(\d+)"\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"')
TOKEN = re.compile(r'\[/?[A-Z]+(?: [a-z_]+)?\]|%[sd]|\{\d*\}')


def entries(lang, root=ROOT):
    text = (root / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
    return ENTRY.findall(text)


def test_the_languages():
    assert sorted(p.name for p in (ROOT / 'language').iterdir()) == sorted(
        'resource.language.{}'.format(lang) for lang in ('en_gb',) + LANGUAGES)


@pytest.mark.parametrize('lang', LANGUAGES)
def test_header_names_the_language(lang):
    text = (ROOT / 'language' / 'resource.language.{}'.format(lang) / 'strings.po').read_text(encoding='utf-8')
    assert text.startswith('msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: {}\\n"\n'.format(lang))


@pytest.mark.parametrize('lang', LANGUAGES)
def test_every_string_is_translated_in_order(lang):
    english = [(i, en) for i, en, _ in entries('en_gb')]
    assert [(i, en) for i, en, _ in entries(lang)] == english
    assert all(tr.strip() for _, _, tr in entries(lang))


@pytest.mark.parametrize('lang', LANGUAGES)
def test_markup_and_placeholders_stay(lang):
    for i, en, tr in entries(lang):
        assert sorted(TOKEN.findall(tr)) == sorted(TOKEN.findall(en)), (i, en, tr)
        assert tr == tr.strip() or en != en.strip(), i


@pytest.mark.parametrize('lang', LANGUAGES)
def test_no_dashes(lang):
    """No en or em dash, as in the English."""
    assert not [i for i, _, tr in entries(lang) if '–' in tr or '—' in tr]


@pytest.mark.parametrize('lang', LANGUAGES)
def test_names_stay_names(lang):
    for i, en, tr in entries(lang):
        for name in ('Kodi', 'TMDb', 'Jellyfin', 'Trakt', 'IMDb', 'CoreELEC'):
            assert en.count(name) <= tr.count(name), (i, name, tr)


def test_unit_after_a_number_stays_small():
    for lang in LANGUAGES:
        tr = dict((i, t) for i, _, t in entries(lang))['31012']
        assert not tr[:1].isupper(), (lang, tr)  # Japanese has no case


def test_confuse_capitalises_translations(confuse_root):
    for lang in LANGUAGES:
        for i, _, tr in entries(lang, confuse_root):
            first = next((c for c in re.sub(r'\[[^\]]*\]', '', tr) if c.isalpha()), '')
            if i != '31012' and not tr.startswith('['):
                assert not first.islower(), (lang, i, tr)


@pytest.mark.parametrize('lang', LANGUAGES)
def test_confuse_translations_answer_its_english(confuse_root, lang):
    """Confuse writes its English msgids with a capital. Kodi takes the English string for an id
    whose msgid in the translation differs (LocalizeStrings.cpp:50-60), so the translation's msgids
    change the same way."""
    english = [(i, en) for i, en, _ in entries('en_gb', confuse_root)]
    assert [(i, en) for i, en, _ in entries(lang, confuse_root)] == english
    assert ('31006', 'Home') in english


def test_nightcity_keeps_translations_as_written(confuse_root):
    """Only the Confuse build changes the case: Nightcity's file is the source."""
    source = entries('de_de')
    assert any(tr[:1].islower() for _, _, tr in source)


@pytest.mark.parametrize('lang', LANGUAGES)
def test_nightcity_fixed_width_labels_fit(lang):
    """Nightcity's buttons of fixed width, in its font and in capitals as it shows most of them: a
    translation fits wherever the English does."""
    from PIL import ImageFont
    from test_confuse_look import fixed_width_buttons, font_defs, font_file, fontset_of

    def width(font_name, text, fontset='Default'):
        filename, size = font_defs(ROOT, fontset)[font_name]
        font = ImageFont.truetype(str(font_file(ROOT, filename)), size)
        return max(font.getlength(text), font.getlength(text.upper()))

    english = list(fixed_width_buttons(ROOT))
    translated = list(fixed_width_buttons(ROOT, lang))
    assert len(english) == len(translated)
    for (_, en, _, _, _), (name, label, w, offset, font) in zip(english, translated):
        if not label.strip() or width(font, en) + 2 * offset > w:
            continue  # the English does not fit either: not the translation's doing
        need = width(font, label, fontset_of(lang)) + 2 * offset
        assert need <= w, (name, label, round(need), w)
