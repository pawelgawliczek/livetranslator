/**
 * Payments API Client
 * Provides functions for payment history and transaction operations
 */

const API_BASE = '';

/**
 * Get payment history for current user
 * @param {string} token - JWT auth token
 * @returns {Promise<{payments: Array, total_spent_usd: number}>}
 */
export async function getPaymentHistory(token) {
  const response = await fetch(`${API_BASE}/api/payments/history`, {
    method: 'GET',
    credentials: 'include',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Failed to fetch payment history' }));
    throw new Error(error.detail || 'Failed to fetch payment history');
  }

  return response.json();
}
