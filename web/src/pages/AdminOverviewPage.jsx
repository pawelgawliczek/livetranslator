import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import MetricCard from '../components/admin/MetricCard';
import { getDatePresets } from '../utils/costAnalytics';
import {
  getUserEngagement,
  getSystemPerformance,
} from '../utils/adminApi';

/**
 * AdminOverviewPage - Admin Dashboard Overview
 *
 * Displays key metric cards:
 * - Total Costs (MTD)
 * - Active Users (DAU)
 * - Total Rooms Created (MTD)
 * - Avg Cost per User
 * - Provider Health Status
 *
 * Features:
 * - Auto-refresh every 60 seconds
 * - Date range selector
 * - Quick links to detailed pages
 * - Loading/error/empty states
 */
export default function AdminOverviewPage({ token, onLogout }) {
  const { t } = useTranslation();
  const presets = getDatePresets();
  const [startDate, setStartDate] = useState(presets.last7days.start);
  const [endDate, setEndDate] = useState(presets.last7days.end);
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleDateChange = (start, end) => {
    setStartDate(start);
    setEndDate(end);
  };

  // Fetch metrics from backend
  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch from multiple endpoints in parallel
      const [engagement, performance] = await Promise.all([
        getUserEngagement(token, startDate, endDate),
        getSystemPerformance(token, startDate, endDate),
      ]);

      // Calculate DAU from engagement metrics
      const dau = engagement.metrics && engagement.metrics.length > 0
        ? engagement.metrics[0].dau || 0
        : 0;

      // Calculate rooms created (TODO: need dedicated API endpoint)
      const roomsCreated = 0;

      // Aggregate provider health
      const providerHealth = aggregateProviderHealth(performance.providers || []);

      setMetrics({
        dau,
        roomsCreated,
        providerHealth,
      });
    } catch (err) {
      console.error('[AdminOverviewPage] Failed to fetch metrics:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Aggregate provider health from performance data
  const aggregateProviderHealth = (providers) => {
    if (!providers || providers.length === 0) {
      return 'Unknown';
    }

    const allHealthy = providers.every(p => p.request_count > 0);
    return allHealthy ? 'Healthy' : 'Degraded';
  };

  // Fetch metrics on mount and when date range changes
  useEffect(() => {
    if (token && startDate && endDate) {
      fetchMetrics();
    }
  }, [token, startDate, endDate]);

  // Auto-refresh every 60 seconds
  useEffect(() => {
    if (!token) return;

    const interval = setInterval(() => {
      fetchMetrics();
    }, 60000);

    return () => clearInterval(interval);
  }, [token, startDate, endDate]);

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-3xl font-bold mb-6">{t('admin.overview.title')}</h1>

        {/* Date Range Picker */}
        <div className="mb-6">
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onChange={handleDateChange}
          />
        </div>

        {/* Error Banner */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
            <strong>{t('admin.overview.error')}: </strong>
            {error}
          </div>
        )}

        {/* Metric Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          {/* Active Users (DAU) */}
          <MetricCard
            title={t('admin.overview.activeUsers')}
            value={metrics ? metrics.dau : '--'}
            loading={loading}
          />

          {/* Rooms Created */}
          <MetricCard
            title={t('admin.overview.roomsCreated')}
            value={metrics ? metrics.roomsCreated : '--'}
            loading={loading}
          />

          {/* Provider Health */}
          <MetricCard
            title={t('admin.overview.providerHealth')}
            value={metrics ? metrics.providerHealth : '--'}
            loading={loading}
          />
        </div>

        {/* Quick Links */}
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">{t('admin.overview.quickLinks')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Link
              to="/admin/cost-analytics"
              className="block p-4 bg-bg-secondary hover:bg-accent hover:text-accent-fg rounded-lg transition-colors text-center"
            >
              Cost Analytics
            </Link>
            <Link
              to="/admin/users"
              className="block p-4 bg-bg-secondary hover:bg-accent hover:text-accent-fg rounded-lg transition-colors text-center"
            >
              {t('admin.overview.viewUsers')}
            </Link>
            <Link
              to="/admin/system"
              className="block p-4 bg-bg-secondary hover:bg-accent hover:text-accent-fg rounded-lg transition-colors text-center"
            >
              {t('admin.overview.viewSystem')}
            </Link>
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
