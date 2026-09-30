export function settings(action, name, value) {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('formlex-local', 1);
    req.onupgradeneeded = () => req.result.createObjectStore('settings');
    req.onerror = () => reject(req.error);
    req.onsuccess = () => {
      const db = req.result, tx = db.transaction('settings', action==='get'?'readonly':'readwrite');
      const request = action==='get' ? tx.objectStore('settings').get(name) : tx.objectStore('settings').put(value,name);
      tx.oncomplete = () => {db.close();resolve(request.result);};
      tx.onerror = () => {db.close();reject(tx.error);};
    };
  });
}
export async function sha256(buffer) {
  return [...new Uint8Array(await crypto.subtle.digest('SHA-256', buffer))].map(x=>x.toString(16).padStart(2,'0')).join('');
}
export async function verifiedResponse(response, spec) {
  if (!response?.ok) throw failure('FILE_UNAVAILABLE','A dictionary file is unavailable. Connect or save the complete dictionary offline.');
  const bytes = await response.arrayBuffer();
  if (bytes.byteLength !== spec.bytes || await sha256(bytes) !== spec.sha256) throw failure('INTEGRITY_ERROR','File integrity check failed: '+spec.path);
  return new Response(bytes, {headers:response.headers});
}
import {failure} from './contract.mjs';
