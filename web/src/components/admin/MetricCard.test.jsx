import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import MetricCard from './MetricCard';

describe('MetricCard', () => {
  it('should render title and value', () => {
    render(
      <MetricCard
        title="Total Revenue"
        value="$12,450"
      />
    );

    expect(screen.getByText('Total Revenue')).toBeInTheDocument();
    expect(screen.getByText('$12,450')).toBeInTheDocument();
  });

  it('should render numeric value', () => {
    render(
      <MetricCard
        title="Active Users"
        value={1234}
      />
    );

    expect(screen.getByText('1234')).toBeInTheDocument();
  });

  it('should show trend indicator with positive change', () => {
    render(
      <MetricCard
        title="Revenue"
        value="$100"
        trend={5.2}
        trendLabel="vs last period"
      />
    );

    // Check for upward trend (positive)
    expect(screen.getByText(/5\.2%/)).toBeInTheDocument();
    expect(screen.getByText(/vs last period/)).toBeInTheDocument();

    // Check for trend icon/symbol
    const trendElement = screen.getByText(/5\.2%/).closest('div');
    expect(trendElement).toHaveClass('text-green-600');
  });

  it('should show trend indicator with negative change', () => {
    render(
      <MetricCard
        title="Revenue"
        value="$100"
        trend={-3.5}
        trendLabel="vs last period"
      />
    );

    // Check for trend value (may be split across elements)
    expect(screen.getByText(/3\.5/)).toBeInTheDocument();
    expect(screen.getByText(/vs last period/)).toBeInTheDocument();

    // Check for downward arrow
    expect(screen.getByText('↓')).toBeInTheDocument();

    // Check for red color class on trend container
    const trendContainer = screen.getByText('↓').parentElement;
    expect(trendContainer).toHaveClass('text-red-600');
  });

  it('should not show trend if not provided', () => {
    render(
      <MetricCard
        title="Revenue"
        value="$100"
      />
    );

    expect(screen.queryByText(/vs last period/)).not.toBeInTheDocument();
  });

  it('should apply red color code for low margin', () => {
    render(
      <MetricCard
        title="Gross Margin"
        value="25%"
        colorCode="red"
      />
    );

    const valueElement = screen.getByText('25%');
    expect(valueElement).toHaveClass('text-red-600');
  });

  it('should apply yellow color code for medium margin', () => {
    render(
      <MetricCard
        title="Gross Margin"
        value="35%"
        colorCode="yellow"
      />
    );

    const valueElement = screen.getByText('35%');
    expect(valueElement).toHaveClass('text-yellow-600');
  });

  it('should apply green color code for high margin', () => {
    render(
      <MetricCard
        title="Gross Margin"
        value="45%"
        colorCode="green"
      />
    );

    const valueElement = screen.getByText('45%');
    expect(valueElement).toHaveClass('text-green-600');
  });

  it('should show loading skeleton when loading', () => {
    render(
      <MetricCard
        title="Revenue"
        value="$100"
        loading={true}
      />
    );

    expect(screen.getByTestId('metric-card-loading')).toBeInTheDocument();
  });

  it('should show error message when error provided', () => {
    render(
      <MetricCard
        title="Revenue"
        value="$100"
        error="Failed to load data"
      />
    );

    expect(screen.getByText(/Failed to load data/)).toBeInTheDocument();
  });

  it('should be responsive', () => {
    const { container } = render(
      <MetricCard
        title="Revenue"
        value="$100"
      />
    );

    const card = container.firstChild;
    expect(card).toHaveClass('bg-card');
    expect(card).toHaveClass('rounded-lg');
    expect(card).toHaveClass('border');
  });
});
