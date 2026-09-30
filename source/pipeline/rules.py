"""Source-qualified projections with preserved originals and bounded repairs."""
import re
import unicodedata as ud
from normalization import nfc, quantity, is_word, script_letters, language_letters

VERSION = 'source-rules-v3'
META = {'table-tags', 'inflection-template', 'class'}
ABSENT = {'', '-', '—', '–', '?'}
TENSES = {'present', 'imperfect', 'future', 'aorist', 'perfect', 'pluperfect', 'future-perfect', 'preterite', 'past'}
MOODS = {'indicative', 'subjunctive', 'optative', 'imperative'}
CONJ = {'grc-conj', 'grc-conj-έω', 'grc-conj-ίζω', 'grc-conj-άζω', 'grc-conj-όω'}
RELATIONS = ('form_of', 'alt_of', 'synonyms', 'antonyms', 'derived', 'related',
             'hypernyms', 'hyponyms', 'holonyms', 'meronyms', 'coordinate_terms',
             'proverbs', 'abbreviations')
ARTICLES = {quantity(s) for s in 'ὁ ἡ τό τὸ τοῦ τῆς τῷ τῇ τόν τὸν τήν τὴν οἱ αἱ τά τὰ τῶν τοῖς ταῖς τούς τοὺς τάς τὰς τώ τὼ τοῖν'.split()}
DIMENSIONS = {
    'person': {'first-person', 'second-person', 'third-person'},
    'number': {'singular', 'dual', 'plural'},
    'case': {'nominative', 'genitive', 'dative', 'accusative', 'ablative', 'vocative', 'locative'},
    'gender': {'masculine', 'feminine', 'neuter', 'common-gender'},
    'voice': {'active', 'middle', 'passive'},
}


def grammar(tags, glosses=()):
    """Keep correlations explicit; do not enumerate feature cross products."""
    result = {'tags': list(tags), 'interpretation': 'source_bundle'}
    pair = r'(?:first-person|second-person|third-person)\s+(?:singular|dual|plural)'
    prefix = re.match(r'^(' + pair + r'(?:/' + pair + r')+)\s+(?:present|imperfect|future|aorist|perfect|pluperfect|active|middle|passive)', glosses[0]) if len(glosses) == 1 else None
    pairs = re.findall(r'(first-person|second-person|third-person)\s+(singular|dual|plural)', prefix[1]) if prefix else []
    dimensions = DIMENSIONS['person'] | DIMENSIONS['number']
    if len(set(pairs)) > 1 and {v for p in pairs for v in p} == set(tags) & dimensions:
        common = set(tags) - DIMENSIONS['person'] - DIMENSIONS['number']
        result['alternatives'] = [sorted(common | {p, n}) for p, n in dict.fromkeys(pairs)]
        result['interpretation'] = 'explicit_person_number_alternatives'
    elif sum(len(set(tags) & d) > 1 for d in DIMENSIONS.values()) > 1:
        result['interpretation'] = 'bundle_not_cartesian'
    return result


def context_tense(header, template):
    if template not in CONJ:
        return None, []
    terms = set((header or '').replace('future perfect', 'future-perfect').split()) & TENSES
    if len(terms) == 1:
        return next(iter(terms)), []
    # Qualified against the source table headings, not the order of extracted tags.
    special = {
        frozenset({'perfect', 'present'}): ('perfect', ['present']),
        frozenset({'pluperfect', 'imperfect'}): ('pluperfect', ['imperfect']),
        frozenset({'present', 'future'}): ('present', ['future']),
        frozenset({'pluperfect', 'present', 'imperfect'}): ('pluperfect', ['present', 'imperfect']),
    }
    return special.get(frozenset(terms), (None, []))


