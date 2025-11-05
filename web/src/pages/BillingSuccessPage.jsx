import React, { useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';

/**
 * BillingSuccessPage - Displayed after successful Stripe checkout
 * Shows success message and redirects to subscription page
 */
export default function BillingSuccessPage({ token }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [searchParams] = useSearchParams();
  const sessionId = searchParams.get('session_id');

  useEffect(() => {
    if (!token) {
      navigate('/login');
    }
  }, [token, navigate]);

  const handleContinue = () => {
    navigate('/subscription');
  };

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-card border border-border rounded-lg shadow-lg p-8 text-center">
        {/* Success Icon */}
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-8 h-8 text-green-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
        </div>

        {/* Success Message */}
        <h1 className="text-2xl font-bold text-fg mb-2">
          {t('subscription.success.title')}
        </h1>
        <p className="text-muted mb-6">
          {t('subscription.success.message')}
        </p>

        {/* Session ID (for debugging) */}
        {sessionId && (
          <p className="text-xs text-muted mb-6 font-mono">
            Session: {sessionId.substring(0, 20)}...
          </p>
        )}

        {/* Continue Button */}
        <button
          onClick={handleContinue}
          className="w-full bg-accent text-accent-fg py-3 px-4 rounded-lg hover:bg-accent/90 transition-colors font-medium"
        >
          {t('subscription.continueToDashboard')}
        </button>
      </div>
    </div>
  );
}

BillingSuccessPage.propTypes = {
  token: PropTypes.string.isRequired,
};
