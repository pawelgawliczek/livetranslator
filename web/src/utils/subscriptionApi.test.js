import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  createCheckoutSession,
  getSubscription,
  getQuotaStatus,
  getCreditPackages,
} from './subscriptionApi';

// Mock fetch globally
global.fetch = vi.fn();

describe('subscriptionApi', () => {
  const mockToken = 'test-token';

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('createCheckoutSession', () => {
    it('creates checkout session for subscription', async () => {
      const mockResponse = {
        checkout_url: 'https://checkout.stripe.com/session123',
        session_id: 'cs_test_123',
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await createCheckoutSession(mockToken, 'subscription', 2);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/payments/stripe/create-checkout',
        expect.objectContaining({
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${mockToken}`,
          },
          body: JSON.stringify({
            product_type: 'subscription',
            tier_id: 2,
          }),
        })
      );

      expect(result).toEqual(mockResponse);
    });

    it('creates checkout session for credits', async () => {
      const mockResponse = {
        checkout_url: 'https://checkout.stripe.com/session456',
        session_id: 'cs_test_456',
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockResponse,
      });

      const result = await createCheckoutSession(mockToken, 'credits', 3);

      expect(result).toEqual(mockResponse);
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/payments/stripe/create-checkout',
        expect.objectContaining({
          body: JSON.stringify({
            product_type: 'credits',
            tier_id: 3,
          }),
        })
      );
    });

    it('throws error when checkout creation fails', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
        json: async () => ({ detail: 'Invalid tier' }),
      });

      await expect(
        createCheckoutSession(mockToken, 'subscription', 999)
      ).rejects.toThrow('Invalid tier');
    });
  });

  describe('getSubscription', () => {
    it('fetches current subscription', async () => {
      const mockSubscription = {
        tier_id: 2,
        tier_name: 'Plus',
        status: 'active',
        billing_period_end: '2025-12-01',
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockSubscription,
      });

      const result = await getSubscription(mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/subscription',
        expect.objectContaining({
          headers: {
            'Authorization': `Bearer ${mockToken}`,
          },
        })
      );

      expect(result).toEqual(mockSubscription);
    });

    it('throws error when fetch fails', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
      });

      await expect(getSubscription(mockToken)).rejects.toThrow(
        'Failed to fetch subscription'
      );
    });
  });

  describe('getQuotaStatus', () => {
    it('fetches quota status', async () => {
      const mockQuota = {
        quota_used_seconds: 1800,
        quota_available_seconds: 7200,
        bonus_credits_seconds: 3600,
        billing_period_end: '2025-12-01',
      };

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockQuota,
      });

      const result = await getQuotaStatus(mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/quota/status',
        expect.objectContaining({
          headers: {
            'Authorization': `Bearer ${mockToken}`,
          },
        })
      );

      expect(result).toEqual(mockQuota);
    });

    it('throws error when fetch fails', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
      });

      await expect(getQuotaStatus(mockToken)).rejects.toThrow(
        'Failed to fetch quota status'
      );
    });
  });

  describe('getCreditPackages', () => {
    it('fetches credit packages', async () => {
      const mockPackages = [
        { id: 1, credit_hours: 1, price_usd: 5 },
        { id: 2, credit_hours: 4, price_usd: 19 },
      ];

      global.fetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockPackages,
      });

      const result = await getCreditPackages(mockToken);

      expect(global.fetch).toHaveBeenCalledWith(
        '/api/payments/credit-packages',
        expect.objectContaining({
          headers: {
            'Authorization': `Bearer ${mockToken}`,
          },
        })
      );

      expect(result).toEqual(mockPackages);
    });

    it('throws error when fetch fails', async () => {
      global.fetch.mockResolvedValueOnce({
        ok: false,
      });

      await expect(getCreditPackages(mockToken)).rejects.toThrow(
        'Failed to fetch credit packages'
      );
    });
  });
});
