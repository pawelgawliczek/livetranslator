/**
 * Tests for useRoomWebSocket hook
 *
 * CRITICAL: Safari Language Normalization Bug Protection
 * This test suite prevents re-introduction of the language code mismatch bug
 * where Safari sends "en-US" but backend normalizes to "en", causing translations
 * to be filtered out.
 *
 * Bug Fix: Language normalization in myLanguageRef
 * - Normalizes "en-US" -> "en" before comparing with translation.tgt
 * - Ensures translations match regardless of locale variant (en-US, en-GB, etc.)
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import useRoomWebSocket from './useRoomWebSocket';

describe('useRoomWebSocket - Language Normalization', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should normalize language codes with locale variants (en-US -> en)', async () => {
    const { result } = renderHook(() =>
      useRoomWebSocket({
        myLanguage: 'en-US', // Safari sends this
        userEmail: 'test@example.com'
      })
    );

    // Create a translation event from backend (backend normalizes to "en")
    const translationEvent = {
      data: JSON.stringify({
        type: 'translation_partial',
        segment_id: 1,
        tgt: 'en', // Backend normalizes to "en"
        src: 'pl',
        text: 'Hello world',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    act(() => {
      result.current.onMessage(translationEvent);
    });

    // Wait for debounced render (200ms)
    await waitFor(() => {
      expect(result.current.lines).toHaveLength(1);
    }, { timeout: 500 });

    expect(result.current.lines[0][1].translation.text).toBe('Hello world');
  });

  it('should accept translations with exact language match (en -> en)', async () => {
    const { result } = renderHook(() =>
      useRoomWebSocket({
        myLanguage: 'en', // Exact match
        userEmail: 'test@example.com'
      })
    );

    const translationEvent = {
      data: JSON.stringify({
        type: 'translation_partial',
        segment_id: 1,
        tgt: 'en',
        src: 'pl',
        text: 'Hello world',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    act(() => {
      result.current.onMessage(translationEvent);
    });

    await waitFor(() => {
      expect(result.current.lines).toHaveLength(1);
    }, { timeout: 500 });

    expect(result.current.lines[0][1].translation.text).toBe('Hello world');
  });

  it('should reject translations with different target language', () => {
    const { result } = renderHook(() =>
      useRoomWebSocket({
        myLanguage: 'en-US',
        userEmail: 'test@example.com'
      })
    );

    const translationEvent = {
      data: JSON.stringify({
        type: 'translation_partial',
        segment_id: 1,
        tgt: 'pl', // Different language
        src: 'en',
        text: 'Cześć świecie',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    act(() => {
      result.current.onMessage(translationEvent);
    });

    // Translation should NOT be stored (wrong language)
    expect(result.current.lines).toHaveLength(0);
  });

  it('should update normalization when language changes', async () => {
    const { result, rerender } = renderHook(
      ({ myLanguage, userEmail }) =>
        useRoomWebSocket({ myLanguage, userEmail }),
      {
        initialProps: {
          myLanguage: 'en-US',
          userEmail: 'test@example.com'
        }
      }
    );

    // First translation (en-US user receives "en" translation)
    const enTranslation = {
      data: JSON.stringify({
        type: 'translation_partial',
        segment_id: 1,
        tgt: 'en',
        src: 'pl',
        text: 'Hello',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    act(() => {
      result.current.onMessage(enTranslation);
    });

    await waitFor(() => {
      expect(result.current.lines).toHaveLength(1);
    }, { timeout: 500 });

    expect(result.current.lines[0][1].translation.text).toBe('Hello');

    // Change language to Polish
    rerender({
      myLanguage: 'pl-PL',
      userEmail: 'test@example.com'
    });

    // After language change, English translation is filtered out (correct behavior)
    // User now only sees translations in their current language (Polish)
    await waitFor(() => {
      // English translation should be filtered out
      expect(result.current.lines).toHaveLength(0);
    }, { timeout: 500 });

    // Now Polish translation should be accepted
    const plTranslation = {
      data: JSON.stringify({
        type: 'translation_partial',
        segment_id: 2,
        tgt: 'pl',
        src: 'en',
        text: 'Cześć',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    act(() => {
      result.current.onMessage(plTranslation);
    });

    await waitFor(() => {
      expect(result.current.lines).toHaveLength(1);
    }, { timeout: 500 });

    // Only Polish translation visible
    expect(result.current.lines[0][1].translation.text).toBe('Cześć');
  });

  it('should handle locale variants (en-GB, en-AU, etc.)', async () => {
    const localeVariants = ['en-GB', 'en-AU', 'en-CA', 'en-NZ', 'en-IN'];

    for (const variant of localeVariants) {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: variant,
          userEmail: 'test@example.com'
        })
      );

      const translationEvent = {
        data: JSON.stringify({
          type: 'translation_partial',
          segment_id: 1,
          tgt: 'en', // Backend always sends "en"
          src: 'pl',
          text: 'Hello world',
          final: false,
          speaker: 'speaker@example.com',
          ts_iso: new Date().toISOString()
        })
      };

      act(() => {
        result.current.onMessage(translationEvent);
      });

      await waitFor(() => {
        expect(result.current.lines).toHaveLength(1);
      }, { timeout: 500 });

      expect(result.current.lines[0][1].translation.text).toBe('Hello world');
    }
  });

  it('should handle STT messages with translation in same segment', async () => {
    const { result } = renderHook(() =>
      useRoomWebSocket({
        myLanguage: 'en-US',
        userEmail: 'test@example.com'
      })
    );

    // STT partial
    const sttEvent = {
      data: JSON.stringify({
        type: 'stt_partial',
        segment_id: 1,
        text: 'Witaj świecie',
        lang: 'pl',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    // Translation partial
    const translationEvent = {
      data: JSON.stringify({
        type: 'translation_partial',
        segment_id: 1,
        tgt: 'en',
        src: 'pl',
        text: 'Hello world',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    act(() => {
      result.current.onMessage(sttEvent);
      result.current.onMessage(translationEvent);
    });

    // Should have 1 segment with both source and translation
    await waitFor(() => {
      expect(result.current.lines).toHaveLength(1);
    }, { timeout: 500 });

    expect(result.current.lines[0][1].source.text).toBe('Witaj świecie');
    expect(result.current.lines[0][1].translation.text).toBe('Hello world');
  });

  it('should handle null or undefined language gracefully', () => {
    const { result } = renderHook(() =>
      useRoomWebSocket({
        myLanguage: null,
        userEmail: 'test@example.com'
      })
    );

    const translationEvent = {
      data: JSON.stringify({
        type: 'translation_partial',
        segment_id: 1,
        tgt: 'en',
        src: 'pl',
        text: 'Hello world',
        final: false,
        speaker: 'speaker@example.com',
        ts_iso: new Date().toISOString()
      })
    };

    // Should not crash
    expect(() => {
      act(() => {
        result.current.onMessage(translationEvent);
      });
    }).not.toThrow();
  });
});
