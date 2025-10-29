/**
 * Tests for usePresenceWebSocket hook
 *
 * This hook manages:
 * - Persistent presence WebSocket connection
 * - Presence events (user_joined, user_left, language_changed, presence_snapshot)
 * - Network monitoring (ping/pong, RTT, quality)
 * - Participant and language count updates
 * - Welcome banner and toast notifications
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import usePresenceWebSocket from './usePresenceWebSocket';

// Mock WebSocket
class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = WebSocket.CONNECTING;
    this.onopen = null;
    this.onmessage = null;
    this.onerror = null;
    this.onclose = null;
    MockWebSocket.instances.push(this);

    // Simulate connection after a tick
    setTimeout(() => {
      this.readyState = WebSocket.OPEN;
      if (this.onopen) this.onopen(new Event('open'));
    }, 0);
  }

  send(data) {
    MockWebSocket.sentMessages.push(data);
  }

  close() {
    this.readyState = WebSocket.CLOSED;
    if (this.onclose) this.onclose(new Event('close'));
  }

  // Helper to simulate receiving a message
  simulateMessage(data) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
    }
  }

  // Helper to simulate error
  simulateError(error) {
    if (this.onerror) {
      this.onerror(error);
    }
  }

  static instances = [];
  static sentMessages = [];

  static reset() {
    MockWebSocket.instances = [];
    MockWebSocket.sentMessages = [];
  }

  static getLastInstance() {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1];
  }
}

// Mock constants for WebSocket readyState
MockWebSocket.CONNECTING = 0;
MockWebSocket.OPEN = 1;
MockWebSocket.CLOSING = 2;
MockWebSocket.CLOSED = 3;

global.WebSocket = MockWebSocket;

describe('usePresenceWebSocket', () => {
  let mockLocation;

  beforeEach(() => {
    MockWebSocket.reset();
    vi.useFakeTimers();

    // Mock window.location
    mockLocation = {
      protocol: 'https:',
      host: 'test.example.com'
    };
    Object.defineProperty(window, 'location', {
      value: mockLocation,
      writable: true
    });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  describe('Connection Management', () => {
    it('should establish WebSocket connection on mount', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(MockWebSocket.instances).toHaveLength(1);
      const ws = MockWebSocket.getLastInstance();
      expect(ws.url).toContain('wss://test.example.com/ws/rooms/test-room');
      expect(ws.url).toContain('token=test-token');
      expect(result.current.isConnected).toBe(true);
    });

    it('should use wss:// protocol for https pages', async () => {
      mockLocation.protocol = 'https:';

      renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();
      expect(ws.url).toMatch(/^wss:/);
    });

    it('should use ws:// protocol for http pages', async () => {
      mockLocation.protocol = 'http:';

      renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();
      expect(ws.url).toMatch(/^ws:/);
    });

    it('should use guest token when isGuest is true', async () => {
      sessionStorage.setItem('guest_token', 'guest-abc-123');

      renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'regular-token',
          isGuest: true
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();
      expect(ws.url).toContain('token=guest-abc-123');
      expect(ws.url).not.toContain('regular-token');
    });

    it('should not connect without token', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: null,
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      expect(MockWebSocket.instances).toHaveLength(0);
      expect(result.current.isConnected).toBe(false);
    });

    it('should close WebSocket on unmount', async () => {
      const { unmount } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();
      const closeSpy = vi.spyOn(ws, 'close');

      unmount();

      expect(closeSpy).toHaveBeenCalled();
    });

    it('should send initial language preference on connection', async () => {
      renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false,
          initialLanguage: 'pl'
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const messages = MockWebSocket.sentMessages.map(JSON.parse);
      const languageMessage = messages.find(m => m.type === 'set_language');

      expect(languageMessage).toBeDefined();
      expect(languageMessage.language).toBe('pl');
    });
  });

  describe('Presence Events', () => {
    it('should handle presence_snapshot event', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        ws.simulateMessage({
          type: 'presence_snapshot',
          room_id: 'test-room',
          participants: [
            { user_id: '1', display_name: 'Alice', language: 'en', is_guest: false },
            { user_id: '2', display_name: 'Bob', language: 'pl', is_guest: false }
          ],
          language_counts: { en: 1, pl: 1 },
          timestamp: '2025-10-28T12:00:00Z'
        });
      });

      expect(result.current.participants).toHaveLength(2);
      expect(result.current.participants[0].display_name).toBe('Alice');
      expect(result.current.languageCounts).toEqual({ en: 1, pl: 1 });
      expect(result.current.showWelcome).toBe(true);
    });

    it('should auto-dismiss welcome banner after 10 seconds', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        ws.simulateMessage({
          type: 'presence_snapshot',
          participants: [],
          language_counts: {}
        });
      });

      expect(result.current.showWelcome).toBe(true);

      await act(async () => {
        vi.advanceTimersByTime(10000);
      });

      expect(result.current.showWelcome).toBe(false);
    });

    it('should handle user_joined event with notification', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        ws.simulateMessage({
          type: 'user_joined',
          room_id: 'test-room',
          triggered_by_user_id: '123',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'en', is_guest: false }
          ],
          language_counts: { en: 1 }
        });
      });

      expect(result.current.participants).toHaveLength(1);
      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0].message).toContain('Charlie');
      expect(result.current.notifications[0].message).toContain('joined');
    });

    it('should handle user_left event with notification', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        ws.simulateMessage({
          type: 'user_left',
          room_id: 'test-room',
          triggered_by_user_id: '123',
          left_user: {
            user_id: '123',
            display_name: 'Charlie',
            language: 'en',
            is_guest: false
          },
          participants: [],
          language_counts: {}
        });
      });

      expect(result.current.participants).toHaveLength(0);
      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0].message).toContain('Charlie');
      expect(result.current.notifications[0].message).toContain('left');
    });

    it('should handle language_changed event with notification', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        ws.simulateMessage({
          type: 'language_changed',
          room_id: 'test-room',
          triggered_by_user_id: '123',
          old_language: 'en',
          new_language: 'ar',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'ar', is_guest: false }
          ],
          language_counts: { ar: 1 }
        });
      });

      expect(result.current.participants[0].language).toBe('ar');
      expect(result.current.notifications).toHaveLength(1);
      expect(result.current.notifications[0].message).toContain('Charlie');
      expect(result.current.notifications[0].message).toContain('changed');
    });

    it('should auto-dismiss notifications after 5 seconds', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        ws.simulateMessage({
          type: 'user_joined',
          triggered_by_user_id: '123',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'en', is_guest: false }
          ],
          language_counts: { en: 1 }
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      expect(result.current.notifications).toHaveLength(0);
    });

    it('should debounce join/leave notifications (10s cooldown)', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      // First join - should show
      act(() => {
        ws.simulateMessage({
          type: 'user_joined',
          triggered_by_user_id: '123',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'en', is_guest: false }
          ],
          language_counts: { en: 1 }
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      // Second join within 10s - should not show
      act(() => {
        ws.simulateMessage({
          type: 'user_joined',
          triggered_by_user_id: '123',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'en', is_guest: false }
          ],
          language_counts: { en: 1 }
        });
      });

      expect(result.current.notifications).toHaveLength(1); // Still 1

      // Wait 11 seconds
      await act(async () => {
        vi.advanceTimersByTime(11000);
      });

      // Third join after cooldown - should show
      act(() => {
        ws.simulateMessage({
          type: 'user_joined',
          triggered_by_user_id: '123',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'en', is_guest: false }
          ],
          language_counts: { en: 1 }
        });
      });

      expect(result.current.notifications).toHaveLength(1); // New notification (old one auto-dismissed)
    });

    it('should NOT debounce language_changed notifications', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      // First language change
      act(() => {
        ws.simulateMessage({
          type: 'language_changed',
          triggered_by_user_id: '123',
          old_language: 'en',
          new_language: 'ar',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'ar', is_guest: false }
          ],
          language_counts: { ar: 1 }
        });
      });

      expect(result.current.notifications).toHaveLength(1);

      // Second language change immediately - should still show
      act(() => {
        ws.simulateMessage({
          type: 'language_changed',
          triggered_by_user_id: '123',
          old_language: 'ar',
          new_language: 'pl',
          participants: [
            { user_id: '123', display_name: 'Charlie', language: 'pl', is_guest: false }
          ],
          language_counts: { pl: 1 }
        });
      });

      expect(result.current.notifications).toHaveLength(2);
    });

    it('should keep last 3 notifications only', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      // Send 5 notifications
      for (let i = 1; i <= 5; i++) {
        act(() => {
          ws.simulateMessage({
            type: 'language_changed', // Use language_changed to bypass debounce
            triggered_by_user_id: `user-${i}`,
            old_language: 'en',
            new_language: 'pl',
            participants: [
              { user_id: `user-${i}`, display_name: `User${i}`, language: 'pl', is_guest: false }
            ],
            language_counts: { pl: 1 }
          });
        });
      }

      // Should only keep last 3
      expect(result.current.notifications).toHaveLength(3);
      expect(result.current.notifications[0].message).toContain('User3');
      expect(result.current.notifications[1].message).toContain('User4');
      expect(result.current.notifications[2].message).toContain('User5');
    });
  });

  describe('Network Monitoring', () => {
    it('should start network monitoring on connection', async () => {
      renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // Should send initial ping
      const messages = MockWebSocket.sentMessages.map(JSON.parse);
      const pingMessage = messages.find(m => m.type === 'ping');
      expect(pingMessage).toBeDefined();
      expect(pingMessage.timestamp).toBeDefined();
    });

    it('should send ping every 2 seconds', async () => {
      renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      MockWebSocket.sentMessages = []; // Clear initial messages

      // Advance 6 seconds (should send 3 pings)
      await act(async () => {
        vi.advanceTimersByTime(6000);
      });

      const messages = MockWebSocket.sentMessages.map(JSON.parse);
      const pingMessages = messages.filter(m => m.type === 'ping');
      expect(pingMessages.length).toBeGreaterThanOrEqual(3);
    });

    it('should calculate RTT from pong response', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      // Get ping timestamp
      const messages = MockWebSocket.sentMessages.map(JSON.parse);
      const pingMessage = messages.find(m => m.type === 'ping');

      // Simulate pong response after 100ms
      await act(async () => {
        vi.advanceTimersByTime(100);
        ws.simulateMessage({
          type: 'pong',
          timestamp: pingMessage.timestamp
        });
      });

      expect(result.current.networkRTT).toBeGreaterThan(0);
      expect(result.current.networkRTT).toBeLessThan(200);
    });

    it('should classify network quality as high (<150ms)', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      // Simulate 5 fast pongs (need 5 for moving average)
      for (let i = 0; i < 5; i++) {
        const messages = MockWebSocket.sentMessages.map(JSON.parse);
        const pingMessage = messages[messages.length - 1];

        await act(async () => {
          vi.advanceTimersByTime(50); // 50ms RTT
          ws.simulateMessage({
            type: 'pong',
            timestamp: pingMessage.timestamp
          });
          vi.advanceTimersByTime(1950);
        });
      }

      expect(result.current.networkQuality).toBe('high');
    });

    it('should classify network quality as medium (150-400ms)', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      // Simulate 5 medium-speed pongs
      for (let i = 0; i < 5; i++) {
        const messages = MockWebSocket.sentMessages.map(JSON.parse);
        const pingMessage = messages[messages.length - 1];

        await act(async () => {
          vi.advanceTimersByTime(250); // 250ms RTT
          ws.simulateMessage({
            type: 'pong',
            timestamp: pingMessage.timestamp
          });
          vi.advanceTimersByTime(1750);
        });
      }

      expect(result.current.networkQuality).toBe('medium');
    });

    it('should classify network quality as low (>400ms)', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      // Simulate 5 slow pongs
      for (let i = 0; i < 5; i++) {
        const messages = MockWebSocket.sentMessages.map(JSON.parse);
        const pingMessage = messages[messages.length - 1];

        await act(async () => {
          vi.advanceTimersByTime(500); // 500ms RTT
          ws.simulateMessage({
            type: 'pong',
            timestamp: pingMessage.timestamp
          });
          vi.advanceTimersByTime(1500);
        });
      }

      expect(result.current.networkQuality).toBe('low');
    });

    it('should handle ping timeout (5s)', async () => {
      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      // Wait 5 seconds without pong
      await act(async () => {
        vi.advanceTimersByTime(5000);
      });

      // Should record degraded network (5000ms RTT)
      expect(result.current.networkQuality).toBe('low');
    });

    it('should stop network monitoring on unmount', async () => {
      const { unmount } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      unmount();

      // Should clear intervals (no more pings sent)
      const messageCountBefore = MockWebSocket.sentMessages.length;

      await act(async () => {
        vi.advanceTimersByTime(10000);
      });

      expect(MockWebSocket.sentMessages.length).toBe(messageCountBefore);
    });
  });

  describe('Language Updates', () => {
    it('should send language update when language changes', async () => {
      const { result, rerender } = renderHook(
        ({ myLanguage }) =>
          usePresenceWebSocket({
            roomId: 'test-room',
            token: 'test-token',
            isGuest: false,
            myLanguage
          }),
        { initialProps: { myLanguage: 'en' } }
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      MockWebSocket.sentMessages = []; // Clear initial messages

      // Change language
      rerender({ myLanguage: 'pl' });

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const messages = MockWebSocket.sentMessages.map(JSON.parse);
      const languageMessage = messages.find(m => m.type === 'set_language' && m.language === 'pl');
      expect(languageMessage).toBeDefined();
    });

    it('should not send language update if WebSocket not connected', async () => {
      const { rerender } = renderHook(
        ({ myLanguage }) =>
          usePresenceWebSocket({
            roomId: 'test-room',
            token: 'test-token',
            isGuest: false,
            myLanguage
          }),
        { initialProps: { myLanguage: 'en' } }
      );

      // Don't wait for connection
      MockWebSocket.sentMessages = [];

      // Change language before connection
      rerender({ myLanguage: 'pl' });

      const messages = MockWebSocket.sentMessages.map(JSON.parse);
      expect(messages.filter(m => m.type === 'set_language')).toHaveLength(0);
    });
  });

  describe('Error Handling', () => {
    it('should handle WebSocket errors gracefully', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { result } = renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        ws.simulateError(new Error('Connection failed'));
      });

      // Should handle error without crashing
      expect(result.current.isConnected).toBe(true); // Still marked as connected until close

      consoleErrorSpy.mockRestore();
    });

    it('should handle malformed JSON messages', async () => {
      const consoleLogSpy = vi.spyOn(console, 'log').mockImplementation(() => {});

      renderHook(() =>
        usePresenceWebSocket({
          roomId: 'test-room',
          token: 'test-token',
          isGuest: false
        })
      );

      await act(async () => {
        await vi.runAllTimersAsync();
      });

      const ws = MockWebSocket.getLastInstance();

      act(() => {
        if (ws.onmessage) {
          ws.onmessage({ data: 'invalid json{{{' });
        }
      });

      // Should handle error without crashing
      expect(consoleLogSpy).toHaveBeenCalled();

      consoleLogSpy.mockRestore();
    });
  });
});
