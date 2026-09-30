#!/usr/bin/env python3
"""Independent SQLite expectations for every production lookup occurrence."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import time
from urllib.parse import quote

def shard(text):
    number=2166136261
    for b in text.encode():number=((number^b)*16777619)&0xffffffff
    return number%1024

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('database',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    if a.output.exists():raise SystemExit('Refusing existing expectations directory')
    a.output.mkdir(parents=True)
    db=sqlite3.connect('file:'+quote(str(a.database.resolve()))+'?mode=ro',uri=True)
    db.execute('PRAGMA cache_size=-80000')
    buffers=defaultdict(list);count=0;started=time.monotonic()
    def flush():
        for name,lines in buffers.items():
            with (a.output/(name+'.jsonl.gz')).open('ab') as f:f.write(gzip.compress(''.join(lines).encode(),mtime=0))
        buffers.clear()
    # Stored keys originate in the separately verified Python importer. Neither
    # the site exporter nor the JavaScript normalizer supplies expected values.
    for lang,text,eid,ordinal,fid,exact,reading,tolerant,spelling in db.execute('''
        SELECT s.lang,s.text,f.entry_id,f.ordinal,f.id,s.exact,s.reading,s.tolerant,s.spelling
        FROM surface s CROSS JOIN form_surface fs ON s.lang=fs.lang AND s.text=fs.surface
        CROSS JOIN form f ON f.id=fs.form_id ORDER BY s.id'''):
        buffers[f'{lang}-{shard(spelling):04d}'].append(json.dumps([text,eid,ordinal,fid,exact,reading,tolerant,spelling],ensure_ascii=False,separators=(',',':'))+'\n')
        count+=1
        if count%100000==0:flush()
    flush()
    report={'postings':count,'surfaces':db.execute('SELECT count(*) FROM surface').fetchone()[0], 'seconds':round(time.monotonic()-started,2)}
    (a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
