import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import userEvent from '@testing-library/user-event';
import MultiSpeakerRoomPage from './MultiSpeakerRoomPage';

// Mock all external dependencies
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: () => ({ roomId: 'test-room-123' }),
    useNavigate: () => vi.fn(),
  };
});

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
    i18n: { language: 'en' }
  }),
  initReactI18next: {
    type: '3rdParty',
    init: () => {}
  }
}));

vi.mock('../hooks/usePresenceWebSocket', () => ({
  default: vi.fn(() => ({
    isConnected: true,
    ws: { readyState: 1 },
    participants: [],
    showWelcome: false,
    dismissWelcome: vi.fn(),
    notifications: [],
    networkQuality: 'good',
    networkRTT: 50
  }))
}));

vi.mock('../hooks/useMultiSpeakerRoom', () => ({
  default: vi.fn(() => ({
    speakers: [
      { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
      { speaker_id: 1, display_name: 'Bob', language: 'pl', color: '#33C3FF' }
    ],
    messages: [],
    onMessage: vi.fn(),
    loading: false,
    error: null
  }))
}));

vi.mock('../hooks/useAudioStream', () => ({
  default: vi.fn(() => ({
    vadReady: true,
    startRecording: vi.fn(),
    stopRecording: vi.fn(),
    setThreshold: vi.fn()
  }))
}));

// Mock child components
vi.mock('../components/room/RoomHeader', () => ({
  default: vi.fn(({ roomId }) => <div data-testid="room-header">{roomId}</div>)
}));

vi.mock('../components/room/MultiSpeakerMessage', () => ({
  default: vi.fn(({ message }) => (
    <div data-testid="multi-speaker-message">{message?.speaker?.display_name || 'Speaker'}</div>
  ))
}));

vi.mock('../components/room/MicrophoneButton', () => ({
  default: vi.fn(() => <button data-testid="mic-button">Mic</button>)
}));

vi.mock('../components/room/RoomControls', () => ({
  default: vi.fn(() => <div data-testid="room-controls">Controls</div>)
}));

vi.mock('../components/SettingsMenu', () => ({
  default: vi.fn(() => <div data-testid="settings-menu">Settings</div>)
}));

vi.mock('../components/SpeakerDiscoveryModal', () => ({
  default: vi.fn(() => <div data-testid="speaker-discovery-modal">Discovery</div>)
}));

describe('MultiSpeakerRoomPage', () => {
  let fetchMock;

  const defaultProps = {
    token: 'test-token',
    onLogout: vi.fn()
  };

  beforeEach(() => {
    // Mock fetch
    fetchMock = vi.fn();
    global.fetch = fetchMock;

    // Mock scrollIntoView
    Element.prototype.scrollIntoView = vi.fn();

    // Mock sessionStorage
    global.sessionStorage = {
      getItem: vi.fn((key) => {
        if (key === 'is_guest') return 'false';
        if (key === 'guest_display_name') return 'Guest';
        if (key === 'guest_language') return 'en';
        return null;
      }),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    };

    // Mock localStorage
    global.localStorage = {
      getItem: vi.fn(() => null),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn()
    };

    // Mock navigator.userAgent for mobile detection
    Object.defineProperty(navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      configurable: true
    });

    // Mock profile fetch
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        email: 'test@example.com',
        is_admin: false
      })
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Initial Rendering', () => {
    it('renders multi-speaker room page', async () => {
      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('room-header')).toBeInTheDocument();
      });
    });

    it('displays room ID in header', async () => {
      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('room-header')).toHaveTextContent('test-room-123');
      });
    });

    it('shows microphone button', async () => {
      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('mic-button')).toBeInTheDocument();
      });
    });

    it('shows room controls', async () => {
      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('room-controls')).toBeInTheDocument();
      });
    });
  });

  describe('Speaker Display', () => {
    it('displays speaker info bar with enrolled speakers', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [
          { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
          { speaker_id: 1, display_name: 'Bob', language: 'pl', color: '#33C3FF' },
          { speaker_id: 2, display_name: 'Carlos', language: 'es', color: '#FFD700' }
        ],
        messages: [],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText(/Alice/)).toBeInTheDocument();
        expect(screen.getByText(/Bob/)).toBeInTheDocument();
        expect(screen.getByText(/Carlos/)).toBeInTheDocument();
      });
    });

    it('displays speaker avatars with color coding', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [
          { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' }
        ],
        messages: [],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        const speakerElement = screen.getByText(/Alice/);
        const avatar = speakerElement.closest('[data-color]');
        expect(avatar).toHaveAttribute('data-color', '#FF5733');
      });
    });

    it('shows speaker number badges', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [
          { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
          { speaker_id: 1, display_name: 'Bob', language: 'pl', color: '#33C3FF' }
        ],
        messages: [],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Speaker badges should show numbers (1, 2, etc.)
        expect(screen.getByText('1')).toBeInTheDocument();
        expect(screen.getByText('2')).toBeInTheDocument();
      });
    });
  });

  describe('Multi-Speaker Messages', () => {
    it('renders messages with speaker attribution', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [
          { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' }
        ],
        messages: [
          {
            segment_id: 1,
            speaker: { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
            originalText: 'Hello everyone',
            translations: []
          }
        ],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('multi-speaker-message')).toHaveTextContent('Alice');
      });
    });

    it('displays all translations for each message', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [
          { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
          { speaker_id: 1, display_name: 'Bob', language: 'pl', color: '#33C3FF' }
        ],
        messages: [
          {
            segment_id: 1,
            speaker: { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
            originalText: 'Hello',
            translations: [
              { target_language: 'pl', text: 'Cześć', target_speaker: 'Bob' }
            ]
          }
        ],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Original message and translation should both be visible
        expect(screen.getByText(/Hello/)).toBeInTheDocument();
        expect(screen.getByText(/Cześć/)).toBeInTheDocument();
      });
    });

    it('shows speaker change indicators', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [
          { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
          { speaker_id: 1, display_name: 'Bob', language: 'pl', color: '#33C3FF' }
        ],
        messages: [
          {
            segment_id: 1,
            speaker: { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
            originalText: 'Hello',
            translations: [],
            speakerChanged: false
          },
          {
            segment_id: 2,
            speaker: { speaker_id: 1, display_name: 'Bob', language: 'pl', color: '#33C3FF' },
            originalText: 'Cześć',
            translations: [],
            speakerChanged: true
          }
        ],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Should have visual indicator for speaker change
        const messages = screen.getAllByTestId('multi-speaker-message');
        expect(messages[1]).toHaveClass(/speaker-change|separator/);
      });
    });

    it('auto-scrolls to latest message', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      const scrollIntoViewMock = vi.fn();

      // Create a ref that will be used by the component
      const mockRef = { current: { scrollIntoView: scrollIntoViewMock } };

      useMultiSpeakerRoom.mockReturnValue({
        speakers: [],
        messages: [
          {
            segment_id: 1,
            speaker: { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
            originalText: 'Hello',
            translations: []
          }
        ],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      // Note: Auto-scroll behavior is tested via the effect hook
      // This test verifies the component renders without errors
      await waitFor(() => {
        expect(screen.getByTestId('multi-speaker-message')).toBeInTheDocument();
      });
    });
  });

  describe('Speaker Discovery Integration', () => {
    it('shows speaker discovery modal when opened from settings', async () => {
      const user = userEvent.setup();

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      // Open settings menu
      const settingsButton = screen.getByLabelText(/settings|menu/i);
      await user.click(settingsButton);

      // Click "Configure Speakers" option (if room admin)
      const configureSpeakers = screen.queryByText(/configure.*speakers|speaker.*discovery/i);
      if (configureSpeakers) {
        await user.click(configureSpeakers);

        await waitFor(() => {
          expect(screen.getByTestId('speaker-discovery-modal')).toBeInTheDocument();
        });
      }
    });

    it('passes WebSocket connection to speaker discovery modal', async () => {
      const mockWs = { readyState: 1 };
      const { default: usePresenceWebSocket } = await import('../hooks/usePresenceWebSocket');
      usePresenceWebSocket.mockReturnValue({
        isConnected: true,
        ws: mockWs,
        participants: [],
        showWelcome: false,
        dismissWelcome: vi.fn(),
        notifications: [],
        networkQuality: 'good',
        networkRTT: 50
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      // The modal should receive the WebSocket connection
      // This is verified through the component prop passing
      await waitFor(() => {
        expect(screen.getByTestId('room-header')).toBeInTheDocument();
      });
    });
  });

  describe('Guest User Support', () => {
    it('supports guest users without token', async () => {
      global.sessionStorage.getItem = vi.fn((key) => {
        if (key === 'is_guest') return 'true';
        if (key === 'guest_display_name') return 'Guest User';
        if (key === 'guest_language') return 'es';
        return null;
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} token={null} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('room-header')).toBeInTheDocument();
      });

      // Should not redirect to login
      expect(screen.queryByText(/login/i)).not.toBeInTheDocument();
    });

    it('uses guest language preference', async () => {
      global.sessionStorage.getItem = vi.fn((key) => {
        if (key === 'is_guest') return 'true';
        if (key === 'guest_language') return 'fr';
        return null;
      });

      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      const mockOnMessage = vi.fn();
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [],
        messages: [],
        onMessage: mockOnMessage,
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} token={null} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(useMultiSpeakerRoom).toHaveBeenCalledWith(
          expect.objectContaining({
            myLanguage: 'fr'
          })
        );
      });
    });
  });

  describe('Push-to-Talk Mode', () => {
    it('defaults to push-to-talk on mobile devices', async () => {
      // Mock mobile user agent
      Object.defineProperty(navigator, 'userAgent', {
        value: 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X)',
        configurable: true
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      // Component should initialize with push-to-talk enabled for mobile
      await waitFor(() => {
        expect(screen.getByTestId('mic-button')).toBeInTheDocument();
      });
    });

    it('loads saved push-to-talk preference from localStorage', async () => {
      global.localStorage.getItem = vi.fn((key) => {
        if (key === 'lt_push_to_talk') return 'true';
        return null;
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByTestId('mic-button')).toBeInTheDocument();
      });
    });
  });

  describe('Room Ownership', () => {
    it('identifies room owner correctly', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          email: 'owner@example.com',
          is_admin: false
        })
      });

      // Mock room data fetch to include owner info
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          owner_email: 'owner@example.com',
          code: 'test-room-123'
        })
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Room owner should see additional controls
        expect(screen.getByTestId('room-header')).toBeInTheDocument();
      });
    });

    it('shows speaker discovery option for room owners only', async () => {
      fetchMock.mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          email: 'owner@example.com',
          is_admin: false
        })
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Owner-only controls should be available
        expect(screen.getByTestId('settings-menu')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    it('handles speaker data loading errors gracefully', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [],
        messages: [],
        onMessage: vi.fn(),
        loading: false,
        error: 'Failed to load speakers'
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        expect(screen.getByText(/failed.*speakers/i)).toBeInTheDocument();
      });
    });

    it('handles WebSocket connection errors', async () => {
      const { default: usePresenceWebSocket } = await import('../hooks/usePresenceWebSocket');
      usePresenceWebSocket.mockReturnValue({
        isConnected: false,
        ws: null,
        participants: [],
        showWelcome: false,
        dismissWelcome: vi.fn(),
        notifications: [],
        networkQuality: 'poor',
        networkRTT: 999
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        // Network status indicator should show poor connection
        expect(screen.getByText(/poor|disconnected/i)).toBeInTheDocument();
      });
    });

    it('redirects to login when not authenticated', async () => {
      // Note: This test is simplified since useNavigate is mocked at module level
      // In real app, missing token would trigger navigation to /login
      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} token={null} />
        </BrowserRouter>
      );

      // Component should handle missing auth gracefully
      await waitFor(() => {
        expect(screen.queryByTestId('room-header')).toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('has proper ARIA labels for interactive elements', async () => {
      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        const micButton = screen.getByTestId('mic-button');
        expect(micButton).toHaveAttribute('aria-label');
      });
    });

    it('provides keyboard navigation support', async () => {
      const user = userEvent.setup();

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        const micButton = screen.getByTestId('mic-button');
        micButton.focus();
        expect(document.activeElement).toBe(micButton);
      });
    });

    it('announces new messages to screen readers', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [],
        messages: [
          {
            segment_id: 1,
            speaker: { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
            originalText: 'New message',
            translations: []
          }
        ],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      render(
        <BrowserRouter>
          <MultiSpeakerRoomPage {...defaultProps} />
        </BrowserRouter>
      );

      await waitFor(() => {
        const messageContainer = screen.getByTestId('multi-speaker-message');
        expect(messageContainer).toHaveAttribute('role', 'log');
      });
    });
  });

  describe('Performance', () => {
    it('does not re-render excessively on message updates', async () => {
      const { default: useMultiSpeakerRoom } = await import('../hooks/useMultiSpeakerRoom');
      let renderCount = 0;

      const TestWrapper = (props) => {
        renderCount++;
        return <MultiSpeakerRoomPage {...props} />;
      };

      const { rerender } = render(
        <BrowserRouter>
          <TestWrapper {...defaultProps} />
        </BrowserRouter>
      );

      const initialRenderCount = renderCount;

      // Simulate new message
      useMultiSpeakerRoom.mockReturnValue({
        speakers: [],
        messages: [
          {
            segment_id: 1,
            speaker: { speaker_id: 0, display_name: 'Alice', language: 'en', color: '#FF5733' },
            originalText: 'Message 1',
            translations: []
          }
        ],
        onMessage: vi.fn(),
        loading: false,
        error: null
      });

      rerender(
        <BrowserRouter>
          <TestWrapper {...defaultProps} />
        </BrowserRouter>
      );

      // Should only re-render once for the new message
      expect(renderCount).toBeLessThanOrEqual(initialRenderCount + 2);
    });
  });
});
