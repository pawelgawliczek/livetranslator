import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

/**
 * QuotaStatusCard - Displays current quota usage with progress bar
 */
export default function QuotaStatusCard({ quotaStatus }) {
  const { t } = useTranslation();

  if (!quotaStatus) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-4 bg-bg-secondary rounded w-1/4 mb-4"></div>
          <div className="h-8 bg-bg-secondary rounded w-1/2 mb-2"></div>
          <div className="h-2 bg-bg-secondary rounded mb-4"></div>
        </div>
      </div>
    );
  }

  // Support both API formats: new (seconds) and legacy (minutes)
  const quota_used_seconds = quotaStatus.quota_used_seconds ||
    (quotaStatus.usage_minutes ? quotaStatus.usage_minutes * 60 : 0);
  const quota_available_seconds = quotaStatus.quota_available_seconds ||
    (quotaStatus.monthly_quota_minutes ? quotaStatus.monthly_quota_minutes * 60 : 0);
  const bonus_credits_seconds = quotaStatus.bonus_credits_seconds || 0;
  const billing_period_end = quotaStatus.billing_period_end;

  // Convert seconds to hours
  const usedHours = (quota_used_seconds / 3600).toFixed(2);
  const totalHours = (quota_available_seconds / 3600).toFixed(2);
  const bonusHours = (bonus_credits_seconds / 3600).toFixed(2);

  // Calculate percentage
  const percentage = quota_available_seconds > 0
    ? Math.min(100, Math.round((quota_used_seconds / quota_available_seconds) * 100))
    : 0;

  // Determine color based on usage
  const getProgressColor = () => {
    if (percentage >= 80) return 'bg-red-500';
    if (percentage >= 50) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const getTextColor = () => {
    if (percentage >= 80) return 'text-red-600';
    if (percentage >= 50) return 'text-yellow-600';
    return 'text-green-600';
  };

  // Format reset date
  const formatResetDate = (dateStr) => {
    if (!dateStr) return '--';
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <h2 className="text-lg font-semibold text-fg mb-4">
        {t('subscription.quotaStatus')}
      </h2>

      {/* Usage Stats */}
      <div className="mb-4">
        <div className="flex items-baseline justify-between mb-2">
          <span className="text-2xl font-bold text-fg">
            {usedHours} / {totalHours}
          </span>
          <span className={`text-sm font-semibold ${getTextColor()}`}>
            {percentage}%
          </span>
        </div>
        <p className="text-sm text-muted">
          {t('subscription.hoursThisMonth')}
        </p>
      </div>

      {/* Progress Bar */}
      <div className="w-full bg-bg-secondary rounded-full h-3 mb-4 overflow-hidden">
        <div
          className={`h-full ${getProgressColor()} transition-all duration-300`}
          style={{ width: `${percentage}%` }}
        />
      </div>

      {/* Bonus Credits */}
      {bonus_credits_seconds > 0 && (
        <div className="bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800 rounded-lg p-3 mb-4">
          <p className="text-sm text-blue-800 dark:text-blue-200 font-medium">
            {t('subscription.bonusHours', { hours: bonusHours })}
          </p>
        </div>
      )}

      {/* Next Reset */}
      <div className="flex items-center justify-between text-sm text-muted">
        <span>{t('subscription.nextReset')}</span>
        <span className="font-medium">{formatResetDate(billing_period_end)}</span>
      </div>

      {/* Low Quota Warning */}
      {percentage >= 80 && (
        <div className="mt-4 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded-lg p-3">
          <p className="text-sm text-yellow-800 dark:text-yellow-200">
            {t('subscription.lowQuotaWarning')}
          </p>
        </div>
      )}
    </div>
  );
}

QuotaStatusCard.propTypes = {
  quotaStatus: PropTypes.shape({
    quota_used_seconds: PropTypes.number,
    quota_available_seconds: PropTypes.number,
    bonus_credits_seconds: PropTypes.number,
    billing_period_end: PropTypes.string,
  }),
};
