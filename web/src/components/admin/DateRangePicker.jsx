import { useState } from 'react';
import PropTypes from 'prop-types';
import { format } from 'date-fns';
import { getDatePresets } from '../../utils/costAnalytics';

export default function DateRangePicker({ startDate, endDate, onChange }) {
  const [showCustom, setShowCustom] = useState(false);
  const [error, setError] = useState(null);
  const [customStart, setCustomStart] = useState(
    startDate ? format(startDate, 'yyyy-MM-dd') : ''
  );
  const [customEnd, setCustomEnd] = useState(
    endDate ? format(endDate, 'yyyy-MM-dd') : ''
  );

  const presets = getDatePresets();

  const handlePresetClick = (preset) => {
    setShowCustom(false);
    if (onChange) {
      onChange(preset.start, preset.end);
    }
  };

  const handleCustomApply = () => {
    if (customStart && customEnd) {
      const start = new Date(customStart);
      start.setHours(0, 0, 0, 0);

      const end = new Date(customEnd);
      end.setHours(23, 59, 59, 999);

      // Validation: Start <= End
      if (start > end) {
        setError('Start date must be before or equal to end date');
        return;
      }

      // Validation: Max range 1 year (365 days)
      const diffMs = end - start;
      const diffDays = diffMs / (1000 * 60 * 60 * 24);
      if (diffDays > 365) {
        setError('Date range cannot exceed 1 year (365 days)');
        return;
      }

      // Clear error on success
      setError(null);
      if (onChange) {
        onChange(start, end);
      }
      setShowCustom(false);
    }
  };

  const handleReset = () => {
    const preset = presets.last7days;
    setCustomStart(format(preset.start, 'yyyy-MM-dd'));
    setCustomEnd(format(preset.end, 'yyyy-MM-dd'));
    if (onChange) {
      onChange(preset.start, preset.end);
    }
    setShowCustom(false);
  };

  return (
    <div className="bg-card rounded-lg p-4 border border-border">
      <div className="flex flex-wrap items-center gap-2">
        {/* Preset buttons - compact inline */}
        {Object.entries(presets).map(([key, preset]) => (
          <button
            key={key}
            onClick={() => handlePresetClick(preset)}
            className="px-3 py-1.5 bg-bg-secondary text-muted rounded text-xs font-medium hover:bg-accent hover:text-accent-fg transition-colors"
          >
            {preset.label}
          </button>
        ))}
        <button
          onClick={() => setShowCustom(!showCustom)}
          className={`px-3 py-1.5 rounded text-xs font-medium transition-colors ${
            showCustom
              ? 'bg-accent text-accent-fg'
              : 'bg-bg-secondary text-muted hover:bg-accent hover:text-accent-fg'
          }`}
        >
          Custom
        </button>

        {/* Current selection display - inline */}
        <div className="ml-auto text-xs text-muted">
          <span className="opacity-70">Period:</span>{' '}
          <span className="text-fg font-medium">
            {startDate && endDate
              ? `${format(startDate, 'MMM dd')} - ${format(endDate, 'MMM dd, yyyy')}`
              : 'Not selected'}
          </span>
        </div>
      </div>

      {/* Custom date range */}
      {showCustom && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="flex flex-wrap items-end gap-2">
            <div className="flex-1 min-w-[120px]">
              <label htmlFor="date-start" className="block text-muted text-xs mb-1">Start</label>
              <input
                id="date-start"
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="w-full px-2 py-1.5 bg-bg-secondary border border-border rounded text-fg text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <div className="flex-1 min-w-[120px]">
              <label htmlFor="date-end" className="block text-muted text-xs mb-1">End</label>
              <input
                id="date-end"
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="w-full px-2 py-1.5 bg-bg-secondary border border-border rounded text-fg text-xs focus:outline-none focus:ring-2 focus:ring-ring"
              />
            </div>
            <button
              onClick={handleCustomApply}
              disabled={!customStart || !customEnd}
              className="px-3 py-1.5 bg-accent text-accent-fg rounded text-xs font-medium hover:bg-accent-dark disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Apply
            </button>
            <button
              onClick={handleReset}
              className="px-3 py-1.5 bg-bg-secondary text-muted rounded text-xs font-medium hover:bg-accent hover:text-accent-fg transition-colors"
            >
              Reset
            </button>
          </div>
          {error && (
            <div className="mt-2 p-2 bg-red-100 border border-red-400 text-red-700 rounded text-sm">
              {error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

DateRangePicker.propTypes = {
  startDate: PropTypes.instanceOf(Date).isRequired,
  endDate: PropTypes.instanceOf(Date).isRequired,
  onChange: PropTypes.func.isRequired,
};
