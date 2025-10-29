import { formatCurrency, formatNumber } from '../../utils/costAnalytics';

export default function CostOverviewCards({ overview, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="bg-gray-800 rounded-lg p-6 animate-pulse">
            <div className="h-4 bg-gray-700 rounded w-1/2 mb-4"></div>
            <div className="h-8 bg-gray-700 rounded w-3/4"></div>
          </div>
        ))}
      </div>
    );
  }

  if (!overview || !overview.totals) {
    return null;
  }

  const { totals } = overview;

  const cards = [
    {
      icon: '💰',
      label: 'Total Cost',
      value: formatCurrency(totals.cost_usd),
      change: totals.growth_rate,
    },
    {
      icon: '🎤',
      label: 'STT Cost',
      value: formatCurrency(totals.stt_cost_usd),
      subValue: null,
    },
    {
      icon: '🌐',
      label: 'MT Cost',
      value: formatCurrency(totals.mt_cost_usd),
      subValue: null,
    },
    {
      icon: '⏱️',
      label: 'Total Time',
      value: `${formatNumber(totals.total_minutes)} min`,
      subValue: `(${totals.total_hours.toFixed(2)} hrs)`,
    },
    {
      icon: '👥',
      label: 'Active Users',
      value: totals.active_users,
      subValue: null,
    },
    {
      icon: '🏠',
      label: 'Active Rooms',
      value: totals.active_rooms,
      subValue: null,
    },
  ];

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {cards.map((card, index) => (
        <div key={index} className="bg-gray-800 rounded-lg p-6 border border-gray-700">
          <div className="flex items-center justify-between mb-2">
            <span className="text-2xl">{card.icon}</span>
            {card.change !== null && card.change !== undefined && (
              <span
                className={`text-sm font-medium ${
                  card.change >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {card.change >= 0 ? '↑' : '↓'} {Math.abs(card.change).toFixed(1)}%
              </span>
            )}
          </div>
          <div className="text-gray-400 text-sm font-medium mb-1">{card.label}</div>
          <div className="text-white text-2xl font-bold">
            {card.value}
          </div>
          {card.subValue && (
            <div className="text-gray-500 text-sm mt-1">{card.subValue}</div>
          )}
        </div>
      ))}
    </div>
  );
}
