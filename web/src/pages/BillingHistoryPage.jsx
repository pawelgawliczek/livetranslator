import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';
import { getPaymentHistory } from '../utils/paymentsApi';

/**
 * BillingHistoryPage - Display user payment history
 * Shows all past payments with status, platform, and download receipts
 */
export default function BillingHistoryPage({ token, onLogout }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [payments, setPayments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [totalSpent, setTotalSpent] = useState(0);

  const PAYMENTS_PER_PAGE = 20;

  // Redirect if not authenticated
  useEffect(() => {
    if (!token) {
      navigate('/login');
    }
  }, [token, navigate]);

  useEffect(() => {
    if (!token) return;
    loadPayments();
  }, [token]);

  const loadPayments = async () => {
    setLoading(true);
    setError(null);

    try {
      const data = await getPaymentHistory(token);
      setPayments(data.payments || []);
      setTotalSpent(data.total_spent_usd || 0);
    } catch (err) {
      console.error('[BillingHistoryPage] Failed to load payments:', err);
      if (err.message && err.message.includes('401')) {
        navigate('/login');
      } else {
        setError(t('billing.errors.loadFailed') || 'Failed to load payment history');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadInvoice = (payment) => {
    if (payment.platform === 'stripe' && payment.stripe_invoice_id) {
      // Open Stripe-hosted invoice in new tab
      window.open(`https://invoice.stripe.com/i/${payment.stripe_invoice_id}`, '_blank');
    } else {
      // Generate text receipt
      const receipt = generateTextReceipt(payment);
      const blob = new Blob([receipt], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `receipt_${payment.id}.txt`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  };

  const generateTextReceipt = (payment) => {
    return `
LIVETRANSLATOR RECEIPT
=====================

Transaction ID: ${payment.id}
Date: ${new Date(payment.created_at).toLocaleString()}
Description: ${getPaymentDescription(payment)}
Amount: $${payment.amount_usd.toFixed(2)} ${payment.currency}
Payment Method: ${payment.platform === 'stripe' ? 'Credit Card' : 'Apple In-App Purchase'}
Status: ${payment.status.toUpperCase()}
Platform: ${payment.platform === 'stripe' ? 'Stripe' : 'Apple'}

Thank you for your business!
LiveTranslator - livetranslator.pawelgawliczek.cloud
    `.trim();
  };

  const getPaymentDescription = (payment) => {
    if (payment.transaction_type === 'subscription') {
      return t('billing.descriptions.subscription') || 'Subscription Payment';
    } else if (payment.transaction_type === 'credit_purchase') {
      // Parse hours from Apple product ID or Stripe metadata
      if (payment.apple_product_id) {
        const match = payment.apple_product_id.match(/(\d+)hr/);
        if (match) return `${match[1]} Hour Credits`;
      }
      return t('billing.descriptions.credits') || 'Credit Purchase';
    }
    return payment.transaction_type;
  };

  const getStatusBadge = (status) => {
    const colors = {
      completed: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300',
      pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300',
      failed: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300',
      refunded: 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'
    };

    return (
      <span className={`px-2 py-1 text-xs font-semibold rounded-full ${colors[status] || 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300'}`}>
        {t(`billing.status.${status}`) || status}
      </span>
    );
  };

  // Pagination
  const startIndex = (page - 1) * PAYMENTS_PER_PAGE;
  const endIndex = startIndex + PAYMENTS_PER_PAGE;
  const paginatedPayments = payments.slice(startIndex, endIndex);
  const totalPages = Math.ceil(payments.length / PAYMENTS_PER_PAGE);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg">
        <header className="bg-card border-b border-border">
          <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
            <button
              onClick={() => navigate('/profile')}
              className="text-accent hover:underline flex items-center"
            >
              <svg
                className="w-5 h-5 mr-1"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
              {t('common.back')}
            </button>
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/profile')}
                className="text-muted hover:text-fg"
              >
                {t('common.profile')}
              </button>
              <button
                onClick={onLogout}
                className="text-muted hover:text-fg"
              >
                {t('common.logout')}
              </button>
            </div>
          </div>
        </header>

        <main className="max-w-6xl mx-auto px-4 py-8">
          <div className="animate-pulse">
            <div className="h-8 bg-gray-200 dark:bg-gray-700 rounded w-1/4 mb-6"></div>
            <div className="space-y-4">
              {[1, 2, 3].map(i => (
                <div key={i} className="h-16 bg-gray-200 dark:bg-gray-700 rounded"></div>
              ))}
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/profile')}
            className="text-accent hover:underline flex items-center"
          >
            <svg
              className="w-5 h-5 mr-1"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M10 19l-7-7m0 0l7-7m-7 7h18"
              />
            </svg>
            {t('common.back')}
          </button>
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/profile')}
              className="text-muted hover:text-fg"
            >
              {t('common.profile')}
            </button>
            <button
              onClick={onLogout}
              className="text-muted hover:text-fg"
            >
              {t('common.logout')}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-fg">
            {t('billing.title') || 'Billing History'}
          </h1>
          <p className="text-muted mt-2">
            {t('billing.subtitle') || 'View all your past payments and download receipts'}
          </p>
          <div className="mt-4 text-lg font-semibold text-fg">
            {t('billing.totalSpent') || 'Total Spent'}: ${totalSpent.toFixed(2)}
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="mb-6 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded flex justify-between items-center">
            <span>{error}</span>
            <button
              onClick={loadPayments}
              className="underline hover:no-underline ml-4"
            >
              {t('billing.errors.retry') || 'Retry'}
            </button>
          </div>
        )}

        {/* Empty State */}
        {!loading && payments.length === 0 && (
          <div className="text-center py-12">
            <svg className="mx-auto h-12 w-12 text-muted mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-fg">
              {t('billing.empty.title') || 'No payment history'}
            </h3>
            <p className="mt-1 text-sm text-muted">
              {t('billing.empty.message') || 'Your payments will appear here once you subscribe or purchase credits.'}
            </p>
            <button
              onClick={() => navigate('/subscription')}
              className="mt-6 px-6 py-3 bg-accent text-white rounded-lg hover:bg-accent-dark transition-colors"
            >
              {t('billing.empty.cta') || 'View Subscription Plans'}
            </button>
          </div>
        )}

        {/* Table */}
        {payments.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-border">
                <thead className="bg-bg-secondary">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">
                      {t('billing.table.date') || 'Date'}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">
                      {t('billing.table.description') || 'Description'}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">
                      {t('billing.table.amount') || 'Amount'}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">
                      {t('billing.table.status') || 'Status'}
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-muted uppercase tracking-wider">
                      {t('billing.table.platform') || 'Platform'}
                    </th>
                    <th className="px-6 py-3 text-right text-xs font-medium text-muted uppercase tracking-wider">
                      {t('billing.table.actions') || 'Actions'}
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-card divide-y divide-border">
                  {paginatedPayments.map((payment) => (
                    <tr key={payment.id} className="hover:bg-bg-secondary transition-colors">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-fg">
                        {new Date(payment.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-fg">
                        {getPaymentDescription(payment)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-fg">
                        ${payment.amount_usd.toFixed(2)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {getStatusBadge(payment.status)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-muted">
                        {payment.platform === 'stripe' ? 'Stripe' : 'Apple'}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                        <button
                          onClick={() => handleDownloadInvoice(payment)}
                          className="text-accent hover:text-accent-dark"
                        >
                          {t('billing.actions.download') || 'Download'}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-between items-center mt-6">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-4 py-2 border border-border rounded text-fg hover:bg-bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t('billing.pagination.previous') || 'Previous'}
                </button>
                <span className="text-sm text-muted">
                  {t('billing.pagination.page') || 'Page'} {page} {t('billing.pagination.of') || 'of'} {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="px-4 py-2 border border-border rounded text-fg hover:bg-bg-secondary disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {t('billing.pagination.next') || 'Next'}
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

BillingHistoryPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
