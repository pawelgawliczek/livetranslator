import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import { getDatePresets } from '../utils/costAnalytics';

/**
 * AdminOverviewPage - US-001: View Admin Dashboard Overview
 *
 * Placeholder for Phase 3B implementation.
 * Will display:
 * - 8 metric cards (Revenue, Costs, Profit, Margin, DAU, Rooms, Avg Cost, Provider Health)
 * - Trend indicators
 * - Quick links to detailed pages
 */
export default function AdminOverviewPage({ token, onLogout }) {
  const { t } = useTranslation();
  const presets = getDatePresets();
  const [startDate, setStartDate] = useState(presets.last7days.start);
  const [endDate, setEndDate] = useState(presets.last7days.end);
  const [loading, setLoading] = useState(false);

  const handleDateChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('admin.overview.title') || 'Dashboard Overview'}</h1>

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
          <div className="text-6xl mb-4">🚧</div>
          <h2 className="text-2xl font-semibold mb-2">Phase 3B: Coming Soon</h2>
          <p className="text-muted mb-4">
            This page will display 8 key metric cards with trends, quick links, and real-time data.
          </p>
          <div className="grid grid-cols-4 gap-4 mt-8">
            {[
              'Total Revenue (MTD)',
              'Total Costs (MTD)',
              'Gross Profit (MTD)',
              'Gross Margin %',
              'Active Users (DAU)',
              'Total Rooms (MTD)',
              'Avg Cost per User',
              'Provider Health',
            ].map((metric, index) => (
              <div key={index} className="bg-bg-secondary p-4 rounded border border-border">
                <div className="text-xs text-muted mb-2">{metric}</div>
                <div className="text-2xl font-bold text-fg">--</div>
                <div className="text-xs text-muted mt-1">↑ --%</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </AdminLayout>
  );
}

AdminOverviewPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
