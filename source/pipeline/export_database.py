#!/usr/bin/env python3
"""Export a portable SQLite release, retaining recoverable source records."""
import argparse
import gzip
import hashlib
import json
from itertools import zip_longest
from pathlib import Path
import shutil
import sqlite3
from lookup import open_readonly


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('database', type=Path)
    p.add_argument('output', type=Path)
    a = p.parse_args()
    if a.output.exists():
        raise SystemExit('Refusing to overwrite an existing export')
    a.output.mkdir(parents=True)
    target = a.output/'dictionary.sqlite'
    with open_readonly(a.database) as source, sqlite3.connect(target) as dest:
        source.backup(dest)
        for sid, path in dest.execute('SELECT id,path FROM source').fetchall():
            dest.execute('UPDATE source SET path=? WHERE id=?', (Path(path).name, sid))
        dest.execute("DELETE FROM meta WHERE key='elapsed_seconds'")
        dest.execute("INSERT INTO meta VALUES ('release_version', '\"0.1.0-beta.1\"')")
        dest.execute('INSERT INTO meta VALUES (?,?)', ('attribution', json.dumps({
            'upstream': 'English Wiktionary contributors',
            'edition': 'Classical Cat DH Lab', 'maintainer': 'Xinjie Fang',
            'data_license': 'CC-BY-SA-4.0',
            'source': 'https://en.wiktionary.org/',
            'edition_url': 'https://data.latingreek.org/wiktionary/',
            'notice': 'Independently modified. Preserve upstream and edition credits, licence and change notices, with separately credited quotation exceptions. Not endorsed by Wikimedia.'})))
        dest.execute('''CREATE VIEW entry_locator AS SELECT e.id,
            'sha256:'||s.sha256||'/line/'||e.source_line AS locator,
            e.raw_sha256 AS record_sha256 FROM entry e JOIN source s ON s.id=e.source_id''')
        dest.commit()
        dest.execute('VACUUM')
        assert dest.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not dest.execute('PRAGMA foreign_key_check').fetchone()
        tables = [r[0] for r in source.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT IN ('source','meta')")]
        for table in tables:
            pk = sorted((r[5], r[1]) for r in source.execute(f'PRAGMA table_info("{table}")') if r[5])
            order = ','.join('"'+name+'"' for _,name in pk) if pk else 'rowid'
            sql = f'SELECT * FROM "{table}" ORDER BY {order}'
            for original, exported in zip_longest(source.execute(sql), dest.execute(sql)):
                assert original == exported, table
        schema = '\n'.join(r[0]+';' for r in dest.execute("SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name"))+'\n'
        (a.output/'schema.sql').write_text(schema)
    packed = a.output/'dictionary.sqlite.gz'
    with target.open('rb') as src, packed.open('wb') as out:
        with gzip.GzipFile(filename='', mode='wb', fileobj=out, mtime=0, compresslevel=6) as gz:
            shutil.copyfileobj(src, gz, 1024*1024)
    report = dict(status='passed', version='0.1.0-beta.1', exporter_sha256=sha(Path(__file__)), relational_tables_compared=tables,
        staging_sha256=sha(a.database), files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in (target,packed,a.output/'schema.sql')})
    (a.output/'database-export.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
