import React from 'react';
import PropTypes from 'prop-types';

/**
 * QuotaProgressBar - Visual quota usage indicator
 *
 * Colors based on usage:
 * - Green: < 70%
 * - Yellow: 70-90%
 * - Red: > 90%
 *
 * Shows "Unlimited" if total is null
 */
export default function QuotaProgressBar({ used, total, unit = 'hours' }) {
  if (total === null || total === undefined) {
    return <span className="text-muted text-sm">Unlimited</span>;
  }

  const usedNum = parseFloat(used) || 0;
  const totalNum = parseFloat(total) || 0;
  const percentage = totalNum > 0 ? Math.min((usedNum / totalNum) * 100, 100) : 0;

  const color = percentage > 90 ? 'bg-red-500' :
                percentage > 70 ? 'bg-yellow-500' :
                'bg-green-500';

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-200 rounded-full h-2 overflow-hidden min-w-[100px]">
        <div
          className={`h-full ${color} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <span className="text-sm whitespace-nowrap text-fg">
        {usedNum.toFixed(2)} / {totalNum.toFixed(2)} {unit} ({percentage.toFixed(1)}%)
      </span>
    </div>
  );
}

QuotaProgressBar.propTypes = {
  used: PropTypes.oneOfType([PropTypes.number, PropTypes.string]).isRequired,
  total: PropTypes.oneOfType([PropTypes.number, PropTypes.string]),
  unit: PropTypes.oneOf(['hours', 'minutes'])
};
