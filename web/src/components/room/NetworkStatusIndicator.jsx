import React from 'prop-types';
import PropTypes from 'prop-types';

/**
 * NetworkStatusIndicator - Displays network connection quality
 *
 * Shows a colored dot + RTT value based on connection quality:
 * - Green: high quality (good connection)
 * - Orange: medium quality (acceptable connection)
 * - Red: low quality (poor connection)
 */
export default function NetworkStatusIndicator({ quality = 'unknown', rtt = null }) {
  // Don't render anything if quality is unknown
  if (quality === 'unknown') {
    return null;
  }

  const qualityColors = {
    high: {
      bg: '#10b981',
      shadow: '#10b981'
    },
    medium: {
      bg: '#f59e0b',
      shadow: '#f59e0b'
    },
    low: {
      bg: '#ef4444',
      shadow: '#ef4444'
    }
  };

  const colors = qualityColors[quality] || qualityColors.medium;

  return (
    <div className="flex items-center gap-2 px-2 py-1 rounded-xl bg-white/5 text-xs text-muted-dark">
      <div
        className="w-3 h-3 rounded-full"
        style={{
          backgroundColor: colors.bg,
          boxShadow: `0 0 6px ${colors.shadow}`
        }}
        aria-label={`Network quality: ${quality}`}
      />
      {rtt !== null && (
        <span aria-label={`Round-trip time: ${rtt} milliseconds`}>
          {rtt}ms
        </span>
      )}
    </div>
  );
}

NetworkStatusIndicator.propTypes = {
  quality: PropTypes.oneOf(['high', 'medium', 'low', 'unknown']),
  rtt: PropTypes.number
};
