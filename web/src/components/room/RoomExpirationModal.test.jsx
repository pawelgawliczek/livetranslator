import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RoomExpirationModal from './RoomExpirationModal';
import { renderWithProviders } from '../../test/utils';

describe('RoomExpirationModal', () => {
  const defaultProps = {
    timeRemaining: 300, // 5 minutes in seconds
    formatCountdown: vi.fn((time) => {
      const minutes = Math.floor(time / 60);
      const seconds = time % 60;
      return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }),
    onClose: vi.fn()
  };

  describe('Rendering', () => {
    it('renders when timeRemaining is provided', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText('Room Closing Soon')).toBeInTheDocument();
    });

    it('does not render when timeRemaining is null', () => {
      const { container } = renderWithProviders(
        <RoomExpirationModal {...defaultProps} timeRemaining={null} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('renders when timeRemaining is 0', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} timeRemaining={0} />);
      expect(screen.getByText('Room Closing Soon')).toBeInTheDocument();
    });

    it('displays warning icon', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText('⚠️')).toBeInTheDocument();
    });

    it('displays title', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText('Room Closing Soon')).toBeInTheDocument();
    });

    it('displays explanation message', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText(/admin has left the room/)).toBeInTheDocument();
    });

    it('displays info message about admin rejoining', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText(/room will remain open if the admin rejoins/)).toBeInTheDocument();
    });

    it('displays Leave Room button', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByRole('button', { name: 'Leave Room' })).toBeInTheDocument();
    });

    it('displays countdown timer', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(defaultProps.formatCountdown).toHaveBeenCalledWith(300);
      expect(screen.getByText('5:00')).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('calls onClose when Leave Room button is clicked', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Leave Room' });
      await user.click(button);
      expect(defaultProps.onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Styling', () => {
    it('has full-screen overlay with dark background', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const overlay = container.firstChild;
      expect(overlay).toHaveClass('fixed', 'inset-0', 'bg-black/95');
    });

    it('has very high z-index', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const overlay = container.firstChild;
      expect(overlay).toHaveClass('z-[200]');
    });

    it('has red border for warning', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modalContent = screen.getByText('Room Closing Soon').closest('div');
      expect(modalContent).toHaveClass('border-2', 'border-red-600');
    });

    it('warning icon is large', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const icon = screen.getByText('⚠️');
      expect(icon.parentElement).toHaveClass('text-[3rem]');
    });

    it('Leave Room button has red background', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Leave Room' });
      expect(button).toHaveClass('bg-red-600', 'hover:bg-red-700');
    });

    it('button has hover effect', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Leave Room' });
      expect(button).toHaveClass('transition-colors');
    });

    it('button is full width', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Leave Room' });
      expect(button).toHaveClass('w-full');
    });

    it('modal content is centered', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const overlay = container.firstChild;
      expect(overlay).toHaveClass('flex', 'items-center', 'justify-center');
    });

    it('countdown has large red text', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const countdown = screen.getByText('5:00');
      expect(countdown).toHaveClass('text-[2.5rem]', 'font-bold', 'text-red-500');
    });
  });

  describe('Layout', () => {
    it('content has proper padding', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modalContent = screen.getByText('Room Closing Soon').closest('div');
      expect(modalContent).toHaveClass('px-8', 'py-10');
    });

    it('has maximum width constraint', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modalContent = screen.getByText('Room Closing Soon').closest('div');
      expect(modalContent).toHaveClass('max-w-[450px]');
    });

    it('text is centered', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modalContent = screen.getByText('Room Closing Soon').closest('div');
      expect(modalContent).toHaveClass('text-center');
    });
  });

  describe('Blocking Behavior', () => {
    it('is truly modal - cannot be closed by clicking outside', async () => {
      const user = userEvent.setup();
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const overlay = container.firstChild;
      await user.click(overlay);
      // onClose should not be called when clicking overlay
      expect(defaultProps.onClose).not.toHaveBeenCalled();
    });
  });

  describe('Edge Cases', () => {
    it('handles countdown at 0 seconds', () => {
      const props = { ...defaultProps, timeRemaining: 0 };
      renderWithProviders(<RoomExpirationModal {...props} />);
      expect(screen.getByText('Room Closing Soon')).toBeInTheDocument();
    });

    it('handles large countdown values', () => {
      const props = { ...defaultProps, timeRemaining: 3600 };
      renderWithProviders(<RoomExpirationModal {...props} />);
      expect(defaultProps.formatCountdown).toHaveBeenCalledWith(3600);
    });
  });

  describe('Accessibility', () => {
    it('has proper heading hierarchy', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const heading = screen.getByRole('heading', { name: 'Room Closing Soon' });
      expect(heading.tagName).toBe('H2');
    });

    it('Leave Room button has proper role', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Leave Room' });
      expect(button).toBeInTheDocument();
    });

    it('Leave Room button is keyboard accessible', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Leave Room' });
      await user.tab();
      expect(button).toHaveFocus();
      await user.keyboard('{Enter}');
      expect(defaultProps.onClose).toHaveBeenCalled();
    });
  });
});
