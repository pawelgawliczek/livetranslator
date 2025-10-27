import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";

export default function ParticipantsModal({ roomCode, token, isOpen, onClose }) {
  const { t } = useTranslation();
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isOpen || !roomCode) return;

    fetchParticipants();
    // Refresh participants every 5 seconds while modal is open
    const interval = setInterval(fetchParticipants, 5000);

    return () => clearInterval(interval);
  }, [isOpen, roomCode]);

  async function fetchParticipants() {
    try {
      setLoading(true);
      const headers = token ? { "Authorization": `Bearer ${token}` } : {};
      const guestToken = sessionStorage.getItem('guest_token');
      if (guestToken && !token) {
        headers["Authorization"] = `Bearer ${guestToken}`;
      }

      const response = await fetch(`/api/rooms/${roomCode}/participants`, {
        headers
      });

      if (!response.ok) {
        throw new Error("Failed to fetch participants");
      }

      const data = await response.json();
      setParticipants(data.participants || []);
    } catch (e) {
      console.error("Failed to fetch participants:", e);
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <h2 style={styles.title}>👥 {t('participants.connectedTitle')}</h2>
          <button style={styles.closeButton} onClick={onClose}>×</button>
        </div>

        <div style={styles.content}>
          {loading && participants.length === 0 ? (
            <div style={styles.loadingContainer}>
              <div style={styles.spinner}></div>
              <p style={styles.loadingText}>{t('participants.loadingParticipants')}</p>
            </div>
          ) : participants.length === 0 ? (
            <div style={styles.emptyState}>
              <p style={styles.emptyText}>{t('participants.emptyState')}</p>
            </div>
          ) : (
            <div style={styles.participantList}>
              {participants.map((participant, index) => (
                <div key={index} style={styles.participantCard}>
                  <div style={styles.participantInfo}>
                    <div style={styles.participantName}>
                      {participant.is_guest && <span style={styles.guestBadge}>{t('participants.guestLabel')}</span>}
                      {participant.display_name || participant.email}
                    </div>
                    <div style={styles.participantMeta}>
                      <span style={styles.languageInfo}>
                        🗣️ {getLanguageName(participant.preferred_lang || "en")}
                      </span>
                    </div>
                  </div>
                  <div style={styles.statusIndicator}>
                    {participant.is_speaking ? (
                      <span style={styles.speakingBadge}>🎤 {t('participants.speaking')}</span>
                    ) : (
                      <span style={styles.connectedBadge}>✓ {t('participants.connected')}</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={styles.footer}>
          <p style={styles.footerText}>
            {participants.length} participant{participants.length !== 1 ? 's' : ''} connected
          </p>
        </div>
      </div>
    </div>
  );
}

function getLanguageName(code) {
  const languages = {
    "auto": "Auto",
    "en": "English",
    "pl": "Polish",
    "ar": "Arabic",
    "es": "Spanish",
    "fr": "French",
    "de": "German"
  };
  // Normalize language code to base language (e.g., "en-GB" -> "en")
  const baseLang = code?.split('-')[0] || code;
  return languages[baseLang] || code.toUpperCase();
}

const styles = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: "rgba(0, 0, 0, 0.8)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    padding: "1rem"
  },
  modal: {
    background: "#1a1a1a",
    borderRadius: "16px",
    border: "1px solid #333",
    maxWidth: "600px",
    width: "100%",
    maxHeight: "80vh",
    display: "flex",
    flexDirection: "column",
    boxShadow: "0 20px 60px rgba(0,0,0,0.5)"
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "1.5rem",
    borderBottom: "1px solid #333"
  },
  title: {
    margin: 0,
    fontSize: "1.5rem",
    fontWeight: "700",
    color: "white"
  },
  closeButton: {
    background: "none",
    border: "none",
    color: "#999",
    fontSize: "2rem",
    cursor: "pointer",
    padding: "0",
    width: "40px",
    height: "40px",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    borderRadius: "8px",
    transition: "all 0.2s"
  },
  content: {
    flex: 1,
    overflow: "auto",
    padding: "1.5rem"
  },
  loadingContainer: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "1rem",
    padding: "3rem 1rem"
  },
  spinner: {
    width: "50px",
    height: "50px",
    border: "4px solid #333",
    borderTop: "4px solid #3b82f6",
    borderRadius: "50%",
    animation: "spin 1s linear infinite"
  },
  loadingText: {
    color: "#999",
    margin: 0
  },
  emptyState: {
    textAlign: "center",
    padding: "3rem 1rem"
  },
  emptyText: {
    color: "#666",
    fontSize: "1rem",
    margin: 0
  },
  participantList: {
    display: "flex",
    flexDirection: "column",
    gap: "0.75rem"
  },
  participantCard: {
    background: "#2a2a2a",
    border: "1px solid #444",
    borderRadius: "12px",
    padding: "1rem",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    transition: "all 0.2s"
  },
  participantInfo: {
    flex: 1
  },
  participantName: {
    color: "white",
    fontSize: "1rem",
    fontWeight: "600",
    marginBottom: "0.5rem",
    display: "flex",
    alignItems: "center",
    gap: "0.5rem"
  },
  guestBadge: {
    background: "#3b82f6",
    color: "white",
    fontSize: "0.65rem",
    fontWeight: "700",
    padding: "0.25rem 0.5rem",
    borderRadius: "4px",
    textTransform: "uppercase"
  },
  participantMeta: {
    display: "flex",
    flexDirection: "column",
    gap: "0.25rem"
  },
  languageInfo: {
    color: "#999",
    fontSize: "0.85rem"
  },
  statusIndicator: {
    display: "flex",
    alignItems: "center",
    gap: "0.5rem"
  },
  speakingBadge: {
    background: "#10b981",
    color: "white",
    fontSize: "0.75rem",
    fontWeight: "600",
    padding: "0.375rem 0.75rem",
    borderRadius: "6px",
    animation: "pulse 2s infinite"
  },
  connectedBadge: {
    color: "#10b981",
    fontSize: "0.85rem",
    fontWeight: "600"
  },
  footer: {
    padding: "1rem 1.5rem",
    borderTop: "1px solid #333",
    background: "#141414"
  },
  footerText: {
    margin: 0,
    color: "#666",
    fontSize: "0.85rem",
    textAlign: "center"
  }
};
