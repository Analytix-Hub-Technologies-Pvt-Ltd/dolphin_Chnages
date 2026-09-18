import { apiRequest } from './client';
import { vi } from 'vitest';

describe('apiRequest', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  it('returns parsed JSON for successful requests', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true }),
    });

    const result = await apiRequest({
      method: 'GET',
      url: '/test',
    });

    expect(result).toEqual({ success: true });
    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringContaining('/test'),
      expect.objectContaining({
        method: 'GET',
        credentials: 'include',
      })
    );
  });

  it('throws a user-friendly error when server responds with an error payload', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      json: async () => ({ message: 'Invalid token' }),
      status: 401,
    });

    await expect(
      apiRequest({ method: 'GET', url: '/secure' })
    ).rejects.toThrow('Invalid token');
  });
});
