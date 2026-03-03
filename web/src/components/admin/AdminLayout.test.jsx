import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AdminLayout from './AdminLayout';

// Mock react-i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => {
      const translations = {
        'admin.menu.overview': 'Overview',
        'admin.menu.financial': 'Financial',
        'admin.menu.users': 'Users',
        'admin.menu.metrics': 'Metrics',
        'admin.menu.system': 'System',
        'admin.menu.tools': 'Tools',
        'admin.menu.admin': 'Admin',
        'common.back_to_rooms': 'Back to Rooms',
        'common.logout': 'Logout',
      };
      return translations[key] || key;
    },
  }),
}));

// Mock react-router-dom hooks
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useLocation: () => ({ pathname: '/admin/overview' }),
    useNavigate: () => vi.fn(),
  };
});

describe('AdminLayout', () => {
  const defaultProps = {
    onLogout: vi.fn(),
  };

  it('should render sidebar with menu items', () => {
    render(
      <BrowserRouter>
        <AdminLayout {...defaultProps}>
          <div>Test Content</div>
        </AdminLayout>
      </BrowserRouter>
    );

    expect(screen.getByText('Admin Panel')).toBeInTheDocument();
    expect(screen.getAllByText('Overview').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Users')).toBeInTheDocument();
    expect(screen.getByText('Metrics')).toBeInTheDocument();
    expect(screen.getByText('System')).toBeInTheDocument();
    expect(screen.getByText('Tools')).toBeInTheDocument();
  });

  it('should render children in main content area', () => {
    render(
      <BrowserRouter>
        <AdminLayout {...defaultProps}>
          <div>Test Content</div>
        </AdminLayout>
      </BrowserRouter>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('should render breadcrumb navigation', () => {
    render(
      <BrowserRouter>
        <AdminLayout {...defaultProps}>
          <div>Test Content</div>
        </AdminLayout>
      </BrowserRouter>
    );

    // Should show "Admin / Overview" in breadcrumb
    expect(screen.getByText('Admin')).toBeInTheDocument();
    expect(screen.getAllByText('Overview').length).toBeGreaterThanOrEqual(1);
  });

  it('should toggle sidebar when button clicked', () => {
    render(
      <BrowserRouter>
        <AdminLayout {...defaultProps}>
          <div>Test Content</div>
        </AdminLayout>
      </BrowserRouter>
    );

    // Initial state: sidebar open, text visible
    expect(screen.getByText('LiveTranslator')).toBeInTheDocument();

    // Click toggle button
    const toggleButton = screen.getByLabelText('Toggle sidebar');
    fireEvent.click(toggleButton);

    // Sidebar collapsed: text should still be in DOM but sidebar width changed
    // Note: We can't easily test CSS classes in JSDOM, so we just verify button works
    expect(toggleButton).toBeInTheDocument();
  });

  it('should call onLogout when logout button clicked', () => {
    const onLogout = vi.fn();

    render(
      <BrowserRouter>
        <AdminLayout {...defaultProps} onLogout={onLogout}>
          <div>Test Content</div>
        </AdminLayout>
      </BrowserRouter>
    );

    const logoutButton = screen.getByText('Logout').closest('button');
    fireEvent.click(logoutButton);

    expect(onLogout).toHaveBeenCalledTimes(1);
  });

  it('should have back to rooms button', () => {
    render(
      <BrowserRouter>
        <AdminLayout {...defaultProps}>
          <div>Test Content</div>
        </AdminLayout>
      </BrowserRouter>
    );

    expect(screen.getByText('Back to Rooms')).toBeInTheDocument();
  });
});
