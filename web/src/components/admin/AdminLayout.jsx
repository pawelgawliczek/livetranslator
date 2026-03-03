import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import PropTypes from 'prop-types';
import { useTranslation } from 'react-i18next';

/**
 * AdminLayout - US-014: Admin Navigation Menu
 *
 * Provides:
 * - Sidebar navigation with menu items
 * - Active page highlighting
 * - Breadcrumb navigation
 * - Responsive design (collapses on mobile)
 * - Only visible to admin users
 */
export default function AdminLayout({ children, onLogout }) {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const menuItems = [
    {
      id: 'overview',
      label: t('admin.menu.overview') || 'Overview',
      path: '/admin/overview',
      icon: '📊',
    },
    {
      id: 'cost-analytics',
      label: t('admin.menu.costAnalytics') || 'Cost Analytics',
      path: '/admin/cost-analytics',
      icon: '💸',
    },
    {
      id: 'users',
      label: t('admin.menu.users') || 'Users',
      path: '/admin/users',
      icon: '👥',
    },
    {
      id: 'metrics',
      label: t('admin.menu.metrics') || 'Metrics',
      path: '/admin/metrics',
      icon: '📈',
    },
    {
      id: 'system',
      label: t('admin.menu.system') || 'System',
      path: '/admin/system',
      icon: '⚙️',
    },
    {
      id: 'tools',
      label: t('admin.menu.tools') || 'Tools',
      path: '/admin/tools',
      icon: '🔧',
    },
    {
      id: 'notifications',
      label: t('admin.menu.notifications') || 'Notifications',
      path: '/admin/notifications',
      icon: '🔔',
    },
  ];

  // Get current breadcrumb
  const getBreadcrumb = () => {
    const currentItem = menuItems.find(item => location.pathname.startsWith(item.path));
    if (currentItem) {
      return [
        { label: t('admin.menu.admin') || 'Admin', path: '/admin/overview' },
        { label: currentItem.label, path: currentItem.path },
      ];
    }
    return [{ label: t('admin.menu.admin') || 'Admin', path: '/admin/overview' }];
  };

  const breadcrumb = getBreadcrumb();

  return (
    <div className="min-h-screen bg-bg text-fg flex">
      {/* Sidebar */}
      <aside
        className={`${
          sidebarOpen ? 'w-64' : 'w-16'
        } bg-card border-r border-border transition-all duration-300 flex flex-col`}
      >
        {/* Logo / Header */}
        <div className="p-4 border-b border-border flex items-center justify-between">
          {sidebarOpen && (
            <div>
              <h1 className="text-xl font-bold text-fg">Admin Panel</h1>
              <p className="text-xs text-muted">LiveTranslator</p>
            </div>
          )}
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="p-2 hover:bg-bg-secondary rounded transition-colors text-fg"
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? '◀' : '▶'}
          </button>
        </div>

        {/* Navigation Menu */}
        <nav className="flex-1 p-4 space-y-2">
          {menuItems.map((item) => {
            const isActive = location.pathname.startsWith(item.path);
            return (
              <Link
                key={item.id}
                to={item.path}
                className={`flex items-center gap-3 px-3 py-2 rounded transition-colors ${
                  isActive
                    ? 'bg-accent text-accent-fg font-semibold'
                    : 'text-muted hover:bg-bg-secondary hover:text-fg'
                }`}
              >
                <span className="text-xl">{item.icon}</span>
                {sidebarOpen && <span>{item.label}</span>}
              </Link>
            );
          })}
        </nav>

        {/* Footer Actions */}
        <div className="p-4 border-t border-border space-y-2">
          <button
            onClick={() => navigate('/rooms')}
            className={`flex items-center gap-3 px-3 py-2 rounded transition-colors w-full text-left text-muted hover:bg-bg-secondary hover:text-fg`}
          >
            <span className="text-xl">🏠</span>
            {sidebarOpen && <span>{t('common.back_to_rooms') || 'Back to Rooms'}</span>}
          </button>
          <button
            onClick={onLogout}
            className={`flex items-center gap-3 px-3 py-2 rounded transition-colors w-full text-left text-muted hover:bg-red-600 hover:text-white`}
          >
            <span className="text-xl">🚪</span>
            {sidebarOpen && <span>{t('common.logout') || 'Logout'}</span>}
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Bar with Breadcrumb */}
        <header className="bg-card border-b border-border p-4">
          <nav className="flex items-center gap-2 text-sm">
            {breadcrumb.map((crumb, index) => (
              <React.Fragment key={index}>
                {index > 0 && <span className="text-muted">/</span>}
                {index === breadcrumb.length - 1 ? (
                  <span className="text-fg font-semibold">{crumb.label}</span>
                ) : (
                  <Link to={crumb.path} className="text-accent hover:underline">
                    {crumb.label}
                  </Link>
                )}
              </React.Fragment>
            ))}
          </nav>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-8">
          {children}
        </main>
      </div>
    </div>
  );
}

AdminLayout.propTypes = {
  children: PropTypes.node.isRequired,
  onLogout: PropTypes.func.isRequired,
};
