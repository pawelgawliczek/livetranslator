import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import { getDatePresets } from '../utils/costAnalytics';

/**
 * AdminFinancialPage - US-002 & US-003: Financial Analytics
 *
 * Placeholder for Phase 3B implementation.
 * Will display:
 * - Financial summary cards (Revenue, Costs, Profit, Margin)
 * - Time series chart (Revenue vs Cost)
 * - Tier profitability analysis table
 */
export default function AdminFinancialPage({ token, onLogout }) {
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
        <h1 className="text-3xl font-bold mb-6">{t('admin.financial.title') || 'Financial Analytics'}</h1>

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
          <div className="text-6xl mb-4">💰</div>
          <h2 className="text-2xl font-semibold mb-2">Phase 3B: Coming Soon</h2>
          <p className="text-muted mb-4">
            Financial summary dashboard with revenue vs cost breakdown and tier profitability analysis.
          </p>
          <ul className="text-left max-w-md mx-auto space-y-2 text-muted">
            <li>• Revenue breakdown by platform (Stripe, Apple IAP, Credits)</li>
            <li>• Time series chart with revenue vs cost trends</li>
            <li>• Tier profitability table (Free/Plus/Pro)</li>
            <li>• CSV export functionality</li>
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}

AdminFinancialPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
