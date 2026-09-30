"""Guarded source-reviewed projection overlays; original records stay immutable."""
import hashlib
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1]/'evidence/source-repairs-20260930.json'


def load():
    data = json.loads(PATH.read_text())
    rows = {(r['language'], r['source_line']): r for r in data['entries']}
    if len(rows) != len(data['entries']):
        raise ValueError('Duplicate source review identity')
    return rows


def checked(rows, lang, line, raw):
    row = rows.get((lang, line))
    if row and hashlib.sha256(raw).hexdigest() != row['raw_sha256']:
        raise ValueError(f'Source review guard failed: {lang}:{line}')
    return row
