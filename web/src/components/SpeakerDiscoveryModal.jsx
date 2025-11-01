import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import Modal from './ui/Modal';
import { getSelectableLanguages } from '../constants/languages';

/**
 * SpeakerDiscoveryModal - Modal for discovering and configuring multiple speakers
 *
 * Features:
 * - One-button discovery start
 * - Auto-detection of speakers from STT events
 * - Real-time voice activity indicator
 * - Manual editing of speaker names and languages
 * - Complete discovery to lock speakers and start session
 */

// Predefined colors for speaker avatars (distinctive and accessible)
const SPEAKER_COLORS = [
  '#FF5733', // Red-orange
  '#33C3FF', // Sky blue
  '#FFD700', // Gold
  '#9B59B6', // Purple
  '#2ECC71', // Emerald green
  '#FF1493', // Deep pink
];

export default function SpeakerDiscoveryModal({
  isOpen,
  onClose,
  onCancel,     // Callback when user cancels during intro (goes back to rooms)
  roomCode,
  token,
  isGuest,
  ws,           // WebSocket connection to listen for STT events
  onComplete,   // Callback when discovery is complete
  onStartAudio  // Callback to start microphone/audio capture
}) {
  const { t } = useTranslation();
  const selectableLanguages = getSelectableLanguages();

  // Discovery state
  const [showIntro, setShowIntro] = useState(true); // Show intro screen first
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [speakers, setSpeakers] = useState([]);
  const [activeSpeakerId, setActiveSpeakerId] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  // Track detected speaker IDs to avoid duplicates
  const [detectedSpeakerIds, setDetectedSpeakerIds] = useState(new Set());

  // Compute unique languages from all speakers
  const detectedLanguages = React.useMemo(() => {
    const uniqueLangs = new Set(speakers.map(s => s.language));
    return Array.from(uniqueLangs).map(langCode => {
      const langInfo = selectableLanguages.find(l => l.code === langCode);
      return langInfo || { code: langCode, flag: '🌐', name: langCode };
    });
  }, [speakers, selectableLanguages]);

  /**
   * Start discovery mode
   */
  const handleStartDiscovery = async () => {
    setError(null);
    setLoading(true);

    try {
      const headers = {
        'Content-Type': 'application/json',
      };

      if (!isGuest && token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // Call API to enable discovery mode
      const response = await fetch(`/api/rooms/${roomCode}/discovery-mode`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ discovery_mode: 'enabled' })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to start discovery');
      }

      setShowIntro(false); // Hide intro screen
      setIsDiscovering(true);
      setSpeakers([]);
      setDetectedSpeakerIds(new Set());

      // Start audio capture (triggers microphone permission)
      if (onStartAudio) {
        await onStartAudio();
      }
    } catch (err) {
      console.error('[SpeakerDiscovery] Failed to start discovery:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Complete discovery and lock speakers
   */
  const handleCompleteDiscovery = async () => {
    if (speakers.length === 0) {
      setError('Please wait for at least one speaker to be detected before completing discovery.');
      return;
    }

    setError(null);
    setLoading(true);

    try {
      const headers = {
        'Content-Type': 'application/json',
      };

      if (!isGuest && token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // Update all speakers first
      const updateResponse = await fetch(`/api/rooms/${roomCode}/speakers`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ speakers })
      });

      if (!updateResponse.ok) {
        const errorData = await updateResponse.json();
        throw new Error(errorData.detail || 'Failed to save speakers');
      }

      // Lock discovery mode
      const lockResponse = await fetch(`/api/rooms/${roomCode}/discovery-mode`, {
        method: 'PATCH',
        headers,
        body: JSON.stringify({ discovery_mode: 'locked' })
      });

      if (!lockResponse.ok) {
        const errorData = await lockResponse.json();
        throw new Error(errorData.detail || 'Failed to lock discovery');
      }

      setIsDiscovering(false);
      if (onComplete) {
        onComplete(speakers);
      }
      onClose();
    } catch (err) {
      console.error('Failed to complete discovery:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  /**
   * Handle speaker name change
   */
  const handleNameChange = (speakerId, newName) => {
    setSpeakers(prevSpeakers =>
      prevSpeakers.map(speaker =>
        speaker.speaker_id === speakerId
          ? { ...speaker, display_name: newName }
          : speaker
      )
    );
  };

  /**
   * Handle speaker language change
   */
  const handleLanguageChange = (speakerId, newLanguage) => {
    setSpeakers(prevSpeakers =>
      prevSpeakers.map(speaker =>
        speaker.speaker_id === speakerId
          ? { ...speaker, language: newLanguage }
          : speaker
      )
    );
  };

  /**
   * Remove a speaker from the list
   */
  const handleRemoveSpeaker = (speakerId) => {
    setSpeakers(prevSpeakers =>
      prevSpeakers.filter(speaker => speaker.speaker_id !== speakerId)
    );
    setDetectedSpeakerIds(prev => {
      const newSet = new Set(prev);
      newSet.delete(speakerId);
      return newSet;
    });
  };

  /**
   * Listen for STT events and auto-detect speakers
   */
  useEffect(() => {
    if (!ws || !isDiscovering) {
      return;
    }

    const handleMessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        // Only process STT events with speaker information
        // speaker_id comes from Speechmatics diarization (numeric: 0, 1, 2...)
        if ((message.type === 'stt_partial' || message.type === 'stt_final' || message.type === 'transcript_partial' || message.type === 'transcript_final') && message.speaker_id !== undefined) {
          const speakerId = message.speaker_id;

          // Skip invalid speaker IDs
          if (typeof speakerId !== 'number' || speakerId < 0) return;

          // Show voice activity
          setActiveSpeakerId(speakerId);
          setTimeout(() => setActiveSpeakerId(null), 1000);

          // Add new speaker if not already detected
          if (!detectedSpeakerIds.has(speakerId)) {
            setDetectedSpeakerIds(prev => new Set(prev).add(speakerId));

            // Auto-detect language from STT event
            // Priority: detected_language (per-speaker from auto-detection) > lang (session) > fallback to 'en'
            const detectedLanguage = message.detected_language || message.lang || message.language || message.src || 'en';

            const newSpeaker = {
              speaker_id: speakerId,
              display_name: `Speaker ${speakerId + 1}`,
              language: detectedLanguage,
              color: SPEAKER_COLORS[speakerId % SPEAKER_COLORS.length]
            };

            setSpeakers(prevSpeakers => [...prevSpeakers, newSpeaker]);
          }
        }
      } catch (err) {
        console.error('[SpeakerDiscovery] Error processing WebSocket message:', err);
      }
    };

    ws.addEventListener('message', handleMessage);

    return () => {
      ws.removeEventListener('message', handleMessage);
    };
  }, [ws, isDiscovering, detectedSpeakerIds]);

  /**
   * Load existing speakers when modal opens
   */
  useEffect(() => {
    if (!isOpen || !roomCode) return;

    const fetchSpeakers = async () => {
      try {
        const headers = {};
        if (!isGuest && token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`/api/rooms/${roomCode}/speakers`, {
          headers
        });

        if (response.ok) {
          const data = await response.json();

          // If room has existing speakers (re-configuration), load them and skip intro
          if (data.speakers && data.speakers.length > 0) {
            setSpeakers(data.speakers);
            setDetectedSpeakerIds(new Set(data.speakers.map(s => s.speaker_id)));
            setShowIntro(false); // Skip intro for re-configuration

            // If locked, unlock for editing (user clicked "Configure Speakers" from settings)
            if (data.discovery_mode === 'locked') {
              console.log('[SpeakerDiscovery] Room locked, unlocking for re-configuration');
              await fetch(`/api/rooms/${roomCode}/discovery-mode`, {
                method: 'PATCH',
                headers: {
                  ...headers,
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify({ discovery_mode: 'enabled' })
              });
              setIsDiscovering(true);
            } else if (data.discovery_mode === 'enabled') {
              setIsDiscovering(true);
            }
          } else {
            // New room with no speakers - show intro
            setShowIntro(true);
            setIsDiscovering(false);
          }
        }
      } catch (err) {
        console.error('Failed to fetch speakers:', err);
      }
    };

    fetchSpeakers();
  }, [isOpen, roomCode, token, isGuest]);

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose} closeOnBackdrop={false}>
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center gap-3">
          <span style={{ fontSize: '2rem' }}>🎤</span>
          <div>
            <h3 className="text-2xl font-semibold text-fg m-0">
              {t('discovery.title', 'Speaker Discovery')}
            </h3>
            <p className="text-sm text-muted m-0 mt-1">
              {isDiscovering
                ? t('discovery.detecting', 'Speak naturally to be detected...')
                : t('discovery.intro', 'Configure speakers for multi-speaker translation')}
            </p>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-3 bg-red-900/20 border border-red-500/50 rounded-lg text-red-300 text-sm">
            {error}
          </div>
        )}

        {/* Intro Screen - First time room setup */}
        {showIntro ? (
          <div className="space-y-4">
            {/* Explanation */}
            <div className="p-4 bg-bg/50 border border-border rounded-lg space-y-3">
              <h4 className="text-lg font-semibold text-fg m-0 flex items-center gap-2">
                <span>🎯</span>
                {t('discovery.howItWorks', 'How Multi-Speaker Discovery Works')}
              </h4>
              <ol className="text-sm text-muted space-y-2 m-0 pl-5">
                <li className="flex gap-2">
                  <span className="text-accent font-semibold">1.</span>
                  <span>{t('discovery.step1', 'Each person will speak into their device in their native language')}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-accent font-semibold">2.</span>
                  <span>{t('discovery.step2', 'The system will automatically detect who is speaking and what language')}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-accent font-semibold">3.</span>
                  <span>{t('discovery.step3', 'You can review and edit speaker names and languages')}</span>
                </li>
                <li className="flex gap-2">
                  <span className="text-accent font-semibold">4.</span>
                  <span>{t('discovery.step4', 'Once complete, the conversation will start with real-time translation')}</span>
                </li>
              </ol>
            </div>

            {/* Important Note */}
            <div className="p-3 bg-accent/10 border border-accent/30 rounded-lg">
              <p className="text-sm text-fg m-0 flex items-start gap-2">
                <span className="text-accent text-lg">💡</span>
                <span>
                  <strong>{t('discovery.tipTitle', 'Tip:')}</strong>{' '}
                  {t('discovery.tipText', 'Have each speaker say a few sentences. The more they speak, the better the detection.')}
                </span>
              </p>
            </div>

            {/* Enable Discovery Button */}
            <button
              onClick={handleStartDiscovery}
              disabled={loading}
              className="w-full px-4 py-3 bg-accent text-white border-0 rounded-lg cursor-pointer font-semibold text-base hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="processing-spinner">⟳</span>
                  {t('discovery.starting', 'Starting...')}
                </span>
              ) : (
                <>✨ {t('discovery.enableDiscovery', 'Enable Discovery & Start Detection')}</>
              )}
            </button>
          </div>
        ) : !isDiscovering ? (
          <div className="space-y-3">
            <p className="text-sm text-muted">
              {t('discovery.instructions', 'Click "Start Discovery" to detect speakers again, or edit the configuration below.')}
            </p>
            <button
              onClick={handleStartDiscovery}
              disabled={loading}
              className="w-full px-4 py-3 bg-accent text-white border-0 rounded-lg cursor-pointer font-semibold text-base hover:bg-accent/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="processing-spinner">⟳</span>
                  {t('discovery.starting', 'Starting...')}
                </span>
              ) : (
                <>🎙️ {t('discovery.start', 'Start Discovery')}</>
              )}
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Detected Languages */}
            {detectedLanguages.length > 0 && (
              <div className="p-4 bg-bg/50 border border-border rounded-lg">
                <div className="flex items-center gap-3">
                  <span className="text-sm font-semibold text-muted whitespace-nowrap">
                    {t('discovery.detectedLanguages', 'Detected Languages')}:
                  </span>
                  <div className="flex items-center gap-2 flex-wrap">
                    {detectedLanguages.map((lang) => (
                      <div
                        key={lang.code}
                        className="flex items-center gap-2 px-3 py-1.5 bg-card border border-accent/30 rounded-full transition-all hover:border-accent/60"
                        title={lang.name}
                      >
                        <span className="text-2xl leading-none">{lang.flag}</span>
                        <span className="text-sm font-medium text-fg">{lang.name}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* Speaker List */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-lg font-semibold text-fg m-0">
                  {t('discovery.detectedSpeakers', 'Detected Speakers')} ({speakers.length})
                </h4>
                {speakers.length === 0 && (
                  <span className="text-xs text-muted italic">
                    {t('discovery.waitingForSpeakers', 'Waiting for speakers...')}
                  </span>
                )}
              </div>

              {speakers.length === 0 && (
                <div className="p-4 bg-bg/50 border border-border rounded-lg text-center">
                  <div className="text-4xl mb-2">🎤</div>
                  <p className="text-sm text-muted">
                    {t('discovery.noSpeakers', 'No speakers detected yet. Start speaking to be detected.')}
                  </p>
                </div>
              )}

              {speakers.map((speaker) => (
                <div
                  key={speaker.speaker_id}
                  className="p-4 bg-card border border-border rounded-lg space-y-3 relative"
                  style={{
                    borderLeft: `4px solid ${speaker.color}`,
                    opacity: activeSpeakerId === speaker.speaker_id ? 1 : 0.95,
                    transform: activeSpeakerId === speaker.speaker_id ? 'scale(1.02)' : 'scale(1)',
                    transition: 'all 0.2s ease'
                  }}
                >
                  {/* Voice Activity Indicator */}
                  {activeSpeakerId === speaker.speaker_id && (
                    <div className="absolute top-2 right-2">
                      <span className="flex items-center gap-1 text-xs font-semibold text-green-400">
                        <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></span>
                        {t('discovery.speaking', 'Speaking')}
                      </span>
                    </div>
                  )}

                  {/* Speaker Avatar & ID */}
                  <div className="flex items-center gap-3">
                    <div
                      className="w-10 h-10 rounded-full flex items-center justify-center font-bold text-white text-lg"
                      style={{ backgroundColor: speaker.color }}
                    >
                      {speaker.speaker_id + 1}
                    </div>
                    <div className="flex-1">
                      <label className="block text-xs text-muted mb-1">
                        {t('discovery.speakerName', 'Name')}
                      </label>
                      <input
                        type="text"
                        value={speaker.display_name}
                        onChange={(e) => handleNameChange(speaker.speaker_id, e.target.value)}
                        placeholder={t('discovery.enterName', 'Enter speaker name')}
                        className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-fg text-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                      />
                    </div>
                  </div>

                  {/* Language Selector */}
                  <div>
                    <label className="block text-xs text-muted mb-1">
                      {t('discovery.language', 'Language')}
                      <span className="ml-1 text-accent">(auto)</span>
                    </label>
                    <select
                      value={speaker.language}
                      onChange={(e) => handleLanguageChange(speaker.speaker_id, e.target.value)}
                      className="w-full px-3 py-2 bg-bg border border-border rounded-lg text-fg text-sm focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
                    >
                      {selectableLanguages.map(lang => (
                        <option key={lang.code} value={lang.code}>
                          {lang.flag} {lang.name}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Remove Button */}
                  <button
                    onClick={() => handleRemoveSpeaker(speaker.speaker_id)}
                    className="text-xs text-red-400 hover:text-red-300 transition-colors"
                  >
                    🗑️ {t('discovery.removeSpeaker', 'Remove')}
                  </button>
                </div>
              ))}
            </div>

            {/* Complete Discovery Button */}
            <button
              onClick={handleCompleteDiscovery}
              disabled={loading || speakers.length === 0}
              className="w-full px-4 py-3 bg-green-600 text-white border-0 rounded-lg cursor-pointer font-semibold text-base hover:bg-green-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="processing-spinner">⟳</span>
                  {t('discovery.completing', 'Completing...')}
                </span>
              ) : (
                <>✓ {t('discovery.complete', 'Complete Discovery')}</>
              )}
            </button>

            {/* Helper Text */}
            <p className="text-xs text-muted text-center">
              {t('discovery.completeHelp', 'Complete discovery to lock speakers and start the session. You can re-run discovery later from settings.')}
            </p>
          </div>
        )}

        {/* Cancel Button */}
        {!isDiscovering && (
          <button
            onClick={() => {
              // If in intro stage and onCancel provided, use that (navigates to rooms)
              // Otherwise use onClose (just closes modal)
              if (showIntro && onCancel) {
                onCancel();
              } else {
                onClose();
              }
            }}
            disabled={loading}
            className="w-full px-4 py-3 bg-transparent text-muted border border-border rounded-lg cursor-pointer font-semibold text-base hover:bg-bg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('discovery.cancel', 'Cancel')}
          </button>
        )}
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        .processing-spinner {
          display: inline-block;
          animation: spin 1s linear infinite;
        }
      `}</style>
    </Modal>
  );
}

SpeakerDiscoveryModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  onCancel: PropTypes.func,
  roomCode: PropTypes.string.isRequired,
  token: PropTypes.string,
  isGuest: PropTypes.bool,
  ws: PropTypes.object,
  onComplete: PropTypes.func,
  onStartAudio: PropTypes.func
};
