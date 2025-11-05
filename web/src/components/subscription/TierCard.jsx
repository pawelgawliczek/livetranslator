import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

/**
 * TierCard - Displays a subscription tier with features and CTA button
 */
export default function TierCard({ tier, isCurrent, onSubscribe, loading }) {
  const { t } = useTranslation();

  const formatPrice = (price) => {
    return price === 0 ? t('subscription.free') : `$${price}`;
  };

  const formatQuota = (seconds) => {
    const hours = seconds / 3600;
    if (hours < 1) {
      const minutes = Math.round(seconds / 60);
      return `${minutes} ${t('subscription.minutes')}`;
    }
    return `${hours} ${t('subscription.hours')}`;
  };

  const getButtonText = () => {
    if (isCurrent) return t('subscription.currentPlan');
    if (loading) return t('subscription.processing');
    return t('subscription.subscribe');
  };

  const getButtonClass = () => {
    const baseClass = 'w-full py-3 px-4 rounded-lg font-medium transition-colors';
    if (isCurrent) {
      return `${baseClass} bg-bg-secondary text-muted cursor-not-allowed`;
    }
    if (loading) {
      return `${baseClass} bg-accent/50 text-accent-fg cursor-wait`;
    }
    return `${baseClass} bg-accent text-accent-fg hover:bg-accent/90`;
  };

  return (
    <div
      className={`bg-card border rounded-lg p-6 flex flex-col ${
        isCurrent ? 'border-accent ring-2 ring-accent' : 'border-border'
      }`}
    >
      {/* Current Plan Badge */}
      {isCurrent && (
        <div className="bg-accent text-accent-fg text-xs font-semibold px-2 py-1 rounded-full w-fit mb-3">
          {t('subscription.currentPlan')}
        </div>
      )}

      {/* Tier Name */}
      <h3 className="text-2xl font-bold text-fg mb-2">{tier.name}</h3>

      {/* Price */}
      <div className="mb-4">
        <span className="text-3xl font-bold text-fg">{formatPrice(tier.price_usd)}</span>
        {tier.price_usd > 0 && (
          <span className="text-muted ml-1">{t('subscription.perMonth')}</span>
        )}
      </div>

      {/* Quota */}
      <div className="text-sm text-muted mb-4">
        {formatQuota(tier.monthly_quota_seconds)} {t('subscription.perMonth')}
      </div>

      {/* Features */}
      <div className="flex-1 mb-6">
        <ul className="space-y-2">
          {tier.features && tier.features.map((feature, index) => (
            <li key={index} className="flex items-start text-sm text-fg">
              <svg
                className="w-5 h-5 text-green-500 mr-2 flex-shrink-0"
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
              <span>{feature}</span>
            </li>
          ))}
        </ul>
      </div>

      {/* CTA Button */}
      <button
        onClick={() => !isCurrent && !loading && onSubscribe(tier.id)}
        disabled={isCurrent || loading}
        className={getButtonClass()}
      >
        {getButtonText()}
      </button>
    </div>
  );
}

TierCard.propTypes = {
  tier: PropTypes.shape({
    id: PropTypes.number.isRequired,
    name: PropTypes.string.isRequired,
    price_usd: PropTypes.number.isRequired,
    monthly_quota_seconds: PropTypes.number.isRequired,
    features: PropTypes.arrayOf(PropTypes.string),
  }).isRequired,
  isCurrent: PropTypes.bool.isRequired,
  onSubscribe: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

TierCard.defaultProps = {
  loading: false,
};
