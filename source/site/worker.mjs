import {bucket,key,matches,groupReadings,prepareIndex,queryFallbacks} from './core.mjs';
import {verifiedResponse} from './store.mjs';
import {API_VERSION,validateRequest,validateManifest,failure} from './contract.mjs';
let manifest, files, cache;
const memo = new Map();
let expanded = 0, peakExpanded = 0;
const MAX_EXPANDED = 24 * 1024 * 1024;
async function init() {
  if (manifest) return;
  const r = await fetch('./manifest.json');
  if (!r.ok) throw new Error('Dictionary manifest unavailable');
  const next = validateManifest(await r.json());
  const nextFiles = new Map(next.files.map(f=>[f.path,f]));
  // Publish complete state only; a failed initialization must remain retryable.
  files = nextFiles; manifest = next;
}
async function cachedResponse(url, spec) {
  // Persistent storage is optional for online lookup. Always verify cached bytes.
  try {
    cache ??= await caches.open('formlex-'+manifest.package);
    const response = await cache.match(url) ?? await caches.match(url);
    if (!response) return null;
    try {return await verifiedResponse(response,spec);}
    catch {await cache.delete(url);}
  } catch {cache = null;}
  return null;
}
async function load(path) {
  await init();
  if (memo.has(path)) { const row=memo.get(path);memo.delete(path);memo.set(path,row);return row.value; }
  const spec=files.get(path);
  if (!spec) throw new Error('Missing manifest item: '+path);
  const url=new URL(path, self.location.href).href;
  let response=await cachedResponse(url,spec);
  if (!response) response=await verifiedResponse(await fetch(url,{cache:'no-store'}),spec);
  const text=await new Response(response.body.pipeThrough(new DecompressionStream('gzip'))).text();
  const decoded=JSON.parse(text), bytes=spec.expandedBytes;
  const value=path.startsWith('data/index/')?prepareIndex(decoded,path.includes('/la-')?'la':'grc'):decoded;
  memo.set(path,{value,bytes});expanded+=bytes;
  while(expanded>MAX_EXPANDED && memo.size>1) {const [k,v]=memo.entries().next().value;expanded-=v.bytes;memo.delete(k);}
  peakExpanded=Math.max(peakExpanded,expanded);
  return value;
}
async function entry(id) {
  if(id>manifest.counts.entry) throw failure('ENTRY_NOT_FOUND','Entry unavailable: '+id);
  const block=Math.floor((id-1)/manifest.block).toString().padStart(4,'0');
  const e=(await load('data/entries/'+block+'.json.gz'))[id];
  if (!e) throw new Error('Entry unavailable: '+id);
  return e;
}
async function lookup(word,lang,profile) {
  let found=[],matchedInput=word;
  for(const input of [word,...queryFallbacks(word)]) {
    const n=bucket(key(input,lang,'spelling'),manifest.buckets).toString().padStart(4,'0');
    const index=await load(`data/index/${lang}-${n}.json.gz`);
    found=matches(index.get(key(input,lang,'spelling'))??[],input,lang,profile);
    if(found.length){matchedInput=input;break;}
  }
  const entries=new Map();
  // Bound parallel decompression and transient memory even for broad homographs.
  for (const id of new Set(found.map(x=>x.row[1]))) entries.set(id,await entry(id));
  for (const e of [...entries.values()]) for(const o of e.owners) if(!entries.has(o.id)) entries.set(o.id,await entry(o.id));
  return {groups:groupReadings(found,entries),occurrences:found.length,matchedInput};
}
// Serial requests bound transient memory. The UI ignores stale responses.
let queue=Promise.resolve();
self.onmessage=({data}) => {queue=queue.then(async()=>{
  try {
    validateRequest(data);
    await init();
    let result;
    if(data.action==='lookup') result=await lookup(data.word,data.lang,data.profile);
    else if(data.action==='entries') {result=[];for(const id of data.ids) result.push(await entry(id));}
    else result={edition:manifest.edition,bytes:manifest.bytes,package:manifest.package,contract:manifest.contract,version:manifest.version};
    self.postMessage({id:data.id,apiVersion:API_VERSION,result,metrics:{cachedExpandedBytes:expanded,peakCachedExpandedBytes:peakExpanded}});
  } catch(error) {self.postMessage({id:data?.id,apiVersion:API_VERSION,error:error.message,errorCode:error.code??'DICTIONARY_UNAVAILABLE'});}
});};
