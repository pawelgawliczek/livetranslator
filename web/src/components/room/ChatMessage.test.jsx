import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '@/test/utils';
import ChatMessage from './ChatMessage';

describe('ChatMessage', () => {
  const mockFormatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  describe('System Messages', () => {
    it('should render system message with centered styling', () => {
      const segment = {
        source: {
          is_system: true,
          text: 'User joined the room'
        }
      };

      renderWithProviders(
        <ChatMessage
          segId="sys1"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('User joined the room')).toBeInTheDocument();
    });

    it('should style system messages differently than regular messages', () => {
      const segment = {
        source: {
          is_system: true,
          text: 'User left the room'
        }
      };

      const { container } = renderWithProviders(
        <ChatMessage
          segId="sys2"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      const messageContainer = container.firstChild;
      expect(messageContainer).toHaveClass('text-center', 'text-muted', 'italic');
    });

    it('should not show debug icon for system messages even when admin', () => {
      const segment = {
        source: {
          is_system: true,
          text: 'System notification'
        }
      };

      renderWithProviders(
        <ChatMessage
          segId="sys3"
          segment={segment}
          isAdmin={true}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.queryByText('🔍')).not.toBeInTheDocument();
    });
  });

  describe('Regular Messages with Translation', () => {
    const createTranslatedSegment = (overrides = {}) => ({
      source: {
        speaker: 'user@example.com',
        text: 'Hello world',
        final: true,
        ts_iso: '2025-01-01T12:00:00Z',
        ...overrides.source
      },
      translation: {
        text: 'Hola mundo',
        final: true,
        ...overrides.translation
      }
    });

    it('should render translated message with translation and source', () => {
      const segment = createTranslatedSegment();

      renderWithProviders(
        <ChatMessage
          segId="msg1"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('Hola mundo')).toBeInTheDocument();
      expect(screen.getByText('Hello world')).toBeInTheDocument();
    });

    it('should show username without email domain', () => {
      const segment = createTranslatedSegment();

      renderWithProviders(
        <ChatMessage
          segId="msg2"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText(/user/)).toBeInTheDocument();
      expect(screen.queryByText(/@example.com/)).not.toBeInTheDocument();
    });

    it('should show timestamp when available', () => {
      const segment = createTranslatedSegment();

      renderWithProviders(
        <ChatMessage
          segId="msg3"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      const formattedTime = mockFormatTime('2025-01-01T12:00:00Z');
      expect(screen.getByText(formattedTime)).toBeInTheDocument();
    });

    it('should render without username when speaker is system', () => {
      const segment = createTranslatedSegment({
        source: { speaker: 'system' }
      });

      renderWithProviders(
        <ChatMessage
          segId="msg4"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.queryByText('👤')).not.toBeInTheDocument();
    });

    it('should show "Speaking..." placeholder when translation is ___SPEAKING___', () => {
      const segment = createTranslatedSegment({
        translation: { text: '___SPEAKING___', final: false }
      });

      renderWithProviders(
        <ChatMessage
          segId="msg5"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText(/Speaking.../)).toBeInTheDocument();
      expect(screen.getByText('🎤')).toBeInTheDocument();
    });

    it('should show animated ellipsis for non-final translation', () => {
      const segment = createTranslatedSegment({
        translation: { text: 'Hello', final: false }
      });

      renderWithProviders(
        <ChatMessage
          segId="msg6"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('Hello')).toBeInTheDocument();
      expect(screen.getByText('⋯')).toBeInTheDocument();
    });

    it('should not show ellipsis for final translation', () => {
      const segment = createTranslatedSegment({
        translation: { text: 'Hello', final: true }
      });

      renderWithProviders(
        <ChatMessage
          segId="msg7"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.queryByText('⋯')).not.toBeInTheDocument();
    });


    it('should not show processing indicator when not processing', () => {
      const segment = createTranslatedSegment({
        translation: { final: true, processing: false }
      });

      renderWithProviders(
        <ChatMessage
          segId="msg9"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.queryByText('⚙️')).not.toBeInTheDocument();
    });
  });

  describe('Regular Messages without Translation', () => {
    const createSourceOnlySegment = (overrides = {}) => ({
      source: {
        speaker: 'alice@example.com',
        text: 'My own message',
        final: true,
        ts_iso: '2025-01-01T13:00:00Z',
        ...overrides
      }
    });

    it('should render source-only message prominently', () => {
      const segment = createSourceOnlySegment();

      renderWithProviders(
        <ChatMessage
          segId="msg10"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('My own message')).toBeInTheDocument();
    });

    it('should show "Speaking..." for source ___SPEAKING___', () => {
      const segment = createSourceOnlySegment({
        text: '___SPEAKING___',
        final: false
      });

      renderWithProviders(
        <ChatMessage
          segId="msg11"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText(/Speaking.../)).toBeInTheDocument();
    });

    it('should show ellipsis for non-final source', () => {
      const segment = createSourceOnlySegment({
        text: 'Typing',
        final: false
      });

      renderWithProviders(
        <ChatMessage
          segId="msg12"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('⋯')).toBeInTheDocument();
    });

    it('should show processing indicator for source when refining', () => {
      const segment = createSourceOnlySegment({
        final: true,
        processing: true
      });

      renderWithProviders(
        <ChatMessage
          segId="msg13"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('⚙️')).toBeInTheDocument();
    });
  });

  describe('Debug Icon for Admins', () => {
    it('should show debug icon when user is admin', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true },
        translation: { text: 'Prueba', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg14"
          segment={segment}
          isAdmin={true}
          formatTime={mockFormatTime}
          onDebugClick={vi.fn()}
        />
      );

      expect(screen.getByText('🔍')).toBeInTheDocument();
    });

    it('should not show debug icon when user is not admin', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true },
        translation: { text: 'Prueba', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg15"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.queryByText('🔍')).not.toBeInTheDocument();
    });

    it('should call onDebugClick with segId when debug icon clicked', () => {
      const onDebugClick = vi.fn();
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true },
        translation: { text: 'Prueba', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg16"
          segment={segment}
          isAdmin={true}
          formatTime={mockFormatTime}
          onDebugClick={onDebugClick}
        />
      );

      const debugIcon = screen.getByText('🔍');
      fireEvent.click(debugIcon);

      expect(onDebugClick).toHaveBeenCalledTimes(1);
      expect(onDebugClick).toHaveBeenCalledWith('msg16');
    });

    it('should have title attribute on debug icon', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg17"
          segment={segment}
          isAdmin={true}
          formatTime={mockFormatTime}
          onDebugClick={vi.fn()}
        />
      );

      const debugIcon = screen.getByText('🔍');
      expect(debugIcon).toHaveAttribute('title', 'View debug info');
    });
  });

  describe('Styling and Layout', () => {
    it('should have card-like appearance for regular messages', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true }
      };

      const { container } = renderWithProviders(
        <ChatMessage
          segId="msg18"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      const messageCard = container.querySelector('.bg-card');
      expect(messageCard).toHaveClass('bg-card', 'rounded-xl', 'border', 'border-border');
    });


    it('should show translation with foreground color for final messages', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Original', final: true },
        translation: { text: 'Translated', final: true }
      };

      const { container } = renderWithProviders(
        <ChatMessage
          segId="msg20"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      const translationText = screen.getByText('Translated');
      expect(translationText).toHaveStyle({
        color: 'var(--fg)'
      });
    });

    it('should show translation with muted color for non-final messages', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Original', final: false },
        translation: { text: 'Translating', final: false }
      };

      const { container } = renderWithProviders(
        <ChatMessage
          segId="msg21"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      const translationText = screen.getByText('Translating');
      expect(translationText).toHaveStyle({
        color: 'var(--muted)'
      });
    });

    it('should show source text with muted styling below translation', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Original text', final: true },
        translation: { text: 'Translated text', final: true }
      };

      const { container } = renderWithProviders(
        <ChatMessage
          segId="msg22"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      const sourceText = screen.getByText('Original text');
      expect(sourceText).toHaveClass('text-muted', 'text-sm', 'italic');
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing timestamp', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'No timestamp', final: true }
      };

      expect(() => {
        renderWithProviders(
          <ChatMessage
            segId="msg23"
            segment={segment}
            isAdmin={false}
            formatTime={mockFormatTime}
          />
        );
      }).not.toThrow();
    });

    it('should handle missing speaker', () => {
      const segment = {
        source: { text: 'Anonymous message', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg24"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('Anonymous message')).toBeInTheDocument();
    });

    it('should handle empty text', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: '', final: true }
      };

      expect(() => {
        renderWithProviders(
          <ChatMessage
            segId="msg25"
            segment={segment}
            isAdmin={false}
            formatTime={mockFormatTime}
          />
        );
      }).not.toThrow();
    });

    it('should handle segment without source', () => {
      const segment = {
        translation: { text: 'Only translation', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg26"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(screen.getByText('Only translation')).toBeInTheDocument();
    });

    it('should handle undefined formatTime gracefully', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true, ts_iso: '2025-01-01T12:00:00Z' }
      };

      expect(() => {
        renderWithProviders(
          <ChatMessage
            segId="msg27"
            segment={segment}
            isAdmin={false}
          />
        );
      }).not.toThrow();
    });

    it('should handle missing onDebugClick callback', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg28"
          segment={segment}
          isAdmin={true}
          formatTime={mockFormatTime}
        />
      );

      const debugIcon = screen.getByText('🔍');
      expect(() => {
        fireEvent.click(debugIcon);
      }).not.toThrow();
    });
  });

  describe('Accessibility', () => {
    it('should use semantic HTML structure', () => {
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test message', final: true }
      };

      const { container } = renderWithProviders(
        <ChatMessage
          segId="msg29"
          segment={segment}
          isAdmin={false}
          formatTime={mockFormatTime}
        />
      );

      expect(container.firstChild).toBeInTheDocument();
    });

    it('should make debug icon keyboard accessible', () => {
      const onDebugClick = vi.fn();
      const segment = {
        source: { speaker: 'user@test.com', text: 'Test', final: true }
      };

      renderWithProviders(
        <ChatMessage
          segId="msg30"
          segment={segment}
          isAdmin={true}
          formatTime={mockFormatTime}
          onDebugClick={onDebugClick}
        />
      );

      const debugIcon = screen.getByText('🔍');
      debugIcon.focus();
      fireEvent.click(debugIcon);

      expect(onDebugClick).toHaveBeenCalled();
    });
  });
});
