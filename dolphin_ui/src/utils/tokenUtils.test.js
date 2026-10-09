import { isTokenExpired } from './tokenUtils';

describe('isTokenExpired', () => {
  it('returns true for null, undefined, and empty string', () => {
    expect(isTokenExpired(null)).toBe(true);
    expect(isTokenExpired(undefined)).toBe(true);
    expect(isTokenExpired('')).toBe(true);
    expect(isTokenExpired('   ')).toBe(true);
  });

  it('returns false for mock or non-JWT tokens', () => {
    expect(isTokenExpired('test-token')).toBe(false);
    expect(isTokenExpired('some_arbitrary_string')).toBe(false);
  });

  it('detects an expired JWT token', () => {
    const expiredPayload = { sub: 'user1', exp: Math.floor(Date.now() / 1000) - 60 };
    const base64Payload = btoa(JSON.stringify(expiredPayload));
    const token = `header.${base64Payload}.signature`;

    expect(isTokenExpired(token)).toBe(true);
  });

  it('detects a valid, unexpired JWT token', () => {
    const validPayload = { sub: 'user1', exp: Math.floor(Date.now() / 1000) + 3600 };
    const base64Payload = btoa(JSON.stringify(validPayload));
    const token = `header.${base64Payload}.signature`;

    expect(isTokenExpired(token)).toBe(false);
  });
});
