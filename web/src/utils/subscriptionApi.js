/**
 * Subscription API Client
 * Provides functions for subscription, quota, and payment operations
 */

const API_BASE = '';

/**
 * Create a Stripe checkout session
 * @param {string} token - JWT auth token
 * @param {string} productType - 'subscription' or 'credits'
 * @param {number} tierId - Tier ID for subscription or package ID for credits
 * @returns {Promise<{checkout_url: string, session_id: string}>}
 */
export async function createCheckoutSession(token, productType, itemId) {
  const response = await fetch(`${API_BASE}/api/payments/stripe/create-checkout`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      'X-Requested-With': 'XMLHttpRequest', // CSRF protection
    },
    body: JSON.stringify({
      product_type: productType,
      tier_id: productType === 'subscription' ? itemId : null,
      package_id: productType === 'credits' ? itemId : null,
    }),
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create checkout' }));
    throw new Error(error.detail || 'Failed to create checkout');
  }

  return response.json();
}

/**
 * Create Stripe Customer Portal session
 * @param {string} token - JWT auth token
 * @returns {Promise<{portal_url: string}>}
 */
export async function createPortalSession(token) {
  const response = await fetch(`${API_BASE}/api/payments/stripe/create-portal-session`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'X-Requested-With': 'XMLHttpRequest', // CSRF protection
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to create portal session' }));
    throw new Error(error.detail || 'Failed to create portal session');
  }

  return response.json();
}

/**
 * Get current user subscription
 * @param {string} token - JWT auth token
 * @returns {Promise<Object>} Subscription details
 */
export async function getSubscription(token) {
  const response = await fetch(`${API_BASE}/api/subscription`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to fetch subscription');
  }

  return response.json();
}

/**
 * Get current quota status
 * @param {string} token - JWT auth token
 * @returns {Promise<Object>} Quota status with used/total/bonus
 */
export async function getQuotaStatus(token) {
  const response = await fetch(`${API_BASE}/api/quota/status`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to fetch quota status');
  }

  return response.json();
}

/**
 * Get available credit packages
 * @param {string} token - JWT auth token
 * @returns {Promise<Array>} List of credit packages
 */
export async function getCreditPackages(token) {
  const response = await fetch(`${API_BASE}/api/payments/credit-packages`, {
    headers: {
      'Authorization': `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error('Failed to fetch credit packages');
  }

  return response.json();
}
