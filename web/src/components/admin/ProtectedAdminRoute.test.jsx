import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import ProtectedAdminRoute from './ProtectedAdminRoute';
import * as adminApi from '../../utils/adminApi';

// Mock adminApi
vi.mock('../../utils/adminApi', () => ({
  isAdmin: vi.fn(),
  testAdminAccess: vi.fn(),
}));

// Mock react-router-dom Navigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    Navigate: ({ to }) => <div data-testid="navigate">{`Navigating to ${to}`}</div>,
  };
});

describe('ProtectedAdminRoute', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const createAdminToken = () => {
    const payload = { sub: '1', is_admin: true, exp: 9999999999 };
    return `header.${btoa(JSON.stringify(payload))}.signature`;
  };

  const createNonAdminToken = () => {
    const payload = { sub: '2', is_admin: false, exp: 9999999999 };
    return `header.${btoa(JSON.stringify(payload))}.signature`;
  };

  it('should show loading state initially', () => {
    adminApi.isAdmin.mockReturnValue(true);
    adminApi.testAdminAccess.mockResolvedValue({ message: 'OK' });

    const token = createAdminToken();

    render(
      <BrowserRouter>
        <ProtectedAdminRoute token={token}>
          <div>Admin Content</div>
        </ProtectedAdminRoute>
      </BrowserRouter>
    );

    expect(screen.getByText(/verifying access/i)).toBeInTheDocument();
  });

  it('should render children for valid admin token', async () => {
    adminApi.isAdmin.mockReturnValue(true);
    adminApi.testAdminAccess.mockResolvedValue({ message: 'OK' });

    const token = createAdminToken();

    render(
      <BrowserRouter>
        <ProtectedAdminRoute token={token}>
          <div>Admin Content</div>
        </ProtectedAdminRoute>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Admin Content')).toBeInTheDocument();
    });
  });

  it('should redirect to /rooms for non-admin user', async () => {
    adminApi.isAdmin.mockReturnValue(false);

    const token = createNonAdminToken();
    const onUnauthorized = vi.fn();

    render(
      <BrowserRouter>
        <ProtectedAdminRoute token={token} onUnauthorized={onUnauthorized}>
          <div>Admin Content</div>
        </ProtectedAdminRoute>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('navigate')).toBeInTheDocument();
      expect(screen.getByText(/navigating to \/rooms/i)).toBeInTheDocument();
    });

    expect(onUnauthorized).toHaveBeenCalledWith(
      expect.stringContaining('Admin access required')
    );
  });

  it('should redirect to /rooms when no token provided', async () => {
    render(
      <BrowserRouter>
        <ProtectedAdminRoute token="">
          <div>Admin Content</div>
        </ProtectedAdminRoute>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('navigate')).toBeInTheDocument();
    });
  });

  it('should redirect when backend verification fails', async () => {
    adminApi.isAdmin.mockReturnValue(true);
    adminApi.testAdminAccess.mockRejectedValue(new Error('Backend error'));

    const token = createAdminToken();
    const onUnauthorized = vi.fn();

    render(
      <BrowserRouter>
        <ProtectedAdminRoute token={token} onUnauthorized={onUnauthorized}>
          <div>Admin Content</div>
        </ProtectedAdminRoute>
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByTestId('navigate')).toBeInTheDocument();
    });

    expect(onUnauthorized).toHaveBeenCalled();
  });
});
