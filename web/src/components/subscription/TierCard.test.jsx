import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import TierCard from './TierCard';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => {
      const translations = {
        'subscription.currentPlan': 'Current Plan',
        'subscription.subscribe': 'Subscribe',
        'subscription.processing': 'Processing...',
        'subscription.free': 'Free',
        'subscription.perMonth': '/month',
        'subscription.hours': 'hours',
        'subscription.minutes': 'minutes',
      };
      return translations[key] || key;
    },
  }),
}));

describe('TierCard', () => {
  const mockTier = {
    id: 2,
    name: 'Plus',
    price_usd: 29,
    monthly_quota_seconds: 7200, // 2 hours
    features: ['Feature 1', 'Feature 2', 'Feature 3'],
  };

  const mockFreeTier = {
    id: 1,
    name: 'Free',
    price_usd: 0,
    monthly_quota_seconds: 600, // 10 minutes
    features: ['Basic feature'],
  };

  it('renders tier information correctly', () => {
    render(<TierCard tier={mockTier} isCurrent={false} onSubscribe={() => {}} />);

    expect(screen.getByText('Plus')).toBeInTheDocument();
    expect(screen.getByText('$29')).toBeInTheDocument();
    expect(screen.getByText('/month')).toBeInTheDocument();
  });

  it('displays current plan badge when isCurrent is true', () => {
    render(<TierCard tier={mockTier} isCurrent={true} onSubscribe={() => {}} />);

    const badges = screen.getAllByText('Current Plan');
    expect(badges.length).toBeGreaterThan(0);
  });

  it('shows Subscribe button for non-current tier', () => {
    render(<TierCard tier={mockTier} isCurrent={false} onSubscribe={() => {}} />);

    expect(screen.getByText('Subscribe')).toBeInTheDocument();
  });

  it('calls onSubscribe when Subscribe button is clicked', () => {
    const mockOnSubscribe = vi.fn();
    render(<TierCard tier={mockTier} isCurrent={false} onSubscribe={mockOnSubscribe} />);

    const button = screen.getByText('Subscribe');
    fireEvent.click(button);

    expect(mockOnSubscribe).toHaveBeenCalledWith(2);
  });

  it('displays Processing when loading', () => {
    render(<TierCard tier={mockTier} isCurrent={false} onSubscribe={() => {}} loading={true} />);

    expect(screen.getByText('Processing...')).toBeInTheDocument();
  });

  it('disables button when isCurrent is true', () => {
    render(<TierCard tier={mockTier} isCurrent={true} onSubscribe={() => {}} />);

    const button = screen.getByText('Current Plan');
    expect(button).toBeDisabled();
  });

  it('disables button when loading', () => {
    render(<TierCard tier={mockTier} isCurrent={false} onSubscribe={() => {}} loading={true} />);

    const button = screen.getByText('Processing...');
    expect(button).toBeDisabled();
  });

  it('renders free tier with $0 price', () => {
    render(<TierCard tier={mockFreeTier} isCurrent={false} onSubscribe={() => {}} />);

    expect(screen.getByText('Free')).toBeInTheDocument();
  });

  it('renders all features in the list', () => {
    render(<TierCard tier={mockTier} isCurrent={false} onSubscribe={() => {}} />);

    mockTier.features.forEach((feature) => {
      expect(screen.getByText(feature)).toBeInTheDocument();
    });
  });

  it('applies accent border when current tier', () => {
    const { container } = render(<TierCard tier={mockTier} isCurrent={true} onSubscribe={() => {}} />);

    const card = container.firstChild;
    expect(card).toHaveClass('border-accent');
    expect(card).toHaveClass('ring-2');
  });
});
