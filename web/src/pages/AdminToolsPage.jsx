import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';

/**
 * AdminToolsPage - US-009, US-010, US-011, US-012: Admin Tools
 *
 * Placeholder for Phase 3C implementation.
 * Will display:
 * - User search and detail viewer
 * - Grant credits modal
 * - Active rooms viewer
 * - Message debug tool
 */
export default function AdminToolsPage({ token, onLogout }) {
  const { t } = useTranslation();

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('admin.tools.title') || 'Admin Tools'}</h1>

        {/* Placeholder Content */}
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <div className="text-6xl mb-4">🔧</div>
          <h2 className="text-2xl font-semibold mb-2">Phase 3C: Coming Soon</h2>
          <p className="text-muted mb-4">
            Admin tools for user search, credit grants, room monitoring, and message debugging.
          </p>
          <ul className="text-left max-w-md mx-auto space-y-2 text-muted">
            <li>• Search users by email or ID</li>
            <li>• View user details and quota balance</li>
            <li>• Grant bonus credits with reason tracking</li>
            <li>• View active rooms with participants</li>
            <li>• Debug message details (STT/MT costs, routing)</li>
          </ul>
        </div>
      </div>
    </AdminLayout>
  );
}

AdminToolsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
