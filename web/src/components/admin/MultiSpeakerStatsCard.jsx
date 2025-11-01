import { formatCurrency } from '../../utils/costAnalytics';

export default function MultiSpeakerStatsCard({ stats, loading }) {
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <span className="text-2xl">🎤</span>
          Multi-Speaker Usage Overview
        </h3>
        <div className="animate-pulse space-y-4">
          <div className="h-16 bg-gray-700 rounded"></div>
          <div className="h-16 bg-gray-700 rounded"></div>
        </div>
      </div>
    );
  }

  if (!stats) {
    return null;
  }

  const {
    active_multi_speaker_rooms,
    total_rooms,
    multi_speaker_percentage,
    total_multi_speaker_cost_usd,
    average_speakers_per_room,
    high_cost_room_count,
    highest_cost_room
  } = stats;

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <span className="text-2xl">🎤</span>
        Multi-Speaker Usage Overview
      </h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
        {/* Active Multi-Speaker Rooms */}
        <div className="bg-gray-900 rounded-lg p-4">
          <div className="text-sm text-gray-400 mb-1">Active Rooms</div>
          <div className="text-2xl font-bold text-blue-400">
            {active_multi_speaker_rooms}
            <span className="text-sm text-gray-500 ml-2">
              / {total_rooms} ({multi_speaker_percentage}%)
            </span>
          </div>
        </div>

        {/* Total Cost */}
        <div className="bg-gray-900 rounded-lg p-4">
          <div className="text-sm text-gray-400 mb-1">Total Cost</div>
          <div className="text-2xl font-bold text-green-400">
            {formatCurrency(total_multi_speaker_cost_usd)}
          </div>
        </div>

        {/* Average Speakers */}
        <div className="bg-gray-900 rounded-lg p-4">
          <div className="text-sm text-gray-400 mb-1">Avg Speakers/Room</div>
          <div className="text-2xl font-bold text-purple-400">
            {average_speakers_per_room.toFixed(1)}
          </div>
        </div>
      </div>

      {/* High Cost Room Alert */}
      {high_cost_room_count > 0 && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 mb-4">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-red-500 text-lg">🔴</span>
            <span className="font-semibold text-red-400">
              {high_cost_room_count} {high_cost_room_count === 1 ? 'room' : 'rooms'} with high costs
            </span>
          </div>
          <div className="text-sm text-gray-300">
            {high_cost_room_count === 1 ? 'This room costs' : 'These rooms cost'} more than $1.00/hour.
            Consider reviewing translation settings or speaker configuration.
          </div>
        </div>
      )}

      {/* Highest Cost Room */}
      {highest_cost_room && highest_cost_room.room_code && (
        <div className="bg-gray-900 rounded-lg p-4">
          <div className="text-sm text-gray-400 mb-2">Highest Cost Room</div>
          <div className="flex items-center justify-between">
            <div>
              <div className="font-mono text-blue-400">{highest_cost_room.room_code}</div>
              <div className="text-xs text-gray-500 mt-1">
                🎤×{highest_cost_room.speaker_count} speakers
              </div>
            </div>
            <div className="text-right">
              <div className="text-xl font-bold text-red-400">
                {formatCurrency(highest_cost_room.total_cost_usd)}
              </div>
              <button
                onClick={() => window.location.href = `/admin/costs/rooms/${highest_cost_room.room_code}`}
                className="text-xs text-blue-400 hover:text-blue-300 transition-colors mt-1"
              >
                View Details →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Empty State */}
      {active_multi_speaker_rooms === 0 && (
        <div className="bg-gray-900 rounded-lg p-6 text-center">
          <div className="text-4xl mb-2">🎙️</div>
          <div className="text-gray-400 text-sm">
            No multi-speaker rooms active in this period
          </div>
        </div>
      )}
    </div>
  );
}
