import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import { createNotification } from '../../utils/adminApi';

/**
 * CreateNotificationModal - Create notification form (Basic version - immediate only)
 */
export default function CreateNotificationModal({ token, onClose, onSuccess }) {
  const { t } = useTranslation();

  const [formData, setFormData] = useState({
    title: '',
    message: '',
    type: 'info',
    target: 'all',
    expires_in_seconds: 86400, // 24 hours
    is_dismissible: true
  });

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    setError(null);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    // Validation
    if (!formData.title.trim()) {
      setError(t('admin.notifications.create.error.titleRequired') || 'Title is required');
      setSubmitting(false);
      return;
    }

    if (!formData.message.trim()) {
      setError(t('admin.notifications.create.error.messageRequired') || 'Message is required');
      setSubmitting(false);
      return;
    }

    if (formData.title.length > 100) {
      setError(t('admin.notifications.create.error.titleTooLong') || 'Title must be 100 characters or less');
      setSubmitting(false);
      return;
    }

    if (formData.message.length > 500) {
      setError(t('admin.notifications.create.error.messageTooLong') || 'Message must be 500 characters or less');
      setSubmitting(false);
      return;
    }

    try {
      // Create notification (immediate only in v1)
      await createNotification(token, {
        ...formData,
        schedule_type: 'immediate'
      });

      onSuccess();
    } catch (err) {
      console.error('[CreateNotificationModal] Failed to create notification:', err);
      setError(err.message || t('admin.notifications.create.error.failed') || 'Failed to create notification');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex justify-between items-start mb-6">
            <h2 className="text-2xl font-bold text-gray-900">
              {t('admin.notifications.create.title') || 'Create Notification'}
            </h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition"
              disabled={submitting}
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Title */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('admin.notifications.create.field.title') || 'Title'} <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.title}
                onChange={(e) => handleChange('title', e.target.value)}
                placeholder={t('admin.notifications.create.placeholder.title') || 'e.g., System Maintenance'}
                maxLength={100}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                disabled={submitting}
              />
              <div className="text-xs text-gray-500 mt-1">
                {formData.title.length}/100 {t('admin.notifications.create.characters') || 'characters'}
              </div>
            </div>

            {/* Message */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('admin.notifications.create.field.message') || 'Message'} <span className="text-red-500">*</span>
              </label>
              <textarea
                value={formData.message}
                onChange={(e) => handleChange('message', e.target.value)}
                placeholder={t('admin.notifications.create.placeholder.message') || 'e.g., The system will be down for maintenance...'}
                maxLength={500}
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                disabled={submitting}
              />
              <div className="text-xs text-gray-500 mt-1">
                {formData.message.length}/500 {t('admin.notifications.create.characters') || 'characters'}
              </div>
            </div>

            {/* Type & Target */}
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('admin.notifications.create.field.type') || 'Type'} <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.type}
                  onChange={(e) => handleChange('type', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                  disabled={submitting}
                >
                  <option value="info">{t('admin.notifications.type.info') || 'Info'}</option>
                  <option value="warning">{t('admin.notifications.type.warning') || 'Warning'}</option>
                  <option value="success">{t('admin.notifications.type.success') || 'Success'}</option>
                  <option value="error">{t('admin.notifications.type.error') || 'Error'}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  {t('admin.notifications.create.field.target') || 'Target'} <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.target}
                  onChange={(e) => handleChange('target', e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                  disabled={submitting}
                >
                  <option value="all">{t('admin.notifications.target.all') || 'All Users'}</option>
                </select>
              </div>
            </div>

            {/* Expiration */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                {t('admin.notifications.create.field.expires') || 'Expires After'}
              </label>
              <select
                value={formData.expires_in_seconds}
                onChange={(e) => handleChange('expires_in_seconds', parseInt(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-blue-500 focus:border-blue-500"
                disabled={submitting}
              >
                <option value={3600}>1 {t('admin.notifications.create.hour') || 'hour'}</option>
                <option value={21600}>6 {t('admin.notifications.create.hours') || 'hours'}</option>
                <option value={86400}>24 {t('admin.notifications.create.hours') || 'hours'}</option>
                <option value={604800}>7 {t('admin.notifications.create.days') || 'days'}</option>
              </select>
            </div>

            {/* Dismissible */}
            <div className="flex items-center">
              <input
                type="checkbox"
                id="dismissible"
                checked={formData.is_dismissible}
                onChange={(e) => handleChange('is_dismissible', e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded"
                disabled={submitting}
              />
              <label htmlFor="dismissible" className="ml-2 block text-sm text-gray-700">
                {t('admin.notifications.create.field.dismissible') || 'Allow users to dismiss this notification'}
              </label>
            </div>

            {/* Actions */}
            <div className="flex justify-end gap-3 pt-4 border-t">
              <button
                type="button"
                onClick={onClose}
                className="px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition"
                disabled={submitting}
              >
                {t('admin.notifications.create.cancel') || 'Cancel'}
              </button>
              <button
                type="submit"
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition disabled:opacity-50 disabled:cursor-not-allowed"
                disabled={submitting}
              >
                {submitting
                  ? (t('admin.notifications.create.sending') || 'Sending...')
                  : (t('admin.notifications.create.send') || 'Send Notification')}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}

CreateNotificationModal.propTypes = {
  token: PropTypes.string.isRequired,
  onClose: PropTypes.func.isRequired,
  onSuccess: PropTypes.func.isRequired,
};
