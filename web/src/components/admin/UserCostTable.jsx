import { useState } from 'react';
import { formatCurrency, formatNumber } from '../../utils/costAnalytics';

export default function UserCostTable({ users, page, totalUsers, onPageChange, onSort, onSearch, onViewDetail, loading }) {
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
        <h4 className="text-lg font-semibold text-white mb-4">👥 Top Users by Cost</h4>
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
      <h4 className="text-lg font-semibold text-white mb-4">👥 Top Users by Cost</h4>

      {/* Search */}
      <div className="mb-4 flex gap-2">
        <input
          type="text"
          placeholder="Search by email or name..."
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
              <th className="text-left py-3 px-2 text-gray-400 font-medium text-sm">User</th>
              <th
                className="text-left py-3 px-2 text-gray-400 font-medium text-sm cursor-pointer hover:text-white"
                onClick={() => handleSort('room_count')}
              >
                Rooms {sortBy === 'room_count' && (sortOrder === 'desc' ? '↓' : '↑')}
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
              <th className="text-right py-3 px-2 text-gray-400 font-medium text-sm">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users && users.length > 0 ? (
              users.map((user, index) => (
                <tr key={user.user_id} className="border-b border-gray-700 hover:bg-gray-750">
                  <td className="py-3 px-2 text-gray-400 text-sm">{page.offset + index + 1}</td>
                  <td className="py-3 px-2">
                    <div className="text-white font-medium text-sm">{user.email}</div>
                    <div className="text-gray-400 text-xs">{user.display_name}</div>
                  </td>
                  <td className="py-3 px-2 text-white text-sm">{user.room_count}</td>
                  <td className="py-3 px-2">
                    <div className="text-white text-sm font-medium">{formatCurrency(user.stt_cost_usd)}</div>
                    <div className="text-gray-500 text-xs">{user.stt_minutes.toFixed(0)} min</div>
                  </td>
                  <td className="py-3 px-2">
                    <div className="text-white text-sm font-medium">{formatCurrency(user.mt_cost_usd)}</div>
                    {user.mt_tokens && (
                      <div className="text-gray-500 text-xs">{formatNumber(user.mt_tokens)} tok</div>
                    )}
                    {user.mt_characters && (
                      <div className="text-gray-500 text-xs">{formatNumber(user.mt_characters)} char</div>
                    )}
                  </td>
                  <td className="py-3 px-2 text-white text-sm font-semibold">
                    {formatCurrency(user.total_cost_usd)}
                  </td>
                  <td className="py-3 px-2 text-right">
                    <button
                      onClick={() => onViewDetail && onViewDetail(user)}
                      className="px-3 py-1 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700 transition-colors"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))
            ) : (
              <tr>
                <td colSpan="7" className="py-8 text-center text-gray-400">
                  No users found
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalUsers > 0 && (
        <div className="mt-4 flex items-center justify-between text-sm">
          <div className="text-gray-400">
            Showing {page.offset + 1} - {Math.min(page.offset + page.limit, totalUsers)} of {totalUsers} users
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
              Page {Math.floor(page.offset / page.limit) + 1} of {Math.ceil(totalUsers / page.limit)}
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
