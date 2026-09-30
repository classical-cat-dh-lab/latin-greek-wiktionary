"""Versioned retrieval keys; these are not lexical identity keys."""
import unicodedata as ud

VERSION = 'word-lookup-v2'
PROFILES = ('exact', 'reading', 'tolerant', 'spelling')
QUANTITY = frozenset('\u0304\u0306')
ACCENTS = frozenset('\u0300\u0301\u0342\u0313\u0314')
APOSTROPHES = str.maketrans({'’': "'", 'ʼ': "'", '᾽': "'"})


def nfc(value):
    return ud.normalize('NFC', value)


def quantity(value):
    """Strict source alias: preserve case and every non-quantity distinction."""
    return nfc(''.join(c for c in ud.normalize('NFD', value) if c not in QUANTITY))


def key(value, language, profile='tolerant'):
    if language not in ('la', 'grc') or profile not in PROFILES:
        raise ValueError('Unsupported language or normalization profile')
    value = value.replace('\u00ad', '')
    if profile == 'exact':
        return nfc(value)
    value = ud.normalize('NFD', value).lower().translate(APOSTROPHES)
    drop = QUANTITY | (ACCENTS if language == 'grc' and profile in ('tolerant', 'spelling') else set())
    value = ''.join(c for c in value if c not in drop)
    if language == 'grc':
        value = value.replace('ς', 'σ')
    elif profile == 'spelling':
        value = value.replace('j', 'i').replace('v', 'u')
    return nfc(value)


def script_letters(value, script):
    return any(script in ud.name(c, '') for c in value if c.isalpha())


def language_letters(value, language):
    scripts = ('GREEK', 'CYPRIOT', 'LINEAR B') if language == 'grc' else ('LATIN', 'OLD ITALIC')
    return any(script_letters(value, script) for script in scripts)


def is_word(value, language):
    """Admit literal tokens; affixes, reconstructions and symbols remain content."""
    value = value.replace('\u00ad', '')
    start = value.lstrip("'’ʼ᾽")
    if not start or not start[0].isalpha():
        return False
    if any(c.isspace() or ud.category(c)[0] in 'CNZ' for c in value):
        return False
    if not language_letters(value, language):
        return False
    return all(c.isalpha() or ud.category(c).startswith('M') or c in "-'’ʼ᾽." for c in value)
