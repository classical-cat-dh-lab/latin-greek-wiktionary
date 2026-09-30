export const API_VERSION = 1;
export function failure(code, message) {
  const error = new Error(message); error.code = code; return error;
}
export function validateRequest(data) {
  if (!data || typeof data !== 'object' || !Number.isSafeInteger(data.id))
    throw failure('INVALID_REQUEST', 'A request ID is required.');
  if (data.apiVersion !== undefined && data.apiVersion !== API_VERSION)
    throw failure('UNSUPPORTED_API', 'This reader requires a compatible dictionary API.');
  if (!['init','lookup','entries'].includes(data.action))
    throw failure('INVALID_REQUEST', 'Unknown dictionary action.');
  if (data.action === 'lookup' && (typeof data.word !== 'string' ||
      !['la','grc'].includes(data.lang) || !['exact','reading','tolerant','spelling'].includes(data.profile)))
    throw failure('INVALID_REQUEST', 'Lookup requires a word, language and matching profile.');
  if (data.action === 'entries' && (!Array.isArray(data.ids) ||
      data.ids.some(id => !Number.isSafeInteger(id) || id < 1)))
    throw failure('INVALID_REQUEST', 'Entry IDs must be positive integers.');
  return data;
}
export function validateManifest(manifest) {
  if (manifest?.schema !== 1 || manifest.apiVersion !== API_VERSION || manifest.contract !== 'lexical-entry/1')
    throw failure('UNSUPPORTED_PACKAGE', 'This dictionary package requires a compatible reader. Reload while connected.');
  return manifest;
}
