import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { grantCredits } from '../../utils/adminApi';

/**
 * GrantCreditsModal - Modal for granting bonus credits to users
 * Part of US-010: Grant Bonus Credits to User
 */
export default function GrantCreditsModal({ isOpen, onClose, user, token, onSuccess }) {
  const { t } = useTranslation();

  // Form state
  const [hours, setHours] = useState('');
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Validation state
  const [hoursError, setHoursError] = useState('');
  const [reasonError, setReasonError] = useState('');
  const [touched, setTouched] = useState({ hours: false, reason: false });

  // Toast state
  const [toast, setToast] = useState(null);

  // Reset form when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setHours('');
      setReason('');
      setHoursError('');
      setReasonError('');
      setTouched({ hours: false, reason: false });
      setToast(null);
    }
  }, [isOpen]);

  // Validate hours
  const validateHours = (value) => {
    if (!value || value === '') {
      return t('admin.users.grantCredits.validation.hoursRequired');
    }
    const numValue = parseFloat(value);
    if (isNaN(numValue) || numValue < 0.1) {
      return t('admin.users.grantCredits.validation.hoursMin');
    }
    if (numValue > 100) {
      return t('admin.users.grantCredits.validation.hoursMax');
    }
    return '';
  };

  // Validate reason
  const validateReason = (value) => {
    if (!value || value.trim() === '') {
      return t('admin.users.grantCredits.validation.reasonRequired');
    }
    if (value.trim().length < 10) {
      return t('admin.users.grantCredits.validation.reasonMinLength');
    }
    return '';
  };

  // Handle hours change
  const handleHoursChange = (e) => {
    const value = e.target.value;
    setHours(value);
    if (touched.hours) {
      setHoursError(validateHours(value));
    }
  };

  // Handle hours blur
  const handleHoursBlur = () => {
    setTouched({ ...touched, hours: true });
    setHoursError(validateHours(hours));
  };

  // Handle reason change
  const handleReasonChange = (e) => {
    const value = e.target.value;
    setReason(value);
    if (touched.reason) {
      setReasonError(validateReason(value));
    }
  };

  // Handle reason blur
  const handleReasonBlur = () => {
    setTouched({ ...touched, reason: true });
    setReasonError(validateReason(reason));
  };

  // Check if form is valid
  const isFormValid = () => {
    const hError = validateHours(hours);
    const rError = validateReason(reason);
    return hError === '' && rError === '';
  };

  // Show toast notification
  const showToast = (type, message) => {
    setToast({ type, message });
    setTimeout(() => setToast(null), 5000);
  };

  // Handle submit
  const handleSubmit = async (e) => {
    e.preventDefault();

    // Mark all fields as touched for validation
    setTouched({ hours: true, reason: true });

    // Validate
    const hError = validateHours(hours);
    const rError = validateReason(reason);
    setHoursError(hError);
    setReasonError(rError);

    if (hError || rError) {
      return;
    }

    // Confirmation dialog
    const confirmed = window.confirm(
      t('admin.users.grantCredits.confirmMessage', {
        hours: parseFloat(hours),
        email: user.email
      })
    );

    if (!confirmed) {
      return;
    }

    // Submit
    setIsSubmitting(true);
    try {
      const result = await grantCredits(token, user.user_id, parseFloat(hours), reason.trim());

      console.log('[GrantCreditsModal] Success:', result);

      showToast('success', t('admin.users.grantCredits.successMessage', {
        hours: result.bonus_hours_granted || parseFloat(hours),
        email: user.email
      }));

      // Call success callback and close
      if (onSuccess) {
        onSuccess();
      }

      // Close after brief delay to show toast
      setTimeout(() => {
        onClose();
      }, 1000);

    } catch (error) {
      console.error('[GrantCreditsModal] Failed to grant credits:', error);

      showToast('error', t('admin.users.grantCredits.errorMessage', {
        error: error.message || 'Unknown error'
      }));

      setIsSubmitting(false);
    }
  };

  // Handle backdrop click
  const handleBackdropClick = (e) => {
    if (e.target === e.currentTarget && !isSubmitting) {
      onClose();
    }
  };

  // Handle content click (prevent backdrop close)
  const handleContentClick = (e) => {
    e.stopPropagation();
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4"
      onClick={handleBackdropClick}
    >
      <div
        role="dialog"
        className="bg-card border border-border rounded-lg shadow-xl max-w-md w-full"
        onClick={handleContentClick}
      >
        {/* Header */}
        <div className="border-b border-border p-6">
          <h2 className="text-xl font-bold">{t('admin.users.grantCredits.title')}</h2>
          <p className="text-sm text-muted mt-1">
            User: <span className="font-medium">{user.email}</span>
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-4">
          {/* Hours Input */}
          <div>
            <label htmlFor="hours" className="block text-sm font-medium mb-1">
              {t('admin.users.grantCredits.hoursLabel')}
            </label>
            <input
              id="hours"
              type="number"
              min="0.1"
              max="100"
              step="0.5"
              value={hours}
              onChange={handleHoursChange}
              onBlur={handleHoursBlur}
              placeholder={t('admin.users.grantCredits.hoursPlaceholder')}
              className={`w-full px-3 py-2 border rounded-md bg-background text-foreground ${
                hoursError && touched.hours ? 'border-red-500' : 'border-border'
              }`}
              disabled={isSubmitting}
            />
            {hoursError && touched.hours && (
              <p className="text-red-500 text-sm mt-1">{hoursError}</p>
            )}
          </div>

          {/* Reason Textarea */}
          <div>
            <label htmlFor="reason" className="block text-sm font-medium mb-1">
              {t('admin.users.grantCredits.reasonLabel')}
            </label>
            <textarea
              id="reason"
              value={reason}
              onChange={handleReasonChange}
              onBlur={handleReasonBlur}
              placeholder={t('admin.users.grantCredits.reasonPlaceholder')}
              rows={4}
              maxLength={500}
              className={`w-full px-3 py-2 border rounded-md bg-background text-foreground resize-none ${
                reasonError && touched.reason ? 'border-red-500' : 'border-border'
              }`}
              disabled={isSubmitting}
            />
            {reasonError && touched.reason && (
              <p className="text-red-500 text-sm mt-1">{reasonError}</p>
            )}
            <p className="text-xs text-muted mt-1">
              {reason.length}/500 characters
            </p>
          </div>
        </form>

        {/* Footer */}
        <div className="border-t border-border p-6 flex justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-4 py-2 bg-secondary text-foreground rounded hover:bg-opacity-80 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {t('admin.users.grantCredits.cancel')}
          </button>
          <button
            type="submit"
            onClick={handleSubmit}
            disabled={!isFormValid() || isSubmitting}
            className="px-4 py-2 bg-primary text-primary-foreground rounded hover:bg-opacity-90 transition disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Granting...' : t('admin.users.grantCredits.submit')}
          </button>
        </div>

        {/* Toast Notification */}
        {toast && (
          <div className="fixed top-20 right-5 z-[1000] pointer-events-none">
            <div
              className={`px-4 py-3 rounded-lg shadow-lg max-w-md pointer-events-auto toast-slide-in ${
                toast.type === 'success'
                  ? 'bg-green-500 text-white'
                  : 'bg-red-500 text-white'
              }`}
            >
              {toast.message}
            </div>
            <style>{`
              @keyframes slideIn {
                from {
                  transform: translateX(400px);
                  opacity: 0;
                }
                to {
                  transform: translateX(0);
                  opacity: 1;
                }
              }
              .toast-slide-in {
                animation: slideIn 0.3s ease-out;
              }
            `}</style>
          </div>
        )}
      </div>
    </div>
  );
}

GrantCreditsModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
  user: PropTypes.shape({
    user_id: PropTypes.number.isRequired,
    email: PropTypes.string.isRequired,
    display_name: PropTypes.string,
  }).isRequired,
  token: PropTypes.string.isRequired,
  onSuccess: PropTypes.func,
};
