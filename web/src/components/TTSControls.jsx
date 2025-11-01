import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';

/**
 * TTS Controls component for room settings
 * Allows users to enable/disable TTS and configure voice preferences per language
 */
export function TTSControls({ roomCode, enabled, voices, onToggle, onVoiceChange }) {
  const { t } = useTranslation();
  const [isExpanded, setIsExpanded] = useState(false);

  // Available voices per language (subset of Google TTS voices)
  const availableVoices = {
    'en': [
      { value: 'en-US-Neural2-D', label: t('tts.voices.enUSNeuralD') },
      { value: 'en-US-Neural2-F', label: t('tts.voices.enUSNeuralF') },
      { value: 'en-GB-Neural2-B', label: t('tts.voices.enGBNeuralB') }
    ],
    'pl': [
      { value: 'pl-PL-Wavenet-A', label: t('tts.voices.plPLWavenetA') },
      { value: 'pl-PL-Wavenet-B', label: t('tts.voices.plPLWavenetB') }
    ],
    'ar': [
      { value: 'ar-XA-Wavenet-A', label: t('tts.voices.arXAWavenetA') },
      { value: 'ar-XA-Wavenet-B', label: t('tts.voices.arXAWavenetB') }
    ],
    'es': [
      { value: 'es-ES-Neural2-A', label: t('tts.voices.esESNeuralA') },
      { value: 'es-ES-Neural2-B', label: t('tts.voices.esESNeuralB') }
    ],
    'fr': [
      { value: 'fr-FR-Neural2-A', label: t('tts.voices.frFRNeuralA') },
      { value: 'fr-FR-Neural2-B', label: t('tts.voices.frFRNeuralB') }
    ],
    'de': [
      { value: 'de-DE-Neural2-A', label: t('tts.voices.deDENeuralA') },
      { value: 'de-DE-Neural2-B', label: t('tts.voices.deDENeuralB') }
    ],
    'it': [
      { value: 'it-IT-Neural2-A', label: t('tts.voices.itITNeuralA') },
      { value: 'it-IT-Neural2-B', label: t('tts.voices.itITNeuralB') }
    ],
    'pt': [
      { value: 'pt-PT-Wavenet-A', label: t('tts.voices.ptPTWavenetA') },
      { value: 'pt-PT-Wavenet-B', label: t('tts.voices.ptPTWavenetB') }
    ],
    'ru': [
      { value: 'ru-RU-Wavenet-A', label: t('tts.voices.ruRUWavenetA') },
      { value: 'ru-RU-Wavenet-B', label: t('tts.voices.ruRUWavenetB') }
    ]
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={enabled}
            onChange={(e) => onToggle(e.target.checked)}
            className="w-5 h-5 cursor-pointer accent-accent"
          />
          <span className="text-sm font-semibold text-fg">{t('tts.enableTTS')}</span>
        </label>
      </div>

      {enabled && (
        <div className="flex flex-col gap-3">
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="flex items-center gap-2 text-sm font-semibold text-fg hover:text-accent transition-colors"
          >
            <span>{isExpanded ? '▼' : '▶'}</span>
            <span>{t('tts.voiceSettings')}</span>
          </button>

          {isExpanded && (
            <div className="flex flex-col gap-4 pl-6 border-l-2 border-border">
              {Object.entries(availableVoices).map(([lang, voiceList]) => (
                <div key={lang} className="flex flex-col gap-2">
                  <label className="text-xs font-semibold text-muted uppercase">
                    {t(`languages.${lang}`)}
                  </label>
                  <select
                    value={voices[lang] || voiceList[0].value}
                    onChange={(e) => onVoiceChange(lang, e.target.value)}
                    className="px-3 py-2 bg-bg-secondary border border-border rounded text-sm text-fg focus:outline-none focus:border-accent"
                  >
                    {voiceList.map((voice) => (
                      <option key={voice.value} value={voice.value}>
                        {voice.label}
                      </option>
                    ))}
                  </select>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

TTSControls.propTypes = {
  roomCode: PropTypes.string.isRequired,
  enabled: PropTypes.bool.isRequired,
  voices: PropTypes.object,
  onToggle: PropTypes.func.isRequired,
  onVoiceChange: PropTypes.func.isRequired
};

TTSControls.defaultProps = {
  voices: {}
};

export default TTSControls;
