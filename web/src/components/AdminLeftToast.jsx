import React from "react";
import { useTranslation } from "react-i18next";

/**
 * Non-closable toast notification for admin absence with countdown timer.
 *
 * Features:
 * - Fixed position at top of page
 * - Shows countdown timer
 * - Color changes based on urgency (orange -> red when < 1 minute)
 * - Cannot be dismissed by user
 * - Doesn't hide chat content (content flows below)
 */
export default function AdminLeftToast({ timeRemaining, formatCountdown }) {
  const { t } = useTranslation();
  if (timeRemaining === null || timeRemaining === undefined || timeRemaining <= 0) {
    return null;
  }

  const isUrgent = timeRemaining < 60000; // Less than 1 minute

  return (
    <div
      style={{
        background: isUrgent
          ? "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)"
          : "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
        padding: "0.75rem 1rem",
        margin: "0.75rem",
        marginBottom: "0",
        color: "white",
        fontSize: "0.85rem",
        fontWeight: "600",
        textAlign: "center",
        borderRadius: "12px",
        boxShadow: "0 4px 12px rgba(0,0,0,0.5)",
        border: "1px solid rgba(255,255,255,0.2)",
        flexShrink: 0,
      }}
    >
        <div style={{ marginBottom: "0.25rem" }}>
          {t('room.adminLeftWarning')}
        </div>
        <div
          style={{
            fontSize: "0.75rem",
            fontWeight: "normal",
            opacity: 0.95,
          }}
        >
          {t('room.roomClosingIn', { countdown: formatCountdown(timeRemaining) })}
        </div>
        {isUrgent && (
          <div
            style={{
              fontSize: "0.7rem",
              fontWeight: "normal",
              opacity: 0.85,
              marginTop: "0.25rem",
            }}
          >
            {t('room.recordingDisabledWarning')}
          </div>
        )}
    </div>
  );
}
