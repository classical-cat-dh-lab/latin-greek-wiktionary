#!/usr/bin/env python3
"""Inspect the compiled lookup projection; no runtime morphological analysis."""
import argparse
import json
from pathlib import Path
import sqlite3
from urllib.parse import quote
import zlib

import normalization as norm


def open_readonly(path):
    return sqlite3.connect('file:' + quote(str(Path(path).resolve())) + '?mode=ro', uri=True)


def lookup(db, word, lang, profile='tolerant'):
    if not norm.is_word(word, lang):
        return {'word': word, 'language': lang, 'status': 'not_a_single_word', 'matches': []}
    matches = {}
    for tier in norm.PROFILES[:norm.PROFILES.index(profile)+1]:
        rows = db.execute(f'''SELECT DISTINCT fs.form_id FROM surface s
            JOIN form_surface fs ON fs.lang=s.lang AND fs.surface=s.text
            WHERE s.lang=? AND s.{tier}=? ORDER BY fs.form_id''', (lang, norm.key(word, lang, tier)))
        for (fid,) in rows:
            matches.setdefault(fid, tier)
    output = []
    for fid, tier in matches.items():
        eid, ordinal, surface, role, grammar, table_id = db.execute('SELECT entry_id,ordinal,surface,role,grammar,table_id FROM form WHERE id=?', (fid,)).fetchone()
        context = db.execute('SELECT source,header,template FROM table_context WHERE id=?',(table_id,)).fetchone() if table_id else None
        entry = db.execute('SELECT source_line,word,headword,pos,role FROM entry WHERE id=?', (eid,)).fetchone()
        owners = []
        for root_id, path, state in db.execute('SELECT root_id,path,status FROM ownership WHERE entry_id=? ORDER BY root_id,path', (eid,)):
            head, pos = db.execute('SELECT headword,pos FROM entry WHERE id=?', (root_id,)).fetchone()
            senses = [{'ordinal': si, 'role': sr, 'glosses': json.loads(gloss), 'grammar': json.loads(g)} for si,sr,gloss,g in
                      db.execute('SELECT ordinal,role,glosses,grammar FROM sense WHERE entry_id=? ORDER BY ordinal', (root_id,))]
            owners.append({'entry_id': root_id, 'headword': head, 'pos': pos, 'path': json.loads(path), 'status': state, 'senses': senses})
        own_senses = [{'ordinal': si, 'role': sr, 'glosses': json.loads(gloss), 'grammar': json.loads(g)} for si,sr,gloss,g in
                      db.execute('SELECT ordinal,role,glosses,grammar FROM sense WHERE entry_id=? ORDER BY ordinal', (eid,))]
        output.append({'form_id': fid, 'entry_id': eid, 'source_line': entry[0], 'source_word': entry[1],
                       'headword': entry[2], 'pos': entry[3], 'entry_role': entry[4], 'form_ordinal': ordinal,
                       'source_surface': surface, 'form_role': role, 'match_tier': tier,
                       'table_context': dict(zip(('source','header','template'),context)) if context else None,
                       'grammar': json.loads(grammar), 'source_senses': own_senses, 'owners': owners})
    return {'word': word, 'language': lang, 'profile': profile, 'status': 'found' if output else 'not_found',
            'occurrences': len(output), 'matches': output}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('database', type=Path)
    p.add_argument('word')
    p.add_argument('--lang', choices=('la','grc'), required=True)
    p.add_argument('--profile', choices=norm.PROFILES, default='tolerant')
    a = p.parse_args()
    with open_readonly(a.database) as db:
        print(json.dumps(lookup(db, a.word, a.lang, a.profile), ensure_ascii=False, indent=2))
