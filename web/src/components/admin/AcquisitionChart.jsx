import PropTypes from 'prop-types';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useTranslation } from 'react-i18next';

/**
 * AcquisitionChart - US-004: Time series chart for user acquisition
 *
 * Displays 3 lines:
 * - New Signups (blue)
 * - Activated Users (green)
 * - Fast Activation <1hr (purple)
 */
export default function AcquisitionChart({ data, loading, error }) {
  const { t } = useTranslation();

  // Loading state
  if (loading) {
    return (
      <div className="bg-card rounded-lg border border-border p-8 flex items-center justify-center h-96">
        <div className="text-muted">
          <div className="animate-spin h-8 w-8 border-4 border-accent border-t-transparent rounded-full mx-auto mb-2"></div>
          <p>{t('common.loading') || 'Loading chart...'}</p>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="bg-card rounded-lg border border-red-400 p-8 text-center h-96 flex flex-col items-center justify-center">
        <div className="text-red-600 mb-4">
          <p className="font-semibold">{t('admin.acquisition.chartError') || 'Error loading chart'}</p>
          <p className="text-sm mt-2">{error}</p>
        </div>
      </div>
    );
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border p-8 text-center h-96 flex flex-col items-center justify-center">
        <div className="text-muted">
          <p className="text-xl mb-2">📊</p>
          <p>{t('admin.acquisition.noData') || 'No data available for selected period'}</p>
        </div>
      </div>
    );
  }

  // Custom tooltip
  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length > 0) {
      const dataPoint = payload[0].payload;
      return (
        <div className="bg-card border border-border rounded-lg p-3 shadow-lg">
          <p className="text-fg font-semibold mb-2">{dataPoint.date}</p>
          <div className="space-y-1 text-sm">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-blue-500"></div>
              <span className="text-muted">
                {t('admin.acquisition.newSignups') || 'New Signups'}:
              </span>
              <span className="font-semibold text-fg ml-auto">{dataPoint.new_signups}</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-500"></div>
              <span className="text-muted">
                {t('admin.acquisition.activated') || 'Activated'}:
              </span>
              <span className="font-semibold text-fg ml-auto">
                {dataPoint.activated} ({dataPoint.activation_pct}%)
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-purple-500"></div>
              <span className="text-muted">
                {t('admin.acquisition.fastActivated') || 'Fast Activation'}:
              </span>
              <span className="font-semibold text-fg ml-auto">
                {dataPoint.fast_activated} ({dataPoint.fast_activation_pct}%)
              </span>
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  CustomTooltip.propTypes = {
    active: PropTypes.bool,
    payload: PropTypes.array,
  };

  return (
    <div className="bg-card rounded-lg border border-border p-6">
      <h3 className="text-lg font-semibold text-fg mb-4">
        {t('admin.acquisition.trend') || 'User Acquisition Trend'}
      </h3>

      <ResponsiveContainer width="100%" height={400}>
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#333" />
          <XAxis
            dataKey="date"
            stroke="#666"
            tick={{ fill: '#999' }}
            tickFormatter={(value) => {
              // Format date as "MMM dd"
              const date = new Date(value);
              return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
            }}
          />
          <YAxis stroke="#666" tick={{ fill: '#999' }} />
          <Tooltip content={<CustomTooltip />} />
          <Legend
            wrapperStyle={{ paddingTop: '20px' }}
            iconType="line"
            formatter={(value) => {
              const labels = {
                new_signups: t('admin.acquisition.newSignups') || 'New Signups',
                activated: t('admin.acquisition.activated') || 'Activated',
                fast_activated: t('admin.acquisition.fastActivated') || 'Fast Activation (<1hr)',
              };
              return labels[value] || value;
            }}
          />
          <Line
            type="monotone"
            dataKey="new_signups"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
            name="new_signups"
          />
          <Line
            type="monotone"
            dataKey="activated"
            stroke="#10b981"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
            name="activated"
          />
          <Line
            type="monotone"
            dataKey="fast_activated"
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 5 }}
            name="fast_activated"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

AcquisitionChart.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string.isRequired,
      new_signups: PropTypes.number.isRequired,
      activated: PropTypes.number.isRequired,
      activation_pct: PropTypes.number.isRequired,
      fast_activated: PropTypes.number.isRequired,
      fast_activation_pct: PropTypes.number.isRequired,
    })
  ),
  loading: PropTypes.bool,
  error: PropTypes.string,
};
