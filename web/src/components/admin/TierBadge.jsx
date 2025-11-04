import React from 'react';
import PropTypes from 'prop-types';

/**
 * TierBadge - Styled badge for subscription tiers
 *
 * Colors:
 * - Free: Gray
 * - Plus: Blue
 * - Pro: Purple
 *
 * Inactive tiers shown with opacity and strikethrough
 */
export default function TierBadge({ tier, active = true }) {
  const colors = {
    free: 'bg-gray-200 text-gray-800',
    plus: 'bg-blue-200 text-blue-800',
    pro: 'bg-purple-200 text-purple-800'
  };

  const labels = {
    free: 'Free',
    plus: 'Plus',
    pro: 'Pro'
  };

  return (
    <span
      className={`px-3 py-1 rounded-full text-sm font-semibold ${colors[tier] || 'bg-gray-200 text-gray-800'} ${
        !active ? 'opacity-50 line-through' : ''
      }`}
    >
      {labels[tier] || tier}
    </span>
  );
}

TierBadge.propTypes = {
  tier: PropTypes.oneOf(['free', 'plus', 'pro']).isRequired,
  active: PropTypes.bool
};
