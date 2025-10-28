/**
 * useRoomWebSocket Hook
 *
 * Manages WebSocket message processing for room transcriptions and translations.
 *
 * Features:
 * - STT message processing (partial, final, finalize)
 * - Translation message processing (partial, final)
 * - Placeholder management for speaking indicators
 * - Segment merging (source + translation)
 * - Message filtering and sorting
 * - Debounced rendering for performance
 *
 * @param {Object} options
 * @param {string} options.myLanguage - Current user's language preference
 * @param {string} options.userEmail - Current user's email (for placeholder tracking)
 *
 * @returns {Object} Message processing state and methods
 */

import { useEffect, useRef, useState } from 'react';

export default function useRoomWebSocket({ myLanguage, userEmail }) {
  // Message storage
  const segsRef = useRef(new Map());
  const [lines, setLines] = useState([]);

  // Rendering state
  const dirtyRef = useRef(false);
  const myLanguageRef = useRef(myLanguage);

  // Placeholder tracking
  const placeholderSegmentKeyRef = useRef(null);

  // Keep myLanguageRef in sync
  useEffect(() => {
    myLanguageRef.current = myLanguage;
    // Trigger re-render when language changes (to update translation filtering)
    scheduleRender();
  }, [myLanguage]);

  /**
   * Schedule a debounced render update
   * Debounces rapid message updates for performance
   */
  function scheduleRender() {
    if (dirtyRef.current) return;
    dirtyRef.current = true;

    setTimeout(() => {
      const segments = new Map();

      // Group messages by segment_id
      for (const [key, msg] of segsRef.current.entries()) {
        const segId = msg.segment_id;
        if (!segments.has(segId)) {
          segments.set(segId, { source: null, translation: null });
        }

        const seg = segments.get(segId);

        if (msg.type && msg.type.startsWith("translation")) {
          // Only store translation if it matches my language (use ref to get current value)
          const currentLang = myLanguageRef.current;
          if (msg.tgt === currentLang) {
            if (!seg.translation || msg.final || (!msg.final && !seg.translation.final)) {
              seg.translation = msg;
            }
          }
        } else {
          // Source message (STT)
          if (!seg.source || msg.final || (!msg.final && !seg.source.final)) {
            seg.source = msg;
          }
        }
      }

      // Convert to array and filter/sort
      const arr = Array.from(segments.entries())
        .filter(([segId, seg]) => {
          // Filter out empty segments, but keep speaking placeholders
          const hasSourceText = seg.source && seg.source.text && seg.source.text.trim().length > 0;
          const hasTranslationText = seg.translation && seg.translation.text && seg.translation.text.trim().length > 0;
          const isPlaceholder = seg.source?.text === '___SPEAKING___' || seg.translation?.text === '___SPEAKING___';
          return hasSourceText || hasTranslationText || isPlaceholder;
        })
        .sort((a, b) => {
          const tsA = a[1].source?.ts_iso || a[1].translation?.ts_iso || "";
          const tsB = b[1].source?.ts_iso || b[1].translation?.ts_iso || "";
          return tsA.localeCompare(tsB) || (a[0] - b[0]);
        })
        .slice(-100); // Keep last 100 segments

      setLines(arr);
      dirtyRef.current = false;
    }, 200); // 200ms debounce
  }

  /**
   * Process incoming WebSocket messages
   * Handles STT/translation messages and updates segment storage
   */
  function onMessage(ev) {
    try {
      const m = JSON.parse(ev.data);
      console.log('[WS] Received:', m);

      // Silently ignore non-STT/translation messages (they're handled elsewhere)
      const messageTypes = ["translation_partial", "translation_final", "partial", "stt_partial", "final", "stt_final", "stt_finalize", "speech_started"];
      if (!messageTypes.includes(m.type)) {
        return;
      }

      // Handle speech_started event
      if (m.type === 'speech_started') {
        console.log('[RoomWS] Speech started from:', m.speaker, 'segment_id:', m.segment_id);

        // Use the real segment ID from the backend
        const segmentId = m.segment_id;
        const placeholderKey = `s-${segmentId}`;

        // Only track our own placeholder for removal
        if (m.speaker === (userEmail || 'Guest')) {
          placeholderSegmentKeyRef.current = placeholderKey;
        }

        segsRef.current.set(placeholderKey, {
          segment_id: segmentId,
          type: 'stt_partial',
          text: '___SPEAKING___',
          speaker: m.speaker,
          final: false,
          ts_iso: new Date().toISOString(),
          is_placeholder: true
        });
        scheduleRender();

        // Auto-remove placeholder after 5 seconds if no text arrives
        setTimeout(() => {
          const segment = segsRef.current.get(placeholderKey);
          // Only delete if it's still a placeholder (not replaced by real text)
          if (segment && segment.is_placeholder) {
            segsRef.current.delete(placeholderKey);
            if (placeholderSegmentKeyRef.current === placeholderKey) {
              placeholderSegmentKeyRef.current = null;
            }
            scheduleRender();
            console.log('[VAD] Removed stale placeholder after timeout for:', m.speaker);
          } else if (segment) {
            console.log('[VAD] Placeholder already replaced with real text, keeping it for:', m.speaker);
          }
        }, 5000);

        return;
      }

      // Handle finalization marker (no text, just marks last partial as final)
      if (m.type === "stt_finalize") {
        const frontend_timestamp = Date.now() / 1000; // Convert to seconds
        const id = m.segment_id | 0;
        const existingSegment = segsRef.current.get(`s-${id}`);
        if (existingSegment) {
          const sync_delay = m.backend_timestamp ? (frontend_timestamp - m.backend_timestamp) : null;
          console.log(`[WS] ✅ Finalizing segment ${id} (sync delay: ${sync_delay ? (sync_delay * 1000).toFixed(0) + 'ms' : 'N/A'})`);
          // Mark existing partial as final
          existingSegment.final = true;
          existingSegment.processing = false;
          existingSegment.type = "stt_final";
          segsRef.current.set(`s-${id}`, existingSegment);
          scheduleRender();
        } else {
          console.warn(`[WS] ⚠️ Cannot finalize segment ${id} - not found in segsRef`);
        }
        return;
      }

      // Check if text field exists (not undefined)
      if (!('text' in m)) {
        console.log('[WS] Rejected: no text field');
        return;
      }

      // Skip messages with empty text (but log them)
      if (!m.text || m.text.trim() === '') {
        console.log('[WS] Skipping empty text message:', m.type, 'segment:', m.segment_id);
        return;
      }

      // Auto-generate segment_id and timestamp if missing
      m.segment_id = m.segment_id || Date.now();
      m.ts_iso = m.ts_iso || new Date().toISOString();
      const id = m.segment_id | 0;

      console.log('[WS] Processing:', m.type, 'segment:', id, 'speaker:', m.speaker);

      // Remove placeholder segment when real text arrives (only if it matches this segment AND is still a placeholder)
      if (placeholderSegmentKeyRef.current) {
        const placeholderSegmentKey = `s-${id}`;
        if (placeholderSegmentKeyRef.current === placeholderSegmentKey) {
          const existingSegment = segsRef.current.get(placeholderSegmentKeyRef.current);
          if (existingSegment && existingSegment.is_placeholder) {
            segsRef.current.delete(placeholderSegmentKeyRef.current);
            console.log('[WS] Removed placeholder segment:', placeholderSegmentKeyRef.current);
          } else {
            console.log('[WS] Placeholder already replaced, keeping real segment:', placeholderSegmentKeyRef.current);
          }
          placeholderSegmentKeyRef.current = null;
        } else {
          console.log('[WS] Skipping placeholder removal - segment mismatch:', placeholderSegmentKeyRef.current, 'vs', placeholderSegmentKey);
        }
      }

      // Store message
      if (m.type === "translation_partial" || m.type === "translation_final") {
        segsRef.current.set(`t-${id}`, { ...m, is_placeholder: false });
      } else if (m.type === "partial" || m.type === "stt_partial" || m.type === "final" || m.type === "stt_final") {
        segsRef.current.set(`s-${id}`, { ...m, is_placeholder: false });
      }

      scheduleRender();
    } catch (e) {
      console.error('[WS] Error:', e);
    }
  }

  return {
    // State
    lines,
    segsRef,

    // Methods
    onMessage,
    scheduleRender
  };
}
