import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import Modal from '../ui/Modal';
import { getSelectableLanguages } from '../../constants/languages';

/**
 * LanguagePickerModal - Modal for selecting user's language
 *
 * Features:
 * - Dropdown with all available languages (except "auto")
 * - Displays language flag + name
 * - Backdrop click or "Done" button to close
 */
export default function LanguagePickerModal({
  isOpen,
  currentLanguage,
  onLanguageChange,
  onClose
}) {
  const { t } = useTranslation();
  const selectableLanguages = getSelectableLanguages();

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div className="space-y-4">
        {/* Header */}
        <h3 className="text-xl font-semibold text-fg m-0">
          {t('settings.myLanguage')}
        </h3>

        {/* Description */}
        <p className="text-sm text-muted m-0">
          {t('settings.selectLanguage')}
          {' '}
          {t('settings.selectLanguageRequired')}
        </p>

        {/* Language Selector */}
        <div>
          <label className="block text-sm text-muted mb-2">
            {t('settings.languageLabel')}
          </label>
          <select
            value={currentLanguage || ''}
            onChange={(e) => onLanguageChange(e.target.value)}
            className="w-full px-3 py-3 bg-[#2a2a2a] border border-[#444] rounded-lg text-white text-base focus:outline-none focus:ring-2 focus:ring-accent focus:border-transparent"
          >
            {selectableLanguages.map(lang => (
              <option key={lang.code} value={lang.code}>
                {lang.flag} {lang.name}
              </option>
            ))}
          </select>
        </div>

        {/* Done Button */}
        <button
          onClick={onClose}
          className="w-full px-4 py-3 bg-accent text-white border-0 rounded-lg cursor-pointer font-semibold text-base hover:bg-accent/90 transition-colors"
        >
          Done
        </button>
      </div>
    </Modal>
  );
}

LanguagePickerModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  currentLanguage: PropTypes.string,
  onLanguageChange: PropTypes.func.isRequired,
  onClose: PropTypes.func.isRequired
};
