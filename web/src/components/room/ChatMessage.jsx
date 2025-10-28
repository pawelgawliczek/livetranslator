import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';

/**
 * ChatMessage - Individual message display with translation support
 *
 * Handles three types of messages:
 * 1. System messages (join/leave notifications)
 * 2. Translated messages (shows translation prominently, source text below)
 * 3. Source-only messages (own messages without translation)
 *
 * @param {Object} props
 * @param {string} props.segId - Unique segment ID
 * @param {Object} props.segment - Message data containing source and/or translation
 * @param {boolean} props.isAdmin - Whether current user is admin (shows debug icon)
 * @param {Function} [props.formatTime] - Function to format timestamps
 * @param {Function} [props.onDebugClick] - Callback when debug icon is clicked
 */
export default function ChatMessage({
  segId,
  segment,
  isAdmin = false,
  formatTime,
  onDebugClick
}) {
  const { t } = useTranslation();

  const timestamp = segment.source?.ts_iso || segment.translation?.ts_iso;
  const isSystemMessage = segment.source?.is_system === true;

  // System messages - centered and small
  if (isSystemMessage) {
    return (
      <div
        style={{
          textAlign: 'center',
          padding: '0.25rem',
          color: '#666',
          fontSize: '0.7rem',
          fontStyle: 'italic'
        }}
      >
        <span
          style={{
            background: 'rgba(42, 42, 42, 0.5)',
            padding: '0.25rem 0.6rem',
            borderRadius: '10px',
            display: 'inline-block',
            border: '1px solid rgba(255, 255, 255, 0.05)'
          }}
        >
          {segment.source.text}
        </span>
      </div>
    );
  }

  // Username component (reusable for translation and source-only)
  const Username = ({ speaker }) => {
    if (!speaker || speaker === 'system') return null;

    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flexShrink: 0,
          minWidth: 'fit-content'
        }}
      >
        <span
          style={{
            fontSize: '0.65rem',
            color: '#3b82f6',
            fontWeight: '600',
            lineHeight: '1.2'
          }}
        >
          👤 {speaker.split('@')[0]}
        </span>
        {timestamp && formatTime && (
          <span
            style={{
              fontSize: '0.6rem',
              color: '#666',
              lineHeight: '1.2'
            }}
          >
            {formatTime(timestamp)}
          </span>
        )}
      </div>
    );
  };

  // Message text component (reusable for translation and source)
  const MessageText = ({ data, isFinal }) => {
    const isSpecialSpeaking = data.text === '___SPEAKING___';

    return (
      <span
        style={{
          color: isFinal ? '#fff' : '#bbb',
          fontSize: '1rem',
          fontWeight: '500',
          lineHeight: '1.45',
          flex: 1,
          minWidth: 0
        }}
      >
        {isSpecialSpeaking ? (
          <>
            <span className="processing-spinner" style={{ color: '#3b82f6' }}>
              🎤
            </span>
            <span style={{ fontStyle: 'italic' }}> Speaking...</span>
          </>
        ) : (
          <>
            {data.text}
            {!isFinal && (
              <span
                className="processing-spinner"
                style={{ marginLeft: '0.5rem', color: '#3b82f6' }}
              >
                ⋯
              </span>
            )}
          </>
        )}
      </span>
    );
  };

  // Processing indicator (reusable)
  const ProcessingIndicator = ({ show }) => {
    if (!show) return null;

    return (
      <div
        style={{
          fontSize: '0.75rem',
          color: '#888',
          marginTop: '0.25rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem'
        }}
      >
        <span className="processing-spinner">⚙️</span>
        <span>{t('room.refiningQuality')}</span>
      </div>
    );
  };

  // Handle debug icon click
  const handleDebugClick = () => {
    onDebugClick?.(segId);
  };

  // Regular message card
  return (
    <div
      style={{
        background: '#1a1a1a',
        borderRadius: '12px',
        padding: '0.5rem 0.65rem',
        border: '1px solid #333',
        position: 'relative'
      }}
    >
      {/* Debug icon - only visible for admin users */}
      {isAdmin && (
        <span
          className="debug-icon"
          onClick={handleDebugClick}
          title="View debug info"
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === 'Enter' || e.key === ' ') {
              e.preventDefault();
              handleDebugClick();
            }
          }}
          style={{
            cursor: 'pointer'
          }}
        >
          🔍
        </span>
      )}

      {segment.translation ? (
        <>
          {/* Message with translation */}
          <div
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              gap: '0.5rem'
            }}
          >
            <Username speaker={segment.source?.speaker} />
            <MessageText
              data={segment.translation}
              isFinal={segment.translation.final}
            />
          </div>

          <ProcessingIndicator
            show={segment.translation.final && segment.translation.processing}
          />

          {/* Original text - small font below */}
          {segment.source && (
            <div
              style={{
                color: '#666',
                fontSize: '0.8rem',
                fontStyle: 'italic',
                lineHeight: '1.35'
              }}
            >
              {segment.source.text}
            </div>
          )}
        </>
      ) : (
        <>
          {/* Message without translation - show source prominently */}
          {segment.source && (
            <>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '0.5rem'
                }}
              >
                <Username speaker={segment.source.speaker} />
                <MessageText
                  data={segment.source}
                  isFinal={segment.source.final}
                />
              </div>

              <ProcessingIndicator
                show={segment.source.final && segment.source.processing}
              />
            </>
          )}
        </>
      )}
    </div>
  );
}

ChatMessage.propTypes = {
  segId: PropTypes.string.isRequired,
  segment: PropTypes.shape({
    source: PropTypes.shape({
      is_system: PropTypes.bool,
      speaker: PropTypes.string,
      text: PropTypes.string,
      final: PropTypes.bool,
      processing: PropTypes.bool,
      ts_iso: PropTypes.string
    }),
    translation: PropTypes.shape({
      text: PropTypes.string,
      final: PropTypes.bool,
      processing: PropTypes.bool,
      ts_iso: PropTypes.string
    })
  }).isRequired,
  isAdmin: PropTypes.bool,
  formatTime: PropTypes.func,
  onDebugClick: PropTypes.func
};
