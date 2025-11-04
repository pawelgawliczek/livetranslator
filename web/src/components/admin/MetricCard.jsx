import PropTypes from 'prop-types';

/**
 * MetricCard - Display a single metric with optional trend and color coding
 *
 * Used in AdminOverviewPage to show KPI cards (revenue, costs, margin, etc.)
 */
export default function MetricCard({
  title,
  value,
  trend,
  trendLabel,
  colorCode,
  loading = false,
  error = null,
}) {
  // Loading state
  if (loading) {
    return (
      <div
        className="bg-card rounded-lg border border-border p-4"
        data-testid="metric-card-loading"
      >
        <div className="h-4 bg-bg-secondary rounded w-3/4 mb-3 animate-pulse"></div>
        <div className="h-8 bg-bg-secondary rounded w-1/2 mb-2 animate-pulse"></div>
        <div className="h-3 bg-bg-secondary rounded w-1/3 animate-pulse"></div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-card rounded-lg border border-red-400 p-4">
        <div className="text-xs text-muted mb-2">{title}</div>
        <div className="text-sm text-red-600">{error}</div>
      </div>
    );
  }

  // Determine trend color and symbol
  let trendColor = '';
  let trendSymbol = '';
  if (trend !== undefined && trend !== null) {
    if (trend > 0) {
      trendColor = 'text-green-600';
      trendSymbol = '↑';
    } else if (trend < 0) {
      trendColor = 'text-red-600';
      trendSymbol = '↓';
    } else {
      trendColor = 'text-muted';
      trendSymbol = '→';
    }
  }

  // Determine value color based on colorCode prop
  let valueColor = 'text-fg';
  if (colorCode === 'red') {
    valueColor = 'text-red-600';
  } else if (colorCode === 'yellow') {
    valueColor = 'text-yellow-600';
  } else if (colorCode === 'green') {
    valueColor = 'text-green-600';
  }

  return (
    <div className="bg-card rounded-lg border border-border p-4 hover:shadow-md transition-shadow">
      {/* Title */}
      <div className="text-xs text-muted mb-2 font-medium uppercase tracking-wide">
        {title}
      </div>

      {/* Value */}
      <div className={`text-2xl font-bold ${valueColor} mb-1`}>
        {value}
      </div>

      {/* Trend */}
      {trend !== undefined && trend !== null && (
        <div className={`text-xs ${trendColor} flex items-center gap-1`}>
          <span>{trendSymbol}</span>
          <span>{Math.abs(trend).toFixed(1)}%</span>
          {trendLabel && <span className="text-muted ml-1">{trendLabel}</span>}
        </div>
      )}
    </div>
  );
}

MetricCard.propTypes = {
  title: PropTypes.string.isRequired,
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
  trend: PropTypes.number, // percentage change, can be negative
  trendLabel: PropTypes.string,
  colorCode: PropTypes.oneOf(['red', 'yellow', 'green']), // for margin color coding
  loading: PropTypes.bool,
  error: PropTypes.string,
};
