import { useState } from 'react';
import { format } from 'date-fns';
import { getDatePresets } from '../../utils/costAnalytics';

export default function DateRangePicker({ startDate, endDate, onChange }) {
  const [showCustom, setShowCustom] = useState(false);
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
        <div className="mt-3 pt-3 border-t border-border flex flex-wrap items-end gap-2">
          <div className="flex-1 min-w-[120px]">
            <label className="block text-muted text-xs mb-1">Start</label>
            <input
              type="date"
              value={customStart}
              onChange={(e) => setCustomStart(e.target.value)}
              className="w-full px-2 py-1.5 bg-bg-secondary border border-border rounded text-fg text-xs focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div className="flex-1 min-w-[120px]">
            <label className="block text-muted text-xs mb-1">End</label>
            <input
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
      )}
    </div>
  );
}
