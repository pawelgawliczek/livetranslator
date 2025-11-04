import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AdminFinancialPage from './AdminFinancialPage';
import * as adminApi from '../utils/adminApi';

// Mock modules
vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (key) => key,
  }),
}));

vi.mock('../utils/adminApi', () => ({
  getFinancialSummary: vi.fn(),
}));

vi.mock('../components/admin/AdminLayout', () => ({
  default: ({ children }) => <div data-testid="admin-layout">{children}</div>,
}));

vi.mock('../components/admin/DateRangePicker', () => ({
  default: ({ startDate, endDate, onChange }) => (
    <div data-testid="date-picker">
      <button onClick={() => onChange(new Date('2024-01-01'), new Date('2024-01-07'))}>
        Change Date
      </button>
    </div>
  ),
}));

vi.mock('../components/admin/MetricCard', () => ({
  default: ({ title, value, loading, error, colorCode }) => (
    <div data-testid="metric-card">
      <div>{title}</div>
      {loading && <div>Loading...</div>}
      {error && <div>Error: {error}</div>}
      {!loading && !error && (
        <>
          <div>{value}</div>
          {colorCode && <div data-testid="color-code">{colorCode}</div>}
        </>
      )}
    </div>
  ),
}));

vi.mock('../components/admin/TimeSeriesChart', () => ({
  default: ({ data, loading, error }) => (
    <div data-testid="time-series-chart">
      {loading && <div>Chart Loading</div>}
      {error && <div>Chart Error: {error}</div>}
      {!loading && !error && data && <div>Chart Data: {data.length} points</div>}
    </div>
  ),
}));

