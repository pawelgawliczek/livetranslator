import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * useMultiSpeakerRoom Hook
 *
 * Manages multi-speaker room state including:
 * - Speaker list with metadata
 * - Message grouping by segment with all translations
 * - Speaker change detection
 *
 * @param {Object} options
 * @param {string} options.roomCode - Room code
 * @param {string} options.token - Auth token
 * @param {boolean} options.isGuest - Whether user is a guest
 * @param {string} options.myLanguage - Current user's language
 * @param {string} options.userEmail - Current user's email
 *
 * @returns {Object} Multi-speaker room state and methods
 */
export default function useMultiSpeakerRoom({
  roomCode,
  token,
  isGuest,
  myLanguage,
  userEmail
}) {
  // Speakers state
  const [speakers, setSpeakers] = useState([]);
  const [speakersMap, setSpeakersMap] = useState(new Map());
  const [loadingSpeakers, setLoadingSpeakers] = useState(true);

  // Message storage for multi-speaker display
  // Map<segment_id, { source, translations: Map<target_lang, translation> }>
  const segmentsRef = useRef(new Map());
  const [messages, setMessages] = useState([]);
  const dirtyRef = useRef(false);

  /**
   * Fetch speakers from API
   */
  const fetchSpeakers = useCallback(async () => {
    if (!roomCode) return;

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
        const speakersList = data.speakers || [];
        setSpeakers(speakersList);

        // Create a map for quick lookup
        const map = new Map();
        speakersList.forEach(speaker => {
          map.set(speaker.speaker_id, speaker);
        });
        setSpeakersMap(map);
      }
    } catch (error) {
      console.error('[MultiSpeaker] Failed to fetch speakers:', error);
    } finally {
      setLoadingSpeakers(false);
    }
  }, [roomCode, token, isGuest]);

  /**
   * Load speakers on mount
   */
  useEffect(() => {
    fetchSpeakers();
  }, [fetchSpeakers]);

  /**
   * Schedule a debounced render update
   */
  const scheduleRender = useCallback(() => {
    if (dirtyRef.current) return;
    dirtyRef.current = true;

    setTimeout(() => {
      const messagesList = [];

      // Convert segments to array and sort by timestamp
      for (const [segId, segment] of segmentsRef.current.entries()) {
        if (!segment.source) continue;

        // Get all translations for this segment
        const translations = Array.from(segment.translations.values());

        messagesList.push({
          segId,
          segment: {
            source: segment.source,
            translation: null // Not used in multi-speaker view
          },
          translations,
          speakerInfo: segment.speakerInfo
        });
      }

      // Sort by timestamp
      messagesList.sort((a, b) => {
        const tsA = a.segment.source?.ts_iso || '';
        const tsB = b.segment.source?.ts_iso || '';
        return tsA.localeCompare(tsB);
      });

      setMessages(messagesList);
      dirtyRef.current = false;
    }, 200); // 200ms debounce
  }, []);

  /**
   * Process incoming WebSocket messages for multi-speaker display
   */
  const onMessage = useCallback((ev) => {
    try {
      const m = JSON.parse(ev.data);

      // Only process STT and translation messages
      const messageTypes = [
        'translation_partial', 'translation_final',
        'partial', 'stt_partial', 'final', 'stt_final', 'stt_finalize',
        'speech_started'
      ];
      if (!messageTypes.includes(m.type)) {
        return;
      }

      // Handle speech_started event
      if (m.type === 'speech_started') {
        const segmentId = m.segment_id;
        const speakerId = m.speaker_id !== undefined ? parseInt(m.speaker_id, 10) : null;

        if (!segmentsRef.current.has(segmentId)) {
          const placeholder = {
            source: {
              segment_id: segmentId,
              type: 'stt_partial',
              text: '___SPEAKING___',
              speaker: m.speaker,
              speaker_id: speakerId,
              final: false,
              ts_iso: new Date().toISOString(),
              is_placeholder: true
            },
            translations: new Map(),
            speakerInfo: speakerId !== null ? speakersMap.get(speakerId) : null
          };
          segmentsRef.current.set(segmentId, placeholder);
          scheduleRender();

          // Auto-remove placeholder after 5 seconds if no text arrives
          setTimeout(() => {
            const segment = segmentsRef.current.get(segmentId);
            if (segment && segment.source?.is_placeholder) {
              segmentsRef.current.delete(segmentId);
              scheduleRender();
            }
          }, 5000);
        }
        return;
      }

      const segId = m.segment_id;
      if (!segId) return;

      // Get or create segment
      if (!segmentsRef.current.has(segId)) {
        segmentsRef.current.set(segId, {
          source: null,
          translations: new Map(),
          speakerInfo: null
        });
      }

      const segment = segmentsRef.current.get(segId);

      // Process translation events
      if (m.type && m.type.startsWith('translation')) {
        const targetLang = m.tgt;
        if (targetLang) {
          // Store all translations (not just user's language)
          segment.translations.set(targetLang, m);
        }
      } else {
        // Process STT events (source)
        if (!segment.source || m.final || (!m.final && !segment.source.final)) {
          segment.source = m;

          // Extract speaker info from message
          const speakerId = m.speaker_info?.speaker_id ??
                           (m.speaker_id !== undefined ? parseInt(m.speaker_id, 10) : null);

          if (speakerId !== null && speakersMap.has(speakerId)) {
            segment.speakerInfo = speakersMap.get(speakerId);
          } else if (m.speaker_info) {
            // Use speaker_info from the message if available
            segment.speakerInfo = m.speaker_info;
          }
        }
      }

      scheduleRender();
    } catch (error) {
      console.error('[MultiSpeaker] Error processing message:', error);
    }
  }, [speakersMap, scheduleRender]);

  /**
   * Clear all messages
   */
  const clearMessages = useCallback(() => {
    segmentsRef.current.clear();
    setMessages([]);
  }, []);

  return {
    speakers,
    loadingSpeakers,
    messages,
    onMessage,
    clearMessages,
    refetchSpeakers: fetchSpeakers
  };
}
