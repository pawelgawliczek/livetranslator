import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import {
  searchRoomByCode,
  getRoomMessages,
  searchUsers,
  getRedisKeys,
  getRedisValue,
  clearCache,
  getCacheStats,
  getMessageDebug
} from '../utils/adminApi';

/**
 * AdminToolsPage - US-007: Support Tools Page
 *
 * Provides troubleshooting tools:
 * - Room Lookup (search by code/ID, view details + messages)
 * - User Lookup (search by email/ID, view profile + quota)
 * - Debug Tools (Redis inspector, error log viewer)
 * - Cache Management (clear room cache, STT cache)
 */
export default function AdminToolsPage({ token, onLogout }) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState('room-lookup');

  // Room Lookup State
  const [roomQuery, setRoomQuery] = useState('');
  const [roomDetails, setRoomDetails] = useState(null);
  const [roomMessages, setRoomMessages] = useState([]);
  const [selectedMessage, setSelectedMessage] = useState(null);
  const [messageDebugData, setMessageDebugData] = useState(null);

  // User Lookup State
  const [userQuery, setUserQuery] = useState('');
  const [userResults, setUserResults] = useState([]);

  // Redis Inspector State
  const [redisPattern, setRedisPattern] = useState('room:*');
  const [redisKeys, setRedisKeys] = useState([]);
  const [selectedKey, setSelectedKey] = useState(null);
  const [keyValue, setKeyValue] = useState(null);

  // Cache Management State
  const [cacheStats, setCacheStats] = useState(null);
  const [clearRoomCode, setClearRoomCode] = useState('');

  // UI State
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Room Lookup Handlers
  const handleRoomSearch = async () => {
    if (!roomQuery.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const room = await searchRoomByCode(token, roomQuery.trim());
      setRoomDetails(room);

      // Fetch messages
      const messages = await getRoomMessages(token, room.room_code, 20, 0);
      setRoomMessages(messages.messages || []);
    } catch (err) {
      setError(err.message);
      setRoomDetails(null);
      setRoomMessages([]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewDebug = async (segmentId) => {
    if (!roomDetails) return;

    setLoading(true);
    try {
      const debug = await getMessageDebug(token, roomDetails.room_code, segmentId);
      setMessageDebugData(debug);
      setSelectedMessage(segmentId);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // User Lookup Handlers
  const handleUserSearch = async () => {
    if (!userQuery.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const results = await searchUsers(token, userQuery.trim());
      setUserResults(results.results || []);
    } catch (err) {
      setError(err.message);
      setUserResults([]);
    } finally {
      setLoading(false);
    }
  };

  // Redis Inspector Handlers
  const handleRedisSearch = async () => {
    if (!redisPattern.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const results = await getRedisKeys(token, redisPattern.trim(), 50);
      setRedisKeys(results.keys || []);
    } catch (err) {
      setError(err.message);
      setRedisKeys([]);
    } finally {
      setLoading(false);
    }
  };

  const handleViewKeyValue = async (key) => {
    setLoading(true);
    try {
      const value = await getRedisValue(token, key);
      setKeyValue(value);
      setSelectedKey(key);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Cache Management Handlers
  const loadCacheStats = async () => {
    try {
      const stats = await getCacheStats(token);
      setCacheStats(stats);
    } catch (err) {
      setError(err.message);
    }
  };

  const handleClearCache = async (cacheType, roomCode = null) => {
    if (!window.confirm(`Are you sure you want to clear ${cacheType}?`)) {
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const result = await clearCache(token, cacheType, roomCode);
      alert(`Cache cleared: ${result.keys_deleted} keys deleted`);
      await loadCacheStats();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Load cache stats when tab changes to cache
  React.useEffect(() => {
    if (activeTab === 'cache' && !cacheStats) {
      loadCacheStats();
    }
  }, [activeTab]);

  // Copy to clipboard helper
  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    // Could add toast notification here
  };

  // Tab rendering
  const renderRoomLookup = () => (
    <div>
      <h2 className="text-2xl font-bold mb-4">Room Lookup</h2>

      {/* Search Bar */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          className="flex-1 px-4 py-2 border border-border rounded bg-bg text-fg"
          placeholder="Enter room code (e.g., ABCD1234) or room ID"
          value={roomQuery}
          onChange={(e) => setRoomQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleRoomSearch()}
        />
        <button
          onClick={handleRoomSearch}
          disabled={loading}
          className="px-6 py-2 bg-accent text-accent-fg rounded hover:bg-accent/80 disabled:opacity-50"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
        <button
          onClick={() => {
            setRoomQuery('');
            setRoomDetails(null);
            setRoomMessages([]);
            setError(null);
          }}
          className="px-4 py-2 border border-border rounded hover:bg-bg-secondary text-fg"
        >
          Clear
        </button>
      </div>

      {error && (
        <div className="bg-red-600/10 border border-red-600 rounded p-4 mb-4 text-red-600">
          {error}
        </div>
      )}

      {/* Room Details Card */}
      {roomDetails && (
        <div className="bg-card border border-border rounded-lg p-6 mb-4">
          <div className="flex items-start justify-between mb-4">
            <h3 className="text-xl font-semibold">
              Room: {roomDetails.room_code}
              <button
                onClick={() => copyToClipboard(roomDetails.room_code)}
                className="ml-2 text-accent hover:underline text-sm"
                title="Copy to clipboard"
              >
                📋
              </button>
            </h3>
            <span className={`px-3 py-1 rounded text-sm font-semibold ${
              roomDetails.status === 'active' ? 'bg-green-600 text-white' : 'bg-gray-500 text-white'
            }`}>
              {roomDetails.status}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <label className="text-muted">Room ID</label>
              <p className="font-mono">{roomDetails.room_id}</p>
            </div>
            <div>
              <label className="text-muted">Owner</label>
              <p>{roomDetails.owner_email}</p>
            </div>
            <div>
              <label className="text-muted">Created</label>
              <p>{new Date(roomDetails.created_at).toLocaleString()}</p>
            </div>
            <div>
              <label className="text-muted">Multi-speaker</label>
              <p>{roomDetails.is_multi_speaker ? 'Yes' : 'No'}</p>
            </div>
            <div>
              <label className="text-muted">Participants</label>
              <p>{roomDetails.participant_count} active, {roomDetails.total_participants} total</p>
            </div>
            <div>
              <label className="text-muted">Messages</label>
              <p>{roomDetails.message_count}</p>
            </div>
            <div className="col-span-2">
              <label className="text-muted">Total Cost</label>
              <p className="font-semibold">
                ${roomDetails.cost_summary.total_cost_usd.toFixed(4)}
                <span className="text-muted text-sm ml-2">
                  (STT: ${roomDetails.cost_summary.stt_cost_usd.toFixed(4)},
                   MT: ${roomDetails.cost_summary.mt_cost_usd.toFixed(4)})
                </span>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Recent Messages Table */}
      {roomMessages.length > 0 && (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="p-4 bg-bg-secondary font-semibold">Recent Messages (Last 20)</div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-bg-secondary">
                <tr>
                  <th className="p-3 text-left">Segment ID</th>
                  <th className="p-3 text-left">Time</th>
                  <th className="p-3 text-left">Speaker</th>
                  <th className="p-3 text-left">Text</th>
                  <th className="p-3 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {roomMessages.map(msg => (
                  <tr key={msg.segment_id} className="border-t border-border hover:bg-bg-secondary">
                    <td className="p-3 font-mono">{msg.segment_id}</td>
                    <td className="p-3 text-sm">{msg.timestamp ? new Date(msg.timestamp).toLocaleTimeString() : 'N/A'}</td>
                    <td className="p-3 text-sm">{msg.speaker_email}</td>
                    <td className="p-3 truncate max-w-xs">{msg.text}</td>
                    <td className="p-3 text-center">
                      <button
                        onClick={() => handleViewDebug(msg.segment_id)}
                        className="text-accent hover:underline"
                      >
                        Debug
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Message Debug Modal */}
      {selectedMessage && messageDebugData && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-card rounded-lg p-6 max-w-4xl w-full max-h-[80vh] overflow-auto">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-semibold">Debug Info: Segment {selectedMessage}</h3>
              <button
                onClick={() => {
                  setSelectedMessage(null);
                  setMessageDebugData(null);
                }}
                className="text-muted hover:text-fg text-2xl leading-none"
              >
                ×
              </button>
            </div>
            <pre className="bg-bg p-4 rounded text-sm overflow-auto">
              {JSON.stringify(messageDebugData, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );

  const renderUserLookup = () => (
    <div>
      <h2 className="text-2xl font-bold mb-4">User Lookup</h2>

      {/* Search Bar */}
      <div className="flex gap-2 mb-4">
        <input
          type="text"
          className="flex-1 px-4 py-2 border border-border rounded bg-bg text-fg"
          placeholder="Enter email or user ID"
          value={userQuery}
          onChange={(e) => setUserQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleUserSearch()}
        />
        <button
          onClick={handleUserSearch}
          disabled={loading}
          className="px-6 py-2 bg-accent text-accent-fg rounded hover:bg-accent/80 disabled:opacity-50"
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
        <button
          onClick={() => {
            setUserQuery('');
            setUserResults([]);
            setError(null);
          }}
          className="px-4 py-2 border border-border rounded hover:bg-bg-secondary text-fg"
        >
          Clear
        </button>
      </div>

      {error && (
        <div className="bg-red-600/10 border border-red-600 rounded p-4 mb-4 text-red-600">
          {error}
        </div>
      )}

      {/* User Results */}
      {userResults.length > 0 && (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="p-4 bg-bg-secondary font-semibold">Search Results ({userResults.length})</div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-bg-secondary">
                <tr>
                  <th className="p-3 text-left">User ID</th>
                  <th className="p-3 text-left">Email</th>
                  <th className="p-3 text-left">Display Name</th>
                  <th className="p-3 text-left">Signup Date</th>
                </tr>
              </thead>
              <tbody>
                {userResults.map(user => (
                  <tr key={user.user_id} className="border-t border-border hover:bg-bg-secondary">
                    <td className="p-3 font-mono">{user.user_id}</td>
                    <td className="p-3">{user.email}</td>
                    <td className="p-3">{user.display_name || '-'}</td>
                    <td className="p-3 text-sm">{user.signup_date ? new Date(user.signup_date).toLocaleDateString() : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {userResults.length === 0 && userQuery && !loading && !error && (
        <div className="bg-card border border-border rounded-lg p-8 text-center text-muted">
          No users found matching &quot;{userQuery}&quot;
        </div>
      )}
    </div>
  );

  const renderDebugTools = () => (
    <div>
      <h2 className="text-2xl font-bold mb-4">Debug Tools</h2>

      {/* Redis Inspector */}
      <div className="mb-8">
        <h3 className="text-lg font-semibold mb-2">Redis Inspector</h3>
        <p className="text-sm text-muted mb-4">
          Allowed patterns: room:*, debug:*, stt_cache:*, mt_cache:*
        </p>

        <div className="flex gap-2 mb-4">
          <input
            type="text"
            className="flex-1 px-4 py-2 border border-border rounded bg-bg text-fg"
            placeholder="Pattern (e.g., room:*, debug:*)"
            value={redisPattern}
            onChange={(e) => setRedisPattern(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleRedisSearch()}
          />
          <button
            onClick={handleRedisSearch}
            disabled={loading}
            className="px-6 py-2 bg-accent text-accent-fg rounded hover:bg-accent/80 disabled:opacity-50"
          >
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {error && (
          <div className="bg-red-600/10 border border-red-600 rounded p-4 mb-4 text-red-600">
            {error}
          </div>
        )}

        {redisKeys.length > 0 && (
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-bg-secondary">
                  <tr>
                    <th className="p-3 text-left">Key</th>
                    <th className="p-3 text-left">Type</th>
                    <th className="p-3 text-center">TTL</th>
                    <th className="p-3 text-center">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {redisKeys.map(key => (
                    <tr key={key.key} className="border-t border-border hover:bg-bg-secondary">
                      <td className="p-3 font-mono text-sm">{key.key}</td>
                      <td className="p-3">{key.type}</td>
                      <td className="p-3 text-center">{key.ttl === -1 ? 'No TTL' : `${key.ttl}s`}</td>
                      <td className="p-3 text-center">
                        <button
                          onClick={() => handleViewKeyValue(key.key)}
                          className="text-accent hover:underline"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* Key Value Modal */}
      {keyValue && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-card rounded-lg p-6 max-w-2xl w-full max-h-96 overflow-auto">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-semibold">Key: {keyValue.key}</h3>
              <button
                onClick={() => {
                  setKeyValue(null);
                  setSelectedKey(null);
                }}
                className="text-muted hover:text-fg text-2xl leading-none"
              >
                ×
              </button>
            </div>
            <div className="text-sm text-muted mb-2">
              Type: {keyValue.type} | TTL: {keyValue.ttl === -1 ? 'No TTL' : `${keyValue.ttl}s`}
            </div>
            <pre className="bg-bg p-4 rounded text-sm overflow-auto">
              {JSON.stringify(keyValue.value, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );

  const renderCacheManagement = () => (
    <div>
      <h2 className="text-2xl font-bold mb-4">Cache Management</h2>

      {/* Cache Stats */}
      {cacheStats && (
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <h3 className="text-lg font-semibold mb-4">Cache Statistics</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-muted text-sm">Memory Used</label>
              <p className="text-2xl font-semibold">{cacheStats.redis_info.used_memory_human}</p>
            </div>
            <div>
              <label className="text-muted text-sm">Total Keys</label>
              <p className="text-2xl font-semibold">{cacheStats.redis_info.total_keys}</p>
            </div>
            <div>
              <label className="text-muted text-sm">STT Cache Keys</label>
              <p>{cacheStats.cache_breakdown.stt_cache}</p>
            </div>
            <div>
              <label className="text-muted text-sm">MT Cache Keys</label>
              <p>{cacheStats.cache_breakdown.mt_cache}</p>
            </div>
            <div>
              <label className="text-muted text-sm">Room Presence Keys</label>
              <p>{cacheStats.cache_breakdown.room_presence}</p>
            </div>
            <div>
              <label className="text-muted text-sm">Debug Keys</label>
              <p>{cacheStats.cache_breakdown.debug_keys}</p>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="bg-red-600/10 border border-red-600 rounded p-4 mb-4 text-red-600">
          {error}
        </div>
      )}

      {/* Clear Room Cache */}
      <div className="bg-card border border-border rounded-lg p-6 mb-4">
        <h3 className="text-lg font-semibold mb-2">Clear Room Cache</h3>
        <p className="text-muted text-sm mb-4">
          Delete all STT and MT cache entries for a specific room.
        </p>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Room code (e.g., ABCD1234)"
            value={clearRoomCode}
            onChange={(e) => setClearRoomCode(e.target.value.toUpperCase())}
            className="flex-1 px-4 py-2 border border-border rounded bg-bg text-fg"
          />
          <button
            onClick={() => handleClearCache('room_translations', clearRoomCode)}
            disabled={!clearRoomCode.trim() || loading}
            className="px-6 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:opacity-50"
          >
            Clear Room Cache
          </button>
        </div>
      </div>

      {/* Clear All STT Cache */}
      <div className="bg-card border border-border rounded-lg p-6 mb-4">
        <h3 className="text-lg font-semibold mb-2">Clear All STT Cache</h3>
        <p className="text-muted text-sm mb-4">
          ⚠️ Warning: This will delete all STT cache entries across all rooms.
        </p>
        <button
          onClick={() => handleClearCache('all_stt')}
          disabled={loading}
          className="px-6 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
        >
          Clear All STT Cache
        </button>
      </div>

      {/* Clear All MT Cache */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h3 className="text-lg font-semibold mb-2">Clear All MT Cache</h3>
        <p className="text-muted text-sm mb-4">
          ⚠️ Warning: This will delete all MT cache entries across all rooms.
        </p>
        <button
          onClick={() => handleClearCache('mt_cache')}
          disabled={loading}
          className="px-6 py-2 bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
        >
          Clear All MT Cache
        </button>
      </div>
    </div>
  );

  // Tab content router
  const renderTabContent = () => {
    switch (activeTab) {
      case 'room-lookup':
        return renderRoomLookup();
      case 'user-lookup':
        return renderUserLookup();
      case 'debug':
        return renderDebugTools();
      case 'cache':
        return renderCacheManagement();
      default:
        return null;
    }
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('admin.tools.title') || 'Support Tools'}</h1>

        {/* Tab Navigation */}
        <div className="flex gap-2 mb-6 border-b border-border">
          <button
            onClick={() => setActiveTab('room-lookup')}
            className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
              activeTab === 'room-lookup'
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-fg'
            }`}
          >
            Room Lookup
          </button>
          <button
            onClick={() => setActiveTab('user-lookup')}
            className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
              activeTab === 'user-lookup'
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-fg'
            }`}
          >
            User Lookup
          </button>
          <button
            onClick={() => setActiveTab('debug')}
            className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
              activeTab === 'debug'
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-fg'
            }`}
          >
            Debug Tools
          </button>
          <button
            onClick={() => setActiveTab('cache')}
            className={`px-4 py-2 font-semibold border-b-2 transition-colors ${
              activeTab === 'cache'
                ? 'border-accent text-accent'
                : 'border-transparent text-muted hover:text-fg'
            }`}
          >
            Cache
          </button>
        </div>

        {/* Tab Content */}
        {renderTabContent()}
      </div>
    </AdminLayout>
  );
}

AdminToolsPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
