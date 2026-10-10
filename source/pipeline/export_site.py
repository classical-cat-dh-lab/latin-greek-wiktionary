#!/usr/bin/env python3
"""Compile a bounded-memory, static text dictionary from the verified database."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import time
import zlib

from lookup import open_readonly
from normalization import VERSION
from entry_model import attach_model, CONTRACT, VERSION as RELEASE_VERSION

HERE = Path(__file__).resolve().parents[1]
BLOCK = 256
BUCKETS = 1024
MEDIA = {'audio', 'ogg_url', 'mp3_url', 'wav_url', 'flac_url', 'video', 'image',
         'images', 'videos', 'audio_url', 'ogg', 'mp3', 'spectrogram', 'waveform'}


def js(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bucket(value):
    h = 2166136261
    for byte in value.encode('utf-8'):
        h = ((h ^ byte) * 16777619) & 0xffffffff
    return h % BUCKETS


def text_content(value):
    """Keep every non-media field; the renderer treats all strings as text."""
    if isinstance(value, dict):
        return {k: text_content(v) for k, v in value.items() if k not in MEDIA}
    if isinstance(value, list):
        return [text_content(v) for v in value]
    return value


def compile_entries(db, first, last):
    entries = {}
    for r in db.execute('SELECT id,lang,word,page,pos,headword,role,source_line,etymology,raw_zlib FROM entry WHERE id BETWEEN ? AND ? ORDER BY id', (first, last)):
        eid, lang, word, page, pos, head, role, line, etym, raw = r
        entries[str(eid)] = dict(id=eid, lang=lang, word=word, page=page, pos=pos,
            headword=head, role=role, sourceLine=line, etymology=etym,
            content=text_content(json.loads(zlib.decompress(raw))),
            senses=[], forms=[], tables={}, owners=[], links=[], relations=[])
    for eid, detail in db.execute('SELECT entry_id,detail FROM source_review WHERE entry_id BETWEEN ? AND ?', (first, last)):
        entries[str(eid)]['review'] = json.loads(detail)
    for _, eid, ordinal, role, gloss, origin, grammar in db.execute('SELECT * FROM sense WHERE entry_id BETWEEN ? AND ? ORDER BY id', (first, last)):
        entries[str(eid)]['senses'].append(dict(ordinal=ordinal, role=role, glosses=json.loads(gloss), origin=origin, grammar=json.loads(grammar)))
    for fid, eid, ordinal, surface, role, table, grammar in db.execute('SELECT * FROM form WHERE entry_id BETWEEN ? AND ? ORDER BY id', (first, last)):
        entries[str(eid)]['forms'].append([fid, ordinal, surface, role, table, json.loads(grammar)])
    for tid, eid, ordinal, source, header, template in db.execute('SELECT t.* FROM entry e JOIN ctx t ON t.entry_id=e.id WHERE e.id BETWEEN ? AND ? ORDER BY t.id', (first, last)):
        entries[str(eid)]['tables'][str(tid)] = dict(source=source, header=header, template=template)
    for eid, root, depth, path, status in db.execute('SELECT * FROM ownership WHERE entry_id BETWEEN ? AND ? ORDER BY entry_id,root_id', (first, last)):
        entries[str(eid)]['owners'].append(dict(id=root, depth=depth, path=json.loads(path), status=status))
    # Distinct occurrences remain attached to their source pointer, even when a
    # link is repeated. Target sets carry the database's resolution, not a guess.
    for eid, pointer, label, lid, target, status, targets in db.execute('''SELECT o.entry_id,o.pointer,o.label,l.id,l.target,l.status,
        (SELECT json_group_array(t.entry_id) FROM link_target t WHERE t.link_id=l.id)
        FROM link_occurrence o JOIN link l ON l.id=o.link_id
        WHERE o.entry_id BETWEEN ? AND ? ORDER BY o.entry_id,o.rowid''', (first, last)):
        entries[str(eid)]['links'].append([pointer, label, target, status, json.loads(targets)])
    for rid, eid, sid, pointer, kind, target, hints, status, targets in db.execute('''SELECT r.*,
        (SELECT json_group_array(t.entry_id) FROM relation_target t WHERE t.relation_id=r.id)
        FROM relation r WHERE entry_id BETWEEN ? AND ? ORDER BY id''', (first, last)):
        entries[str(eid)]['relations'].append([pointer, kind, target, json.loads(hints), status, json.loads(targets)])
    for eid, rid, disposition, detail in db.execute('''SELECT r.entry_id,v.relation_id,v.disposition,v.detail
        FROM relation_review v JOIN relation r ON r.id=v.relation_id WHERE r.entry_id BETWEEN ? AND ?''', (first, last)):
        entries[str(eid)].setdefault('relationReviews', []).append(
            dict(relationId=rid, disposition=disposition, evidence=json.loads(detail)))
    for eid, source_hash, raw_hash in db.execute('''SELECT e.id,s.sha256,e.raw_sha256 FROM entry e
        JOIN source s ON s.id=e.source_id WHERE e.id BETWEEN ? AND ?''', (first, last)):
        attach_model(entries[str(eid)], source_hash, raw_hash)
    return entries


def package_shell(output, edition, data_files):
    # A repair on the same upstream capture must still change the worker bytes.
    # Include both the data projection and authored shell, without a hash cycle.
    inputs = {p.relative_to(HERE/'site').as_posix(): digest(p.read_bytes())
              for p in sorted((HERE/'site').rglob('*')) if p.is_file()}
    build = digest(js([data_files, inputs]).encode())[:20]
    for p in (HERE/'site').rglob('*'):
        if p.is_file():
            dest = output/p.relative_to(HERE/'site')
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, dest)
    # Embed the fixed edition in the service worker. This increment does not
    # choose a rolling-update policy or activate a different data edition.
    sw = output/'sw.js'
    sw.write_text(sw.read_text().replace('__EDITION__', edition).replace('__BUILD__', build))
    return build


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('database', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--shell-only', action='store_true')
    a = ap.parse_args()
    started = time.monotonic()
    if a.shell_only:
        manifest = json.loads((a.output/'manifest.json').read_text())
        manifest['files'] = [f for f in manifest['files'] if f['path'].startswith('data/')]
    else:
        if a.output.exists():
            raise SystemExit('Refusing to overwrite an existing package')
        a.output.mkdir(parents=True)
        db = open_readonly(a.database)
        db.execute('PRAGMA cache_size=-100000')
        # A read-only connection cannot add the missing table-context index;
        # load this small context table once rather than rescan it per block.
        db.execute('CREATE TEMP TABLE ctx AS SELECT * FROM table_context')
        db.execute('CREATE INDEX temp.ctx_entry ON ctx(entry_id)')
        manifest = dict(schema=1, version=RELEASE_VERSION, contract=CONTRACT, apiVersion=1, block=BLOCK, buckets=BUCKETS,
            normalization=VERSION, files=[], counts={},
            sources=[dict(zip(['language','sha256','bytes','records'], r)) for r in db.execute('SELECT lang,sha256,bytes,records FROM source')])
        manifest['edition'] = 'capture-20260920-reviewed-' + digest(js(manifest['sources']).encode())[:12]
        def write_gzip(path, value):
            dest = a.output/path
            dest.parent.mkdir(parents=True, exist_ok=True)
            payload = js(value).encode()
            data = gzip.compress(payload, compresslevel=6, mtime=0)
            dest.write_bytes(data)
            manifest['files'].append(dict(path=path, bytes=len(data), sha256=digest(data), expandedBytes=len(payload)))
        # Accumulate only one hash bucket's worth per flush. Scratch lines are
        # outside the distributable package and never enter offline storage.
        temp = a.output.parent/(a.output.name+'-index-work')
        temp.mkdir()
        buffers = defaultdict(list)
        count = 0
        for lang, surface, spelling, eid, ordinal, fid in db.execute('''SELECT s.lang,s.text,s.spelling,f.entry_id,f.ordinal,f.id
            FROM surface s CROSS JOIN form_surface fs ON fs.lang=s.lang AND fs.surface=s.text
            CROSS JOIN form f ON f.id=fs.form_id ORDER BY s.id'''):
            path = f'{lang}-{bucket(spelling):04d}'
            buffers[path].append(js([surface, eid, ordinal, fid])+'\n')
            count += 1
            if count % 100000 == 0:
                for name, rows in buffers.items():
                    with (temp/name).open('a') as out:
                        out.writelines(rows)
                buffers.clear()
        for name, rows in buffers.items():
            with (temp/name).open('a') as out:
                out.writelines(rows)
        for lang in ('la','grc'):
            for n in range(BUCKETS):
                p = temp/f'{lang}-{n:04d}'
                rows = [json.loads(line) for line in p.open()] if p.exists() else []
                write_gzip(f'data/index/{lang}-{n:04d}.json.gz', rows)
        manifest['counts']['postings'] = count
        shutil.rmtree(temp)
        print(f'Index: {count:,} occurrences', flush=True)
        maximum = db.execute('SELECT max(id) FROM entry').fetchone()[0]
        for start in range(1, maximum+1, BLOCK):
            entries = compile_entries(db, start, start+BLOCK-1)
            write_gzip(f'data/entries/{(start-1)//BLOCK:04d}.json.gz', entries)
            if start % (BLOCK*500) == 1:
                print(f'Entries: {start:,}/{maximum:,}', flush=True)
        for table in ('entry', 'sense', 'form', 'surface', 'link_occurrence', 'relation', 'ownership'):
            manifest['counts'][table] = db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
        db.close()
    manifest['version'] = RELEASE_VERSION
    manifest['shellBuild'] = package_shell(a.output, manifest['edition'], manifest['files'])
    for p in sorted(a.output.rglob('*')):
        if p.is_file() and 'data' not in p.relative_to(a.output).parts and p != a.output/'manifest.json':
            data = p.read_bytes()
            manifest['files'].append(dict(path=p.relative_to(a.output).as_posix(), bytes=len(data), sha256=digest(data)))
    manifest['files'].sort(key=lambda f:f['path'])
    manifest['bytes'] = sum(f['bytes'] for f in manifest['files'])
    manifest['expandedBytes'] = sum(f.get('expandedBytes', f['bytes']) for f in manifest['files'])
    manifest['package'] = digest(js(manifest['files']).encode())[:20]
    (a.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(package=manifest['package'], bytes=manifest['bytes'], files=len(manifest['files']), seconds=round(time.monotonic()-started,2))), flush=True)


if __name__ == '__main__':
    main()
