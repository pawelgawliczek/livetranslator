import React from 'react';
import PropTypes from 'prop-types';

/**
 * RoomExpirationModal - Full-screen modal shown when room is closing or closed
 *
 * Displayed when:
 * - Room admin has been away and room is about to expire
 * - Room is automatically closed and deleted
 *
 * Features:
 * - Cannot be closed (no backdrop click, no ESC)
 * - Shows countdown timer
 * - Close button to leave room
 */
export default function RoomExpirationModal({ timeRemaining, formatCountdown, onClose }) {
  if (!timeRemaining && timeRemaining !== 0) return null;

  return (
    <div className="fixed inset-0 bg-black/95 z-[200] flex items-center justify-center p-4">
      <div className="bg-card rounded-2xl px-8 py-10 max-w-[450px] w-full border-2 border-red-600 text-center">
        {/* Warning Icon */}
        <div className="text-[3rem] mb-4">
          ⚠️
        </div>

        {/* Title */}
        <h2 className="m-0 mb-4 text-2xl text-fg font-semibold">
          Room Closing Soon
        </h2>

        {/* Main Message */}
        <p className="m-0 mb-6 text-base text-muted leading-relaxed">
          The admin has left the room. The room will close in:
        </p>

        {/* Countdown */}
        <div className="text-[2.5rem] font-bold text-red-500 mb-6">
          {formatCountdown(timeRemaining)}
        </div>

        {/* Info Message */}
        <p className="m-0 mb-8 text-sm text-muted">
          The room will remain open if the admin rejoins.
        </p>

        {/* Close Button */}
        <button
          onClick={onClose}
          className="w-full px-4 py-4 bg-red-600 text-white border-0 rounded-xl cursor-pointer font-semibold text-[1.05rem] hover:bg-red-700 transition-colors"
        >
          Leave Room
        </button>
      </div>
    </div>
  );
}

RoomExpirationModal.propTypes = {
  timeRemaining: PropTypes.number,
  formatCountdown: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired
};
