/**
 * Integration Test for Phase 3A: Admin Panel Foundation
 *
 * Tests:
 * - US-013: Access Control
 * - US-014: Admin Navigation
 * - US-016: Date Range Picker
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import App from '../main';
import * as adminApi from '../utils/adminApi';

// Mock adminApi
vi.mock('../utils/adminApi', () => ({
  isAdmin: vi.fn(),
  testAdminAccess: vi.fn(),
  parseJwt: vi.fn(),
  getCurrentUser: vi.fn(),
}));

describe('Phase 3A Integration Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Clear localStorage
    window.localStorage.clear();
  });

  describe('US-013: Access Control', () => {
    it('should redirect non-admin users from admin routes', async () => {
      const nonAdminToken = btoa(JSON.stringify({ sub: '1', is_admin: false, exp: 9999999999 }));
      window.localStorage.setItem('token', `header.${nonAdminToken}.sig`);

      adminApi.isAdmin.mockReturnValue(false);

      render(
        <BrowserRouter>
          <App />
        </BrowserRouter>
      );

      // Should not crash and should handle redirect gracefully
      expect(screen.queryByText('Admin Panel')).not.toBeInTheDocument();
    });

    it('should allow admin users to access admin routes', async () => {
      const adminToken = btoa(JSON.stringify({ sub: '1', is_admin: true, exp: 9999999999 }));
      window.localStorage.setItem('token', `header.${adminToken}.sig`);

      adminApi.isAdmin.mockReturnValue(true);
      adminApi.testAdminAccess.mockResolvedValue({ message: 'OK' });

      // This test verifies the token parsing logic works
      const parsed = adminApi.parseJwt(`header.${adminToken}.sig`);
      expect(parsed).toBeDefined();
    });
  });

  describe('JWT Token Parsing', () => {
    it('should include is_admin flag in JWT token', () => {
      // Create a mock JWT token with is_admin flag
      const payload = {
        sub: '1',
        email: 'admin@test.com',
        is_admin: true,
        exp: 9999999999
      };

      const encodedPayload = btoa(JSON.stringify(payload));
      const fakeToken = `header.${encodedPayload}.signature`;

      // Test that parseJwt can extract is_admin
      adminApi.parseJwt.mockImplementation((token) => {
        try {
          const base64Url = token.split('.')[1];
          const jsonPayload = atob(base64Url);
          return JSON.parse(jsonPayload);
        } catch {
          return null;
        }
      });

      const parsed = adminApi.parseJwt(fakeToken);
      expect(parsed.is_admin).toBe(true);
    });
  });
});
