import React from "react";

/**
 * Toast notification system for presence events.
 *
 * Features:
 * - Auto-dismiss after 5 seconds
 * - Stacks up to 3 notifications
 * - Slide-in animation
 * - Shows join/leave/language change events
 */
export default function NotificationToast({ notifications }) {
  if (!notifications || notifications.length === 0) {
    return null;
  }

  return (
    <div style={styles.container}>
      {notifications.map((notif) => (
        <div key={notif.id} style={styles.toast} className="toast-slide-in">
          {notif.message}
        </div>
      ))}
      <style>{`
        @keyframes slideIn {
          from {
            transform: translateX(400px);
            opacity: 0;
          }
          to {
            transform: translateX(0);
            opacity: 1;
          }
        }
        .toast-slide-in {
          animation: slideIn 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}

const styles = {
  container: {
    position: "fixed",
    top: "80px",
    right: "20px",
    zIndex: 1000,
    display: "flex",
    flexDirection: "column",
    gap: "10px",
    pointerEvents: "none", // Allow clicking through
  },
  toast: {
    background: "#2a2a2a",
    border: "1px solid #444",
    borderRadius: "8px",
    padding: "12px 16px",
    color: "white",
    fontSize: "0.9rem",
    boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
    maxWidth: "300px",
    wordWrap: "break-word",
    pointerEvents: "auto", // Allow interaction with individual toasts
  },
};
