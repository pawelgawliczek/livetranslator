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
  const borderColorClass = isUrgent ? 'border-red-600' : 'border-orange-500';
  const accentColorClass = isUrgent ? 'text-red-500' : 'text-orange-500';

  return (
    <div className={`bg-card border-2 ${borderColorClass} rounded-xl px-4 py-3 mx-3 mb-0 shadow-lg flex-shrink-0`}>
      <div className="text-fg font-semibold text-sm mb-1 text-center">
        {t('room.adminLeftWarning')}
      </div>
      <div className={`${accentColorClass} text-xs font-normal text-center`}>
        {t('room.roomClosingIn', { countdown: formatCountdown(timeRemaining) })}
      </div>
      {isUrgent && (
        <div className="text-muted text-xs font-normal mt-1 text-center">
          {t('room.recordingDisabledWarning')}
        </div>
      )}
    </div>
  );
}
