import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import CreateNotificationModal from '../components/admin/CreateNotificationModal';
import { getNotifications } from '../utils/adminApi';

/**
 * AdminNotificationsPage - US-008: Notification Management (Basic Version)
 *
 * Allows admins to:
 * - View all notifications
 * - Create notifications (immediate only, no scheduling in v1)
 * - Filter by type, target, status
 */
export default function AdminNotificationsPage({ token, onLogout }) {
  const { t } = useTranslation();

  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Filters
  const [filters, setFilters] = useState({
    type: '',
    target: '',
    status: '',
    limit: 20,
    offset: 0
  });

  const [total, setTotal] = useState(0);

  useEffect(() => {
    loadNotifications();
  }, [filters.offset, filters.type, filters.target, filters.status]);

  const loadNotifications = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getNotifications(token, filters);
      setNotifications(data.notifications || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('[AdminNotificationsPage] Failed to load notifications:', err);
      setError(t('admin.notifications.loadError') || 'Failed to load notifications');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value, offset: 0 }));
  };

  const handlePageChange = (newOffset) => {
    setFilters(prev => ({ ...prev, offset: newOffset }));
  };

  const handleNotificationCreated = () => {
    setShowCreateModal(false);
    loadNotifications();
  };

  const getTypeBadgeColor = (type) => {
    switch (type) {
      case 'info': return 'bg-blue-100 text-blue-800';
      case 'warning': return 'bg-yellow-100 text-yellow-800';
      case 'success': return 'bg-green-100 text-green-800';
      case 'error': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getStatusBadgeColor = (status) => {
    switch (status) {
      case 'sent': return 'bg-green-100 text-green-800';
      case 'scheduled': return 'bg-orange-100 text-orange-800';
      case 'draft': return 'bg-gray-100 text-gray-800';
      case 'expired': return 'bg-gray-300 text-gray-600';
      case 'cancelled': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString();
  };

  const currentPage = Math.floor(filters.offset / filters.limit) + 1;
  const totalPages = Math.ceil(total / filters.limit);

  return (
    <AdminLayout token={token} onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <div className="mb-6 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {t('admin.notifications.title') || 'Notification Management'}
            </h1>
            <p className="text-gray-600 mt-1">
              {t('admin.notifications.subtitle') || 'Create and manage in-app notifications'}
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
          >
            {t('admin.notifications.createButton') || 'Create Notification'}
          </button>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('admin.notifications.filter.type') || 'Type'}
              </label>
              <select
                value={filters.type}
                onChange={(e) => handleFilterChange('type', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">{t('admin.notifications.filter.allTypes') || 'All Types'}</option>
                <option value="info">{t('admin.notifications.type.info') || 'Info'}</option>
                <option value="warning">{t('admin.notifications.type.warning') || 'Warning'}</option>
                <option value="success">{t('admin.notifications.type.success') || 'Success'}</option>
                <option value="error">{t('admin.notifications.type.error') || 'Error'}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('admin.notifications.filter.target') || 'Target'}
              </label>
              <select
                value={filters.target}
                onChange={(e) => handleFilterChange('target', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">{t('admin.notifications.filter.allTargets') || 'All Targets'}</option>
                <option value="all">{t('admin.notifications.target.all') || 'All Users'}</option>
                <option value="free">{t('admin.notifications.target.free') || 'Free Tier'}</option>
                <option value="plus">{t('admin.notifications.target.plus') || 'Plus Tier'}</option>
                <option value="pro">{t('admin.notifications.target.pro') || 'Pro Tier'}</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('admin.notifications.filter.status') || 'Status'}
              </label>
              <select
                value={filters.status}
                onChange={(e) => handleFilterChange('status', e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">{t('admin.notifications.filter.allStatuses') || 'All Statuses'}</option>
                <option value="sent">{t('admin.notifications.status.sent') || 'Sent'}</option>
                <option value="scheduled">{t('admin.notifications.status.scheduled') || 'Scheduled'}</option>
                <option value="draft">{t('admin.notifications.status.draft') || 'Draft'}</option>
              </select>
            </div>

            <div className="flex items-end">
              <button
                onClick={loadNotifications}
                className="w-full px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
              >
                {t('admin.notifications.refreshButton') || 'Refresh'}
              </button>
            </div>
          </div>
        </div>

        {/* Notifications Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {error && (
            <div className="p-4 bg-red-50 text-red-700">
              {error}
            </div>
          )}

          {loading ? (
            <div className="p-8 text-center text-gray-500">
              {t('admin.notifications.loading') || 'Loading...'}
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              {t('admin.notifications.empty') || 'No notifications found'}
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('admin.notifications.table.title') || 'Title'}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('admin.notifications.table.type') || 'Type'}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('admin.notifications.table.target') || 'Target'}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('admin.notifications.table.status') || 'Status'}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('admin.notifications.table.delivered') || 'Delivered'}
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        {t('admin.notifications.table.created') || 'Created'}
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {notifications.map((notification) => (
                      <tr key={notification.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4">
                          <div className="text-sm font-medium text-gray-900">
                            {notification.title}
                          </div>
                          <div className="text-sm text-gray-500 truncate max-w-xs">
                            {notification.message}
                          </div>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getTypeBadgeColor(notification.type)}`}>
                            {notification.type}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {notification.target}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusBadgeColor(notification.status)}`}>
                            {notification.status}
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {notification.delivered_count} / {notification.target_count}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          <div>{formatDate(notification.created_at)}</div>
                          <div className="text-xs text-gray-400">
                            {notification.created_by_email}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="px-6 py-4 bg-gray-50 border-t border-gray-200 flex items-center justify-between">
                  <div className="text-sm text-gray-700">
                    {t('admin.notifications.pagination.showing') || 'Showing'}{' '}
                    <span className="font-medium">{filters.offset + 1}</span> -
                    <span className="font-medium">{Math.min(filters.offset + filters.limit, total)}</span>{' '}
                    {t('admin.notifications.pagination.of') || 'of'}{' '}
                    <span className="font-medium">{total}</span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handlePageChange(Math.max(0, filters.offset - filters.limit))}
                      disabled={currentPage === 1}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                      {t('admin.notifications.pagination.previous') || 'Previous'}
                    </button>
                    <span className="px-3 py-1 text-sm text-gray-700">
                      {t('admin.notifications.pagination.page') || 'Page'} {currentPage} {t('admin.notifications.pagination.of') || 'of'} {totalPages}
                    </span>
                    <button
                      onClick={() => handlePageChange(filters.offset + filters.limit)}
                      disabled={currentPage === totalPages}
                      className="px-3 py-1 border border-gray-300 rounded-md text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
                    >
                      {t('admin.notifications.pagination.next') || 'Next'}
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <CreateNotificationModal
          token={token}
          onClose={() => setShowCreateModal(false)}
          onSuccess={handleNotificationCreated}
        />
      )}
    </AdminLayout>
  );
}

AdminNotificationsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
