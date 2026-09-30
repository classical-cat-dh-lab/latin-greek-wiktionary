"""Regression evidence for meaning-preserving import and graph construction."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
import unicodedata as ud
import zlib

from build import Builder, checked, js, link_parts, HERE
from lookup import lookup
import normalization as n
import rules
import repairs
import hashlib


class NormalizationTests(unittest.TestCase):
    def test_discretionary_soft_hyphen_is_not_a_letter(self):
        self.assertTrue(n.is_word('λοπαδο\u00adτεμαχο', 'grc'))
        for profile in n.PROFILES:
            self.assertEqual(n.key('λοπαδο\u00adτεμαχο','grc',profile),n.key('λοπαδοτεμαχο','grc',profile))
        self.assertFalse(n.is_word('λοπαδο\u200bτεμαχο','grc'))

    def test_canonical_equivalence(self):
        self.assertEqual(n.key('amāre','la','exact'), n.key('ama\u0304re','la','exact'))

    def test_quantities_do_not_define_identity(self):
        self.assertNotEqual(n.key('mālum','la','exact'),n.key('malum','la','exact'))
        self.assertEqual(n.key('MĀLUM','la','reading'),n.key('malum','la','reading'))

    def test_latin_spelling_is_opt_in(self):
        self.assertNotEqual(n.key('jūs','la'),n.key('ius','la'))
        self.assertEqual(n.key('jūs','la','spelling'),n.key('ius','la','spelling'))
        self.assertEqual(n.key('vīta','la','spelling'),n.key('uita','la','spelling'))

    def test_greek_accents_are_tiered(self):
        self.assertNotEqual(n.key('ἤ','grc','reading'),n.key('ἡ','grc','reading'))
        self.assertEqual(n.key('ἤ','grc'),n.key('ἡ','grc'))
        self.assertEqual(n.key('λόγος','grc','reading'),n.key('λόγοσ','grc','reading'))

    def test_iota_and_diaeresis_survive(self):
        self.assertNotEqual(n.key('ᾧ','grc'),n.key('ὧ','grc'))
        self.assertIn('\u0345',ud.normalize('NFD',n.key('ᾧ','grc')))
        self.assertNotEqual(n.key('αϊ','grc'),n.key('αι','grc'))

    def test_idempotence(self):
        for lang,word in [('la','JŪS'),('la','amāre'),('grc','ᾯ'),('grc','λόγος'),('grc','μετ᾽')]:
            for p in n.PROFILES:
                with self.subTest(lang=lang,word=word,profile=p):
                    self.assertEqual(n.key(n.key(word,lang,p),lang,p),n.key(word,lang,p))

    def test_word_boundaries(self):
        self.assertTrue(n.is_word('μετ᾽','grc'))
        self.assertTrue(n.is_word("'s",'la'))
        self.assertTrue(n.is_word('𐠞𐠪𐠐𐠵𐠩','grc'))
        self.assertTrue(n.is_word('𐀩𐀄𐀒','grc'))
        self.assertFalse(n.is_word('amo','grc'))
        for text in ['amātus sum','*amo','-que','amō + sum','amo\u200b']:
            self.assertFalse(n.is_word(text,'la'))


class RuleTests(unittest.TestCase):
    def test_source_review_requires_exact_original_bytes(self):
        payload=b'{"source":"original"}\n'
        review={('la',1):{'raw_sha256':hashlib.sha256(payload).hexdigest()}}
        self.assertIsNotNone(repairs.checked(review,'la',1,payload))
        with self.assertRaises(ValueError):repairs.checked(review,'la',1,payload+b' ')

    def test_formula_remains_content(self):
        result=rules.project_form({'form':'amātus + present active indicative of sum'}, {'lang_code':'la','pos':'verb','word':'amo'},None)
        self.assertEqual(result[:2],('periphrastic_formula',[]))

    def test_table_tense_and_meaning(self):
        self.assertEqual(rules.context_tense('Attic perfect present','grc-conj'),('perfect',['present']))
        self.assertEqual(rules.context_tense('Epic imperfect pluperfect present','grc-conj'),('pluperfect',['present','imperfect']))
        self.assertEqual(rules.context_tense('future present','grc-conj'),('present',['future']))
        self.assertEqual(rules.context_tense('future perfect','grc-conj'),('future-perfect',[]))

    def test_context_does_not_cross_source(self):
        f={'form':'λύω','tags':['indicative'],'source':'different'}
        result=rules.project_form(f,{'lang_code':'grc','pos':'verb','word':'λύω'}, {'header':'present','template':'grc-conj','source':'conjugation'})
        self.assertNotIn('present',result[2]['tags'])

    def test_article_requires_links(self):
        context={'header':'Attic declension-3','template':'grc-decl','source':'declension'}
        e={'lang_code':'grc','pos':'noun','word':'κύων'}
        f={'form':'ἡ κῠ́ων','tags':['nominative','singular'],'source':'declension','links':[['ἡ','ἡ#Ancient_Greek'],['κῠ́ων','κύων#Ancient_Greek']]}
        self.assertEqual(rules.project_form(f,e,context)[1],['κῠ́ων'])
        del f['links']
        self.assertEqual(rules.project_form(f,e,context)[1],[])

    def test_leaked_romanization_is_retained(self):
        r=rules.project_form({'form':'adeukésĭn','source':'declension'}, {'lang_code':'grc','pos':'adj','word':'ἀδευκής'}, {'source':'declension','template':'grc-decl','header':'Attic'})
        self.assertEqual(r[:2],('romanization_recovered',[]))

    def test_movable_nu_is_not_a_phrase(self):
        r=rules.project_form({'form':'λύουσι(ν)'},{'lang_code':'grc','pos':'verb','word':'λύω'},None)
        self.assertEqual(r[1],['λύουσι','λύουσιν'])

    def test_uncertain_gloss_stays_uncertain(self):
        s={'raw_glosses':['(meaning uncertain; perhaps bitter)'],'tags':['empty-gloss']}
        self.assertEqual(rules.project_sense(s)[1:3],(['(meaning uncertain; perhaps bitter)'],'raw_glosses'))

    def test_correlated_person_number(self):
        tags=['first-person','third-person','singular','plural','imperfect']
        g=rules.grammar(tags,['first-person singular/third-person plural imperfect active indicative'])
        self.assertEqual(g['alternatives'],[['first-person','imperfect','singular'],['imperfect','plural','third-person']])

    def test_unresolved_bundle_is_not_expanded(self):
        g=rules.grammar(['masculine','neuter','nominative','vocative'])
        self.assertEqual(g['interpretation'],'bundle_not_cartesian')
        self.assertNotIn('alternatives',g)

    def test_partial_person_number_evidence_is_not_expanded(self):
        tags=['first-person','third-person','singular','plural','imperfect']
        for gloss in ['first-person singular or third-person plural or singular imperfect',
                      'A first-person singular example; compare third-person plural imperfect']:
            self.assertNotIn('alternatives',rules.grammar(tags,[gloss]))

    def test_infinitive_finite_tags_are_repaired_in_qualified_tables(self):
        e={'word':'λύω','pos':'verb','lang_code':'grc'}
        f={'form':'λύεσθαι','source':'conjugation','tags':['infinitive','middle','passive','plural']}
        c={'header':'present','source':'conjugation','template':'grc-conj'}
        r=rules.project_form(f,e,c)
        self.assertEqual(set(r[2]['tags']),{'infinitive','middle','passive','present'})
        self.assertIn('infinitive_finite_tags_removed',r[3])
        self.assertIn('plural',f['tags'])

    def test_head_metadata_does_not_become_a_word(self):
        e={'word':'κύων','pos':'noun','lang_code':'grc'}
        self.assertEqual(rules.project_form({'form':'first','tags':['canonical']},e,None)[:2],('prose_metadata',[]))

    def test_bounded_suffix_label_preserves_spelling(self):
        e={'word':'κακός','pos':'adj','lang_code':'grc'}
        self.assertEqual(rules.project_form({'form':'κᾰκῐ́ων Epic'},e,None)[1],['κᾰκῐ́ων'])
        self.assertEqual(rules.project_form({'form':'ὀνόμᾰσῐv'},e,None)[1],[])

    def test_link_language_and_external_scope(self):
        self.assertEqual(link_parts('amo#Latin','x'),('amo','la','Latin','pending'))
        self.assertEqual(link_parts('#English','nomen')[3],'other_language_or_anchor')
        self.assertEqual(link_parts('https://example.org/a','x')[3],'external')


def fixture(word,pos,gloss,forms=(),target=None):
    s={'glosses':[gloss]}
    if target:
        s.update(form_of=[{'word':target}],tags=['form-of'],links=[[target,target.replace('ā','a').replace('ō','o')+'#Latin']])
    return {'word':word,'lang_code':'la','lang':'Latin','pos':pos,'senses':[s],'forms':list(forms), 'unmodeled':{'keep':['all',17]}}


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(':memory:')
        self.db.executescript((HERE/'schema.sql').read_text())
        self.db.execute('INSERT INTO source VALUES (1,\'la\',\'fixture\',\'fixture\',0,0)')
        self.b=Builder(self.db)
        self.entries=[
            fixture('amo','verb','to love',[{'form':'amō','tags':['canonical']},{'form':'amātus + present active indicative of sum'}]),
            fixture('amatus','verb','loved; having been loved',[{'form':'amātus','tags':['canonical']},{'form':'amātīs','tags':['dative','plural']}],'amō'),
            fixture('amatis','verb','dative plural of amātus',[{'form':'amātīs','tags':['canonical']}],'amātus'),
            fixture('amatus','noun','a loved one',[{'form':'amātus','tags':['canonical']}]),
            fixture('malum','noun','an apple',[{'form':'mālum','tags':['canonical']}]),
            fixture('malum','noun','an evil',[{'form':'malum','tags':['canonical']}]),
        ]
        for i,e in enumerate(self.entries,1):self.b.record((js(e)+'\n').encode(),i,1,'la')
        self.b.flush();self.b.indexes()
        self.b.resolve_links();self.b.make_surfaces();self.b.resolve_relations();self.b.resolve_form_links();self.b.make_ownership()

    def tearDown(self):
        self.db.close()

    def test_lossless_unknown_fields(self):
        raw=self.db.execute('SELECT raw_zlib FROM entry WHERE id=1').fetchone()[0]
        self.assertEqual(json.loads(zlib.decompress(raw)),self.entries[0])

    def test_participle_path_keeps_noun_independent(self):
        roots=self.db.execute('SELECT root_id,path FROM ownership WHERE entry_id=3').fetchall()
        self.assertEqual(roots,[(1,'[3,2,1]')])
        self.assertEqual(self.db.execute('SELECT root_id FROM ownership WHERE entry_id=4').fetchall(),[(4,)])

    def test_formula_never_indexed(self):
        self.assertEqual(self.db.execute("SELECT count(*) FROM surface WHERE text LIKE '% + %'").fetchone()[0],0)
        self.assertEqual(lookup(self.db,'amātus sum','la')['status'],'not_a_single_word')

    def test_lookup_preserves_homographs_and_exact_ranking(self):
        r=lookup(self.db,'mālum','la')
        self.assertEqual({x['entry_id'] for x in r['matches']},{5,6})
        self.assertEqual(r['matches'][0]['match_tier'],'exact')

    def test_internal_links_resolve(self):
        self.assertGreater(self.db.execute('SELECT count(*) FROM link_target').fetchone()[0],0)

    def test_link_to_form_without_page_resolves_locally(self):
        self.db.execute("INSERT INTO link VALUES (999,'amātīs#Latin','amātīs','la','Latin','missing_local_target')")
        self.b.resolve_form_links()
        self.assertEqual(self.db.execute('SELECT status FROM link WHERE id=999').fetchone()[0],'local_form')
        self.assertIn((2,),self.db.execute('SELECT entry_id FROM link_target WHERE link_id=999').fetchall())

    def test_source_link_gender_label_and_conjunction(self):
        for target in ['amātus m or f','and amātus','amātus /amo']:
            hints={'links':[['amātus','amatus#Latin'],['amo','amo#Latin']]}
            candidates,state,_=self.b.relation_candidates('la','verb','form_of',target,hints)
            self.assertEqual(state,'resolved')
            self.assertIn(2,[eid for eid,_ in candidates])

    def test_foreign_keys_and_accounting(self):
        self.assertIsNone(self.db.execute('PRAGMA foreign_key_check').fetchone())
        self.assertEqual(self.db.execute('SELECT count(*) FROM form WHERE ordinal>=0').fetchone()[0],sum(len(e['forms']) for e in self.entries))

    def test_pin_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'source';path.write_bytes(b'{}\n')
            with self.assertRaises(ValueError):checked(path,{'bytes':3,'sha256':'wrong'})

    def test_redirect_cycle_terminates(self):
        self.b.redirects={'x':'y','y':'x'}
        self.b.follow_redirect.cache_clear()
        self.assertEqual(self.b.follow_redirect('x','')[3],'redirect_cycle')

    def test_ownership_cycle_keeps_all_reachable_roots(self):
        db=sqlite3.connect(':memory:');db.executescript((HERE/'schema.sql').read_text())
        db.execute('INSERT INTO source VALUES (1,\'la\',\'fixture\',\'fixture\',0,0)')
        b=Builder(db)
        a=fixture('a','noun','inflection of b and c',target='b')
        a['senses'][0]['form_of'].append({'word':'c'})
        a['senses'][0]['links'].append(['c','c#Latin'])
        bb=fixture('b','noun','inflection of a and d',target='a')
        bb['senses'][0]['form_of'].append({'word':'d'})
        bb['senses'][0]['links'].append(['d','d#Latin'])
        for i,e in enumerate([a,bb,fixture('c','noun','root c'),fixture('d','noun','root d')],1):
            b.record((js(e)+'\n').encode(),i,1,'la')
        b.flush();b.indexes();b.resolve_relations();b.make_ownership()
        for eid in (1,2):
            self.assertEqual({r[0] for r in db.execute('SELECT root_id FROM ownership WHERE entry_id=?',(eid,))},{3,4})
        db.close()


if __name__ == '__main__':
    unittest.main()
