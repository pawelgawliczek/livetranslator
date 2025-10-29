import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCostOverview, getUserCosts, getRoomCosts, getDatePresets, exportToCSV } from '../utils/costAnalytics';
import DateRangePicker from '../components/admin/DateRangePicker';
import CostOverviewCards from '../components/admin/CostOverviewCards';
import CostTrendChart from '../components/admin/CostTrendChart';
import ProviderBreakdownChart from '../components/admin/ProviderBreakdownChart';
import UserCostTable from '../components/admin/UserCostTable';
import RoomCostTable from '../components/admin/RoomCostTable';
import UserDetailModal from '../components/admin/UserDetailModal';

export default function AdminCostAnalyticsPage({ token, onLogout }) {
  const navigate = useNavigate();

  // Date range state
  const presets = getDatePresets();
  const [startDate, setStartDate] = useState(presets.last7days.start);
  const [endDate, setEndDate] = useState(presets.last7days.end);

  // Overview data
  const [overview, setOverview] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);

  // Users data
  const [users, setUsers] = useState([]);
  const [usersPage, setUsersPage] = useState({ limit: 50, offset: 0, has_more: false });
  const [totalUsers, setTotalUsers] = useState(0);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersSortBy, setUsersSortBy] = useState('total_cost');
  const [usersSortOrder, setUsersSortOrder] = useState('desc');
  const [usersSearch, setUsersSearch] = useState('');

  // Rooms data
  const [rooms, setRooms] = useState([]);
  const [roomsPage, setRoomsPage] = useState({ limit: 50, offset: 0, has_more: false });
  const [totalRooms, setTotalRooms] = useState(0);
  const [roomsLoading, setRoomsLoading] = useState(true);
  const [roomsSortBy, setRoomsSortBy] = useState('total_cost');
  const [roomsSortOrder, setRoomsSortOrder] = useState('desc');
  const [roomsSearch, setRoomsSearch] = useState('');

  // User detail modal
  const [selectedUser, setSelectedUser] = useState(null);

  // Fetch overview when date range changes
  useEffect(() => {
    if (!token || !startDate || !endDate) return;

    const fetchOverview = async () => {
      setOverviewLoading(true);

      try {
        const data = await getCostOverview(token, startDate, endDate);
        setOverview(data);
      } catch (err) {
        console.error('Error fetching overview:', err);
        if (err.message.includes('403') || err.message.includes('401')) {
          onLogout && onLogout();
          navigate('/login');
        }
      } finally {
        setOverviewLoading(false);
      }
    };

    fetchOverview();
  }, [token, startDate, endDate, navigate, onLogout]);

  // Fetch users when date range or pagination/sort changes
  useEffect(() => {
    if (!token || !startDate || !endDate) return;

    const fetchUsers = async () => {
      setUsersLoading(true);

      try {
        const data = await getUserCosts(token, {
          startDate,
          endDate,
          limit: usersPage.limit,
          offset: usersPage.offset,
          sortBy: usersSortBy,
          sortOrder: usersSortOrder,
          search: usersSearch || null,
        });

        setUsers(data.users || []);
        setUsersPage(data.page);
        setTotalUsers(data.total_users);
      } catch (err) {
        console.error('Error fetching users:', err);
      } finally {
        setUsersLoading(false);
      }
    };

    fetchUsers();
  }, [token, startDate, endDate, usersPage.limit, usersPage.offset, usersSortBy, usersSortOrder, usersSearch]);

  // Fetch rooms when date range or pagination/sort changes
  useEffect(() => {
    if (!token || !startDate || !endDate) return;

    const fetchRooms = async () => {
      setRoomsLoading(true);

      try {
        const data = await getRoomCosts(token, {
          startDate,
          endDate,
          limit: roomsPage.limit,
          offset: roomsPage.offset,
          sortBy: roomsSortBy,
          sortOrder: roomsSortOrder,
          search: roomsSearch || null,
        });

        setRooms(data.rooms || []);
        setRoomsPage(data.page);
        setTotalRooms(data.total_rooms);
      } catch (err) {
        console.error('Error fetching rooms:', err);
      } finally {
        setRoomsLoading(false);
      }
    };

    fetchRooms();
  }, [token, startDate, endDate, roomsPage.limit, roomsPage.offset, roomsSortBy, roomsSortOrder, roomsSearch]);

  // Handlers
  const handleDateChange = (newStart, newEnd) => {
    setStartDate(newStart);
    setEndDate(newEnd);
    // Reset pagination when date changes
    setUsersPage((prev) => ({ ...prev, offset: 0 }));
    setRoomsPage((prev) => ({ ...prev, offset: 0 }));
  };

  const handleUsersPageChange = (newOffset) => {
    setUsersPage((prev) => ({ ...prev, offset: newOffset }));
  };

  const handleUsersSort = (sortBy, sortOrder) => {
    setUsersSortBy(sortBy);
    setUsersSortOrder(sortOrder);
    setUsersPage((prev) => ({ ...prev, offset: 0 })); // Reset to first page
  };

  const handleUsersSearch = (search) => {
    setUsersSearch(search);
    setUsersPage((prev) => ({ ...prev, offset: 0 })); // Reset to first page
  };

  const handleRoomsPageChange = (newOffset) => {
    setRoomsPage((prev) => ({ ...prev, offset: newOffset }));
  };

  const handleRoomsSort = (sortBy, sortOrder) => {
    setRoomsSortBy(sortBy);
    setRoomsSortOrder(sortOrder);
    setRoomsPage((prev) => ({ ...prev, offset: 0 })); // Reset to first page
  };

  const handleRoomsSearch = (search) => {
    setRoomsSearch(search);
    setRoomsPage((prev) => ({ ...prev, offset: 0 })); // Reset to first page
  };

  const handleViewUserDetail = (user) => {
    setSelectedUser(user);
  };

  const handleExportUsers = () => {
    if (users.length === 0) return;

    const exportData = users.map((user) => ({
      email: user.email,
      display_name: user.display_name,
      room_count: user.room_count,
      stt_cost_usd: user.stt_cost_usd,
      stt_minutes: user.stt_minutes,
      mt_cost_usd: user.mt_cost_usd,
      total_cost_usd: user.total_cost_usd,
      top_stt_provider: user.top_stt_provider,
      top_mt_provider: user.top_mt_provider,
    }));

    exportToCSV(exportData, `user-costs-${startDate.toISOString().split('T')[0]}.csv`);
  };

  const handleExportRooms = () => {
    if (rooms.length === 0) return;

    const exportData = rooms.map((room) => ({
      room_code: room.room_code,
      owner_email: room.owner.email,
      owner_name: room.owner.display_name,
      is_public: room.is_public ? 'Public' : 'Private',
      created_at: room.created_at,
      stt_cost_usd: room.stt_cost_usd,
      stt_minutes: room.stt_minutes,
      mt_cost_usd: room.mt_cost_usd,
      total_cost_usd: room.total_cost_usd,
    }));

    exportToCSV(exportData, `room-costs-${startDate.toISOString().split('T')[0]}.csv`);
  };

  if (!token) {
    navigate('/login');
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <div className="bg-gray-800 border-b border-gray-700 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/admin')}
            className="text-gray-400 hover:text-white transition-colors"
          >
            ← Back to Admin
          </button>
          <h1 className="text-2xl font-bold">Cost Analytics</h1>
        </div>
        <button
          onClick={onLogout}
          className="px-4 py-2 bg-red-600 hover:bg-red-700 rounded-lg font-medium transition-colors"
        >
          Logout
        </button>
      </div>

      {/* Main Content */}
      <div className="container mx-auto px-6 py-8 space-y-6 max-w-7xl">
        {/* Date Range Picker */}
        <DateRangePicker startDate={startDate} endDate={endDate} onChange={handleDateChange} />

        {/* Overview Cards */}
        <CostOverviewCards overview={overview} loading={overviewLoading} />

        {/* Cost Trend Chart */}
        <CostTrendChart token={token} startDate={startDate} endDate={endDate} />

        {/* Provider Breakdown Charts */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <ProviderBreakdownChart
            title="🔌 STT Provider Breakdown"
            breakdown={overview?.stt_breakdown}
            type="stt"
            loading={overviewLoading}
          />
          <ProviderBreakdownChart
            title="🌍 MT Provider Breakdown"
            breakdown={overview?.mt_breakdown}
            type="mt"
            loading={overviewLoading}
          />
        </div>

        {/* Users Table */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xl font-semibold"></h3>
            <button
              onClick={handleExportUsers}
              disabled={users.length === 0}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
            >
              Export Users to CSV
            </button>
          </div>
          <UserCostTable
            users={users}
            page={usersPage}
            totalUsers={totalUsers}
            onPageChange={handleUsersPageChange}
            onSort={handleUsersSort}
            onSearch={handleUsersSearch}
            onViewDetail={handleViewUserDetail}
            loading={usersLoading}
          />
        </div>

        {/* Rooms Table */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-xl font-semibold"></h3>
            <button
              onClick={handleExportRooms}
              disabled={rooms.length === 0}
              className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
            >
              Export Rooms to CSV
            </button>
          </div>
          <RoomCostTable
            rooms={rooms}
            page={roomsPage}
            totalRooms={totalRooms}
            onPageChange={handleRoomsPageChange}
            onSort={handleRoomsSort}
            onSearch={handleRoomsSearch}
            loading={roomsLoading}
          />
        </div>
      </div>

      {/* User Detail Modal */}
      {selectedUser && (
        <UserDetailModal
          token={token}
          userId={selectedUser.user_id}
          startDate={startDate}
          endDate={endDate}
          onClose={() => setSelectedUser(null)}
        />
      )}
    </div>
  );
}
