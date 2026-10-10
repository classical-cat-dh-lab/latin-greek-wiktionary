// Exercise the production worker and service worker with explicit storage faults.
import assert from 'node:assert/strict';
import test from 'node:test';
import {readFile} from 'node:fs/promises';
import {createHash, randomUUID, webcrypto} from 'node:crypto';
import {gzipSync} from 'node:zlib';
import {runInNewContext} from 'node:vm';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const site = process.env.WIKTIONARY_TEST_SITE
  ? pathToFileURL(resolve(process.env.WIKTIONARY_TEST_SITE) + '/')
  : new URL('../site/', import.meta.url);
const origin = 'https://dictionary.test/wiktionary/';
const sha = bytes => createHash('sha256').update(bytes).digest('hex');
const entry = {id:1, headword:'amō', forms:[[1,0,'amō','word',null,{}]],
  senses:[], tables:{}, owners:[{id:1,status:'lexical_path',path:[1]}]};
const payloads = new Map([
  ['data/index/la-0000.json.gz', [['amō',1,0,1]]],
  ['data/entries/0000.json.gz', {'1':entry}],
]);
const bytes = new Map([...payloads].map(([path,value]) => [path,gzipSync(JSON.stringify(value))]));
const manifest = {schema:1, apiVersion:1, contract:'lexical-entry/1', package:'fixture',
  edition:'fixture-edition', shellBuild:'fixture-build', block:256, buckets:1, counts:{entry:1},
  files:[...bytes].map(([path,b]) => ({path,bytes:b.length,sha256:sha(b),
    expandedBytes:Buffer.byteLength(JSON.stringify(payloads.get(path)))}))};

async function runtime(t, faults = {}) {
  const saved = new Map(['self','caches','fetch'].map(k => [k,Object.getOwnPropertyDescriptor(globalThis,k)]));
  t.after(() => {for (const [k,descriptor] of saved) {
    if (descriptor) Object.defineProperty(globalThis,k,descriptor); else delete globalThis[k];
  }});
  const pending = new Map(), calls = {manifest:0, data:0, open:0};
  globalThis.self = {location:{href:origin+'worker.mjs'},
    postMessage:reply => pending.get(reply.id)(reply)};
  const cache = {
    async match(url) {
      if (faults.match) throw new Error('Cache read refused');
      if (faults.cached) return new Response(faults.corruptCache ? 'damaged' : bytes.get(new URL(url).pathname.slice('/wiktionary/'.length)));
    },
    async delete() {if (faults.delete) throw new Error('Cache deletion refused');},
  };
  globalThis.caches = {async open() {
    calls.open++;
    if (faults.open || (faults.openOnce && calls.open===1)) throw new Error('Cache open refused');
    return cache;
  }, async match() {if (faults.match) throw new Error('Cache read refused');}};
  globalThis.fetch = async input => {
    const path = new URL(input,origin).pathname.slice('/wiktionary/'.length);
    if (path==='manifest.json') {
      calls.manifest++;
      return Response.json(faults.manifestOnce && calls.manifest===1 ? {...manifest,files:null} : manifest);
    }
    calls.data++;
    if (faults.offline) throw new Error('Network unavailable');
    return new Response(faults.corruptNetwork ? 'damaged' : bytes.get(path));
  };
  await import(new URL('worker.mjs?test='+randomUUID(),site));
  let id = 0;
  const ask = body => new Promise(resolve => {
    pending.set(++id,reply => {pending.delete(reply.id);resolve(reply);});
    self.onmessage({data:{id,...body}});
  });
  return {ask,calls};
}

const query = {action:'lookup',word:'amō',lang:'la',profile:'tolerant'};
function found(reply) {
  assert.equal(reply.error,undefined);
  assert.equal(reply.result.occurrences,1);
  assert.equal(reply.result.groups[0].entry.headword,'amō');
}

test('verified cached data supports lookup without the network', async t => {
  const {ask,calls} = await runtime(t,{cached:true,offline:true});
  found(await ask(query));
  assert.equal(calls.data,0);
  assert.deepEqual((await ask({...query,word:'missing'})).result.groups,[]);
});

for (const fault of ['open','match']) test(`online lookup survives CacheStorage ${fault} failure`, async t => {
  const {ask,calls} = await runtime(t,{[fault]:true});
  assert.equal((await ask({action:'init'})).error,undefined);
  found(await ask(query));
  assert.equal(calls.data,2);
});

test('a transient storage failure does not poison subsequent requests', async t => {
  const {ask} = await runtime(t,{openOnce:true});
  await ask({action:'init'});
  found(await ask(query));
  assert.equal((await ask({action:'entries',ids:[1]})).result[0].id,1);
});

test('a malformed manifest can be retried in the same worker', async t => {
  const {ask,calls} = await runtime(t,{manifestOnce:true});
  assert.ok((await ask({action:'init'})).error);
  found(await ask(query));
  assert.equal(calls.manifest,2);
});

test('damaged cache data can recover even when deletion is refused', async t => {
  const {ask} = await runtime(t,{cached:true,corruptCache:true,delete:true});
  found(await ask(query));
});

test('storage fallback still rejects damaged network data', async t => {
  const {ask} = await runtime(t,{open:true,corruptNetwork:true});
  const reply = await ask(query);
  assert.equal(reply.errorCode,'INTEGRITY_ERROR');
  assert.equal(reply.result,undefined);
});

test('unavailable files produce an error and a later request can recover', async t => {
  const faults = {open:true,offline:true}, {ask} = await runtime(t,faults);
  const reply = await ask(query);
  assert.equal(reply.errorCode,'DICTIONARY_UNAVAILABLE');
  assert.equal(reply.result,undefined);
  faults.offline=false;
  found(await ask(query));
});

async function serviceWorker(faults = {}) {
  const handlers = {}, calls = {network:0};
  const code = (await readFile(new URL('sw.js',site),'utf8'))
    .replace('__EDITION__',manifest.edition).replace('__BUILD__',manifest.shellBuild);
  runInNewContext(code, {URL,Response,crypto:webcrypto,
    self:{registration:{scope:origin},addEventListener:(name,handler)=>{handlers[name]=handler;}},
    caches:{async open(name) {return {
      async match() {
        if (name.startsWith('formlex-bootstrap-')) return Response.json(manifest);
        if (faults.match) throw new Error('Cache read refused');
        return new Response('damaged cache');
      },
    };}},
    fetch:async () => {calls.network++;return new Response('network bytes');},
  });
  const request = new Request(origin+'data/index/la-0000.json.gz', faults.noStore ? {cache:'no-store'} : {});
  let response;
  handlers.fetch({request,respondWith:value=>{response=value;}});
  return {text:await (await response).text(),calls};
}

test('service worker uses the network when its package cache cannot be read', async () => {
  assert.equal((await serviceWorker({match:true})).text,'network bytes');
});

test('explicit data recovery bypasses a damaged service-worker cache', async () => {
  assert.equal((await serviceWorker({noStore:true})).text,'network bytes');
});
