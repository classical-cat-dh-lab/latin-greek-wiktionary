#!/usr/bin/env python3
"""Recover three source-witnessed omissions with a bounded rendered-table parser."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit, parse_qs
import hashlib
import json
import re

PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / 'sources/beta-supplement-20260930'


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent, self.children = tag, dict(attrs), parent, []

    def all(self, predicate):
        for child in self.children:
            if isinstance(child, Node):
                if predicate(child):
                    yield child
                yield from child.all(predicate)

    def text(self, exclude=()):
        if self.tag in exclude:
            return ''
        if self.tag == 'br':
            return ' '
        return ''.join(c.text(exclude) if isinstance(c, Node) else c for c in self.children)

    def has(self, cls):
        return cls in self.attrs.get('class', '').split()


class Tree(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node(); self.current = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current); self.current.children.append(node)
        if tag not in {'br', 'wbr', 'hr', 'img', 'link', 'meta', 'input'}:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.current.tag == tag:
            self.current = self.current.parent

    def handle_endtag(self, tag):
        node = self.current
        while node.parent and node.tag != tag:
            node = node.parent
        if node.parent:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def clean(value):
    return re.sub(r'\s+', ' ', value).replace('\u200e', '').strip()


def links(node):
    result = []
    for a in node.all(lambda n: n.tag == 'a'):
        href = a.attrs.get('href', '')
        if href.startswith('/wiki/'):
            target = unquote(href[6:]).replace('_', ' ')
            target = target.replace('#Ancient Greek', '#Ancient_Greek')
        elif href.startswith('/w/index.php?'):
            target = parse_qs(urlsplit(href).query).get('title', [''])[0] + '#Ancient_Greek'
        elif href.startswith(('https://', 'http://')):
            target = href
        else:
            continue
        result.append([clean(a.text()), target])
    return result


TAG = {'first': ['first-person'], 'second': ['second-person'], 'third': ['third-person'],
       'singular': ['singular'], 'dual': ['dual'], 'plural': ['plural'],
       'active': ['active'], 'middle': ['middle'], 'passive': ['passive'],
       'middle/passive': ['middle', 'passive'], 'indicative': ['indicative'],
       'subjunctive': ['subjunctive'], 'optative': ['optative'], 'imperative': ['imperative'],
       'infinitive': ['infinitive'], 'participle': ['participle'],
       'm': ['masculine'], 'f': ['feminine'], 'n': ['neuter']}


def table_forms(table, number):
    """Use actual row/column spans and reset column labels at each header block."""
    classes = table.attrs.get('class', '').split()
    tense = next(c.removeprefix('grc-conj-') for c in classes if c.startswith('grc-conj-'))
    yield {'form': tense, 'tags': ['table-tags'], 'source': f'reviewed table {number}'}
    yield {'form': 'grc-conj', 'tags': ['inflection-template'], 'source': f'reviewed table {number}'}
    grid = {}; column_labels = {}; previous_header = False
    for ri, row in enumerate(table.all(lambda n: n.tag == 'tr')):
        cells = [c for c in row.children if isinstance(c, Node) and c.tag in ('th', 'td')]
        positioned = []; col = 0
        for cell in cells:
            while (ri, col) in grid:
                col += 1
            width, height = int(cell.attrs.get('colspan', 1)), int(cell.attrs.get('rowspan', 1))
            positioned.append((col, width, cell))
            for y in range(ri, ri + height):
                for x in range(col, col + width):
                    if (y, x) in grid:
                        raise ValueError('Overlapping source table cells')
                    grid[y, x] = cell
            col += width
        header_only = all(c.tag == 'th' for c in cells)
        if header_only:
            if not previous_header:
                column_labels = {}
            for col, width, cell in positioned:
                for x in range(col, col + width):
                    column_labels.setdefault(x, []).append(clean(cell.text()))
        else:
            for col, width, cell in positioned:
                if not (cell.has('grc-conj-finite-form') or cell.has('grc-conj-nonfinite-form')) or cell.tag != 'td':
                    continue
                headers = list(dict.fromkeys(clean(grid[ri, x].text()) for x in range(col)
                    if (ri, x) in grid and grid[ri, x].tag == 'th'))
                headers += column_labels.get(col, [])
                tags = sorted({tense, 'Attic'} | {t for h in headers for t in TAG.get(h, [])})
                for value in re.split(r',\s*', clean(cell.text())):
                    if not value:
                        continue
                    yield {'form': value, 'tags': tags, 'source': f'reviewed table {number}',
                           'source_cell': {'table': number, 'row': ri, 'column': col,
                                           'headers': headers}, 'links': links(cell)}
        previous_header = header_only


def extract(item):
    path = SOURCE / item['file']; payload = path.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == item['sha256']
    source = json.loads(payload)['parse']; title = item['title']
    assert source['revid'] == item['revision'] and source['title'] == title
    root = Tree(source['text']).root
    heads = list(root.all(lambda n: n.has('headword') and n.attrs.get('lang') == 'grc'))
    assert len(heads) == 1
    head = clean(heads[0].text())
    # These witnesses each contain exactly one Greek lexical head and one direct
    # definition list. No global POS inference from arbitrary headings is used.
    definitions = list(root.all(lambda n: n.tag == 'ol' and not any(
        a.tag in ('li', 'table') for a in ancestors(n))))
    assert len(definitions) == 1
    senses = []
    for li in definitions[0].children:
        if not isinstance(li, Node) or li.tag != 'li':
            continue
        sense = {'glosses': [clean(li.text(('ul', 'dl', 'ol')))], 'links': links(li)}
        quotes = list(li.all(lambda n: n.has('wiktQuote')))
        if quotes:
            sense['examples'] = [{'text': clean(next(q.all(lambda n: n.attrs.get('lang') == 'grc')).text()),
                                  'ref': clean(q.text())} for q in quotes]
        if title == 'κλῄζω':
            sense.update(tags=['alt-of', 'alternative', 'Old-Attic'], alt_of=[{'word': 'κλέω'}])
        senses.append(sense)
    assert len(senses) == {'κλῄζω': 1, 'ἀνακόπτω': 2, 'συνέχω': 9}[title]
    forms = [{'form': head, 'tags': ['canonical']}]
    tables = list(root.all(lambda n: n.tag == 'table' and n.has('grc-conj')))
    assert len(tables) == (0 if title == 'κλῄζω' else 5)
    for i, table in enumerate(tables):
        forms.extend(table_forms(table, i))
    sections = []; current = None
    # Preserve remaining rendered dictionary text as labelled source sections,
    # excluding multimedia/control markup; never render the captured HTML itself.
    parser_output = next(root.all(lambda n: n.has('mw-parser-output')))
    for node in parser_output.children:
        if not isinstance(node, Node):
            continue
        headings = list(node.all(lambda n: n.tag in ('h2', 'h3', 'h4')))
        if headings:
            heading = clean(headings[0].text())
            if headings[0].tag == 'h2' and heading != 'Ancient Greek':
                break
            current = {'heading': heading, 'text': [], 'links': []}; sections.append(current)
        elif current and node.tag in ('p', 'ul', 'div') and not list(node.all(lambda n: n.tag == 'table')):
            value = clean(node.text(('style', 'script', 'audio', 'video')))
            if value:
                current['text'].append(value); current['links'].extend(links(node))
    return {'word': title, 'lang': 'Ancient Greek', 'lang_code': 'grc', 'pos': 'verb',
            'senses': senses, 'forms': forms, 'source_sections': sections,
            'source_witness': {'kind': 'reviewed_wiktionary_supplement', 'revision': item['revision'],
                               'render_sha256': item['sha256'], 'render_capture': '2026-09-30',
                               'url': f"https://en.wiktionary.org/w/index.php?oldid={item['revision']}"},
            'recovery_note': 'Recovered from the cited page revision and captured template rendering.' +
              (' The grc-verb head and verb definitions occur under a second Pronunciation heading in the source.' if title == 'συνέχω' else '')}


def ancestors(node):
    while node.parent:
        node = node.parent
        yield node


if __name__ == '__main__':
    manifest = json.loads((SOURCE / 'manifest.json').read_text())
    records = [extract(item) for item in manifest['files']]
    out = PROJECT / 'evidence/beta-source-supplement.jsonl'
    out.write_text(''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n' for r in records))
    print(json.dumps([{'word': r['word'], 'senses': len(r['senses']), 'forms': len(r['forms'])} for r in records], ensure_ascii=False))
