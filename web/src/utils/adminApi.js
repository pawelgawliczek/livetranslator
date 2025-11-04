/**
 * Admin Panel API Client
 *
 * Provides functions to interact with admin panel endpoints.
 * Requires admin authentication (is_admin=true).
 */

const API_BASE = '';  // Uses same origin

/**
 * Parse JWT token to extract claims without verification
 * Client-side parsing only - server always validates
 */
export function parseJwt(token) {
  try {
    const base64Url = token.split('.')[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map(c => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    );
    return JSON.parse(jsonPayload);
  } catch (e) {
    console.error('[adminApi] Failed to parse JWT:', e);
    return null;
  }
}

/**
 * Check if user is admin from JWT token
 * Note: This is client-side check only - backend always validates
 */
export function isAdmin(token) {
  if (!token) return false;

  const payload = parseJwt(token);
  if (!payload) return false;

  // Check token expiration
  if (payload.exp && payload.exp * 1000 < Date.now()) {
    return false;
  }

  return payload.is_admin === true;
}

/**
 * Get current user info from JWT token
 */
export function getCurrentUser(token) {
  if (!token) return null;

  const payload = parseJwt(token);
  if (!payload) return null;

  return {
    userId: parseInt(payload.sub),
    email: payload.email,
    preferredLang: payload.preferred_lang,
    isAdmin: payload.is_admin === true,
    exp: payload.exp
  };
}

/**
 * Test admin access
 */
export async function testAdminAccess(token) {
  const response = await fetch(`${API_BASE}/api/admin/test`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    if (response.status === 403) {
      throw new Error('Admin access required');
    }
    throw new Error(`Failed to verify admin access: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get financial summary
 */
export async function getFinancialSummary(token, startDate, endDate, granularity = 'day') {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
    granularity,
  });

  const response = await fetch(`${API_BASE}/api/admin/financial/summary?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch financial summary: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get tier analysis
 */
export async function getTierAnalysis(token, startDate, endDate) {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
  });

  const response = await fetch(`${API_BASE}/api/admin/financial/tier-analysis?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch tier analysis: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user acquisition metrics
 */
export async function getUserAcquisition(token, startDate, endDate, granularity = 'day') {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
    granularity,
  });

  const response = await fetch(`${API_BASE}/api/admin/users/acquisition?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch user acquisition: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user engagement metrics (DAU/WAU/MAU)
 */
export async function getUserEngagement(token, startDate, endDate) {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
  });

  const response = await fetch(`${API_BASE}/api/admin/users/engagement?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch user engagement: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user retention cohorts
 */
export async function getUserRetention(token, startDate, endDate) {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
  });

  const response = await fetch(`${API_BASE}/api/admin/users/retention?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch user retention: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get system performance metrics
 */
export async function getSystemPerformance(token, startDate, endDate) {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
  });

  const response = await fetch(`${API_BASE}/api/admin/system/performance?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch system performance: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get quota utilization
 */
export async function getQuotaUtilization(token, startDate, endDate) {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
  });

  const response = await fetch(`${API_BASE}/api/admin/system/quota-utilization?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch quota utilization: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get active rooms
 */
export async function getActiveRooms(token, options = {}) {
  const {
    limit = 50,
    offset = 0,
    startDate,
    endDate,
  } = options;

  const params = new URLSearchParams({
    limit: limit.toString(),
    offset: offset.toString(),
  });

  if (startDate) {
    params.append('start_date', startDate.toISOString());
  }
  if (endDate) {
    params.append('end_date', endDate.toISOString());
  }

  const response = await fetch(`${API_BASE}/api/admin/rooms/active?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch active rooms: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Grant bonus credits to a user
 */
export async function grantCredits(token, userId, bonusHours, reason) {
  const response = await fetch(`${API_BASE}/api/admin/users/${userId}/grant-credits`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      bonus_hours: bonusHours,
      reason: reason,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to grant credits: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get message debug info
 */
export async function getMessageDebug(token, roomCode, segmentId) {
  const response = await fetch(`${API_BASE}/api/admin/message-debug/${roomCode}/${segmentId}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch message debug: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Search users by email or user ID (US-009)
 */
export async function searchUsers(token, query) {
  const params = new URLSearchParams({ q: query });
  const response = await fetch(`${API_BASE}/api/admin/users/search?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to search users: ${response.statusText}`);
  }

  return response.json();
}

// ============================================================================
// US-003: System Settings Page APIs
// ============================================================================

/**
 * Get all language routing configurations (STT/MT)
 */
export async function getLanguageConfigurations(token) {
  const response = await fetch(`${API_BASE}/api/admin/languages`, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch language configs: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get provider health status
 */
export async function getProviderHealth(token) {
  const response = await fetch(`${API_BASE}/api/admin/providers/health`, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch provider health: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Reset provider health (mark as healthy)
 */
export async function resetProviderHealth(token, provider, serviceType) {
  const response = await fetch(
    `${API_BASE}/api/admin/providers/${provider}/health/reset?service_type=${serviceType}`,
    {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    }
  );

  if (!response.ok) {
    throw new Error(`Failed to reset provider health: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get all feature flags with metadata
 */
export async function getFeatureFlags(token) {
  const response = await fetch(`${API_BASE}/api/admin/settings/feature-flags`, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch feature flags: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update a single feature flag
 */
export async function updateFeatureFlag(token, key, value) {
  const response = await fetch(`${API_BASE}/api/admin/settings/feature-flags/${key}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ value: String(value) })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update feature flag');
  }

  return response.json();
}

/**
 * Get rate limit settings
 */
export async function getRateLimits(token) {
  const response = await fetch(`${API_BASE}/api/admin/settings/rate-limits`, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch rate limits: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update multiple rate limits at once
 */
export async function updateRateLimits(token, limits) {
  const response = await fetch(`${API_BASE}/api/admin/settings/rate-limits`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ limits })
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update rate limits');
  }

  return response.json();
}

/**
 * Get current system usage statistics
 */
export async function getUsageStats(token) {
  const response = await fetch(`${API_BASE}/api/admin/system/usage-stats`, {
    headers: { Authorization: `Bearer ${token}` }
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch usage stats: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Update STT routing configuration
 */
export async function updateSTTRouting(token, id, update) {
  const response = await fetch(`${API_BASE}/api/admin/routing/stt/${id}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(update)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update STT routing');
  }

  return response.json();
}

/**
 * Update MT routing configuration
 */
export async function updateMTRouting(token, id, update) {
  const response = await fetch(`${API_BASE}/api/admin/routing/mt/${id}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(update)
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update MT routing');
  }

  return response.json();
}