describe('AdminFinancialPage', () => {
  const mockToken = 'mock-token';
  const mockOnLogout = vi.fn();

  const mockFinancialData = {
    total_revenue: 1000,
    total_cost: 600,
    stripe_revenue: 700,
    apple_revenue: 200,
    credit_usage: 100,
    daily: [
      { date: '2024-01-01', revenue: 100, cost: 60 },
      { date: '2024-01-02', revenue: 150, cost: 90 },
      { date: '2024-01-03', revenue: 200, cost: 120 },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should render page structure', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      expect(screen.getByText('admin.financial.title')).toBeInTheDocument();
    });

    expect(screen.getByTestId('admin-layout')).toBeInTheDocument();
    expect(screen.getByTestId('date-picker')).toBeInTheDocument();
    expect(screen.getByText('admin.financial.exportCSV')).toBeInTheDocument();
  });

  it('should render 4 summary cards', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      const metricCards = screen.getAllByTestId('metric-card');
      expect(metricCards).toHaveLength(4);
    });

    expect(screen.getByText('admin.financial.totalRevenue')).toBeInTheDocument();
    expect(screen.getByText('admin.financial.totalCosts')).toBeInTheDocument();
    expect(screen.getByText('admin.financial.grossProfit')).toBeInTheDocument();
    expect(screen.getByText('admin.financial.grossMargin')).toBeInTheDocument();
  });

  it('should render time series chart', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      expect(screen.getByTestId('time-series-chart')).toBeInTheDocument();
    });

    expect(screen.getByText('admin.financial.revenueVsCost')).toBeInTheDocument();
    expect(screen.getByText('Chart Data: 3 points')).toBeInTheDocument();
  });

  it('should render platform breakdown', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      expect(screen.getByText('admin.financial.platformBreakdown')).toBeInTheDocument();
    });

    expect(screen.getByText('admin.financial.stripeRevenue')).toBeInTheDocument();
    expect(screen.getByText('admin.financial.appleRevenue')).toBeInTheDocument();
    expect(screen.getByText('admin.financial.creditUsage')).toBeInTheDocument();
  });

  it('should calculate summary metrics correctly', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      // Total Revenue: $1000
      expect(screen.getByText('$1000.00')).toBeInTheDocument();
      // Total Costs: $600
      expect(screen.getByText('$600.00')).toBeInTheDocument();
      // Gross Profit: $400
      expect(screen.getByText('$400.00')).toBeInTheDocument();
      // Gross Margin: 40%
      expect(screen.getByText('40.0%')).toBeInTheDocument();
    });
  });

  it('should color-code margin card - green (>40%)', async () => {
    const highMarginData = {
      ...mockFinancialData,
      total_revenue: 1000,
      total_cost: 500, // 50% margin
    };
    adminApi.getFinancialSummary.mockResolvedValue(highMarginData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      const colorCodes = screen.getAllByTestId('color-code');
      expect(colorCodes.some(el => el.textContent === 'green')).toBe(true);
    });
  });

  it('should color-code margin card - yellow (30-40%)', async () => {
    const mediumMarginData = {
      ...mockFinancialData,
      total_revenue: 1000,
      total_cost: 650, // 35% margin
    };
    adminApi.getFinancialSummary.mockResolvedValue(mediumMarginData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      const colorCodes = screen.getAllByTestId('color-code');
      expect(colorCodes.some(el => el.textContent === 'yellow')).toBe(true);
    });
  });

  it('should color-code margin card - red (<30%)', async () => {
    const lowMarginData = {
      ...mockFinancialData,
      total_revenue: 1000,
      total_cost: 800, // 20% margin
    };
    adminApi.getFinancialSummary.mockResolvedValue(lowMarginData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      const colorCodes = screen.getAllByTestId('color-code');
      expect(colorCodes.some(el => el.textContent === 'red')).toBe(true);
    });
  });

  it('should handle date range changes', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      expect(adminApi.getFinancialSummary).toHaveBeenCalledTimes(1);
    });

    // Click date change button
    const changeDateBtn = screen.getByText('Change Date');
    await userEvent.click(changeDateBtn);

    await waitFor(() => {
      expect(adminApi.getFinancialSummary).toHaveBeenCalledTimes(2);
    });
  });

  it('should export CSV on button click', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    // Mock URL.createObjectURL and link.click
    const mockCreateObjectURL = vi.fn(() => 'blob:mock-url');
    const mockRevokeObjectURL = vi.fn();
    const mockClick = vi.fn();

    global.URL.createObjectURL = mockCreateObjectURL;
    global.URL.revokeObjectURL = mockRevokeObjectURL;

    // Mock document.createElement to return mock link only for 'a' elements
    const originalCreateElement = document.createElement.bind(document);
    const mockLink = {
      click: mockClick,
      href: '',
      download: '',
      style: {},
    };
    vi.spyOn(document, 'createElement').mockImplementation((tagName) => {
      if (tagName === 'a') {
        return mockLink;
      }
      return originalCreateElement(tagName);
    });

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      expect(screen.getByText('Chart Data: 3 points')).toBeInTheDocument();
    });

    const exportBtn = screen.getByText('admin.financial.exportCSV');
    await userEvent.click(exportBtn);

    expect(mockCreateObjectURL).toHaveBeenCalled();
    expect(mockClick).toHaveBeenCalled();
    expect(mockRevokeObjectURL).toHaveBeenCalled();
  });

  it('should not export CSV when no data', async () => {
    const emptyData = { ...mockFinancialData, daily: [] };
    adminApi.getFinancialSummary.mockResolvedValue(emptyData);

    global.alert = vi.fn();

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      const exportBtn = screen.getByText('admin.financial.exportCSV');
      expect(exportBtn).toBeDisabled();
    });
  });

  it('should show loading state', () => {
    adminApi.getFinancialSummary.mockReturnValue(new Promise(() => {})); // Never resolves

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    expect(screen.getAllByText('Loading...').length).toBeGreaterThan(0);
  });

  it('should show error state', async () => {
    adminApi.getFinancialSummary.mockRejectedValue(new Error('API Error'));

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      // Check for error message (i18n key + error text)
      expect(screen.getByText((content, element) => {
        return element?.tagName.toLowerCase() === 'p' &&
               content.includes('admin.financial.error') &&
               content.includes('API Error');
      })).toBeInTheDocument();
    });
  });

  it('should show empty state when no transactions', async () => {
    const emptyData = {
      total_revenue: 0,
      total_cost: 0,
      stripe_revenue: 0,
      apple_revenue: 0,
      credit_usage: 0,
      daily: [],
    };
    adminApi.getFinancialSummary.mockResolvedValue(emptyData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      // Wait for loading to complete first - check that metric cards show actual values (multiple $0.00)
      expect(screen.getAllByText('$0.00').length).toBeGreaterThan(0);
    });

    // Now check for empty state message (i18n key)
    expect(screen.getByText('admin.financial.empty')).toBeInTheDocument();
  });

  it('should display platform percentage breakdown', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      // Stripe: 700/1000 = 70%
      expect(screen.getByText('70.0% of total')).toBeInTheDocument();
      // Apple: 200/1000 = 20%
      expect(screen.getByText('20.0% of total')).toBeInTheDocument();
      // Credits: 100/1000 = 10%
      expect(screen.getByText('10.0% of total')).toBeInTheDocument();
    });
  });

  it('should handle zero revenue gracefully (no division by zero)', async () => {
    const zeroRevenueData = {
      total_revenue: 0,
      total_cost: 100,
      stripe_revenue: 0,
      apple_revenue: 0,
      credit_usage: 0,
      daily: [
        { date: '2024-01-01', revenue: 0, cost: 100 },
      ],
    };
    adminApi.getFinancialSummary.mockResolvedValue(zeroRevenueData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      // Margin should be 0%, not NaN or Infinity
      expect(screen.getByText('0.0%')).toBeInTheDocument();
    });

    // Should not show percentage breakdown if revenue is 0
    expect(screen.queryByText('% of total')).not.toBeInTheDocument();
  });

  it('should format currency with 2 decimal places', async () => {
    const decimalData = {
      ...mockFinancialData,
      total_revenue: 1234.56,
      total_cost: 789.12,
    };
    adminApi.getFinancialSummary.mockResolvedValue(decimalData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      expect(screen.getByText('$1234.56')).toBeInTheDocument();
      expect(screen.getByText('$789.12')).toBeInTheDocument();
    });
  });

  it('should call API with correct parameters', async () => {
    adminApi.getFinancialSummary.mockResolvedValue(mockFinancialData);

    render(<AdminFinancialPage token={mockToken} onLogout={mockOnLogout} />);

    await waitFor(() => {
      expect(adminApi.getFinancialSummary).toHaveBeenCalledWith(
        mockToken,
        expect.any(Date),
        expect.any(Date),
        'day'
      );
    });
  });
});
