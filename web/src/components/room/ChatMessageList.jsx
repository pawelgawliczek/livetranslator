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
export default function ChatMessageList({
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
    <div
      style={{
        flex: 1,
        overflowY: 'auto',
        overflowX: 'hidden',
        padding: '0.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
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
        <div
          style={{
            textAlign: 'center',
            color: '#666',
            padding: '2rem 1rem',
            margin: 'auto',
            fontSize: '0.9rem'
          }}
        >
          📜 Loading history...
        </div>
      )}

      {/* Empty State */}
      {!loadingHistory && messages.length === 0 && (
        <div
          style={{
            textAlign: 'center',
            color: '#666',
            padding: '2rem 1rem',
            margin: 'auto',
            fontSize: '0.9rem'
          }}
        >
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
