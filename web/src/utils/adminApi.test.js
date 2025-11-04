import { describe, it, expect, vi, beforeEach } from 'vitest';
import { parseJwt, isAdmin, getCurrentUser } from './adminApi';

describe('adminApi utils', () => {
  describe('parseJwt', () => {
    it('should parse valid JWT token', () => {
      // Create a simple JWT-like token (header.payload.signature)
      const payload = { sub: '123', email: 'test@example.com', is_admin: true, exp: 9999999999 };
      const encodedPayload = btoa(JSON.stringify(payload));
      const fakeToken = `header.${encodedPayload}.signature`;

      const result = parseJwt(fakeToken);
      expect(result).toEqual(payload);
    });

    it('should return null for invalid token', () => {
      const result = parseJwt('invalid-token');
      expect(result).toBeNull();
    });

    it('should return null for empty token', () => {
      const result = parseJwt('');
      expect(result).toBeNull();
    });
  });

  describe('isAdmin', () => {
    it('should return true for admin user with valid token', () => {
      const payload = { sub: '123', is_admin: true, exp: 9999999999 };
      const encodedPayload = btoa(JSON.stringify(payload));
      const token = `header.${encodedPayload}.signature`;

      expect(isAdmin(token)).toBe(true);
    });

    it('should return false for non-admin user', () => {
      const payload = { sub: '123', is_admin: false, exp: 9999999999 };
      const encodedPayload = btoa(JSON.stringify(payload));
      const token = `header.${encodedPayload}.signature`;

      expect(isAdmin(token)).toBe(false);
    });

    it('should return false for expired token', () => {
      const payload = { sub: '123', is_admin: true, exp: 1000000000 }; // Past timestamp
      const encodedPayload = btoa(JSON.stringify(payload));
      const token = `header.${encodedPayload}.signature`;

      expect(isAdmin(token)).toBe(false);
    });

    it('should return false for invalid token', () => {
      expect(isAdmin('invalid-token')).toBe(false);
    });

    it('should return false for null token', () => {
      expect(isAdmin(null)).toBe(false);
    });
  });

  describe('getCurrentUser', () => {
    it('should extract user info from valid token', () => {
      const payload = {
        sub: '123',
        email: 'admin@example.com',
        preferred_lang: 'en',
        is_admin: true,
        exp: 9999999999
      };
      const encodedPayload = btoa(JSON.stringify(payload));
      const token = `header.${encodedPayload}.signature`;

      const user = getCurrentUser(token);
      expect(user).toEqual({
        userId: 123,
        email: 'admin@example.com',
        preferredLang: 'en',
        isAdmin: true,
        exp: 9999999999
      });
    });

    it('should return null for invalid token', () => {
      expect(getCurrentUser('invalid-token')).toBeNull();
    });

    it('should return null for null token', () => {
      expect(getCurrentUser(null)).toBeNull();
    });

    it('should handle missing is_admin field', () => {
      const payload = {
        sub: '123',
        email: 'user@example.com',
        preferred_lang: 'en',
        exp: 9999999999
      };
      const encodedPayload = btoa(JSON.stringify(payload));
      const token = `header.${encodedPayload}.signature`;

      const user = getCurrentUser(token);
      expect(user.isAdmin).toBe(false);
    });
  });
});
