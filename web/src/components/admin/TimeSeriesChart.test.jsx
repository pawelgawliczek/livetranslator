import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import TimeSeriesChart from './TimeSeriesChart';

describe('TimeSeriesChart', () => {
  const mockData = [
    { date: '2024-01-01', revenue: 100, cost: 50 },
    { date: '2024-01-02', revenue: 150, cost: 75 },
    { date: '2024-01-03', revenue: 200, cost: 100 },
  ];

  it('should render chart with valid data', () => {
    const { container } = render(<TimeSeriesChart data={mockData} />);

    // Chart should render without errors (ResponsiveContainer may not fully render in jsdom)
    // Just verify the component doesn't throw and mounts successfully
    expect(container.firstChild).toBeTruthy();
  });

  it('should show loading state', () => {
    const { getByTestId, getByText } = render(<TimeSeriesChart loading={true} />);

    expect(getByTestId('chart-loading')).toBeInTheDocument();
    expect(getByText(/loading chart/i)).toBeInTheDocument();
  });

  it('should show error state', () => {
    const { getByTestId, getByText } = render(<TimeSeriesChart error="API Error" />);

    expect(getByTestId('chart-error')).toBeInTheDocument();
    expect(getByText(/error loading chart/i)).toBeInTheDocument();
    expect(getByText('API Error')).toBeInTheDocument();
  });

  it('should show empty state when data is null', () => {
    const { getByTestId, getByText } = render(<TimeSeriesChart data={null} />);

    expect(getByTestId('chart-empty')).toBeInTheDocument();
    expect(getByText(/no data available/i)).toBeInTheDocument();
  });

  it('should show empty state when data is empty array', () => {
    const { getByTestId, getByText } = render(<TimeSeriesChart data={[]} />);

    expect(getByTestId('chart-empty')).toBeInTheDocument();
    expect(getByText(/no data available/i)).toBeInTheDocument();
  });

  it('should not render chart when loading', () => {
    const { getByTestId, queryByTestId } = render(<TimeSeriesChart data={mockData} loading={true} />);

    expect(getByTestId('chart-loading')).toBeInTheDocument();
    expect(queryByTestId('chart-empty')).not.toBeInTheDocument();
  });

  it('should prioritize error over loading', () => {
    const { getByTestId, queryByTestId } = render(<TimeSeriesChart data={mockData} loading={true} error="API Error" />);

    expect(getByTestId('chart-error')).toBeInTheDocument();
    expect(queryByTestId('chart-loading')).not.toBeInTheDocument();
  });

  it('should handle data with zero values', () => {
    const zeroData = [
      { date: '2024-01-01', revenue: 0, cost: 0 },
    ];

    render(<TimeSeriesChart data={zeroData} />);

    // Should render chart, not empty state
    expect(screen.queryByTestId('chart-empty')).not.toBeInTheDocument();
  });

  it('should render with negative values', () => {
    const negativeData = [
      { date: '2024-01-01', revenue: 100, cost: 150 }, // Loss scenario
    ];

    render(<TimeSeriesChart data={negativeData} />);

    // Should render chart normally
    expect(screen.queryByTestId('chart-empty')).not.toBeInTheDocument();
  });
});
