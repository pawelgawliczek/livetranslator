import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';
import NetworkStatusIndicator from './NetworkStatusIndicator';
import MicrophoneButton from './MicrophoneButton';

/**
 * RoomControls - Bottom panel with push-to-talk toggle, network status, and microphone button
 *
 * @param {Object} props
 * @param {string} props.status - Current recording status
 * @param {boolean} props.pushToTalk - Whether push-to-talk mode is enabled
 * @param {boolean} props.isPressing - Whether user is currently pressing the mic button (PTT)
 * @param {string} props.networkQuality - Network quality: 'high', 'medium', 'low', 'unknown'
 * @param {number|null} props.networkRTT - Round-trip time in milliseconds
 * @param {Function} props.onPushToTalkChange - Callback when PTT toggle changes
 * @param {Function} props.onStart - Callback when starting recording
 * @param {Function} props.onStop - Callback when stopping recording
 * @param {Function} [props.onPressStart] - Callback when user starts pressing (PTT mode)
 * @param {Function} [props.onPressEnd] - Callback when user stops pressing (PTT mode)
 */
export default function RoomControls({
  status = 'idle',
  pushToTalk = false,
  isPressing = false,
  networkQuality = 'unknown',
  networkRTT = null,
  onPushToTalkChange,
  onStart,
  onStop,
  onPressStart,
  onPressEnd
}) {
  const { t } = useTranslation();

  const handlePushToTalkToggle = (e) => {
    const newValue = e.target.checked;
    onPushToTalkChange?.(newValue);
    console.log('[Push-to-Talk] Toggle:', newValue ? 'ENABLED' : 'DISABLED');
  };

  return (
    <div
      style={{
        background: '#1a1a1a',
        borderTop: '1px solid #333',
        padding: '0.75rem',
        paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))',
        flexShrink: 0
      }}
    >
      {/* Push-to-talk checkbox and Network Status */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          marginBottom: '0.65rem'
        }}
      >
        <label
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            fontSize: '0.8rem',
            color: '#999',
            cursor: 'pointer'
          }}
        >
          <input
            type="checkbox"
            checked={pushToTalk}
            onChange={handlePushToTalkToggle}
            aria-label={t('room.pushToTalk')}
            style={{
              cursor: 'pointer',
              width: '18px',
              height: '18px'
            }}
          />
          {t('room.pushToTalk')}
        </label>

        {/* Network Status Indicator */}
        <NetworkStatusIndicator quality={networkQuality} rtt={networkRTT} />
      </div>

      {/* Microphone button */}
      <MicrophoneButton
        status={status}
        pushToTalk={pushToTalk}
        isPressing={isPressing}
        onStart={onStart}
        onStop={onStop}
        onPressStart={onPressStart}
        onPressEnd={onPressEnd}
      />
    </div>
  );
}

RoomControls.propTypes = {
  status: PropTypes.oneOf(['idle', 'streaming', 'connecting', 'reconnecting', 'error']),
  pushToTalk: PropTypes.bool,
  isPressing: PropTypes.bool,
  networkQuality: PropTypes.oneOf(['high', 'medium', 'low', 'unknown']),
  networkRTT: PropTypes.number,
  onPushToTalkChange: PropTypes.func,
  onStart: PropTypes.func,
  onStop: PropTypes.func,
  onPressStart: PropTypes.func,
  onPressEnd: PropTypes.func
};
