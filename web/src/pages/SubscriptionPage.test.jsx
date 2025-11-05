import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import SubscriptionPage from './SubscriptionPage';
import * as subscriptionApi from '../utils/subscriptionApi';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => {
      const translations = {
        'subscription.title': 'Subscription & Credits',
        'subscription.choosePlan': 'Choose Your Plan',
        'subscription.buyCredits': 'Buy Additional Credits',
        'subscription.buyCreditsDescription': 'Top up your quota',
        'subscription.errorLoading': 'Failed to load',
        'subscription.noPackages': 'No packages',
        'common.back_to_rooms': 'Back to Rooms',
        'common.profile': 'Profile',
        'common.logout': 'Logout',
        'common.error': 'Error',
        'subscription.features.basicTranslation': 'Basic translation',
        'subscription.features.webSpeech': 'Web Speech API',
        'subscription.features.multiSpeaker': 'Multi-speaker',
        'subscription.features.communitySupportOnly': 'Community support',
        'subscription.features.premiumProviders': 'Premium providers',
        'subscription.features.deepLOpenAI': 'DeepL & OpenAI',
        'subscription.features.historyExport': 'History export',
        'subscription.features.emailSupport': 'Email support',
        'subscription.features.allProviders': 'All providers',
        'subscription.features.serverTTS': 'Server-side TTS',
        'subscription.features.apiAccess': 'API access',
        'subscription.features.prioritySupport': 'Priority support',
      };
      return translations[key] || key;
    },
  }),
}));

// Mock the subscription API
vi.mock('../utils/subscriptionApi');

describe('SubscriptionPage', () => {
  const mockToken = 'mock-token';
  const mockOnLogout = vi.fn();

  const mockSubscription = {
    tier_id: 1,
    tier_name: 'Free',
    status: 'active',
  };

  const mockQuotaStatus = {
    quota_used_seconds: 300,
    quota_available_seconds: 600,
    bonus_credits_seconds: 0,
    billing_period_end: '2025-12-01T00:00:00Z',
  };

  const mockCreditPackages = [
    { id: 1, credit_hours: 1, price_usd: 5, discount_pct: 0 },
    { id: 2, credit_hours: 4, price_usd: 19, discount_pct: 5 },
    { id: 3, credit_hours: 8, price_usd: 35, discount_pct: 12 },
    { id: 4, credit_hours: 20, price_usd: 80, discount_pct: 20 },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    subscriptionApi.getSubscription.mockResolvedValue(mockSubscription);
    subscriptionApi.getQuotaStatus.mockResolvedValue(mockQuotaStatus);
    subscriptionApi.getCreditPackages.mockResolvedValue({ packages: mockCreditPackages });
  });

  it('renders subscription page title', async () => {
    render(
      <BrowserRouter>
        <SubscriptionPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    expect(screen.getByText('Subscription & Credits')).toBeInTheDocument();
  });

  it('fetches and displays subscription data', async () => {
    render(
      <BrowserRouter>
        <SubscriptionPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(subscriptionApi.getSubscription).toHaveBeenCalledWith(mockToken);
      expect(subscriptionApi.getQuotaStatus).toHaveBeenCalledWith(mockToken);
      expect(subscriptionApi.getCreditPackages).toHaveBeenCalledWith(mockToken);
    });
  });

  it('displays tier comparison section', async () => {
    render(
      <BrowserRouter>
        <SubscriptionPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Choose Your Plan')).toBeInTheDocument();
    });
  });

  it('displays credit packages section', async () => {
    render(
      <BrowserRouter>
        <SubscriptionPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Buy Additional Credits')).toBeInTheDocument();
    });
  });

  it('shows error message when API fails', async () => {
    const errorMessage = 'API Error';
    subscriptionApi.getSubscription.mockRejectedValue(new Error(errorMessage));

    render(
      <BrowserRouter>
        <SubscriptionPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/Error/)).toBeInTheDocument();
    });
  });

  it('displays loading state initially', () => {
    render(
      <BrowserRouter>
        <SubscriptionPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    // Should show loading skeletons
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders navigation header', () => {
    render(
      <BrowserRouter>
        <SubscriptionPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    expect(screen.getByText('Back to Rooms')).toBeInTheDocument();
    expect(screen.getByText('Profile')).toBeInTheDocument();
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });
});
