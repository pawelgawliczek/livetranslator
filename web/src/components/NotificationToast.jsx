import React from "react";

/**
 * Toast notification for presence events (join/leave/language change).
 *
 * Features:
 * - Auto-dismiss after 5 seconds (managed by parent)
 * - Slide-in animation
 * - Theme-aware colors
 * - Fixed position at top right
 */
export default function NotificationToast({ message }) {
  if (!message) {
    return null;
  }

  return (
    <div className="fixed top-20 right-5 z-[1000] pointer-events-none">
      <div className="bg-card border border-border rounded-lg px-4 py-3 text-fg text-sm shadow-lg max-w-[300px] break-words pointer-events-auto toast-slide-in">
        {message}
      </div>
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
