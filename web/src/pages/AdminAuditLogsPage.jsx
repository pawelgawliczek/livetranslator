import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { useLocation, useNavigate } from 'react-router-dom';
import AdminLayout from '../components/admin/AdminLayout';
import { getAuditLogs, exportAuditLogs, getAdminUsers } from '../utils/adminApi';

/**
 * AdminAuditLogsPage - US-006: Audit Log Viewer
 *
 * Allows admins to:
 * - View chronological log of all admin actions
 * - Filter by date range, admin user, action type
 * - Export logs as CSV
 * - Expand rows to see full details JSON
 */
export default function AdminAuditLogsPage({ token, onLogout }) {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();

  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [admins, setAdmins] = useState([]);
  const [expandedRows, setExpandedRows] = useState(new Set());
  const [exporting, setExporting] = useState(false);

  // Default to last 30 days
  const defaultStartDate = new Date(Date.now() - 30 * 24 * 3600 * 1000).toISOString().slice(0, 16);
  const defaultEndDate = new Date().toISOString().slice(0, 16);

  const [filters, setFilters] = useState({
    start_date: defaultStartDate,
    end_date: defaultEndDate,
    admin_id: '',
    action: '',
    limit: 50,
    offset: 0
  });

  const [total, setTotal] = useState(0);

  // Load filters from URL on mount
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlFilters = {};

    if (params.get('start_date')) {
      urlFilters.start_date = new Date(params.get('start_date')).toISOString().slice(0, 16);
    }
    if (params.get('end_date')) {
      urlFilters.end_date = new Date(params.get('end_date')).toISOString().slice(0, 16);
    }
    if (params.get('admin_id')) {
      urlFilters.admin_id = params.get('admin_id');
    }
    if (params.get('action')) {
      urlFilters.action = params.get('action');
    }
    if (params.get('offset')) {
      urlFilters.offset = parseInt(params.get('offset'));
    }

    if (Object.keys(urlFilters).length > 0) {
      setFilters(prev => ({ ...prev, ...urlFilters }));
    }
  }, []);

  // Load admin users for dropdown
  useEffect(() => {
    loadAdminUsers();
  }, []);

  // Load logs when filters change
  useEffect(() => {
    loadLogs();
  }, [filters.offset]);

  const loadAdminUsers = async () => {
    try {
      const data = await getAdminUsers(token);
      setAdmins(data.admins || []);
    } catch (err) {
      console.error('[AdminAuditLogsPage] Failed to load admin users:', err);
    }
  };

  const loadLogs = async () => {
    setLoading(true);
    setError(null);

    try {
      // Convert datetime-local to ISO 8601
      const apiFilters = {
        ...filters,
        start_date: filters.start_date ? new Date(filters.start_date).toISOString() : undefined,
        end_date: filters.end_date ? new Date(filters.end_date).toISOString() : undefined,
        admin_id: filters.admin_id || undefined,
        action: filters.action || undefined
      };

      const data = await getAuditLogs(token, apiFilters);
      setLogs(data.logs || []);
      setTotal(data.total || 0);
    } catch (err) {
      console.error('[AdminAuditLogsPage] Failed to load audit logs:', err);
      setError('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  };

  const updateUrl = () => {
    const params = new URLSearchParams();

    if (filters.start_date) {
      params.set('start_date', new Date(filters.start_date).toISOString());
    }
    if (filters.end_date) {
      params.set('end_date', new Date(filters.end_date).toISOString());
    }
    if (filters.admin_id) {
      params.set('admin_id', filters.admin_id);
    }
    if (filters.action) {
      params.set('action', filters.action);
    }
    if (filters.offset > 0) {
      params.set('offset', filters.offset);
    }

    navigate(`?${params.toString()}`, { replace: true });
  };

  const handleApplyFilters = () => {
    setFilters(prev => ({ ...prev, offset: 0 }));
    updateUrl();
    loadLogs();
  };

  const handleResetFilters = () => {
    const defaults = {
      start_date: defaultStartDate,
      end_date: defaultEndDate,
      admin_id: '',
      action: '',
      limit: 50,
      offset: 0
    };
    setFilters(defaults);
    navigate('', { replace: true });
    setTimeout(() => loadLogs(), 100);
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      const apiFilters = {
        start_date: filters.start_date ? new Date(filters.start_date).toISOString() : undefined,
        end_date: filters.end_date ? new Date(filters.end_date).toISOString() : undefined,
        admin_id: filters.admin_id || undefined,
        action: filters.action || undefined
      };

      await exportAuditLogs(token, apiFilters);
    } catch (err) {
      console.error('[AdminAuditLogsPage] Failed to export:', err);
      alert('Failed to export audit logs');
    } finally {
      setExporting(false);
    }
  };

  const toggleExpanded = (logId) => {
    setExpandedRows(prev => {
      const newSet = new Set(prev);
      if (newSet.has(logId)) {
        newSet.delete(logId);
      } else {
        newSet.add(logId);
      }
      return newSet;
    });
  };

  const getActionBadgeColor = (action) => {
    // User Management
    if (action.includes('user') || action.includes('role')) {
      return 'bg-blue-100 text-blue-800';
    }
    // Subscriptions
    if (action.includes('subscription') || action.includes('tier')) {
      return 'bg-purple-100 text-purple-800';
    }
    // Credits
    if (action.includes('credit') || action.includes('grant') || action.includes('refund')) {
      return 'bg-green-100 text-green-800';
    }
    // Notifications
    if (action.includes('notification')) {
      return 'bg-yellow-100 text-yellow-800';
    }
    // System
    if (action.includes('system') || action.includes('cache') || action.includes('config')) {
      return 'bg-red-100 text-red-800';
    }
    // Default
    return 'bg-gray-100 text-gray-800';
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return '-';
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
  };

  const currentPage = Math.floor(filters.offset / filters.limit) + 1;
  const totalPages = Math.ceil(total / filters.limit);

  const handlePageChange = (newOffset) => {
    setFilters(prev => ({ ...prev, offset: newOffset }));
    updateUrl();
  };

  return (
    <AdminLayout token={token} onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-gray-900">
            Audit Logs
          </h1>
          <p className="text-gray-600 mt-1">
            View chronological log of all admin actions
          </p>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Start Date */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Start Date
              </label>
              <input
                type="datetime-local"
                value={filters.start_date}
                onChange={(e) => setFilters(prev => ({ ...prev, start_date: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* End Date */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                End Date
              </label>
              <input
                type="datetime-local"
                value={filters.end_date}
                onChange={(e) => setFilters(prev => ({ ...prev, end_date: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
              />
            </div>

            {/* Admin User Dropdown */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Admin User
              </label>
              <select
                value={filters.admin_id}
                onChange={(e) => setFilters(prev => ({ ...prev, admin_id: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Admins</option>
                {admins.map(admin => (
                  <option key={admin.id} value={admin.id}>
                    {admin.email}
                  </option>
                ))}
              </select>
            </div>

            {/* Action Type Dropdown */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Action Type
              </label>
              <select
                value={filters.action}
                onChange={(e) => setFilters(prev => ({ ...prev, action: e.target.value }))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
              >
                <option value="">All Actions</option>
                <optgroup label="User Management">
                  <option value="create_user">Create User</option>
                  <option value="update_user">Update User</option>
                  <option value="delete_user">Delete User</option>
                </optgroup>
                <optgroup label="Subscriptions">
                  <option value="update_subscription_tier">Update Tier</option>
                  <option value="change_subscription_tier">Change User Tier</option>
                  <option value="cancel_subscription">Cancel Subscription</option>
                  <option value="reactivate_subscription">Reactivate Subscription</option>
                </optgroup>
                <optgroup label="Credits">
                  <option value="update_credit_package">Update Package</option>
                  <option value="grant_credits">Grant Credits</option>
                  <option value="refund_credits">Refund Credits</option>
                </optgroup>
                <optgroup label="Notifications">
                  <option value="create_notification">Create Notification</option>
                  <option value="delete_notification">Delete Notification</option>
                </optgroup>
              </select>
            </div>
          </div>

          <div className="flex gap-2 mt-4">
            <button
              onClick={handleApplyFilters}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
            >
              Apply Filters
            </button>
            <button
              onClick={handleResetFilters}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition"
            >
              Reset Filters
            </button>
            <button
              onClick={handleExport}
              disabled={exporting}
              className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition disabled:opacity-50 disabled:cursor-not-allowed ml-auto"
            >
              {exporting ? 'Exporting...' : 'Export CSV'}
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-500">
              Loading audit logs...
            </div>
          ) : error ? (
            <div className="p-8 text-center text-red-600">
              {error}
            </div>
          ) : logs.length === 0 ? (
            <div className="p-8 text-center text-gray-500">
              No audit logs found for the selected filters
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Timestamp
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Admin
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Action
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Target
                      </th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                        IP Address
                      </th>
                      <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                        Details
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {logs.map(log => (
                      <React.Fragment key={log.id}>
                        <tr className="hover:bg-gray-50">
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                            {formatTimestamp(log.timestamp)}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                            <div>{log.admin.email}</div>
                            {log.admin.display_name && (
                              <div className="text-xs text-gray-500">{log.admin.display_name}</div>
                            )}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 py-1 text-xs font-medium rounded-full ${getActionBadgeColor(log.action)}`}>
                              {log.action}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-600">
                            {log.target_user ? log.target_user.email : '-'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                            {log.ip_address || 'N/A'}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-right text-sm">
                            <button
                              onClick={() => toggleExpanded(log.id)}
                              className="text-blue-600 hover:text-blue-900 font-medium"
                            >
                              {expandedRows.has(log.id) ? '▼ Hide' : '▶ Show'}
                            </button>
                          </td>
                        </tr>
                        {expandedRows.has(log.id) && (
                          <tr>
                            <td colSpan="6" className="px-6 py-4 bg-gray-50">
                              <div className="text-sm font-medium text-gray-700 mb-2">Details:</div>
                              <pre className="text-xs bg-gray-100 p-3 rounded overflow-x-auto whitespace-pre-wrap border border-gray-200">
                                {JSON.stringify(log.details, null, 2)}
                              </pre>
                              {log.user_agent && (
                                <div className="mt-2 text-xs text-gray-600">
                                  <span className="font-medium">User Agent:</span> {log.user_agent}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="bg-gray-50 px-6 py-4 border-t border-gray-200 flex items-center justify-between">
                  <div className="text-sm text-gray-700">
                    Showing {filters.offset + 1} to {Math.min(filters.offset + filters.limit, total)} of {total} logs
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handlePageChange(Math.max(0, filters.offset - filters.limit))}
                      disabled={filters.offset === 0}
                      className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                    >
                      Previous
                    </button>
                    <div className="px-4 py-2 text-sm text-gray-700">
                      Page {currentPage} of {totalPages}
                    </div>
                    <button
                      onClick={() => handlePageChange(filters.offset + filters.limit)}
                      disabled={filters.offset + filters.limit >= total}
                      className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 disabled:opacity-50 disabled:cursor-not-allowed transition"
                    >
                      Next
                    </button>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </AdminLayout>
  );
}

AdminAuditLogsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
