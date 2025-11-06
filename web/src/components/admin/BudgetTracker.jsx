import { useEffect, useState } from 'react';

/**
 * BudgetTracker - Monitor cost budgets and display alerts
 * Shows monthly budget status with visual indicators
 */
export default function BudgetTracker({ token }) {
  const [budgets, setBudgets] = useState([]);
  const [budgetStatuses, setBudgetStatuses] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [refreshTrigger, setRefreshTrigger] = useState(0);
  const [newBudget, setNewBudget] = useState({
    period_type: 'monthly',
    budget_usd: '',
    alert_threshold_pct: 80,
    critical_threshold_pct: 95,
  });

  // Fetch budgets
  useEffect(() => {
    if (!token) return;

    const fetchBudgets = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch('/api/budgets', {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) throw new Error('Failed to fetch budgets');

        const data = await response.json();
        setBudgets(data);

        // Fetch status for each budget
        const statuses = {};
        for (const budget of data) {
          if (budget.is_active) {
            const statusResponse = await fetch(`/api/budgets/${budget.id}/status`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (statusResponse.ok) {
              statuses[budget.id] = await statusResponse.json();
            }
          }
        }
        setBudgetStatuses(statuses);
      } catch (err) {
        console.error('Error fetching budgets:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchBudgets();
  }, [token, refreshTrigger]);

  const handleCreateBudget = async () => {
    if (!newBudget.budget_usd || parseFloat(newBudget.budget_usd) <= 0) {
      setError('Budget must be greater than 0');
      return;
    }

    try {
      const response = await fetch('/api/budgets', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          ...newBudget,
          budget_usd: parseFloat(newBudget.budget_usd),
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to create budget');
      }

      // Refresh budgets
      setShowCreateForm(false);
      setNewBudget({
        period_type: 'monthly',
        budget_usd: '',
        alert_threshold_pct: 80,
        critical_threshold_pct: 95,
      });
      setRefreshTrigger(prev => prev + 1);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleToggleBudget = async (budgetId, isActive) => {
    try {
      const response = await fetch(`/api/budgets/${budgetId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ is_active: !isActive }),
      });

      if (!response.ok) throw new Error('Failed to update budget');

      // Refresh budgets
      setRefreshTrigger(prev => prev + 1);
    } catch (err) {
      setError(err.message);
    }
  };

  const getStatusColor = (status) => {
    switch (status) {
      case 'exceeded':
        return 'bg-red-500';
      case 'critical':
        return 'bg-red-400';
      case 'warning':
        return 'bg-yellow-400';
      default:
        return 'bg-green-500';
    }
  };

  const getStatusText = (status) => {
    switch (status) {
      case 'exceeded':
        return 'Budget Exceeded';
      case 'critical':
        return 'Critical Alert';
      case 'warning':
        return 'Warning';
      default:
        return 'On Track';
    }
  };

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="animate-pulse">
          <div className="h-6 bg-bg-secondary rounded w-1/3 mb-4"></div>
          <div className="h-20 bg-bg-secondary rounded"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card border border-red-500 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-red-600 mb-2">Budget Tracker</h2>
        <p className="text-sm text-red-500">{error}</p>
      </div>
    );
  }

  const activeBudgets = budgets.filter((b) => b.is_active);

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-fg">💰 Budget Tracker</h2>
        <button
          onClick={() => setShowCreateForm(!showCreateForm)}
          className="px-4 py-2 bg-accent text-white rounded-lg hover:bg-accent-hover transition-colors text-sm font-medium"
        >
          {showCreateForm ? 'Cancel' : '+ Set Budget'}
        </button>
      </div>

      {/* Create Budget Form */}
      {showCreateForm && (
        <div className="mb-6 p-4 border border-border rounded-lg bg-bg-secondary">
          <h3 className="text-sm font-semibold text-fg mb-4">Create New Budget</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-fg-secondary mb-1">Period</label>
              <select
                value={newBudget.period_type}
                onChange={(e) => setNewBudget({ ...newBudget, period_type: e.target.value })}
                className="w-full px-3 py-2 bg-card border border-border rounded-lg text-fg"
              >
                <option value="monthly">Monthly</option>
                <option value="weekly">Weekly</option>
                <option value="daily">Daily</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-fg-secondary mb-1">Budget (USD)</label>
              <input
                type="number"
                step="0.01"
                value={newBudget.budget_usd}
                onChange={(e) => setNewBudget({ ...newBudget, budget_usd: e.target.value })}
                className="w-full px-3 py-2 bg-card border border-border rounded-lg text-fg"
                placeholder="100.00"
              />
            </div>
            <div>
              <label className="block text-xs text-fg-secondary mb-1">Warning Threshold (%)</label>
              <input
                type="number"
                min="0"
                max="100"
                value={newBudget.alert_threshold_pct}
                onChange={(e) => setNewBudget({ ...newBudget, alert_threshold_pct: parseInt(e.target.value) })}
                className="w-full px-3 py-2 bg-card border border-border rounded-lg text-fg"
              />
            </div>
            <div>
              <label className="block text-xs text-fg-secondary mb-1">Critical Threshold (%)</label>
              <input
                type="number"
                min="0"
                max="100"
                value={newBudget.critical_threshold_pct}
                onChange={(e) => setNewBudget({ ...newBudget, critical_threshold_pct: parseInt(e.target.value) })}
                className="w-full px-3 py-2 bg-card border border-border rounded-lg text-fg"
              />
            </div>
          </div>
          <button
            onClick={handleCreateBudget}
            className="mt-4 w-full px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors font-medium"
          >
            Create Budget
          </button>
        </div>
      )}

      {/* Active Budgets */}
      {activeBudgets.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-fg-secondary mb-2">No active budgets</p>
          <p className="text-xs text-fg-secondary">Set a budget to track costs and receive alerts</p>
        </div>
      ) : (
        <div className="space-y-4">
          {activeBudgets.map((budget) => {
            const status = budgetStatuses[budget.id];
            if (!status) return null;

            // Convert to numbers for safe operations
            const currentCost = parseFloat(status.current_cost_usd) || 0;
            const budgetAmount = parseFloat(status.budget.budget_usd) || 0;
            const projectedCost = status.projected_month_end_cost ? parseFloat(status.projected_month_end_cost) : null;

            return (
              <div key={budget.id} className="border border-border rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-lg font-semibold text-fg capitalize">
                      {budget.period_type} Budget
                    </h3>
                    <p className="text-xs text-fg-secondary">
                      {new Date(status.current_period_start).toLocaleDateString()} -{' '}
                      {new Date(status.current_period_end).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-2xl font-bold text-fg">
                      ${currentCost.toFixed(2)}
                    </div>
                    <div className="text-xs text-fg-secondary">
                      of ${budgetAmount.toFixed(2)}
                    </div>
                  </div>
                </div>

                {/* Progress Bar */}
                <div className="mb-3">
                  <div className="w-full bg-bg-secondary rounded-full h-3 overflow-hidden">
                    <div
                      className={`h-full transition-all ${getStatusColor(status.status)}`}
                      style={{ width: `${Math.min(status.percentage_used, 100)}%` }}
                    ></div>
                  </div>
                  <div className="flex items-center justify-between mt-1">
                    <span className="text-xs font-medium text-fg-secondary">
                      {status.percentage_used}% used
                    </span>
                    <span className={`text-xs font-semibold ${
                      status.status === 'exceeded' ? 'text-red-600' :
                      status.status === 'critical' ? 'text-red-500' :
                      status.status === 'warning' ? 'text-yellow-600' :
                      'text-green-600'
                    }`}>
                      {getStatusText(status.status)}
                    </span>
                  </div>
                </div>

                {/* Projected Cost (Monthly only) */}
                {projectedCost && (
                  <div className="text-xs text-fg-secondary mb-3">
                    📊 Projected month-end: ${projectedCost.toFixed(2)}
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleToggleBudget(budget.id, budget.is_active)}
                    className="px-3 py-1 text-xs border border-border rounded hover:bg-bg-secondary transition-colors"
                  >
                    Pause
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Info */}
      <div className="mt-6 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-xs text-blue-800">
          💡 <span className="font-semibold">Tip:</span> Set warning thresholds to receive alerts
          before exceeding your budget. Alerts are triggered automatically when thresholds are reached.
        </p>
      </div>
    </div>
  );
}
