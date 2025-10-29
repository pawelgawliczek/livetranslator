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
      className={`w-full h-14 rounded-[28px] text-white border-0 text-lg font-semibold cursor-pointer flex items-center justify-center gap-2 shadow-lg select-none ${
        isIdle ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
      }`}
      style={{
        WebkitTapHighlightColor: 'transparent',
        touchAction: 'manipulation',
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
