import {tokenize,languageOf,groupReadings} from './core.mjs';
import {settings} from './store.mjs';
import {offlineInit} from './offline.mjs';
const $=id=>document.getElementById(id);
const worker=new Worker('./worker.mjs',{type:'module'}), pending=new Map();
let sequence=0, view=0, currentWord=null, selected=null;
function request(action, extra={}) {
  return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject});worker.postMessage({id,action,...extra});});
}
worker.onmessage=({data})=>{const p=pending.get(data.id);if(!p)return;pending.delete(data.id);window.readerMetrics=data.metrics;data.error?p.reject(new Error(data.error)):p.resolve(data.result);};
worker.onerror=event=>{for(const p of pending.values())p.reject(new Error(event.message));pending.clear();};
function el(tag,text,cls) {const n=document.createElement(tag);if(text!==undefined)n.textContent=String(text);if(cls)n.className=cls;return n;}
function lazy(title,build) {
  const d=el('details');d.append(el('summary',title));let built=false;
  d.addEventListener('toggle',()=>{if(d.open&&!built){built=true;d.append(build());}});return d;
}
function label(value){return value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase());}
function paged(items,render,count=50) {
  const box=el('div');let cursor=0;
  const more=el('button','Show more');more.type='button';
  function next(){const end=Math.min(cursor+count,items.length);while(cursor<end)box.insertBefore(render(items[cursor++]),more);more.hidden=cursor===items.length;more.textContent=`Show more (${items.length-cursor} remaining)`;}
  box.append(more);more.addEventListener('click',next);next();return box;
}
function grammar(g) {
  const p=el('div',undefined,'grammar');
  if(g.alternatives) {p.append(el('span','Alternative readings:'));const ul=el('ul');for(const a of g.alternatives)ul.append(el('li',a.join(' · ')));p.append(ul);}
  else if(g.tags?.length)p.append(el('span',g.tags.join(' · ')));
  if(g.interpretation==='bundle_not_cartesian')p.append(el('p','Source feature bundle; combinations are not individually specified.','notice'));
  if(g.tense_meaning?.length)p.append(el('p','Meaning: '+g.tense_meaning.join(' / ')));
  if(g.source_label)p.append(el('p',g.source_label));
  if(g.review_note)p.append(el('p',g.review_note));
  if(g.article_wrapper)p.append(el('p','Source article: '+g.article_wrapper));
  return p;
}
function external(target,text) {
  const a=el('a',text);try{const u=new URL(target);if(!['https:','http:'].includes(u.protocol))return el('span',text);a.href=u.href;a.target='_blank';a.rel='noopener noreferrer';return a;}catch{return el('span',text);}
}
function sourceURL(entry){return 'https://en.wiktionary.org/wiki/'+encodeURIComponent(entry.page)+'#'+(entry.lang==='la'?'Latin':'Ancient_Greek');}
function linkNode(entry,item) {
  const [pointer,text,target,status,ids]=item;
  const box=el('span');
  if(ids.length){const b=el('button',text||target,'internal-link');b.type='button';b.dataset.targetIds=ids.join(',');b.addEventListener('click',()=>navigate(ids,text||target));box.append(b);}
  else {box.append(el('span',text||target));box.append(el('span',` — ${status.replaceAll('_',' ')}. `,'link-status'));const absolute=/^https?:/u.test(target)?target:'https://en.wiktionary.org/wiki/'+encodeURIComponent(target.startsWith('#')?entry.page+target:target).replaceAll('%23','#');box.append(external(absolute,'View source online'));}
  return box;
}
// An intentionally lossless text view of supplemental dictionary fields. It is
// built only when opened, paginated, and never interprets source HTML as markup.
function structured(value,entry,depth=0) {
  if(value===null || value===undefined)return el('span','');
  if(typeof value!=='object')return /^https?:\/\//u.test(String(value))?external(String(value),String(value)):el('span',value);
  if(Array.isArray(value)){
    return paged(value,v=>{const li=el('div',undefined,'content-item');li.append(structured(v,entry,depth+1));return li;});
  }
  const dl=el('dl');
  for(const [k,v] of Object.entries(value)){
    dl.append(el('dt',label(k)));const dd=el('dd');
    if(k==='links'&&Array.isArray(v)){
      for(const pair of v){if(!Array.isArray(pair)){dd.append(structured(pair,entry,depth+1));continue;}const found=entry.links.find(l=>l[1]===pair[0]&&l[2]===pair[1]);dd.append(found?linkNode(entry,found):el('span',pair.join(' → ')),document.createTextNode(' '));}
    } else if(v&&typeof v==='object'&&JSON.stringify(v).length>500)dd.append(lazy(Array.isArray(v)?`${v.length} items`:'Read details',()=>structured(v,entry,depth+1)));
    else dd.append(structured(v,entry,depth+1));dl.append(dd);
  }
  return dl;
}
function entryCard(group) {
  const {entry,readings,unresolved}=group;
  const card=el('article',undefined,'reader-entry');card.dataset.entryId=entry.id;card.lang=entry.lang==='la'?'la':'grc';
  card.append(el('h3',entry.headword||entry.word,'entry-title'));
  card.append(el('p',`${entry.lang==='la'?'Latin':'Ancient Greek'} · ${entry.pos}${entry.etymology?' · Etymology '+entry.etymology:''}`,'entry-meta'));
  if(unresolved)card.append(el('p','The source identifies a form or variant, but its owning entry is unresolved. Available source information follows.','notice'));
  const lexical=entry.senses.filter(s=>s.role==='lexical');
  const senses=lexical.length?lexical:entry.senses;
  for(const sense of senses) {
    const s=el('div',undefined,'sense');
    if(sense.glosses.length)for(const gloss of sense.glosses)s.append(el('p',gloss));
    else s.append(el('p',sense.grammar.definition_status==='source_no_definition'?'Wiktionary supplies no definition for this source entry (checked 30 September 2026).':sense.grammar.definition_status==='source_page_unavailable'?'No definition in the capture; the source page was unavailable when checked on 30 September 2026.':'No definition supplied in this source record.','notice'));
    if(sense.grammar.tags?.length)s.append(grammar(sense.grammar));
    if(sense.sourceGlosses.length&&JSON.stringify(sense.sourceGlosses)!==JSON.stringify(sense.glossPath))s.append(lazy('Source sense wording',()=>{const box=el('div');for(const text of sense.sourceGlosses)box.append(el('p',text));return box;}));
    const supplement=Object.fromEntries(Object.entries(sense.annotations).filter(([k])=>!['categories','links'].includes(k)));
    if(sense.examples.length)supplement.examples=sense.examples;
    if(Object.keys(supplement).length)s.append(lazy('Examples, usage & related words',()=>structured(supplement,entry)));
    card.append(s);
  }
  if(!senses.length)card.append(el('p','No definition supplied in this source record.','notice'));
  if(readings.length) {
    const renderReading=r=>{
      const box=el('div',undefined,'reading');box.append(el('p',`${r.surface} · ${r.tier} match${r.sourceId!==entry.id?' · via '+r.sourceHead:''}`,'entry-meta'));
      box.append(grammar(r.form[5]));
      if(r.table?.header)box.append(el('p',r.table.header,'notice'));
      if(r.sourceId!==entry.id){
        for(const s of r.sourceSenses){for(const g of s.glosses)box.append(el('p',g));box.append(grammar(s.grammar));}
        box.append(lazy('Supplementary source-form content',()=>{
          const body=el('div','Loading source-form details…','entry-content');
          request('entries',{ids:[r.sourceId]}).then(([source])=>body.replaceChildren(structured(source.content,source))).catch(error=>{body.textContent=error.message;});return body;
        }));
      }
      return box;
    };
    card.append(lazy(`Matching forms & readings (${readings.length})`,()=>paged(readings,renderReading,20)));
  }
  if(entry.etymologyGroup.text)card.append(lazy('Etymology',()=>el('p',entry.etymologyGroup.text)));
  if(entry.pronunciations.length)card.append(lazy('Pronunciation (text)',()=>structured(entry.pronunciations,entry)));
  card.append(lazy(`Forms & table notes (${entry.forms.length})`,()=>{
    return paged(entry.forms,f=>{const box=el('div');box.append(el('p',f[2]),grammar(f[5]));if(entry.tables[f[4]])box.append(el('p',entry.tables[f[4]].header,'notice'));if(!['word','headword','canonical'].includes(f[3]))box.append(el('p',label(f[3]),'notice'));return box;},30);
  }));
  if(entry.links.length)card.append(lazy('Explore dictionary links',()=>{
    const seen=new Set(), links=entry.links.filter(l=>{const k=JSON.stringify(l.slice(1));if(seen.has(k))return false;seen.add(k);return true;});
    return paged(links,l=>{const p=el('p');p.append(linkNode(entry,l));return p;});
  }));
  const relations=entry.relations.filter(r=>r[4]!=='source_explanation');
  if(relations.length)card.append(lazy('Lexical relations',()=>paged(relations,r=>{const p=el('p',label(r[1])+': ');p.append(linkNode(entry,[r[0],r[2],r[2],r[4],r[5]]));return p;})));
  const rest=entry.metadata;
  const content=lazy('Further dictionary content',()=>structured(rest,entry));content.classList.add('entry-content');card.append(content);
  if(entry.review)card.append(lazy('Source review & corrections',()=>structured(entry.review,entry)));
  if(entry.relationReviews)card.append(lazy('Relation review',()=>structured(entry.relationReviews,entry)));
  const note=el('p',undefined,'source-note');note.append(external(entry.provenance.pageUrl,'Wiktionary source'),document.createTextNode(' · '),external('https://en.wiktionary.org/w/index.php?title='+encodeURIComponent(entry.page)+'&action=history','Contributors & history'),document.createTextNode(` · Capture ${entry.provenance.captureDate} · ${entry.lang}:${entry.sourceLine}`));if(entry.provenance.revisionUrl)note.append(document.createTextNode(' · '),external(entry.provenance.revisionUrl,'Fixed revision'));card.append(note);
  return card;
}
function showGroups(groups,title,description) {
  const output=$('reader-output');output.replaceChildren(el('h2',title));
  if(description)output.append(el('p',description,'notice'));
  if(!groups.length)output.append(el('p','No match in this dictionary snapshot under the selected profile. Try another matching option or check the original spelling.'));
  else output.append(paged(groups,entryCard,30));
}
async function lookup(word,lang,button) {
  const ticket=++view;currentWord={word,lang};$('back').hidden=true;
  selected?.setAttribute('aria-pressed','false');selected=button;button?.setAttribute('aria-pressed','true');
  $('reader-output').setAttribute('aria-busy','true');$('status').textContent='Looking up '+word+'…';
  const started=performance.now();
  try {
    const result=await request('lookup',{word,lang,profile:$('profile').value});
    if(ticket!==view)return;
    showGroups(result.groups,word,`${result.groups.length} dictionary candidates · ${result.occurrences} matching form occurrences${result.matchedInput!==word?' · Looked up '+result.matchedInput+' after separating punctuation':''}`);
    $('status').textContent=`Complete · ${(performance.now()-started).toFixed(0)} ms`;
  } catch(error){if(ticket===view){$('reader-output').replaceChildren(el('p',error.message,'error'));$('status').textContent='Lookup unavailable';}}
  finally{if(ticket===view)$('reader-output').setAttribute('aria-busy','false');}
}
async function navigate(ids,title) {
  const ticket=++view;$('reader-output').setAttribute('aria-busy','true');$('status').textContent='Opening '+title+'…';
  try {
    const source=await request('entries',{ids}), entries=new Map(source.map(e=>[e.id,e]));
    const missing=[...new Set(source.flatMap(e=>e.owners.map(o=>o.id)))].filter(id=>!entries.has(id));
    if(missing.length)for(const e of await request('entries',{ids:missing}))entries.set(e.id,e);
    const occurrences=source.map(e=>{const f=e.forms.find(x=>x[1]===-1)??e.forms[0];return f?{row:[e.word,e.id,f[1],f[0]],tier:0}:null;}).filter(Boolean);
    if(ticket!==view)return;
    showGroups(groupReadings(occurrences,entries),title,'Linked dictionary entries');$('status').textContent='Complete · Local dictionary link';$('back').hidden=!currentWord;
  }catch(error){if(ticket===view)$('reader-output').replaceChildren(el('p',error.message,'error'));}
  finally{if(ticket===view)$('reader-output').setAttribute('aria-busy','false');}
}
function submit(event) {
  event?.preventDefault();++view;const text=$('input').value, spans=tokenize(text), words=spans.filter(s=>s.word);
  $('results').hidden=!words.length;$('passage').replaceChildren();$('word-list-items').replaceChildren();$('reader-output').replaceChildren();
  $('status').textContent=words.length?`${words.length} words · Select a word`:'Enter a word or passage.';
  const seen=new Set();let first;
  for(const span of spans){
    if(!span.word){$('passage').append(document.createTextNode(span.text));continue;}
    const lang=$('mode').value==='auto'?span.lang:$('mode').value;
    const b=el('button',span.text,'passage-word');b.type='button';b.lang=lang;b.setAttribute('aria-pressed','false');b.addEventListener('click',()=>lookup(span.text,lang,b));$('passage').append(b);first??={word:span.text,lang,b};
    const id=lang+'|'+span.text;if(!seen.has(id)){seen.add(id);const c=el('button',span.text,'word-chip');c.type='button';c.addEventListener('click',()=>lookup(span.text,lang,b));$('word-list-items').append(c);}
  }
  if(first)lookup(first.word,first.lang,first.b);
}
$('analysis-form').addEventListener('submit',submit);
$('input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();submit();}});
$('clear-input').addEventListener('click',()=>{++view;currentWord=null;selected=null;$('input').value='';$('results').hidden=true;$('passage').replaceChildren();$('reader-output').replaceChildren();$('status').textContent='Ready';$('input').focus();});
$('back').addEventListener('click',()=>currentWord&&lookup(currentWord.word,currentWord.lang,selected));
$('profile').addEventListener('change',()=>currentWord&&lookup(currentWord.word,currentWord.lang,selected));
function theme(value){document.documentElement.dataset.theme=value;$('theme-toggle').setAttribute('aria-pressed',String(value==='dark'));}
$('theme-toggle').addEventListener('click',async()=>{const value=document.documentElement.dataset.theme==='dark'?'light':'dark';theme(value);try{await settings('put','theme',value);}catch{$('status').textContent='Theme changed; preference could not be saved.';}});
try{theme(await settings('get','theme')==='dark'?'dark':'light');}catch{/* A failed preference store does not prevent reading. */}
try{await request('init');$('status').textContent='Ready';}catch(error){$('status').textContent=error.message;}
offlineInit().catch(error=>{$('offline').hidden=false;$('offline-status').textContent=error.message;});
for(const id of ['about','offline-help'])document.querySelector(`a[href="#${id}"]`).addEventListener('click',()=>{$(id).open=true;});
