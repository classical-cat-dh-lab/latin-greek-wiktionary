import assert from 'node:assert/strict';
import test from 'node:test';
import {validateRequest,validateManifest} from '../site/contract.mjs';
test('protocol rejects malformed requests and incompatible packages',()=>{
  for(const request of [{},{id:1,action:'delete'},{id:1,action:'lookup',word:'amō',lang:'en',profile:'exact'},{id:1,action:'entries',ids:[-1]},{id:1,action:'init',apiVersion:2}])
    assert.throws(()=>validateRequest(request),e=>['INVALID_REQUEST','UNSUPPORTED_API'].includes(e.code));
  assert.throws(()=>validateManifest({schema:1}),e=>e.code==='UNSUPPORTED_PACKAGE');
  assert.doesNotThrow(()=>validateRequest({id:1,action:'entries',ids:[1,2],apiVersion:1}));
});
import {key,tokenize,matches,groupReadings,queryFallbacks} from '../site/core.mjs';
test('iota and diaeresis survive while accents are tiered',()=>{
  assert.notEqual(key('ᾧ','grc'),key('ὧ','grc'));assert.notEqual(key('αϊ','grc'),key('αι','grc'));
  assert.equal(key('ἤ','grc'),key('ἡ','grc'));assert.notEqual(key('ἤ','grc','reading'),key('ἡ','grc','reading'));
});
test('Latin spelling mapping is opt-in and canonical equivalence is exact',()=>{
  assert.equal(key('ma\u0304lum','la','exact'),key('mālum','la','exact'));
  assert.notEqual(key('jus','la'),key('ius','la'));assert.equal(key('jus','la','spelling'),key('ius','la','spelling'));
});
test('paragraph spans preserve punctuation, elision and astral scripts',()=>{
  const text="‘μετ᾽ ἐμοῦ.’\nAmātus sum; 's 𐠞𐠪𐠐𐠵𐠩, 𐀩𐀄𐀒!";
  const spans=tokenize(text);assert.equal(spans.map(s=>s.text).join(''),text);
  assert.ok(spans.some(s=>s.text==='Amātus'));assert.ok(spans.some(s=>s.text==='sum'));
  for(const s of spans)assert.equal(text.slice(s.start,s.end),s.text);
});
test('all normalized candidates survive with exact-first order',()=>{
  const rows=[['mālum',2,0,2],['malum',1,0,1],['malum',3,0,3]];
  assert.deepEqual(matches(rows,'malum','la').map(x=>x.row[3]),[1,3,2]);
  assert.deepEqual(matches(rows,'malum','la','exact').map(x=>x.row[3]),[1,3]);
});
test('form-only intermediaries route to every root and retain readings',()=>{
  const form={id:2,headword:'amātus',forms:[[20,0,'amātīs','word',null,{}]],senses:[],tables:{},owners:[{id:1,status:'lexical_path'},{id:3,status:'candidate_paths'}]};
  const entries=new Map([[2,form],[1,{id:1}],[3,{id:3}]]);
  const out=groupReadings([{row:['amātīs',2,0,20],tier:0}],entries);
  assert.deepEqual(out.map(x=>x.entry.id),[1,3]);assert.equal(out[0].readings[0].sourceId,2);
});
test('unresolved ownership keeps an explicit notice',()=>{
  const e={id:1,headword:'JUL',forms:[[1,-1,'JUL','title_word',null,{}]],senses:[],tables:{},owners:[{id:1,status:'unresolved_form'}]};
  assert.equal(groupReadings([{row:['JUL',1,-1,1],tier:0}],new Map([[1,e]]))[0].unresolved,true);
});
test('source punctuation and soft hyphens remain in selectable spans',()=>{
  for(const s of ["M.'",'M.’','i.e.','trāns-','λοπαδο\u00adτεμαχο','amō.'])assert.equal(tokenize(s).filter(x=>x.word)[0].text,s);
  assert.equal(key('λοπαδο\u00adτεμαχο','grc','exact'),'λοπαδοτεμαχο');
  assert.ok(queryFallbacks('amō.').includes('amō'));assert.deepEqual(queryFallbacks('trāns-'),[]);
});
test('compound abbreviation and elision punctuation remains selectable',()=>{
  for(const word of ['not.-Tīr.','M.-Emp.','n.-Tīr.',"M'.",'M’.','ᾰ̓ντ’-']) {
    const spans=tokenize(word);
    assert.equal(spans.length,1);assert.equal(spans[0].text,word);assert.ok(spans[0].word);
  }
  const text='amō...sum; amat--sum';
  assert.deepEqual(tokenize(text).filter(s=>s.word).map(s=>s.text),['amō...','sum','amat--','sum']);
  assert.equal(tokenize(text).map(s=>s.text).join(''),text);
});
