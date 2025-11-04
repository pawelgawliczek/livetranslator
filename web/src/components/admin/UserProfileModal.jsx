import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import GrantCreditsModal from './GrantCreditsModal';

/**
 * UserProfileModal - Display user profile and subscription details
 * Part of US-009: Search and View User Details
 * Updated for US-010: Grant Bonus Credits to User
 */
export default function UserProfileModal({ user, onClose, token, onUserUpdate }) {
  const { t } = useTranslation();
  const [showGrantModal, setShowGrantModal] = useState(false);

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      });
    } catch (e) {
      return isoString;
    }
  };

  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  const handleContentClick = (e) => {
    e.stopPropagation();
  };

  const handleOpenGrantModal = () => {
    setShowGrantModal(true);
  };

  const handleGrantSuccess = () => {
    console.log('[UserProfileModal] Credits granted successfully');
    // Refresh user data if callback provided
    if (onUserUpdate) {
      onUserUpdate();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        className="bg-card border border-border rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto"
        onClick={handleContentClick}
      >
        {/* Header */}
        <div className="border-b border-border p-6">
          <h2 className="text-2xl font-bold">{t('admin.users.modal.title')}</h2>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Profile Section */}
          <div>
            <h3 className="text-lg font-semibold mb-4 text-primary">
              {t('admin.users.modal.profile')}
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted">{t('admin.users.email')}</p>
                <p className="font-medium">{user.email}</p>
              </div>
              <div>
                <p className="text-sm text-muted">{t('admin.users.displayName')}</p>
                <p className="font-medium">{user.display_name || 'N/A'}</p>
              </div>
              <div>
                <p className="text-sm text-muted">{t('admin.users.userId')}</p>
                <p className="font-medium">{user.user_id}</p>
              </div>
              <div>
                <p className="text-sm text-muted">{t('admin.users.signupDate')}</p>
                <p className="font-medium">{formatDate(user.signup_date)}</p>
              </div>
            </div>
          </div>

          {/* Subscription Section */}
          <div>
            <h3 className="text-lg font-semibold mb-4 text-primary">
              {t('admin.users.modal.subscription')}
            </h3>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted">{t('admin.users.tier')}</p>
                <p className="font-medium capitalize">{user.tier_name || 'free'}</p>
              </div>
              <div>
                <p className="text-sm text-muted">{t('admin.users.modal.monthlyQuota')}</p>
                <p className="font-medium">
                  {user.quota_limit_hours !== null ? `${user.quota_limit_hours} hours` : 'Unlimited'}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted">{t('admin.users.quotaUsed')}</p>
                <p className="font-medium">{user.quota_used_hours} hours</p>
              </div>
              <div>
                <p className="text-sm text-muted">Usage</p>
                <div className="w-full bg-secondary rounded-full h-2 mt-2">
                  <div
                    className="bg-primary h-2 rounded-full"
                    style={{
                      width: user.quota_limit_hours
                        ? `${Math.min((user.quota_used_hours / user.quota_limit_hours) * 100, 100)}%`
                        : '0%',
                    }}
                  />
                </div>
              </div>
            </div>
          </div>

          {/* Activity Section - Placeholder for US-010 */}
          <div>
            <h3 className="text-lg font-semibold mb-4 text-primary">
              {t('admin.users.modal.activity')}
            </h3>
            <p className="text-muted text-sm">
              Activity history will be available in future updates.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="border-t border-border p-6 flex justify-end gap-4">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-secondary text-foreground rounded hover:bg-opacity-80 transition"
          >
            {t('admin.users.modal.close')}
          </button>
          <button
            onClick={handleOpenGrantModal}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-opacity-90 transition"
          >
            {t('admin.users.modal.grantCredits')}
          </button>
        </div>
      </div>

      {/* Grant Credits Modal */}
      {showGrantModal && (
        <GrantCreditsModal
          isOpen={showGrantModal}
          onClose={() => setShowGrantModal(false)}
          user={user}
          token={token}
          onSuccess={handleGrantSuccess}
        />
      )}
    </div>
  );
}

UserProfileModal.propTypes = {
  user: PropTypes.shape({
    user_id: PropTypes.number.isRequired,
    email: PropTypes.string.isRequired,
    display_name: PropTypes.string,
    tier_name: PropTypes.string,
    quota_used_hours: PropTypes.number.isRequired,
    quota_limit_hours: PropTypes.number,
    signup_date: PropTypes.string,
  }).isRequired,
  onClose: PropTypes.func.isRequired,
  token: PropTypes.string.isRequired,
  onUserUpdate: PropTypes.func,
};
