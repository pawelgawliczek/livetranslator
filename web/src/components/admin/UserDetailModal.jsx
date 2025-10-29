import { useEffect, useState } from 'react';
import { format } from 'date-fns';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { getUserDetail, formatCurrency, AGGREGATE_COLORS } from '../../utils/costAnalytics';

export default function UserDetailModal({ token, userId, startDate, endDate, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token || !userId || !startDate || !endDate) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const result = await getUserDetail(token, userId, startDate, endDate);
        setData(result);
      } catch (err) {
        console.error('Error fetching user detail:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, userId, startDate, endDate]);

  if (!userId) return null;

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null;

    return (
      <div className="bg-gray-900 border border-gray-700 rounded p-3 shadow-lg">
        <p className="text-gray-300 font-semibold mb-2">{label}</p>
        {payload.map((entry, index) => (
          <div key={index} className="text-sm">
            <span style={{ color: entry.color }}>{entry.name}: </span>
            <span className="text-white">{formatCurrency(entry.value)}</span>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-lg max-w-6xl w-full max-h-[90vh] overflow-y-auto border border-border">
        {/* Header */}
        <div className="sticky top-0 bg-card border-b border-border p-6 flex items-center justify-between">
          <h3 className="text-xl font-semibold text-fg">📊 User Details</h3>
          <button
            onClick={onClose}
            className="text-muted hover:text-fg transition-colors text-2xl font-bold"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-muted">Loading user details...</div>
            </div>
          ) : error ? (
            <div className="flex items-center justify-center h-64">
              <div className="text-red-400">Error: {error}</div>
            </div>
          ) : data ? (
            <>
              {/* User Info */}
              <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <div className="text-muted text-sm mb-1">Email</div>
                    <div className="text-fg font-medium">{data.user.email}</div>
                  </div>
                  <div>
                    <div className="text-muted text-sm mb-1">Display Name</div>
                    <div className="text-fg font-medium">{data.user.display_name}</div>
                  </div>
                  <div>
                    <div className="text-muted text-sm mb-1">Member Since</div>
                    <div className="text-fg font-medium">
                      {format(new Date(data.user.created_at), 'MMM dd, yyyy')}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted text-sm mb-1">Rooms Created</div>
                    <div className="text-fg font-medium">{data.summary.room_count}</div>
                  </div>
                </div>
              </div>

              {/* Cost Summary Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                  <div className="text-muted text-sm mb-2">Total Cost</div>
                  <div className="text-fg text-2xl font-bold">
                    {formatCurrency(data.summary.total_cost_usd)}
                  </div>
                </div>
                <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                  <div className="text-muted text-sm mb-2">STT Cost</div>
                  <div className="text-fg text-2xl font-bold">
                    {formatCurrency(data.summary.stt_cost_usd)}
                  </div>
                </div>
                <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                  <div className="text-muted text-sm mb-2">MT Cost</div>
                  <div className="text-fg text-2xl font-bold">
                    {formatCurrency(data.summary.mt_cost_usd)}
                  </div>
                </div>
              </div>

              {/* Daily Cost Trend */}
              {data.daily_costs && data.daily_costs.length > 0 && (
                <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                  <h4 className="text-lg font-semibold text-fg mb-4">Daily Cost Trend</h4>
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={data.daily_costs}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                      <XAxis dataKey="date" stroke="#9ca3af" style={{ fontSize: '12px' }} />
                      <YAxis stroke="#9ca3af" style={{ fontSize: '12px' }} tickFormatter={formatCurrency} />
                      <Tooltip content={<CustomTooltip />} />
                      <Line
                        type="monotone"
                        dataKey="cost_usd"
                        stroke={AGGREGATE_COLORS.total}
                        strokeWidth={2}
                        dot={{ r: 3 }}
                        name="Cost"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Provider Usage */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* STT Providers */}
                {data.provider_usage.stt && Object.keys(data.provider_usage.stt).length > 0 && (
                  <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                    <h4 className="text-lg font-semibold text-fg mb-4">STT Provider Usage</h4>
                    <div className="space-y-3">
                      {Object.entries(data.provider_usage.stt).map(([provider, usage]) => (
                        <div key={provider}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-fg text-sm font-medium">{provider}</span>
                            <span className="text-muted text-sm">{usage.percentage}%</span>
                          </div>
                          <div className="w-full bg-border rounded-full h-2">
                            <div
                              className="bg-blue-500 h-2 rounded-full transition-all"
                              style={{ width: `${usage.percentage}%` }}
                            ></div>
                          </div>
                          <div className="flex items-center justify-between mt-1 text-xs text-muted">
                            <span>{formatCurrency(usage.cost_usd)}</span>
                            <span>
                              {usage.minutes ? `${usage.minutes.toFixed(0)} min` : `${usage.units} ${usage.unit_type}`}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* MT Providers */}
                {data.provider_usage.mt && Object.keys(data.provider_usage.mt).length > 0 && (
                  <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                    <h4 className="text-lg font-semibold text-fg mb-4">MT Provider Usage</h4>
                    <div className="space-y-3">
                      {Object.entries(data.provider_usage.mt).map(([provider, usage]) => (
                        <div key={provider}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-fg text-sm font-medium">{provider}</span>
                            <span className="text-muted text-sm">{usage.percentage}%</span>
                          </div>
                          <div className="w-full bg-border rounded-full h-2">
                            <div
                              className="bg-green-500 h-2 rounded-full transition-all"
                              style={{ width: `${usage.percentage}%` }}
                            ></div>
                          </div>
                          <div className="flex items-center justify-between mt-1 text-xs text-muted">
                            <span>{formatCurrency(usage.cost_usd)}</span>
                            <span>{usage.units} {usage.unit_type}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Rooms Table */}
              {data.rooms && data.rooms.length > 0 && (
                <div className="bg-bg-secondary rounded-lg p-6 border border-border">
                  <h4 className="text-lg font-semibold text-fg mb-4">Rooms Created ({data.rooms.length})</h4>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left py-2 px-2 text-muted text-sm font-medium">Room Code</th>
                          <th className="text-left py-2 px-2 text-muted text-sm font-medium">Created</th>
                          <th className="text-left py-2 px-2 text-muted text-sm font-medium">Privacy</th>
                          <th className="text-right py-2 px-2 text-muted text-sm font-medium">STT Cost</th>
                          <th className="text-right py-2 px-2 text-muted text-sm font-medium">MT Cost</th>
                          <th className="text-right py-2 px-2 text-muted text-sm font-medium">Total</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.rooms.map((room) => (
                          <tr key={room.room_id} className="border-b border-border">
                            <td className="py-2 px-2 text-fg text-sm font-medium">{room.room_code}</td>
                            <td className="py-2 px-2 text-fg text-sm">
                              {format(new Date(room.created_at), 'MMM dd, yyyy')}
                            </td>
                            <td className="py-2 px-2 text-sm">
                              {room.is_public ? (
                                <span className="text-green-400">🌍 Public</span>
                              ) : (
                                <span className="text-muted">🔒 Private</span>
                              )}
                            </td>
                            <td className="py-2 px-2 text-right text-fg text-sm">
                              {formatCurrency(room.stt_cost_usd)}
                            </td>
                            <td className="py-2 px-2 text-right text-fg text-sm">
                              {formatCurrency(room.mt_cost_usd)}
                            </td>
                            <td className="py-2 px-2 text-right text-fg text-sm font-semibold">
                              {formatCurrency(room.total_cost_usd)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="sticky bottom-0 bg-card border-t border-border p-6 flex justify-end">
          <button
            onClick={onClose}
            className="px-6 py-2 bg-bg-secondary text-fg rounded-lg font-medium hover:bg-accent hover:bg-opacity-20 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
