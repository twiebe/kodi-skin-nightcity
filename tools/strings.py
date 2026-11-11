"""Keep the translations in step with the English strings.

    python tools/strings.py todo [LANG ...]    what is to translate, as _build/strings/todo.tsv
    python tools/strings.py apply FILE.tsv     put translations in, the files in the English order

`todo` lists per language every English string the translation lacks and every one whose English
changed since it was translated (with the old English and the old translation), one tab-separated
line each, the texts as they are written in the .po files (escapes kept, no tabs): lang, id, English, translation (empty), old English, old translation, German (as a hint
to the meaning). Fill in the fourth column and hand the file to `apply`, which also takes a file
of three columns (lang, id, translation).

`apply` rewrites each translation in the order of en_gb: the English msgid of each id, the given
translation, else the one it had when its English is unchanged, else an empty msgstr (which
tests/static/test_translations.py reports). Ids the English no longer has are dropped. Run it
without a file (`apply -`) only to sort and drop.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
LANGUAGE = ROOT / 'language'
TODO = ROOT / '_build' / 'strings' / 'todo.tsv'
ENTRY = re.compile(r'msgctxt "#(\d+)"\nmsgid "((?:[^"\\]|\\.)*)"\nmsgstr "((?:[^"\\]|\\.)*)"')
HEADER = 'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n"Language: {}\\n"\n'
HINT = 'de_de'


def po(lang):
    return LANGUAGE / 'resource.language.{}'.format(lang) / 'strings.po'


def entries(lang):
    """[(id, msgid, msgstr)] of a language's file, in its order."""
    return ENTRY.findall(po(lang).read_text(encoding='utf-8'))


def languages():
    return sorted(p.parent.name.split('.')[-1] for p in LANGUAGE.glob('*/strings.po')
                  if p.parent.name != 'resource.language.en_gb')


def todo(langs):
    english = entries('en_gb')
    hint = {i: tr for i, _, tr in entries(HINT)}
    rows = []
    for lang in langs or languages():
        have = {i: (en, tr) for i, en, tr in entries(lang)}
        for i, en, _ in english:
            old_en, old_tr = have.get(i, ('', ''))
            if i not in have or old_en != en or not old_tr:
                rows.append([lang, i, en, '', old_en if old_en != en else '', old_tr,
                             hint.get(i, '') if lang != HINT else ''])
    TODO.parent.mkdir(parents=True, exist_ok=True)
    lines = [['lang', 'id', 'english', 'translation', 'old english', 'old translation', HINT]] + rows
    TODO.write_text(''.join('\t'.join(row) + '\n' for row in lines), encoding='utf-8')
    counts = {}
    for row in rows:
        counts[row[0]] = counts.get(row[0], 0) + 1
    print('{} to translate in {} languages: {}'.format(len(rows), len(counts), TODO.relative_to(ROOT)))
    for lang, n in sorted(counts.items()):
        print('  {} {}'.format(lang, n))
    return 0


def read(path):
    """{(lang, id): translation} of a todo file filled in, or of lang, id, translation lines."""
    given = {}
    for line in pathlib.Path(path).read_text(encoding='utf-8').splitlines():
        row = line.split('\t')
        if not line.strip() or row[0] == 'lang':
            continue
        translation = row[3] if len(row) > 4 else row[2] if len(row) > 2 else ''
        if translation:
            given[(row[0], row[1])] = translation
    return given


def render(lang, english=None, given=None):
    """The file of LANG as apply writes it: English order and msgids, GIVEN ({(lang, id): text})
    over what it had, a translation of an English that changed since left out."""
    english = english or entries('en_gb')
    given = given or {}
    have = {i: (en, tr) for i, en, tr in entries(lang)}
    out = [HEADER.format(lang)]
    for i, en, _ in english:
        old_en, old_tr = have.get(i, ('', ''))
        tr = given.get((lang, i)) or (old_tr if old_en == en else '')
        out.append('msgctxt "#{}"\nmsgid "{}"\nmsgstr "{}"\n'.format(i, en, tr))
    return '\n'.join(out)


def apply(path):
    english = entries('en_gb')
    given = read(path) if path != '-' else {}
    unknown = sorted({lang for lang, _ in given} - set(languages()))
    if unknown:
        print('no translation file for: ' + ', '.join(unknown))
        return 1
    empty = 0
    for lang in languages():
        text = render(lang, english, given)
        empty += text.count('msgstr ""\n') - 1  # the header's
        po(lang).write_text(text, encoding='utf-8')
    print('{} translations put in; {} strings still without one'.format(len(given), empty))
    return 1 if empty else 0


def main(args):
    if args[:1] == ['todo']:
        return todo(args[1:])
    if args[:1] == ['apply'] and len(args) == 2:
        return apply(args[1])
    print(__doc__)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
