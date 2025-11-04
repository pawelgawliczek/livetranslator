import { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

/**
 * DailyBreakdownTable - US-004: Daily breakdown table with pagination
 *
 * Shows:
 * - Date
 * - New Signups
 * - Activated (count + %)
 * - Fast Activation (count + %)
 *
 * Color-coded activation percentages
 */
export default function DailyBreakdownTable({ data, loading }) {
  const { t } = useTranslation();
  const [currentPage, setCurrentPage] = useState(1);
  const rowsPerPage = 30;

  // Loading state
  if (loading) {
    return (
      <div className="bg-card rounded-lg border border-border p-6">
        <h3 className="text-lg font-semibold text-fg mb-4">
          {t('admin.acquisition.dailyBreakdown') || 'Daily Breakdown'}
        </h3>
        <div className="animate-pulse space-y-2">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-8 bg-bg-secondary rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div className="bg-card rounded-lg border border-border p-6">
        <h3 className="text-lg font-semibold text-fg mb-4">
          {t('admin.acquisition.dailyBreakdown') || 'Daily Breakdown'}
        </h3>
        <div className="text-center text-muted py-8">
          <p>{t('admin.acquisition.empty') || 'No data available'}</p>
        </div>
      </div>
    );
  }

  // Pagination
  const totalPages = Math.ceil(data.length / rowsPerPage);
  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = startIndex + rowsPerPage;
  const currentData = data.slice(startIndex, endIndex);

  // Color coding helper
  const getActivationColor = (pct) => {
    if (pct >= 40) return 'text-green-600 bg-green-100';
    if (pct >= 20) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  const getFastActivationColor = (pct) => {
    if (pct >= 25) return 'text-green-600 bg-green-100';
    if (pct >= 10) return 'text-yellow-600 bg-yellow-100';
    return 'text-red-600 bg-red-100';
  };

  return (
    <div className="bg-card rounded-lg border border-border p-6">
      <h3 className="text-lg font-semibold text-fg mb-4">
        {t('admin.acquisition.dailyBreakdown') || 'Daily Breakdown'}
      </h3>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-border">
            <tr className="text-left">
              <th className="pb-3 font-medium text-muted">
                {t('admin.acquisition.date') || 'Date'}
              </th>
              <th className="pb-3 font-medium text-muted text-right">
                {t('admin.acquisition.newSignups') || 'New Signups'}
              </th>
              <th className="pb-3 font-medium text-muted text-right">
                {t('admin.acquisition.activated') || 'Activated'}
              </th>
              <th className="pb-3 font-medium text-muted text-right">
                {t('admin.acquisition.activationPct') || 'Activation %'}
              </th>
              <th className="pb-3 font-medium text-muted text-right">
                {t('admin.acquisition.fastActivated') || 'Fast Activation'}
              </th>
              <th className="pb-3 font-medium text-muted text-right">
                {t('admin.acquisition.fastActivationPct') || 'Fast %'}
              </th>
            </tr>
          </thead>
          <tbody>
            {currentData.map((row, index) => (
              <tr
                key={row.date}
                className={`border-b border-border last:border-0 ${
                  index % 2 === 0 ? 'bg-bg-secondary/30' : ''
                }`}
              >
                <td className="py-2 text-fg font-medium">{row.date}</td>
                <td className="py-2 text-right text-fg">{row.new_signups}</td>
                <td className="py-2 text-right text-fg">{row.activated}</td>
                <td className="py-2 text-right">
                  <span
                    className={`px-2 py-1 rounded text-xs font-semibold ${getActivationColor(
                      row.activation_pct
                    )}`}
                  >
                    {row.activation_pct.toFixed(1)}%
                  </span>
                </td>
                <td className="py-2 text-right text-fg">{row.fast_activated}</td>
                <td className="py-2 text-right">
                  <span
                    className={`px-2 py-1 rounded text-xs font-semibold ${getFastActivationColor(
                      row.fast_activation_pct
                    )}`}
                  >
                    {row.fast_activation_pct.toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-4 flex items-center justify-between">
          <div className="text-xs text-muted">
            Showing {startIndex + 1}-{Math.min(endIndex, data.length)} of {data.length} rows
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
              disabled={currentPage === 1}
              className="px-3 py-1 bg-bg-secondary text-muted rounded text-xs hover:bg-accent hover:text-accent-fg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <div className="flex items-center gap-1">
              {[...Array(totalPages)].map((_, i) => {
                const page = i + 1;
                // Show first, last, current, and 1 on each side
                if (
                  page === 1 ||
                  page === totalPages ||
                  (page >= currentPage - 1 && page <= currentPage + 1)
                ) {
                  return (
                    <button
                      key={page}
                      onClick={() => setCurrentPage(page)}
                      className={`px-2 py-1 rounded text-xs transition-colors ${
                        page === currentPage
                          ? 'bg-accent text-accent-fg font-semibold'
                          : 'bg-bg-secondary text-muted hover:bg-accent hover:text-accent-fg'
                      }`}
                    >
                      {page}
                    </button>
                  );
                } else if (page === currentPage - 2 || page === currentPage + 2) {
                  return (
                    <span key={page} className="text-muted px-1">
                      ...
                    </span>
                  );
                }
                return null;
              })}
            </div>
            <button
              onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
              disabled={currentPage === totalPages}
              className="px-3 py-1 bg-bg-secondary text-muted rounded text-xs hover:bg-accent hover:text-accent-fg disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

DailyBreakdownTable.propTypes = {
  data: PropTypes.arrayOf(
    PropTypes.shape({
      date: PropTypes.string.isRequired,
      new_signups: PropTypes.number.isRequired,
      activated: PropTypes.number.isRequired,
      activation_pct: PropTypes.number.isRequired,
      fast_activated: PropTypes.number.isRequired,
      fast_activation_pct: PropTypes.number.isRequired,
    })
  ),
  loading: PropTypes.bool,
};
