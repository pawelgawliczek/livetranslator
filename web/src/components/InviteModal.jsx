import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";

export default function InviteModal({ roomCode, onClose }) {
  const { t } = useTranslation();
  const [inviteData, setInviteData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(false);
  const [shareMethod, setShareMethod] = useState("qr"); // qr, link, email

  useEffect(() => {
    fetchInvite();
  }, [roomCode]);

  async function fetchInvite() {
    try {
      setLoading(true);
      const response = await fetch(`/api/invites/generate/${roomCode}`, {
        method: "POST"
      });

      if (!response.ok) {
        throw new Error("Failed to generate invite");
      }

      const data = await response.json();
      setInviteData(data);
    } catch (e) {
      console.error("Failed to fetch invite:", e);
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function copyLink() {
    if (!inviteData) return;
    navigator.clipboard.writeText(inviteData.invite_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  function shareViaEmail() {
    if (!inviteData) return;
    const subject = encodeURIComponent(t('invite.emailSubject'));
    const body = encodeURIComponent(
      `${t('invite.emailBodyGreeting')}\n\n` +
      `${t('invite.emailBodyLink')} ${inviteData.invite_url}\n\n` +
      t('invite.emailBodyExpiry', { minutes: inviteData.expires_in_minutes })
    );
    window.location.href = `mailto:?subject=${subject}&body=${body}`;
  }

  function downloadQR() {
    if (!inviteData) return;
    const link = document.createElement("a");
    link.href = inviteData.qr_code;
    link.download = `livetranslator-${roomCode}-qr.png`;
    link.click();
  }

  if (loading) {
    return (
      <div style={styles.overlay} onClick={onClose}>
        <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
          <div style={styles.modalHeader}>
            <h2 style={styles.modalTitle}>{t('invite.generatingInvite')}</h2>
            <button style={styles.closeButton} onClick={onClose}>✕</button>
          </div>
          <div style={styles.modalBody}>
            <div style={styles.loadingSpinner}>
              <div style={styles.spinner}></div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.overlay} onClick={onClose}>
        <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
          <div style={styles.modalHeader}>
            <h2 style={styles.modalTitle}>{t('invite.error')}</h2>
            <button style={styles.closeButton} onClick={onClose}>✕</button>
          </div>
          <div style={styles.modalBody}>
            <p style={{color: "#ef4444", textAlign: "center"}}>
              {error}
            </p>
            <button style={styles.primaryButton} onClick={onClose}>
              {t('common.close')}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <h2 style={styles.modalTitle}>{t('invite.title')}</h2>
          <button style={styles.closeButton} onClick={onClose}>✕</button>
        </div>

        <div style={styles.modalBody}>
          {/* Share method tabs */}
          <div style={styles.tabs}>
            <button
              style={{
                ...styles.tab,
                ...(shareMethod === "qr" ? styles.tabActive : {})
              }}
              onClick={() => setShareMethod("qr")}
            >
              {t('invite.qrCodeTab')}
            </button>
            <button
              style={{
                ...styles.tab,
                ...(shareMethod === "link" ? styles.tabActive : {})
              }}
              onClick={() => setShareMethod("link")}
            >
              {t('invite.linkTab')}
            </button>
            <button
              style={{
                ...styles.tab,
                ...(shareMethod === "email" ? styles.tabActive : {})
              }}
              onClick={() => setShareMethod("email")}
            >
              {t('invite.emailTab')}
            </button>
          </div>

          {/* QR Code view */}
          {shareMethod === "qr" && inviteData && (
            <div style={styles.contentSection}>
              <p style={styles.instructionText}>
                {t('invite.qrInstructions')}
              </p>
              <div style={styles.qrContainer}>
                <img
                  src={inviteData.qr_code}
                  alt="QR Code"
                  style={styles.qrCode}
                />
              </div>
              <button style={styles.secondaryButton} onClick={downloadQR}>
                {t('invite.downloadQR')}
              </button>
            </div>
          )}

          {/* Link view */}
          {shareMethod === "link" && inviteData && (
            <div style={styles.contentSection}>
              <p style={styles.instructionText}>
                {t('invite.linkInstructions')}
              </p>
              <div style={styles.linkContainer}>
                <input
                  type="text"
                  readOnly
                  value={inviteData.invite_url}
                  style={styles.linkInput}
                  onClick={(e) => e.target.select()}
                />
              </div>
              <button
                style={styles.primaryButton}
                onClick={copyLink}
              >
                {copied ? "✓ Copied!" : t('rooms.copyCode')}
              </button>
            </div>
          )}

          {/* Email view */}
          {shareMethod === "email" && inviteData && (
            <div style={styles.contentSection}>
              <p style={styles.instructionText}>
                {t('invite.emailInstructions')}
              </p>
              <div style={styles.emailPreview}>
                <div style={styles.emailLabel}>{t('invite.preview')}</div>
                <div style={styles.emailBody}>
                  <p><strong>{t('invite.emailBodyGreeting')}</strong></p>
                  <p>{t('invite.emailBodyLink')} <br/>
                    <code style={styles.inlineCode}>{inviteData.invite_url}</code>
                  </p>
                  <p style={{fontSize: "0.85rem", color: "#999"}}>
                    {t('invite.emailBodyExpiry', { minutes: inviteData.expires_in_minutes })}
                  </p>
                </div>
              </div>
              <button style={styles.primaryButton} onClick={shareViaEmail}>
                {t('invite.openEmail')}
              </button>
            </div>
          )}

          {/* Room info */}
          <div style={styles.roomInfo}>
            <div style={styles.roomInfoRow}>
              <span style={styles.infoLabel}>{t('invite.roomLabel')}</span>
              <code style={styles.infoValue}>{roomCode}</code>
            </div>
            <div style={styles.roomInfoRow}>
              <span style={styles.infoLabel}>{t('invite.expiresLabel')}</span>
              <span style={styles.infoValue}>
                {t('invite.expiresInMinutes', { minutes: inviteData?.expires_in_minutes || 30 })}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
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
    maxWidth: "550px",
    width: "100%",
    maxHeight: "90vh",
    overflow: "auto",
    boxShadow: "0 20px 60px rgba(0,0,0,0.5)"
  },
  modalHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "1.5rem",
    borderBottom: "1px solid #333"
  },
  modalTitle: {
    fontSize: "clamp(1.25rem, 4vw, 1.5rem)",
    margin: 0,
    color: "white"
  },
  closeButton: {
    background: "none",
    border: "none",
    color: "#999",
    fontSize: "1.5rem",
    cursor: "pointer",
    padding: "0.25rem",
    lineHeight: 1,
    transition: "color 0.2s"
  },
  modalBody: {
    padding: "1.5rem"
  },
  tabs: {
    display: "flex",
    gap: "0.5rem",
    marginBottom: "1.5rem",
    borderBottom: "1px solid #333",
    paddingBottom: "0.5rem",
    flexWrap: "wrap"
  },
  tab: {
    flex: "1 1 90px",
    minWidth: "90px",
    padding: "0.75rem 0.5rem",
    background: "transparent",
    color: "#999",
    border: "none",
    borderRadius: "8px 8px 0 0",
    cursor: "pointer",
    fontSize: "0.875rem",
    fontWeight: "500",
    transition: "all 0.2s",
    textAlign: "center"
  },
  tabActive: {
    background: "#2a2a2a",
    color: "#3b82f6",
    borderBottom: "2px solid #3b82f6"
  },
  contentSection: {
    minHeight: "300px"
  },
  instructionText: {
    color: "#ccc",
    fontSize: "0.95rem",
    lineHeight: "1.5",
    marginBottom: "1.5rem",
    textAlign: "center"
  },
  qrContainer: {
    display: "flex",
    justifyContent: "center",
    marginBottom: "1.5rem"
  },
  qrCode: {
    width: "min(280px, 70vw)",
    height: "min(280px, 70vw)",
    borderRadius: "12px",
    border: "2px solid #333",
    background: "white",
    padding: "0.75rem"
  },
  linkContainer: {
    marginBottom: "1.5rem"
  },
  linkInput: {
    width: "100%",
    padding: "0.875rem",
    background: "#2a2a2a",
    border: "1px solid #444",
    borderRadius: "8px",
    color: "#3b82f6",
    fontSize: "0.9rem",
    fontFamily: "monospace",
    boxSizing: "border-box"
  },
  emailPreview: {
    background: "#2a2a2a",
    borderRadius: "8px",
    padding: "1rem",
    marginBottom: "1.5rem",
    border: "1px solid #444"
  },
  emailLabel: {
    color: "#999",
    fontSize: "0.85rem",
    marginBottom: "0.75rem",
    fontWeight: "600"
  },
  emailBody: {
    color: "#ccc",
    fontSize: "0.9rem",
    lineHeight: "1.6"
  },
  inlineCode: {
    background: "#1a1a1a",
    padding: "0.25rem 0.5rem",
    borderRadius: "4px",
    fontSize: "0.85rem",
    color: "#3b82f6",
    wordBreak: "break-all"
  },
  roomInfo: {
    background: "#2a2a2a",
    borderRadius: "8px",
    padding: "1rem",
    marginTop: "1.5rem",
    border: "1px solid #444"
  },
  roomInfoRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0.5rem 0"
  },
  infoLabel: {
    color: "#999",
    fontSize: "0.9rem"
  },
  infoValue: {
    color: "#3b82f6",
    fontSize: "0.9rem",
    fontFamily: "monospace",
    fontWeight: "600"
  },
  primaryButton: {
    width: "100%",
    padding: "0.875rem 1.5rem",
    background: "#3b82f6",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "1rem",
    transition: "background 0.2s"
  },
  secondaryButton: {
    width: "100%",
    padding: "0.875rem 1.5rem",
    background: "#2a2a2a",
    color: "white",
    border: "1px solid #444",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "1rem",
    transition: "all 0.2s"
  },
  loadingSpinner: {
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
  }
};
