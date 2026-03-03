import React, { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';
import AdminLayout from '../components/admin/AdminLayout';
import UserProfileModal from '../components/admin/UserProfileModal';
import { searchUsers } from '../utils/adminApi';

/**
 * AdminUsersPage - US-009: Search and View User Details
 *
 * Allows admins to search for users by email or ID and view their details.
 */
export default function AdminUsersPage({ token, onLogout }) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState('');
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedUser, setSelectedUser] = useState(null);
  const [debouncedQuery, setDebouncedQuery] = useState('');

  // Debounce search query (500ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(searchQuery);
    }, 500);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Perform search when debounced query changes (and is not empty)
  useEffect(() => {
    if (debouncedQuery.trim().length > 0) {
      performSearch(debouncedQuery);
    }
  }, [debouncedQuery]);

  const performSearch = async (query) => {
    if (!query || query.trim().length === 0) {
      setResults([]);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await searchUsers(token, query);
      setResults(data.results || []);
    } catch (err) {
      console.error('[AdminUsersPage] Search error:', err);
      setError(t('admin.users.error'));
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const handleSearchClick = () => {
    performSearch(searchQuery);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      performSearch(searchQuery);
    }
  };

  const handleClear = () => {
    setSearchQuery('');
    setResults([]);
    setError(null);
  };

  const handleViewDetails = (user) => {
    setSelectedUser(user);
  };

  const handleCloseModal = () => {
    setSelectedUser(null);
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
      });
    } catch (e) {
      return isoString;
    }
  };

  return (
    <AdminLayout onLogout={onLogout}>
      <div className="max-w-7xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">{t('admin.users.title')}</h1>

        {/* Search Box */}
        <div className="bg-card border border-border rounded-lg p-6 mb-6">
          <div className="flex gap-4">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={t('admin.users.searchPlaceholder')}
              className="flex-1 px-4 py-2 bg-secondary border border-border rounded focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button
              onClick={handleSearchClick}
              disabled={loading}
              className="px-6 py-2 bg-primary text-primary-foreground rounded hover:bg-opacity-90 transition disabled:opacity-50"
            >
              {loading ? t('admin.users.loading') : t('admin.users.search')}
            </button>
            <button
              onClick={handleClear}
              disabled={loading}
              className="px-6 py-2 bg-secondary text-foreground rounded hover:bg-opacity-80 transition disabled:opacity-50"
            >
              {t('admin.users.clear')}
            </button>
          </div>
        </div>

        {/* Error Message */}
        {error && (
          <div className="bg-red-900 bg-opacity-20 border border-red-600 text-red-400 rounded-lg p-4 mb-6">
            {error}
          </div>
        )}

        {/* Results Table */}
        {results.length > 0 ? (
          <div className="bg-card border border-border rounded-lg overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-secondary">
                  <tr>
                    <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.users.userId')}</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.users.email')}</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.users.displayName')}</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.users.signupDate')}</th>
                    <th className="px-6 py-3 text-left text-sm font-semibold">{t('admin.users.actions')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {results.map((user) => (
                    <tr key={user.user_id} className="hover:bg-secondary hover:bg-opacity-50 transition">
                      <td className="px-6 py-4 text-sm">{user.user_id}</td>
                      <td className="px-6 py-4 text-sm">{user.email}</td>
                      <td className="px-6 py-4 text-sm">{user.display_name || 'N/A'}</td>
                      <td className="px-6 py-4 text-sm">{formatDate(user.signup_date)}</td>
                      <td className="px-6 py-4 text-sm">
                        <button
                          onClick={() => handleViewDetails(user)}
                          className="text-primary hover:underline"
                        >
                          {t('admin.users.viewDetails')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : !loading && searchQuery.trim().length > 0 && !error ? (
          <div className="bg-card border border-border rounded-lg p-12 text-center">
            <div className="text-6xl mb-4">🔍</div>
            <p className="text-lg text-muted">{t('admin.users.noResults')}</p>
          </div>
        ) : null}

        {/* User Detail Modal */}
        {selectedUser && (
          <UserProfileModal
            user={selectedUser}
            onClose={handleCloseModal}
          />
        )}
      </div>
    </AdminLayout>
  );
}

AdminUsersPage.propTypes = {
  token: PropTypes.string.isRequired,
  onLogout: PropTypes.func.isRequired,
};
