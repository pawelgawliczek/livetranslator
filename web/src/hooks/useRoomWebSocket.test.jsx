/**
 * Tests for useRoomWebSocket hook
 *
 * This hook manages:
 * - Message processing (STT partial/final, translation partial/final)
 * - Placeholder management for speaking indicators
 * - Segment rendering and deduplication
 * - Message filtering and sorting
 * - Auto-scroll support
 *
 * HIGH RISK: Complex message ordering, placeholder management, and state synchronization
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import useRoomWebSocket from './useRoomWebSocket';

describe('useRoomWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Message Processing', () => {
    it('should process stt_partial messages', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_partial',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: false,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300); // Debounce render
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.text).toBe('Hello');
      expect(result.current.lines[0][1].source.final).toBe(false);
    });

    it('should process stt_final messages', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 1,
            text: 'Hello world',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            processing: false,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.text).toBe('Hello world');
      expect(result.current.lines[0][1].source.final).toBe(true);
    });

    it('should replace partial with final when segment_id matches', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send partial
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_partial',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: false,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines[0][1].source.final).toBe(false);

      // Send final with same segment_id
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 1,
            text: 'Hello world',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1); // Still one message
      expect(result.current.lines[0][1].source.text).toBe('Hello world'); // Updated text
      expect(result.current.lines[0][1].source.final).toBe(true); // Now final
    });

    it('should process translation_partial messages', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'pl',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'translation_partial',
            segment_id: 1,
            text: 'Witaj',
            src: 'en',
            tgt: 'pl',
            final: false,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].translation.text).toBe('Witaj');
      expect(result.current.lines[0][1].translation.final).toBe(false);
    });

    it('should only store translations matching myLanguage', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'pl', // User wants Polish
          userEmail: 'test@example.com'
        })
      );

      // Send English translation (should be ignored)
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'translation_final',
            segment_id: 1,
            text: 'Hello',
            src: 'pl',
            tgt: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(0); // Not shown (wrong language)

      // Send Polish translation (should be stored)
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'translation_final',
            segment_id: 1,
            text: 'Witaj',
            src: 'en',
            tgt: 'pl',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].translation.text).toBe('Witaj');
    });

    it('should handle stt_finalize messages', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send partial
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_partial',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: false,
            processing: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines[0][1].source.final).toBe(false);
      expect(result.current.lines[0][1].source.processing).toBe(true);

      // Send finalize marker
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_finalize',
            segment_id: 1,
            backend_timestamp: Date.now() / 1000
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines[0][1].source.final).toBe(true);
      expect(result.current.lines[0][1].source.processing).toBe(false);
    });

    it('should skip messages with empty text', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 1,
            text: '',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(0); // Empty text skipped
    });

    it('should skip messages without text field', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 1,
            // No text field
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(0);
    });

    it('should auto-generate segment_id if missing', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            // No segment_id
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: true
            // No ts_iso
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.segment_id).toBeDefined();
      expect(result.current.lines[0][1].source.ts_iso).toBeDefined();
    });
  });

  describe('Placeholder Management', () => {
    it('should handle speech_started event', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'speech_started',
            segment_id: 1,
            speaker: 'test@example.com'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.text).toBe('___SPEAKING___');
      expect(result.current.lines[0][1].source.is_placeholder).toBe(true);
    });

    it('should remove placeholder when real text arrives', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send speech_started
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'speech_started',
            segment_id: 1,
            speaker: 'test@example.com'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.is_placeholder).toBe(true);

      // Send real text with same segment_id
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_partial',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: false,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.text).toBe('Hello');
      expect(result.current.lines[0][1].source.is_placeholder).toBe(false);
    });

    it('should auto-remove stale placeholder after 5 seconds', async () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send speech_started
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'speech_started',
            segment_id: 1,
            speaker: 'test@example.com'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);

      // Wait 5 seconds (no real text arrives)
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      // Additional render cycle
      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(0); // Placeholder removed
    });

    it('should not remove placeholder if it was replaced by real text', async () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send speech_started
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'speech_started',
            segment_id: 1,
            speaker: 'test@example.com'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Send real text
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_partial',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: false,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Wait 5 seconds
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      await act(async () => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.text).toBe('Hello'); // Real text still there
    });
  });

  describe('Segment Rendering', () => {
    it('should merge source and translation for same segment', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'pl',
          userEmail: 'test@example.com'
        })
      );

      // Send source
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      // Send translation
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'translation_final',
            segment_id: 1,
            text: 'Witaj',
            src: 'en',
            tgt: 'pl',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].source.text).toBe('Hello');
      expect(result.current.lines[0][1].translation.text).toBe('Witaj');
    });

    it('should sort segments by timestamp', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send segments in reverse order
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 3,
            text: 'Third',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:03Z'
          })
        });
      });

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 1,
            text: 'First',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:01Z'
          })
        });
      });

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 2,
            text: 'Second',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:02Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(3);
      expect(result.current.lines[0][1].source.text).toBe('First');
      expect(result.current.lines[1][1].source.text).toBe('Second');
      expect(result.current.lines[2][1].source.text).toBe('Third');
    });

    it('should keep last 100 segments only', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send 150 messages
      act(() => {
        for (let i = 1; i <= 150; i++) {
          result.current.onMessage({
            data: JSON.stringify({
              type: 'stt_final',
              segment_id: i,
              text: `Message ${i}`,
              speaker: 'test@example.com',
              lang: 'en',
              final: true,
              ts_iso: `2025-10-28T12:00:${String(i).padStart(2, '0')}Z`
            })
          });
        }
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      expect(result.current.lines).toHaveLength(100); // Only last 100
      expect(result.current.lines[0][1].source.text).toBe('Message 51'); // First is #51
      expect(result.current.lines[99][1].source.text).toBe('Message 150'); // Last is #150
    });

    it('should debounce rendering (200ms)', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      // Send multiple messages quickly
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_partial',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: false,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      // Render not triggered yet
      expect(result.current.lines).toHaveLength(0);

      act(() => {
        vi.advanceTimersByTime(199); // Just before 200ms
      });

      // Still not rendered
      expect(result.current.lines).toHaveLength(0);

      act(() => {
        vi.advanceTimersByTime(1); // Now 200ms passed
      });

      // Now rendered
      expect(result.current.lines).toHaveLength(1);
    });
  });

  describe('Error Handling', () => {
    it('should handle malformed JSON gracefully', () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: 'invalid json{{{'
        });
      });

      // Should not crash
      expect(result.current.lines).toHaveLength(0);
      expect(consoleErrorSpy).toHaveBeenCalled();

      consoleErrorSpy.mockRestore();
    });

    it('should handle messages without type field', () => {
      const { result } = renderHook(() =>
        useRoomWebSocket({
          myLanguage: 'en',
          userEmail: 'test@example.com'
        })
      );

      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            // No type field
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Should be ignored
      expect(result.current.lines).toHaveLength(0);
    });
  });

  describe('Language Change', () => {
    it('should update displayed translations when myLanguage changes', () => {
      const { result, rerender } = renderHook(
        ({ myLanguage }) =>
          useRoomWebSocket({
            myLanguage,
            userEmail: 'test@example.com'
          }),
        { initialProps: { myLanguage: 'pl' } }
      );

      // Send source
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'stt_final',
            segment_id: 1,
            text: 'Hello',
            speaker: 'test@example.com',
            lang: 'en',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      // Send Polish translation
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'translation_final',
            segment_id: 1,
            text: 'Witaj',
            src: 'en',
            tgt: 'pl',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      // Send Arabic translation
      act(() => {
        result.current.onMessage({
          data: JSON.stringify({
            type: 'translation_final',
            segment_id: 1,
            text: 'مرحبا',
            src: 'en',
            tgt: 'ar',
            final: true,
            ts_iso: '2025-10-28T12:00:00Z'
          })
        });
      });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Should show Polish translation
      expect(result.current.lines).toHaveLength(1);
      expect(result.current.lines[0][1].translation.text).toBe('Witaj');

      // Change language to Arabic
      rerender({ myLanguage: 'ar' });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Should now show Arabic translation
      expect(result.current.lines[0][1].translation.text).toBe('مرحبا');
    });
  });
});
