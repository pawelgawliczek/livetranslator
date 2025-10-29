import React from 'react';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';
import ChatMessage from './ChatMessage';
import AdminLeftToast from '../AdminLeftToast';

/**
 * ChatMessageList - Scrollable container for chat messages
 *
 * Displays:
 * - Loading state when fetching history
 * - Empty state when no messages
 * - Admin left warning toast
 * - All chat messages with translations
 *
 * @param {Object} props
 * @param {Array<[string, Object]>} props.messages - Array of [segId, segment] tuples
 * @param {boolean} props.isAdmin - Whether current user is admin
 * @param {boolean} props.loadingHistory - Whether history is being loaded
 * @param {Function} props.formatTime - Function to format timestamps
 * @param {React.Ref} props.chatEndRef - Ref for auto-scroll anchor element
 * @param {Function} [props.onDebugClick] - Callback for debug icon clicks
 * @param {boolean} [props.showAdminLeftToast] - Whether to show admin left warning
 * @param {number} [props.timeRemaining] - Seconds remaining before room closes
 * @param {Function} [props.formatCountdown] - Function to format countdown
 */
function ChatMessageList({
  messages = [],
  isAdmin = false,
  loadingHistory = false,
  formatTime,
  chatEndRef,
  onDebugClick,
  showAdminLeftToast = false,
  timeRemaining = 0,
  formatCountdown
}) {
  const { t } = useTranslation();

  return (
    <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 flex flex-col gap-3"
      style={{
        WebkitOverflowScrolling: 'touch'
      }}
    >
      {/* Admin Left Toast - Non-closable countdown timer inside chat */}
      {showAdminLeftToast && (
        <AdminLeftToast
          timeRemaining={timeRemaining}
          formatCountdown={formatCountdown}
        />
      )}

      {/* Loading History */}
      {loadingHistory && messages.length === 0 && (
        <div className="text-center text-muted py-8 px-4 m-auto text-sm">
          📜 Loading history...
        </div>
      )}

      {/* Empty State */}
      {!loadingHistory && messages.length === 0 && (
        <div className="text-center text-muted py-8 px-4 m-auto text-sm">
          {t('room.pressToStart')}
        </div>
      )}

      {/* Messages */}
      {messages.map(([segId, segment]) => {
        // Skip invalid messages
        if (!segment || !segId) return null;

        return (
          <ChatMessage
            key={segId}
            segId={segId}
            segment={segment}
            isAdmin={isAdmin}
            formatTime={formatTime}
            onDebugClick={onDebugClick}
          />
        );
      })}

      {/* Scroll anchor for auto-scroll */}
      <div ref={chatEndRef} />
    </div>
  );
}

ChatMessageList.propTypes = {
  messages: PropTypes.arrayOf(
    PropTypes.arrayOf(
      PropTypes.oneOfType([
        PropTypes.string,
        PropTypes.shape({
          source: PropTypes.object,
          translation: PropTypes.object
        })
      ])
    )
  ),
  isAdmin: PropTypes.bool,
  loadingHistory: PropTypes.bool,
  formatTime: PropTypes.func,
  chatEndRef: PropTypes.oneOfType([
    PropTypes.func,
    PropTypes.shape({ current: PropTypes.any })
  ]),
  onDebugClick: PropTypes.func,
  showAdminLeftToast: PropTypes.bool,
  timeRemaining: PropTypes.number,
  formatCountdown: PropTypes.func
};

// Memoize to prevent re-renders when parent updates but props don't change
export default React.memo(ChatMessageList);
