import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import { getDatePresets } from '../utils/costAnalytics';

/**
 * AdminUsersPage - US-004, US-005, US-006: User Analytics
 *
 * Placeholder for Phase 3B implementation.
 * Will display:
 * - User acquisition metrics (signups, activation rates)
 * - User engagement (DAU/WAU/MAU, stickiness)
 * - Cohort retention analysis
 */
export default function AdminUsersPage({ token, onLogout }) {
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
        <h1 className="text-3xl font-bold mb-6">{t('admin.users.title') || 'User Analytics'}</h1>

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
          <div className="text-6xl mb-4">👥</div>
          <h2 className="text-2xl font-semibold mb-2">Phase 3B: Coming Soon</h2>
          <p className="text-muted mb-4">
            User acquisition, engagement (DAU/WAU/MAU), and cohort retention analytics.
          </p>
          <ul className="text-left max-w-md mx-auto space-y-2 text-muted">
            <li>• New signups and activation rates</li>
            <li>• DAU, WAU, MAU metrics with stickiness ratio</li>
            <li>• Cohort retention (Day 1, 7, 30)</li>
            <li>• Paying vs Free user breakdown</li>
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}

AdminUsersPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
