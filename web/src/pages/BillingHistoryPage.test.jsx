import React from 'react';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { BrowserRouter } from 'react-router-dom';
import BillingHistoryPage from './BillingHistoryPage';
import * as paymentsApi from '../utils/paymentsApi';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => {
      const translations = {
        'billing.title': 'Billing History',
        'billing.subtitle': 'View all your past payments and download receipts',
        'billing.totalSpent': 'Total Spent',
        'billing.table.date': 'Date',
        'billing.table.description': 'Description',
        'billing.table.amount': 'Amount',
        'billing.table.status': 'Status',
        'billing.table.platform': 'Platform',
        'billing.table.actions': 'Actions',
        'billing.status.completed': 'Completed',
        'billing.status.pending': 'Pending',
        'billing.status.failed': 'Failed',
        'billing.status.refunded': 'Refunded',
        'billing.descriptions.subscription': 'Subscription Payment',
        'billing.descriptions.credits': 'Credit Purchase',
        'billing.actions.download': 'Download',
        'billing.empty.title': 'No payment history',
        'billing.empty.message': 'Your payments will appear here once you subscribe or purchase credits.',
        'billing.empty.cta': 'View Subscription Plans',
        'billing.errors.loadFailed': 'Failed to load payment history',
        'billing.errors.retry': 'Retry',
        'billing.pagination.previous': 'Previous',
        'billing.pagination.next': 'Next',
        'billing.pagination.page': 'Page',
        'billing.pagination.of': 'of',
        'common.back': 'Back',
        'common.profile': 'Profile',
        'common.logout': 'Logout',
      };
      return translations[key] || key;
    },
  }),
}));

// Mock the payments API
vi.mock('../utils/paymentsApi');

