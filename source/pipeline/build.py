#!/usr/bin/env python3
"""Build the private, source-accounted lexical staging database using stdlib only."""
import argparse
from collections import Counter, defaultdict
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import platform
import re
import sqlite3
import time
import unicodedata as ud
from urllib.parse import unquote, urlsplit
import zlib

import normalization as norm
import rules
import repairs

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
LAB = PROJECT.parents[1]
CAPTURE = LAB / 'cat-lab/lexical-qa/sources/kaikki-2026-09-20'
INVENTORY = LAB / 'cat-lab/lexical-qa/evidence/raw-inventory.json'
LANG_NAMES = {'Latin': 'la', 'Ancient_Greek': 'grc'}


def js(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checked(path, pin):
    if path.stat().st_size != pin['bytes'] or sha(path) != pin['sha256']:
        raise ValueError(f'Source pin mismatch: {path}')


def link_parts(target, own_page):
    value = unquote(target).replace('_', ' ')
    if value.startswith(('http:', 'https:', '//')):
        url = urlsplit(value if not value.startswith('//') else 'https:' + value)
        if url.netloc != 'en.wiktionary.org' or not url.path.startswith('/wiki/'):
            return '', '', '', 'external'
        value = url.path[6:] + ('#' + url.fragment if url.fragment else '')
    elif value.startswith('/wiki/'):
        value = value[6:]
    page, sep, anchor = value.partition('#')
    page = norm.nfc(page or own_page)
    anchor = anchor.replace(' ', '_')
    if page.startswith(('w:', 'wikipedia:', 's:', 'File:', 'Image:', 'Category:', 'Template:', 'Module:')):
        return page, '', anchor, 'reference_namespace'
    lang = LANG_NAMES.get(anchor, '')
    if not lang and anchor:
        for label, code in LANG_NAMES.items():
            if anchor.startswith(label + '-') or anchor.startswith(label + ':'):
                lang = code
                break
        if not lang and (anchor[:1].isupper() and not re.match(r'(Etymology|Noun|Verb|Adjective|Pronoun|Adverb|Proper_noun|Derived|Related|Usage|References|Sense|senses)', anchor)):
            return page, '', anchor, 'other_language_or_anchor'
    return page, lang, anchor, 'pending'


def load_reviews():
    review_path = PROJECT / 'evidence/bounded-semantic-review.json'
    review = json.loads(review_path.read_text())
    overrides = {}
    for row in review['records']:
        ordinal = int(row['pointer'].split('/')[-1])
        overrides[('grc', row['slice_line'], ordinal)] = {
            'glosses': row['glosses'], 'rule': row['assessment'], 'targets': row['targets']}
    overrides[('la', 2481, 3)] = {
        'glosses': ['noun, inclusive of substantives, adjectives, pronouns, articles, and numerals'],
        'targets': ['substantives', 'adjectives', 'pronouns', 'articles', 'and numerals'],
        'rule': 'ordinary_definition_misparsed_as_form_of'}
    return overrides


class Builder:
    def __init__(self, db, overrides=None, reviews=None):
        self.db = db
        self.overrides = overrides or {}
        self.applied_overrides = set()
        self.reviews = reviews or {}
        self.applied_reviews = set()
        self.reviewed_owners = []
        self.counts = defaultdict(Counter)
        self.ids = Counter()
        self.buffers = defaultdict(list)
        self.redirects = {}
        self.link_cache = {}

    def add(self, table, row):
        self.buffers[table].append(row)

    def next_id(self, table):
        self.ids[table] += 1
        return self.ids[table]

    def flush(self):
        for table in ('entry', 'sense', 'table_context', 'form', 'form_surface', 'head',
                      'relation', 'link', 'link_occurrence', 'issue', 'change', 'source_review'):
            rows = self.buffers[table]
            if rows:
                self.db.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in rows[0])})', rows)
                rows.clear()
        self.db.commit()

    def issue(self, eid, pointer, kind, detail):
        self.add('issue', (self.next_id('issue'), eid, pointer, kind, js(detail)))

    def change(self, eid, pointer, rule, detail=None):
        self.add('change', (self.next_id('change'), eid, pointer, rule, js(detail or {})))

    def record(self, raw, line, source_id, lang, supplement=False):
        e = json.loads(raw)
        if e['lang_code'] != lang:
            raise ValueError(f'Wrong language at {lang}:{line}')
        eid = self.next_id('entry')
        review = (repairs.checked(self.reviews, lang, line, raw) or {}) if not supplement else {}
        if review:
            self.applied_reviews.add((lang, line))
            self.add('source_review', (eid, js(review)))
            self.reviewed_owners.extend((eid, owner) for owner in review.get('owners', []))
        page = e.get('original_title') or e['word']
        canonical = [f['form'] for f in e.get('forms', []) if 'canonical' in f.get('tags', []) and norm.language_letters(f['form'],lang)]
        headword = canonical[0] if canonical else e['word']
        headword = review.get('headword', headword)
        local_senses = []
        for ordinal, sense in enumerate(e['senses']):
            sid = self.next_id('sense'); pointer = f'/senses/{ordinal}'
            override = self.overrides.get((lang, line, ordinal)) if not supplement else None
            if override:
                if sense.get('glosses', []) != override['glosses'] or sorted(t['word'] for t in sense.get('form_of', [])) != sorted(override['targets']):
                    raise ValueError(f'Semantic correction guard failed: {lang}:{line}{pointer}')
                self.applied_overrides.add((lang, line, ordinal))
                self.change(eid, pointer, override['rule'])
            role, glosses, origin, grammar = rules.project_sense(sense, bool(override))
            patch = review.get('senses', {}).get(str(ordinal), {})
            if patch:
                role = patch.get('role', role)
                glosses = patch.get('glosses', glosses)
                origin = 'reviewed_source' if 'glosses' in patch else origin
                grammar.update(patch.get('grammar', {}))
                if patch.get('suppress'):
                    grammar['tags'] = [t for t in grammar['tags'] if t not in ('form-of', 'alt-of')]
                if patch.get('definition_status'):
                    grammar['definition_status'] = patch['definition_status']
                self.change(eid, pointer, patch['rule'], patch)
            local_senses.append(role)
            self.add('sense', (sid, eid, ordinal, role, js(glosses), origin, js(grammar)))
            self.counts[lang]['senses'] += 1
            if origin in ('raw_glosses', 'qualifier'):
                self.change(eid, pointer, 'display_gloss_recovered', {'from': origin})
            if origin == 'missing' and not patch.get('definition_status'):
                self.issue(eid, pointer, 'source_definition_unavailable', {})
            for kind in rules.RELATIONS:
                for ti, target in enumerate(sense.get(kind, [])):
                    if not isinstance(target, dict) or not isinstance(target.get('word'), str):
                        self.issue(eid, pointer + '/' + kind, 'relation_shape', target)
                        continue
                    rid = self.next_id('relation')
                    status = 'source_explanation' if (override and kind == 'form_of') or kind in patch.get('suppress', []) else 'pending'
                    hints = {'links': sense.get('links', []), 'tags': sense.get('tags', []),
                             'extra': target.get('extra'), 'glosses': glosses}
                    if kind == 'form_of' and patch.get('owner_targets'):
                        if len(sense.get('form_of', [])) != 1:
                            raise ValueError('Reviewed composite owner is not a single source assertion')
                        hints['reviewed_targets'] = patch['owner_targets']
                    self.add('relation', (rid, eid, sid, pointer + f'/{kind}/{ti}', kind, target['word'], js(hints), status))
                    self.counts[lang][kind + '_relations'] += 1
        for kind in rules.RELATIONS:
            for ti, target in enumerate(e.get(kind, [])):
                if not isinstance(target, dict) or not isinstance(target.get('word'), str):
                    self.issue(eid, '/' + kind, 'relation_shape', target)
                    continue
                hints = {'links': target.get('links', []), 'tags': target.get('tags', []),
                         'target_lang': target.get('lang_code'), 'sense': target.get('sense')}
                self.add('relation', (self.next_id('relation'), eid, None, f'/{kind}/{ti}', kind,
                                      target['word'], js(hints), 'pending'))
                self.counts[lang][kind + '_relations'] += 1
        role = ('mixed' if any(r in ('form', 'variant') for r in local_senses) else 'lexical') if 'lexical' in local_senses else 'form_only' if 'form' in local_senses else 'variant_only' if 'variant' in local_senses else 'incomplete'
        self.add('entry', (eid, source_id, line, lang, e['word'], page, e['pos'],
                           e.get('etymology_number'), headword, role, hashlib.sha256(raw).hexdigest(), zlib.compress(raw, 1)))
        self.counts[lang]['entries'] += 1
        head_values = [(e['word'], 'title'), (page, 'source_page')] + [(c, 'canonical') for c in canonical]
        if 'headword' in review:
            head_values.append((headword, 'reviewed_head'))
        for value, kind in dict.fromkeys(head_values):
            self.add('head', (lang, value, norm.nfc(value), norm.quantity(value), eid, kind))
        titleid = self.next_id('form')
        title_role = 'title_word' if norm.is_word(e['word'], lang) else 'title_content'
        self.add('form', (titleid, eid, -1, e['word'], title_role, None, '{}'))
        if title_role == 'title_word':
            self.add('form_surface', (lang, e['word'], titleid))
            if '\u00ad' in e['word']:
                self.change(eid, '/word', 'soft_hyphen_retrieval_only')
        context = None; context_rows = []
        for ordinal, form in enumerate(e.get('forms', [])):
            ptr = f'/forms/{ordinal}'; tags = set(form.get('tags', []))
            if 'table-tags' in tags:
                context = {'id': self.next_id('table_context'), 'ordinal': ordinal,
                           'header': form['form'], 'source': form.get('source'), 'template': None}
                context_rows.append(context)
            if 'inflection-template' in tags and context:
                context['template'] = form['form']
            projected, surfaces, grammar, changes, issues = rules.project_form(form, e, context)
            patch = review.get('forms', {}).get(str(ordinal))
            if patch:
                projected = patch['role']; surfaces = patch['surfaces']
                if any(not norm.is_word(s, lang) for s in surfaces):
                    raise ValueError(f'Review admitted non-word: {lang}:{line}{ptr}')
                grammar.update(patch.get('grammar', {}))
                grammar['review_note'] = patch['note']
                changes.append(patch['rule'])
                issues = [i for i in issues if i not in patch['resolved_issues']]
            fid = self.next_id('form')
            self.add('form', (fid, eid, ordinal, form['form'], projected, context['id'] if context else None, js(grammar)))
            for value in dict.fromkeys(surfaces):
                self.add('form_surface', (lang, value, fid))
            for change in changes:
                self.change(eid, ptr, change)
            for issue in issues:
                self.issue(eid, ptr, issue, {'surface': form['form'], 'table': context})
            self.counts[lang]['forms'] += 1
            self.counts[lang]['form_role:' + projected] += 1
        for row in context_rows:
            self.add('table_context', (row['id'], eid, row['ordinal'], row['source'], row['header'], row['template']))
        for pointer, label, target in rules.explicit_links(e):
            parts = link_parts(target, page)
            cache_key = (target,) + parts[:3]
            lid = self.link_cache.get(cache_key)
            if lid is None:
                lid = self.next_id('link')
                self.link_cache[cache_key] = lid
                self.add('link', (lid, target, *parts))
            self.add('link_occurrence', (eid, pointer, label, lid))
            self.counts[lang]['explicit_link_occurrences'] += 1
        if line % 2000 == 0:
            self.flush()
        if line % 100000 == 0:
            print(lang, line, 'records imported', flush=True)

    def import_redirects(self, path):
        records = [json.loads(line) for line in path.open(encoding='utf-8')]
        self.redirects = {r['title']: r['redirect'] for r in records}
        rows = []
        for ordinal, row in enumerate(records, 1):
            page, lang, anchor, state = self.follow_redirect(row['title'], '')
            rows.append((ordinal, row['line'], row['title'], row['redirect'], page, anchor, state))
        self.db.executemany('INSERT INTO redirect VALUES (?,?,?,?,?,?,?)', rows)
        self.db.commit()

    @lru_cache(maxsize=100000)
    def follow_redirect(self, page, anchor):
        visited = set()
        while page in self.redirects:
            if page in visited:
                return page, '', anchor, 'redirect_cycle'
            visited.add(page)
            dest, lang, dest_anchor, state = link_parts(self.redirects[page], page)
            if state != 'pending':
                return dest, lang, dest_anchor or anchor, state
            page, anchor = dest, dest_anchor or anchor
        return page, LANG_NAMES.get(anchor, ''), anchor, 'redirected' if visited else 'direct'

    def indexes(self):
        self.db.executescript('''
        CREATE INDEX entry_page ON entry(page,lang);
        CREATE INDEX entry_lang_line ON entry(lang,source_line);
        CREATE INDEX sense_entry ON sense(entry_id);
        CREATE INDEX form_entry ON form(entry_id);
        CREATE INDEX form_surface_word ON form_surface(lang,surface);
        CREATE INDEX form_surface_form ON form_surface(form_id);
        CREATE INDEX head_exact ON head(lang,exact);
        CREATE INDEX head_quantity ON head(lang,quantity);
        CREATE INDEX relation_entry ON relation(entry_id);
        CREATE INDEX relation_sense ON relation(sense_id);
        CREATE INDEX link_occurrence_entry ON link_occurrence(entry_id);
        CREATE INDEX issue_kind ON issue(kind);
        CREATE INDEX change_rule ON change(rule);
        ''')

    @lru_cache(maxsize=100000)
    def heads(self, lang, target, page='', pos=''):
        """Resolve source spelling within source page/POS constraints, not reader folds."""
        if page:
            rows = self.db.execute('SELECT id,pos,role,headword FROM entry WHERE page=? AND lang=?', (page, lang)).fetchall()
            exact = [r for r in rows if norm.nfc(r[3]) == norm.nfc(target)]
            if exact:
                rows = exact
            else:
                supported = {r[0] for r in self.db.execute('''SELECT DISTINCT f.entry_id FROM form_surface fs
                    JOIN form f ON f.id=fs.form_id JOIN entry e ON e.id=f.entry_id
                    WHERE fs.lang=? AND fs.surface=? AND e.page=?''', (lang, target, page))}
                if supported:
                    rows = [r for r in rows if r[0] in supported]
                else:
                    q = [r for r in rows if norm.quantity(r[3]) == norm.quantity(target)]
                    if q:
                        rows = q
        else:
            rows = self.db.execute('''SELECT DISTINCT e.id,e.pos,e.role,e.headword FROM head h
                JOIN entry e ON e.id=h.entry_id WHERE h.lang=? AND h.exact=?''', (lang, norm.nfc(target))).fetchall()
            if not rows:
                rows = self.db.execute('''SELECT DISTINCT e.id,e.pos,e.role,e.headword FROM head h
                    JOIN entry e ON e.id=h.entry_id WHERE h.lang=? AND h.quantity=?''', (lang, norm.quantity(target))).fetchall()
        canonical = [r for r in rows if norm.nfc(r[3]) == norm.nfc(target)]
        if canonical:
            rows = canonical
        if pos and any(r[1] == pos for r in rows):
            rows = [r for r in rows if r[1] == pos]
        return tuple(r[0] for r in rows)

    def relation_candidates(self, lang, pos, kind, target, hints):
        if hints.get('reviewed_targets'):
            candidates = {}
            for reviewed_target in hints['reviewed_targets']:
                found = self.heads(lang, reviewed_target, '', pos)
                if not found:
                    raise ValueError('Reviewed composite owner has no local target')
                candidates.update((eid, 'reviewed_explicit_alternatives') for eid in found)
            return list(candidates.items()), 'resolved', ['source_composite_owner_split']
        if hints.get('target_lang') and hints['target_lang'] not in ('la', 'grc'):
            return [], 'other_language', []
        target_lang = hints.get('target_lang') or lang
        candidates = {}; changes = []
        matching_links = []
        for label, href in hints.get('links', []):
            # Source links can group principal parts; require the target in the label.
            qlabel = norm.quantity(label); qtarget = norm.quantity(target)
            clean_target = re.sub(r'^\([^)]*\)\s*', '', qtarget)
            clean_target = re.sub(r'\s+(?:[mfn](?: or [mfn])*|sg|pl)$', '', clean_target)
            clean_target = re.sub(r'^(?:and|or)\s+', '', clean_target)
            pieces = re.split(r'\s+(?:and|or)\s+|\s*/\s*', clean_target)
            if (qlabel == clean_target or clean_target in re.split(r',\s*', qlabel)
                    or qlabel in pieces or qlabel == qtarget):
                matching_links.append((label, href))
        if matching_links:
            nonlocal_count = 0
            for label, href in matching_links:
                page, linked_lang, anchor, state = link_parts(href, '')
                if state != 'pending' or (linked_lang and linked_lang != target_lang):
                    nonlocal_count += 1
                    continue
                page, redirect_lang, _, rstate = self.follow_redirect(page, anchor)
                if rstate not in ('direct', 'redirected') or (redirect_lang and redirect_lang != target_lang):
                    nonlocal_count += 1
                    continue
                for eid in self.heads(target_lang, target if len(matching_links) == 1 else label, page, pos if kind in ('form_of', 'alt_of') else ''):
                    candidates[eid] = 'source_link'
            if candidates:
                if len(matching_links) > 1:
                    changes.append('linked_target_split')
                return list(candidates.items()), 'resolved', changes
            if nonlocal_count == len(matching_links):
                return [], 'explicit_nonlocal', changes
        # Affix qualifiers are removable only when the cleaned head is attested.
        clean = re.sub(r'^\((?:Attic|Ionic|Epic|Doric|Aeolic)\)\s*', '', target)
        clean = re.sub(r'\s+(?:m|f|n|sg|pl)$', '', clean)
        for eid in self.heads(target_lang, clean, '', pos if kind in ('form_of', 'alt_of') else ''):
            candidates[eid] = 'source_head' if clean == target else 'qualified_source_head'
        if candidates and clean != target:
            changes.append('target_qualifier_separated')
        if not candidates:
            page, linked_lang, _, state = self.follow_redirect(target, '')
            if state == 'redirected' and (not linked_lang or linked_lang == target_lang):
                for eid in self.heads(target_lang, page, page, pos if kind in ('form_of', 'alt_of') else ''):
                    candidates[eid] = 'source_redirect'
        if not candidates and norm.is_word(target, target_lang):
            for eid in self.form_targets(target_lang, target, pos if kind in ('form_of','alt_of') else ''):
                candidates[eid] = 'attested_paradigm_surface'
        return list(candidates.items()), 'resolved' if candidates else 'unresolved', changes

    def form_targets(self, lang, target, pos=''):
        # During construction SQLite has not yet collected final statistics.
        # Force the narrow source-spelling probe before joining occurrences.
        rows = self.db.execute('''SELECT DISTINCT f.entry_id,e.pos FROM surface s INDEXED BY surface_quantity
          CROSS JOIN form_surface fs ON fs.lang=s.lang AND fs.surface=s.text
          CROSS JOIN form f ON f.id=fs.form_id CROSS JOIN entry e ON e.id=f.entry_id
          WHERE s.lang=? AND s.quantity=?''',(lang,norm.quantity(target))).fetchall()
        if pos and any(p==pos for _,p in rows):
            rows = [(eid,p) for eid,p in rows if p==pos]
        return [eid for eid,_ in rows]

    def resolve_relations(self):
        cache = {}; edge_rows = []; updates = []
        read = self.db.execute('''SELECT r.id,r.entry_id,r.pointer,r.kind,r.target,r.hints,e.lang,e.pos
            FROM relation r JOIN entry e ON e.id=r.entry_id WHERE r.status='pending' ORDER BY r.id''')
        for i, (rid, eid, ptr, kind, target, hint_json, lang, pos) in enumerate(read, 1):
            hints = json.loads(hint_json)
            ck = (lang, pos if kind in ('form_of','alt_of') else '', kind, target, js(hints.get('links', [])), hints.get('target_lang'), js(hints.get('reviewed_targets')))
            if ck not in cache:
                cache[ck] = self.relation_candidates(lang, pos, kind, target, hints)
            candidates, state, changes = cache[ck]
            # A same-title form node must not hide an independently defined target.
            if any(t != eid for t, _ in candidates):
                candidates = [(t, m) for t, m in candidates if t != eid]
            if state == 'resolved':
                state = 'resolved_one' if len(candidates) == 1 else 'resolved_candidates'
            if candidates and all(t == eid for t, _ in candidates):
                own_role = self.db.execute('SELECT role FROM entry WHERE id=?', (eid,)).fetchone()[0]
                state = 'resolved_local_reading' if own_role in ('lexical','mixed') else 'self_reference'
            updates.append((state, rid))
            edge_rows.extend((rid, target_id, method) for target_id, method in candidates)
            for rule in changes:
                self.change(eid, ptr, rule, {'target': target})
            if state in ('unresolved', 'self_reference'):
                self.issue(eid, ptr, kind + '_' + state, {'target': target})
            if i % 10000 == 0:
                self.db.executemany('UPDATE relation SET status=? WHERE id=?', updates); updates.clear()
                self.db.executemany('INSERT INTO relation_target VALUES (?,?,?)', edge_rows); edge_rows.clear()
                self.flush()
            if i % 200000 == 0:
                print(i, 'relations resolved', flush=True)
        self.db.executemany('UPDATE relation SET status=? WHERE id=?', updates)
        self.db.executemany('INSERT INTO relation_target VALUES (?,?,?)', edge_rows)
        self.flush()
        # An explicitly foreign explanation is not an inflection-owner assertion.
        self.db.execute('''UPDATE sense SET role='lexical' WHERE role IN ('form','variant')
          AND EXISTS(SELECT 1 FROM relation r WHERE r.sense_id=sense.id)
          AND NOT EXISTS(SELECT 1 FROM relation r WHERE r.sense_id=sense.id
            AND r.kind IN ('form_of','alt_of') AND r.status NOT IN ('source_explanation','explicit_nonlocal','other_language'))''')
        self.db.execute('''UPDATE entry SET role=CASE
          WHEN EXISTS(SELECT 1 FROM sense s WHERE s.entry_id=entry.id AND s.role='lexical')
          THEN CASE WHEN EXISTS(SELECT 1 FROM sense s WHERE s.entry_id=entry.id AND s.role IN ('form','variant')) THEN 'mixed' ELSE 'lexical' END
          WHEN EXISTS(SELECT 1 FROM sense s WHERE s.entry_id=entry.id AND s.role='form') THEN 'form_only'
          WHEN EXISTS(SELECT 1 FROM sense s WHERE s.entry_id=entry.id AND s.role='variant') THEN 'variant_only'
          ELSE 'incomplete' END''')
        self.db.commit()

    def apply_relation_reviews(self, rows):
        for row in rows:
            found = self.db.execute('''SELECT r.id,e.raw_sha256,r.target,r.hints FROM relation r
              JOIN entry e ON e.id=r.entry_id WHERE e.source_id IN (1,2) AND e.lang=?
              AND e.source_line=? AND r.pointer=? AND r.kind=?''',
              (row['language'], row['source_line'], row['pointer'], row['kind'])).fetchall()
            if len(found) != 1 or found[0][1:3] != (row['raw_sha256'], row['target']):
                raise ValueError('Beta relation review guard failed')
            rid, _, _, hint_json = found[0]
            hints = json.loads(hint_json)
            if row.get('action') == 'source_explanation':
                self.db.execute("UPDATE relation SET status='source_explanation' WHERE id=?", (rid,))
            elif row.get('action') == 'qualified_target':
                hints['reviewed_targets'] = row['target_words']
                self.db.execute('UPDATE relation SET hints=? WHERE id=?', (js(hints), rid))
            self.db.execute('INSERT INTO relation_review VALUES (?,?,?)',
                            (rid, row['disposition'], js(row)))
        self.db.commit()

    def resolve_links(self):
        changed = []
        for lid, page, lang, anchor in self.db.execute("SELECT id,page,lang,anchor FROM link WHERE status='pending'"):
            dest, target_lang, target_anchor, state = self.follow_redirect(page, anchor)
            if state == 'redirected':
                changed.append((dest, target_lang or lang, target_anchor, lid))
            elif state not in ('direct',):
                self.db.execute('UPDATE link SET status=? WHERE id=?', (state, lid))
        # Preserve original node identity/target text; redirect destinations need not be unique.
        for dest, lang, anchor, lid in changed:
            try:
                self.db.execute('UPDATE link SET page=?,lang=?,anchor=? WHERE id=?', (dest, lang, anchor, lid))
            except sqlite3.IntegrityError:
                raise ValueError('Unexpected duplicate link identity after redirect resolution')
        self.db.execute('''INSERT INTO link_target SELECT l.id,e.id FROM link l JOIN entry e ON e.page=l.page
            WHERE l.status='pending' AND (l.lang='' OR l.lang=e.lang)''')
        self.db.execute('''UPDATE link SET status=CASE WHEN EXISTS(SELECT 1 FROM link_target t WHERE t.link_id=link.id)
            THEN CASE WHEN anchor='' OR anchor IN ('Latin','Ancient_Greek') THEN 'local' ELSE 'local_page_anchor' END
            ELSE 'missing_local_target' END WHERE status='pending' ''')
        self.db.execute('''UPDATE redirect SET status=CASE WHEN EXISTS(SELECT 1 FROM entry e WHERE e.page=redirect.final_page)
            THEN 'included_page' ELSE 'outside_capture' END WHERE status IN ('direct','redirected')''')
        for title, page, anchor in self.db.execute("SELECT title,final_page,anchor FROM redirect WHERE status='included_page'").fetchall():
            lang = LANG_NAMES.get(anchor, '')
            for eid, language in self.db.execute('SELECT id,lang FROM entry WHERE page=? AND (?=\'\' OR lang=?)', (page, lang, lang)).fetchall():
                if norm.is_word(title, language):
                    fid = self.next_id('form')
                    # Negative ordinals after -1 identify synthetic captured-redirect aliases.
                    self.db.execute('INSERT INTO form VALUES (?,?,?,?,?,?,?)', (fid, eid, -fid-1, title, 'redirect_word', None, '{}'))
                    self.db.execute('INSERT INTO form_surface VALUES (?,?,?)', (language, title, fid))
        self.db.commit()
        self.link_cache.clear()

    def make_surfaces(self):
        rows = []
        for lang, text in self.db.execute('SELECT DISTINCT lang,surface FROM form_surface ORDER BY lang,surface'):
            rows.append((lang, text, *(norm.key(text, lang, p) for p in norm.PROFILES), norm.quantity(text)))
            if len(rows) == 10000:
                self.db.executemany('INSERT INTO surface(lang,text,exact,reading,tolerant,spelling,quantity) VALUES (?,?,?,?,?,?,?)', rows); rows.clear()
        self.db.executemany('INSERT INTO surface(lang,text,exact,reading,tolerant,spelling,quantity) VALUES (?,?,?,?,?,?,?)', rows)
        for profile in (*norm.PROFILES,'quantity'):
            self.db.execute(f'CREATE INDEX surface_{profile} ON surface(lang,{profile})')
        self.db.commit()

    def resolve_form_links(self):
        for lid, page, lang in self.db.execute("SELECT id,page,lang FROM link WHERE status='missing_local_target'"):
            candidates = set()
            for language in (lang,) if lang else ('la','grc'):
                if norm.is_word(page,language):
                    candidates.update(self.form_targets(language,page))
            if candidates:
                self.db.executemany('INSERT INTO link_target VALUES (?,?)',[(lid,eid) for eid in sorted(candidates)])
                self.db.execute("UPDATE link SET status='local_form' WHERE id=?",(lid,))
        self.db.commit()

    def make_ownership(self):
        roles = dict(self.db.execute('SELECT id,role FROM entry'))
        adjacent = defaultdict(set)
        for eid, owner in self.reviewed_owners:
            target = self.db.execute('SELECT id,headword FROM entry WHERE source_id IN (1,2) AND lang=? AND source_line=?',
                                     (owner['language'], owner['source_line'])).fetchone()
            if not target or target[1] != owner['headword']:
                raise ValueError('Reviewed owner target guard failed')
            adjacent[eid].add(target[0])
            self.db.execute('INSERT INTO reviewed_owner VALUES (?,?,?)', (eid, target[0], js(owner)))
        for src, dst in self.db.execute('''SELECT DISTINCT r.entry_id,t.entry_id FROM relation r
             JOIN relation_target t ON t.relation_id=r.id JOIN sense s ON s.id=r.sense_id
             WHERE r.kind IN ('form_of','alt_of') AND s.role IN ('form','variant')
             AND r.status IN ('resolved_one','resolved_candidates','self_reference')'''):
            adjacent[src].add(dst)
        memo = {}; cycles = set(); depth_exceeded = set(); tainted = set()

        def walk(eid, trail):
            if eid in trail:
                cycles.add(eid)
                tainted.update(trail)
                return ()
            if len(trail) > 32:
                depth_exceeded.add(eid)
                tainted.update(trail)
                return ()
            if eid in memo:
                return memo[eid]
            results = []
            if roles[eid] in ('lexical', 'mixed', 'incomplete'):
                results.append((eid, (eid,)))
            for target in sorted(adjacent.get(eid, ())):
                for root, path in walk(target, trail + (eid,)):
                    results.append((root, (eid,) + path))
            # Cycles are not memoized as empty until all entry roots have been explored.
            # One shortest witness per root; every assertion remains in the graph.
            by_root = {}
            for root, path in results:
                if root not in by_root or (len(path), path) < (len(by_root[root]), by_root[root]):
                    by_root[root] = path
            unique = tuple(sorted(by_root.items()))
            if unique and eid not in tainted:
                memo[eid] = unique
            return unique

        batch = []
        for eid in roles:
            paths = walk(eid, ())
            if not paths:
                paths = ((eid, (eid,)),)
                state = 'unresolved_form'
            else:
                state = 'candidate_paths' if len({r for r, _ in paths}) > 1 else 'lexical_path'
            for root, path in paths:
                batch.append((eid, root, len(path)-1, js(path), state))
            if len(batch) >= 10000:
                self.db.executemany('INSERT OR IGNORE INTO ownership VALUES (?,?,?,?,?)', batch); batch.clear()
        self.db.executemany('INSERT OR IGNORE INTO ownership VALUES (?,?,?,?,?)', batch)
        for eid in sorted(cycles):
            self.issue(eid, '', 'ownership_cycle', {})
        for eid in sorted(depth_exceeded):
            self.issue(eid, '', 'ownership_depth_limit', {})
        self.flush()
        self.db.execute('CREATE INDEX ownership_root ON ownership(root_id)')
        self.db.commit()


