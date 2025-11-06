import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import AdminLayout from '../components/admin/AdminLayout';
import DateRangePicker from '../components/admin/DateRangePicker';
import { getDatePresets } from '../utils/costAnalytics';

export default function AdminMultiSpeakerPage({ token, onLogout }) {
  const navigate = useNavigate();
  const presets = getDatePresets();
  const [startDate, setStartDate] = useState(presets.last7days.start);
  const [endDate, setEndDate] = useState(presets.last7days.end);

  const [overview, setOverview] = useState(null);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch multi-speaker overview
  useEffect(() => {
    if (!token || !startDate || !endDate) return;

    const fetchData = async () => {
      setLoading(true);
      setError(null);

      try {
        const start = startDate.toISOString();
        const end = endDate.toISOString();

        const response = await fetch(
          `/api/admin/costs/multi-speaker/overview?start_date=${start}&end_date=${end}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );

        if (!response.ok) {
          if (response.status === 403 || response.status === 401) {
            onLogout && onLogout();
            navigate('/login');
            return;
          }
          throw new Error('Failed to fetch data');
        }

        const data = await response.json();
        setOverview(data);
        setRooms(data.rooms || []);
      } catch (err) {
        console.error('Error:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, startDate, endDate, navigate, onLogout]);

  return (
    <AdminLayout title="Multi-Speaker Room Analytics" token={token} onLogout={onLogout}>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-fg">Multi-Speaker Analytics</h1>
            <p className="text-fg-secondary mt-1">
              Rooms with 2+ simultaneous speakers (N×(N-1) translation cost)
            </p>
          </div>
          <button
            onClick={() => navigate('/admin/costs')}
            className="px-4 py-2 border border-border rounded-lg hover:bg-bg-secondary transition-colors"
          >
            ← Back to Overview
          </button>
        </div>

        {/* Date Range Picker */}
        <DateRangePicker
          startDate={startDate}
          endDate={endDate}
          onStartDateChange={setStartDate}
          onEndDateChange={setEndDate}
          presets={presets}
        />

        {/* Error State */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">Error: {error}</p>
          </div>
        )}

        {/* Loading State */}
        {loading && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[1, 2, 3].map((i) => (
              <div key={i} className="bg-card border border-border rounded-lg p-6 animate-pulse">
                <div className="h-6 bg-bg-secondary rounded w-3/4 mb-4"></div>
                <div className="h-12 bg-bg-secondary rounded w-1/2"></div>
              </div>
            ))}
          </div>
        )}

        {/* Overview Cards */}
        {!loading && overview && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-sm text-fg-secondary mb-2">Total Rooms</h3>
                <div className="text-3xl font-bold text-fg">{overview.total_rooms || 0}</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-sm text-fg-secondary mb-2">Total Cost</h3>
                <div className="text-3xl font-bold text-fg">${(overview.total_cost_usd || 0).toFixed(2)}</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-sm text-fg-secondary mb-2">Avg Speakers/Room</h3>
                <div className="text-3xl font-bold text-fg">{(overview.avg_speakers_per_room || 0).toFixed(1)}</div>
              </div>
              <div className="bg-card border border-border rounded-lg p-6">
                <h3 className="text-sm text-fg-secondary mb-2">Avg Cost/Room</h3>
                <div className="text-3xl font-bold text-fg">${(overview.avg_cost_per_room || 0).toFixed(2)}</div>
              </div>
            </div>

            {/* Rooms Table */}
            <div className="bg-card border border-border rounded-lg">
              <div className="p-6 border-b border-border">
                <h2 className="text-xl font-semibold text-fg">Multi-Speaker Rooms</h2>
                <p className="text-sm text-fg-secondary mt-1">
                  Sorted by total cost (highest first)
                </p>
              </div>

              {rooms.length === 0 ? (
                <div className="p-12 text-center">
                  <p className="text-fg-secondary mb-2">No multi-speaker rooms found</p>
                  <p className="text-sm text-fg-secondary">
                    Try adjusting the date range or create rooms with multiple speakers
                  </p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-bg-secondary">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-fg-secondary uppercase">Room</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-fg-secondary uppercase">Speakers</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-fg-secondary uppercase">Translations</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-fg-secondary uppercase">STT Cost</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-fg-secondary uppercase">MT Cost</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-fg-secondary uppercase">Total Cost</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-fg-secondary uppercase">Multiplier</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {rooms.map((room, idx) => {
                        const multiplier = room.speaker_count * (room.speaker_count - 1);
                        const isHighCost = room.total_cost_usd > overview.avg_cost_per_room * 2;

                        return (
                          <tr key={idx} className={`hover:bg-bg-secondary ${isHighCost ? 'bg-red-50' : ''}`}>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <div className="font-medium text-fg">{room.room_code}</div>
                              <div className="text-xs text-fg-secondary">{room.is_public ? 'Public' : 'Private'}</div>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-fg">
                              {room.speaker_count}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-fg">
                              {room.translation_count}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-fg">
                              ${(room.stt_cost_usd || 0).toFixed(4)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-fg">
                              ${(room.mt_cost_usd || 0).toFixed(4)}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`font-semibold ${isHighCost ? 'text-red-600' : 'text-fg'}`}>
                                ${(room.total_cost_usd || 0).toFixed(4)}
                              </span>
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap">
                              <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                                multiplier > 6 ? 'bg-red-100 text-red-700' :
                                multiplier > 2 ? 'bg-yellow-100 text-yellow-700' :
                                'bg-green-100 text-green-700'
                              }`}>
                                {multiplier}x
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </AdminLayout>
  );
}