describe('BillingHistoryPage', () => {
  const mockToken = 'mock-token';
  const mockOnLogout = vi.fn();

  const mockPaymentData = {
    payments: [
      {
        id: 1,
        platform: 'stripe',
        transaction_type: 'subscription',
        amount_usd: 29.00,
        currency: 'USD',
        status: 'completed',
        stripe_invoice_id: 'in_test123',
        apple_product_id: null,
        created_at: '2025-11-01T10:00:00Z',
        completed_at: '2025-11-01T10:00:05Z'
      },
      {
        id: 2,
        platform: 'apple',
        transaction_type: 'credit_purchase',
        amount_usd: 19.00,
        currency: 'USD',
        status: 'completed',
        stripe_invoice_id: null,
        apple_product_id: 'com.livetranslator.credits.4hr',
        created_at: '2025-10-25T14:30:00Z',
        completed_at: '2025-10-25T14:30:10Z'
      }
    ],
    total_spent_usd: 48.00
  };

  beforeEach(() => {
    vi.clearAllMocks();
    paymentsApi.getPaymentHistory.mockResolvedValue(mockPaymentData);
  });

  // TC-001: Load page with 0 payments → Empty state visible
  it('TC-001: shows empty state when no payments', async () => {
    paymentsApi.getPaymentHistory.mockResolvedValue({ payments: [], total_spent_usd: 0 });

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('No payment history')).toBeInTheDocument();
      expect(screen.getByText('Your payments will appear here once you subscribe or purchase credits.')).toBeInTheDocument();
      expect(screen.getByText('View Subscription Plans')).toBeInTheDocument();
    });
  });

  // TC-002: Load page with 1 payment → Table shows 1 row
  it('TC-002: displays payment table with 1 payment', async () => {
    const singlePayment = {
      payments: [mockPaymentData.payments[0]],
      total_spent_usd: 29.00
    };
    paymentsApi.getPaymentHistory.mockResolvedValue(singlePayment);

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Billing History')).toBeInTheDocument();
      expect(screen.getByText('Total Spent: $29.00')).toBeInTheDocument();
      expect(screen.getByText('Subscription Payment')).toBeInTheDocument();
      expect(screen.getByText('$29.00')).toBeInTheDocument();
    });
  });

  // TC-003: Payment status=completed → Green badge displayed
  it('TC-003: shows green badge for completed payment', async () => {
    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      const completedBadge = screen.getAllByText('Completed')[0];
      expect(completedBadge).toBeInTheDocument();
      expect(completedBadge).toHaveClass('bg-green-100');
    });
  });

  // TC-004: Click download on Stripe payment with invoice_id → Opens Stripe URL
  it('TC-004: opens Stripe URL when clicking download with invoice_id', async () => {
    const windowOpenSpy = vi.spyOn(window, 'open').mockImplementation(() => null);

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('Download')[0]).toBeInTheDocument();
    });

    const downloadButtons = screen.getAllByText('Download');
    fireEvent.click(downloadButtons[0]);

    expect(windowOpenSpy).toHaveBeenCalledWith(
      'https://invoice.stripe.com/i/in_test123',
      '_blank'
    );

    windowOpenSpy.mockRestore();
  });

  // TC-005: Unauthenticated user visits page → Redirect to /login
  it('TC-005: redirects to /login when unauthenticated', () => {
    const mockNavigate = vi.fn();
    vi.mock('react-router-dom', async () => {
      const actual = await vi.importActual('react-router-dom');
      return {
        ...actual,
        useNavigate: () => mockNavigate,
      };
    });

    render(
      <BrowserRouter>
        <BillingHistoryPage token="" onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    // Component should trigger navigation
    expect(mockNavigate).toHaveBeenCalled();
  });

  // TC-006: Payment status=failed → Red badge
  it('TC-006: shows red badge for failed payment', async () => {
    const failedPayment = {
      payments: [{
        ...mockPaymentData.payments[0],
        status: 'failed'
      }],
      total_spent_usd: 0
    };
    paymentsApi.getPaymentHistory.mockResolvedValue(failedPayment);

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      const failedBadge = screen.getByText('Failed');
      expect(failedBadge).toBeInTheDocument();
      expect(failedBadge).toHaveClass('bg-red-100');
    });
  });

  // TC-007: Payment status=pending → Yellow badge
  it('TC-007: shows yellow badge for pending payment', async () => {
    const pendingPayment = {
      payments: [{
        ...mockPaymentData.payments[0],
        status: 'pending'
      }],
      total_spent_usd: 0
    };
    paymentsApi.getPaymentHistory.mockResolvedValue(pendingPayment);

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      const pendingBadge = screen.getByText('Pending');
      expect(pendingBadge).toBeInTheDocument();
      expect(pendingBadge).toHaveClass('bg-yellow-100');
    });
  });

  // TC-011: Sort by date → Newest payments first
  it('TC-011: sorts payments by date (newest first)', async () => {
    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      // First row is header, second row should be newest payment (11/1/2025)
      expect(rows[1].textContent).toContain('11/1/2025');
      // Third row should be older payment (10/25/2025)
      expect(rows[2].textContent).toContain('10/25/2025');
    });
  });

  // TC-012: Downloads text receipt for Apple payment
  it('TC-012: downloads text receipt for Apple payment', async () => {
    // Mock createElement, appendChild, removeChild
    const mockLink = document.createElement('a');
    const createElementSpy = vi.spyOn(document, 'createElement').mockReturnValue(mockLink);
    const appendChildSpy = vi.spyOn(document.body, 'appendChild').mockImplementation(() => {});
    const removeChildSpy = vi.spyOn(document.body, 'removeChild').mockImplementation(() => {});
    const clickSpy = vi.spyOn(mockLink, 'click').mockImplementation(() => {});

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('Download')[1]).toBeInTheDocument();
    });

    const downloadButtons = screen.getAllByText('Download');
    fireEvent.click(downloadButtons[1]); // Apple payment (second row)

    expect(createElementSpy).toHaveBeenCalledWith('a');
    expect(appendChildSpy).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    expect(removeChildSpy).toHaveBeenCalled();

    createElementSpy.mockRestore();
    appendChildSpy.mockRestore();
    removeChildSpy.mockRestore();
    clickSpy.mockRestore();
  });

  // TC-014: API returns 500 → Error message displayed, retry button
  it('TC-014: shows error message and retry button on 500', async () => {
    paymentsApi.getPaymentHistory.mockRejectedValue(new Error('Server error'));

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Failed to load payment history')).toBeInTheDocument();
      expect(screen.getByText('Retry')).toBeInTheDocument();
    });
  });

  // TC-016: Shows 20 payments per page with pagination
  it('TC-016: shows 20 payments per page with pagination', async () => {
    const manyPayments = {
      payments: Array.from({ length: 25 }, (_, i) => ({
        id: i + 1,
        platform: 'stripe',
        transaction_type: 'subscription',
        amount_usd: 29.00,
        currency: 'USD',
        status: 'completed',
        stripe_invoice_id: `in_test${i}`,
        apple_product_id: null,
        created_at: `2025-${String(11 - Math.floor(i / 30)).padStart(2, '0')}-${String(25 - i % 30).padStart(2, '0')}T10:00:00Z`,
        completed_at: `2025-${String(11 - Math.floor(i / 30)).padStart(2, '0')}-${String(25 - i % 30).padStart(2, '0')}T10:00:05Z`
      })),
      total_spent_usd: 725.00
    };
    paymentsApi.getPaymentHistory.mockResolvedValue(manyPayments);

    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      const rows = screen.getAllByRole('row');
      // 21 rows = 1 header + 20 data rows
      expect(rows.length).toBe(21);
      expect(screen.getByText('Page 1 of 2')).toBeInTheDocument();
      expect(screen.getByText('Next')).toBeInTheDocument();
    });
  });

  it('displays loading state initially', () => {
    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    // Should show loading skeleton
    const skeletons = document.querySelectorAll('.animate-pulse');
    expect(skeletons.length).toBeGreaterThan(0);
  });

  it('renders navigation header', async () => {
    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getAllByText('Back')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Profile')[0]).toBeInTheDocument();
      expect(screen.getAllByText('Logout')[0]).toBeInTheDocument();
    });
  });

  it('displays total spent correctly', async () => {
    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Total Spent: $48.00')).toBeInTheDocument();
    });
  });

  it('parses Apple product ID to extract hours', async () => {
    render(
      <BrowserRouter>
        <BillingHistoryPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('4 Hour Credits')).toBeInTheDocument();
    });
  });
});
