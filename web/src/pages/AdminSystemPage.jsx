import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import {
  getFeatureFlags,
  getRateLimits,
  getProviderHealth,
  updateFeatureFlag,
  updateRateLimits,
  resetProviderHealth
} from '../utils/adminApi';

/**
 * AdminSystemPage - US-003: System Settings
 *
 * Provides admin interface for:
 * - Feature toggles (diarization, caching, throttling)
 * - Rate limits (connections, requests, quotas)
 * - Provider health monitoring
 */
export default function AdminSystemPage({ token, onLogout }) {
  const { t } = useTranslation();

  // Tab state
  const [activeTab, setActiveTab] = useState('features');

  // Data state
  const [featureFlags, setFeatureFlags] = useState([]);
  const [rateLimits, setRateLimits] = useState([]);
  const [providerHealth, setProviderHealth] = useState([]);
  const [editedLimits, setEditedLimits] = useState({});

  // UI state
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [successMessage, setSuccessMessage] = useState(null);

  // Fetch all data on mount
  useEffect(() => {
    fetchAllData();
  }, []);

  // Auto-refresh provider health every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      if (activeTab === 'health') {
        fetchProviderHealth();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [activeTab]);

  const fetchAllData = async () => {
    setLoading(true);
    setError(null);

    try {
      const [flagsData, limitsData, healthData] = await Promise.all([
        getFeatureFlags(token),
        getRateLimits(token),
        getProviderHealth(token)
      ]);

      setFeatureFlags(flagsData.flags || []);
      setRateLimits(limitsData.limits || []);
      setProviderHealth(healthData.providers || []);
    } catch (err) {
      console.error('[AdminSystemPage] Failed to fetch data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchProviderHealth = async () => {
    try {
      const healthData = await getProviderHealth(token);
      setProviderHealth(healthData.providers || []);
    } catch (err) {
      console.error('[AdminSystemPage] Failed to refresh provider health:', err);
    }
  };

  const handleToggleFlag = async (flag) => {
    const newValue = flag.value_type === 'boolean' ? !flag.value : flag.value;

    try {
      await updateFeatureFlag(token, flag.key, newValue);
      setSuccessMessage('Feature flag updated successfully');
      setTimeout(() => setSuccessMessage(null), 3000);
      fetchAllData();
    } catch (err) {
      console.error('[AdminSystemPage] Failed to update flag:', err);
      setError(err.message);
      setTimeout(() => setError(null), 5000);
    }
  };

  const handleSaveRateLimits = async () => {
    try {
      await updateRateLimits(token, editedLimits);
      setSuccessMessage('Rate limits updated successfully');
      setEditedLimits({});
      setTimeout(() => setSuccessMessage(null), 3000);
      fetchAllData();
    } catch (err) {
      console.error('[AdminSystemPage] Failed to save limits:', err);
      setError(err.message);
      setTimeout(() => setError(null), 5000);
    }
  };

  const handleResetProvider = async (provider, serviceType) => {
    if (!window.confirm(`Mark ${provider} (${serviceType}) as healthy?`)) {
      return;
    }

    try {
      await resetProviderHealth(token, provider, serviceType);
      setSuccessMessage('Provider health reset successfully');
      setTimeout(() => setSuccessMessage(null), 3000);
      fetchProviderHealth();
    } catch (err) {
      console.error('[AdminSystemPage] Failed to reset provider:', err);
      setError(err.message);
      setTimeout(() => setError(null), 5000);
    }
  };

  const getStatusBadge = (provider) => {
    if (provider.status === 'healthy') {
      return <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">Healthy</span>;
    } else if (provider.status === 'degraded') {
      return <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded text-xs">Degraded</span>;
    } else {
      return <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">Down</span>;
    }
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">System Settings</h1>

        {/* Error/Success Messages */}
        {error && (
          <div className="mb-4 p-3 bg-red-100 text-red-800 rounded">
            {error}
          </div>
        )}
        {successMessage && (
          <div className="mb-4 p-3 bg-green-100 text-green-800 rounded">
            {successMessage}
          </div>
        )}

        {/* Tab Navigation */}
        <div className="mb-6 border-b border-border">
          <div className="flex gap-4">
            <button
              className={`pb-2 px-1 ${activeTab === 'features' ? 'border-b-2 border-primary font-semibold' : 'text-muted'}`}
              onClick={() => setActiveTab('features')}
            >
              Feature Flags
            </button>
            <button
              className={`pb-2 px-1 ${activeTab === 'limits' ? 'border-b-2 border-primary font-semibold' : 'text-muted'}`}
              onClick={() => setActiveTab('limits')}
            >
              Rate Limits
            </button>
            <button
              className={`pb-2 px-1 ${activeTab === 'health' ? 'border-b-2 border-primary font-semibold' : 'text-muted'}`}
              onClick={() => setActiveTab('health')}
            >
              Provider Health
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {loading && activeTab !== 'health' ? (
          <div className="text-center py-8">Loading...</div>
        ) : (
          <>
            {/* Feature Flags Tab */}
            {activeTab === 'features' && (
              <div className="bg-card border border-border rounded-lg overflow-hidden">
                <table className="w-full">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3">Feature</th>
                      <th className="text-left p-3">Description</th>
                      <th className="text-left p-3">Category</th>
                      <th className="text-center p-3">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {featureFlags.map((flag) => (
                      <tr key={flag.key} className="border-t border-border">
                        <td className="p-3 font-mono text-sm">{flag.key}</td>
                        <td className="p-3 text-sm text-muted">{flag.description}</td>
                        <td className="p-3 text-sm">{flag.category}</td>
                        <td className="p-3 text-center">
                          {flag.value_type === 'boolean' ? (
                            <button
                              onClick={() => handleToggleFlag(flag)}
                              className={`px-3 py-1 rounded text-sm ${
                                flag.value ? 'bg-green-100 text-green-800' : 'bg-gray-200 text-gray-600'
                              }`}
                            >
                              {flag.value ? 'ON' : 'OFF'}
                            </button>
                          ) : (
                            <span className="font-mono">{flag.value}</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* Rate Limits Tab */}
            {activeTab === 'limits' && (
              <div>
                <div className="bg-card border border-border rounded-lg overflow-hidden">
                  <table className="w-full">
                    <thead className="bg-muted">
                      <tr>
                        <th className="text-left p-3">Setting</th>
                        <th className="text-left p-3">Description</th>
                        <th className="text-center p-3">Current Value</th>
                        <th className="text-center p-3">New Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rateLimits.map((limit) => (
                        <tr key={limit.key} className="border-t border-border">
                          <td className="p-3 font-mono text-sm">{limit.key}</td>
                          <td className="p-3 text-sm text-muted">{limit.description}</td>
                          <td className="p-3 text-center font-mono">{limit.value}</td>
                          <td className="p-3 text-center">
                            <input
                              type="number"
                              className="w-24 px-2 py-1 border border-border rounded text-center"
                              defaultValue={limit.value}
                              onChange={(e) => setEditedLimits({
                                ...editedLimits,
                                [limit.key]: parseInt(e.target.value)
                              })}
                            />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {Object.keys(editedLimits).length > 0 && (
                  <div className="mt-4 flex gap-2">
                    <button
                      onClick={handleSaveRateLimits}
                      className="px-4 py-2 bg-primary text-white rounded hover:bg-primary-dark"
                    >
                      Save Changes
                    </button>
                    <button
                      onClick={() => setEditedLimits({})}
                      className="px-4 py-2 border border-border rounded hover:bg-muted"
                    >
                      Cancel
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* Provider Health Tab */}
            {activeTab === 'health' && (
              <div className="bg-card border border-border rounded-lg overflow-hidden">
                <div className="p-3 bg-muted flex justify-between items-center">
                  <span className="font-semibold">Provider Status</span>
                  <button
                    onClick={fetchProviderHealth}
                    className="px-3 py-1 bg-white border border-border rounded text-sm hover:bg-gray-50"
                  >
                    Refresh
                  </button>
                </div>
                <table className="w-full">
                  <thead className="bg-muted">
                    <tr>
                      <th className="text-left p-3">Provider</th>
                      <th className="text-left p-3">Service</th>
                      <th className="text-center p-3">Status</th>
                      <th className="text-center p-3">Failures</th>
                      <th className="text-center p-3">Last Check</th>
                      <th className="text-center p-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {providerHealth.map((provider) => (
                      <tr key={`${provider.provider}-${provider.service_type}`} className="border-t border-border">
                        <td className="p-3 font-mono text-sm">{provider.provider}</td>
                        <td className="p-3 text-sm">{provider.service_type.toUpperCase()}</td>
                        <td className="p-3 text-center">{getStatusBadge(provider)}</td>
                        <td className="p-3 text-center font-mono">{provider.consecutive_failures}</td>
                        <td className="p-3 text-center text-sm text-muted">
                          {provider.last_check ? new Date(provider.last_check).toLocaleString() : 'Never'}
                        </td>
                        <td className="p-3 text-center">
                          {provider.status !== 'healthy' && (
                            <button
                              onClick={() => handleResetProvider(provider.provider, provider.service_type)}
                              className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded text-sm hover:bg-yellow-200"
                            >
                              Reset
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
      </div>
    </AdminLayout>
  );
}

AdminSystemPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
