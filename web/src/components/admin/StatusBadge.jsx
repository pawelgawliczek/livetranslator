import React from 'react';
import PropTypes from 'prop-types';

/**
 * StatusBadge - Subscription status badge with color coding
 *
 * Colors:
 * - Active: Green
 * - Cancelled: Yellow
 * - Expired: Red
 * - Past Due: Orange
 */
export default function StatusBadge({ status }) {
  const colors = {
    active: 'bg-green-200 text-green-800',
    cancelled: 'bg-yellow-200 text-yellow-800',
    expired: 'bg-red-200 text-red-800',
    past_due: 'bg-orange-200 text-orange-800'
  };

  const labels = {
    active: 'Active',
    cancelled: 'Cancelled',
    expired: 'Expired',
    past_due: 'Past Due'
  };

  return (
    <span className={`px-3 py-1 rounded-full text-sm font-semibold ${colors[status] || 'bg-gray-200 text-gray-800'}`}>
      {labels[status] || status}
    </span>
  );
}

StatusBadge.propTypes = {
  status: PropTypes.oneOf(['active', 'cancelled', 'expired', 'past_due']).isRequired
};
