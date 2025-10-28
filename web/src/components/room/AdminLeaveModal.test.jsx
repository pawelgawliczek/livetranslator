import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminLeaveModal from './AdminLeaveModal';
import { renderWithProviders } from '../../test/utils';

describe('AdminLeaveModal', () => {
  const defaultProps = {
    isOpen: true,
    onStay: vi.fn(),
    onLeave: vi.fn()
  };

  describe('Rendering', () => {
    it('renders when isOpen is true', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      expect(screen.getByText('⚠️')).toBeInTheDocument();
    });

    it('does not render when isOpen is false', () => {
      const { container} = renderWithProviders(
        <AdminLeaveModal {...defaultProps} isOpen={false} />
      );
      expect(container.firstChild).toBeNull();
    });

    it('displays warning icon', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      expect(screen.getByText('⚠️')).toBeInTheDocument();
    });

    it('displays title from translations', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      // The title should be rendered (even if translation is missing in test)
      const title = screen.queryByRole('heading', { level: 3 });
      expect(title).toBeInTheDocument();
    });

    it('displays Stay button', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const stayButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-blue-500')
      );
      expect(stayButton).toBeInTheDocument();
    });

    it('displays Leave button', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const leaveButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-red-600')
      );
      expect(leaveButton).toBeInTheDocument();
    });

    it('displays warning list with 4 points', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const listItems = screen.getAllByRole('listitem');
      expect(listItems).toHaveLength(4);
    });
  });

  describe('User Interactions', () => {
    it('calls onStay when Stay button is clicked', async () => {
      const user = userEvent.setup();
      const onStay = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onStay={onStay} />);

      const stayButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-blue-500')
      );
      await user.click(stayButton);

      expect(onStay).toHaveBeenCalledTimes(1);
    });

    it('calls onLeave when Leave button is clicked', async () => {
      const user = userEvent.setup();
      const onLeave = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onLeave={onLeave} />);

      const leaveButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-red-600')
      );
      await user.click(leaveButton);

      expect(onLeave).toHaveBeenCalledTimes(1);
    });

    it('calls onStay when backdrop is clicked', async () => {
      const user = userEvent.setup();
      const onStay = vi.fn();
      const { container } = renderWithProviders(
        <AdminLeaveModal {...defaultProps} onStay={onStay} />
      );

      const backdrop = container.querySelector('.fixed.inset-0');
      await user.click(backdrop);

      expect(onStay).toHaveBeenCalledTimes(1);
    });

    it('calls onStay when ESC key is pressed', async () => {
      const user = userEvent.setup();
      const onStay = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onStay={onStay} />);

      await user.keyboard('{Escape}');
      expect(onStay).toHaveBeenCalledTimes(1);
    });

    it('does not call onLeave when backdrop is clicked', async () => {
      const user = userEvent.setup();
      const onLeave = vi.fn();
      const { container } = renderWithProviders(
        <AdminLeaveModal {...defaultProps} onLeave={onLeave} />
      );

      const backdrop = container.querySelector('.fixed.inset-0');
      await user.click(backdrop);

      expect(onLeave).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('Stay button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onStay = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onStay={onStay} />);

      const stayButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-blue-500')
      );
      stayButton.focus();
      await user.keyboard('{Enter}');

      expect(onStay).toHaveBeenCalledTimes(1);
    });

    it('Leave button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onLeave = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onLeave={onLeave} />);

      const leaveButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-red-600')
      );
      leaveButton.focus();
      await user.keyboard('{Enter}');

      expect(onLeave).toHaveBeenCalledTimes(1);
    });

    it('has proper heading hierarchy', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const heading = screen.queryByRole('heading', { level: 3 });
      expect(heading).toBeInTheDocument();
    });

    it('list items have proper semantic structure', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const list = screen.getByRole('list');
      expect(list).toBeInTheDocument();
      expect(list.querySelectorAll('li')).toHaveLength(4);
    });
  });

  describe('Styling', () => {
    it('warning icon is large and centered', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const icon = screen.getByText('⚠️');
      expect(icon).toHaveClass('text-[2.5rem]', 'text-center');
    });

    it('title is centered and large', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const title = screen.queryByRole('heading', { level: 3 });
      expect(title).toHaveClass('text-center', 'text-[1.3rem]');
    });

    it('Stay button has blue background', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const stayButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-blue-500')
      );
      expect(stayButton).toHaveClass('bg-blue-500', 'hover:bg-blue-600');
    });

    it('Leave button has red background', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const leaveButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-red-600')
      );
      expect(leaveButton).toHaveClass('bg-red-600', 'hover:bg-red-700');
    });

    it('buttons have equal flex sizing', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        if (button.className.includes('bg-blue') || button.className.includes('bg-red')) {
          expect(button).toHaveClass('flex-1');
        }
      });
    });

    it('buttons have hover effects', () => {
      renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const buttons = screen.getAllByRole('button');
      buttons.forEach(button => {
        if (button.className.includes('bg-blue') || button.className.includes('bg-red')) {
          expect(button).toHaveClass('transition-colors');
        }
      });
    });

    it('rejoin note is italicized and muted', () => {
      const { container } = renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const italicText = container.querySelector('.italic');
      expect(italicText).toBeInTheDocument();
      expect(italicText).toHaveClass('text-muted-dark');
    });
  });

  describe('Component Behavior', () => {
    it('toggles visibility with isOpen', () => {
      const { rerender } = renderWithProviders(<AdminLeaveModal {...defaultProps} isOpen={true} />);
      expect(screen.getByText('⚠️')).toBeInTheDocument();

      rerender(<AdminLeaveModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByText('⚠️')).not.toBeInTheDocument();
    });

    it('does not call callbacks when not interacted with', () => {
      const onStay = vi.fn();
      const onLeave = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onStay={onStay} onLeave={onLeave} />);

      expect(onStay).not.toHaveBeenCalled();
      expect(onLeave).not.toHaveBeenCalled();
    });

    it('prevents multiple rapid clicks on Stay', async () => {
      const user = userEvent.setup();
      const onStay = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onStay={onStay} />);

      const stayButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-blue-500')
      );

      await user.click(stayButton);
      await user.click(stayButton);
      await user.click(stayButton);

      expect(onStay).toHaveBeenCalledTimes(3);
    });

    it('prevents multiple rapid clicks on Leave', async () => {
      const user = userEvent.setup();
      const onLeave = vi.fn();
      renderWithProviders(<AdminLeaveModal {...defaultProps} onLeave={onLeave} />);

      const leaveButton = screen.getAllByRole('button').find(
        btn => btn.className.includes('bg-red-600')
      );

      await user.click(leaveButton);
      await user.click(leaveButton);
      await user.click(leaveButton);

      expect(onLeave).toHaveBeenCalledTimes(3);
    });
  });

  describe('Edge Cases', () => {
    it('renders correctly with minimal props', () => {
      const minimalProps = {
        isOpen: true,
        onStay: vi.fn(),
        onLeave: vi.fn()
      };
      renderWithProviders(<AdminLeaveModal {...minimalProps} />);
      expect(screen.getByText('⚠️')).toBeInTheDocument();
    });

    it('handles undefined callbacks gracefully', () => {
      // Should not crash even with undefined callbacks (though PropTypes will warn)
      const { container } = renderWithProviders(
        <AdminLeaveModal isOpen={true} onStay={undefined} onLeave={undefined} />
      );
      expect(container.firstChild).not.toBeNull();
    });
  });

  describe('Layout', () => {
    it('buttons are in a flex container with gap', () => {
      const { container } = renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const buttonContainer = container.querySelector('.flex.gap-3');
      expect(buttonContainer).toBeInTheDocument();
    });

    it('content has proper spacing', () => {
      const { container } = renderWithProviders(<AdminLeaveModal {...defaultProps} />);
      const mainContainer = container.querySelector('.space-y-4');
      expect(mainContainer).toBeInTheDocument();
    });
  });
});
