import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import NetworkStatusIndicator from './NetworkStatusIndicator';

describe('NetworkStatusIndicator', () => {
  describe('Rendering', () => {
    it('renders with high quality and RTT', () => {
      render(<NetworkStatusIndicator quality="high" rtt={50} />);
      expect(screen.getByText('50ms')).toBeInTheDocument();
      expect(screen.getByLabelText('Network quality: high')).toBeInTheDocument();
    });

    it('renders with medium quality and RTT', () => {
      render(<NetworkStatusIndicator quality="medium" rtt={150} />);
      expect(screen.getByText('150ms')).toBeInTheDocument();
      expect(screen.getByLabelText('Network quality: medium')).toBeInTheDocument();
    });

    it('renders with low quality and RTT', () => {
      render(<NetworkStatusIndicator quality="low" rtt={500} />);
      expect(screen.getByText('500ms')).toBeInTheDocument();
      expect(screen.getByLabelText('Network quality: low')).toBeInTheDocument();
    });

    it('does not render when quality is unknown', () => {
      const { container } = render(<NetworkStatusIndicator quality="unknown" rtt={50} />);
      expect(container.firstChild).toBeNull();
    });

    it('renders without RTT value', () => {
      render(<NetworkStatusIndicator quality="high" rtt={null} />);
      expect(screen.queryByText(/ms$/)).not.toBeInTheDocument();
      expect(screen.getByLabelText('Network quality: high')).toBeInTheDocument();
    });

    it('renders with RTT of 0', () => {
      render(<NetworkStatusIndicator quality="high" rtt={0} />);
      expect(screen.getByText('0ms')).toBeInTheDocument();
    });
  });

  describe('Visual Quality Indicators', () => {
    it('high quality shows green dot', () => {
      const { container } = render(<NetworkStatusIndicator quality="high" rtt={50} />);
      const dot = container.querySelector('.w-3.h-3.rounded-full');
      expect(dot).toHaveStyle({ backgroundColor: '#10b981' });
    });

    it('medium quality shows orange dot', () => {
      const { container } = render(<NetworkStatusIndicator quality="medium" rtt={150} />);
      const dot = container.querySelector('.w-3.h-3.rounded-full');
      expect(dot).toHaveStyle({ backgroundColor: '#f59e0b' });
    });

    it('low quality shows red dot', () => {
      const { container } = render(<NetworkStatusIndicator quality="low" rtt={500} />);
      const dot = container.querySelector('.w-3.h-3.rounded-full');
      expect(dot).toHaveStyle({ backgroundColor: '#ef4444' });
    });

    it('applies glow effect to quality dot', () => {
      const { container } = render(<NetworkStatusIndicator quality="high" rtt={50} />);
      const dot = container.querySelector('.w-3.h-3.rounded-full');
      expect(dot).toHaveStyle({ boxShadow: '0 0 6px #10b981' });
    });
  });

  describe('Default Props', () => {
    it('uses unknown quality by default', () => {
      const { container } = render(<NetworkStatusIndicator />);
      expect(container.firstChild).toBeNull();
    });

    it('handles missing rtt prop', () => {
      render(<NetworkStatusIndicator quality="high" />);
      expect(screen.queryByText(/ms$/)).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has aria-label for quality indicator', () => {
      render(<NetworkStatusIndicator quality="high" rtt={50} />);
      expect(screen.getByLabelText('Network quality: high')).toBeInTheDocument();
    });

    it('has aria-label for RTT value', () => {
      render(<NetworkStatusIndicator quality="high" rtt={50} />);
      expect(screen.getByLabelText('Round-trip time: 50 milliseconds')).toBeInTheDocument();
    });

    it('does not add aria-label for RTT when null', () => {
      render(<NetworkStatusIndicator quality="high" rtt={null} />);
      expect(screen.queryByLabelText(/Round-trip time/)).not.toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles very high RTT values', () => {
      render(<NetworkStatusIndicator quality="low" rtt={9999} />);
      expect(screen.getByText('9999ms')).toBeInTheDocument();
    });

    it('handles fractional RTT values', () => {
      render(<NetworkStatusIndicator quality="high" rtt={45.7} />);
      expect(screen.getByText('45.7ms')).toBeInTheDocument();
    });

    it('handles negative RTT gracefully', () => {
      render(<NetworkStatusIndicator quality="high" rtt={-10} />);
      expect(screen.getByText('-10ms')).toBeInTheDocument();
    });

    it('handles invalid quality value by using medium colors', () => {
      // @ts-expect-error - Testing invalid prop
      const { container } = render(<NetworkStatusIndicator quality="invalid" rtt={50} />);
      const dot = container.querySelector('.w-3.h-3.rounded-full');
      // Should fallback to medium colors
      expect(dot).toHaveStyle({ backgroundColor: '#f59e0b' });
    });
  });

  describe('Styling', () => {
    it('applies correct container classes', () => {
      const { container } = render(<NetworkStatusIndicator quality="high" rtt={50} />);
      const containerDiv = container.firstChild;
      expect(containerDiv).toHaveClass(
        'flex',
        'items-center',
        'gap-2',
        'px-2',
        'py-1',
        'rounded-xl',
        'bg-white/5',
        'text-xs',
        'text-muted-dark'
      );
    });

    it('quality dot has correct size and shape', () => {
      const { container } = render(<NetworkStatusIndicator quality="high" rtt={50} />);
      const dot = container.querySelector('.w-3.h-3.rounded-full');
      expect(dot).toBeInTheDocument();
      expect(dot).toHaveClass('w-3', 'h-3', 'rounded-full');
    });
  });

  describe('Component Behavior', () => {
    it('re-renders when quality changes', () => {
      const { rerender, container } = render(<NetworkStatusIndicator quality="high" rtt={50} />);
      let dot = container.querySelector('.w-3.h-3.rounded-full');
      expect(dot).toHaveStyle({ backgroundColor: '#10b981' });

      rerender(<NetworkStatusIndicator quality="low" rtt={50} />);
      dot = container.querySelector('.w-3.h-3.rounded-full');
      expect(dot).toHaveStyle({ backgroundColor: '#ef4444' });
    });

    it('re-renders when RTT changes', () => {
      const { rerender } = render(<NetworkStatusIndicator quality="high" rtt={50} />);
      expect(screen.getByText('50ms')).toBeInTheDocument();

      rerender(<NetworkStatusIndicator quality="high" rtt={100} />);
      expect(screen.getByText('100ms')).toBeInTheDocument();
      expect(screen.queryByText('50ms')).not.toBeInTheDocument();
    });

    it('shows indicator when quality changes from unknown', () => {
      const { rerender, container } = render(<NetworkStatusIndicator quality="unknown" rtt={50} />);
      expect(container.firstChild).toBeNull();

      rerender(<NetworkStatusIndicator quality="high" rtt={50} />);
      expect(container.firstChild).not.toBeNull();
      expect(screen.getByText('50ms')).toBeInTheDocument();
    });

    it('hides indicator when quality changes to unknown', () => {
      const { rerender, container } = render(<NetworkStatusIndicator quality="high" rtt={50} />);
      expect(container.firstChild).not.toBeNull();

      rerender(<NetworkStatusIndicator quality="unknown" rtt={50} />);
      expect(container.firstChild).toBeNull();
    });
  });
});
