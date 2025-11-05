import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';

/**
 * BillingCancelPage - Displayed when user cancels Stripe checkout
 * Shows cancel message and allows retry
 */
export default function BillingCancelPage({ token }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  useEffect(() => {
    if (!token) {
      navigate('/login');
    }
  }, [token, navigate]);

  const handleTryAgain = () => {
    navigate('/subscription');
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-card border border-border rounded-lg shadow-lg p-8 text-center">
        {/* Cancel Icon */}
        <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-8 h-8 text-yellow-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
            />
          </svg>
        </div>

        {/* Cancel Message */}
        <h1 className="text-2xl font-bold text-fg mb-2">
          {t('subscription.cancel.title')}
        </h1>
        <p className="text-muted mb-6">
          {t('subscription.cancel.message')}
        </p>

        {/* Action Buttons */}
        <div className="space-y-3">
          <button
            onClick={handleTryAgain}
            className="w-full bg-accent text-accent-fg py-3 px-4 rounded-lg hover:bg-accent/90 transition-colors font-medium"
          >
            {t('subscription.tryAgain')}
          </button>
          <button
            onClick={() => navigate('/rooms')}
            className="w-full bg-bg-secondary text-fg py-3 px-4 rounded-lg hover:bg-bg-secondary/80 transition-colors"
          >
            {t('common.back_to_rooms')}
          </button>
        </div>
      </div>
    </div>
  );
}

BillingCancelPage.propTypes = {
  token: PropTypes.string.isRequired,
};
