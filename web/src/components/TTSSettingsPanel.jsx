import React from 'react';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';

/**
 * TTS Settings Panel for user profile page
 * Allows users to configure global TTS preferences
 */
export function TTSSettingsPanel({ settings, onChange }) {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-6">
      {/* Enable TTS Toggle */}
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={settings.tts_enabled}
            onChange={(e) => onChange({ ...settings, tts_enabled: e.target.checked })}
            className="w-5 h-5 cursor-pointer accent-accent"
          />
          <span className="text-sm font-semibold text-fg">{t('tts.enableTTS')}</span>
        </label>
        <p className="text-xs text-muted ml-8">
          Enable text-to-speech for incoming translations across all rooms
        </p>
      </div>

      {settings.tts_enabled && (
        <>
          {/* Volume Control */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-muted">{t('tts.volume')}</label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={settings.tts_volume || 0.8}
                onChange={(e) => onChange({ ...settings, tts_volume: parseFloat(e.target.value) })}
                className="flex-1 h-2 bg-border rounded-lg appearance-none cursor-pointer accent-accent"
              />
              <span className="text-sm font-semibold text-fg min-w-[60px] text-right">
                {Math.round((settings.tts_volume || 0.8) * 100)}%
              </span>
            </div>
            <div className="flex justify-between text-xs text-muted">
              <span>Quiet</span>
              <span>Loud</span>
            </div>
          </div>

          {/* Speaking Rate Control */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-muted">{t('tts.speakingRate')}</label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="0.25"
                max="4"
                step="0.25"
                value={settings.tts_rate || 1.0}
                onChange={(e) => onChange({ ...settings, tts_rate: parseFloat(e.target.value) })}
                className="flex-1 h-2 bg-border rounded-lg appearance-none cursor-pointer accent-accent"
              />
              <span className="text-sm font-semibold text-fg min-w-[60px] text-right">
                {(settings.tts_rate || 1.0).toFixed(2)}x
              </span>
            </div>
            <div className="flex justify-between text-xs text-muted">
              <span>0.25x (Slow)</span>
              <span>4x (Fast)</span>
            </div>
          </div>

          {/* Pitch Control */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-muted">{t('tts.pitch')}</label>
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="-20"
                max="20"
                step="1"
                value={settings.tts_pitch || 0}
                onChange={(e) => onChange({ ...settings, tts_pitch: parseInt(e.target.value) })}
                className="flex-1 h-2 bg-border rounded-lg appearance-none cursor-pointer accent-accent"
              />
              <span className="text-sm font-semibold text-fg min-w-[60px] text-right">
                {settings.tts_pitch || 0}
              </span>
            </div>
            <div className="flex justify-between text-xs text-muted">
              <span>-20 (Lower)</span>
              <span>+20 (Higher)</span>
            </div>
          </div>

          {/* Info Box */}
          <div className="bg-bg-secondary p-4 rounded-lg border border-border">
            <p className="text-xs text-muted">
              <strong className="text-fg">💡 Tip:</strong> These settings apply to all rooms by default.
              You can override voice selection per room in room settings.
            </p>
          </div>
        </>
      )}
    </div>
  );
}

TTSSettingsPanel.propTypes = {
  settings: PropTypes.shape({
    tts_enabled: PropTypes.bool,
    tts_volume: PropTypes.number,
    tts_rate: PropTypes.number,
    tts_pitch: PropTypes.number
  }).isRequired,
  onChange: PropTypes.func.isRequired
};

export default TTSSettingsPanel;
