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
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h3 className="text-lg font-semibold text-white mb-4">📊 Time Period</h3>

      {/* Preset buttons */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-4">
        {Object.entries(presets).map(([key, preset]) => (
          <button
            key={key}
            onClick={() => handlePresetClick(preset)}
            className="px-4 py-2 bg-gray-700 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-600 hover:text-white transition-colors"
          >
            {preset.label}
          </button>
        ))}
        <button
          onClick={() => setShowCustom(!showCustom)}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            showCustom
              ? 'bg-blue-600 text-white'
              : 'bg-gray-700 text-gray-300 hover:bg-gray-600 hover:text-white'
          }`}
        >
          Custom Range
        </button>
      </div>

      {/* Custom date range */}
      {showCustom && (
        <div className="bg-gray-700 rounded-lg p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-gray-300 text-sm font-medium mb-2">Start Date</label>
              <input
                type="date"
                value={customStart}
                onChange={(e) => setCustomStart(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              />
            </div>
            <div>
              <label className="block text-gray-300 text-sm font-medium mb-2">End Date</label>
              <input
                type="date"
                value={customEnd}
                onChange={(e) => setCustomEnd(e.target.value)}
                className="w-full px-4 py-2 bg-gray-800 border border-gray-600 rounded-lg text-white focus:outline-none focus:border-blue-500"
              />
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleCustomApply}
              disabled={!customStart || !customEnd}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
            >
              Apply
            </button>
            <button
              onClick={handleReset}
              className="px-4 py-2 bg-gray-600 text-white rounded-lg font-medium hover:bg-gray-500 transition-colors"
            >
              Reset
            </button>
          </div>
        </div>
      )}

      {/* Current selection display */}
      <div className="mt-4 pt-4 border-t border-gray-700">
        <div className="text-sm text-gray-400">
          Current Period:{' '}
          <span className="text-white font-medium">
            {startDate && endDate
              ? `${format(startDate, 'MMM dd, yyyy')} - ${format(endDate, 'MMM dd, yyyy')}`
              : 'Not selected'}
          </span>
        </div>
      </div>
    </div>
  );
}
