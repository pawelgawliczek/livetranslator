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
    <div style={{
      minHeight: "100vh",
      background: "#0a0a0a",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif",
      display: "flex",
      flexDirection: "column"
    }}>
      <div style={{
        flex: 1,
        padding: "2rem 2rem 1rem 2rem"
      }}>
        <div style={{
          maxWidth: "1000px",
          margin: "0 auto"
        }}>
          {/* Header */}
          <div style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            marginBottom: "2rem"
          }}>
            <div>
              <h1 style={{fontSize: "2rem", marginBottom: "0.5rem"}}>🌍 Language Configuration</h1>
              <p style={{color: "#999", fontSize: "0.9rem"}}>Manage STT and MT provider settings for all languages</p>
            </div>
            <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
              <button
                onClick={() => navigate("/rooms")}
                style={{
                  padding: "0.75rem 1.5rem",
                  background: "#6366f1",
                  color: "white",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontWeight: "600"
                }}
              >
                ← {t("back_to_rooms") || "Rooms"}
              </button>
              <button
                onClick={onLogout}
                style={{
                  padding: "0.75rem 1.5rem",
                  background: "#dc2626",
                  color: "white",
                  border: "none",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontWeight: "600"
                }}
              >
                {t("logout") || "Logout"}
              </button>
            </div>
          </div>

        <div style={{ marginBottom: "2rem" }}>
        {/* Error Messages */}
        {error && (
          <div style={{
            background: "#1a1a1a",
            border: "1px solid #dc2626",
            color: "#dc2626",
            padding: "12px",
            borderRadius: "8px",
            marginBottom: "20px"
          }}>
            {error}
          </div>
        )}

        {/* Languages Content */}
        <div>
            {/* Stats Overview */}
            {stats && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: "1rem", marginBottom: "2rem" }}>
                <div style={{ background: "#1a1a1a", padding: "1.5rem", borderRadius: "12px", border: "1px solid #333" }}>
                  <div style={{ fontSize: "0.85rem", color: "#999", marginBottom: "0.5rem" }}>Languages</div>
                  <div style={{ fontSize: "2rem", fontWeight: "bold" }}>{stats.languages_configured}</div>
                </div>
                <div style={{ background: "#1a1a1a", padding: "1.5rem", borderRadius: "12px", border: "1px solid #333" }}>
                  <div style={{ fontSize: "0.85rem", color: "#999", marginBottom: "0.5rem" }}>STT Configs</div>
                  <div style={{ fontSize: "2rem", fontWeight: "bold" }}>{stats.stt_configs}</div>
                </div>
                <div style={{ background: "#1a1a1a", padding: "1.5rem", borderRadius: "12px", border: "1px solid #333" }}>
                  <div style={{ fontSize: "0.85rem", color: "#999", marginBottom: "0.5rem" }}>MT Configs</div>
                  <div style={{ fontSize: "2rem", fontWeight: "bold" }}>{stats.mt_configs}</div>
                </div>
                <div style={{ background: "#1a1a1a", padding: "1.5rem", borderRadius: "12px", border: "1px solid #333" }}>
                  <div style={{ fontSize: "0.85rem", color: "#999", marginBottom: "0.5rem" }}>Healthy Providers</div>
                  <div style={{ fontSize: "2rem", fontWeight: "bold", color: "#10b981" }}>{stats.healthy_providers}/{stats.total_providers}</div>
                </div>
              </div>
            )}

            <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "2rem" }}>
              {/* Languages List */}
              <div style={{ background: "#1a1a1a", borderRadius: "12px", border: "1px solid #333" }}>
                <div style={{ padding: "1.5rem", borderBottom: "1px solid #333" }}>
                  <h2 style={{ margin: 0, fontSize: "1.25rem" }}>Configured Languages ({languages.length})</h2>
                </div>
                <div style={{ maxHeight: "600px", overflowY: "auto" }}>
                  {languages.map((lang) => (
                    <div
                      key={lang.language}
                      onClick={() => fetchLanguageDetail(lang.language)}
                      style={{
                        padding: "1rem 1.5rem",
                        borderBottom: "1px solid #2a2a2a",
                        cursor: "pointer",
                        background: selectedLanguage === lang.language ? "#2a2a2a" : "transparent",
                        transition: "background 0.2s"
                      }}
                      onMouseEnter={(e) => e.currentTarget.style.background = "#2a2a2a"}
                      onMouseLeave={(e) => e.currentTarget.style.background = selectedLanguage === lang.language ? "#2a2a2a" : "transparent"}
                    >
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                        <div>
                          <div style={{ fontSize: "1rem", fontWeight: "600", marginBottom: "0.25rem" }}>
                            {lang.language_name} <span style={{ color: "#666", fontSize: "0.85rem" }}>({lang.language})</span>
                          </div>
                          <div style={{ fontSize: "0.8rem", color: "#999" }}>
                            STT: {lang.stt_standard?.partial?.provider_primary || 'N/A'} • MT: {lang.mt_pairs} pairs
                          </div>
                        </div>
                        <div style={{ padding: "0.25rem 0.75rem", borderRadius: "6px", fontSize: "0.75rem", fontWeight: "600", background: lang.status === 'active' ? "#10b98122" : "#66666622", color: lang.status === 'active' ? "#10b981" : "#666" }}>
                          {lang.status.toUpperCase()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Provider Health */}
              <div style={{ background: "#1a1a1a", borderRadius: "12px", border: "1px solid #333" }}>
                <div style={{ padding: "1.5rem", borderBottom: "1px solid #333" }}>
                  <h2 style={{ margin: 0, fontSize: "1.25rem" }}>Provider Health</h2>
                </div>
                <div style={{ maxHeight: "600px", overflowY: "auto" }}>
                  {providerHealth.map((provider, idx) => (
                    <div key={idx} style={{ padding: "1rem 1.5rem", borderBottom: "1px solid #2a2a2a" }}>
                      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem" }}>
                        <div>
                          <div style={{ fontSize: "0.95rem", fontWeight: "600" }}>{provider.provider}</div>
                          <div style={{ fontSize: "0.75rem", color: "#666", textTransform: "uppercase" }}>{provider.service_type}</div>
                        </div>
                        <div style={{ padding: "0.25rem 0.75rem", borderRadius: "6px", fontSize: "0.7rem", fontWeight: "600", background: provider.status === 'healthy' ? "#10b98122" : provider.status === 'degraded' ? "#f59e0b22" : "#dc262622", color: provider.status === 'healthy' ? "#10b981" : provider.status === 'degraded' ? "#f59e0b" : "#dc2626" }}>
                          {provider.status.toUpperCase()}
                        </div>
                      </div>
                      {provider.consecutive_failures > 0 && (
                        <div style={{ fontSize: "0.75rem", color: "#dc2626" }}>
                          {provider.consecutive_failures} failures
                        </div>
                      )}
                      {provider.response_time_ms && (
                        <div style={{ fontSize: "0.75rem", color: "#666" }}>
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
              <div style={{ marginTop: "2rem", background: "#1a1a1a", borderRadius: "12px", padding: "1.5rem", border: "1px solid #333" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1.5rem" }}>
                  <h2 style={{ margin: 0, fontSize: "1.25rem" }}>
                    {languages.find(l => l.language === selectedLanguage)?.language_name || selectedLanguage}
                  </h2>
                  <button
                    onClick={() => { setSelectedLanguage(null); setLanguageDetail(null); }}
                    style={{ background: "transparent", border: "none", color: "#666", fontSize: "1.5rem", cursor: "pointer" }}
                  >
                    ×
                  </button>
                </div>

                {/* STT Configuration */}
                <div style={{ marginBottom: "2rem" }}>
                  <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>STT Configuration</h3>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))", gap: "1rem" }}>
                    {languageDetail.stt_configs.map((config, idx) => (
                      <div key={idx} style={{ background: "#0a0a0a", border: "1px solid #333", borderRadius: "8px", padding: "1rem" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                          <h4 style={{ margin: 0, fontSize: "0.95rem", fontWeight: "600" }}>{config.mode} / {config.quality_tier}</h4>
                          <span style={{ padding: "0.25rem 0.5rem", borderRadius: "4px", fontSize: "0.7rem", fontWeight: "600", background: config.enabled ? "#10b98122" : "#66666622", color: config.enabled ? "#10b981" : "#666" }}>
                            {config.enabled ? 'ACTIVE' : 'DISABLED'}
                          </span>
                        </div>
                        <div style={{ fontSize: "0.85rem" }}>
                          <div style={{ marginBottom: "0.5rem" }}>
                            <span style={{ color: "#999" }}>Primary:</span> <span style={{ fontWeight: "600" }}>{config.provider_primary}</span>
                          </div>
                          <div>
                            <span style={{ color: "#999" }}>Fallback:</span> <span style={{ fontWeight: "600" }}>{config.provider_fallback}</span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* MT Configuration */}
                <div>
                  <h3 style={{ fontSize: "1.1rem", marginBottom: "1rem" }}>MT Configuration ({languageDetail.mt_configs.length} pairs)</h3>
                  <div style={{ maxHeight: "300px", overflowY: "auto", background: "#0a0a0a", border: "1px solid #333", borderRadius: "8px" }}>
                    <table style={{ width: "100%", fontSize: "0.85rem" }}>
                      <thead style={{ background: "#1a1a1a", position: "sticky", top: 0 }}>
                        <tr>
                          <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "600", color: "#999" }}>Direction</th>
                          <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "600", color: "#999" }}>Tier</th>
                          <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "600", color: "#999" }}>Primary</th>
                          <th style={{ padding: "0.75rem", textAlign: "left", fontWeight: "600", color: "#999" }}>Fallback</th>
                        </tr>
                      </thead>
                      <tbody>
                        {languageDetail.mt_configs.slice(0, 20).map((config, idx) => (
                          <tr key={idx} style={{ borderBottom: "1px solid #2a2a2a" }}>
                            <td style={{ padding: "0.75rem" }}>{config.src_lang} → {config.tgt_lang}</td>
                            <td style={{ padding: "0.75rem", fontSize: "0.75rem", color: "#999" }}>{config.quality_tier}</td>
                            <td style={{ padding: "0.75rem", fontWeight: "600" }}>{config.provider_primary}</td>
                            <td style={{ padding: "0.75rem", color: "#999" }}>{config.provider_fallback}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {languageDetail.mt_configs.length > 20 && (
                      <div style={{ padding: "0.75rem", textAlign: "center", fontSize: "0.85rem", color: "#666" }}>
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
