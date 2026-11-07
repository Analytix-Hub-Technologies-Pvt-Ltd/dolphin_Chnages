import { apiGet, apiPut, sessionFetch } from './client';
import { APP_URL } from './config';
import { loginApi, logout } from './apiAuth';
import { createSession, getSavedSessions, saveSession, deleteSession, submitMessageFeedback, fetchTopicDetails } from './fetchApi';
jest.mock('axios', () => ({ post: jest.fn(), get: jest.fn() }));
const axios = require('axios');
const loginData = { user_id: 'owner', access_token: 'test-token', token_type: 'bearer' };
beforeEach(() => {
  localStorage.clear();
  jest.clearAllMocks();
  localStorage.setItem('userData', JSON.stringify(loginData));
  localStorage.setItem('user_id', 'owner');
  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ success: true }) });
});
const expectBearer = () => {
  expect(fetch.mock.calls[0][1].headers.get('Authorization')).toBe('Bearer test-token');
};
test('login persists the access token using existing storage and logout removes it', async () => {
  axios.post.mockResolvedValue({ data: loginData });
  await loginApi('test@example.com', 'password');
  expect(JSON.parse(localStorage.getItem('userData')).access_token).toBe('test-token');
  await logout();
  expect(localStorage.getItem('userData')).toBeNull();
});
test.each(['/sessions', '/sessions/', '/sessions/session-id'])('shared client authenticates %s without changing query parameters', async path => {
  await apiGet(path, { query: { user_id: 'owner' } });
  expect(fetch.mock.calls[0][0]).toBe(`${APP_URL}${path}?user_id=owner`);
  expectBearer();
});
test.each([
  ['saved', () => getSavedSessions(), '/sessions/saved/owner', 'GET'],
  ['create', () => createSession(), '/sessions', 'POST'],
  ['save', () => saveSession('s1'), '/sessions/save/s1', 'POST'],
  ['delete', () => deleteSession('s1'), '/sessions/s1', 'DELETE'],
  ['feedback', () => submitMessageFeedback({ message_id: 'm1' }), '/sessions/message-feedback', 'POST'],
  ['topic', () => fetchTopicDetails('t1'), '/sessions/topic/t1', 'GET'],
])('%s session API sends the token', async (_, request, path, method) => {
  await request();
  expect(fetch.mock.calls[0][0]).toBe(`${APP_URL}${path}`);
  expect(fetch.mock.calls[0][1].method).toBe(method);
  expectBearer();
});
test('does not forward tokens to third-party URLs or unrelated endpoints', async () => {
  await sessionFetch('https://example.org/sessions', { headers: { Authorization: 'Bearer secret' } });
  await apiGet('/api/v1/health');
  for (const [, config] of fetch.mock.calls) expect(config.headers.has('Authorization')).toBe(false);
});
test.each([null, '{}', 'invalid json'])('missing or malformed stored authentication does not fabricate a token: %s', async stored => {
  if (stored === null) localStorage.removeItem('userData');
  else localStorage.setItem('userData', stored);
  await apiGet('/sessions');
  expect(fetch.mock.calls[0][1].headers.has('Authorization')).toBe(false);
});
test.each([401, 403])('HTTP %s keeps existing error handling', async status => {
  fetch.mockResolvedValue({ ok: false, status, json: async () => ({ detail: 'Request denied' }) });
  await expect(apiGet('/sessions')).rejects.toThrow('Request denied');
});
test('reads the current token for every request and prevents authenticated redirects', async () => {
  await apiGet('/sessions');
  localStorage.setItem('userData', JSON.stringify({ access_token: 'new-token' }));
  await apiGet('/sessions');
  expect(fetch.mock.calls[1][1].headers.get('Authorization')).toBe('Bearer new-token');
  expect(fetch.mock.calls[1][1].redirect).toBe('error');
});

test('members list and role update receive bearer tokens', async () => {
  await apiGet('/users', { query: { admin_user_id: 'owner', limit: 100, offset: 0 } });
  await apiPut('/users/member/role?admin_user_id=owner', { role_id: 2 });
  for (const [, config] of fetch.mock.calls) {
    expect(config.headers.get('Authorization')).toBe('Bearer test-token');
    expect(config.redirect).toBe('error');
  }
  expect(fetch.mock.calls[1][1].body).toBe(JSON.stringify({ role_id: 2 }));
});
test('members authentication is restricted to the API origin and resource path', async () => {
  await sessionFetch('https://example.org/users', { headers: { Authorization: 'Bearer secret' } });
  await apiGet('/users-public');
  for (const [, config] of fetch.mock.calls) expect(config.headers.has('Authorization')).toBe(false);
});
