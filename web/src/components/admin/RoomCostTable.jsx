import { useState } from 'react';
import { format } from 'date-fns';
import { formatCurrency } from '../../utils/costAnalytics';

export default function RoomCostTable({ rooms, page, totalRooms, onPageChange, onSort, onSearch, loading }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState('total_cost');
  const [sortOrder, setSortOrder] = useState('desc');

  const handleSort = (field) => {
    const newOrder = sortBy === field && sortOrder === 'desc' ? 'asc' : 'desc';
    setSortBy(field);
    setSortOrder(newOrder);
    if (onSort) {
      onSort(field, newOrder);
    }
  };

  const handleSearch = () => {
    if (onSearch) {
      onSearch(searchTerm);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-6">
        <h4 className="text-lg font-semibold text-white mb-4">🏠 Top Rooms by Cost</h4>
        <div className="animate-pulse space-y-4">
          {[...Array(5)].map((_, i) => (
            <div key={i} className="h-16 bg-gray-700 rounded"></div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-6 border border-gray-700">
      <h4 className="text-lg font-semibold text-white mb-4">🏠 Top Rooms by Cost</h4>

      {/* Search */}
      <div className="mb-4 flex gap-2">
        <input
          type="text"
          placeholder="Search by room code..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          onKeyPress={handleKeyPress}
          className="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:border-blue-500"
        />
        <button
          onClick={handleSearch}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
        >
          🔍 Search
        </button>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-3 px-2 text-gray-400 font-medium text-sm">#</th>
              <th className="text-left py-3 px-2 text-gray-400 font-medium text-sm">Room</th>
              <th className="text-left py-3 px-2 text-gray-400 font-medium text-sm">Owner</th>
              <th
                className="text-left py-3 px-2 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                onClick={() => handleSort('created_at')}
              >
                Created {sortBy === 'created_at' && (sortOrder === 'desc' ? '↓' : '↑')}
              </th>
              <th
                className="text-left py-3 px-2 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                onClick={() => handleSort('stt_cost')}
              >
                STT Cost {sortBy === 'stt_cost' && (sortOrder === 'desc' ? '↓' : '↑')}
              </th>
              <th
                className="text-left py-3 px-2 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                onClick={() => handleSort('mt_cost')}
              >
                MT Cost {sortBy === 'mt_cost' && (sortOrder === 'desc' ? '↓' : '↑')}
              </th>
              <th
                className="text-left py-3 px-2 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                onClick={() => handleSort('total_cost')}
              >
                Total Cost {sortBy === 'total_cost' && (sortOrder === 'desc' ? '↓' : '↑')}
              </th>
            </tr>
          </thead>
          <tbody>
            {rooms && rooms.length > 0 ? (
              rooms.map((room, index) => (
                <tr key={room.room_id} className="border-b border-gray-700 hover:bg-gray-750">
                  <td className="py-3 px-2 text-gray-400 text-sm">{page.offset + index + 1}</td>
                  <td className="py-3 px-2">
                    <div className="flex items-center gap-2">
                      <span className="text-lg">{room.is_public ? '🌍' : '🔒'}</span>
                      <span className="text-white font-medium text-sm">{room.room_code}</span>
                    </div>
                  </td>
                  <td className="py-3 px-2">
                    <div className="text-white text-sm">{room.owner.email}</div>
                    <div className="text-gray-400 text-xs">{room.owner.display_name}</div>
                  </td>
                  <td className="py-3 px-2 text-white text-sm">
                    {room.created_at ? format(new Date(room.created_at), 'MMM dd, yyyy') : '-'}
                  </td>
                  <td className="py-3 px-2">
                    <div className="text-white text-sm font-medium">{formatCurrency(room.stt_cost_usd)}</div>
                    <div className="text-gray-500 text-xs">{room.stt_minutes.toFixed(0)} min</div>
                  </td>
                  <td className="py-3 px-2">
                    <div className="text-white text-sm font-medium">{formatCurrency(room.mt_cost_usd)}</div>
                  </td>
                  <td className="py-3 px-2 text-white text-sm font-semibold">
                    {formatCurrency(room.total_cost_usd)}
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="7" className="py-8 text-center text-gray-400">
                  No rooms found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalRooms > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="text-gray-400">
            Showing {page.offset + 1} - {Math.min(page.offset + page.limit, totalRooms)} of {totalRooms} rooms
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => onPageChange && onPageChange(page.offset - page.limit)}
              disabled={page.offset === 0}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg font-medium hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed transition-colors"
            >
              ← Previous
            </button>
            <span className="px-4 py-2 text-gray-400">
              Page {Math.floor(page.offset / page.limit) + 1} of {Math.ceil(totalRooms / page.limit)}
            </span>
            <button
              onClick={() => onPageChange && onPageChange(page.offset + page.limit)}
              disabled={!page.has_more}
              className="px-4 py-2 bg-gray-700 text-white rounded-lg font-medium hover:bg-gray-600 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed transition-colors"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
