import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import MetricCard from '../components/admin/MetricCard';
import TimeSeriesChart from '../components/admin/TimeSeriesChart';
import { getDatePresets, formatCurrency } from '../utils/costAnalytics';
import { getFinancialSummary } from '../utils/adminApi';

/**
 * AdminFinancialPage - US-002: Financial Summary Dashboard
 *
 * Displays:
 * - 4 summary cards: Total Revenue, Total Costs, Gross Profit, Gross Margin %
 * - Time series chart: Revenue vs Cost over selected period
 * - Revenue breakdown by platform: Stripe, Apple IAP, Credit usage
 * - CSV export functionality
 */
export default function AdminFinancialPage({ token, onLogout }) {
  const { t } = useTranslation();
  const presets = getDatePresets();

  // State
  const [startDate, setStartDate] = useState(presets.last30days.start);
  const [endDate, setEndDate] = useState(presets.last30days.end);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [financialData, setFinancialData] = useState(null);

  // Fetch financial data
  useEffect(() => {
    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const data = await getFinancialSummary(token, startDate, endDate, 'day');
        setFinancialData(data);
      } catch (err) {
        console.error('[AdminFinancialPage] Failed to fetch financial data:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    }

    fetchData();
  }, [token, startDate, endDate]);

  // Handle date range change
  const handleDateChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
  };

  // Get margin color code
  const getMarginColor = (margin) => {
    if (margin < 30) return 'red';
    if (margin < 40) return 'yellow';
    return 'green';
  };

  // Export CSV
  const handleExportCSV = () => {
    if (!financialData || !financialData.daily || financialData.daily.length === 0) {
      alert(t('admin.financial.empty') || 'No data to export');
      return;
    }

    // Prepare CSV data
    const csvRows = [
      ['Date', 'Revenue', 'Costs', 'Profit', 'Margin %'],
      ...financialData.daily.map(row => [
        row.date,
        row.revenue.toFixed(2),
        row.cost.toFixed(2),
        (row.revenue - row.cost).toFixed(2),
        row.revenue > 0 ? (((row.revenue - row.cost) / row.revenue) * 100).toFixed(2) : '0.00',
      ])
    ];

    // Convert to CSV string
    const csvContent = csvRows.map(row => row.join(',')).join('\n');

    // Create blob and download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `livetranslator_financial_${startDate.toISOString().split('T')[0]}_to_${endDate.toISOString().split('T')[0]}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  // Calculate summary metrics
  const summary = financialData ? {
    revenue: financialData.total_revenue || 0,
    costs: financialData.total_cost || 0,
    profit: (financialData.total_revenue || 0) - (financialData.total_cost || 0),
    margin: financialData.total_revenue > 0
      ? (((financialData.total_revenue - financialData.total_cost) / financialData.total_revenue) * 100)
      : 0,
  } : { revenue: 0, costs: 0, profit: 0, margin: 0 };

  // Platform breakdown
  const breakdown = financialData ? {
    stripe: financialData.stripe_revenue || 0,
    apple: financialData.apple_revenue || 0,
    credits: financialData.credit_usage || 0,
  } : { stripe: 0, apple: 0, credits: 0 };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold">
            {t('admin.financial.title') || 'Financial Analytics'}
          </h1>
          <button
            onClick={handleExportCSV}
            disabled={loading || !financialData || financialData.daily?.length === 0}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
          >
            {t('admin.financial.exportCSV') || 'Export CSV'}
          </button>
        </div>

        {/* Date Range Picker */}
        <div className="mb-6">
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onChange={handleDateChange}
          />
        </div>

        {/* Error State */}
        {error && !loading && (
          <div className="bg-red-50 border border-red-400 rounded-lg p-4 mb-6">
            <p className="text-red-800">
              {t('admin.financial.error') || 'Failed to load financial data'}: {error}
            </p>
          </div>
        )}

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
          <MetricCard
            title={t('admin.financial.totalRevenue') || 'Total Revenue'}
            value={formatCurrency(summary.revenue)}
            loading={loading}
            error={error && 'Error'}
          />
          <MetricCard
            title={t('admin.financial.totalCosts') || 'Total Costs'}
            value={formatCurrency(summary.costs)}
            loading={loading}
            error={error && 'Error'}
          />
          <MetricCard
            title={t('admin.financial.grossProfit') || 'Gross Profit'}
            value={formatCurrency(summary.profit)}
            loading={loading}
            error={error && 'Error'}
          />
          <MetricCard
            title={t('admin.financial.grossMargin') || 'Gross Margin'}
            value={`${summary.margin.toFixed(1)}%`}
            colorCode={getMarginColor(summary.margin)}
            loading={loading}
            error={error && 'Error'}
          />
        </div>

        {/* Revenue vs Cost Chart */}
        <div className="bg-card border border-border rounded-lg p-6 mb-8">
          <h2 className="text-xl font-semibold mb-4">
            {t('admin.financial.revenueVsCost') || 'Revenue vs Cost Trend'}
          </h2>
          <TimeSeriesChart
            data={financialData?.daily || []}
            loading={loading}
            error={error}
          />
        </div>

        {/* Platform Breakdown */}
        <div>
          <h2 className="text-xl font-semibold mb-4">
            {t('admin.financial.platformBreakdown') || 'Revenue by Platform'}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Stripe Revenue */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-muted uppercase">
                  {t('admin.financial.stripeRevenue') || 'Stripe Revenue'}
                </h3>
                <span className="text-2xl">💳</span>
              </div>
              {loading ? (
                <div className="h-8 bg-bg-secondary rounded animate-pulse"></div>
              ) : (
                <p className="text-2xl font-bold">{formatCurrency(breakdown.stripe)}</p>
              )}
              {!loading && breakdown.stripe > 0 && (
                <p className="text-sm text-muted mt-1">
                  {((breakdown.stripe / summary.revenue) * 100).toFixed(1)}% of total
                </p>
              )}
            </div>

            {/* Apple IAP Revenue */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-muted uppercase">
                  {t('admin.financial.appleRevenue') || 'Apple IAP Revenue'}
                </h3>
                <span className="text-2xl">🍎</span>
              </div>
              {loading ? (
                <div className="h-8 bg-bg-secondary rounded animate-pulse"></div>
              ) : (
                <p className="text-2xl font-bold">{formatCurrency(breakdown.apple)}</p>
              )}
              {!loading && breakdown.apple > 0 && (
                <p className="text-sm text-muted mt-1">
                  {((breakdown.apple / summary.revenue) * 100).toFixed(1)}% of total
                </p>
              )}
            </div>

            {/* Credit Usage */}
            <div className="bg-card border border-border rounded-lg p-6">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-muted uppercase">
                  {t('admin.financial.creditUsage') || 'Credit Usage'}
                </h3>
                <span className="text-2xl">🎟️</span>
              </div>
              {loading ? (
                <div className="h-8 bg-bg-secondary rounded animate-pulse"></div>
              ) : (
                <p className="text-2xl font-bold">{formatCurrency(breakdown.credits)}</p>
              )}
              {!loading && breakdown.credits > 0 && (
                <p className="text-sm text-muted mt-1">
                  {((breakdown.credits / summary.revenue) * 100).toFixed(1)}% of total
                </p>
              )}
            </div>
          </div>
        </div>

        {/* Empty State */}
        {!loading && !error && financialData && financialData.daily?.length === 0 && (
          <div className="bg-card border border-border rounded-lg p-8 text-center mt-8">
            <div className="text-6xl mb-4">📊</div>
            <p className="text-muted">
              {t('admin.financial.empty') || 'No financial transactions in selected period'}
            </p>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}

AdminFinancialPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
