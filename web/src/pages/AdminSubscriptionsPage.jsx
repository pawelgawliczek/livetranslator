import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import TierBadge from '../components/admin/TierBadge';
import StatusBadge from '../components/admin/StatusBadge';
import QuotaProgressBar from '../components/admin/QuotaProgressBar';
import {
  getSubscriptionTiers,
  updateSubscriptionTier,
  getUserSubscriptions,
  changeSubscriptionTier,
  cancelSubscription,
  reactivateSubscription,
  getSubscriptionAnalytics
} from '../utils/adminApi';

/**
 * AdminSubscriptionsPage - US-011: Subscription Plan Management
 *
 * Features:
 * - View and edit subscription tiers (pricing, quotas, features)
 * - View user subscriptions with filters (tier, status, platform)
 * - Change user tier, cancel, or reactivate subscriptions
 * - View subscription analytics (MRR, churn, distribution)
 * - Audit logging for all actions
 */
export default function AdminSubscriptionsPage({ token, onLogout }) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('tiers');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Tier management state
  const [tiers, setTiers] = useState([]);
  const [showInactive, setShowInactive] = useState(false);
  const [editingTier, setEditingTier] = useState(null);

  // User subscriptions state
  const [subscriptions, setSubscriptions] = useState([]);
  const [subscriptionFilters, setSubscriptionFilters] = useState({
    tier: '',
    status: '',
    platform: '',
    search: '',
    limit: 50,
    offset: 0
  });
  const [subscriptionTotal, setSubscriptionTotal] = useState(0);
  const [selectedSubscription, setSelectedSubscription] = useState(null);
  const [actionModal, setActionModal] = useState(null);  // 'change-tier', 'cancel', 'reactivate'

  // Analytics state
  const [analytics, setAnalytics] = useState(null);

  // Load data on mount and tab change
  useEffect(() => {
    loadData();
  }, [activeTab, showInactive, subscriptionFilters]);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      if (activeTab === 'tiers') {
        const data = await getSubscriptionTiers(token, showInactive);
        setTiers(data.tiers || []);
      } else if (activeTab === 'users') {
        const data = await getUserSubscriptions(token, subscriptionFilters);
        setSubscriptions(data.subscriptions || []);
        setSubscriptionTotal(data.total || 0);
      } else if (activeTab === 'analytics') {
        const data = await getSubscriptionAnalytics(token);
        setAnalytics(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateTier = async (tierId, updates) => {
    try {
      await updateSubscriptionTier(token, tierId, updates);
      setEditingTier(null);
      loadData();
      alert('Tier updated successfully');
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleChangeTier = async (subscriptionId, newTierId, effectiveDate, reason) => {
    try {
      await changeSubscriptionTier(token, subscriptionId, {
        new_tier_id: newTierId,
        effective_date: effectiveDate,
        reason: reason
      });
      setActionModal(null);
      setSelectedSubscription(null);
      loadData();
      alert('Tier changed successfully');
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleCancel = async (subscriptionId, effectiveDate, reason) => {
    try {
      await cancelSubscription(token, subscriptionId, {
        effective_date: effectiveDate,
        reason: reason
      });
      setActionModal(null);
      setSelectedSubscription(null);
      loadData();
      alert('Subscription cancelled successfully');
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  const handleReactivate = async (subscriptionId, tierId, reason) => {
    try {
      await reactivateSubscription(token, subscriptionId, {
        tier_id: tierId,
        reason: reason
      });
      setActionModal(null);
      setSelectedSubscription(null);
      loadData();
      alert('Subscription reactivated successfully');
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-fg">
            {t('admin.subscriptions.title') || 'Subscription Management'}
          </h1>
          <p className="text-muted mt-2">
            {t('admin.subscriptions.description') || 'Manage subscription tiers and user subscriptions'}
          </p>
        </div>

        {/* Tabs */}
        <div className="border-b border-border">
          <nav className="flex gap-4">
            <button
              onClick={() => setActiveTab('tiers')}
              className={`px-4 py-2 font-medium transition-colors ${
                activeTab === 'tiers'
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-muted hover:text-fg'
              }`}
            >
              {t('admin.subscriptions.tiers_tab') || 'Subscription Tiers'}
            </button>
            <button
              onClick={() => setActiveTab('users')}
              className={`px-4 py-2 font-medium transition-colors ${
                activeTab === 'users'
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-muted hover:text-fg'
              }`}
            >
              {t('admin.subscriptions.users_tab') || 'User Subscriptions'}
            </button>
            <button
              onClick={() => setActiveTab('analytics')}
              className={`px-4 py-2 font-medium transition-colors ${
                activeTab === 'analytics'
                  ? 'text-accent border-b-2 border-accent'
                  : 'text-muted hover:text-fg'
              }`}
            >
              {t('admin.subscriptions.analytics_tab') || 'Analytics'}
            </button>
          </nav>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
            {error}
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="text-center py-8 text-muted">
            Loading...
          </div>
        )}

        {/* Tab Content */}
        {!loading && (
          <div>
            {activeTab === 'tiers' && (
              <TiersTab
                tiers={tiers}
                showInactive={showInactive}
                setShowInactive={setShowInactive}
                editingTier={editingTier}
                setEditingTier={setEditingTier}
                onUpdateTier={handleUpdateTier}
              />
            )}
            {activeTab === 'users' && (
              <UsersTab
                subscriptions={subscriptions}
                total={subscriptionTotal}
                filters={subscriptionFilters}
                setFilters={setSubscriptionFilters}
                selectedSubscription={selectedSubscription}
                setSelectedSubscription={setSelectedSubscription}
                actionModal={actionModal}
                setActionModal={setActionModal}
                tiers={tiers.length > 0 ? tiers : []}  // Load tiers for modals
                onChangeTier={handleChangeTier}
                onCancel={handleCancel}
                onReactivate={handleReactivate}
              />
            )}
            {activeTab === 'analytics' && analytics && (
              <AnalyticsTab analytics={analytics} />
            )}
          </div>
        )}
      </div>
    </AdminLayout>
  );
}

// Tiers Tab Component
function TiersTab({ tiers, showInactive, setShowInactive, editingTier, setEditingTier, onUpdateTier }) {
  return (
    <div className="space-y-4">
      {/* Controls */}
      <div className="flex justify-between items-center">
        <label className="flex items-center gap-2 text-fg">
          <input
            type="checkbox"
            checked={showInactive}
            onChange={(e) => setShowInactive(e.target.checked)}
            className="rounded"
          />
          <span>Show Inactive Tiers</span>
        </label>
      </div>

      {/* Tiers Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-bg-secondary">
            <tr>
              <th className="px-4 py-3 text-left text-fg">Tier</th>
              <th className="px-4 py-3 text-left text-fg">Price</th>
              <th className="px-4 py-3 text-left text-fg">Quota</th>
              <th className="px-4 py-3 text-left text-fg">Active Users</th>
              <th className="px-4 py-3 text-left text-fg">Provider</th>
              <th className="px-4 py-3 text-left text-fg">Status</th>
              <th className="px-4 py-3 text-left text-fg">Actions</th>
            </tr>
          </thead>
          <tbody>
            {tiers.map((tier) => (
              <tr key={tier.id} className="border-t border-border">
                <td className="px-4 py-3">
                  <TierBadge tier={tier.tier_name} active={tier.is_active} />
                </td>
                <td className="px-4 py-3 text-fg">${tier.monthly_price_usd}/mo</td>
                <td className="px-4 py-3 text-fg">
                  {tier.monthly_quota_hours ? `${tier.monthly_quota_hours} hrs` : 'Unlimited'}
                </td>
                <td className="px-4 py-3 text-fg">{tier.active_users}</td>
                <td className="px-4 py-3 text-fg">{tier.provider_tier}</td>
                <td className="px-4 py-3">
                  {tier.is_active ? (
                    <span className="text-green-600">Active</span>
                  ) : (
                    <span className="text-red-600">Inactive</span>
                  )}
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => setEditingTier(tier)}
                    className="text-accent hover:underline"
                  >
                    Edit
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Edit Modal */}
      {editingTier && (
        <EditTierModal
          tier={editingTier}
          onClose={() => setEditingTier(null)}
          onSave={onUpdateTier}
        />
      )}
    </div>
  );
}

// Users Tab Component
function UsersTab({
  subscriptions,
  total,
  filters,
  setFilters,
  selectedSubscription,
  setSelectedSubscription,
  actionModal,
  setActionModal,
  tiers,
  onChangeTier,
  onCancel,
  onReactivate
}) {
  const handleFilterChange = (key, value) => {
    setFilters({ ...filters, [key]: value, offset: 0 });
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="grid grid-cols-4 gap-4">
        <select
          value={filters.tier}
          onChange={(e) => handleFilterChange('tier', e.target.value)}
          className="px-3 py-2 border border-border rounded bg-card text-fg"
        >
          <option value="">All Tiers</option>
          <option value="free">Free</option>
          <option value="plus">Plus</option>
          <option value="pro">Pro</option>
        </select>
        <select
          value={filters.status}
          onChange={(e) => handleFilterChange('status', e.target.value)}
          className="px-3 py-2 border border-border rounded bg-card text-fg"
        >
          <option value="">All Statuses</option>
          <option value="active">Active</option>
          <option value="cancelled">Cancelled</option>
          <option value="expired">Expired</option>
        </select>
        <select
          value={filters.platform}
          onChange={(e) => handleFilterChange('platform', e.target.value)}
          className="px-3 py-2 border border-border rounded bg-card text-fg"
        >
          <option value="">All Platforms</option>
          <option value="stripe">Stripe</option>
          <option value="apple">Apple</option>
        </select>
        <input
          type="text"
          placeholder="Search by email..."
          value={filters.search}
          onChange={(e) => handleFilterChange('search', e.target.value)}
          className="px-3 py-2 border border-border rounded bg-card text-fg"
        />
      </div>

      {/* Subscriptions Table */}
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-bg-secondary">
            <tr>
              <th className="px-4 py-3 text-left text-fg">User</th>
              <th className="px-4 py-3 text-left text-fg">Tier</th>
              <th className="px-4 py-3 text-left text-fg">Status</th>
              <th className="px-4 py-3 text-left text-fg">Platform</th>
              <th className="px-4 py-3 text-left text-fg">Quota Used</th>
              <th className="px-4 py-3 text-left text-fg">Auto-Renew</th>
              <th className="px-4 py-3 text-left text-fg">Actions</th>
            </tr>
          </thead>
          <tbody>
            {subscriptions.map((sub) => (
              <tr key={sub.id} className="border-t border-border">
                <td className="px-4 py-3 text-fg">{sub.user_email}</td>
                <td className="px-4 py-3">
                  <TierBadge tier={sub.tier_name} />
                </td>
                <td className="px-4 py-3">
                  <StatusBadge status={sub.status} />
                </td>
                <td className="px-4 py-3 text-fg">{sub.platform || '-'}</td>
                <td className="px-4 py-3">
                  <QuotaProgressBar
                    used={sub.quota_used_hours}
                    total={sub.monthly_quota_hours}
                  />
                </td>
                <td className="px-4 py-3 text-fg">{sub.auto_renew ? '✓' : '✗'}</td>
                <td className="px-4 py-3">
                  <div className="flex gap-2">
                    <button
                      onClick={() => {
                        setSelectedSubscription(sub);
                        setActionModal('change-tier');
                      }}
                      className="text-accent hover:underline text-sm"
                    >
                      Change
                    </button>
                    <button
                      onClick={() => {
                        setSelectedSubscription(sub);
                        setActionModal('cancel');
                      }}
                      className="text-red-600 hover:underline text-sm"
                    >
                      Cancel
                    </button>
                    {sub.status !== 'active' && (
                      <button
                        onClick={() => {
                          setSelectedSubscription(sub);
                          setActionModal('reactivate');
                        }}
                        className="text-green-600 hover:underline text-sm"
                      >
                        Reactivate
                      </button>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      <div className="text-fg">
        Showing {subscriptions.length} of {total} subscriptions
      </div>

      {/* Action Modals */}
      {actionModal === 'change-tier' && selectedSubscription && (
        <ChangeTierModal
          subscription={selectedSubscription}
          tiers={tiers}
          onClose={() => {
            setActionModal(null);
            setSelectedSubscription(null);
          }}
          onConfirm={onChangeTier}
        />
      )}
      {actionModal === 'cancel' && selectedSubscription && (
        <CancelModal
          subscription={selectedSubscription}
          onClose={() => {
            setActionModal(null);
            setSelectedSubscription(null);
          }}
          onConfirm={onCancel}
        />
      )}
      {actionModal === 'reactivate' && selectedSubscription && (
        <ReactivateModal
          subscription={selectedSubscription}
          tiers={tiers}
          onClose={() => {
            setActionModal(null);
            setSelectedSubscription(null);
          }}
          onConfirm={onReactivate}
        />
      )}
    </div>
  );
}

// Analytics Tab Component
function AnalyticsTab({ analytics }) {
  const { summary, mrr_history } = analytics;

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-muted text-sm">Active Subscriptions</div>
          <div className="text-3xl font-bold text-fg mt-2">{summary.total_active}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-muted text-sm">Monthly Recurring Revenue</div>
          <div className="text-3xl font-bold text-fg mt-2">${summary.mrr_usd.toFixed(2)}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-muted text-sm">Churn Rate</div>
          <div className={`text-3xl font-bold mt-2 ${
            summary.churn_rate > 10 ? 'text-red-600' :
            summary.churn_rate > 5 ? 'text-yellow-600' :
            'text-green-600'
          }`}>
            {summary.churn_rate.toFixed(1)}%
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-muted text-sm">Total Cancelled</div>
          <div className="text-3xl font-bold text-fg mt-2">{summary.total_cancelled}</div>
        </div>
      </div>

      {/* Tier Distribution */}
      <div className="bg-card border border-border rounded-lg p-4">
        <h3 className="text-lg font-semibold text-fg mb-4">Tier Distribution</h3>
        <div className="grid grid-cols-3 gap-4">
          {Object.entries(summary.tier_distribution).map(([tier, data]) => (
            <div key={tier} className="text-center">
              <TierBadge tier={tier} />
              <div className="mt-2 text-fg">
                <span className="text-2xl font-bold">{data.count}</span>
                <span className="text-muted ml-2">({data.percentage}%)</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// Edit Tier Modal
function EditTierModal({ tier, onClose, onSave }) {
  const [formData, setFormData] = useState({
    display_name: tier.display_name,
    monthly_price_usd: tier.monthly_price_usd,
    monthly_quota_hours: tier.monthly_quota_hours || '',
    is_active: tier.is_active
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    const updates = {};
    if (formData.display_name !== tier.display_name) {
      updates.display_name = formData.display_name;
    }
    if (parseFloat(formData.monthly_price_usd) !== parseFloat(tier.monthly_price_usd)) {
      updates.monthly_price_usd = parseFloat(formData.monthly_price_usd);
    }
    if (formData.monthly_quota_hours && parseFloat(formData.monthly_quota_hours) !== parseFloat(tier.monthly_quota_hours)) {
      updates.monthly_quota_hours = parseFloat(formData.monthly_quota_hours);
    }
    if (formData.is_active !== tier.is_active) {
      updates.is_active = formData.is_active;
    }

    if (Object.keys(updates).length > 0) {
      onSave(tier.id, updates);
    } else {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg p-6 w-full max-w-2xl">
        <h2 className="text-2xl font-bold text-fg mb-4">Edit Tier: {tier.display_name}</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-fg mb-2">Display Name</label>
              <input
                type="text"
                value={formData.display_name}
                onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
                maxLength={50}
                required
              />
            </div>
            <div>
              <label className="block text-fg mb-2">Monthly Price (USD)</label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="999.99"
                value={formData.monthly_price_usd}
                onChange={(e) => setFormData({ ...formData, monthly_price_usd: e.target.value })}
                className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-fg mb-2">Monthly Quota (Hours)</label>
            <input
              type="number"
              step="0.01"
              min="0"
              value={formData.monthly_quota_hours}
              onChange={(e) => setFormData({ ...formData, monthly_quota_hours: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              placeholder="Leave empty for unlimited"
            />
          </div>
          <div>
            <label className="flex items-center gap-2 text-fg">
              <input
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                className="rounded"
              />
              <span>Tier is Active</span>
            </label>
            {!formData.is_active && tier.active_users > 0 && (
              <p className="text-red-600 text-sm mt-2">
                ⚠️ Cannot deactivate tier with {tier.active_users} active subscriptions
              </p>
            )}
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-border rounded text-fg hover:bg-bg-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-accent text-accent-fg rounded hover:opacity-90"
            >
              Save Changes
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Change Tier Modal
function ChangeTierModal({ subscription, tiers, onClose, onConfirm }) {
  const [formData, setFormData] = useState({
    new_tier_id: '',
    effective_date: 'immediate',
    reason: ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (formData.reason.length < 20) {
      alert('Reason must be at least 20 characters');
      return;
    }
    onConfirm(subscription.id, parseInt(formData.new_tier_id), formData.effective_date, formData.reason);
  };

  const availableTiers = tiers.filter(t => t.id !== subscription.tier_id && t.is_active);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg p-6 w-full max-w-lg">
        <h2 className="text-2xl font-bold text-fg mb-4">Change Subscription Tier</h2>
        <p className="text-muted mb-4">User: {subscription.user_email}</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-fg mb-2">New Tier</label>
            <select
              value={formData.new_tier_id}
              onChange={(e) => setFormData({ ...formData, new_tier_id: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              required
            >
              <option value="">Select tier...</option>
              {availableTiers.map(tier => (
                <option key={tier.id} value={tier.id}>
                  {tier.display_name} (${tier.monthly_price_usd}/mo)
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-fg mb-2">Effective Date</label>
            <select
              value={formData.effective_date}
              onChange={(e) => setFormData({ ...formData, effective_date: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              required
            >
              <option value="immediate">Immediate</option>
              <option value="next_renewal">Next Renewal</option>
            </select>
          </div>
          <div>
            <label className="block text-fg mb-2">Reason (min 20 chars)</label>
            <textarea
              value={formData.reason}
              onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              rows={3}
              minLength={20}
              maxLength={500}
              required
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-border rounded text-fg hover:bg-bg-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-accent text-accent-fg rounded hover:opacity-90"
            >
              Confirm Change
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Cancel Modal
function CancelModal({ subscription, onClose, onConfirm }) {
  const [formData, setFormData] = useState({
    effective_date: 'period_end',
    reason: ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (formData.reason.length < 20) {
      alert('Reason must be at least 20 characters');
      return;
    }
    onConfirm(subscription.id, formData.effective_date, formData.reason);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg p-6 w-full max-w-lg">
        <h2 className="text-2xl font-bold text-fg mb-4">Cancel Subscription</h2>
        <p className="text-muted mb-4">User: {subscription.user_email}</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-fg mb-2">Effective Date</label>
            <select
              value={formData.effective_date}
              onChange={(e) => setFormData({ ...formData, effective_date: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              required
            >
              <option value="period_end">End of Billing Period</option>
              <option value="immediate">Immediate</option>
            </select>
          </div>
          <div>
            <label className="block text-fg mb-2">Reason (min 20 chars)</label>
            <textarea
              value={formData.reason}
              onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              rows={3}
              minLength={20}
              maxLength={500}
              required
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-border rounded text-fg hover:bg-bg-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              Confirm Cancellation
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Reactivate Modal
function ReactivateModal({ subscription, tiers, onClose, onConfirm }) {
  const [formData, setFormData] = useState({
    tier_id: '',
    reason: ''
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    if (formData.reason.length < 20) {
      alert('Reason must be at least 20 characters');
      return;
    }
    onConfirm(subscription.id, parseInt(formData.tier_id), formData.reason);
  };

  const activeTiers = tiers.filter(t => t.is_active);

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-card rounded-lg p-6 w-full max-w-lg">
        <h2 className="text-2xl font-bold text-fg mb-4">Reactivate Subscription</h2>
        <p className="text-muted mb-4">User: {subscription.user_email}</p>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-fg mb-2">Tier</label>
            <select
              value={formData.tier_id}
              onChange={(e) => setFormData({ ...formData, tier_id: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              required
            >
              <option value="">Select tier...</option>
              {activeTiers.map(tier => (
                <option key={tier.id} value={tier.id}>
                  {tier.display_name} (${tier.monthly_price_usd}/mo)
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-fg mb-2">Reason (min 20 chars)</label>
            <textarea
              value={formData.reason}
              onChange={(e) => setFormData({ ...formData, reason: e.target.value })}
              className="w-full px-3 py-2 border border-border rounded bg-bg text-fg"
              rows={3}
              minLength={20}
              maxLength={500}
              required
            />
          </div>
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-border rounded text-fg hover:bg-bg-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Confirm Reactivation
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

AdminSubscriptionsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired
};

TiersTab.propTypes = {
  tiers: PropTypes.array.isRequired,
  showInactive: PropTypes.bool.isRequired,
  setShowInactive: PropTypes.func.isRequired,
  editingTier: PropTypes.object,
  setEditingTier: PropTypes.func.isRequired,
  onUpdateTier: PropTypes.func.isRequired
};

UsersTab.propTypes = {
  subscriptions: PropTypes.array.isRequired,
  total: PropTypes.number.isRequired,
  filters: PropTypes.object.isRequired,
  setFilters: PropTypes.func.isRequired,
  selectedSubscription: PropTypes.object,
  setSelectedSubscription: PropTypes.func.isRequired,
  actionModal: PropTypes.string,
  setActionModal: PropTypes.func.isRequired,
  tiers: PropTypes.array.isRequired,
  onChangeTier: PropTypes.func.isRequired,
  onCancel: PropTypes.func.isRequired,
  onReactivate: PropTypes.func.isRequired
};

AnalyticsTab.propTypes = {
  analytics: PropTypes.object.isRequired
};

EditTierModal.propTypes = {
  tier: PropTypes.object.isRequired,
  onClose: PropTypes.func.isRequired,
  onSave: PropTypes.func.isRequired
};

ChangeTierModal.propTypes = {
  subscription: PropTypes.object.isRequired,
  tiers: PropTypes.array.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired
};

CancelModal.propTypes = {
  subscription: PropTypes.object.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired
};

ReactivateModal.propTypes = {
  subscription: PropTypes.object.isRequired,
  tiers: PropTypes.array.isRequired,
  onClose: PropTypes.func.isRequired,
  onConfirm: PropTypes.func.isRequired
};
