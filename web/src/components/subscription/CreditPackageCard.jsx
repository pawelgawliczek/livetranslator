import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

/**
 * CreditPackageCard - Displays a credit package with purchase button
 */
export default function CreditPackageCard({ package: pkg, onBuy, loading }) {
  const { t } = useTranslation();

  const hours = pkg.credit_hours;
  const price = pkg.price_usd;
  const discount = pkg.discount_pct;

  // Calculate per-hour rate
  const perHourRate = (price / hours).toFixed(2);

  // Highlight best value (8hr package typically)
  const isBestValue = discount >= 12;

  return (
    <div
      className={`bg-card border rounded-lg p-6 flex flex-col relative ${
        isBestValue ? 'border-accent' : 'border-border'
      }`}
    >
      {/* Best Value Badge */}
      {isBestValue && (
        <div className="absolute -top-3 left-1/2 transform -translate-x-1/2">
          <span className="bg-accent text-accent-fg text-xs font-bold px-3 py-1 rounded-full whitespace-nowrap">
            {t('subscription.bestValue')}
          </span>
        </div>
      )}

      {/* Hours */}
      <div className="text-center mb-3">
        <div className="text-4xl font-bold text-fg">
          {hours}
        </div>
        <div className="text-sm text-muted">
          {t('subscription.hours')}
        </div>
      </div>

      {/* Price */}
      <div className="text-center mb-2">
        <span className="text-2xl font-bold text-fg">${price}</span>
      </div>

      {/* Per Hour Rate */}
      <div className="text-center text-xs text-muted mb-4">
        ${perHourRate} / {t('subscription.hour')}
      </div>

      {/* Discount Badge */}
      {discount > 0 && (
        <div className="text-center mb-4">
          <span className="inline-block bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 text-xs font-semibold px-2 py-1 rounded">
            {t('subscription.savePercent', { percent: discount })}
          </span>
        </div>
      )}

      {/* Buy Button */}
      <button
        onClick={() => !loading && onBuy(pkg.id)}
        disabled={loading}
        className={`w-full py-3 px-4 rounded-lg font-medium transition-colors ${
          loading
            ? 'bg-accent/50 text-accent-fg cursor-wait'
            : 'bg-accent text-accent-fg hover:bg-accent/90'
        }`}
      >
        {loading ? t('subscription.processing') : t('subscription.buyNow')}
      </button>
    </div>
  );
}

CreditPackageCard.propTypes = {
  package: PropTypes.shape({
    id: PropTypes.number.isRequired,
    credit_hours: PropTypes.number.isRequired,
    price_usd: PropTypes.number.isRequired,
    discount_pct: PropTypes.number,
  }).isRequired,
  onBuy: PropTypes.func.isRequired,
  loading: PropTypes.bool,
};

CreditPackageCard.defaultProps = {
  loading: false,
};
