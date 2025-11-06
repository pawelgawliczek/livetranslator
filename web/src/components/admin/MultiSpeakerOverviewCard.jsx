import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';

/**
 * MultiSpeakerOverviewCard - Shows summary of multi-speaker room costs
 */
export default function MultiSpeakerOverviewCard({ token, startDate, endDate }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );

        if (!response.ok) throw new Error('Failed to fetch multi-speaker data');
        const result = await response.json();
        setData(result);
      } catch (err) {
        console.error('Multi-speaker fetch error:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [token, startDate, endDate]);

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6 animate-pulse">
        <div className="h-6 bg-bg-secondary rounded w-3/4 mb-4"></div>
        <div className="h-12 bg-bg-secondary rounded w-1/2 mb-2"></div>
        <div className="h-4 bg-bg-secondary rounded w-full"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card border border-red-500 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-red-600 mb-2">Multi-Speaker Rooms</h3>
        <p className="text-sm text-red-500">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const {
    total_rooms = 0,
    total_cost_usd = 0,
    avg_speakers_per_room = 0,
    avg_cost_per_room = 0,
    top_room
  } = data;

  // If no multi-speaker rooms, show a helpful message
  if (total_rooms === 0) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold text-fg mb-4">Multi-Speaker Rooms</h3>
        <div className="text-center py-8">
          <p className="text-fg-secondary mb-2">No multi-speaker rooms in this period</p>
          <p className="text-xs text-fg-secondary">
            Multi-speaker rooms have 2+ simultaneous speakers with real-time translation
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6 hover:border-accent transition-colors">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-fg">Multi-Speaker Rooms</h3>
        <span className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm font-medium">
          {total_rooms} rooms
        </span>
      </div>

      {/* Main Metric */}
      <div className="mb-4">
        <div className="text-3xl font-bold text-fg">
          ${(total_cost_usd || 0).toFixed(2)}
        </div>
        <p className="text-sm text-fg-secondary mt-1">
          Total cost ({(avg_speakers_per_room || 0).toFixed(1)} avg speakers/room)
        </p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 gap-4 mb-4">
        <div>
          <div className="text-sm text-fg-secondary">Avg Cost/Room</div>
          <div className="text-xl font-semibold text-fg">
            ${(avg_cost_per_room || 0).toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-sm text-fg-secondary">Top Room</div>
          <div className="text-xl font-semibold text-fg truncate" title={top_room?.room_code || 'N/A'}>
            {top_room?.room_code || 'N/A'}
          </div>
        </div>
      </div>

      {/* Info Alert */}
      <div className="bg-purple-50 border border-purple-200 rounded-lg p-3 mb-4">
        <p className="text-xs text-purple-800">
          💡 Multi-speaker rooms cost N×(N-1) translations.
          {total_rooms > 0 && avg_speakers_per_room >= 3 && (
            <span className="font-semibold"> High multiplier detected!</span>
          )}
        </p>
      </div>

      {/* Link to Details */}
      <Link
        to="/admin/costs/multi-speaker"
        className="block w-full text-center px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
      >
        View Detailed Analysis →
      </Link>
    </div>
  );
}
