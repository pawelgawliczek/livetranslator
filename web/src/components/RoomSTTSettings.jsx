import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";

export default function RoomSTTSettings({ token, roomCode, isOwner, isAdmin, isOpen, onClose }) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [providers, setProviders] = useState(null);
  const [currentSettings, setCurrentSettings] = useState(null);
  const [sttPartialProvider, setSttPartialProvider] = useState("");
  const [sttFinalProvider, setSttFinalProvider] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (isOpen) {
      fetchSettings();
      fetchProviders();
    }
  }, [isOpen]);

  async function fetchProviders() {
    try {
      const res = await fetch("/api/admin/providers", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setProviders(data);
      }
    } catch (e) {
      console.error("Failed to fetch providers:", e);
    }
  }

  async function fetchSettings() {
    setLoading(true);
    try {
      const res = await fetch(`/api/rooms/${roomCode}/stt-settings`, {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setCurrentSettings(data);
        setSttPartialProvider(data.stt_partial_provider || "");
        setSttFinalProvider(data.stt_final_provider || "");
      }
    } catch (e) {
      console.error("Failed to fetch room STT settings:", e);
      setError("Failed to load settings");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpdateSettings(e) {
    e.preventDefault();
    setMessage("");
    setError("");

    try {
      const res = await fetch(`/api/rooms/${roomCode}/stt-settings`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          stt_partial_provider: sttPartialProvider || null,
          stt_final_provider: sttFinalProvider || null
        })
      });

      if (res.ok) {
        const data = await res.json();
        setCurrentSettings(data);
        setMessage("STT settings updated successfully!");
        setTimeout(() => setMessage(""), 3000);
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to update settings");
      }
    } catch (e) {
      console.error("Failed to update STT settings:", e);
      setError("Failed to update settings");
    }
  }

  async function handleResetToDefaults() {
    setMessage("");
    setError("");

    try {
      const res = await fetch(`/api/rooms/${roomCode}/stt-settings`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({
          stt_partial_provider: null,
          stt_final_provider: null
        })
      });

      if (res.ok) {
        const data = await res.json();
        setCurrentSettings(data);
        setSttPartialProvider("");
        setSttFinalProvider("");
        setMessage("Reset to global defaults");
        setTimeout(() => setMessage(""), 3000);
      } else {
        const errData = await res.json();
        setError(errData.detail || "Failed to reset settings");
      }
    } catch (e) {
      console.error("Failed to reset STT settings:", e);
      setError("Failed to reset settings");
    }
  }

  // Only show if user is owner or admin
  if (!isOwner && !isAdmin) {
    return null;
  }

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0,0,0,0.85)",
        zIndex: 1100,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem"
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#1a1a1a",
          border: "1px solid #333",
          borderRadius: "12px",
          padding: "20px",
          minWidth: "400px",
          maxWidth: "500px",
          boxShadow: "0 8px 16px rgba(0,0,0,0.5)",
          maxHeight: "90vh",
          overflowY: "auto"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "16px"
        }}>
          <h3 style={{ margin: 0, color: "#ddd", fontSize: "18px" }}>
            ⚙️ Room Admin Settings
          </h3>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#999",
              fontSize: "24px",
              cursor: "pointer",
              padding: "0",
              lineHeight: "1"
            }}
          >
            ×
          </button>
        </div>

          {loading ? (
            <p style={{ color: "#999" }}>Loading...</p>
          ) : (
            <>
              {message && (
                <div style={{
                  background: "#0a0a0a",
                  border: "1px solid #10b981",
                  color: "#10b981",
                  padding: "10px",
                  borderRadius: "6px",
                  marginBottom: "16px",
                  fontSize: "14px"
                }}>
                  {message}
                </div>
              )}

              {error && (
                <div style={{
                  background: "#0a0a0a",
                  border: "1px solid #dc2626",
                  color: "#dc2626",
                  padding: "10px",
                  borderRadius: "6px",
                  marginBottom: "16px",
                  fontSize: "14px"
                }}>
                  {error}
                </div>
              )}

              {currentSettings?.is_using_defaults && (
                <div style={{
                  background: "#0a0a0a",
                  border: "1px solid #6366f1",
                  color: "#6366f1",
                  padding: "10px",
                  borderRadius: "6px",
                  marginBottom: "16px",
                  fontSize: "12px"
                }}>
                  ℹ️ Currently using global default settings
                </div>
              )}

              {providers && (
                <form onSubmit={handleUpdateSettings}>
                  <div style={{ marginBottom: "16px" }}>
                    <label style={{
                      display: "block",
                      color: "#ddd",
                      marginBottom: "6px",
                      fontSize: "14px",
                      fontWeight: "600"
                    }}>
                      Partial Provider (Real-time)
                    </label>
                    <select
                      value={sttPartialProvider}
                      onChange={(e) => setSttPartialProvider(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "8px",
                        background: "#0a0a0a",
                        color: "white",
                        border: "1px solid #333",
                        borderRadius: "6px",
                        fontSize: "14px"
                      }}
                    >
                      <option value="" style={{background: "#0a0a0a"}}>Use global default</option>
                      {providers.stt_partial.map((p) => (
                        <option key={p.id} value={p.id} style={{background: "#0a0a0a"}}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div style={{ marginBottom: "20px" }}>
                    <label style={{
                      display: "block",
                      color: "#ddd",
                      marginBottom: "6px",
                      fontSize: "14px",
                      fontWeight: "600"
                    }}>
                      Final Provider (High Quality)
                    </label>
                    <select
                      value={sttFinalProvider}
                      onChange={(e) => setSttFinalProvider(e.target.value)}
                      style={{
                        width: "100%",
                        padding: "8px",
                        background: "#0a0a0a",
                        color: "white",
                        border: "1px solid #333",
                        borderRadius: "6px",
                        fontSize: "14px"
                      }}
                    >
                      <option value="" style={{background: "#0a0a0a"}}>Use global default</option>
                      {providers.stt_final.map((p) => (
                        <option key={p.id} value={p.id} style={{background: "#0a0a0a"}}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div style={{ display: "flex", gap: "10px" }}>
                    <button
                      type="submit"
                      style={{
                        flex: 1,
                        padding: "10px",
                        background: "#6366f1",
                        color: "white",
                        border: "none",
                        borderRadius: "6px",
                        cursor: "pointer",
                        fontWeight: "600",
                        fontSize: "14px"
                      }}
                    >
                      Save
                    </button>
                    <button
                      type="button"
                      onClick={handleResetToDefaults}
                      style={{
                        flex: 1,
                        padding: "10px",
                        background: "#333",
                        color: "white",
                        border: "none",
                        borderRadius: "6px",
                        cursor: "pointer",
                        fontWeight: "600",
                        fontSize: "14px"
                      }}
                    >
                      Reset to Defaults
                    </button>
                  </div>
                </form>
              )}
            </>
          )}
      </div>
    </div>
  );
}
