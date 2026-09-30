import {settings,verifiedResponse} from './store.mjs';
import {validateManifest} from './contract.mjs';
const $=id=>document.getElementById(id);
let manifest, cache, controller, running=false;
export async function offlineInit() {
  manifest=validateManifest(await (await fetch('./manifest.json')).json());
  cache=await caches.open('formlex-'+manifest.package);
  $('package-size').textContent=(manifest.bytes/1048576).toFixed(1)+' MiB';
  if(!('serviceWorker' in navigator)) throw new Error('Offline saving requires a browser with service workers.');
  const registration=await navigator.serviceWorker.register('./sw.js');
  let controlled=Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.addEventListener('controllerchange',()=>{
    if(controlled)location.reload();
    controlled=true;
  });
  function offerUpdate(){
    const available=Boolean(registration.active&&registration.waiting);
    $('offline-update').hidden=!available;
    if(!available)return;
    $('offline-update').onclick=()=>{
      if(!running)registration.waiting?.postMessage({action:'ACTIVATE_UPDATE'});
    };
  }
  registration.addEventListener('updatefound',()=>registration.installing?.addEventListener('statechange',offerUpdate));
  offerUpdate();
  if(!registration.active) await new Promise((resolve,reject)=>{
    const installing=registration.installing??registration.waiting;
    if(!installing){reject(new Error('Offline application could not be installed. Reload while connected.'));return;}
    const timer=setTimeout(()=>reject(new Error('Offline application installation timed out. Reload while connected.')),60000);
    function changed(){
      if(installing.state==='activated'){clearTimeout(timer);resolve();}
      if(installing.state==='redundant'){clearTimeout(timer);reject(new Error('Offline application integrity or download failed. Reload while connected.'));}
    }
    installing.addEventListener('statechange',changed);changed();
  });
  const ready=await settings('get','ready-'+manifest.package);
  if(ready && await complete()) {
    $('offline-status').textContent='Ready offline. Saved dictionary files are present.';
    $('offline-save').textContent='Verify offline copy';
  } else if(ready) {
    await settings('put','ready-'+manifest.package,false);
    $('offline').hidden=false;
    $('offline-status').textContent='The saved dictionary is incomplete. Save again while connected to restore missing files.';
  }
  $('offline-save').addEventListener('click',save);
  $('offline-cancel').addEventListener('click',()=>controller?.abort());
  $('offline-save').disabled=false;
}
async function complete() {
  const paths=new Set((await cache.keys()).map(r=>r.url));
  return manifest.files.every(f=>paths.has(new URL(f.path,location.href).href));
}
async function save() {
  if(running) return;
  running=true;const taskController=new AbortController();controller=taskController;
  $('offline').hidden=false;$('offline-save').disabled=true;$('offline-cancel').hidden=false;
  $('offline-progress').value=0;
  let done=0, next=0;
  try {
    await settings('put','ready-'+manifest.package,false);
    const estimate=await navigator.storage?.estimate?.() ?? {};
    const available=(estimate.quota ?? Infinity)-(estimate.usage ?? 0);
    const existing=new Set((await cache.keys()).map(r=>r.url));
    const missing=manifest.files.filter(f=>!existing.has(new URL(f.path,location.href).href)).reduce((n,f)=>n+f.bytes,0);
    if(available<missing*1.1) throw new Error('Not enough available browser storage. Free space and try again.');
    const persistent=await navigator.storage?.persist?.() ?? false;
    const outcomes=await Promise.allSettled(Array.from({length:4},async()=>{
      try {while(next<manifest.files.length) {
        if(taskController.signal.aborted) throw new DOMException('Cancelled','AbortError');
        const file=manifest.files[next++], url=new URL(file.path,location.href);
        const local=await cache.match(url);
        let r=local ?? await caches.match(url);
        if(r) {
          try {r=await verifiedResponse(r,file);if(!local)await cache.put(url,r.clone());} catch {await cache.delete(url);r=null;}
        }
        if(!r) {
          const fetched=await fetch(url,{signal:taskController.signal,cache:'no-store'});
          await cache.put(url,await verifiedResponse(fetched,file));
        }
        if(taskController.signal.aborted) throw new DOMException('Cancelled','AbortError');
        done+=file.bytes;
        $('offline-progress').value=done/manifest.bytes;
        $('offline-status').textContent=`Saving and verifying: ${(done/1048576).toFixed(1)} / ${(manifest.bytes/1048576).toFixed(1)} MiB`;
      }} catch(error){taskController.abort();throw error;}
    }));
    const failures=outcomes.filter(o=>o.status==='rejected').map(o=>o.reason);
    if(failures.length)throw failures.find(e=>e.name!=='AbortError')??failures[0];
    if(taskController.signal.aborted)throw new DOMException('Cancelled','AbortError');
    if(!await complete()) throw new Error('Saved copy is incomplete. Try again to resume.');
    await settings('put','ready-'+manifest.package,true);
    $('offline-status').textContent='Ready offline. '+(persistent?'Persistent storage granted.':'The browser may reclaim storage when space is low.');
    $('offline-save').textContent='Verify offline copy';
  } catch(error) {
    taskController.abort();
    $('offline-status').textContent=error.name==='AbortError'?'Saving cancelled. Verified files are kept; save again to resume.':error.message+' Verified files are kept; save again to resume.';
  } finally {
    running=false;$('offline-save').disabled=false;$('offline-cancel').hidden=true;
  }
}
