import React from 'react';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';
import { getLanguageFlag } from '../../constants/languages';

/**
 * MultiSpeakerMessage - Message display for multi-speaker rooms
 *
 * Shows:
 * - Speaker avatar with color and name
 * - Original message text
 * - All translations grouped below (N-1 translations)
 * - Visual indicators for speaker changes
 *
 * @param {Object} props
 * @param {string} props.segId - Unique segment ID
 * @param {Object} props.segment - Message data
 * @param {Object} props.speakerInfo - Speaker metadata (speaker_id, display_name, language, color)
 * @param {Array} props.allTranslations - All translations for this segment
 * @param {boolean} props.isAdmin - Whether current user is admin
 * @param {Function} [props.formatTime] - Function to format timestamps
 * @param {Function} [props.onDebugClick] - Callback when debug icon is clicked
 * @param {boolean} [props.isNewSpeaker] - Whether this is a speaker change
 */
function MultiSpeakerMessage({
  segId,
  segment,
  speakerInfo,
  allTranslations = [],
  isAdmin = false,
  formatTime,
  onDebugClick,
  isNewSpeaker = false
}) {
  const { t } = useTranslation();

  const timestamp = segment.source?.ts_iso || segment.translation?.ts_iso;
  const isSystemMessage = segment.source?.is_system === true;
  const sourceText = segment.source?.text || '';
  const isFinal = segment.source?.final;
  const isSpecialSpeaking = sourceText === '___SPEAKING___';

  // System messages - centered and small
  if (isSystemMessage) {
    return (
      <div className="text-center p-1 text-muted text-xs italic">
        <span className="bg-bg-secondary/50 px-2.5 py-1 rounded-xl inline-block border border-border/20">
          {sourceText}
        </span>
      </div>
    );
  }

  // Handle debug icon click
  const handleDebugClick = () => {
    onDebugClick?.(segId);
  };

  return (
    <div className="space-y-2">
      {/* Speaker Change Indicator */}
      {isNewSpeaker && (
        <div className="flex items-center gap-2 my-3">
          <div className="flex-1 h-px bg-border"></div>
          <span className="text-xs text-muted">Speaker changed</span>
          <div className="flex-1 h-px bg-border"></div>
        </div>
      )}

      {/* Main Message Card */}
      <div
        className="bg-card rounded-xl p-3 border-l-4 relative"
        style={{
          borderLeftColor: speakerInfo?.color || '#888'
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
          >
            🔍
          </span>
        )}

        {/* Speaker Header */}
        <div className="flex items-center gap-2 mb-2">
          {/* Speaker Avatar */}
          <div
            className="w-8 h-8 rounded-full flex items-center justify-center font-bold text-white text-sm flex-shrink-0"
            style={{ backgroundColor: speakerInfo?.color || '#888' }}
          >
            {speakerInfo?.speaker_id !== undefined ? speakerInfo.speaker_id + 1 : '?'}
          </div>

          {/* Speaker Name & Language */}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-fg truncate">
                {speakerInfo?.display_name || 'Unknown Speaker'}
              </span>
              {speakerInfo?.language && (
                <span className="text-xs">
                  {getLanguageFlag(speakerInfo.language)}
                </span>
              )}
            </div>
            {timestamp && formatTime && (
              <span className="text-[0.6rem] text-muted">
                {formatTime(timestamp)}
              </span>
            )}
          </div>
        </div>

        {/* Original Message */}
        <div className="mb-2">
          <span
            className="text-base leading-relaxed"
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
                {sourceText}
                {!isFinal && (
                  <span className="processing-spinner ml-2 text-blue-500">
                    ⋯
                  </span>
                )}
              </>
            )}
          </span>
        </div>

        {/* Translations */}
        {allTranslations.length > 0 && !isSpecialSpeaking && (
          <div className="space-y-1.5 mt-3 pt-3 border-t border-border/30">
            {allTranslations.map((translation, index) => {
              const targetLang = translation.tgt;
              const translationText = translation.text;
              const translationFinal = translation.final;

              return (
                <div
                  key={`${segId}-${targetLang}-${index}`}
                  className="flex items-start gap-2 text-sm"
                >
                  <span className="text-muted flex-shrink-0">
                    → {getLanguageFlag(targetLang)}
                  </span>
                  <span
                    className="flex-1"
                    style={{
                      color: translationFinal ? 'var(--muted)' : 'var(--muted-light)',
                      fontStyle: 'italic'
                    }}
                  >
                    {translationText}
                    {!translationFinal && (
                      <span className="processing-spinner ml-2 text-blue-500 text-xs">
                        ⋯
                      </span>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Processing Indicator */}
        {isFinal && segment.source?.processing && (
          <div className="text-xs text-muted mt-2 flex items-center gap-1.5">
            <span className="processing-spinner">⚙️</span>
            <span>{t('room.refiningQuality')}</span>
          </div>
        )}
      </div>
    </div>
  );
}

MultiSpeakerMessage.propTypes = {
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
      ts_iso: PropTypes.string,
      tgt: PropTypes.string
    })
  }).isRequired,
  speakerInfo: PropTypes.shape({
    speaker_id: PropTypes.number,
    display_name: PropTypes.string,
    language: PropTypes.string,
    color: PropTypes.string
  }),
  allTranslations: PropTypes.arrayOf(
    PropTypes.shape({
      text: PropTypes.string,
      final: PropTypes.bool,
      tgt: PropTypes.string
    })
  ),
  isAdmin: PropTypes.bool,
  formatTime: PropTypes.func,
  onDebugClick: PropTypes.func,
  isNewSpeaker: PropTypes.bool
};

export default React.memo(MultiSpeakerMessage);
