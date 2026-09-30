"""Beta regressions for source recovery and the frozen consumer model."""
import importlib.util
import json
from pathlib import Path
import sqlite3
import unittest

from build import Builder, HERE
from entry_model import attach_model

spec = importlib.util.spec_from_file_location('supplement', HERE.parent/'research/extract_beta_supplement.py')
supplement = importlib.util.module_from_spec(spec); spec.loader.exec_module(supplement)


class BetaTests(unittest.TestCase):
    def test_rendered_table_uses_spans_and_optional_nu_as_one_form(self):
        html = '''<table class="grc-conj grc-conj-present"><tr><th colspan="2"></th><th>plural</th></tr>
        <tr><th colspan="2"></th><th>third</th></tr><tr><th>active</th><th>indicative</th>
        <td class="grc-conj-finite-form"><span lang="grc">λύουσι</span>(<span lang="grc">ν</span>)</td></tr>
        <tr><th colspan="2"></th><th>middle/passive</th></tr><tr><th colspan="2">infinitive</th>
        <td class="grc-conj-nonfinite-form">λύεσθαι</td></tr></table>'''
        table = next(supplement.Tree(html).root.all(lambda n: n.tag == 'table'))
        forms = list(supplement.table_forms(table, 0))
        self.assertEqual(forms[2]['form'], 'λύουσι(ν)')
        self.assertEqual(set(forms[2]['tags']), {'present','Attic','third-person','plural','active','indicative'})
        self.assertEqual(set(forms[3]['tags']), {'present','Attic','middle','passive','infinitive'})

    def test_supplement_does_not_apply_base_line_overlays(self):
        db = sqlite3.connect(':memory:'); db.executescript((HERE/'schema.sql').read_text())
        db.execute('INSERT INTO source VALUES (3,?,?,?,?,?)', ('grc','supplement','hash',0,1))
        builder = Builder(db, reviews={('grc', 1): {'raw_sha256': 'wrong'}})
        entry = {'word':'λόγος','lang_code':'grc','pos':'noun','senses':[{'glosses':['word']}], 'forms':[]}
        builder.record((json.dumps(entry)+'\n').encode(),1,3,'grc',supplement=True);builder.flush()
        self.assertEqual(db.execute('SELECT count(*) FROM entry').fetchone()[0], 1)
        self.assertEqual(db.execute('SELECT count(*) FROM source_review').fetchone()[0], 0)

    def test_ordered_gloss_paths_and_examples_do_not_invent_parent_senses(self):
        entry = {'id':1,'sourceLine':7,'lang':'la','page':'amo','etymology':None,
          'content':{'senses':[{'glosses':['love','value'], 'examples':[{'text':'amo'}]}]},
          'senses':[{'ordinal':0,'glosses':['love','value'],'grammar':{}}],
          'relations':[],'links':[]}
        attach_model(entry, 'source-a', 'record-a')
        self.assertEqual(entry['senses'][0]['glossPath'], ['love','value'])
        self.assertIsNone(entry['senses'][0]['parentKey'])
        self.assertEqual(entry['senses'][0]['examples'], [{'text':'amo'}])
        self.assertEqual(entry['etymologyGroup']['grouping'], 'unassigned')
        self.assertEqual(entry['identity']['locator'],'sha256:source-a/line/7')


if __name__ == '__main__':
    unittest.main()
