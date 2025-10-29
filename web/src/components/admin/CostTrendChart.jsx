import { useState, useEffect } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { format } from 'date-fns';
import { getCostTimeseries, autoDetectGranularity, getAvailableGranularities, PROVIDER_COLORS, AGGREGATE_COLORS, exportToCSV } from '../../utils/costAnalytics';

export default function CostTrendChart({ token, startDate, endDate, userId, roomId }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Chart configuration state
  const [granularity, setGranularity] = useState('day');
  const [viewMode, setViewMode] = useState('normal'); // 'normal' or 'accumulated'
  const [dataGrouping, setDataGrouping] = useState('aggregate'); // 'aggregate' or 'by_provider'

  // Line toggles for aggregate view
  const [showTotal, setShowTotal] = useState(true);
  const [showSTT, setShowSTT] = useState(true);
  const [showMT, setShowMT] = useState(true);

  // Provider toggles
  const [sttProviders, setSttProviders] = useState({
    openai: true,
    soniox: true,
    google_v2: true,
    azure: true,
    speechmatics: true,
  });

  const [mtProviders, setMtProviders] = useState({
    deepl: true,
    azure_translator: true,
    openai: true,
  });

  // Auto-detect granularity when dates change
  useEffect(() => {
    if (startDate && endDate) {
      const detected = autoDetectGranularity(startDate, endDate);
      setGranularity(detected);
    }
  }, [startDate, endDate]);

  // Fetch data when configuration changes
  useEffect(() => {
    if (!token || !startDate || !endDate || !granularity) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await getCostTimeseries(token, {
          startDate,
          endDate,
          granularity,
          accumulated: viewMode === 'accumulated',
          byProvider: dataGrouping === 'by_provider',
          userId,
          roomId,
        });

        setData(result.data || []);
      } catch (err) {
        console.error('Error fetching cost timeseries:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, startDate, endDate, granularity, viewMode, dataGrouping, userId, roomId]);

  const availableGranularities = startDate && endDate ? getAvailableGranularities(startDate, endDate) : [];

  // Format timestamp for display
  const formatTimestamp = (timestamp) => {
    const date = new Date(timestamp);

    switch (granularity) {
      case 'hour':
        return format(date, 'MMM dd HH:mm');
      case 'day':
        return format(date, 'MMM dd');
      case 'week':
        return format(date, 'MMM dd');
      case 'month':
        return format(date, 'MMM yyyy');
      case 'year':
        return format(date, 'yyyy');
      default:
        return format(date, 'MMM dd');
    }
  };

  // Format currency for tooltip
  const formatCurrency = (value) => {
    if (value === undefined || value === null) return '$0.00';
    return `$${value.toFixed(2)}`;
  };

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;

    return (
      <div className="bg-gray-900 border border-gray-700 rounded p-3 shadow-lg">
        <p className="text-gray-300 font-semibold mb-2">{formatTimestamp(label)}</p>
        {payload.map((entry, index) => (
          <div key={index} className="flex items-center justify-between gap-4 text-sm">
            <span style={{ color: entry.color }} className="font-medium">
              {entry.name}:
            </span>
            <span className="text-white">{formatCurrency(entry.value)}</span>
          </div>
        ))}
      </div>
    );
  };

  // Export chart data
  const handleExport = () => {
    if (data.length === 0) return;

    const exportData = data.map((point) => {
      const row = {
        timestamp: formatTimestamp(point.timestamp),
      };

      if (dataGrouping === 'aggregate') {
        row.total_cost_usd = point.total_cost_usd;
        row.stt_cost_usd = point.stt_cost_usd;
        row.mt_cost_usd = point.mt_cost_usd;

        if (viewMode === 'accumulated') {
          row.accumulated_total = point.accumulated_cost_usd;
          row.accumulated_stt = point.accumulated_stt_cost_usd;
          row.accumulated_mt = point.accumulated_mt_cost_usd;
        }
      } else {
        // By provider view
        if (point.providers) {
          Object.entries(point.providers.stt || {}).forEach(([provider, cost]) => {
            row[`stt_${provider}`] = cost;
          });
          Object.entries(point.providers.mt || {}).forEach(([provider, cost]) => {
            row[`mt_${provider}`] = cost;
          });
        }
      }

      return row;
    });

    const filename = `cost-trend-${format(startDate, 'yyyy-MM-dd')}-to-${format(endDate, 'yyyy-MM-dd')}.csv`;
    exportToCSV(exportData, filename);
  };

  // Get unique providers from data (for by_provider view)
  const getUniqueProviders = () => {
    const sttSet = new Set();
    const mtSet = new Set();

    data.forEach((point) => {
      if (point.providers) {
        Object.keys(point.providers.stt || {}).forEach((p) => sttSet.add(p));
        Object.keys(point.providers.mt || {}).forEach((p) => mtSet.add(p));
      }
    });

    return {
      stt: Array.from(sttSet),
      mt: Array.from(mtSet),
    };
  };

  const uniqueProviders = dataGrouping === 'by_provider' ? getUniqueProviders() : { stt: [], mt: [] };

  if (loading) {
    return (
      <div className="bg-card rounded-lg p-6 border border-border">
        <h3 className="text-xl font-semibold text-fg mb-4">📈 Cost Trend</h3>
        <div className="flex items-center justify-center h-64">
          <div className="text-muted">Loading chart data...</div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card rounded-lg p-6 border border-border">
        <h3 className="text-xl font-semibold text-fg mb-4">📈 Cost Trend</h3>
        <div className="flex items-center justify-center h-64">
          <div className="text-red-400">Error: {error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card rounded-lg p-6 border border-border">
      <h3 className="text-xl font-semibold text-fg mb-4">📈 Cost Trend</h3>

      {/* Controls */}
      <div className="space-y-4 mb-6">
        {/* Granularity */}
        <div>
          <label className="text-muted text-sm font-medium block mb-2">Granularity:</label>
          <div className="flex gap-2 flex-wrap">
            {availableGranularities.map((g) => (
              <button
                key={g}
                onClick={() => setGranularity(g)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  granularity === g
                    ? 'bg-accent text-accent-fg'
                    : 'bg-bg-secondary text-muted hover:bg-accent hover:bg-opacity-20'
                }`}
              >
                {g.charAt(0).toUpperCase() + g.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {/* View Mode */}
        <div>
          <label className="text-muted text-sm font-medium block mb-2">View Mode:</label>
          <div className="flex gap-2">
            <button
              onClick={() => setViewMode('normal')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                viewMode === 'normal'
                  ? 'bg-accent text-accent-fg'
                  : 'bg-bg-secondary text-muted hover:bg-accent hover:bg-opacity-20'
              }`}
            >
              Normal
            </button>
            <button
              onClick={() => setViewMode('accumulated')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                viewMode === 'accumulated'
                  ? 'bg-accent text-accent-fg'
                  : 'bg-bg-secondary text-muted hover:bg-accent hover:bg-opacity-20'
              }`}
            >
              Accumulated (Cumulative)
            </button>
          </div>
        </div>

        {/* Data Grouping */}
        <div>
          <label className="text-muted text-sm font-medium block mb-2">Data View:</label>
          <div className="flex gap-2">
            <button
              onClick={() => setDataGrouping('aggregate')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                dataGrouping === 'aggregate'
                  ? 'bg-accent text-accent-fg'
                  : 'bg-bg-secondary text-muted hover:bg-accent hover:bg-opacity-20'
              }`}
            >
              Aggregate
            </button>
            <button
              onClick={() => setDataGrouping('by_provider')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                dataGrouping === 'by_provider'
                  ? 'bg-accent text-accent-fg'
                  : 'bg-bg-secondary text-muted hover:bg-accent hover:bg-opacity-20'
              }`}
            >
              By Provider
            </button>
          </div>
        </div>

        {/* Toggles */}
        {dataGrouping === 'aggregate' ? (
          <div className="bg-bg-secondary rounded-lg p-4 border border-border">
            <label className="text-fg text-sm font-medium block mb-2">Show:</label>
            <div className="flex gap-4 flex-wrap">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showTotal}
                  onChange={(e) => setShowTotal(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm text-fg">Total</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showSTT}
                  onChange={(e) => setShowSTT(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm text-fg">STT</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={showMT}
                  onChange={(e) => setShowMT(e.target.checked)}
                  className="w-4 h-4"
                />
                <span className="text-sm text-fg">MT</span>
              </label>
            </div>
          </div>
        ) : (
          <div className="bg-bg-secondary rounded-lg p-4 border border-border space-y-3">
            {uniqueProviders.stt.length > 0 && (
              <div>
                <label className="text-fg text-sm font-medium block mb-2">STT Providers:</label>
                <div className="flex gap-4 flex-wrap">
                  {uniqueProviders.stt.map((provider) => (
                    <label key={provider} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={sttProviders[provider] !== false}
                        onChange={(e) =>
                          setSttProviders((prev) => ({ ...prev, [provider]: e.target.checked }))
                        }
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-fg">{provider}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
            {uniqueProviders.mt.length > 0 && (
              <div>
                <label className="text-fg text-sm font-medium block mb-2">MT Providers:</label>
                <div className="flex gap-4 flex-wrap">
                  {uniqueProviders.mt.map((provider) => (
                    <label key={provider} className="flex items-center gap-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={mtProviders[provider] !== false}
                        onChange={(e) =>
                          setMtProviders((prev) => ({ ...prev, [provider]: e.target.checked }))
                        }
                        className="w-4 h-4"
                      />
                      <span className="text-sm text-fg">{provider}</span>
                    </label>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chart */}
      {data.length > 0 ? (
        <ResponsiveContainer width="100%" height={400}>
          <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTimestamp}
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} tickFormatter={formatCurrency} />
            <Tooltip content={<CustomTooltip />} />
            <Legend />

            {dataGrouping === 'aggregate' ? (
              <>
                {showTotal && (
                  <Line
                    type="monotone"
                    dataKey={viewMode === 'accumulated' ? 'accumulated_cost_usd' : 'total_cost_usd'}
                    stroke={AGGREGATE_COLORS.total}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="Total"
                  />
                )}
                {showSTT && (
                  <Line
                    type="monotone"
                    dataKey={viewMode === 'accumulated' ? 'accumulated_stt_cost_usd' : 'stt_cost_usd'}
                    stroke={AGGREGATE_COLORS.stt}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="STT"
                  />
                )}
                {showMT && (
                  <Line
                    type="monotone"
                    dataKey={viewMode === 'accumulated' ? 'accumulated_mt_cost_usd' : 'mt_cost_usd'}
                    stroke={AGGREGATE_COLORS.mt}
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    name="MT"
                  />
                )}
              </>
            ) : (
              <>
                {/* STT Provider lines */}
                {uniqueProviders.stt
                  .filter((provider) => sttProviders[provider] !== false)
                  .map((provider) => (
                    <Line
                      key={`stt-${provider}`}
                      type="monotone"
                      dataKey={(point) => point.providers?.stt?.[provider] || 0}
                      stroke={PROVIDER_COLORS[provider] || '#6b7280'}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      name={`STT: ${provider}`}
                    />
                  ))}

                {/* MT Provider lines */}
                {uniqueProviders.mt
                  .filter((provider) => mtProviders[provider] !== false)
                  .map((provider) => (
                    <Line
                      key={`mt-${provider}`}
                      type="monotone"
                      dataKey={(point) => point.providers?.mt?.[provider] || 0}
                      stroke={PROVIDER_COLORS[provider] || '#6b7280'}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      name={`MT: ${provider}`}
                      strokeDasharray="5 5"
                    />
                  ))}
              </>
            )}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <div className="flex items-center justify-center h-64 text-muted">
          No data available for the selected period
        </div>
      )}

      {/* Export Button */}
      <div className="mt-4 flex justify-end">
        <button
          onClick={handleExport}
          disabled={data.length === 0}
          className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:bg-bg-secondary disabled:text-muted disabled:cursor-not-allowed transition-colors"
        >
          Export Chart Data (CSV)
        </button>
      </div>
    </div>
  );
}
