import { apiGet } from './client';
import { clearChatHistoryCache, getChatHistory, getChatSession } from './chatHistoryCache';

jest.mock('./client', () => ({ apiGet: jest.fn() }));
const row = { session_id: 'session', id: 'owner' };
beforeEach(() => {
  clearChatHistoryCache();
  localStorage.setItem('userData', 'login-one');
  apiGet.mockResolvedValue({ messages: [] });
});
afterEach(() => jest.restoreAllMocks());

test('shares concurrent requests and reuses completed details', async () => {
  const first = getChatSession(row);
  expect(getChatSession(row)).toBe(first);
  await first;
  await getChatSession(row);
  expect(apiGet).toHaveBeenCalledTimes(1);
});

test('caches each list query and owner separately', async () => {
  await getChatHistory({ limit: 10, offset: 0 });
  await getChatHistory({ offset: 0, limit: 10 });
  await getChatHistory({ limit: 10, offset: 10 });
  await getChatSession(row);
  await getChatSession({ ...row, id: 'other-owner' });
  expect(apiGet).toHaveBeenCalledTimes(4);
});

test('expires entries after one minute', async () => {
  const now = jest.spyOn(Date, 'now').mockReturnValue(1000);
  await getChatSession(row);
  now.mockReturnValue(61001);
  await getChatSession(row);
  expect(apiGet).toHaveBeenCalledTimes(2);
});

test('retries failures and clears cached data on login changes', async () => {
  apiGet.mockRejectedValueOnce(new Error('offline'));
  await expect(getChatSession(row)).rejects.toThrow('offline');
  await getChatSession(row);
  localStorage.setItem('userData', 'login-two');
  await getChatSession(row);
  expect(apiGet).toHaveBeenCalledTimes(3);
});

test('refresh cannot be overwritten by an older in-flight response', async () => {
  let resolveOld;
  apiGet.mockImplementationOnce(() => new Promise((resolve) => { resolveOld = resolve; }));
  const oldRequest = getChatSession(row);
  clearChatHistoryCache();
  apiGet.mockResolvedValueOnce({ messages: ['fresh'] });
  await getChatSession(row);
  resolveOld({ messages: ['old'] });
  await oldRequest;
  expect(await getChatSession(row)).toEqual({ messages: ['fresh'] });
  expect(apiGet).toHaveBeenCalledTimes(2);
});
