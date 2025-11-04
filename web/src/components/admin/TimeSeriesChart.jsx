import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import PropTypes from 'prop-types';

/**
 * TimeSeriesChart - Display revenue vs cost trends over time
 *
 * Used in AdminFinancialPage to visualize financial performance.
 * Supports daily, weekly, and monthly aggregations.
 */
export default function TimeSeriesChart({ data, loading, error }) {
  // Error state (prioritize over loading)
  if (error) {
    return (
      <div
        className="h-64 flex items-center justify-center text-red-600"
        data-testid="chart-error"
      >
        <div className="text-center">
          <p className="font-medium">Error loading chart</p>
          <p className="text-sm mt-1">{error}</p>
        </div>
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div
        className="h-64 flex items-center justify-center text-muted"
        data-testid="chart-loading"
      >
        <div className="animate-pulse">Loading chart...</div>
      </div>
    );
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div
        className="h-64 flex items-center justify-center text-muted"
        data-testid="chart-empty"
      >
        <div className="text-center">
          <p className="text-lg mb-2">📊</p>
          <p>No data available for selected period</p>
        </div>
      </div>
    );
  }

  // Format date for display
  const formatDate = (dateStr) => {
    try {
      const date = new Date(dateStr);
      // Short format: MM/DD
      return `${date.getMonth() + 1}/${date.getDate()}`;
    } catch (e) {
      return dateStr;
    }
  };

  // Format currency for tooltip
  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(value);
  };

  // Format currency for axis (shorter format)
  const formatAxisCurrency = (value) => {
    if (value >= 1000) {
      return `$${(value / 1000).toFixed(1)}K`;
    }
    return `$${value.toFixed(0)}`;
  };

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart
        data={data}
        margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
      >
        <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
        <XAxis
          dataKey="date"
          tickFormatter={formatDate}
          stroke="#6b7280"
          style={{ fontSize: '12px' }}
        />
        <YAxis
          tickFormatter={formatAxisCurrency}
          stroke="#6b7280"
          style={{ fontSize: '12px' }}
        />
        <Tooltip
          formatter={(value) => formatCurrency(value)}
          labelFormatter={(date) => {
            try {
              return new Date(date).toLocaleDateString('en-US', {
                month: 'short',
                day: 'numeric',
                year: 'numeric'
              });
            } catch (e) {
              return date;
            }
          }}
          contentStyle={{
            backgroundColor: '#fff',
            border: '1px solid #e5e7eb',
            borderRadius: '6px',
            padding: '8px 12px',
          }}
        />
        <Legend
          wrapperStyle={{ paddingTop: '20px' }}
          iconType="line"
        />
        <Line
          type="monotone"
          dataKey="revenue"
          stroke="#10b981"
          strokeWidth={2}
          name="Revenue"
          dot={{ fill: '#10b981', r: 3 }}
          activeDot={{ r: 5 }}
        />
        <Line
          type="monotone"
          dataKey="cost"
          stroke="#ef4444"
          strokeWidth={2}
          name="Cost"
          dot={{ fill: '#ef4444', r: 3 }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

TimeSeriesChart.propTypes = {
  data: PropTypes.arrayOf(PropTypes.shape({
    date: PropTypes.string.isRequired,
    revenue: PropTypes.number.isRequired,
    cost: PropTypes.number.isRequired,
  })),
  loading: PropTypes.bool,
  error: PropTypes.string,
};
