import assert from 'node:assert/strict';
import {readFile,writeFile} from 'node:fs/promises';
import {gunzipSync} from 'node:zlib';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
const [siteArg,expectArg,outputArg]=process.argv.slice(2),site=resolve(siteArg),expected=resolve(expectArg);
const {key,bucket,profiles,matches,prepareIndex,tokenize}=await import(pathToFileURL(resolve(site,'core.mjs')));
const report={started:new Date().toISOString(),postings:0,surfaces:0,profileQueries:0,normalizationChecks:0,spanFailures:0,spanExamples:[],failures:[]};
const failure=(kind,detail)=>{if(report.failures.length<100)report.failures.push({kind,...detail});};
for(const lang of ['la','grc'])for(let n=0;n<1024;n++) {
  const name=lang+'-'+n.toString().padStart(4,'0');
  const rows=JSON.parse(gunzipSync(await readFile(resolve(site,'data/index',name+'.json.gz'))));
  const source=gunzipSync(await readFile(resolve(expected,name+'.jsonl.gz'))).toString().trim().split('\n').filter(Boolean).map(s=>JSON.parse(s));
  assert.deepEqual(rows.map(r=>JSON.stringify(r)).sort(),source.map(r=>JSON.stringify(r.slice(0,4))).sort(),name+' occurrence parity');
  report.postings+=rows.length;
  const indexed=prepareIndex(rows,lang), surfaces=new Map(), wanted=profiles.map(()=>new Map());
  for(const row of source){
    surfaces.set(row[0],row.slice(4));
    for(let i=0;i<4;i++){const k=row[i+4];if(!wanted[i].has(k))wanted[i].set(k,new Set());wanted[i].get(k).add(row[3]);}
  }
  for(const [surface,keys] of surfaces) {
    report.surfaces++;
    const spans=tokenize(surface), words=spans.filter(s=>s.word);
    if(spans.map(s=>s.text).join('')!==surface)throw new Error('Passage text changed');
    if(words.length!==1 || words[0].text!==surface){report.spanFailures++;if(report.spanExamples.length<1000)report.spanExamples.push({lang,surface,words:words.map(s=>s.text)});}
    for(let i=0;i<4;i++) {
      for(const input of [surface,surface.normalize('NFD')]){
        report.normalizationChecks++;
        if(key(input,lang,profiles[i])!==keys[i])failure('normalization',{lang,surface,profile:profiles[i],actual:key(input,lang,profiles[i]),expected:keys[i]});
      }
      if(bucket(key(surface,lang,'spelling'))!==n)throw new Error('Wrong shard');
      const got=matches(indexed.get(keys[3])??[],surface,lang,profiles[i]);
      const actual=got.map(x=>x.row[3]).sort((a,b)=>a-b), want=[...wanted[i].get(keys[i])].sort((a,b)=>a-b);
      if(actual.length!==want.length||actual.some((v,j)=>v!==want[j]))failure('candidate-set',{lang,surface,profile:profiles[i],actual,want});
      if(got.some((g,j)=>j>0&&g.tier<got[j-1].tier))failure('tier-order',{lang,surface});
      report.profileQueries++;
    }
  }
  if(n%256===0)console.log(name,report.surfaces.toLocaleString());
}
report.finished=new Date().toISOString();report.pass=report.failures.length===0&&report.spanFailures===0;
await writeFile(outputArg,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,spanExamples:report.spanExamples.slice(0,5)}));
if(!report.pass)process.exitCode=1;