def build(args):
    started = time.monotonic()
    implementation = {p.name: sha(p) for p in sorted(HERE.glob('*')) if p.suffix in ('.py','.sql')}
    review_pin = sha(PROJECT / 'evidence/bounded-semantic-review.json')
    repair_pin = sha(repairs.PATH)
    supplement_path = PROJECT / 'evidence/beta-source-supplement.jsonl'
    relation_review_path = PROJECT / 'evidence/beta-relation-review.json'
    supplement_pin = sha(supplement_path)
    relation_review_pin = sha(relation_review_path)
    inventory = json.loads(args.inventory.read_text())
    pins = inventory['lossless_slices']
    redirect_manifest = json.loads((args.capture / 'raw-latin-supplement/manifest.json').read_text())
    for lang in ('la', 'grc'):
        checked(args.capture / 'raw-language-slices' / (lang + '.jsonl'), pins[lang])
    redirect_path = args.capture / 'raw-latin-supplement/redirects.jsonl'
    checked(redirect_path, redirect_manifest['files']['redirects.jsonl'])
    args.output.mkdir(parents=True, exist_ok=True)
    target = args.output / 'dictionary.sqlite'
    partial = args.output / 'dictionary.partial.sqlite'
    if target.exists() or partial.exists():
        raise FileExistsError('Use a new output directory; completed/partial builds are never overwritten')
    db = sqlite3.connect(partial)
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA synchronous=NORMAL')
    db.execute('PRAGMA cache_size=-131072')
    db.execute('PRAGMA temp_store=FILE')
    db.executescript((HERE / 'schema.sql').read_text())
    overrides = load_reviews()
    reviews = repairs.load()
    b = Builder(db, overrides, reviews)
    for sid, lang in enumerate(('la', 'grc'), 1):
        path = args.capture / 'raw-language-slices' / (lang + '.jsonl')
        expected = inventory['languages'][lang]['counts']
        db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)', (sid, lang, str(path), pins[lang]['sha256'], pins[lang]['bytes'], expected['entries']))
        for line, raw in enumerate(path.open('rb'), 1):
            b.record(raw, line, sid, lang)
        b.flush()
        for name, pin_name in [('entries','entries'), ('senses','senses'), ('forms','form_occurrences_total'),
                               ('form_of_relations','form_of_relations'), ('alt_of_relations','alt_of_relations')]:
            if b.counts[lang][name] != expected[pin_name]:
                raise ValueError(f'Accounting mismatch: {lang}:{name}')
        print(lang, 'import complete', dict(b.counts[lang]), flush=True)
    if b.applied_overrides != set(overrides):
        raise ValueError('Not all guarded semantic corrections were applied')
    if b.applied_reviews != set(reviews):
        raise ValueError('Not all source-reviewed projections were applied')
    supplementary = supplement_path.read_bytes().splitlines(keepends=True)
    db.execute('INSERT INTO source VALUES (?,?,?,?,?,?)',
        (3, 'grc', str(supplement_path), supplement_pin, supplement_path.stat().st_size, len(supplementary)))
    for line, raw in enumerate(supplementary, 1):
        b.record(raw, line, 3, 'grc', supplement=True)
    b.flush()
    print('Indexing source projection', flush=True); b.indexes()
    b.apply_relation_reviews(json.loads(relation_review_path.read_text())['records'])
    b.import_redirects(redirect_path)
    print('Resolving internal links and redirects', flush=True); b.resolve_links()
    print('Compiling normalized surfaces', flush=True); b.make_surfaces()
    print('Resolving lexical assertions', flush=True); b.resolve_relations()
    print('Resolving links to paradigm forms', flush=True); b.resolve_form_links()
    print('Compiling form-only ownership paths', flush=True); b.make_ownership()
    manifest = {
        'schema': 'formlex-build/2', 'input_pins': pins,
        'redirect_pin': redirect_manifest['files']['redirects.jsonl'],
        'inventory_sha256': sha(args.inventory), 'normalization': norm.VERSION,
        'rules': rules.VERSION, 'unicode_version': ud.unidata_version,
        'python_version': platform.python_version(), 'sqlite_version': sqlite3.sqlite_version,
        'files': implementation, 'semantic_review_sha256': review_pin, 'source_repairs_sha256': repair_pin,
        'supplement_sha256': supplement_pin, 'relation_review_sha256': relation_review_pin,
        'counts': dict(b.counts), 'elapsed_seconds': round(time.monotonic()-started, 3),
        'scope': 'Complete projection of pinned captures; not a claim of complete Wiktionary channel capture or scholarly correctness'}
    db.executemany('INSERT INTO meta VALUES (?,?)', [(k,js(v)) for k,v in manifest.items()])
    db.execute('ANALYZE'); db.commit()
    if implementation != {p.name:sha(p) for p in sorted(HERE.glob('*')) if p.suffix in ('.py','.sql')} or review_pin != sha(PROJECT / 'evidence/bounded-semantic-review.json') or repair_pin != sha(repairs.PATH) or supplement_pin != sha(supplement_path) or relation_review_pin != sha(relation_review_path):
        raise ValueError('Implementation or semantic review changed during build')
    if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('Database integrity check failed')
    db.close()
    partial.rename(target)
    manifest['database_bytes'] = target.stat().st_size
    manifest['database_sha256'] = sha(target)
    (args.output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print('Built', target, manifest['database_bytes'], 'bytes', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, default=CAPTURE)
    parser.add_argument('--inventory', type=Path, default=INVENTORY)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args())
