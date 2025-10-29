import { formatCurrency, formatNumber } from '../../utils/costAnalytics';

export default function CostOverviewCards({ overview, loading }) {
  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[...Array(6)].map((_, i) => (
          <div key={i} className="bg-card rounded-lg p-3 animate-pulse border border-border">
            <div className="h-3 bg-bg-secondary rounded w-1/2 mb-2"></div>
            <div className="h-6 bg-bg-secondary rounded w-3/4"></div>
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
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {cards.map((card, index) => (
        <div key={index} className="bg-card rounded-lg p-3 border border-border">
          <div className="flex items-center justify-between mb-1">
            <span className="text-lg">{card.icon}</span>
            {card.change !== null && card.change !== undefined && (
              <span
                className={`text-xs font-medium ${
                  card.change >= 0 ? 'text-green-400' : 'text-red-400'
                }`}
              >
                {card.change >= 0 ? '↑' : '↓'} {Math.abs(card.change).toFixed(1)}%
              </span>
            )}
          </div>
          <div className="text-muted text-xs font-medium mb-1">{card.label}</div>
          <div className="text-fg text-lg font-bold">
            {card.value}
          </div>
          {card.subValue && (
            <div className="text-muted opacity-70 text-xs mt-0.5">{card.subValue}</div>
          )}
        </div>
      ))}
    </div>
  );
}
