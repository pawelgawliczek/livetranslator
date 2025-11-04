import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import AdminOverviewPage from './AdminOverviewPage';

// Create mock functions
const mockGetFinancialSummary = vi.fn();
const mockGetUserEngagement = vi.fn();
const mockGetSystemPerformance = vi.fn();

// Mock the admin API module
vi.mock('../utils/adminApi', () => ({
  getFinancialSummary: (...args) => mockGetFinancialSummary(...args),
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

  const mockFinancialData = {
    total_revenue_usd: 12450.50,
    total_cost_usd: 6225.25,
    gross_profit_usd: 6225.25,
    gross_margin_pct: 50.0,
  };

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

  it('should render 8 metric cards', async () => {
    mockGetFinancialSummary.mockResolvedValue(mockFinancialData);
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('admin.overview.totalRevenue')).toBeInTheDocument();
    });

    // Check all 8 metric cards are rendered
    expect(screen.getByText('admin.overview.totalRevenue')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.totalCosts')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.grossProfit')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.grossMargin')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.activeUsers')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.roomsCreated')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.avgCostPerUser')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.providerHealth')).toBeInTheDocument();
  });

  it('should fetch data on mount', async () => {
    mockGetFinancialSummary.mockResolvedValue(mockFinancialData);
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(mockGetFinancialSummary).toHaveBeenCalledWith(
        mockToken,
        expect.any(Date),
        expect.any(Date)
      );
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

  it('should show loading state while fetching', () => {
    mockGetFinancialSummary.mockImplementation(() => new Promise(() => {})); // Never resolves
    mockGetUserEngagement.mockImplementation(() => new Promise(() => {}));
    mockGetSystemPerformance.mockImplementation(() => new Promise(() => {}));

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    // Should show loading skeletons
    const loadingCards = screen.getAllByTestId('metric-card-loading');
    expect(loadingCards).toHaveLength(8);
  });

  it('should show error message on fetch failure', async () => {
    mockGetFinancialSummary.mockRejectedValue(new Error('API Error'));
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
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
    mockGetFinancialSummary.mockResolvedValue(mockFinancialData);
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      expect(screen.getByText('admin.overview.viewFinancial')).toBeInTheDocument();
    });

    expect(screen.getByText('admin.overview.viewFinancial')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.viewUsers')).toBeInTheDocument();
    expect(screen.getByText('admin.overview.viewSystem')).toBeInTheDocument();
  });

  it('should calculate avg cost per user correctly', async () => {
    mockGetFinancialSummary.mockResolvedValue(mockFinancialData);
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      // total_cost_usd (6225.25) / dau (250) = $24.90
      expect(screen.getByText('$24.90')).toBeInTheDocument();
    });
  });

  it('should show provider health status', async () => {
    mockGetFinancialSummary.mockResolvedValue(mockFinancialData);
    mockGetUserEngagement.mockResolvedValue(mockEngagementData);
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      // Should aggregate provider health (all healthy = "Healthy")
      expect(screen.getByText('Healthy')).toBeInTheDocument();
    });
  });

  it('should handle empty engagement data (zero DAU)', async () => {
    mockGetFinancialSummary.mockResolvedValue(mockFinancialData);
    mockGetUserEngagement.mockResolvedValue({ metrics: [] });
    mockGetSystemPerformance.mockResolvedValue(mockPerformanceData);

    render(
      <BrowserRouter>
        <AdminOverviewPage token={mockToken} onLogout={mockOnLogout} />
      </BrowserRouter>
    );

    await waitFor(() => {
      // Should show 0 for DAU and handle division by zero
      expect(screen.getByText('admin.overview.activeUsers')).toBeInTheDocument();
    });
  });
});
