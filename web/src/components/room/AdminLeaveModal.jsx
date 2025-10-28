import React from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import Modal from '../ui/Modal';

/**
 * AdminLeaveModal - Warning modal for room admin leaving
 *
 * Displays warning that leaving will:
 * - Close the room for all participants
 * - Delete all message history
 * - Remove all participants
 *
 * Features:
 * - Stay button (cancel)
 * - Leave button (confirm exit)
 * - Orange border for warning emphasis
 */
export default function AdminLeaveModal({ isOpen, onStay, onLeave }) {
  const { t } = useTranslation();

  if (!isOpen) return null;

  return (
    <Modal isOpen={isOpen} onClose={onStay} maxWidth="400px">
      <div className="space-y-4">
        {/* Warning Icon */}
        <div className="text-[2.5rem] text-center mb-4">
          ⚠️
        </div>

        {/* Title */}
        <h3 className="m-0 mb-4 text-[1.3rem] text-center font-semibold text-fg-dark">
          {t('room.adminLeaveModal.title')}
        </h3>

        {/* Subtitle */}
        <p className="m-0 mb-6 text-[0.95rem] text-[#ccc] leading-relaxed">
          {t('room.adminLeaveModal.subtitle')}
        </p>

        {/* Warning Points List */}
        <ul className="m-0 mb-6 text-sm text-[#ccc] leading-relaxed pl-6">
          <li>{t('room.adminLeaveModal.point1')}</li>
          <li>{t('room.adminLeaveModal.point2')}</li>
          <li>{t('room.adminLeaveModal.point3')}</li>
          <li>{t('room.adminLeaveModal.point4')}</li>
        </ul>

        {/* Rejoin Note */}
        <p className="m-0 mb-6 text-[0.85rem] text-muted-dark italic">
          {t('room.adminLeaveModal.rejoinNote')}
        </p>

        {/* Action Buttons */}
        <div className="flex gap-3">
          <button
            onClick={onStay}
            className="flex-1 px-4 py-3 bg-blue-500 text-white border-0 rounded-lg cursor-pointer font-semibold text-base hover:bg-blue-600 transition-colors"
          >
            {t('room.adminLeaveModal.stay')}
          </button>
          <button
            onClick={onLeave}
            className="flex-1 px-4 py-3 bg-red-600 text-white border-0 rounded-lg cursor-pointer font-semibold text-base hover:bg-red-700 transition-colors"
          >
            {t('room.adminLeaveModal.leave')}
          </button>
        </div>
      </div>
    </Modal>
  );
}

AdminLeaveModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onStay: PropTypes.func.isRequired,
  onLeave: PropTypes.func.isRequired
};
