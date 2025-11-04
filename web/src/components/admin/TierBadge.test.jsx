import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import TierBadge from './TierBadge';

describe('TierBadge', () => {
  it('renders free tier badge', () => {
    render(<TierBadge tier="free" />);
    expect(screen.getByText('Free')).toBeInTheDocument();
  });

  it('renders plus tier badge', () => {
    render(<TierBadge tier="plus" />);
    expect(screen.getByText('Plus')).toBeInTheDocument();
  });

  it('renders pro tier badge', () => {
    render(<TierBadge tier="pro" />);
    expect(screen.getByText('Pro')).toBeInTheDocument();
  });

  it('shows inactive state with opacity', () => {
    const { container } = render(<TierBadge tier="plus" active={false} />);
    const badge = container.querySelector('span');
    expect(badge).toHaveClass('opacity-50');
    expect(badge).toHaveClass('line-through');
  });

  it('shows active state without opacity', () => {
    const { container } = render(<TierBadge tier="plus" active={true} />);
    const badge = container.querySelector('span');
    expect(badge).not.toHaveClass('opacity-50');
    expect(badge).not.toHaveClass('line-through');
  });
});
