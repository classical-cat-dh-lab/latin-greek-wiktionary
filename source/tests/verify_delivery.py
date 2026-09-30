#!/usr/bin/env python3
"""Verify every delivered record, relationship and byte against SQLite/source text."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import quote
import zlib

MEDIA={'audio','ogg_url','mp3_url','wav_url','flac_url','video','image','images','videos','audio_url','ogg','mp3','spectrogram','waveform'}
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def check_text(source, delivered, counts):
    if isinstance(source,dict):
        assert set(delivered)==set(source)-MEDIA
        for k,v in source.items():
            if k in MEDIA:counts['excluded_media_fields']+=1
            else:check_text(v,delivered[k],counts)
    elif isinstance(source,list):
        assert len(source)==len(delivered)
        for a,b in zip(source,delivered):check_text(a,b,counts)
    else:
        assert source==delivered
        counts['retained_content_values']+=1

def same(actual,expected,name):
    assert sorted(map(canonical,actual))==sorted(map(canonical,expected)),name

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('database',type=Path);p.add_argument('site',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    start=time.monotonic();m=json.loads((a.site/'manifest.json').read_text());counts=Counter();failures=[]
    db=sqlite3.connect('file:'+quote(str(a.database.resolve()))+'?mode=ro',uri=True);db.execute('PRAGMA cache_size=-100000')
    db.execute('CREATE TEMP TABLE ctx AS SELECT * FROM table_context');db.execute('CREATE INDEX temp.ctx_entry ON ctx(entry_id)')
    for file in m['files']:
        b=(a.site/file['path']).read_bytes();assert len(b)==file['bytes'];assert hashlib.sha256(b).hexdigest()==file['sha256'];counts['verified_files']+=1
        if not file['path'].startswith('data/entries/'):continue
        entries=json.loads(gzip.decompress(b));ids=list(map(int,entries));lo,hi=min(ids),max(ids)
        raw=list(db.execute('SELECT id,lang,word,page,pos,headword,role,source_line,etymology,raw_zlib FROM entry WHERE id BETWEEN ? AND ? ORDER BY id',(lo,hi)))
        assert ids==[r[0] for r in raw]
        for eid,lang,word,page,pos,head,role,line,etym,blob in raw:
            e=entries[str(eid)];assert [e[k] for k in ['id','lang','word','page','pos','headword','role','sourceLine','etymology']]==[eid,lang,word,page,pos,head,role,line,etym]
            check_text(json.loads(zlib.decompress(blob)),e['content'],counts);counts['entries']+=1
            source_hash,record_hash=db.execute('SELECT s.sha256,e.raw_sha256 FROM entry e JOIN source s ON s.id=e.source_id WHERE e.id=?',(eid,)).fetchone()
            locator=f'sha256:{source_hash}/line/{line}'
            assert e['contract']=='lexical-entry/1'
            assert e['identity']==dict(locator=locator,sourceSha256=source_hash,recordSha256=record_hash,pointer='')
            assert e['etymologyGroup']['number']==etym
            assert e['etymologyGroup']['text']==e['content'].get('etymology_text','')
            assert e['pronunciations']==e['content'].get('sounds',[])
            for s in e['senses']:
                original=e['content']['senses'][s['ordinal']]
                assert s['glossPath']==s['glosses'] and s['parentKey'] is None
                assert s['key']==locator+f"/senses/{s['ordinal']}"
                assert s['sourceGlosses']==original.get('raw_glosses',original.get('glosses',[]))
                assert s['examples']==original.get('examples',[])
                counts['semantic_senses']+=1
            assert e['lexicalRelations']==[dict(pointer=r[0],kind=r[1],targetText=r[2],qualifiers=r[3],status=r[4],targetIds=r[5]) for r in e['relations']]
            assert e['internalLinks']==[dict(pointer=l[0],label=l[1],targetText=l[2],status=l[3],targetIds=l[4]) for l in e['links']]
        actual=[[e['id'],e['review']] for e in entries.values() if 'review' in e]
        expected=[[eid,json.loads(detail)] for eid,detail in db.execute('SELECT entry_id,detail FROM source_review WHERE entry_id BETWEEN ? AND ?',(lo,hi))]
        same(actual,expected,'source reviews');counts['source_reviews']+=len(actual)
        actual=[]
        for e in entries.values():
            for s in e['senses']:actual.append([e['id'],s['ordinal'],s['role'],s['glosses'],s['origin'],s['grammar']])
        expected=[[eid,o,r,json.loads(g),d,json.loads(t)] for eid,o,r,g,d,t in db.execute('SELECT entry_id,ordinal,role,glosses,display_origin,grammar FROM sense WHERE entry_id BETWEEN ? AND ?',(lo,hi))]
        same(actual,expected,'senses');counts['senses']+=len(actual)
        actual=[[f[0],e['id'],*f[1:]] for e in entries.values() for f in e['forms']]
        expected=[[*r[:-1],json.loads(r[-1])] for r in db.execute('SELECT * FROM form WHERE entry_id BETWEEN ? AND ?',(lo,hi))]
        same(actual,expected,'forms');counts['forms']+=len(actual)
        actual=[[int(tid),e['id'],t['source'],t['header'],t['template']] for e in entries.values() for tid,t in e['tables'].items()]
        expected=[list(r) for r in db.execute('SELECT id,entry_id,source,header,template FROM ctx WHERE entry_id BETWEEN ? AND ?',(lo,hi))]
        same(actual,expected,'tables');counts['tables']+=len(actual)
        actual=[[e['id'],o['id'],o['depth'],o['path'],o['status']] for e in entries.values() for o in e['owners']]
        expected=[[eid,r,d,json.loads(path),status] for eid,r,d,path,status in db.execute('SELECT * FROM ownership WHERE entry_id BETWEEN ? AND ?',(lo,hi))]
        same(actual,expected,'ownership');counts['ownership_paths']+=len(actual)
        actual=[[e['id'],*l] for e in entries.values() for l in e['links']]
        expected=[]
        for eid,pointer,label,target,status,targets in db.execute('''SELECT o.entry_id,o.pointer,o.label,l.target,l.status,(SELECT json_group_array(t.entry_id) FROM link_target t WHERE t.link_id=l.id) FROM link_occurrence o JOIN link l ON o.link_id=l.id WHERE o.entry_id BETWEEN ? AND ?''',(lo,hi)):
            expected.append([eid,pointer,label,target,status,json.loads(targets)])
        same(actual,expected,'links');counts['link_occurrences']+=len(actual)
        actual=[[e['id'],*r] for e in entries.values() for r in e['relations']]
        expected=[]
        for eid,pointer,kind,target,hints,status,targets in db.execute('''SELECT r.entry_id,r.pointer,r.kind,r.target,r.hints,r.status,(SELECT json_group_array(t.entry_id) FROM relation_target t WHERE t.relation_id=r.id) FROM relation r WHERE entry_id BETWEEN ? AND ?''',(lo,hi)):
            expected.append([eid,pointer,kind,target,json.loads(hints),status,json.loads(targets)])
        same(actual,expected,'relations');counts['relations']+=len(actual)
        if counts['entries']%128000==0:print(dict(counts),flush=True)
    assert counts['entries']==db.execute('SELECT count(*) FROM entry').fetchone()[0]
    expected_files={f['path'] for f in m['files']}|{'manifest.json'}
    assert expected_files=={p.relative_to(a.site).as_posix() for p in a.site.rglob('*') if p.is_file()}
    lock=json.loads((a.site/'design-system.lock.json').read_text())
    for path,digest in lock['files'].items():assert hashlib.sha256((a.site/lock['path']/path).read_bytes()).hexdigest()==digest
    result={'pass':True,'package':m['package'],'counts':dict(counts),'bytes':m['bytes'],'expandedBytes':m['expandedBytes'],'largestExpandedShard':max(f.get('expandedBytes',0) for f in m['files']),'seconds':round(time.monotonic()-start,2)}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
