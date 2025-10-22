import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";

export default function AdminSettingsPage({ token, onLogout }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState("stt");
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  // STT Settings state
  const [providers, setProviders] = useState(null);
  const [currentSettings, setCurrentSettings] = useState(null);
  const [sttPartialProvider, setSttPartialProvider] = useState("");
  const [sttFinalProvider, setSttFinalProvider] = useState("");

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

      // Fetch providers
      const providersRes = await fetch("/api/admin/providers", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (providersRes.ok) {
        const providersData = await providersRes.json();
        setProviders(providersData);
      }

      // Fetch current settings
      const settingsRes = await fetch("/api/admin/settings/stt", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (settingsRes.ok) {
        const settingsData = await settingsRes.json();
        setCurrentSettings(settingsData);

        // Set initial form values
        const settingsMap = settingsData.settings.reduce((acc, s) => {
          acc[s.key] = s.value;
          return acc;
        }, {});
        setSttPartialProvider(settingsMap["stt_partial_provider_default"] || "");
        setSttFinalProvider(settingsMap["stt_final_provider_default"] || "");
      }
    } catch (e) {
      console.error("Failed to fetch admin data:", e);
      setError("Failed to load admin data");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpdateSTTSettings(e) {
    e.preventDefault();
    setMessage("");
    setError("");

    try {
      const res = await fetch("/api/admin/settings/stt", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          stt_partial_provider_default: sttPartialProvider,
          stt_final_provider_default: sttFinalProvider
        })
      });

      if (res.ok) {
        const data = await res.json();
        setMessage(data.message);
        fetchAdminData(); // Refresh data
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to update settings");
      }
    } catch (e) {
      console.error("Failed to update STT settings:", e);
      setError("Failed to update settings");
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
              <h1 style={{fontSize: "2rem", marginBottom: "0.5rem"}}>🛠️ Admin Settings</h1>
              <p style={{color: "#999", fontSize: "0.9rem"}}>Configure STT/MT providers and system defaults</p>
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
        {/* Tabs */}
        <div style={{ display: "flex", gap: "10px", borderBottom: "2px solid #333", marginBottom: "20px" }}>
          <button
            onClick={() => setActiveTab("stt")}
            style={{
              background: activeTab === "stt" ? "#6366f1" : "transparent",
              color: "white",
              border: "none",
              padding: "10px 20px",
              borderRadius: "8px 8px 0 0",
              cursor: "pointer",
              fontSize: "16px",
              fontWeight: activeTab === "stt" ? "600" : "normal",
              opacity: activeTab === "stt" ? "1" : "0.6"
            }}
          >
            STT Settings
          </button>
          <button
            onClick={() => setActiveTab("mt")}
            style={{
              background: activeTab === "mt" ? "#6366f1" : "transparent",
              color: "white",
              border: "none",
              padding: "10px 20px",
              borderRadius: "8px 8px 0 0",
              cursor: "pointer",
              fontSize: "16px",
              fontWeight: activeTab === "mt" ? "600" : "normal",
              opacity: activeTab === "mt" ? "1" : "0.6"
            }}
          >
            MT Settings
          </button>
        </div>

        {/* Messages */}
        {message && (
          <div style={{
            background: "#1a1a1a",
            border: "1px solid #10b981",
            color: "#10b981",
            padding: "12px",
            borderRadius: "8px",
            marginBottom: "20px"
          }}>
            {message}
          </div>
        )}

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

        {/* STT Settings Tab */}
        {activeTab === "stt" && providers && (
          <div style={{
            background: "#1a1a1a",
            borderRadius: "12px",
            padding: "1.5rem",
            border: "1px solid #333"
          }}>
            <h2 style={{ fontSize: "1.25rem", marginBottom: "1.5rem" }}>Speech-to-Text Provider Settings</h2>

            <form onSubmit={handleUpdateSTTSettings}>
              {/* Partial Provider */}
              <div style={{ marginBottom: "24px" }}>
                <label style={{ display: "block", fontWeight: "600", marginBottom: "8px", color: "#ddd" }}>
                  Partial Transcription Provider (Real-time)
                </label>
                <select
                  value={sttPartialProvider}
                  onChange={(e) => setSttPartialProvider(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px",
                    background: "#0a0a0a",
                    color: "white",
                    border: "1px solid #333",
                    borderRadius: "8px",
                    fontSize: "14px"
                  }}
                >
                  {providers.stt_partial.map((p) => (
                    <option key={p.id} value={p.id} style={{background: "#0a0a0a"}}>
                      {p.name} - {p.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Final Provider */}
              <div style={{ marginBottom: "24px" }}>
                <label style={{ display: "block", fontWeight: "600", marginBottom: "8px", color: "#ddd" }}>
                  Final Transcription Provider (High Quality)
                </label>
                <select
                  value={sttFinalProvider}
                  onChange={(e) => setSttFinalProvider(e.target.value)}
                  style={{
                    width: "100%",
                    padding: "10px",
                    background: "#0a0a0a",
                    color: "white",
                    border: "1px solid #333",
                    borderRadius: "8px",
                    fontSize: "14px"
                  }}
                >
                  {providers.stt_final.map((p) => (
                    <option key={p.id} value={p.id} style={{background: "#0a0a0a"}}>
                      {p.name} - {p.description}
                    </option>
                  ))}
                </select>
              </div>

              <button
                type="submit"
                style={{
                  background: "#6366f1",
                  color: "white",
                  border: "none",
                  padding: "0.75rem 1.5rem",
                  borderRadius: "8px",
                  cursor: "pointer",
                  fontSize: "16px",
                  fontWeight: "600"
                }}
              >
                Save STT Settings
              </button>
            </form>

            {/* Current Settings Info */}
            {currentSettings && (
              <div style={{
                marginTop: "40px",
                padding: "20px",
                background: "#0a0a0a",
                borderRadius: "8px",
                border: "1px solid #333"
              }}>
                <h3 style={{ fontSize: "16px", marginBottom: "12px", color: "#ddd" }}>Current Settings</h3>
                {currentSettings.settings.map((s) => (
                  <div key={s.key} style={{ marginBottom: "8px", fontSize: "14px" }}>
                    <strong style={{color: "#10b981"}}>{s.key}:</strong> <span style={{color: "#ddd"}}>{s.value}</span>
                    <br />
                    <span style={{ color: "#666", fontSize: "12px" }}>
                      Updated: {new Date(s.updated_at).toLocaleString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* MT Settings Tab */}
        {activeTab === "mt" && providers && (
          <div style={{
            background: "#1a1a1a",
            borderRadius: "12px",
            padding: "1.5rem",
            border: "1px solid #333"
          }}>
            <h2 style={{ fontSize: "1.25rem", marginBottom: "1.5rem" }}>Machine Translation Provider Settings</h2>

            <div style={{
              padding: "20px",
              background: "#0a0a0a",
              border: "1px solid #f59e0b",
              borderRadius: "8px",
              marginBottom: "20px"
            }}>
              <p style={{ margin: 0, color: "#ddd" }}>
                <strong style={{color: "#f59e0b"}}>Available MT Providers:</strong>
              </p>
              {providers.mt.map((p) => (
                <div key={p.id} style={{ marginTop: "10px", color: "#ddd" }}>
                  <strong style={{color: "#10b981"}}>{p.name}</strong> - {p.description}
                </div>
              ))}
            </div>

            <p style={{ color: "#666", fontSize: "14px" }}>
              MT provider selection coming in future phases. Currently using OpenAI GPT-4o-mini for all translations.
            </p>
          </div>
        )}
        </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}
