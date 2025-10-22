import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';

const LanguageConfigPage = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [languages, setLanguages] = useState([]);
  const [providers, setProviders] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedLanguage, setSelectedLanguage] = useState(null);
  const [languageDetail, setLanguageDetail] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      // Fetch all data in parallel
      const [langsRes, providersRes, statsRes] = await Promise.all([
        fetch('/api/admin/languages', { credentials: 'include' }),
        fetch('/api/admin/providers/health', { credentials: 'include' }),
        fetch('/api/admin/stats', { credentials: 'include' })
      ]);

      if (!langsRes.ok || !providersRes.ok || !statsRes.ok) {
        throw new Error('Failed to fetch configuration data');
      }

      const langsData = await langsRes.json();
      const providersData = await providersRes.json();
      const statsData = await statsRes.json();

      setLanguages(langsData.languages);
      setProviders(providersData.providers);
      setStats(statsData);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchLanguageDetail = async (language) => {
    try {
      const res = await fetch(`/api/admin/languages/${language}/config`, {
        credentials: 'include'
      });

      if (!res.ok) throw new Error('Failed to fetch language details');

      const data = await res.json();
      setLanguageDetail(data);
      setSelectedLanguage(language);
    } catch (err) {
      console.error('Error fetching language detail:', err);
      setError(err.message);
    }
  };

  const resetProviderHealth = async (provider, serviceType) => {
    try {
      const res = await fetch(
        `/api/admin/providers/${provider}/health/reset?service_type=${serviceType}`,
        {
          method: 'POST',
          credentials: 'include'
        }
      );

      if (!res.ok) throw new Error('Failed to reset provider health');

      // Refresh data
      fetchData();
      alert(`Provider ${provider} (${serviceType}) has been reset to healthy`);
    } catch (err) {
      console.error('Error resetting provider:', err);
      alert(`Error: ${err.message}`);
    }
  };

  const getStatusBadge = (status) => {
    const colors = {
      healthy: 'bg-green-100 text-green-800',
      degraded: 'bg-yellow-100 text-yellow-800',
      down: 'bg-red-100 text-red-800',
      active: 'bg-blue-100 text-blue-800',
      disabled: 'bg-gray-100 text-gray-800'
    };

    return (
      <span className={`px-2 py-1 rounded text-xs font-medium ${colors[status] || colors.disabled}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading language configuration...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <h3 className="text-red-800 font-medium">Error</h3>
            <p className="text-red-600 mt-1">{error}</p>
            <button
              onClick={() => fetchData()}
              className="mt-3 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
            >
              Retry
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Language Configuration</h1>
              <p className="mt-1 text-sm text-gray-500">
                Manage STT and MT provider settings for all languages
              </p>
            </div>
            <button
              onClick={() => navigate('/admin')}
              className="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50"
            >
              ← Back to Admin
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats Overview */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-8">
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="text-sm text-gray-500">Languages</div>
              <div className="text-3xl font-bold text-gray-900 mt-2">
                {stats.languages_configured}
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="text-sm text-gray-500">STT Configs</div>
              <div className="text-3xl font-bold text-gray-900 mt-2">
                {stats.stt_configs}
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="text-sm text-gray-500">MT Configs</div>
              <div className="text-3xl font-bold text-gray-900 mt-2">
                {stats.mt_configs}
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="text-sm text-gray-500">Healthy Providers</div>
              <div className="text-3xl font-bold text-green-600 mt-2">
                {stats.healthy_providers}/{stats.total_providers}
              </div>
            </div>
            <div className="bg-white p-6 rounded-lg shadow">
              <div className="text-sm text-gray-500">System Status</div>
              <div className="mt-2">
                {getStatusBadge(stats.system_status)}
              </div>
            </div>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Languages List */}
          <div className="lg:col-span-2">
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-medium text-gray-900">
                  Configured Languages ({languages.length})
                </h2>
              </div>
              <div className="divide-y divide-gray-200">
                {languages.map((lang) => (
                  <div
                    key={lang.language}
                    className={`px-6 py-4 hover:bg-gray-50 cursor-pointer ${
                      selectedLanguage === lang.language ? 'bg-blue-50' : ''
                    }`}
                    onClick={() => fetchLanguageDetail(lang.language)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1">
                        <div className="flex items-center space-x-3">
                          <h3 className="text-sm font-medium text-gray-900">
                            {lang.language_name}
                          </h3>
                          <span className="text-xs text-gray-500">
                            {lang.language}
                          </span>
                          {getStatusBadge(lang.status)}
                        </div>
                        <div className="mt-1 text-xs text-gray-500">
                          <span className="mr-4">
                            STT: {lang.stt_standard.partial?.provider_primary || 'N/A'}
                          </span>
                          <span>
                            MT: {lang.mt_pairs} pairs
                          </span>
                        </div>
                      </div>
                      <div className="text-gray-400">
                        →
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Provider Health */}
          <div className="lg:col-span-1">
            <div className="bg-white shadow rounded-lg">
              <div className="px-6 py-4 border-b border-gray-200">
                <h2 className="text-lg font-medium text-gray-900">
                  Provider Health
                </h2>
              </div>
              <div className="divide-y divide-gray-200">
                {providers.map((provider) => (
                  <div key={`${provider.provider}-${provider.service_type}`} className="px-6 py-3">
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-gray-900 truncate">
                          {provider.provider}
                        </div>
                        <div className="text-xs text-gray-500">
                          {provider.service_type.toUpperCase()}
                        </div>
                      </div>
                      <div className="ml-4">
                        {getStatusBadge(provider.status)}
                      </div>
                    </div>
                    {provider.consecutive_failures > 0 && (
                      <div className="mt-2 text-xs text-red-600">
                        {provider.consecutive_failures} consecutive failures
                        <button
                          onClick={() => resetProviderHealth(provider.provider, provider.service_type)}
                          className="ml-2 text-blue-600 hover:text-blue-800"
                        >
                          Reset
                        </button>
                      </div>
                    )}
                    {provider.response_time_ms && (
                      <div className="mt-1 text-xs text-gray-500">
                        {provider.response_time_ms}ms avg
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Language Detail Modal */}
        {languageDetail && (
          <div className="mt-8 bg-white shadow rounded-lg p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-gray-900">
                {languages.find(l => l.language === selectedLanguage)?.language_name || selectedLanguage}
              </h2>
              <button
                onClick={() => {
                  setSelectedLanguage(null);
                  setLanguageDetail(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            {/* STT Configuration */}
            <div className="mb-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                STT Configuration
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {languageDetail.stt_configs.map((config) => (
                  <div key={`${config.mode}-${config.quality_tier}`} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-medium text-gray-900">
                        {config.mode} / {config.quality_tier}
                      </h4>
                      {getStatusBadge(config.enabled ? 'active' : 'disabled')}
                    </div>
                    <div className="text-sm space-y-1">
                      <div>
                        <span className="text-gray-500">Primary:</span>{' '}
                        <span className="font-medium">{config.provider_primary}</span>
                      </div>
                      <div>
                        <span className="text-gray-500">Fallback:</span>{' '}
                        <span className="font-medium">{config.provider_fallback}</span>
                      </div>
                      {config.config && Object.keys(config.config).length > 0 && (
                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs">
                          <pre>{JSON.stringify(config.config, null, 2)}</pre>
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* MT Configuration */}
            <div>
              <h3 className="text-lg font-medium text-gray-900 mb-4">
                MT Configuration ({languageDetail.mt_configs.length} pairs)
              </h3>
              <div className="max-h-64 overflow-y-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50 sticky top-0">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                        Direction
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                        Tier
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                        Primary
                      </th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">
                        Fallback
                      </th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {languageDetail.mt_configs.slice(0, 20).map((config, idx) => (
                      <tr key={idx} className="text-sm">
                        <td className="px-4 py-2">
                          {config.src_lang} → {config.tgt_lang}
                        </td>
                        <td className="px-4 py-2">
                          <span className="text-xs">{config.quality_tier}</span>
                        </td>
                        <td className="px-4 py-2 font-medium">
                          {config.provider_primary}
                        </td>
                        <td className="px-4 py-2 text-gray-500">
                          {config.provider_fallback}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {languageDetail.mt_configs.length > 20 && (
                  <div className="text-center py-2 text-sm text-gray-500">
                    ... and {languageDetail.mt_configs.length - 20} more pairs
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LanguageConfigPage;
