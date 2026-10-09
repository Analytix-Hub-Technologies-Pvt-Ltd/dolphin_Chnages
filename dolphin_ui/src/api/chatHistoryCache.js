import { apiGet } from './client';

const TTL_MS = 60_000;
const MAX_ENTRIES = 100;
const cached = new Map();
const pending = new Map();
let authScope;
let generation = 0;

export const clearChatHistoryCache = () => {
  generation += 1;
  cached.clear();
  pending.clear();
};

const cachedGet = (path, query = {}) => {
  // Never reuse another login's data, including after a token change.
  const scope = localStorage.getItem('userData');
  if (scope !== authScope) {
    clearChatHistoryCache();
    authScope = scope;
  }
  const key = JSON.stringify([path, Object.entries(query).sort()]);
  const hit = cached.get(key);
  if (hit && hit.expires > Date.now()) {
    cached.delete(key);
    cached.set(key, hit);
    return Promise.resolve(hit.data);
  }
  cached.delete(key);
  if (pending.has(key)) return pending.get(key);
  const requestGeneration = generation;
  const request = apiGet(path, { query }).then((data) => {
    if (generation === requestGeneration) {
      cached.set(key, { data, expires: Date.now() + TTL_MS });
      while (cached.size > MAX_ENTRIES) cached.delete(cached.keys().next().value);
    }
    return data;
  }).finally(() => {
    if (pending.get(key) === request) pending.delete(key);
  });
  pending.set(key, request);
  return request;
};

export const getChatHistory = (query) => cachedGet('/sessions/', query);
export const getChatSession = (row) => cachedGet(
  `/sessions/${encodeURIComponent(row.session_id)}`,
  row.id ? { user_id: row.id } : {}
);
