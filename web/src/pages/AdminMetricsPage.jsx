import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import { getDatePresets } from '../utils/costAnalytics';

/**
 * AdminMetricsPage - US-017: Success KPIs Dashboard
 *
 * Placeholder for Phase 3D implementation.
 * Will display:
 * - Key success metrics (Conversion rate, MRR, Churn, ARPU, LTV)
 * - Trend indicators
 * - KPI line charts
 */
export default function AdminMetricsPage({ token, onLogout }) {
  const { t } = useTranslation();
  const presets = getDatePresets();
  const [startDate, setStartDate] = useState(presets.last30days.start);
  const [endDate, setEndDate] = useState(presets.last30days.end);

  const handleDateChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('admin.metrics.title') || 'Success KPIs'}</h1>

        {/* Date Range Picker */}
        <div className="mb-6">
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onChange={handleDateChange}
          />
        </div>

        {/* Placeholder Content */}
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <div className="text-6xl mb-4">📈</div>
          <h2 className="text-2xl font-semibold mb-2">Phase 3D: Coming Soon</h2>
          <p className="text-muted mb-4">
            Success KPIs dashboard with conversion rates, MRR, churn, ARPU, and LTV.
          </p>
          <ul className="text-left max-w-md mx-auto space-y-2 text-muted">
            <li>• Conversion Rate (Free → Paid)</li>
            <li>• Monthly Recurring Revenue (MRR)</li>
            <li>• Churn Rate (% users canceled)</li>
            <li>• Avg Revenue per User (ARPU)</li>
            <li>• Customer Lifetime Value (LTV)</li>
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}

AdminMetricsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
