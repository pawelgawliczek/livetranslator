import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WelcomeBanner from './WelcomeBanner';
import { renderWithProviders } from '../../test/utils';

describe('WelcomeBanner', () => {
  const defaultProps = {
    isOpen: true,
    roomId: 'test-room',
    participants: [],
    currentUserId: 'user-123',
    isGuest: false,
    onClose: vi.fn()
  };

  describe('Rendering', () => {
    it('renders when isOpen is true', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} />);
      expect(screen.getByText(/Welcome to test-room!/)).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      const { container } = renderWithProviders(
        <WelcomeBanner {...defaultProps} isOpen={false} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('displays the room name in title', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} roomId="my-awesome-room" />);
      expect(screen.getByText('Welcome to my-awesome-room!')).toBeInTheDocument();
    });

    it('displays close button', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} />);
      expect(screen.getByLabelText('Close welcome banner')).toBeInTheDocument();
    });

    it('shows empty message when no other participants', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={[]} />);
      expect(screen.getByText("You're the first one here!")).toBeInTheDocument();
    });

    it('shows empty message when only current user in room', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText("You're the first one here!")).toBeInTheDocument();
    });
  });

  describe('Participants List', () => {
    it('shows "Also here:" header when participants exist', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText('Also here:')).toBeInTheDocument();
    });

    it('displays other participants with flags and names', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
      expect(screen.getByText(/Español/)).toBeInTheDocument();
    });

    it('filters out current user from list', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false },
        { user_id: 'user-789', display_name: 'Bob', language: 'fr', is_guest: false }
      ];
      renderWithProviders(
        <WelcomeBanner {...defaultProps} participants={participants} currentUserId="user-123" />
      );

      expect(screen.queryByText('Me')).not.toBeInTheDocument();
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
      expect(screen.getByText(/Bob/)).toBeInTheDocument();
    });

    it('displays multiple participants', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false },
        { user_id: 'user-789', display_name: 'Bob', language: 'fr', is_guest: false },
        { user_id: 'user-999', display_name: 'Charlie', language: 'de', is_guest: true }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);

      expect(screen.getByText(/Alice/)).toBeInTheDocument();
      expect(screen.getByText(/Bob/)).toBeInTheDocument();
      expect(screen.getByText(/Charlie/)).toBeInTheDocument();
    });

    it('shows guest badge for guest users', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'guest-456', display_name: 'Guest User', language: 'es', is_guest: true }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText('(guest)')).toBeInTheDocument();
    });

    it('does not show guest badge for registered users', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.queryByText('(guest)')).not.toBeInTheDocument();
    });

    it('shows language name for each participant', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText(/Español/)).toBeInTheDocument();
    });

    it('shows fallback flag for unknown language', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'unknown', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
      expect(screen.getByText(/unknown/)).toBeInTheDocument();
    });

    it('shows language code when language not in LANGUAGES', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'xyz', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText(/xyz/)).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('calls onClose when close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<WelcomeBanner {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByLabelText('Close welcome banner'));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('close button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<WelcomeBanner {...defaultProps} onClose={onClose} />);

      const closeButton = screen.getByLabelText('Close welcome banner');
      closeButton.focus();
      await user.keyboard('{Enter}');

      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Accessibility', () => {
    it('close button has aria-label', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} />);
      expect(screen.getByLabelText('Close welcome banner')).toBeInTheDocument();
    });

    it('close button has proper role', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} />);
      const closeButton = screen.getByLabelText('Close welcome banner');
      expect(closeButton.tagName).toBe('BUTTON');
    });
  });

  describe('Styling', () => {
    it('has fixed positioning at top', () => {
      const { container } = renderWithProviders(<WelcomeBanner {...defaultProps} />);
      const banner = container.firstChild;
      expect(banner).toHaveClass('fixed', 'top-[60px]');
    });

    it('is centered horizontally', () => {
      const { container } = renderWithProviders(<WelcomeBanner {...defaultProps} />);
      const banner = container.firstChild;
      expect(banner).toHaveClass('left-1/2', '-translate-x-1/2');
    });

    it('has high z-index for overlay', () => {
      const { container } = renderWithProviders(<WelcomeBanner {...defaultProps} />);
      const banner = container.firstChild;
      expect(banner).toHaveClass('z-[998]');
    });

    it('has dark theme styling', () => {
      const { container } = renderWithProviders(<WelcomeBanner {...defaultProps} />);
      const banner = container.firstChild;
      expect(banner).toHaveClass('bg-card-dark', 'border-border-dark');
    });

    it('close button has hover effect', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} />);
      const closeButton = screen.getByLabelText('Close welcome banner');
      expect(closeButton).toHaveClass('hover:text-white', 'transition-colors');
    });
  });

  describe('Edge Cases', () => {
    it('handles undefined participants', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={undefined} />);
      expect(screen.getByText("You're the first one here!")).toBeInTheDocument();
    });

    it('handles null currentUserId', () => {
      const participants = [
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false }
      ];
      renderWithProviders(
        <WelcomeBanner {...defaultProps} participants={participants} currentUserId={null} />
      );
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
    });

    it('handles empty room ID', () => {
      renderWithProviders(<WelcomeBanner {...defaultProps} roomId="" />);
      expect(screen.getByText('Welcome to !')).toBeInTheDocument();
    });

    it('handles very long room name', () => {
      const longRoomName = 'a'.repeat(100);
      renderWithProviders(<WelcomeBanner {...defaultProps} roomId={longRoomName} />);
      expect(screen.getByText(`Welcome to ${longRoomName}!`)).toBeInTheDocument();
    });

    it('handles participant without language', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: undefined, is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
    });

    it('handles participant without display_name', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: '', language: 'es', is_guest: false }
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);
      // Should still render the empty name
      const listItems = screen.getAllByRole('listitem');
      expect(listItems.length).toBe(1);
    });

    it('handles many participants', () => {
      const participants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        ...Array.from({ length: 20 }, (_, i) => ({
          user_id: `user-${i}`,
          display_name: `User ${i}`,
          language: 'en',
          is_guest: false
        }))
      ];
      renderWithProviders(<WelcomeBanner {...defaultProps} participants={participants} />);

      // Should show all participants except current user
      const listItems = screen.getAllByRole('listitem');
      expect(listItems.length).toBe(20);
    });
  });

  describe('Component Behavior', () => {
    it('updates when participants change', () => {
      const { rerender } = renderWithProviders(<WelcomeBanner {...defaultProps} participants={[]} />);
      expect(screen.getByText("You're the first one here!")).toBeInTheDocument();

      const newParticipants = [
        { user_id: 'user-123', display_name: 'Me', language: 'en', is_guest: false },
        { user_id: 'user-456', display_name: 'Alice', language: 'es', is_guest: false }
      ];
      rerender(<WelcomeBanner {...defaultProps} participants={newParticipants} />);

      expect(screen.queryByText("You're the first one here!")).not.toBeInTheDocument();
      expect(screen.getByText('Also here:')).toBeInTheDocument();
      expect(screen.getByText(/Alice/)).toBeInTheDocument();
    });

    it('updates when roomId changes', () => {
      const { rerender } = renderWithProviders(<WelcomeBanner {...defaultProps} roomId="room-1" />);
      expect(screen.getByText('Welcome to room-1!')).toBeInTheDocument();

      rerender(<WelcomeBanner {...defaultProps} roomId="room-2" />);
      expect(screen.getByText('Welcome to room-2!')).toBeInTheDocument();
    });

    it('toggles visibility with isOpen', () => {
      const { rerender } = renderWithProviders(<WelcomeBanner {...defaultProps} isOpen={true} />);
      expect(screen.getByText(/Welcome to/)).toBeInTheDocument();

      rerender(<WelcomeBanner {...defaultProps} isOpen={false} />);
      expect(screen.queryByText(/Welcome to/)).not.toBeInTheDocument();
    });
  });
});
