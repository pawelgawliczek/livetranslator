import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import DateRangePicker from './DateRangePicker';

describe('DateRangePicker', () => {
  const mockOnChange = vi.fn();

  const defaultProps = {
    startDate: new Date('2024-01-01'),
    endDate: new Date('2024-01-07'),
    onChange: mockOnChange,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should render preset buttons', () => {
    render(<DateRangePicker {...defaultProps} />);

    expect(screen.getByText('Today')).toBeInTheDocument();
    expect(screen.getByText('Yesterday')).toBeInTheDocument();
    expect(screen.getByText('Last 7 days')).toBeInTheDocument();
    expect(screen.getByText('Last 30 days')).toBeInTheDocument();
    expect(screen.getByText('This month')).toBeInTheDocument();
    expect(screen.getByText('Last month')).toBeInTheDocument();
    expect(screen.getByText('Custom')).toBeInTheDocument();
  });

  it('should display current date range', () => {
    render(<DateRangePicker {...defaultProps} />);

    expect(screen.getByText(/Jan 01 - Jan 07, 2024/)).toBeInTheDocument();
  });

  it('should call onChange when preset clicked', () => {
    render(<DateRangePicker {...defaultProps} />);

    const todayButton = screen.getByText('Today');
    fireEvent.click(todayButton);

    expect(mockOnChange).toHaveBeenCalledWith(
      expect.any(Date),
      expect.any(Date)
    );
  });

  it('should show custom date inputs when Custom button clicked', () => {
    render(<DateRangePicker {...defaultProps} />);

    const customButton = screen.getByText('Custom');
    fireEvent.click(customButton);

    // Should show date inputs
    expect(screen.getByLabelText('Start')).toBeInTheDocument();
    expect(screen.getByLabelText('End')).toBeInTheDocument();
    expect(screen.getByText('Apply')).toBeInTheDocument();
    expect(screen.getByText('Reset')).toBeInTheDocument();
  });

  it('should apply custom date range', () => {
    render(<DateRangePicker {...defaultProps} />);

    // Open custom picker
    fireEvent.click(screen.getByText('Custom'));

    // Set dates
    const startInput = screen.getByLabelText('Start');
    const endInput = screen.getByLabelText('End');

    fireEvent.change(startInput, { target: { value: '2024-02-01' } });
    fireEvent.change(endInput, { target: { value: '2024-02-28' } });

    // Click Apply
    fireEvent.click(screen.getByText('Apply'));

    expect(mockOnChange).toHaveBeenCalledWith(
      expect.any(Date),
      expect.any(Date)
    );
  });

  it('should disable Apply button when dates not selected', () => {
    render(<DateRangePicker {...defaultProps} />);

    // Open custom picker
    fireEvent.click(screen.getByText('Custom'));

    // Clear dates
    const startInput = screen.getByLabelText('Start');
    fireEvent.change(startInput, { target: { value: '' } });

    const applyButton = screen.getByText('Apply');
    expect(applyButton).toBeDisabled();
  });

  it('should reset to Last 7 days when Reset clicked', () => {
    render(<DateRangePicker {...defaultProps} />);

    // Open custom picker
    fireEvent.click(screen.getByText('Custom'));

    // Click Reset
    fireEvent.click(screen.getByText('Reset'));

    expect(mockOnChange).toHaveBeenCalled();
  });

  it('should show error when start > end', () => {
    render(<DateRangePicker {...defaultProps} />);

    // Open custom picker
    fireEvent.click(screen.getByText('Custom'));

    const startInput = screen.getByLabelText('Start');
    const endInput = screen.getByLabelText('End');

    // Set invalid range (start > end)
    fireEvent.change(startInput, { target: { value: '2024-12-31' } });
    fireEvent.change(endInput, { target: { value: '2024-01-01' } });

    // Click Apply
    fireEvent.click(screen.getByText('Apply'));

    // Verify error message appears
    expect(screen.getByText(/start date must be before or equal to end date/i)).toBeInTheDocument();

    // Verify onChange was NOT called
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('should show error when range exceeds 365 days', () => {
    render(<DateRangePicker {...defaultProps} />);

    // Open custom picker
    fireEvent.click(screen.getByText('Custom'));

    const startInput = screen.getByLabelText('Start');
    const endInput = screen.getByLabelText('End');

    // Set range > 365 days (400 days)
    fireEvent.change(startInput, { target: { value: '2024-01-01' } });
    fireEvent.change(endInput, { target: { value: '2025-02-04' } });

    // Click Apply
    fireEvent.click(screen.getByText('Apply'));

    // Verify error message appears
    expect(screen.getByText(/date range cannot exceed 1 year/i)).toBeInTheDocument();

    // Verify onChange was NOT called
    expect(mockOnChange).not.toHaveBeenCalled();
  });

  it('should clear error on successful date selection', () => {
    render(<DateRangePicker {...defaultProps} />);

    // Open custom picker
    fireEvent.click(screen.getByText('Custom'));

    const startInput = screen.getByLabelText('Start');
    const endInput = screen.getByLabelText('End');

    // First trigger error
    fireEvent.change(startInput, { target: { value: '2024-12-31' } });
    fireEvent.change(endInput, { target: { value: '2024-01-01' } });
    fireEvent.click(screen.getByText('Apply'));

    // Verify error appears
    expect(screen.getByText(/start date must be before or equal to end date/i)).toBeInTheDocument();

    // Now fix the dates
    fireEvent.change(startInput, { target: { value: '2024-01-01' } });
    fireEvent.change(endInput, { target: { value: '2024-01-31' } });
    fireEvent.click(screen.getByText('Apply'));

    // Verify error is cleared
    expect(screen.queryByText(/start date must be before or equal to end date/i)).not.toBeInTheDocument();

    // Verify onChange WAS called
    expect(mockOnChange).toHaveBeenCalled();
  });
});
