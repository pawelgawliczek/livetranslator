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
      className="bg-card border-t border-border p-3 shrink-0"
      style={{
        paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))'
      }}
    >
      {/* Push-to-talk checkbox and Network Status */}
      <div className="flex items-center justify-center gap-4 mb-2.5">
        <label className="flex items-center gap-2 text-xs text-muted cursor-pointer">
          <input
            type="checkbox"
            checked={pushToTalk}
            onChange={handlePushToTalkToggle}
            aria-label={t('room.pushToTalk')}
            className="cursor-pointer w-[18px] h-[18px]"
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
