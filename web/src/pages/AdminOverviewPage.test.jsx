import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AdminOverviewPage from './AdminOverviewPage';

// Create mock functions
const mockGetUserEngagement = vi.fn();
const mockGetSystemPerformance = vi.fn();

// Mock the admin API module
vi.mock('../utils/adminApi', () => ({
  getUserEngagement: (...args) => mockGetUserEngagement(...args),
  getSystemPerformance: (...args) => mockGetSystemPerformance(...args),
}));

// Mock DateRangePicker
vi.mock('../components/admin/DateRangePicker', () => ({
  default: ({ startDate, endDate, onChange }) => (
    <div data-testid="date-range-picker">
      DateRangePicker: {startDate?.toISOString()} - {endDate?.toISOString()}
    </div>
  ),
}));

// Mock AdminLayout
vi.mock('../components/admin/AdminLayout', () => ({
  default: ({ children, onLogout }) => (
    <div data-testid="admin-layout">
      <button onClick={onLogout}>Logout</button>
      {children}
    </div>
  ),
}));

// Mock i18next
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

describe('AdminOverviewPage', () => {
  const mockToken = 'test-admin-token';
  const mockOnLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const mockEngagementData = {
    metrics: [
      { metric_date: '2025-11-04', dau: 250, paying_users: 50, free_users: 200 },
    ],
  };

  const mockPerformanceData = {
    providers: [
      {
        service: 'stt',
        provider: 'openai',
        request_count: 1500,
        avg_cost_per_request: 0.006,
        total_cost: 9.0,
      },
      {
        service: 'mt',
        provider: 'openai',
        request_count: 3000,
        avg_cost_per_request: 0.001,
        total_cost: 3.0,
      },
    ],
  };

  it('should render metric cards', async () => {
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('admin.overview.activeUsers')).toBeInTheDocument();
    });

    expect(screen.getByText('admin.overview.activeUsers')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.roomsCreated')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.providerHealth')).toBeInTheDocument();
  });

  it('should fetch data on mount', async () => {
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(mockGetUserEngagement).toHaveBeenCalledWith(
        mockToken,
        expect.any(Date),
        expect.any(Date)
      );
      expect(mockGetSystemPerformance).toHaveBeenCalledWith(
        mockToken,
        expect.any(Date),
        expect.any(Date)
      );
    });
  });

  it('should show error message on fetch failure', async () => {
    mockGetUserEngagement.mockRejectedValue(new Error('API Error'));
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/API Error/)).toBeInTheDocument();
    });
  });

  it('should render quick links to other pages', async () => {
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Cost Analytics')).toBeInTheDocument();
    });

    expect(screen.getByText('admin.overview.viewUsers')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.viewSystem')).toBeInTheDocument();
  });

  it('should show provider health status', async () => {
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });
  });

  it('should handle empty engagement data (zero DAU)', async () => {
    mockGetUserEngagement.mockResolvedValue({ metrics: [] });
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('admin.overview.activeUsers')).toBeInTheDocument();
    });
  });
});
