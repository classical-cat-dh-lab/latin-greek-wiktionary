#!/usr/bin/env python3
"""Verify the full compiled capture and export complete, source-located residuals."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sqlite3
import time
import zlib

from build import js, sha
from lookup import open_readonly, lookup
import normalization as norm
import rules


def require(condition, message):
    if not condition:
        raise ValueError(message)


def explicit_link_count(value):
    count = 0; pending = [value]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            for key, child in item.items():
                if key == 'links':
                    require(isinstance(child,list), 'Unsupported source links shape')
                    for link in child:
                        require(isinstance(link,list) and len(link)==2 and all(isinstance(v,str) for v in link), 'Unsupported source link item')
                    count += len(child)
                else:
                    pending.append(child)
        elif isinstance(item,list):
            pending.extend(item)
    return count


def source_accounting(db):
    result = {}
    for sid, lang, expected_sha, byte_size, records in db.execute('SELECT id,lang,sha256,bytes,records FROM source ORDER BY id').fetchall():
        digest = hashlib.sha256(); actual_bytes = 0; counts = Counter()
        for line, row_sha, compressed in db.execute('SELECT source_line,raw_sha256,raw_zlib FROM entry WHERE source_id=? ORDER BY source_line',(sid,)):
            raw = zlib.decompress(compressed)
            require(hashlib.sha256(raw).hexdigest()==row_sha, f'Payload mismatch {lang}:{line}')
            digest.update(raw); actual_bytes += len(raw); e = json.loads(raw)
            require(line == counts['entries']+1 and e['lang_code']==lang, f'Source ordinal/language mismatch {lang}:{line}')
            counts['entries'] += 1; counts['senses'] += len(e['senses']); counts['forms'] += len(e.get('forms',[]))
            counts['links'] += explicit_link_count(e)
            for node in [e] + e['senses']:
                for kind in rules.RELATIONS:
                    counts['relations'] += len(node.get(kind,[]))
            if line % 300000 == 0: print(lang,line,'payloads verified',flush=True)
        require(digest.hexdigest()==expected_sha and actual_bytes==byte_size and counts['entries']==records, 'Full source round-trip failed')
        sql_counts = {
            'entries': db.execute('SELECT count(*) FROM entry WHERE source_id=?',(sid,)).fetchone()[0],
            'senses': db.execute('SELECT count(*) FROM sense s JOIN entry e ON e.id=s.entry_id WHERE e.source_id=?',(sid,)).fetchone()[0],
            'forms': db.execute('SELECT count(*) FROM form f JOIN entry e ON e.id=f.entry_id WHERE e.source_id=? AND f.ordinal>=0',(sid,)).fetchone()[0],
            'relations': db.execute('SELECT count(*) FROM relation r JOIN entry e ON e.id=r.entry_id WHERE e.source_id=?',(sid,)).fetchone()[0],
            'links': db.execute('SELECT count(*) FROM link_occurrence l JOIN entry e ON e.id=l.entry_id WHERE e.source_id=?',(sid,)).fetchone()[0],
        }
        require(dict(counts)==sql_counts, f'Projection accounting failed: {lang} {counts} {sql_counts}')
        result[f'{lang}:source-{sid}'] = {'raw_payloads_sha256': digest.hexdigest(), 'bytes': actual_bytes, 'counts':sql_counts,'status':'passed'}
    return result


def query_cases(db):
    result = []
    for lang, word in [('la','amātīs'),('la','amātus'),('la','amare'),('la','mālum'),('grc','λόγοις'),('grc','λελύκαμεν'),('grc','ἔργον'),('grc','ἀδευκής'),('grc','𐠞𐠪𐠐𐠵𐠩')]:
        start=time.perf_counter(); r=lookup(db,word,lang)
        require(r['status']=='found',f'Known lookup missed: {word}')
        item={'language':lang,'query':word,'occurrences':r['occurrences'],
              'roots':sorted({(o['headword'],o['pos']) for m in r['matches'] for o in m['owners']}),
              'diagnostic_query_ms':round((time.perf_counter()-start)*1000,3)}
        if word=='amātīs':
            paths=[o for m in r['matches'] if m['source_line']==7715 for o in m['owners']]
            require(any(o['headword']=='amō' and len(o['path'])>=3 for o in paths), 'Participle ownership path lost')
            item['participle_path_to_verb']='passed'
        if word=='amātus':
            require(any(p=='noun' for h,p in item['roots'] if h=='amātus'),'Independent noun lost')
            require(not any(h=='amātus' and p=='verb' for h,p in item['roots']),'Form-only participle became independent verb')
        if word=='ἀδευκής':
            require(any('uncertain' in ' '.join(s['glosses']) for m in r['matches'] for o in m['owners'] for s in o['senses']),'Uncertain definition lost')
        result.append(item)
    require(lookup(db,'amātus sum','la')['status']=='not_a_single_word','Phrase query admitted')
    return result


def reviewed_projections(db):
    """Compare compiled overlays with the pinned review, without projecting them."""
    path = Path(__file__).resolve().parents[1]/'evidence/source-repairs-20260930.json'
    expected = json.loads(path.read_text())['entries']
    require(json.loads(db.execute("SELECT value FROM meta WHERE key='source_repairs_sha256'").fetchone()[0]) == sha(path), 'Review pin mismatch')
    require(db.execute('SELECT count(*) FROM source_review').fetchone()[0] == len(expected), 'Review accounting mismatch')
    forms = senses = owners = 0
    for row in expected:
        eid, raw_hash = db.execute('SELECT id,raw_sha256 FROM entry WHERE source_id IN (1,2) AND lang=? AND source_line=?', (row['language'],row['source_line'])).fetchone()
        require(raw_hash == row['raw_sha256'], 'Review source identity mismatch')
        require(json.loads(db.execute('SELECT detail FROM source_review WHERE entry_id=?',(eid,)).fetchone()[0]) == row, 'Review provenance lost')
        for ordinal, patch in row['forms'].items():
            fid, role, grammar = db.execute('SELECT id,role,grammar FROM form WHERE entry_id=? AND ordinal=?', (eid,int(ordinal))).fetchone()
            require(role == patch['role'], 'Reviewed form role mismatch')
            require({r[0] for r in db.execute('SELECT surface FROM form_surface WHERE form_id=?',(fid,))} == set(patch['surfaces']), 'Reviewed surfaces mismatch')
            require(json.loads(grammar)['review_note'] == patch['note'], 'Reviewed form explanation lost')
            forms += 1
        for ordinal, patch in row['senses'].items():
            role, glosses, grammar = db.execute('SELECT role,glosses,grammar FROM sense WHERE entry_id=? AND ordinal=?',(eid,int(ordinal))).fetchone()
            if 'role' in patch: require(role == patch['role'], 'Reviewed sense role mismatch')
            if 'glosses' in patch: require(json.loads(glosses) == patch['glosses'], 'Reviewed source wording lost')
            if 'definition_status' in patch: require(json.loads(grammar)['definition_status'] == patch['definition_status'], 'Definition disposition lost')
            if patch.get('owner_targets'):
                targets = {r[0] for r in db.execute('''SELECT DISTINCT e.headword FROM relation r
                  JOIN relation_target t ON t.relation_id=r.id JOIN entry e ON e.id=t.entry_id
                  WHERE r.entry_id=? AND r.pointer LIKE ? AND r.kind='form_of' ''', (eid,f'/senses/{ordinal}/%'))}
                require(set(patch['owner_targets']) <= targets, 'Reviewed alternative owners lost')
                require(not db.execute("SELECT 1 FROM ownership WHERE entry_id=? AND status='unresolved_form'",(eid,)).fetchone(),'Reviewed alternatives still unresolved')
            for kind in patch.get('suppress',[]):
                require(not db.execute("SELECT 1 FROM relation WHERE entry_id=? AND pointer LIKE ? AND kind=? AND status!='source_explanation'",(eid,f'/senses/{ordinal}/%',kind)).fetchone(), 'False relation remained active')
            senses += 1
        for owner in row.get('owners',[]):
            target = db.execute('SELECT id FROM entry WHERE source_id IN (1,2) AND lang=? AND source_line=?',(owner['language'],owner['source_line'])).fetchone()[0]
            require(db.execute('SELECT 1 FROM reviewed_owner WHERE entry_id=? AND root_id=?',(eid,target)).fetchone(), 'Reviewed ownership missing')
            require(db.execute('SELECT 1 FROM ownership WHERE entry_id=? AND root_id=?',(eid,target)).fetchone(), 'Reviewed owner unreachable')
            owners += 1
    return dict(entries=len(expected),forms=forms,senses=senses,owners=owners,status='passed')


def beta_reviews(db):
    root = Path(__file__).resolve().parents[1]
    rows = json.loads((root/'evidence/beta-relation-review.json').read_text())['records']
    require(db.execute('SELECT count(*) FROM relation_review').fetchone()[0] == len(rows), 'Relation review accounting mismatch')
    counts = Counter()
    for disposition, detail, status in db.execute('SELECT v.disposition,v.detail,r.status FROM relation_review v JOIN relation r ON r.id=v.relation_id'):
        row = json.loads(detail)
        require(row in rows, 'Unrecognized relation review')
        if disposition == 'extraction_explanation_tail':
            require(status == 'source_explanation', 'Explanatory tail remained an active relation')
        if disposition == 'qualified_source_target':
            require(status in ('resolved_one','resolved_candidates'), 'Qualified target did not resolve')
        counts[disposition] += 1
    require(db.execute('SELECT count(*) FROM entry WHERE source_id=3').fetchone()[0] == 3, 'Supplement accounting mismatch')
    for word in ('κλῄζω','ἀνακόπτω','συνέχω'):
        require(lookup(db, word, 'grc')['status'] == 'found', 'Supplement not searchable: '+word)
    return dict(dispositions=dict(counts), supplemented_entries=3, status='passed')


def export_residuals(db, out):
    with (out/'issues.jsonl').open('w',encoding='utf-8') as stream:
        for issue_id, lang, line, word, pointer, kind, detail in db.execute('''SELECT i.id,e.lang,e.source_line,e.word,i.pointer,i.kind,i.detail
            FROM issue i LEFT JOIN entry e ON e.id=i.entry_id ORDER BY i.kind,e.lang,e.source_line,i.id'''):
            stream.write(js({'id':issue_id,'language':lang,'source_line':line,'word':word,'pointer':pointer,'kind':kind,'detail':json.loads(detail)})+'\n')
    with (out/'unresolved-relations.jsonl').open('w',encoding='utf-8') as stream:
        for rid, lang, line, word, ptr, kind, target, status in db.execute('''SELECT r.id,e.lang,e.source_line,e.word,r.pointer,r.kind,r.target,r.status
            FROM relation r JOIN entry e ON e.id=r.entry_id WHERE r.status IN ('unresolved','self_reference') ORDER BY e.lang,r.kind,r.target,r.id'''):
            stream.write(js(dict(zip(('id','language','source_line','word','pointer','kind','target','status'),(rid,lang,line,word,ptr,kind,target,status))))+'\n')
    with (out/'unresolved-links.jsonl').open('w',encoding='utf-8') as stream:
        for row in db.execute("SELECT id,target,page,lang,anchor,status FROM link WHERE status NOT IN ('local','local_page_anchor','local_form') ORDER BY id"):
            stream.write(js(dict(zip(('link_id','source_target','resolved_page','language','anchor','status'),row)))+'\n')
    with (out/'unresolved-ownership.jsonl').open('w',encoding='utf-8') as stream:
        for row in db.execute('''SELECT e.lang,e.source_line,e.word,e.id,o.status FROM ownership o JOIN entry e ON e.id=o.entry_id
                                WHERE o.status='unresolved_form' ORDER BY e.lang,e.source_line'''):
            stream.write(js(dict(zip(('language','source_line','word','entry_id','status'),row)))+'\n')


def verify(args):
    started=time.monotonic();args.output.mkdir(parents=True,exist_ok=True)
    with open_readonly(args.database) as db:
        require(db.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity failure')
        require(db.execute('PRAGMA foreign_key_check').fetchone() is None,'Foreign-key failure')
        accounting=source_accounting(db)
        reviews=reviewed_projections(db)
        beta=beta_reviews(db)
        require(db.execute("SELECT count(*) FROM relation WHERE status='pending'").fetchone()[0]==0,'Unprocessed relations')
        require(db.execute("SELECT count(*) FROM link WHERE status='pending'").fetchone()[0]==0,'Unprocessed links')
        require(db.execute('''SELECT count(*) FROM entry e WHERE NOT EXISTS(SELECT 1 FROM ownership o WHERE o.entry_id=e.id)''').fetchone()[0]==0,'Entry missing ownership disposition')
        require(db.execute('''SELECT count(*) FROM form_surface fs JOIN form f ON f.id=fs.form_id
            WHERE f.role IN ('metadata','prose_metadata','romanization','romanization_recovered','absence','pronunciation','periphrastic_formula','multiword_content')''').fetchone()[0]==0,'Non-word content entered lookup')
        require(db.execute('''SELECT count(*) FROM form_surface fs WHERE NOT EXISTS(SELECT 1 FROM surface s WHERE s.lang=fs.lang AND s.text=fs.surface)''').fetchone()[0]==0,'Admitted form has no index key')
        for eid, root, path in db.execute('SELECT entry_id,root_id,path FROM ownership'):
            ids=json.loads(path)
            require(ids[0]==eid and ids[-1]==root and len(ids)==len(set(ids)), 'Invalid ownership witness')
        e=db.execute("SELECT id FROM entry WHERE lang='grc' AND source_line=265").fetchone()[0]
        grammar=json.loads(db.execute('SELECT grammar FROM sense WHERE entry_id=? AND ordinal=0',(e,)).fetchone()[0])
        require(len(grammar.get('alternatives',[]))==2,'Correlated Greek reading lost')
        for lang,lines in [('la',(9,10,80,81)),('grc',(436,437))]:
            require(db.execute(f'SELECT count(*) FROM entry WHERE lang=? AND source_line IN ({",".join("?" for _ in lines)})',(lang,*lines)).fetchone()[0]==len(lines),'Repeated source identities collapsed')
        cases=query_cases(db)
        metrics={
            'entries_by_role':[list(r) for r in db.execute('SELECT lang,role,count(*) FROM entry GROUP BY lang,role ORDER BY lang,role')],
            'forms_by_role':[list(r) for r in db.execute('SELECT e.lang,f.role,count(*) FROM form f JOIN entry e ON e.id=f.entry_id GROUP BY e.lang,f.role ORDER BY e.lang,f.role')],
            'surfaces_by_language':dict(db.execute('SELECT lang,count(*) FROM surface GROUP BY lang')),
            'relations':[list(r) for r in db.execute('SELECT e.lang,r.kind,r.status,count(*) FROM relation r JOIN entry e ON e.id=r.entry_id GROUP BY e.lang,r.kind,r.status ORDER BY e.lang,r.kind,r.status')],
            'relation_target_edges':db.execute('SELECT count(*) FROM relation_target').fetchone()[0],
            'links_by_state':dict(db.execute('SELECT status,count(*) FROM link GROUP BY status')),
            'link_target_edges':db.execute('SELECT count(*) FROM link_target').fetchone()[0],
            'redirects_by_state':dict(db.execute('SELECT status,count(*) FROM redirect GROUP BY status')),
            'ownership_by_state':dict(db.execute('SELECT status,count(*) FROM ownership GROUP BY status')),
            'entries_by_ownership_state':dict(db.execute('SELECT status,count(DISTINCT entry_id) FROM ownership GROUP BY status')),
            'missing_links_by_declared_language':dict(db.execute("SELECT lang,count(*) FROM link WHERE status='missing_local_target' GROUP BY lang")),
            'applied_rules':dict(db.execute('SELECT rule,count(*) FROM change GROUP BY rule ORDER BY rule')),
            'issues':dict(db.execute('SELECT kind,count(*) FROM issue GROUP BY kind ORDER BY kind')),
            'correlated_grammar':dict(db.execute("SELECT json_extract(grammar,'$.interpretation'),count(*) FROM sense GROUP BY json_extract(grammar,'$.interpretation')")),
        }
        collisions={}
        for profile in norm.PROFILES:
            collisions[profile]=[list(r) for r in db.execute(f'''SELECT lang,count(*),max(n) FROM
                (SELECT lang,{profile},count(*) n FROM surface GROUP BY lang,{profile} HAVING count(*)>1) GROUP BY lang''')]
        export_residuals(db,args.output)
        report={'schema':'formlex-checkpoint/1','status':'passed','scope':'complete pinned-capture projection, not global Wiktionary completeness or scholarly certification',
                'database_bytes':args.database.stat().st_size,'database_sha256':sha(args.database),
                'verifier_sha256':sha(Path(__file__)),'source_accounting':accounting,'reviewed_projections':reviews,'beta_reviews':beta,'metrics':metrics,
                'normalization_collision_groups':collisions,'case_studies':cases,
                'verification_seconds':round(time.monotonic()-started,3),
                'limits':['Diagnostic local queries are not a browser performance benchmark.',
                          'Candidate targets are not disambiguated lexeme identities.',
                          'All source content is retained; unresolved source assertions remain explicit.',
                          'Other Wiktionary channels and historical rendered pages are not proven complete by this capture.'],
                'exports':{p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(args.output.glob('*.jsonl'))}}
        (args.output/'checkpoint.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({'status':report['status'],'metrics':metrics,'output':str(args.output)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('database',type=Path);p.add_argument('--output',type=Path,required=True)
    verify(p.parse_args())
