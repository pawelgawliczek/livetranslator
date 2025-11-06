import { useEffect, useState } from 'react';
import { getUserCosts, getRoomCosts } from '../../utils/costAnalytics';

/**
 * TopCostDrivers - Shows Top 10 users, rooms, and multi-speaker rooms
 * Helps quickly identify biggest cost drivers
 */
export default function TopCostDrivers({ token, startDate, endDate }) {
  const [topUsers, setTopUsers] = useState([]);
  const [topRooms, setTopRooms] = useState([]);
  const [topMultiSpeaker, setTopMultiSpeaker] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token || !startDate || !endDate) return;

    const fetchTopDrivers = async () => {
      setLoading(true);
      setError(null);

      try {
        const start = startDate.toISOString();
        const end = endDate.toISOString();

        // Fetch top 10 users by total cost
        const usersData = await getUserCosts(token, {
          startDate,
          endDate,
          limit: 10,
          offset: 0,
          sortBy: 'total_cost',
          sortOrder: 'desc',
          search: null,
        });
        setTopUsers(usersData.users || []);

        // Fetch top 10 rooms by total cost
        const roomsData = await getRoomCosts(token, {
          startDate,
          endDate,
          limit: 10,
          offset: 0,
          sortBy: 'total_cost',
          sortOrder: 'desc',
          search: null,
        });
        setTopRooms(roomsData.rooms || []);

        // Fetch top 10 multi-speaker rooms by cost
        const multiSpeakerResponse = await fetch(
          `/api/admin/costs/multi-speaker/overview?start_date=${start}&end_date=${end}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );

        if (multiSpeakerResponse.ok) {
          const multiSpeakerData = await multiSpeakerResponse.json();
          // Sort by cost and take top 10
          const sortedRooms = (multiSpeakerData.rooms || [])
            .sort((a, b) => (b.total_cost_usd || 0) - (a.total_cost_usd || 0))
            .slice(0, 10);
          setTopMultiSpeaker(sortedRooms);
        }
      } catch (err) {
        console.error('Error fetching top drivers:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchTopDrivers();
  }, [token, startDate, endDate]);

  if (loading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-xl font-semibold text-fg mb-4">Top Cost Drivers</h2>
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-20 bg-bg-secondary rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card border border-red-500 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-red-600 mb-2">Top Cost Drivers</h2>
        <p className="text-sm text-red-500">{error}</p>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <h2 className="text-xl font-semibold text-fg mb-6">🔥 Top Cost Drivers</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Top 10 Users */}
        <div>
          <h3 className="text-sm font-semibold text-fg-secondary uppercase mb-3">
            👥 Top Users by Cost
          </h3>
          {topUsers.length === 0 ? (
            <p className="text-sm text-fg-secondary italic">No data</p>
          ) : (
            <div className="space-y-2">
              {topUsers.map((user, idx) => (
                <div
                  key={user.user_id}
                  className="flex items-center justify-between p-2 rounded hover:bg-bg-secondary transition-colors"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-xs font-semibold text-fg-secondary w-5 flex-shrink-0">
                      #{idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-fg truncate">
                        {user.display_name || user.email}
                      </div>
                      <div className="text-xs text-fg-secondary">
                        {user.room_count} rooms • {(user.stt_minutes || 0).toFixed(0)}m
                      </div>
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-fg ml-2 flex-shrink-0">
                    ${(user.total_cost_usd || 0).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top 10 Rooms */}
        <div>
          <h3 className="text-sm font-semibold text-fg-secondary uppercase mb-3">
            🏠 Top Rooms by Cost
          </h3>
          {topRooms.length === 0 ? (
            <p className="text-sm text-fg-secondary italic">No data</p>
          ) : (
            <div className="space-y-2">
              {topRooms.map((room, idx) => (
                <div
                  key={room.room_id}
                  className="flex items-center justify-between p-2 rounded hover:bg-bg-secondary transition-colors"
                >
                  <div className="flex items-center gap-2 flex-1 min-w-0">
                    <span className="text-xs font-semibold text-fg-secondary w-5 flex-shrink-0">
                      #{idx + 1}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-fg truncate">
                        {room.room_code}
                      </div>
                      <div className="text-xs text-fg-secondary">
                        {room.is_public ? 'Public' : 'Private'} • {(room.stt_minutes || 0).toFixed(0)}m
                      </div>
                    </div>
                  </div>
                  <div className="text-sm font-semibold text-fg ml-2 flex-shrink-0">
                    ${(room.total_cost_usd || 0).toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top 10 Multi-Speaker Rooms */}
        <div>
          <h3 className="text-sm font-semibold text-fg-secondary uppercase mb-3">
            🎙️ Top Multi-Speaker Rooms
          </h3>
          {topMultiSpeaker.length === 0 ? (
            <p className="text-sm text-fg-secondary italic">No multi-speaker rooms</p>
          ) : (
            <div className="space-y-2">
              {topMultiSpeaker.map((room, idx) => {
                const multiplier = room.speaker_count * (room.speaker_count - 1);
                return (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded hover:bg-bg-secondary transition-colors"
                  >
                    <div className="flex items-center gap-2 flex-1 min-w-0">
                      <span className="text-xs font-semibold text-fg-secondary w-5 flex-shrink-0">
                        #{idx + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-sm font-medium text-fg truncate">
                          {room.room_code}
                        </div>
                        <div className="text-xs text-fg-secondary">
                          {room.speaker_count} speakers • {multiplier}x multiplier
                        </div>
                      </div>
                    </div>
                    <div className="text-sm font-semibold text-fg ml-2 flex-shrink-0">
                      ${(room.total_cost_usd || 0).toFixed(2)}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 pt-4 border-t border-border">
        <p className="text-xs text-fg-secondary">
          💡 <span className="font-semibold">Tip:</span> Focus on top users and multi-speaker rooms
          to optimize costs. Multi-speaker rooms have N×(N-1) translation cost multiplier.
        </p>
      </div>
    </div>
  );
}
