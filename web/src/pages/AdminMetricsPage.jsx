import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import MetricCard from '../components/admin/MetricCard';
import AcquisitionChart from '../components/admin/AcquisitionChart';
import DailyBreakdownTable from '../components/admin/DailyBreakdownTable';
import { getUserAcquisition } from '../utils/adminApi';
import { getDatePresets } from '../utils/costAnalytics';

/**
 * AdminMetricsPage - US-004: User Acquisition Metrics
 *
 * Displays:
 * - Summary cards (Total Signups, Activation Rate, Fast Activation)
 * - Time series chart (3 lines)
 * - Daily breakdown table
 * - CSV export
 */
export default function AdminMetricsPage({ token, onLogout }) {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  // Date range state (URL-persisted)
  const presets = getDatePresets();
  const [startDate, setStartDate] = useState(() => {
    const urlStart = searchParams.get('start');
    return urlStart ? new Date(urlStart) : presets.last30days.start;
  });
  const [endDate, setEndDate] = useState(() => {
    const urlEnd = searchParams.get('end');
    return urlEnd ? new Date(urlEnd) : presets.last30days.end;
  });

  // Data state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [summary, setSummary] = useState(null);
  const [daily, setDaily] = useState([]);

  // Fetch data
  const fetchData = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getUserAcquisition(token, startDate, endDate);
      setSummary(data.summary);
      setDaily(data.daily);
    } catch (err) {
      console.error('[AdminMetricsPage] Fetch error:', err);
      setError(err.message || 'Failed to load acquisition data');
    } finally {
      setLoading(false);
    }
  };

  // Load data on mount and when date range changes
  useEffect(() => {
    fetchData();
  }, [startDate, endDate]);

  // Update URL when date range changes
  const handleDateChange = (newStart, newEnd) => {
    setStartDate(newStart);
    setEndDate(newEnd);

    // Update URL params
    const params = new URLSearchParams();
    params.set('start', newStart.toISOString().split('T')[0]);
    params.set('end', newEnd.toISOString().split('T')[0]);
    setSearchParams(params);
  };

  // CSV Export
  const handleExportCSV = () => {
    if (!daily || daily.length === 0) {
      alert(t('admin.acquisition.empty') || 'No data to export');
      return;
    }

    // Build CSV
    const headers = [
      t('admin.acquisition.date') || 'Date',
      t('admin.acquisition.newSignups') || 'New Signups',
      t('admin.acquisition.activated') || 'Activated',
      t('admin.acquisition.activationPct') || 'Activation %',
      t('admin.acquisition.fastActivated') || 'Fast Activation',
      t('admin.acquisition.fastActivationPct') || 'Fast Activation %',
    ];

    const rows = daily.map((row) => [
      row.date,
      row.new_signups,
      row.activated,
      row.activation_pct.toFixed(1),
      row.fast_activated,
      row.fast_activation_pct.toFixed(1),
    ]);

    const csvContent = [headers, ...rows].map((row) => row.join(',')).join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `livetranslator_acquisition_${startDate.toISOString().split('T')[0]}_to_${
      endDate.toISOString().split('T')[0]
    }.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // Calculate trend percentages
  const getTrend = (current, previous) => {
    if (!previous || previous === 0) return 0;
    return ((current - previous) / previous) * 100;
  };

  const activationRateTrend = summary
    ? getTrend(summary.activation_rate, summary.previous_period.activation_rate)
    : 0;

  const fastActivationTrend = summary
    ? getTrend(summary.fast_activation_rate, summary.previous_period.fast_activation_rate)
    : 0;

  const signupsTrend = summary
    ? getTrend(summary.total_signups, summary.previous_period.total_signups)
    : 0;

  // Color code for activation rates
  const getActivationColor = (rate) => {
    if (rate >= 40) return 'green';
    if (rate >= 20) return 'yellow';
    return 'red';
  };

  const getFastActivationColor = (rate) => {
    if (rate >= 25) return 'green';
    if (rate >= 10) return 'yellow';
    return 'red';
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-fg">
            {t('admin.acquisition.title') || 'User Acquisition Metrics'}
          </h1>
          <button
            onClick={handleExportCSV}
            disabled={loading || !daily || daily.length === 0}
            className="px-4 py-2 bg-accent text-accent-fg rounded font-medium hover:bg-accent-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {t('admin.acquisition.exportCSV') || 'Export CSV'}
          </button>
        </div>

        {/* Date Range Picker */}
        <DateRangePicker startDate={startDate} endDate={endDate} onChange={handleDateChange} />

        {/* Error Banner */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded flex items-center justify-between">
            <div>
              <p className="font-semibold">
                {t('admin.acquisition.error') || 'Failed to load acquisition data'}
              </p>
              <p className="text-sm">{error}</p>
            </div>
            <button
              onClick={fetchData}
              className="px-3 py-1 bg-red-600 text-white rounded text-sm hover:bg-red-700 transition-colors"
            >
              {t('admin.acquisition.retry') || 'Retry'}
            </button>
          </div>
        )}

        {/* Summary Metric Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <MetricCard
            title={t('admin.acquisition.totalSignups') || 'Total Signups'}
            value={summary ? summary.total_signups : '--'}
            trend={signupsTrend}
            loading={loading}
            error={error ? 'Error' : null}
          />
          <MetricCard
            title={t('admin.acquisition.activationRate') || 'Activation Rate'}
            value={summary ? `${summary.activation_rate.toFixed(1)}%` : '--'}
            trend={activationRateTrend}
            colorCode={summary ? getActivationColor(summary.activation_rate) : null}
            loading={loading}
            error={error ? 'Error' : null}
          />
          <MetricCard
            title={t('admin.acquisition.fastActivation') || 'Fast Activation (<1hr)'}
            value={summary ? `${summary.fast_activation_rate.toFixed(1)}%` : '--'}
            trend={fastActivationTrend}
            colorCode={summary ? getFastActivationColor(summary.fast_activation_rate) : null}
            loading={loading}
            error={error ? 'Error' : null}
          />
        </div>

        {/* Chart */}
        <AcquisitionChart data={daily} loading={loading} error={error} />

        {/* Daily Breakdown Table */}
        <DailyBreakdownTable data={daily} loading={loading} />
      </div>
    </AdminLayout>
  );
}

AdminMetricsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
