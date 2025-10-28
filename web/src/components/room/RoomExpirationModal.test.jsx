import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RoomExpirationModal from './RoomExpirationModal';
import { renderWithProviders } from '../../test/utils';

describe('RoomExpirationModal', () => {
  const defaultProps = {
    isOpen: true,
    onCreateAccount: vi.fn(),
    onSignIn: vi.fn()
  };

  describe('Rendering', () => {
    it('renders when isOpen is true', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText('Thank you for joining!')).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      const { container } = renderWithProviders(
        <RoomExpirationModal {...defaultProps} isOpen={false} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('displays goodbye icon', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText('👋')).toBeInTheDocument();
    });

    it('displays title', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText('Thank you for joining!')).toBeInTheDocument();
    });

    it('displays closure message', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText(/closed because the admin has been away/)).toBeInTheDocument();
    });

    it('displays promotional message', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByText(/Create your own account/)).toBeInTheDocument();
    });

    it('displays Create Account button', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByRole('button', { name: 'Create Account' })).toBeInTheDocument();
    });

    it('displays Sign In button', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      expect(screen.getByRole('button', { name: 'Sign In' })).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('calls onCreateAccount when Create Account button is clicked', async () => {
      const user = userEvent.setup();
      const onCreateAccount = vi.fn();
      renderWithProviders(
        <RoomExpirationModal {...defaultProps} onCreateAccount={onCreateAccount} />
      );

      await user.click(screen.getByRole('button', { name: 'Create Account' }));
      expect(onCreateAccount).toHaveBeenCalledTimes(1);
    });

    it('calls onSignIn when Sign In button is clicked', async () => {
      const user = userEvent.setup();
      const onSignIn = vi.fn();
      renderWithProviders(<RoomExpirationModal {...defaultProps} onSignIn={onSignIn} />);

      await user.click(screen.getByRole('button', { name: 'Sign In' }));
      expect(onSignIn).toHaveBeenCalledTimes(1);
    });

    it('does not close on backdrop click (no backdrop handler)', async () => {
      const user = userEvent.setup();
      const onCreateAccount = vi.fn();
      const onSignIn = vi.fn();
      const { container } = renderWithProviders(
        <RoomExpirationModal {...defaultProps} onCreateAccount={onCreateAccount} onSignIn={onSignIn} />
      );

      const backdrop = container.firstChild;
      await user.click(backdrop);

      // Modal should remain open (callbacks should not be called from backdrop)
      expect(onCreateAccount).not.toHaveBeenCalled();
      expect(onSignIn).not.toHaveBeenCalled();
    });

    it('does not close on ESC key (no ESC handler)', async () => {
      const user = userEvent.setup();
      const onCreateAccount = vi.fn();
      const onSignIn = vi.fn();
      renderWithProviders(
        <RoomExpirationModal {...defaultProps} onCreateAccount={onCreateAccount} onSignIn={onSignIn} />
      );

      await user.keyboard('{Escape}');

      // Modal should remain open (callbacks should not be called from ESC)
      expect(onCreateAccount).not.toHaveBeenCalled();
      expect(onSignIn).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('Create Account button has proper role', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Create Account' });
      expect(button).toBeInTheDocument();
    });

    it('Sign In button has proper role', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Sign In' });
      expect(button).toBeInTheDocument();
    });

    it('Create Account button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onCreateAccount = vi.fn();
      renderWithProviders(
        <RoomExpirationModal {...defaultProps} onCreateAccount={onCreateAccount} />
      );

      const button = screen.getByRole('button', { name: 'Create Account' });
      button.focus();
      await user.keyboard('{Enter}');

      expect(onCreateAccount).toHaveBeenCalledTimes(1);
    });

    it('Sign In button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onSignIn = vi.fn();
      renderWithProviders(<RoomExpirationModal {...defaultProps} onSignIn={onSignIn} />);

      const button = screen.getByRole('button', { name: 'Sign In' });
      button.focus();
      await user.keyboard('{Enter}');

      expect(onSignIn).toHaveBeenCalledTimes(1);
    });

    it('has proper heading hierarchy', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const heading = screen.getByRole('heading', { level: 2 });
      expect(heading).toBeInTheDocument();
      expect(heading).toHaveTextContent('Thank you for joining!');
    });

    it('buttons can be tabbed between', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);

      const createButton = screen.getByRole('button', { name: 'Create Account' });
      const signInButton = screen.getByRole('button', { name: 'Sign In' });

      createButton.focus();
      expect(document.activeElement).toBe(createButton);

      await user.keyboard('{Tab}');
      expect(document.activeElement).toBe(signInButton);
    });
  });

  describe('Styling', () => {
    it('has full-screen overlay', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const backdrop = container.firstChild;
      expect(backdrop).toHaveClass('fixed', 'inset-0');
    });

    it('has very high z-index', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const backdrop = container.firstChild;
      expect(backdrop).toHaveClass('z-[200]');
    });

    it('has dark background', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const backdrop = container.firstChild;
      expect(backdrop).toHaveClass('bg-black/95');
    });

    it('modal content is centered', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const backdrop = container.firstChild;
      expect(backdrop).toHaveClass('flex', 'items-center', 'justify-center');
    });

    it('has red border for warning', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modal = container.querySelector('.border-red-600');
      expect(modal).toBeInTheDocument();
    });

    it('goodbye icon is large', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const icon = screen.getByText('👋');
      expect(icon).toHaveClass('text-[3rem]');
    });

    it('Create Account button has blue background', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Create Account' });
      expect(button).toHaveClass('bg-blue-500', 'hover:bg-blue-600');
    });

    it('Sign In button has dark background', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Sign In' });
      expect(button).toHaveClass('bg-[#2a2a2a]', 'hover:bg-[#333]');
    });

    it('buttons have hover effects', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveClass('transition-colors');
      });
    });

    it('buttons are full width', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        expect(button).toHaveClass('w-full');
      });
    });

    it('buttons are stacked vertically', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const buttonContainer = container.querySelector('.flex-col');
      expect(buttonContainer).toBeInTheDocument();
    });
  });

  describe('Component Behavior', () => {
    it('toggles visibility with isOpen', () => {
      const { rerender } = renderWithProviders(
        <RoomExpirationModal {...defaultProps} isOpen={true} />
      );
      expect(screen.getByText('Thank you for joining!')).toBeInTheDocument();

      rerender(<RoomExpirationModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByText('Thank you for joining!')).not.toBeInTheDocument();
    });

    it('does not call callbacks on mount', () => {
      const onCreateAccount = vi.fn();
      const onSignIn = vi.fn();
      renderWithProviders(
        <RoomExpirationModal {...defaultProps} onCreateAccount={onCreateAccount} onSignIn={onSignIn} />
      );

      expect(onCreateAccount).not.toHaveBeenCalled();
      expect(onSignIn).not.toHaveBeenCalled();
    });

    it('handles rapid clicks on Create Account', async () => {
      const user = userEvent.setup();
      const onCreateAccount = vi.fn();
      renderWithProviders(
        <RoomExpirationModal {...defaultProps} onCreateAccount={onCreateAccount} />
      );

      const button = screen.getByRole('button', { name: 'Create Account' });
      await user.click(button);
      await user.click(button);
      await user.click(button);

      expect(onCreateAccount).toHaveBeenCalledTimes(3);
    });

    it('handles rapid clicks on Sign In', async () => {
      const user = userEvent.setup();
      const onSignIn = vi.fn();
      renderWithProviders(<RoomExpirationModal {...defaultProps} onSignIn={onSignIn} />);

      const button = screen.getByRole('button', { name: 'Sign In' });
      await user.click(button);
      await user.click(button);
      await user.click(button);

      expect(onSignIn).toHaveBeenCalledTimes(3);
    });
  });

  describe('Edge Cases', () => {
    it('renders with minimal props', () => {
      const minimalProps = {
        isOpen: true,
        onCreateAccount: vi.fn(),
        onSignIn: vi.fn()
      };
      renderWithProviders(<RoomExpirationModal {...minimalProps} />);
      expect(screen.getByText('Thank you for joining!')).toBeInTheDocument();
    });

    it('handles undefined callbacks gracefully', () => {
      // Should not crash even with undefined callbacks (though PropTypes will warn)
      const { container } = renderWithProviders(
        <RoomExpirationModal isOpen={true} onCreateAccount={undefined} onSignIn={undefined} />
      );
      expect(container.firstChild).not.toBeNull();
    });
  });

  describe('Layout', () => {
    it('content has proper padding', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modal = container.querySelector('.px-8.py-10');
      expect(modal).toBeInTheDocument();
    });

    it('has maximum width constraint', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modal = container.querySelector('.max-w-\\[450px\\]');
      expect(modal).toBeInTheDocument();
    });

    it('text is centered', () => {
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const modal = container.querySelector('.text-center');
      expect(modal).toBeInTheDocument();
    });

    it('has proper spacing between elements', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const icon = screen.getByText('👋');
      const title = screen.getByText('Thank you for joining!');

      expect(icon).toHaveClass('mb-4');
      expect(title).toHaveClass('mb-4');
    });
  });

  describe('Blocking Behavior', () => {
    it('cannot be dismissed by clicking outside', async () => {
      const user = userEvent.setup();
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);

      // Try to click outside the modal (on backdrop)
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      await user.click(container.firstChild);

      // Modal should still be visible
      expect(screen.getByText('Thank you for joining!')).toBeInTheDocument();
    });

    it('is truly modal - blocks all other interactions', () => {
      renderWithProviders(<RoomExpirationModal {...defaultProps} />);

      // The modal should be the highest z-index element
      const { container } = renderWithProviders(<RoomExpirationModal {...defaultProps} />);
      const backdrop = container.firstChild;
      expect(backdrop).toHaveClass('z-[200]');
    });
  });
});
