import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';

/**
 * MicrophoneButton - Large button for starting/stopping audio recording
 *
 * Supports two modes:
 * 1. Normal mode: Click to start/stop recording
 * 2. Push-to-Talk (PTT) mode: Hold button to record, release to stop
 *
 * @param {Object} props
 * @param {string} props.status - Current recording status: 'idle', 'streaming', 'connecting', etc.
 * @param {boolean} props.pushToTalk - Whether push-to-talk mode is enabled
 * @param {boolean} props.isPressing - Whether user is currently pressing the button (PTT mode)
 * @param {Function} props.onStart - Callback when starting recording
 * @param {Function} props.onStop - Callback when stopping recording
 * @param {Function} [props.onPressStart] - Callback when user starts pressing (PTT mode)
 * @param {Function} [props.onPressEnd] - Callback when user stops pressing (PTT mode)
 */
export default function MicrophoneButton({
  status = 'idle',
  pushToTalk = false,
  isPressing = false,
  onStart,
  onStop,
  onPressStart,
  onPressEnd
}) {
  const { t } = useTranslation();

  const isIdle = status === 'idle';
  const isStreaming = status === 'streaming';

  // Determine button color
  const getBackgroundColor = () => {
    if (isIdle) return '#16a34a'; // green-600
    return '#dc2626'; // red-600
  };

  // Determine button content based on state
  const getButtonContent = () => {
    if (isIdle) {
      return (
        <>
          🎤 {t('room.start')}
        </>
      );
    }

    if (pushToTalk) {
      return isPressing ? (
        <>
          🔴 {t('room.recording')}
        </>
      ) : (
        <>
          👆 {t('room.holdToSpeak')}
        </>
      );
    }

    return (
      <>
        ⏹ {t('room.stop')}
      </>
    );
  };

  // Handle click for start/stop
  const handleClick = () => {
    if (isIdle) {
      onStart?.();
    } else {
      onStop?.();
    }
  };

  // Handle mouse/touch press events for PTT mode
  const handlePressStart = (e) => {
    if (pushToTalk && isStreaming) {
      if (e.type === 'touchstart') {
        e.preventDefault();
      }
      onPressStart?.();
    }
  };

  const handlePressEnd = (e) => {
    if (pushToTalk && isStreaming) {
      if (e.type === 'touchend') {
        e.preventDefault();
      }
      onPressEnd?.();
    }
  };

  const handleContextMenu = (e) => {
    e.preventDefault();
  };

  return (
    <button
      onClick={handleClick}
      onTouchStart={handlePressStart}
      onTouchEnd={handlePressEnd}
      onMouseDown={handlePressStart}
      onMouseUp={handlePressEnd}
      onContextMenu={handleContextMenu}
      aria-label={isIdle ? t('room.start') : t('room.stop')}
      style={{
        width: '100%',
        height: '56px',
        borderRadius: '28px',
        background: getBackgroundColor(),
        color: 'white',
        border: 'none',
        fontSize: '1.05rem',
        fontWeight: '600',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '0.5rem',
        boxShadow: '0 4px 12px rgba(0,0,0,0.4)',
        WebkitTapHighlightColor: 'transparent',
        touchAction: 'manipulation',
        userSelect: 'none',
        WebkitUserSelect: 'none',
        MozUserSelect: 'none',
        msUserSelect: 'none',
        WebkitTouchCallout: 'none'
      }}
    >
      {getButtonContent()}
    </button>
  );
}

MicrophoneButton.propTypes = {
  status: PropTypes.oneOf(['idle', 'streaming', 'connecting', 'reconnecting', 'error']),
  pushToTalk: PropTypes.bool,
  isPressing: PropTypes.bool,
  onStart: PropTypes.func.isRequired,
  onStop: PropTypes.func.isRequired,
  onPressStart: PropTypes.func,
  onPressEnd: PropTypes.func
};
