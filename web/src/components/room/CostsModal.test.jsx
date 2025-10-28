import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CostsModal from './CostsModal';
import { renderWithProviders } from '../../test/utils';

describe('CostsModal', () => {
  const mockCosts = {
    total_cost_usd: 0.012345,
    breakdown: {
      stt: {
        events: 10,
        cost_usd: 0.006
      },
      mt: {
        events: 20,
        cost_usd: 0.006345
      }
    }
  };

  const defaultProps = {
    isOpen: true,
    costs: mockCosts,
    onClose: vi.fn()
  };

  it('renders when isOpen is true', () => {
    renderWithProviders(<CostsModal {...defaultProps} />);
    expect(screen.getByText('💰 Costs')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    const { container } = renderWithProviders(
      <CostsModal {...defaultProps} isOpen={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('displays the modal title', () => {
    renderWithProviders(<CostsModal {...defaultProps} />);
    expect(screen.getByText('💰 Costs')).toBeInTheDocument();
  });

  describe('Loading State', () => {
    it('shows loading message when costs are null', () => {
      renderWithProviders(<CostsModal {...defaultProps} costs={null} />);
      expect(screen.getByText('Loading costs...')).toBeInTheDocument();
    });

    it('shows loading message when costs are undefined', () => {
      renderWithProviders(<CostsModal {...defaultProps} costs={undefined} />);
      expect(screen.getByText('Loading costs...')).toBeInTheDocument();
    });

    it('does not show total cost when loading', () => {
      renderWithProviders(<CostsModal {...defaultProps} costs={null} />);
      expect(screen.queryByText(/^\$/)).not.toBeInTheDocument();
    });

    it('does not show breakdown when loading', () => {
      renderWithProviders(<CostsModal {...defaultProps} costs={null} />);
      expect(screen.queryByText(/events/)).not.toBeInTheDocument();
    });
  });

  describe('Cost Display', () => {
    it('displays total cost with 6 decimal places', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      expect(screen.getByText('$0.012345')).toBeInTheDocument();
    });

    it('handles zero cost', () => {
      const zeroCosts = {
        total_cost_usd: 0,
        breakdown: {}
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={zeroCosts} />);
      expect(screen.getByText('$0.000000')).toBeInTheDocument();
    });

    it('handles very small costs', () => {
      const smallCosts = {
        total_cost_usd: 0.000001,
        breakdown: {}
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={smallCosts} />);
      expect(screen.getByText('$0.000001')).toBeInTheDocument();
    });

    it('handles large costs', () => {
      const largeCosts = {
        total_cost_usd: 123.456789,
        breakdown: {}
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={largeCosts} />);
      expect(screen.getByText('$123.456789')).toBeInTheDocument();
    });
  });

  describe('Breakdown Display', () => {
    it('displays STT breakdown with label', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      expect(screen.getByText('🎤 STT')).toBeInTheDocument();
    });

    it('displays MT breakdown with label', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      expect(screen.getByText('🔤 Translation')).toBeInTheDocument();
    });

    it('displays STT events and cost', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      expect(screen.getByText('10 events • $0.006000')).toBeInTheDocument();
    });

    it('displays MT events and cost', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      expect(screen.getByText('20 events • $0.006345')).toBeInTheDocument();
    });

    it('handles empty breakdown', () => {
      const noCosts = {
        total_cost_usd: 0,
        breakdown: {}
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={noCosts} />);
      expect(screen.queryByText(/events/)).not.toBeInTheDocument();
    });

    it('handles missing breakdown property', () => {
      const costsWithoutBreakdown = {
        total_cost_usd: 0.012345
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={costsWithoutBreakdown} />);
      expect(screen.queryByText(/events/)).not.toBeInTheDocument();
    });

    it('handles only STT in breakdown', () => {
      const sttOnlyCosts = {
        total_cost_usd: 0.006,
        breakdown: {
          stt: {
            events: 10,
            cost_usd: 0.006
          }
        }
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={sttOnlyCosts} />);
      expect(screen.getByText('🎤 STT')).toBeInTheDocument();
      expect(screen.queryByText('🔤 Translation')).not.toBeInTheDocument();
    });

    it('handles only MT in breakdown', () => {
      const mtOnlyCosts = {
        total_cost_usd: 0.006345,
        breakdown: {
          mt: {
            events: 20,
            cost_usd: 0.006345
          }
        }
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={mtOnlyCosts} />);
      expect(screen.getByText('🔤 Translation')).toBeInTheDocument();
      expect(screen.queryByText('🎤 STT')).not.toBeInTheDocument();
    });

    it('handles unknown pipeline type gracefully', () => {
      const unknownPipelineCosts = {
        total_cost_usd: 0.01,
        breakdown: {
          unknown: {
            events: 5,
            cost_usd: 0.01
          }
        }
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={unknownPipelineCosts} />);
      expect(screen.getByText('5 events • $0.010000')).toBeInTheDocument();
    });
  });

  describe('User Interactions', () => {
    it('calls onClose when Close button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<CostsModal {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByRole('button', { name: 'Close' }));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when backdrop is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      const { container } = renderWithProviders(<CostsModal {...defaultProps} onClose={onClose} />);

      const backdrop = container.querySelector('.fixed.inset-0');
      await user.click(backdrop);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not close when clicking inside modal content', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<CostsModal {...defaultProps} onClose={onClose} />);

      const title = screen.getByText('💰 Costs');
      await user.click(title);

      expect(onClose).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('Close button has proper role', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      expect(screen.getByRole('button', { name: 'Close' })).toBeInTheDocument();
    });

    it('Close button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<CostsModal {...defaultProps} onClose={onClose} />);

      const button = screen.getByRole('button', { name: 'Close' });
      button.focus();
      await user.keyboard('{Enter}');

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('can close with Escape key', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<CostsModal {...defaultProps} onClose={onClose} />);

      await user.keyboard('{Escape}');
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Styling', () => {
    it('title has correct styling', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      const title = screen.getByText('💰 Costs');
      expect(title).toHaveClass('text-xl', 'font-semibold', 'text-fg-dark');
    });

    it('total cost has blue color and large font', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      const totalCost = screen.getByText('$0.012345');
      expect(totalCost).toHaveClass('text-blue-500', 'font-bold');
    });

    it('breakdown items have dark background', () => {
      const { container } = renderWithProviders(<CostsModal {...defaultProps} />);
      const breakdownItems = container.querySelectorAll('.bg-\\[\\#2a2a2a\\]');
      expect(breakdownItems.length).toBeGreaterThan(0);
    });

    it('Close button has blue background', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Close' });
      expect(button).toHaveClass('bg-blue-500', 'text-white');
    });

    it('Close button has hover effect', () => {
      renderWithProviders(<CostsModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Close' });
      expect(button).toHaveClass('hover:bg-blue-600', 'transition-colors');
    });

    it('loading text is muted and centered', () => {
      renderWithProviders(<CostsModal {...defaultProps} costs={null} />);
      const loadingText = screen.getByText('Loading costs...');
      expect(loadingText).toHaveClass('text-center', 'text-muted-dark');
    });
  });

  describe('Component Behavior', () => {
    it('updates when costs change', () => {
      const { rerender } = renderWithProviders(<CostsModal {...defaultProps} />);
      expect(screen.getByText('$0.012345')).toBeInTheDocument();

      const newCosts = {
        total_cost_usd: 0.05,
        breakdown: {}
      };
      rerender(<CostsModal {...defaultProps} costs={newCosts} />);
      expect(screen.getByText('$0.050000')).toBeInTheDocument();
    });

    it('transitions from loading to loaded state', () => {
      const { rerender } = renderWithProviders(<CostsModal {...defaultProps} costs={null} />);
      expect(screen.getByText('Loading costs...')).toBeInTheDocument();

      rerender(<CostsModal {...defaultProps} costs={mockCosts} />);
      expect(screen.queryByText('Loading costs...')).not.toBeInTheDocument();
      expect(screen.getByText('$0.012345')).toBeInTheDocument();
    });

    it('handles modal state toggle', () => {
      const { rerender } = renderWithProviders(<CostsModal {...defaultProps} isOpen={true} />);
      expect(screen.getByText('💰 Costs')).toBeInTheDocument();

      rerender(<CostsModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByText('💰 Costs')).not.toBeInTheDocument();

      rerender(<CostsModal {...defaultProps} isOpen={true} />);
      expect(screen.getByText('💰 Costs')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles breakdown with zero events', () => {
      const zeroEventsCosts = {
        total_cost_usd: 0,
        breakdown: {
          stt: {
            events: 0,
            cost_usd: 0
          }
        }
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={zeroEventsCosts} />);
      expect(screen.getByText('0 events • $0.000000')).toBeInTheDocument();
    });

    it('handles very high event counts', () => {
      const highEventsCosts = {
        total_cost_usd: 1.5,
        breakdown: {
          stt: {
            events: 10000,
            cost_usd: 1.5
          }
        }
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={highEventsCosts} />);
      expect(screen.getByText('10000 events • $1.500000')).toBeInTheDocument();
    });

    it('handles multiple breakdown items', () => {
      const multiBreakdownCosts = {
        total_cost_usd: 0.03,
        breakdown: {
          stt: { events: 10, cost_usd: 0.01 },
          mt: { events: 20, cost_usd: 0.01 },
          custom: { events: 5, cost_usd: 0.01 }
        }
      };
      renderWithProviders(<CostsModal {...defaultProps} costs={multiBreakdownCosts} />);

      expect(screen.getByText('🎤 STT')).toBeInTheDocument();
      expect(screen.getByText('🔤 Translation')).toBeInTheDocument();
      expect(screen.getByText('10 events • $0.010000')).toBeInTheDocument();
      expect(screen.getByText('20 events • $0.010000')).toBeInTheDocument();
      expect(screen.getByText('5 events • $0.010000')).toBeInTheDocument();
    });
  });
});
