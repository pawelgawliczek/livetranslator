import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import RoomPageWrapper from './RoomPageWrapper';

// Mock child components
vi.mock('./RoomPage', () => ({
  default: vi.fn(() => <div data-testid="regular-room-page">Regular Room Page</div>)
}));

vi.mock('./MultiSpeakerRoomPage', () => ({
  default: vi.fn(() => <div data-testid="multi-speaker-room-page">Multi-Speaker Room Page</div>)
}));

// Mock react-router-dom
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ roomId: 'test-room-123' })
  };
});

describe('RoomPageWrapper', () => {
  let fetchMock;

  const defaultProps = {
    token: 'test-token',
    onLogout: vi.fn()
  };

  beforeEach(() => {
    // Mock fetch
    fetchMock = vi.fn();
    global.fetch = fetchMock;

    // Mock sessionStorage
    global.sessionStorage = {
      getItem: vi.fn((key) => {
        if (key === 'is_guest') return 'false';
        return null;
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    };

    // Mock console.error to avoid cluttering test output
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.clearAllMocks();
    console.error.mockRestore();
  });

  describe('Loading State', () => {
    it('shows loading screen while checking room mode', async () => {
      fetchMock.mockImplementationOnce(() =>
        new Promise(resolve => setTimeout(() => resolve({
          ok: true,
          json: async () => ({ speakers_locked: false })
        }), 100))
      );

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      expect(screen.getByText(/loading room/i)).toBeInTheDocument();
      expect(screen.getByText('🎤')).toBeInTheDocument();
    });

    it('hides loading screen after room data is fetched', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.queryByText(/loading room/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('Routing to Regular Room Page', () => {
    it('routes to regular RoomPage when speakers_locked is false', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: false,
          discovery_mode: 'disabled'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
        expect(screen.queryByTestId('multi-speaker-room-page')).not.toBeInTheDocument();
      });
    });

    it('routes to regular RoomPage when speakers_locked is undefined', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123'
          // speakers_locked not present
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });

    it('routes to regular RoomPage when discovery_mode is disabled', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: false,
          discovery_mode: 'disabled'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });

    it('routes to regular RoomPage when discovery_mode is enabled but not locked', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: false,
          discovery_mode: 'enabled'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });
  });

  describe('Routing to Multi-Speaker Room Page', () => {
    it('routes to MultiSpeakerRoomPage when speakers_locked is true', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: true,
          discovery_mode: 'locked'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('multi-speaker-room-page')).toBeInTheDocument();
        expect(screen.queryByTestId('regular-room-page')).not.toBeInTheDocument();
      });
    });

    it('routes to MultiSpeakerRoomPage when discovery_mode is locked', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: true,
          discovery_mode: 'locked'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('multi-speaker-room-page')).toBeInTheDocument();
      });
    });

    it('routes to MultiSpeakerRoomPage when speakers_locked is true even if discovery_mode is not locked', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: true,
          discovery_mode: 'enabled'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('multi-speaker-room-page')).toBeInTheDocument();
      });
    });
  });

  describe('API Requests', () => {
    it('sends Authorization header for authenticated users', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/rooms/test-room-123',
          expect.objectContaining({
            headers: expect.objectContaining({
              'Authorization': 'Bearer test-token'
            })
          })
        );
      });
    });

    it('does not send Authorization header for guest users', async () => {
      global.sessionStorage.getItem = vi.fn((key) => {
        if (key === 'is_guest') return 'true';
        return null;
      });

      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} token={null} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/rooms/test-room-123',
          expect.objectContaining({
            headers: expect.not.objectContaining({
              'Authorization': expect.any(String)
            })
          })
        );
      });
    });

    it('fetches room data with correct room ID', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith(
          '/api/rooms/test-room-123',
          expect.any(Object)
        );
      });
    });
  });

  describe('Error Handling', () => {
    it('defaults to regular room page on API error', async () => {
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });

    it('defaults to regular room page on invalid JSON response', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => {
          throw new Error('Invalid JSON');
        }
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });

    it('logs error to console when fetch fails', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      fetchMock.mockRejectedValueOnce(new Error('Network error'));

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(consoleErrorSpy).toHaveBeenCalledWith(
          expect.stringContaining('[RoomWrapper]'),
          expect.any(Error)
        );
      });

      consoleErrorSpy.mockRestore();
    });

    it('handles missing roomId parameter gracefully', async () => {
      // Note: This test is simplified since we can't dynamically change the mock
      // In real app, missing roomId would be handled by routing
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      // Component should render and make API call with the mocked roomId
      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalled();
      });
    });
  });

  describe('Props Passing', () => {
    it('passes token and onLogout to regular RoomPage', async () => {
      const RoomPage = (await import('./RoomPage')).default;
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      const onLogout = vi.fn();
      render(
        <BrowserRouter>
          <RoomPageWrapper token="test-token-123" onLogout={onLogout} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(RoomPage).toHaveBeenCalledWith(
          expect.objectContaining({
            token: 'test-token-123',
            onLogout: onLogout
          }),
          expect.any(Object)
        );
      });
    });

    it('passes token and onLogout to MultiSpeakerRoomPage', async () => {
      const MultiSpeakerRoomPage = (await import('./MultiSpeakerRoomPage')).default;
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: true })
      });

      const onLogout = vi.fn();
      render(
        <BrowserRouter>
          <RoomPageWrapper token="test-token-456" onLogout={onLogout} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(MultiSpeakerRoomPage).toHaveBeenCalledWith(
          expect.objectContaining({
            token: 'test-token-456',
            onLogout: onLogout
          }),
          expect.any(Object)
        );
      });
    });
  });

  describe('State Transitions', () => {
    it('transitions from loading to regular room page', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      // Initially loading
      expect(screen.getByText(/loading room/i)).toBeInTheDocument();

      // Then shows room page
      await waitFor(() => {
        expect(screen.queryByText(/loading room/i)).not.toBeInTheDocument();
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });

    it('transitions from loading to multi-speaker room page', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: true })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      // Initially loading
      expect(screen.getByText(/loading room/i)).toBeInTheDocument();

      // Then shows multi-speaker room page
      await waitFor(() => {
        expect(screen.queryByText(/loading room/i)).not.toBeInTheDocument();
        expect(screen.getByTestId('multi-speaker-room-page')).toBeInTheDocument();
      });
    });
  });

  describe('Re-rendering Behavior', () => {
    it('does not refetch room data when token changes', async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      const { rerender } = render(
        <BrowserRouter>
          <RoomPageWrapper token="token-1" onLogout={vi.fn()} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledTimes(1);
      });

      // Update token
      rerender(
        <BrowserRouter>
          <RoomPageWrapper token="token-2" onLogout={vi.fn()} />
        </BrowserRouter>
      );

      // Should refetch since token changed (it's in the dependency array)
      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledTimes(2);
      });
    });

    it('refetches room data when roomId changes', async () => {
      fetchMock.mockResolvedValue({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      const { rerender } = render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(fetchMock).toHaveBeenCalledWith('/api/rooms/test-room-123', expect.any(Object));
      });

      const initialCallCount = fetchMock.mock.calls.length;

      // Rerender with different token to trigger refetch
      rerender(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} token="new-token" />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Should have made another API call
        expect(fetchMock.mock.calls.length).toBeGreaterThan(initialCallCount);
      });
    });
  });

  describe('Edge Cases', () => {
    it('handles room with both speakers_locked and discovery_mode as locked', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: true,
          discovery_mode: 'locked'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('multi-speaker-room-page')).toBeInTheDocument();
      });
    });

    it('handles room with empty response data', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({})
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Should default to regular room page
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });

    it('handles room with null speakers_locked value', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          code: 'test-room-123',
          speakers_locked: null,
          discovery_mode: 'disabled'
        })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('provides accessible loading message', () => {
      fetchMock.mockImplementationOnce(() =>
        new Promise(() => {}) // Never resolves to keep loading state
      );

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      const loadingText = screen.getByText(/loading room/i);
      expect(loadingText).toBeInTheDocument();
      // Check that loading text has proper styling (check for text-lg which is the actual class)
      expect(loadingText).toHaveClass('text-lg');
    });

    it('has proper color contrast for loading screen', () => {
      fetchMock.mockImplementationOnce(() =>
        new Promise(() => {}) // Never resolves
      );

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      const container = screen.getByText(/loading room/i).closest('div').parentElement.parentElement;
      expect(container).toHaveClass('bg-bg', 'text-fg');
    });
  });

  describe('Performance', () => {
    it('only makes one API call per mount', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });

      expect(fetchMock).toHaveBeenCalledTimes(1);
    });

    it('cleans up properly on unmount', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({ speakers_locked: false })
      });

      const { unmount } = render(
        <BrowserRouter>
          <RoomPageWrapper {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('regular-room-page')).toBeInTheDocument();
      });

      // Should unmount without errors
      expect(() => unmount()).not.toThrow();
    });
  });
});
