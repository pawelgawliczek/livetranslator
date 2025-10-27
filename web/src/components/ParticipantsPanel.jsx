import React from "react";
import { useTranslation } from "react-i18next";

/**
 * Collapsible sidebar showing active participants.
 *
 * Features:
 * - Shows all active participants with language flags
 * - Displays user names and languages
 * - Guest indicator
 * - Slide-in/out animation
 */
export default function ParticipantsPanel({
  participants,
  languages,
  isOpen,
  onToggle,
}) {
  const { t } = useTranslation();
  return (
    <>
      <div
        style={{
          ...styles.panel,
          transform: isOpen ? "translateX(0)" : "translateX(100%)",
        }}
      >
        <div style={styles.header}>
          <h3 style={styles.title}>{t('participants.panelTitle')} ({participants.length})</h3>
          <button onClick={onToggle} style={styles.closeBtn}>
            ✕
          </button>
        </div>

        <div style={styles.list}>
          {participants.length === 0 ? (
            <div style={styles.emptyState}>{t('participants.empty')}</div>
          ) : (
            participants.map((p) => {
              const lang = languages.find((l) => l.code === p.language);
              return (
                <div key={p.user_id} style={styles.participant}>
                  <div style={styles.participantInfo}>
                    <span style={styles.flag}>{lang?.flag || "🌐"}</span>
                    <div style={styles.nameContainer}>
                      <span style={styles.name}>
                        {p.display_name}
                        {p.is_guest && (
                          <span style={styles.guestBadge}>{t('participants.guestLabel')}</span>
                        )}
                      </span>
                      <span style={styles.lang}>{lang?.name || p.language}</span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Overlay when panel is open */}
      {isOpen && <div style={styles.overlay} onClick={onToggle} />}
    </>
  );
}

const styles = {
  panel: {
    position: "fixed",
    right: 0,
    top: 0,
    height: "100vh",
    width: "300px",
    background: "#1a1a1a",
    borderLeft: "1px solid #333",
    transition: "transform 0.3s ease",
    zIndex: 1001,
    display: "flex",
    flexDirection: "column",
    boxShadow: "-4px 0 20px rgba(0,0,0,0.5)",
  },
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: "rgba(0,0,0,0.5)",
    zIndex: 1000,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "1rem",
    borderBottom: "1px solid #333",
  },
  title: {
    margin: 0,
    fontSize: "1.1rem",
    fontWeight: "600",
    color: "white",
  },
  closeBtn: {
    background: "none",
    border: "none",
    color: "#999",
    fontSize: "1.5rem",
    cursor: "pointer",
    padding: "0.25rem",
    lineHeight: 1,
    transition: "color 0.2s",
  },
  list: {
    flex: 1,
    overflowY: "auto",
    padding: "0.5rem",
  },
  emptyState: {
    padding: "2rem 1rem",
    textAlign: "center",
    color: "#666",
    fontSize: "0.9rem",
  },
  participant: {
    padding: "0.75rem",
    borderRadius: "8px",
    marginBottom: "0.5rem",
    transition: "background 0.2s",
    cursor: "default",
  },
  participantInfo: {
    display: "flex",
    alignItems: "center",
    gap: "0.75rem",
  },
  flag: {
    fontSize: "1.5rem",
    flexShrink: 0,
  },
  nameContainer: {
    display: "flex",
    flexDirection: "column",
    gap: "0.25rem",
    minWidth: 0,
    flex: 1,
  },
  name: {
    color: "white",
    fontSize: "0.95rem",
    fontWeight: "500",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  },
  guestBadge: {
    marginLeft: "0.5rem",
    color: "#999",
    fontSize: "0.8rem",
    fontWeight: "normal",
  },
  lang: {
    color: "#999",
    fontSize: "0.85rem",
  },
};
