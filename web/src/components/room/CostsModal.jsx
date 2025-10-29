import React from 'react';
import PropTypes from 'prop-types';
import Modal from '../ui/Modal';

/**
 * CostsModal - Display room usage costs breakdown
 *
 * Shows:
 * - Total cost in USD
 * - Breakdown by service (STT, MT)
 * - Event count per service
 * - Loading state
 */
export default function CostsModal({ isOpen, costs, onClose }) {
  if (!isOpen) return null;

  const getPipelineLabel = (pipeline) => {
    const labels = {
      mt: '🔤 Translation',
      stt: '🎤 STT'
    };
    return labels[pipeline] || pipeline;
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose}>
      <div className="space-y-4">
        {/* Header */}
        <h3 className="text-xl font-semibold text-fg-dark m-0">
          💰 Costs
        </h3>

        {/* Loading State */}
        {!costs ? (
          <div className="text-center text-muted-dark py-8 text-sm">
            Loading costs...
          </div>
        ) : (
          <>
            {/* Total Cost */}
            <div className="text-[1.75rem] font-bold text-blue-500 mb-4">
              ${costs.total_cost_usd.toFixed(6)}
            </div>

            {/* Breakdown */}
            <div className="flex flex-col gap-3 mb-4">
              {Object.entries(costs.breakdown || {}).map(([pipeline, data]) => (
                <div
                  key={pipeline}
                  className="bg-bg-secondary px-3.5 py-3.5 rounded-lg"
                >
                  <div className="font-semibold text-[0.95rem] mb-1">
                    {getPipelineLabel(pipeline)}
                  </div>
                  <div className="text-[0.8rem] text-muted-dark">
                    {data.events} events • ${data.cost_usd.toFixed(6)}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Close Button */}
        <button
          onClick={onClose}
          className="w-full px-4 py-3.5 bg-blue-500 text-white border-0 rounded-lg cursor-pointer font-semibold text-base hover:bg-blue-600 transition-colors"
        >
          Close
        </button>
      </div>
    </Modal>
  );
}

CostsModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  costs: PropTypes.shape({
    total_cost_usd: PropTypes.number.isRequired,
    breakdown: PropTypes.objectOf(
      PropTypes.shape({
        events: PropTypes.number.isRequired,
        cost_usd: PropTypes.number.isRequired
      })
    )
  }),
  onClose: PropTypes.func.isRequired
};
