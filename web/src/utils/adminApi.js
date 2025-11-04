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
