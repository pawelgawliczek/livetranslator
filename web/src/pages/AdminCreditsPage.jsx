import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import {
  getCreditPackages,
  updateCreditPackage,
  getCreditPurchases
} from '../utils/adminApi';

/**
 * AdminCreditsPage - US-012: Credit Package Purchase Flow
 *
 * Allows admins to:
 * - View and edit credit packages
 * - View purchase history with filters
 * - Export purchase data as CSV
 */
export default function AdminCreditsPage({ token, onLogout }) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('packages');

  // Packages state
  const [packages, setPackages] = useState([]);
  const [packagesLoading, setPackagesLoading] = useState(true);
  const [packagesError, setPackagesError] = useState(null);
  const [editingPackage, setEditingPackage] = useState(null);

  // Purchases state
  const [purchases, setPurchases] = useState([]);
  const [purchasesLoading, setPurchasesLoading] = useState(false);
  const [purchasesError, setPurchasesError] = useState(null);
  const [totalPurchases, setTotalPurchases] = useState(0);
  const [selectedPurchase, setSelectedPurchase] = useState(null);

  // Filters
  const [filters, setFilters] = useState({
    userEmail: '',
    package: '',
    platform: '',
    status: '',
    startDate: null,
    endDate: null,
    limit: 50,
    offset: 0
  });

  // Load packages on mount
  useEffect(() => {
    loadPackages();
  }, []);

  // Load purchases when tab changes to purchases
  useEffect(() => {
    if (activeTab === 'purchases') {
      loadPurchases();
    }
  }, [activeTab, filters.offset]);

  const loadPackages = async () => {
    setPackagesLoading(true);
    setPackagesError(null);

    try {
      const data = await getCreditPackages(token);
      setPackages(data.packages || []);
    } catch (err) {
      console.error('[AdminCreditsPage] Failed to load packages:', err);
      setPackagesError(t('admin.credits.error'));
    } finally {
      setPackagesLoading(false);
    }
  };

  const loadPurchases = async () => {
    setPurchasesLoading(true);
    setPurchasesError(null);

    try {
      const data = await getCreditPurchases(token, filters);
      setPurchases(data.purchases || []);
      setTotalPurchases(data.total || 0);
    } catch (err) {
      console.error('[AdminCreditsPage] Failed to load purchases:', err);
      setPurchasesError(t('admin.credits.error'));
    } finally {
      setPurchasesLoading(false);
    }
  };

  const handleEditPackage = (pkg) => {
    setEditingPackage({
      ...pkg,
      hours: pkg.hours,
      price_usd: pkg.price_usd,
      discount_percent: pkg.discount_percent,
      is_active: pkg.is_active
    });
  };

  const handleSavePackage = async () => {
    if (!editingPackage) return;

    try {
      await updateCreditPackage(token, editingPackage.id, {
        display_name: editingPackage.display_name,
        hours: parseFloat(editingPackage.hours),
        price_usd: parseFloat(editingPackage.price_usd),
        sort_order: editingPackage.sort_order,
        is_active: editingPackage.is_active
      });

      setEditingPackage(null);
      await loadPackages();
    } catch (err) {
      console.error('[AdminCreditsPage] Failed to update package:', err);
      alert(t('admin.credits.update_error') + ': ' + err.message);
    }
  };

  const handleApplyFilters = () => {
    setFilters(prev => ({ ...prev, offset: 0 }));
    loadPurchases();
  };

  const handleResetFilters = () => {
    setFilters({
      userEmail: '',
      package: '',
      platform: '',
      status: '',
      startDate: null,
      endDate: null,
      limit: 50,
      offset: 0
    });
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch (e) {
      return isoString;
    }
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-2">{t('admin.credits.title')}</h1>
        <p className="text-muted mb-6">{t('admin.credits.description')}</p>

        {/* Tabs */}
        <div className="border-b border-border mb-6">
          <div className="flex gap-4">
            <button
              onClick={() => setActiveTab('packages')}
              className={`px-4 py-2 border-b-2 transition-colors ${
                activeTab === 'packages'
                  ? 'border-primary text-primary font-semibold'
                  : 'border-transparent text-muted hover:text-fg'
              }`}
            >
              {t('admin.credits.packages_tab')}
            </button>
            <button
              onClick={() => setActiveTab('purchases')}
              className={`px-4 py-2 border-b-2 transition-colors ${
                activeTab === 'purchases'
                  ? 'border-primary text-primary font-semibold'
                  : 'border-transparent text-muted hover:text-fg'
              }`}
            >
              {t('admin.credits.purchases_tab')}
            </button>
          </div>
        </div>

        {/* Packages Tab */}
        {activeTab === 'packages' && (
          <div>
            {packagesLoading ? (
              <div className="text-center py-12">
                <div className="text-4xl mb-4">⏳</div>
                <p className="text-muted">{t('admin.credits.loading')}</p>
              </div>
            ) : packagesError ? (
              <div className="bg-red-900 bg-opacity-20 border border-red-600 text-red-400 rounded-lg p-4">
                {packagesError}
              </div>
            ) : packages.length === 0 ? (
              <div className="text-center py-12">
                <div className="text-4xl mb-4">📦</div>
                <p className="text-muted">{t('admin.credits.no_packages')}</p>
              </div>
            ) : (
              <div className="bg-card border border-border rounded-lg overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-secondary">
                      <tr>
                        <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.package_name')}</th>
                        <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.hours')}</th>
                        <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.price')}</th>
                        <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.discount')}</th>
                        <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.purchases_30d')}</th>
                        <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.status')}</th>
                        <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.actions')}</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {packages.map((pkg) => (
                        <tr key={pkg.id} className="hover:bg-secondary hover:bg-opacity-50 transition">
                          <td className="px-6 py-4 text-sm">{pkg.display_name}</td>
                          <td className="px-6 py-4 text-sm">{pkg.hours}</td>
                          <td className="px-6 py-4 text-sm">${pkg.price_usd}</td>
                          <td className="px-6 py-4 text-sm">{pkg.discount_percent}%</td>
                          <td className="px-6 py-4 text-sm">{pkg.purchase_count_30d}</td>
                          <td className="px-6 py-4 text-sm">
                            <span className={`px-2 py-1 rounded text-xs font-semibold ${
                              pkg.is_active
                                ? 'bg-green-900 bg-opacity-30 text-green-400'
                                : 'bg-red-900 bg-opacity-30 text-red-400'
                            }`}>
                              {pkg.is_active ? t('admin.credits.active') : t('admin.credits.inactive')}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-sm">
                            <button
                              onClick={() => handleEditPackage(pkg)}
                              className="text-primary hover:underline"
                            >
                              {t('admin.credits.edit')}
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Purchases Tab */}
        {activeTab === 'purchases' && (
          <div>
            {/* Filters */}
            <div className="bg-card border border-border rounded-lg p-6 mb-6">
              <h3 className="text-lg font-semibold mb-4">{t('admin.credits.filters')}</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">{t('admin.credits.user_email')}</label>
                  <input
                    type="text"
                    value={filters.userEmail}
                    onChange={(e) => setFilters({ ...filters, userEmail: e.target.value })}
                    placeholder="user@example.com"
                    className="w-full px-3 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">{t('admin.credits.package')}</label>
                  <select
                    value={filters.package}
                    onChange={(e) => setFilters({ ...filters, package: e.target.value })}
                    className="w-full px-3 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">{t('admin.credits.all_packages')}</option>
                    {packages.map((pkg) => (
                      <option key={pkg.id} value={pkg.package_name}>{pkg.display_name}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">{t('admin.credits.platform')}</label>
                  <select
                    value={filters.platform}
                    onChange={(e) => setFilters({ ...filters, platform: e.target.value })}
                    className="w-full px-3 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">{t('admin.credits.all_platforms')}</option>
                    <option value="stripe">{t('admin.credits.stripe')}</option>
                    <option value="apple">{t('admin.credits.apple')}</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">{t('admin.credits.status')}</label>
                  <select
                    value={filters.status}
                    onChange={(e) => setFilters({ ...filters, status: e.target.value })}
                    className="w-full px-3 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
                  >
                    <option value="">{t('admin.credits.all_statuses')}</option>
                    <option value="completed">{t('admin.credits.completed')}</option>
                    <option value="pending">{t('admin.credits.pending')}</option>
                    <option value="failed">{t('admin.credits.failed')}</option>
                  </select>
                </div>
              </div>

              <div className="mt-4">
                <DateRangePicker
                  startDate={filters.startDate}
                  endDate={filters.endDate}
                  onChange={(start, end) => setFilters({ ...filters, startDate: start, endDate: end })}
                />
              </div>

              <div className="flex gap-4 mt-4">
                <button
                  onClick={handleApplyFilters}
                  disabled={purchasesLoading}
                  className="px-6 py-2 bg-primary text-primary-foreground rounded hover:bg-opacity-90 transition disabled:opacity-50"
                >
                  {t('admin.credits.apply_filters')}
                </button>
                <button
                  onClick={handleResetFilters}
                  className="px-6 py-2 bg-secondary text-foreground rounded hover:bg-opacity-80 transition"
                >
                  {t('admin.credits.reset_filters')}
                </button>
              </div>
            </div>

            {/* Purchase History Table */}
            {purchasesLoading ? (
              <div className="text-center py-12">
                <div className="text-4xl mb-4">⏳</div>
                <p className="text-muted">{t('admin.credits.loading_purchases')}</p>
              </div>
            ) : purchasesError ? (
              <div className="bg-red-900 bg-opacity-20 border border-red-600 text-red-400 rounded-lg p-4">
                {purchasesError}
              </div>
            ) : purchases.length === 0 ? (
              <div className="text-center py-12">
                <div className="text-4xl mb-4">📭</div>
                <p className="text-muted">{t('admin.credits.no_purchases')}</p>
              </div>
            ) : (
              <>
                <div className="bg-card border border-border rounded-lg overflow-hidden mb-4">
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-secondary">
                        <tr>
                          <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.user')}</th>
                          <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.package')}</th>
                          <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.amount')}</th>
                          <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.platform')}</th>
                          <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.transaction_id')}</th>
                          <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.status')}</th>
                          <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.credits.date')}</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-border">
                        {purchases.map((purchase) => (
                          <tr
                            key={purchase.id}
                            className="hover:bg-secondary hover:bg-opacity-50 transition cursor-pointer"
                            onClick={() => setSelectedPurchase(purchase)}
                          >
                            <td className="px-6 py-4 text-sm">{purchase.user_email}</td>
                            <td className="px-6 py-4 text-sm">{purchase.package_name}</td>
                            <td className="px-6 py-4 text-sm">${purchase.amount_usd}</td>
                            <td className="px-6 py-4 text-sm capitalize">{purchase.platform}</td>
                            <td className="px-6 py-4 text-sm font-mono text-xs">{purchase.transaction_id?.slice(0, 20)}...</td>
                            <td className="px-6 py-4 text-sm">
                              <span className={`px-2 py-1 rounded text-xs font-semibold ${
                                purchase.status === 'completed'
                                  ? 'bg-green-900 bg-opacity-30 text-green-400'
                                  : purchase.status === 'pending'
                                  ? 'bg-yellow-900 bg-opacity-30 text-yellow-400'
                                  : 'bg-red-900 bg-opacity-30 text-red-400'
                              }`}>
                                {purchase.status}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-sm">{formatDate(purchase.created_at)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>

                <div className="text-sm text-muted">
                  {t('admin.credits.showing_results', { count: purchases.length, total: totalPurchases })}
                </div>
              </>
            )}
          </div>
        )}

        {/* Edit Package Modal */}
        {editingPackage && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-card border border-border rounded-lg max-w-md w-full p-6">
              <h2 className="text-2xl font-bold mb-4">{t('admin.credits.edit_package')}</h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">{t('admin.credits.hours_label')}</label>
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={editingPackage.hours}
                    onChange={(e) => setEditingPackage({ ...editingPackage, hours: e.target.value })}
                    className="w-full px-3 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">{t('admin.credits.price_label')}</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    value={editingPackage.price_usd}
                    onChange={(e) => setEditingPackage({ ...editingPackage, price_usd: e.target.value })}
                    className="w-full px-3 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2">{t('admin.credits.discount_label')}</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="100"
                    value={editingPackage.discount_percent}
                    onChange={(e) => setEditingPackage({ ...editingPackage, discount_percent: e.target.value })}
                    className="w-full px-3 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_active"
                    checked={editingPackage.is_active}
                    onChange={(e) => setEditingPackage({ ...editingPackage, is_active: e.target.checked })}
                    className="w-4 h-4"
                  />
                  <label htmlFor="is_active" className="text-sm font-medium cursor-pointer">
                    {t('admin.credits.active_label')}
                  </label>
                </div>
              </div>

              <div className="flex gap-4 mt-6">
                <button
                  onClick={() => setEditingPackage(null)}
                  className="flex-1 px-4 py-2 bg-secondary text-foreground rounded hover:bg-opacity-80 transition"
                >
                  {t('admin.credits.cancel')}
                </button>
                <button
                  onClick={handleSavePackage}
                  className="flex-1 px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-opacity-90 transition"
                >
                  {t('admin.credits.save')}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Purchase Detail Modal */}
        {selectedPurchase && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
            <div className="bg-card border border-border rounded-lg max-w-2xl w-full p-6 max-h-[80vh] overflow-y-auto">
              <h2 className="text-2xl font-bold mb-4">{t('admin.credits.purchase_details')}</h2>

              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <span className="text-muted text-sm">Transaction ID:</span>
                    <p className="font-mono text-sm">{selectedPurchase.id}</p>
                  </div>
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.user')}:</span>
                    <p className="text-sm">{selectedPurchase.user_email}</p>
                  </div>
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.package')}:</span>
                    <p className="text-sm">{selectedPurchase.package_name}</p>
                  </div>
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.amount')}:</span>
                    <p className="text-sm">${selectedPurchase.amount_usd}</p>
                  </div>
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.platform')}:</span>
                    <p className="text-sm capitalize">{selectedPurchase.platform}</p>
                  </div>
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.status')}:</span>
                    <p className="text-sm capitalize">{selectedPurchase.status}</p>
                  </div>
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.date')}:</span>
                    <p className="text-sm">{formatDate(selectedPurchase.created_at)}</p>
                  </div>
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.completed_at')}:</span>
                    <p className="text-sm">{formatDate(selectedPurchase.completed_at)}</p>
                  </div>
                </div>

                <div>
                  <span className="text-muted text-sm">{t('admin.credits.transaction_id')}:</span>
                  <p className="font-mono text-xs break-all">{selectedPurchase.transaction_id}</p>
                </div>

                {selectedPurchase.metadata && Object.keys(selectedPurchase.metadata).length > 0 && (
                  <div>
                    <span className="text-muted text-sm">{t('admin.credits.metadata')}:</span>
                    <pre className="mt-2 p-3 bg-secondary rounded text-xs overflow-x-auto">
                      {JSON.stringify(selectedPurchase.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>

              <div className="mt-6">
                <button
                  onClick={() => setSelectedPurchase(null)}
                  className="w-full px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-opacity-90 transition"
                >
                  {t('admin.credits.close')}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AdminLayout>
  );
}

AdminCreditsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
