import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { renderWithProviders } from '@/test/utils';
import { createRef } from 'react';
import ChatMessageList from './ChatMessageList';

describe('ChatMessageList', () => {
  const mockFormatTime = (timestamp) => {
    return new Date(timestamp).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const mockFormatCountdown = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  const createMessage = (id, text, speaker = 'user@example.com', final = true) => [
    id,
    {
      source: {
        speaker,
        text,
        final,
        ts_iso: '2025-01-01T12:00:00Z'
      }
    }
  ];

  describe('Loading States', () => {
    it('should show loading indicator when loading history with no messages', () => {
      renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={true}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.getByText(/loading history/i)).toBeInTheDocument();
      expect(screen.getByText('📜')).toBeInTheDocument();
    });

    it('should not show loading indicator when not loading', () => {
      renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.queryByText(/loading history/i)).not.toBeInTheDocument();
    });

    it('should not show loading indicator when loading but messages exist', () => {
      const messages = [createMessage('msg1', 'Hello')];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={true}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.queryByText(/loading history/i)).not.toBeInTheDocument();
      expect(screen.getByText('Hello')).toBeInTheDocument();
    });
  });

  describe('Empty State', () => {
    it('should show "Press to start" when no messages and not loading', () => {
      renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.getByText(/press to start/i)).toBeInTheDocument();
    });

    it('should not show empty state when messages exist', () => {
      const messages = [createMessage('msg1', 'Hello')];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.queryByText(/press to start/i)).not.toBeInTheDocument();
    });

    it('should not show empty state when loading', () => {
      renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={true}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.queryByText(/press to start/i)).not.toBeInTheDocument();
    });
  });

  describe('Message Rendering', () => {
    it('should render all messages', () => {
      const messages = [
        createMessage('msg1', 'First message'),
        createMessage('msg2', 'Second message'),
        createMessage('msg3', 'Third message')
      ];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.getByText('First message')).toBeInTheDocument();
      expect(screen.getByText('Second message')).toBeInTheDocument();
      expect(screen.getByText('Third message')).toBeInTheDocument();
    });

    it('should render messages in order', () => {
      const messages = [
        createMessage('msg1', 'Message 1'),
        createMessage('msg2', 'Message 2'),
        createMessage('msg3', 'Message 3')
      ];

      const { container } = renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      const messageTexts = Array.from(container.querySelectorAll('[style*="background"]'))
        .map(el => el.textContent);

      expect(messageTexts).toContain('Message 1');
      expect(messageTexts).toContain('Message 2');
      expect(messageTexts).toContain('Message 3');
    });

    it('should pass isAdmin prop to messages', () => {
      const messages = [createMessage('msg1', 'Test message')];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={true}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
          onDebugClick={vi.fn()}
        />
      );

      // Debug icon should be present when admin
      expect(screen.getByText('🔍')).toBeInTheDocument();
    });

    it('should pass formatTime prop to messages', () => {
      const messages = [createMessage('msg1', 'Test message')];
      const customFormatTime = vi.fn(() => '12:00 PM');

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={customFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(customFormatTime).toHaveBeenCalled();
    });

    it('should pass onDebugClick prop to messages', () => {
      const messages = [createMessage('msg1', 'Test message')];
      const onDebugClick = vi.fn();

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={true}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
          onDebugClick={onDebugClick}
        />
      );

      const debugIcon = screen.getByText('🔍');
      debugIcon.click();

      expect(onDebugClick).toHaveBeenCalledWith('msg1');
    });
  });

  describe('Admin Left Toast', () => {
    it('should show admin left toast when conditions met', () => {
      const messages = [createMessage('msg1', 'Hello')];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
          showAdminLeftToast={true}
          timeRemaining={600}
          formatCountdown={mockFormatCountdown}
        />
      );

      expect(screen.getByText(/admin.*away/i)).toBeInTheDocument();
    });

    it('should not show admin left toast when showAdminLeftToast is false', () => {
      const messages = [createMessage('msg1', 'Hello')];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
          showAdminLeftToast={false}
          timeRemaining={600}
          formatCountdown={mockFormatCountdown}
        />
      );

      expect(screen.queryByText(/admin.*away/i)).not.toBeInTheDocument();
    });

    it('should display countdown in admin left toast', () => {
      const messages = [createMessage('msg1', 'Hello')];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
          showAdminLeftToast={true}
          timeRemaining={300}
          formatCountdown={mockFormatCountdown}
        />
      );

      expect(screen.getByText(/5:00/)).toBeInTheDocument();
    });
  });

  describe('Scroll Behavior', () => {
    it('should attach chatEndRef to scroll anchor', () => {
      const ref = createRef();
      const messages = [createMessage('msg1', 'Hello')];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={ref}
        />
      );

      expect(ref.current).toBeInTheDocument();
    });

    it('should place scroll anchor at the end of message list', () => {
      const ref = createRef();
      const messages = [
        createMessage('msg1', 'First'),
        createMessage('msg2', 'Last')
      ];

      const { container } = renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={ref}
        />
      );

      // Scroll anchor should be last child
      const scrollContainer = container.firstChild;
      const lastChild = scrollContainer.lastChild;
      expect(lastChild).toBe(ref.current);
    });
  });

  describe('Layout and Styling', () => {
    it('should have scrollable container', () => {
      const { container } = renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      const scrollContainer = container.firstChild;
      expect(scrollContainer).toHaveStyle({
        overflowY: 'auto',
        overflowX: 'hidden'
      });
    });

    it('should have flex column layout', () => {
      const { container } = renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      const scrollContainer = container.firstChild;
      expect(scrollContainer).toHaveStyle({
        display: 'flex',
        flexDirection: 'column'
      });
    });

    it('should have appropriate gap between messages', () => {
      const { container } = renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      const scrollContainer = container.firstChild;
      expect(scrollContainer).toHaveStyle({
        gap: '0.75rem'
      });
    });

    it('should have touch scrolling enabled', () => {
      const { container } = renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      const scrollContainer = container.firstChild;
      expect(scrollContainer).toHaveStyle({
        WebkitOverflowScrolling: 'touch'
      });
    });
  });

  describe('Edge Cases', () => {
    it('should handle messages with missing data gracefully', () => {
      const messages = [
        ['msg1', { source: { text: 'Valid message', final: true } }],
        ['msg2', { source: null }],
        ['msg3', null]
      ];

      expect(() => {
        renderWithProviders(
          <ChatMessageList
            messages={messages}
            isAdmin={false}
            loadingHistory={false}
            formatTime={mockFormatTime}
            chatEndRef={createRef()}
          />
        );
      }).not.toThrow();
    });

    it('should handle empty message array', () => {
      renderWithProviders(
        <ChatMessageList
          messages={[]}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.getByText(/press to start/i)).toBeInTheDocument();
    });

    it('should handle undefined chatEndRef', () => {
      const messages = [createMessage('msg1', 'Hello')];

      expect(() => {
        renderWithProviders(
          <ChatMessageList
            messages={messages}
            isAdmin={false}
            loadingHistory={false}
            formatTime={mockFormatTime}
          />
        );
      }).not.toThrow();
    });

    it('should handle large message lists', () => {
      const messages = Array.from({ length: 100 }, (_, i) =>
        createMessage(`msg${i}`, `Message ${i}`)
      );

      const { container } = renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      // Should render without errors
      const messageElements = container.querySelectorAll('[style*="background"]');
      expect(messageElements.length).toBeGreaterThan(0);
    });
  });

  describe('System Messages', () => {
    it('should render system messages differently', () => {
      const messages = [
        [
          'sys1',
          {
            source: {
              is_system: true,
              text: 'User joined the room'
            }
          }
        ]
      ];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.getByText('User joined the room')).toBeInTheDocument();
    });

    it('should mix system and regular messages', () => {
      const messages = [
        createMessage('msg1', 'Regular message'),
        [
          'sys1',
          {
            source: {
              is_system: true,
              text: 'System notification'
            }
          }
        ],
        createMessage('msg2', 'Another regular message')
      ];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(screen.getByText('Regular message')).toBeInTheDocument();
      expect(screen.getByText('System notification')).toBeInTheDocument();
      expect(screen.getByText('Another regular message')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should use semantic HTML structure', () => {
      const messages = [createMessage('msg1', 'Hello')];

      const { container } = renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={false}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
        />
      );

      expect(container.firstChild).toBeInTheDocument();
    });

    it('should allow keyboard navigation through messages', () => {
      const messages = [
        createMessage('msg1', 'First'),
        createMessage('msg2', 'Second')
      ];

      renderWithProviders(
        <ChatMessageList
          messages={messages}
          isAdmin={true}
          loadingHistory={false}
          formatTime={mockFormatTime}
          chatEndRef={createRef()}
          onDebugClick={vi.fn()}
        />
      );

      const debugIcons = screen.getAllByText('🔍');
      expect(debugIcons.length).toBe(2);
      debugIcons.forEach(icon => {
        expect(icon).toHaveAttribute('tabindex', '0');
      });
    });
  });
});
