import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import PropTypes from 'prop-types';
import TierCard from '../components/subscription/TierCard';
import QuotaStatusCard from '../components/subscription/QuotaStatusCard';
import CreditPackageCard from '../components/subscription/CreditPackageCard';
import {
  createCheckoutSession,
  getSubscription,
  getQuotaStatus,
  getCreditPackages,
} from '../utils/subscriptionApi';

/**
 * SubscriptionPage - Main subscription management page
 * Displays tier comparison, quota status, and credit packages
 */
export default function SubscriptionPage({ token, onLogout }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [subscription, setSubscription] = useState(null);
  const [quotaStatus, setQuotaStatus] = useState(null);
  const [creditPackages, setCreditPackages] = useState([]);
  const [tiers, setTiers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [tiersLoading, setTiersLoading] = useState(true);
  const [error, setError] = useState(null);
  const [processingTierId, setProcessingTierId] = useState(null);
  const [processingPackageId, setProcessingPackageId] = useState(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!token) {
      navigate('/login');
    }
  }, [token, navigate]);

  // Fetch tiers from API (public endpoint, no auth needed)
  useEffect(() => {
    const fetchTiers = async () => {
      setTiersLoading(true);
      try {
        const response = await fetch('/api/subscription/tiers', {
          credentials: 'include'
        });
        if (!response.ok) throw new Error('Failed to fetch tiers');
        const data = await response.json();

        // Map API tiers to frontend format with translated features
        const mappedTiers = data.tiers.map((tier) => ({
          id: tier.id,
          name: tier.display_name,
          plan: tier.plan,
          price_usd: tier.price_usd,
          monthly_quota_seconds: tier.monthly_quota_seconds,
          features: getFeatureList(tier)
        }));

        setTiers(mappedTiers);
      } catch (err) {
        console.error('[SubscriptionPage] Failed to load tiers:', err);
        setError(t('subscription.errors.loadTiers') || 'Failed to load subscription tiers');
      } finally {
        setTiersLoading(false);
      }
    };

    fetchTiers();
  }, [t]);

  // Helper function to map API features to translated feature list
  const getFeatureList = (tier) => {
    const features = [];

    if (tier.plan === 'free') {
      features.push(
        t('subscription.features.basicTranslation'),
        t('subscription.features.webSpeech'),
        t('subscription.features.multiSpeaker'),
        t('subscription.features.communitySupportOnly')
      );
    } else if (tier.plan === 'plus') {
      features.push(
        t('subscription.features.premiumProviders'),
        t('subscription.features.deepLOpenAI'),
        t('subscription.features.historyExport'),
        t('subscription.features.emailSupport')
      );
    } else if (tier.plan === 'pro') {
      features.push(
        t('subscription.features.allProviders'),
        t('subscription.features.serverTTS'),
        t('subscription.features.apiAccess'),
        t('subscription.features.prioritySupport')
      );
    }

    return features;
  };

  // Fetch all data on mount
  useEffect(() => {
    if (!token) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const [subData, quotaData, packagesData] = await Promise.all([
          getSubscription(token),
          getQuotaStatus(token),
          getCreditPackages(token),
        ]);

        setSubscription(subData);
        setQuotaStatus(quotaData);
        setCreditPackages(packagesData.packages || packagesData);
      } catch (err) {
        console.error('[SubscriptionPage] Failed to fetch data:', err);
        setError(err.message || t('subscription.errorLoading'));
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, t]);

  // Handle subscription upgrade
  const handleSubscribe = async (tierId) => {
    if (!token || processingTierId) return;

    setProcessingTierId(tierId);
    setError(null);

    try {
      const { checkout_url } = await createCheckoutSession(token, 'subscription', tierId);
      // Redirect to Stripe checkout
      window.location.href = checkout_url;
    } catch (err) {
      console.error('[SubscriptionPage] Failed to create checkout:', err);

      // Check for downgrade error
      if (err.message && err.message.toLowerCase().includes('downgrade')) {
        setError(
          t('subscription.errors.downgradeNotAllowed') ||
          'Downgrades are not available via self-service. Please contact support to change your plan.'
        );
      } else {
        setError(err.message || t('subscription.stripeError'));
      }
      setProcessingTierId(null);
    }
  };

  // Handle credit package purchase
  const handleBuyCredits = async (packageId) => {
    if (!token || processingPackageId) return;

    setProcessingPackageId(packageId);
    setError(null);

    try {
      const { checkout_url } = await createCheckoutSession(token, 'credits', packageId);
      // Redirect to Stripe checkout
      window.location.href = checkout_url;
    } catch (err) {
      console.error('[SubscriptionPage] Failed to create checkout:', err);
      setError(err.message || t('subscription.stripeError'));
      setProcessingPackageId(null);
    }
  };

  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="bg-card border-b border-border">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <button
            onClick={() => navigate('/rooms')}
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
            {t('common.back_to_rooms')}
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
      <main className="max-w-7xl mx-auto px-4 py-8">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-fg">
            {t('subscription.title')}
          </h1>
          <button
            onClick={() => navigate('/billing/history')}
            className="text-accent hover:underline text-sm"
          >
            {t('subscription.viewHistory') || 'View Billing History →'}
          </button>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="bg-red-100 dark:bg-red-900/30 border border-red-400 dark:border-red-800 text-red-700 dark:text-red-300 px-4 py-3 rounded mb-6">
            <strong>{t('common.error')}: </strong>
            {error}
          </div>
        )}

        {/* Quota Status Card */}
        <div className="mb-8">
          <QuotaStatusCard quotaStatus={quotaStatus} />
        </div>

        {/* Tier Comparison */}
        <section className="mb-12">
          <h2 className="text-2xl font-semibold text-fg mb-6">
            {t('subscription.choosePlan')}
          </h2>

          {tiersLoading ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="bg-card border border-border rounded-lg p-6 animate-pulse"
                >
                  <div className="h-6 bg-bg-secondary rounded w-1/2 mb-4"></div>
                  <div className="h-8 bg-bg-secondary rounded w-3/4 mb-4"></div>
                  <div className="h-20 bg-bg-secondary rounded mb-4"></div>
                  <div className="h-10 bg-bg-secondary rounded"></div>
                </div>
              ))}
            </div>
          ) : tiers.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {tiers.map((tier) => (
                <TierCard
                  key={tier.id}
                  tier={tier}
                  isCurrent={subscription?.plan === tier.plan}
                  onSubscribe={handleSubscribe}
                  loading={processingTierId === tier.id}
                />
              ))}
            </div>
          ) : (
            <p className="text-center text-muted py-8">
              {t('subscription.noPackages')}
            </p>
          )}
        </section>

        {/* Credit Packages */}
        <section>
          <h2 className="text-2xl font-semibold text-fg mb-2">
            {t('subscription.buyCredits')}
          </h2>
          <p className="text-muted mb-6">
            {t('subscription.buyCreditsDescription')}
          </p>

          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {[1, 2, 3, 4].map((i) => (
                <div
                  key={i}
                  className="bg-card border border-border rounded-lg p-6 animate-pulse"
                >
                  <div className="h-10 bg-bg-secondary rounded mb-4"></div>
                  <div className="h-6 bg-bg-secondary rounded w-2/3 mx-auto mb-4"></div>
                  <div className="h-10 bg-bg-secondary rounded"></div>
                </div>
              ))}
            </div>
          ) : creditPackages.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {creditPackages.map((pkg) => (
                <CreditPackageCard
                  key={pkg.id}
                  package={pkg}
                  onBuy={handleBuyCredits}
                  loading={processingPackageId === pkg.id}
                />
              ))}
            </div>
          ) : (
            <p className="text-center text-muted py-8">
              {t('subscription.noPackages')}
            </p>
          )}
        </section>
      </main>
    </div>
  );
}

SubscriptionPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
