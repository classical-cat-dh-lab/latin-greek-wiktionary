// Shared by the browser worker and exhaustive Node qualification.
export const profiles = ['exact', 'reading', 'tolerant', 'spelling'];
const encoder = new TextEncoder();
export function key(value, language, profile = 'tolerant') {
  if (!['la', 'grc'].includes(language) || !profiles.includes(profile)) throw new Error('Unsupported lookup profile');
  value=value.replace(/\u00ad/gu,'');
  if (profile === 'exact') return value.normalize('NFC');
  let s = value.normalize('NFD').toLowerCase().replace(/[’ʼ᾽]/gu, "'").replace(/[\u0304\u0306]/gu, '');
  if (language === 'grc') {
    s = s.replace(/ς/gu, 'σ');
    if (profile === 'tolerant' || profile === 'spelling') s = s.replace(/[\u0300\u0301\u0342\u0313\u0314]/gu, '');
  } else if (profile === 'spelling') s = s.replace(/j/gu, 'i').replace(/v/gu, 'u');
  return s.normalize('NFC');
}
export function bucket(value, count = 1024) {
  let hash = 2166136261;
  for (const byte of encoder.encode(value)) hash = Math.imul(hash ^ byte, 16777619) >>> 0;
  return hash % count;
}
export function matches(rows, word, language, profile = 'tolerant') {
  const tiers = profiles.slice(0, profiles.indexOf(profile) + 1);
  const keys = tiers.map(p => key(word, language, p));
  const results = new Map();
  for (const row of rows) {
    const tier = tiers.findIndex((p, i) => key(row[0], language, p) === keys[i]);
    if (tier !== -1 && (!results.has(row[3]) || tier < results.get(row[3]).tier))
      results.set(row[3], {row, tier});
  }
  return [...results.values()].sort((a,b) => a.tier-b.tier || a.row[3]-b.row[3]);
}
export function prepareIndex(rows, language) {
  const groups=new Map();
  for(const row of rows){const k=key(row[0],language,'spelling');if(!groups.has(k))groups.set(k,[]);groups.get(k).push(row);}
  return groups;
}
export function languageOf(word) {
  return /[\p{Script=Greek}\p{Script=Cypriot}\p{Script=Linear_B}]/u.test(word) ? 'grc' : 'la';
}
// Preserve every input character and its UTF-16 offsets. Initial/trailing
// apostrophes belong to elided words; punctuation is otherwise left untouched.
export function tokenize(text) {
  const re = /['’ʼ᾽]*\p{L}[\p{L}\p{M}\u00ad]*(?:(?:\.-|[-.'’ʼ᾽])[\p{L}\p{M}\u00ad]+)*[-.'’ʼ᾽]*/gu;
  const spans = [];
  let end = 0;
  for (const m of text.matchAll(re)) {
    if (m.index > end) spans.push({text:text.slice(end,m.index),start:end,end:m.index,word:false});
    end = m.index + m[0].length;
    spans.push({text:m[0],start:m.index,end,word:true,lang:languageOf(m[0])});
  }
  if (end < text.length) spans.push({text:text.slice(end),start:end,end:text.length,word:false});
  return spans;
}
export function groupReadings(occurrences, entries) {
  const groups = new Map();
  for (const {row, tier} of occurrences) {
    const source = entries.get(row[1]);
    const form = source.forms.find(f => f[0] === row[3]);
    if (!form) throw new Error('Missing indexed form');
    const owners = source.owners.length ? source.owners : [{id:source.id,status:'unresolved',path:[]}];
    for (const owner of owners) {
      if (!groups.has(owner.id)) groups.set(owner.id, {entry:entries.get(owner.id), readings:[], unresolved:['unresolved','unresolved_form'].includes(owner.status)});
      groups.get(owner.id).readings.push({surface:row[0],tier:profiles[tier],form,sourceId:source.id,
        sourceHead:source.headword,sourceSenses:source.senses,table:source.tables[form[4]] ?? null, owner});
    }
  }
  return [...groups.values()];
}
// A literal dictionary spelling has priority, including abbreviations/elisions.
// Only a miss permits terminal punctuation/quotation fallbacks. Hyphens are
// never stripped and no lexical or morphological guessing takes place.
export function queryFallbacks(word) {
  const unquoted=word.replace(/^['’ʼ᾽]+|['’ʼ᾽]+$/gu,'');
  return [...new Set([word.replace(/\.+$/u,''),unquoted,unquoted.replace(/\.+$/u,'')])].filter(s=>s&&s!==word);
}
