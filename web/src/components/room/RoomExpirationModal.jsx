import React from 'react';
import PropTypes from 'prop-types';

/**
 * RoomExpirationModal - Full-screen modal shown when room is closed
 *
 * Displayed when:
 * - Room admin has been away for 30 minutes
 * - Room is automatically closed and deleted
 *
 * Features:
 * - Cannot be closed (no backdrop click, no ESC)
 * - Two action buttons: Create Account or Sign In
 * - Centered layout with promotional message
 */
export default function RoomExpirationModal({ isOpen, onCreateAccount, onSignIn }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/95 z-[200] flex items-center justify-center p-4">
      <div className="bg-card-dark rounded-2xl px-8 py-10 max-w-[450px] w-full border-2 border-red-600 text-center">
        {/* Goodbye Icon */}
        <div className="text-[3rem] mb-4">
          👋
        </div>

        {/* Title */}
        <h2 className="m-0 mb-4 text-2xl text-white font-semibold">
          Thank you for joining!
        </h2>

        {/* Main Message */}
        <p className="m-0 mb-6 text-base text-[#ccc] leading-relaxed">
          This room has been closed because the admin has been away for 30 minutes.
        </p>

        {/* Promotional Message */}
        <p className="m-0 mb-8 text-sm text-muted-dark">
          Create your own account to host unlimited translation rooms.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col gap-3">
          <button
            onClick={onCreateAccount}
            className="w-full px-4 py-4 bg-blue-500 text-white border-0 rounded-xl cursor-pointer font-semibold text-[1.05rem] hover:bg-blue-600 transition-colors"
          >
            Create Account
          </button>
          <button
            onClick={onSignIn}
            className="w-full px-4 py-4 bg-[#2a2a2a] text-white border border-[#444] rounded-xl cursor-pointer font-semibold text-[1.05rem] hover:bg-[#333] transition-colors"
          >
            Sign In
          </button>
        </div>
      </div>
    </div>
  );
}

RoomExpirationModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onCreateAccount: PropTypes.func.isRequired,
  onSignIn: PropTypes.func.isRequired
};
