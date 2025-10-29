import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { formatCurrency, formatNumber, PROVIDER_COLORS } from '../../utils/costAnalytics';

export default function ProviderBreakdownChart({ title, breakdown, type, loading }) {
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-gray-700 rounded w-1/3 mb-4"></div>
        <div className="h-64 bg-gray-700 rounded"></div>
      </div>
    );
  }

  if (!breakdown || Object.keys(breakdown).length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h4 className="text-lg font-semibold text-white mb-4">{title}</h4>
        <div className="flex items-center justify-center h-64 text-gray-400">
          No data available
        </div>
      </div>
    );
  }

  // Convert breakdown object to array and sort by cost
  const data = Object.entries(breakdown)
    .map(([provider, data]) => ({
      provider,
      cost: data.cost_usd,
      units: data.units,
      unitType: data.unit_type,
      percentage: data.percentage,
    }))
    .sort((a, b) => b.cost - a.cost);

  const totalCost = data.reduce((sum, item) => sum + item.cost, 0);

  // Custom tooltip
  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload || payload.length === 0) return null;

    const item = payload[0].payload;

    return (
      <div className="bg-gray-900 border border-gray-700 rounded p-3 shadow-lg">
        <p className="text-white font-semibold mb-2">{item.provider}</p>
        <p className="text-gray-300 text-sm">Cost: {formatCurrency(item.cost)}</p>
        <p className="text-gray-300 text-sm">
          Usage: {formatNumber(item.units)} {item.unitType}
        </p>
        <p className="text-gray-300 text-sm">{item.percentage.toFixed(1)}% of total</p>
      </div>
    );
  };

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h4 className="text-lg font-semibold text-white mb-4">{title}</h4>

      {/* Bar chart */}
      <ResponsiveContainer width="100%" height={300}>
        <BarChart data={data} layout="vertical" margin={{ top: 5, right: 30, left: 100, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis type="number" stroke="#9ca3af" style={{ fontSize: '12px' }} tickFormatter={formatCurrency} />
          <YAxis
            type="category"
            dataKey="provider"
            stroke="#9ca3af"
            style={{ fontSize: '12px' }}
            width={90}
          />
          <Tooltip content={<CustomTooltip />} />
          <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={PROVIDER_COLORS[entry.provider] || '#6b7280'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>

      {/* Stats summary */}
      <div className="mt-4 space-y-2">
        {data.map((item) => (
          <div key={item.provider} className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded"
                style={{ backgroundColor: PROVIDER_COLORS[item.provider] || '#6b7280' }}
              ></div>
              <span className="text-gray-300">{item.provider}</span>
            </div>
            <div className="text-right">
              <div className="text-white font-medium">{formatCurrency(item.cost)}</div>
              <div className="text-gray-500 text-xs">
                {formatNumber(item.units)} {item.unitType} ({item.percentage.toFixed(1)}%)
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Total */}
      <div className="mt-4 pt-4 border-t border-gray-700 flex items-center justify-between font-semibold">
        <span className="text-gray-300">{type === 'stt' ? 'Total STT' : 'Total MT'}:</span>
        <span className="text-white">{formatCurrency(totalCost)}</span>
      </div>

      {/* Average cost per unit */}
      {data.length > 0 && data[0].unitType && (
        <div className="mt-2 text-sm text-gray-400 text-right">
          Avg: {formatCurrency(totalCost / data.reduce((sum, d) => sum + d.units, 0))}/{data[0].unitType}
        </div>
      )}
    </div>
  );
}
