/**
 * Cost Analytics API Client
 *
 * Provides functions to interact with the admin cost analytics API endpoints.
 */

const API_BASE = '';  // Uses same origin

/**
 * Get cost overview for a date range
 */
export async function getCostOverview(token, startDate, endDate, granularity = null, roomId = null, userId = null) {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
  });

  if (granularity) {
    params.append('granularity', granularity);
  }

  if (roomId) {
    params.append('room_id', roomId);
  }

  if (userId) {
    params.append('user_id', userId);
  }

  const response = await fetch(`${API_BASE}/api/admin/costs/overview?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch cost overview: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get time-series cost data
 */
export async function getCostTimeseries(token, options) {
  const {
    startDate,
    endDate,
    granularity,
    accumulated = false,
    byProvider = false,
    userId = null,
    roomId = null,
  } = options;

  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
    granularity,
    accumulated: accumulated.toString(),
    by_provider: byProvider.toString(),
  });

  if (userId) {
    params.append('user_id', userId);
  }

  if (roomId) {
    params.append('room_id', roomId);
  }

  const response = await fetch(`${API_BASE}/api/admin/costs/timeseries?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch cost timeseries: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get user costs with pagination
 */
export async function getUserCosts(token, options) {
  const {
    startDate,
    endDate,
    limit = 50,
    offset = 0,
    sortBy = 'total_cost',
    sortOrder = 'desc',
    search = null,
  } = options;

  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
    limit: limit.toString(),
    offset: offset.toString(),
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  if (search) {
    params.append('search', search);
  }

  const response = await fetch(`${API_BASE}/api/admin/costs/users?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch user costs: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get detailed cost information for a specific user
 */
export async function getUserDetail(token, userId, startDate, endDate) {
  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
  });

  const response = await fetch(`${API_BASE}/api/admin/costs/users/${userId}?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch user detail: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Get room costs with pagination
 */
export async function getRoomCosts(token, options) {
  const {
    startDate,
    endDate,
    userId = null,
    limit = 50,
    offset = 0,
    sortBy = 'total_cost',
    sortOrder = 'desc',
    search = null,
  } = options;

  const params = new URLSearchParams({
    start_date: startDate.toISOString(),
    end_date: endDate.toISOString(),
    limit: limit.toString(),
    offset: offset.toString(),
    sort_by: sortBy,
    sort_order: sortOrder,
  });

  if (userId) {
    params.append('user_id', userId);
  }

  if (search) {
    params.append('search', search);
  }

  const response = await fetch(`${API_BASE}/api/admin/costs/rooms?${params}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch room costs: ${response.statusText}`);
  }

  return response.json();
}

/**
 * Auto-detect appropriate granularity based on date range
 */
export function autoDetectGranularity(startDate, endDate) {
  const diffMs = endDate - startDate;
  const hours = diffMs / (1000 * 60 * 60);
  const days = hours / 24;

  if (hours <= 48) return 'hour';
  if (days <= 60) return 'day';
  if (days <= 365) return 'week';
  if (days <= 730) return 'month';
  return 'year';
}

/**
 * Get available granularities for a date range
 */
export function getAvailableGranularities(startDate, endDate) {
  const diffMs = endDate - startDate;
  const days = diffMs / (1000 * 60 * 60 * 24);

  const options = [];

  if (days <= 7) options.push('hour');
  options.push('day');
  if (days >= 7) options.push('week');
  if (days >= 30) options.push('month');
  if (days >= 365) options.push('year');

  return options;
}

/**
 * Format currency amount
 */
export function formatCurrency(amount, decimals = 2) {
  return `$${amount.toFixed(decimals)}`;
}

/**
 * Format large numbers with K/M suffixes
 */
export function formatNumber(num) {
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toFixed(0);
}

/**
 * Export data to CSV
 */
export function exportToCSV(data, filename) {
  if (!data || data.length === 0) return;

  // Get headers from first object
  const headers = Object.keys(data[0]);

  // Build CSV content
  const csvContent = [
    headers.join(','),
    ...data.map(row =>
      headers.map(header => {
        const value = row[header];
        // Escape values containing commas or quotes
        if (typeof value === 'string' && (value.includes(',') || value.includes('"'))) {
          return `"${value.replace(/"/g, '""')}"`;
        }
        return value;
      }).join(',')
    ),
  ].join('\n');

  // Create download link
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);

  link.setAttribute('href', url);
  link.setAttribute('download', filename);
  link.style.visibility = 'hidden';

  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

/**
 * Get date presets for quick selection
 */
export function getDatePresets() {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());

  return {
    today: {
      label: 'Today',
      start: today,
      end: now,
    },
    yesterday: {
      label: 'Yesterday',
      start: new Date(today.getTime() - 24 * 60 * 60 * 1000),
      end: today,
    },
    last7days: {
      label: 'Last 7 days',
      start: new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000),
      end: now,
    },
    last30days: {
      label: 'Last 30 days',
      start: new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000),
      end: now,
    },
    thisMonth: {
      label: 'This month',
      start: new Date(now.getFullYear(), now.getMonth(), 1),
      end: now,
    },
    lastMonth: {
      label: 'Last month',
      start: new Date(now.getFullYear(), now.getMonth() - 1, 1),
      end: new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59),
    },
  };
}

/**
 * Provider color scheme for charts
 */
export const PROVIDER_COLORS = {
  // STT Providers
  openai: '#10b981',      // Green
  soniox: '#f59e0b',      // Amber
  google_v2: '#ef4444',   // Red
  azure: '#3b82f6',       // Blue
  speechmatics: '#8b5cf6', // Purple

  // MT Providers
  deepl: '#06b6d4',       // Cyan
  azure_translator: '#3b82f6', // Blue
  // openai MT uses same as STT
};

/**
 * Aggregate colors for charts
 */
export const AGGREGATE_COLORS = {
  total: '#8b5cf6',  // Purple
  stt: '#3b82f6',    // Blue
  mt: '#10b981',     // Green
};
