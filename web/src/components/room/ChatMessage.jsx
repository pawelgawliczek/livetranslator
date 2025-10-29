import React from 'react';
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
function ChatMessage({
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
      <div className="text-center p-1 text-muted text-xs italic">
        <span className="bg-bg-secondary/50 px-2.5 py-1 rounded-xl inline-block border border-border/20">
          {segment.source.text}
        </span>
      </div>
    );
  }

  // Username component (reusable for translation and source-only)
  const Username = ({ speaker }) => {
    if (!speaker || speaker === 'system') return null;

    return (
      <div className="flex flex-col flex-shrink-0 min-w-fit">
        <span className="text-xs text-blue-500 font-semibold leading-tight">
          👤 {speaker.split('@')[0]}
        </span>
        {timestamp && formatTime && (
          <span className="text-[0.6rem] text-muted leading-tight">
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
      <span className="text-base font-medium leading-relaxed flex-1 min-w-0"
        style={{ color: isFinal ? 'var(--fg)' : 'var(--muted)' }}
      >
        {isSpecialSpeaking ? (
          <>
            <span className="processing-spinner text-blue-500">
              🎤
            </span>
            <span className="italic"> Speaking...</span>
          </>
        ) : (
          <>
            {data.text}
            {!isFinal && (
              <span className="processing-spinner ml-2 text-blue-500">
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
      <div className="text-xs text-muted mt-1 flex items-center gap-1.5">
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
    <div className="bg-card rounded-xl p-2 px-2.5 border border-border relative">
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
        >
          🔍
        </span>
      )}
      {isAdmin && <div style={{display: 'none'}}>DEBUG_ICON_SHOULD_RENDER</div>}

      {segment.translation ? (
        <>
          {/* Message with translation */}
          <div className="flex items-start gap-2">
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
            <div className="text-muted text-sm italic leading-snug">
              {segment.source.text}
            </div>
          )}
        </>
      ) : (
        <>
          {/* Message without translation - show source prominently */}
          {segment.source && (
            <>
              <div className="flex items-start gap-2">
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

// Memoize to prevent re-renders when parent updates but props don't change
export default React.memo(ChatMessage);
