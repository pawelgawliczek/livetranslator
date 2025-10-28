import React from 'react';
import PropTypes from 'prop-types';
import { LANGUAGES } from '../../constants/languages';

/**
 * WelcomeBanner - Welcome notification with participant list
 *
 * Displays:
 * - Welcome message with room name
 * - List of current participants (if any)
 * - Close button
 * - Fixed positioning at top of screen
 */
export default function WelcomeBanner({
  isOpen,
  roomId,
  participants = [],
  currentUserId,
  isGuest = false,
  onClose
}) {
  if (!isOpen) return null;

  // Filter out current user from participants list
  const otherParticipants = participants.filter(p => p.user_id !== currentUserId);

  return (
    <div className="fixed top-[60px] left-1/2 -translate-x-1/2 bg-card-dark border border-border-dark rounded-xl px-6 py-4 shadow-2xl z-[998] max-w-[400px] w-[90%]">
      {/* Header with title and close button */}
      <div className="flex justify-between items-start mb-2">
        <h3 className="m-0 text-base font-semibold text-white">
          Welcome to {roomId}!
        </h3>
        <button
          onClick={onClose}
          className="bg-transparent border-0 text-muted-dark cursor-pointer text-xl p-0 leading-none hover:text-white transition-colors"
          aria-label="Close welcome banner"
        >
          ✕
        </button>
      </div>

      {/* Participants list or empty message */}
      {otherParticipants.length > 0 ? (
        <div className="text-[#ccc] text-sm">
          <p className="m-0 mb-2">Also here:</p>
          <ul className="m-0 p-0 pl-5 list-none">
            {otherParticipants.map(p => {
              const lang = LANGUAGES.find(l => l.code === p.language);
              return (
                <li key={p.user_id} className="mb-1">
                  {lang?.flag || '🌐'} {p.display_name}
                  {p.is_guest && <span className="text-muted-dark"> (guest)</span>}
                  <span className="text-muted-dark"> ({lang?.name || p.language})</span>
                </li>
              );
            })}
          </ul>
        </div>
      ) : (
        <p className="m-0 text-[#ccc] text-sm">
          You're the first one here!
        </p>
      )}
    </div>
  );
}

WelcomeBanner.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  roomId: PropTypes.string.isRequired,
  participants: PropTypes.arrayOf(
    PropTypes.shape({
      user_id: PropTypes.string.isRequired,
      display_name: PropTypes.string.isRequired,
      language: PropTypes.string.isRequired,
      is_guest: PropTypes.bool
    })
  ),
  currentUserId: PropTypes.string,
  isGuest: PropTypes.bool,
  onClose: PropTypes.func.isRequired
};
