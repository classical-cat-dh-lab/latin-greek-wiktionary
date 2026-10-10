"""Versioned semantic projection shared by the reader and reusable data export."""
from urllib.parse import quote

CONTRACT = 'lexical-entry/1'
VERSION = '0.1.1'


def attach_model(entry, source_hash, raw_hash):
    """Expose source distinctions without inferring an unsupported sense tree."""
    raw = entry['content']
    locator = f"sha256:{source_hash}/line/{entry['sourceLine']}"
    entry['contract'] = CONTRACT
    entry['identity'] = {'locator': locator, 'sourceSha256': source_hash,
                         'recordSha256': raw_hash, 'pointer': ''}
    witness = raw.get('source_witness', {})
    entry['provenance'] = {
        'source': 'English Wiktionary',
        'acquisition': witness.get('kind', 'kaikki_capture'),
        'pageUrl': 'https://en.wiktionary.org/wiki/' + quote(entry['page']) +
                   ('#Latin' if entry['lang'] == 'la' else '#Ancient_Greek'),
        'revision': witness.get('revision'), 'revisionUrl': witness.get('url'),
        'captureDate': witness.get('render_capture', '2026-09-20'),
    }
    # Missing etymology numbering is unknown, not authority to merge entries.
    entry['etymologyGroup'] = {'language': entry['lang'], 'page': entry['page'],
        'number': entry['etymology'], 'grouping': 'source_number' if entry['etymology'] is not None else 'unassigned',
        'text': raw.get('etymology_text', '')}
    entry['pronunciations'] = raw.get('sounds', [])
    entry['metadata'] = {k: v for k, v in raw.items() if k not in
        {'word', 'lang', 'lang_code', 'pos', 'senses', 'forms', 'etymology_text', 'sounds'}}
    for sense in entry['senses']:
        source = raw.get('senses', [])[sense['ordinal']]
        sense['key'] = locator + f"/senses/{sense['ordinal']}"
        sense['glossPath'] = list(sense['glosses'])
        sense['hierarchy'] = 'ordered_source_gloss_path'
        sense['parentKey'] = None
        sense['sourceGlosses'] = source.get('raw_glosses', source.get('glosses', []))
        sense['examples'] = source.get('examples', [])
        sense['annotations'] = {k: v for k, v in source.items() if k not in
            {'glosses', 'raw_glosses', 'tags', 'examples', 'form_of', 'alt_of'}}
        sense['definitionStatus'] = sense['grammar'].get('definition_status',
            'available' if sense['glosses'] else 'source_unspecified')
    entry['lexicalRelations'] = [dict(pointer=r[0], kind=r[1], targetText=r[2],
        qualifiers=r[3], status=r[4], targetIds=r[5]) for r in entry['relations']]
    entry['internalLinks'] = [dict(pointer=l[0], label=l[1], targetText=l[2],
        status=l[3], targetIds=l[4]) for l in entry['links']]
    return entry
