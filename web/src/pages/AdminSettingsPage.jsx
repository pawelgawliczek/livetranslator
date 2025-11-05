import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";

export default function AdminSettingsPage({ token, onLogout }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Language Configuration state
  const [languages, setLanguages] = useState([]);
  const [providerHealth, setProviderHealth] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedLanguage, setSelectedLanguage] = useState(null);
  const [languageDetail, setLanguageDetail] = useState(null);

  useEffect(() => {
    if (!token) {
      navigate("/login");
      return;
    }
    fetchAdminData();
  }, [token]);

  async function fetchAdminData() {
    setLoading(true);
    try {
      // Test admin access
      const testRes = await fetch("/api/admin/test", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (!testRes.ok) {
        setError("Unauthorized: Admin access required");
        setTimeout(() => navigate("/rooms"), 2000);
        return;
      }

      // Fetch language configuration data
      try {
        const [langsRes, healthRes, statsRes] = await Promise.all([
          fetch("/api/admin/languages", { headers: { "Authorization": `Bearer ${token}` } }),
          fetch("/api/admin/providers/health", { headers: { "Authorization": `Bearer ${token}` } }),
          fetch("/api/admin/stats", { headers: { "Authorization": `Bearer ${token}` } })
        ]);

        if (langsRes.ok) {
          const langsData = await langsRes.json();
          console.log('[Admin] Languages data:', langsData);
          setLanguages(langsData.languages || []);
        } else {
          console.error('[Admin] Languages fetch failed:', langsRes.status);
        }
        if (healthRes.ok) {
          const healthData = await healthRes.json();
          console.log('[Admin] Provider health:', healthData);
          setProviderHealth(healthData.providers || []);
        }
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          console.log('[Admin] Stats:', statsData);
          setStats(statsData);
        }
      } catch (e) {
        console.error("Language config error:", e);
        setError("Failed to load language configuration");
      }
    } catch (e) {
      console.error("Failed to fetch admin data:", e);
      setError("Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }

  async function fetchLanguageDetail(language) {
    try {
      const res = await fetch(`/api/admin/languages/${language}/config`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setLanguageDetail(data);
        setSelectedLanguage(language);
      }
    } catch (e) {
      console.error("Failed to fetch language detail:", e);
    }
  }

  if (loading) {
    return (
      <div style={{ padding: "20px", textAlign: "center" }}>
        <p>{t("loading") || "Loading admin settings..."}</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg text-fg font-sans flex flex-col">
      <div className="flex-1 p-8 pb-4">
        <div className="max-w-[1000px] mx-auto">
          {/* Header */}
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-3xl mb-2">🌍 Language Configuration</h1>
              <p className="text-muted text-sm">Manage STT and MT provider settings for all languages</p>
            </div>
            <div className="flex gap-2.5 items-center">
              <button
                onClick={() => navigate("/rooms")}
                className="px-6 py-3 bg-accent text-white border-none rounded-lg cursor-pointer font-semibold
                           hover:bg-accent-dark transition-colors"
              >
                ← {t("back_to_rooms") || "Rooms"}
              </button>
              <button
                onClick={() => navigate("/admin/cost-analytics")}
                className="px-6 py-3 bg-blue-600 text-white border-none rounded-lg cursor-pointer font-semibold
                           hover:bg-blue-700 transition-colors"
              >
                💰 Cost Analytics
              </button>
              <button
                onClick={onLogout}
                className="px-6 py-3 bg-red-600 text-white border-none rounded-lg cursor-pointer font-semibold
                           hover:bg-red-700 transition-colors"
              >
                {t("logout") || "Logout"}
              </button>
            </div>
          </div>

          <div className="mb-8">
            {/* Error Messages */}
            {error && (
              <div className="bg-card border border-red-600 text-red-600 p-3 rounded-lg mb-5">
                {error}
              </div>
            )}

            {/* Languages Content */}
            <div>
              {/* Stats Overview */}
              {stats && (
                <div className="grid grid-cols-[repeat(auto-fit,minmax(200px,1fr))] gap-4 mb-8">
                  <div className="bg-card p-6 rounded-xl border border-border">
                    <div className="text-sm text-muted mb-2">Languages</div>
                    <div className="text-3xl font-bold text-fg">{stats.languages_configured}</div>
                  </div>
                  <div className="bg-card p-6 rounded-xl border border-border">
                    <div className="text-sm text-muted mb-2">STT Configs</div>
                    <div className="text-3xl font-bold text-fg">{stats.stt_configs}</div>
                  </div>
                  <div className="bg-card p-6 rounded-xl border border-border">
                    <div className="text-sm text-muted mb-2">MT Configs</div>
                    <div className="text-3xl font-bold text-fg">{stats.mt_configs}</div>
                  </div>
                  <div className="bg-card p-6 rounded-xl border border-border">
                    <div className="text-sm text-muted mb-2">Healthy Providers</div>
                    <div className="text-3xl font-bold text-green-500">{stats.healthy_providers}/{stats.total_providers}</div>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-[2fr_1fr] gap-8">
                {/* Languages List */}
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-6 border-b border-border">
                    <h2 className="m-0 text-xl">Configured Languages ({languages.length})</h2>
                  </div>
                  <div className="max-h-[600px] overflow-y-auto">
                    {languages.map((lang) => (
                      <div
                        key={lang.language}
                        onClick={() => fetchLanguageDetail(lang.language)}
                        className={`p-4 px-6 border-b border-bg-secondary cursor-pointer transition-colors
                                   ${selectedLanguage === lang.language ? 'bg-bg-secondary' : 'hover:bg-bg-secondary'}`}
                      >
                        <div className="flex justify-between items-center">
                          <div>
                            <div className="text-base font-semibold mb-1 text-fg">
                              {lang.language_name} <span className="text-muted text-sm">({lang.language})</span>
                            </div>
                            <div className="text-xs text-muted">
                              STT: {lang.stt_standard?.partial?.provider_primary || 'N/A'} • MT: {lang.mt_pairs} pairs
                            </div>
                          </div>
                          <div className={`px-3 py-1 rounded-md text-[0.75rem] font-semibold
                                         ${lang.status === 'active'
                                           ? 'bg-green-500/10 text-green-500'
                                           : 'bg-muted/10 text-muted'}`}>
                            {lang.status.toUpperCase()}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Provider Health */}
                <div className="bg-card rounded-xl border border-border">
                  <div className="p-6 border-b border-border">
                    <h2 className="m-0 text-xl">Provider Health</h2>
                  </div>
                  <div className="max-h-[600px] overflow-y-auto">
                    {providerHealth.map((provider, idx) => (
                      <div key={idx} className="p-4 px-6 border-b border-bg-secondary">
                        <div className="flex justify-between items-center mb-2">
                          <div>
                            <div className="text-[0.95rem] font-semibold text-fg">{provider.provider}</div>
                            <div className="text-xs text-muted uppercase">{provider.service_type}</div>
                          </div>
                          <div className={`px-3 py-1 rounded-md text-[0.7rem] font-semibold
                                         ${provider.status === 'healthy'
                                           ? 'bg-green-500/10 text-green-500'
                                           : provider.status === 'degraded'
                                           ? 'bg-amber-500/10 text-amber-500'
                                           : 'bg-red-600/10 text-red-600'}`}>
                            {provider.status.toUpperCase()}
                          </div>
                        </div>
                        {provider.consecutive_failures > 0 && (
                          <div className="text-xs text-red-600">
                            {provider.consecutive_failures} failures
                          </div>
                        )}
                        {provider.response_time_ms && (
                          <div className="text-xs text-muted">
                            {provider.response_time_ms}ms avg
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Language Detail */}
              {languageDetail && selectedLanguage && (
                <div className="mt-8 bg-card rounded-xl p-6 border border-border">
                  <div className="flex justify-between items-center mb-6">
                    <h2 className="m-0 text-xl text-fg">
                      {languages.find(l => l.language === selectedLanguage)?.language_name || selectedLanguage}
                    </h2>
                    <button
                      onClick={() => { setSelectedLanguage(null); setLanguageDetail(null); }}
                      className="bg-transparent border-none text-muted text-2xl cursor-pointer hover:text-fg transition-colors"
                    >
                      ×
                    </button>
                  </div>

                  {/* STT Configuration */}
                  <div className="mb-8">
                    <h3 className="text-lg mb-4 text-fg">STT Configuration</h3>
                    <div className="grid grid-cols-[repeat(auto-fit,minmax(300px,1fr))] gap-4">
                      {languageDetail.stt_configs.map((config, idx) => (
                        <div key={idx} className="bg-bg border border-border rounded-lg p-4">
                          <div className="flex justify-between mb-3">
                            <h4 className="m-0 text-[0.95rem] font-semibold text-fg">{config.mode} / {config.quality_tier}</h4>
                            <span className={`px-2 py-1 rounded text-[0.7rem] font-semibold
                                           ${config.enabled
                                             ? 'bg-green-500/10 text-green-500'
                                             : 'bg-muted/10 text-muted'}`}>
                              {config.enabled ? 'ACTIVE' : 'DISABLED'}
                            </span>
                          </div>
                          <div className="text-sm text-fg">
                            <div className="mb-2">
                              <span className="text-muted">Primary:</span> <span className="font-semibold">{config.provider_primary}</span>
                            </div>
                            <div>
                              <span className="text-muted">Fallback:</span> <span className="font-semibold">{config.provider_fallback}</span>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* MT Configuration */}
                  <div>
                    <h3 className="text-lg mb-4 text-fg">MT Configuration ({languageDetail.mt_configs.length} pairs)</h3>
                    <div className="max-h-[300px] overflow-y-auto bg-bg border border-border rounded-lg">
                      <table className="w-full text-sm">
                        <thead className="bg-card sticky top-0">
                          <tr>
                            <th className="p-3 text-left font-semibold text-muted">Direction</th>
                            <th className="p-3 text-left font-semibold text-muted">Tier</th>
                            <th className="p-3 text-left font-semibold text-muted">Primary</th>
                            <th className="p-3 text-left font-semibold text-muted">Fallback</th>
                          </tr>
                        </thead>
                        <tbody>
                          {languageDetail.mt_configs.slice(0, 20).map((config, idx) => (
                            <tr key={idx} className="border-b border-bg-secondary">
                              <td className="p-3 text-fg">{config.src_lang} → {config.tgt_lang}</td>
                              <td className="p-3 text-xs text-muted">{config.quality_tier}</td>
                              <td className="p-3 font-semibold text-fg">{config.provider_primary}</td>
                              <td className="p-3 text-muted">{config.provider_fallback}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {languageDetail.mt_configs.length > 20 && (
                        <div className="p-3 text-center text-sm text-muted">
                          ... and {languageDetail.mt_configs.length - 20} more pairs
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}
