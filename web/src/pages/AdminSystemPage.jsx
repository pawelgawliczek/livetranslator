import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import { getDatePresets } from '../utils/costAnalytics';

/**
 * AdminSystemPage - US-007, US-008, US-018: System Monitoring
 *
 * Placeholder for Phase 3C implementation.
 * Will display:
 * - System performance metrics (provider costs, request counts)
 * - Quota utilization by tier
 * - Provider health status
 */
export default function AdminSystemPage({ token, onLogout }) {
  const { t } = useTranslation();
  const presets = getDatePresets();
  const [startDate, setStartDate] = useState(presets.today.start);
  const [endDate, setEndDate] = useState(presets.today.end);

  const handleDateChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('admin.system.title') || 'System Monitoring'}</h1>

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
          <div className="text-6xl mb-4">⚙️</div>
          <h2 className="text-2xl font-semibold mb-2">Phase 3C: Coming Soon</h2>
          <p className="text-muted mb-4">
            System performance metrics, quota utilization, and provider health monitoring.
          </p>
          <ul className="text-left max-w-md mx-auto space-y-2 text-muted">
            <li>• Provider performance (STT, MT costs and request counts)</li>
            <li>• Quota utilization by tier (Free/Plus/Pro)</li>
            <li>• Provider health status with alerts</li>
            <li>• Reset provider health action</li>
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}

AdminSystemPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
