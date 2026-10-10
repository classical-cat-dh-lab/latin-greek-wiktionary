const EDITION = '__EDITION__';
const BUILD = '__BUILD__';
const BOOT = 'formlex-bootstrap-'+BUILD+'-'+encodeURIComponent(new URL(self.registration.scope).pathname);
async function digest(bytes) {return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(x=>x.toString(16).padStart(2,'0')).join('');}
async function loadManifest() {
  const cache=await caches.open(BOOT),url=new URL('manifest.json',self.registration.scope);
  let response=await cache.match(url);
  if(!response){
    response=await fetch(url,{cache:'no-store'});
    const manifest=await response.clone().json();
    if(!response.ok||manifest.edition!==EDITION||manifest.shellBuild!==BUILD)throw new Error('Dictionary update required');
    await cache.put(url,response.clone());
  }
  return response.json();
}
self.addEventListener('install', event => event.waitUntil((async()=>{
  const response=await fetch(new URL('manifest.json',self.registration.scope),{cache:'no-store'});
  if(!response.ok) throw new Error('Manifest unavailable');
  const manifest=await response.clone().json();
  if(manifest.edition!==EDITION || manifest.shellBuild!==BUILD) throw new Error('Edition mismatch');
  const cache=await caches.open('formlex-'+manifest.package);
  for(const file of manifest.files.filter(f=>!f.path.startsWith('data/'))) {
    const url=new URL(file.path,self.registration.scope), r=await fetch(url,{cache:'no-store'}), bytes=await r.arrayBuffer();
    if(!r.ok || bytes.byteLength!==file.bytes || await digest(bytes)!==file.sha256) throw new Error('Shell integrity failure');
    await cache.put(url,new Response(bytes,{headers:r.headers}));
  }
  await (await caches.open(BOOT)).put(new URL('manifest.json',self.registration.scope),response);
})()));
self.addEventListener('message',event=>{
  if(event.data?.action==='ACTIVATE_UPDATE')event.waitUntil(self.skipWaiting());
});
self.addEventListener('activate', event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch', event=>{
  if(event.request.method!=='GET' || !event.request.url.startsWith(self.registration.scope)) return;
  event.respondWith((async()=>{
    const url=new URL(event.request.url);
    // Data readers already checked CacheStorage. Recovery must reach the network
    // even when deleting a damaged cached file failed. Keep shell updates pinned.
    if(event.request.cache==='no-store' && url.href.startsWith(new URL('data/',self.registration.scope).href))
      return fetch(event.request);
    let manifest;
    try{manifest=await loadManifest();}catch{return fetch(event.request);}
    if(url.href===new URL('manifest.json',self.registration.scope).href)
      return (await caches.open(BOOT)).match(url);
    if(event.request.mode==='navigate' && url.pathname===new URL(self.registration.scope).pathname) url.pathname+='index.html';
    try {
      const hit=await (await caches.open('formlex-'+manifest.package)).match(url);
      if(hit) return hit;
    } catch { /* Storage failure must not prevent an available online response. */ }
    return fetch(event.request);
  })());
});