def project_form(form, entry, context):
    value = form['form']; tags = list(form.get('tags', [])); tagset = set(tags)
    changes = []; issues = []; features = grammar(tags)
    template = context.get('template') if context else None
    same_table = context is not None and context.get('source') == form.get('source')
    if META & tagset:
        return 'metadata', [], features, changes, issues
    if 'romanization' in tagset:
        return 'romanization', [], features, changes, issues
    if value in ABSENT:
        return 'absence', [], features, changes, issues
    if value.startswith('/') and value.endswith('/'):
        return 'pronunciation', [], features, changes, issues
    if ' + ' in value:
        return 'periphrastic_formula', [], features, changes, issues
    if 'infinitive' in tagset and same_table and template in CONJ | {'la-conj'}:
        bad = tagset & (DIMENSIONS['person'] | DIMENSIONS['number'])
        if bad:
            tagset -= bad
            features = grammar(sorted(tagset))
            changes.append('infinitive_finite_tags_removed')
    if entry['lang_code'] == 'grc' and same_table and template in CONJ:
        tense, meaning = context_tense(context['header'], template)
        if tense and not tagset & TENSES:
            features['tags'] = sorted(tagset | {tense})
            features['tense_source'] = 'table_header'
            changes.append('greek_table_tense')
            if meaning:
                features['tense_meaning'] = meaning
                changes.append('tense_meaning_separated')
        elif not tense and tagset & MOODS and not tagset & TENSES:
            issues.append('unresolved_table_tense')
    elif entry['pos'] == 'verb' and tagset & MOODS and not tagset & TENSES:
        issues.append('unresolved_table_tense')
    if any(t.startswith('error-') for t in tags):
        issues.append('source_error_tag')
    lang = entry['lang_code']
    if lang == 'grc' and value in {'first','third','third declension','declension','irregular declension','Attic declension','first declension.','Ionic','Doric','Epic','Attic','uncontracted','and','n'}:
        changes.append('head_metadata_separated')
        return 'prose_metadata', [], features, changes, issues
    if lang == 'la' and re.match(r'^(?:First|Second|Third|Fourth|Fifth)-declension noun\b',value):
        changes.append('table_prose_separated')
        return 'prose_metadata', [], features, changes, issues
    if lang == 'grc' and any(c.isalpha() for c in value) and not language_letters(value, lang):
        if same_table and template and template.startswith('grc-') and script_letters(value, 'LATIN'):
            changes.append('leaked_romanization_separated')
            return 'romanization_recovered', [], features, changes, issues
        issues.append('foreign_or_unclassified_surface')
        return 'foreign_text', [], features, changes, issues
    if lang == 'grc' and script_letters(value, 'GREEK') and re.search('[a-zA-Z]', value):
        # Bounded suffix labels; never rewrite mixed-script letters inside a word.
        decorated = re.fullmatch(r'(.+?)\s+(?:(?:[mfn] )?with movable nu|Epic|Medieval|[mfn]\.?|\([mfn]\))', value)
        if decorated and is_word(decorated[1],lang) and not script_letters(decorated[1],'LATIN'):
            features['source_label'] = value[len(decorated[1]):].strip()
            changes.append('surface_label_separated')
            return 'labelled_word', [decorated[1]], features, changes, issues
        if value.startswith('-'):
            return 'affix', [], features, changes, issues
        issues.append('mixed_script_surface')
        return 'mixed_script', [], features, changes, issues
    candidate = value
    if lang == 'grc' and same_table and template == 'grc-decl' and not any(c.isspace() for c in entry['word']):
        bits = value.split()
        links = {quantity(v[0]) for v in form.get('links', []) if isinstance(v, list) and len(v) == 2}
        if len(bits) == 2 and quantity(bits[0]) in ARTICLES and all(quantity(b) in links for b in bits):
            candidate = bits[1]
            features['article_wrapper'] = bits[0]
            changes.append('greek_article_wrapper')
    movable = re.fullmatch(r'(.+)\(ν\)', candidate) if lang == 'grc' else None
    if movable and is_word(movable[1], lang):
        changes.append('explicit_movable_nu')
        return 'word_notation', [movable[1], movable[1] + 'ν'], features, changes, issues
    if is_word(candidate, lang):
        if '\u00ad' in candidate:
            changes.append('soft_hyphen_retrieval_only')
        return ('article_wrapped_word' if candidate != value else 'word'), [candidate], features, changes, issues
    if '(' in value or ')' in value:
        issues.append('unclassified_parenthesized_surface')
        return 'parenthesized_content', [], features, changes, issues
    if any(c.isspace() for c in value):
        return 'multiword_content', [], features, changes, issues
    if value.startswith('*'):
        return 'reconstruction', [], features, changes, issues
    if value.startswith('-') or value.endswith('-'):
        return 'affix', [], features, changes, issues
    if any(ud.category(c) in {'Cc', 'Cf'} for c in value):
        issues.append('control_character_surface')
    return 'symbol_or_other', [], features, changes, issues


def project_sense(sense, suppressed=False):
    tags = sense.get('tags', [])
    if suppressed:
        tags = [t for t in tags if t not in ('form-of', 'alt-of')]
    glosses = sense.get('glosses', [])
    origin = 'glosses'
    if not glosses:
        glosses = sense.get('raw_glosses', [])
        origin = 'raw_glosses'
    if not glosses and sense.get('qualifier'):
        glosses = [sense['qualifier']]; origin = 'qualifier'
    role = 'lexical' if suppressed else 'form' if sense.get('form_of') else 'variant' if sense.get('alt_of') else 'lexical' if glosses else 'incomplete'
    return role, glosses, origin if glosses else 'missing', grammar(tags, glosses)


def explicit_links(value, pointer=''):
    """Yield every links-array occurrence, retaining its full source pointer."""
    if isinstance(value, dict):
        for k, v in value.items():
            path = pointer + '/' + k.replace('~', '~0').replace('/', '~1')
            if k == 'links' and isinstance(v, list):
                for i, item in enumerate(v):
                    if isinstance(item, list) and len(item) == 2 and all(isinstance(x, str) for x in item):
                        yield path + '/' + str(i), item[0], item[1]
            else:
                yield from explicit_links(v, path)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from explicit_links(v, pointer + '/' + str(i))
