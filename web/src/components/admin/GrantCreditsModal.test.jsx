import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../i18n';
import GrantCreditsModal from './GrantCreditsModal';

// Mock adminApi
jest.mock('../../utils/adminApi', () => ({
  grantCredits: jest.fn(),
}));

const { grantCredits } = require('../../utils/adminApi');

describe('GrantCreditsModal', () => {
  const mockUser = {
    user_id: 123,
    email: 'test@example.com',
    display_name: 'Test User',
  };

  const mockToken = 'mock-admin-token';
  const mockOnClose = jest.fn();
  const mockOnSuccess = jest.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
    mockOnSuccess.mockClear();
    grantCredits.mockClear();
    jest.spyOn(window, 'confirm').mockImplementation(() => true);
  });

  afterEach(() => {
    window.confirm.mockRestore();
  });

  it('renders modal when isOpen is true', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    expect(screen.getByText('Grant Bonus Credits')).toBeInTheDocument();
    expect(screen.getByLabelText(/Hours to Grant/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Reason/i)).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={false}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    expect(screen.queryByText('Grant Bonus Credits')).not.toBeInTheDocument();
  });

  it('shows validation error when hours is less than 0.1', async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    fireEvent.change(hoursInput, { target: { value: '0.05' } });
    fireEvent.blur(hoursInput);

    await waitFor(() => {
      expect(screen.getByText(/Hours must be at least 0.1/i)).toBeInTheDocument();
    });
  });

  it('shows validation error when hours is greater than 100', async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    fireEvent.change(hoursInput, { target: { value: '101' } });
    fireEvent.blur(hoursInput);

    await waitFor(() => {
      expect(screen.getByText(/Hours cannot exceed 100/i)).toBeInTheDocument();
    });
  });

  it('shows validation error when reason is less than 10 characters', async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const reasonInput = screen.getByLabelText(/Reason/i);
    fireEvent.change(reasonInput, { target: { value: 'short' } });
    fireEvent.blur(reasonInput);

    await waitFor(() => {
      expect(screen.getByText(/Reason must be at least 10 characters/i)).toBeInTheDocument();
    });
  });

  it('submit button is disabled when validation fails', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const submitButton = screen.getByText('Grant Credits');
    expect(submitButton).toBeDisabled();
  });

  it('submit button is enabled when validation passes', async () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '10' } });
    fireEvent.change(reasonInput, { target: { value: 'Customer support compensation for service outage' } });

    await waitFor(() => {
      const submitButton = screen.getByText('Grant Credits');
      expect(submitButton).not.toBeDisabled();
    });
  });

  it('submit button is disabled during submission', async () => {
    grantCredits.mockImplementation(() => new Promise(resolve => setTimeout(resolve, 100)));

    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '5' } });
    fireEvent.change(reasonInput, { target: { value: 'Test reason for granting credits' } });

    const submitButton = screen.getByText('Grant Credits');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(submitButton).toBeDisabled();
    });
  });

  it('calls API with correct parameters on submit', async () => {
    grantCredits.mockResolvedValue({
      success: true,
      bonus_hours_granted: 10.0,
      user_id: 123,
    });

    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '10.5' } });
    fireEvent.change(reasonInput, { target: { value: 'Customer support compensation for service outage' } });

    const submitButton = screen.getByText('Grant Credits');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(grantCredits).toHaveBeenCalledWith(
        mockToken,
        123,
        10.5,
        'Customer support compensation for service outage'
      );
    });
  });

  it('shows confirmation dialog before submission', async () => {
    const mockConfirm = jest.spyOn(window, 'confirm').mockReturnValue(false);

    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '10' } });
    fireEvent.change(reasonInput, { target: { value: 'Test reason for granting credits' } });

    const submitButton = screen.getByText('Grant Credits');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockConfirm).toHaveBeenCalled();
      expect(grantCredits).not.toHaveBeenCalled();
    });

    mockConfirm.mockRestore();
  });

  it('shows success toast on successful grant', async () => {
    grantCredits.mockResolvedValue({
      success: true,
      bonus_hours_granted: 10.0,
      user_id: 123,
      user_email: 'test@example.com',
    });

    // Mock console.log to check for toast message
    const consoleSpy = jest.spyOn(console, 'log').mockImplementation(() => {});

    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '10' } });
    fireEvent.change(reasonInput, { target: { value: 'Test reason for granting credits' } });

    const submitButton = screen.getByText('Grant Credits');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  it('shows error toast on API failure', async () => {
    grantCredits.mockRejectedValue(new Error('Failed to grant credits'));

    const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {});

    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '10' } });
    fireEvent.change(reasonInput, { target: { value: 'Test reason for granting credits' } });

    const submitButton = screen.getByText('Grant Credits');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSuccess).not.toHaveBeenCalled();
      expect(mockOnClose).not.toHaveBeenCalled();
    });

    consoleSpy.mockRestore();
  });

  it('closes modal on success', async () => {
    grantCredits.mockResolvedValue({
      success: true,
      bonus_hours_granted: 5.0,
      user_id: 123,
    });

    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '5' } });
    fireEvent.change(reasonInput, { target: { value: 'Test reason for granting credits' } });

    const submitButton = screen.getByText('Grant Credits');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnClose).toHaveBeenCalledTimes(1);
    });
  });

  it('calls onSuccess callback after grant', async () => {
    grantCredits.mockResolvedValue({
      success: true,
      bonus_hours_granted: 5.0,
      user_id: 123,
    });

    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const hoursInput = screen.getByLabelText(/Hours to Grant/i);
    const reasonInput = screen.getByLabelText(/Reason/i);

    fireEvent.change(hoursInput, { target: { value: '5' } });
    fireEvent.change(reasonInput, { target: { value: 'Test reason for granting credits' } });

    const submitButton = screen.getByText('Grant Credits');
    fireEvent.click(submitButton);

    await waitFor(() => {
      expect(mockOnSuccess).toHaveBeenCalledTimes(1);
    });
  });

  it('closes modal when Cancel button is clicked', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const cancelButton = screen.getByText('Cancel');
    fireEvent.click(cancelButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('closes modal when backdrop is clicked', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <GrantCreditsModal
          isOpen={true}
          onClose={mockOnClose}
          user={mockUser}
          token={mockToken}
          onSuccess={mockOnSuccess}
        />
      </I18nextProvider>
    );

    const backdrop = screen.getByRole('dialog').parentElement;
    fireEvent.click(backdrop);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });
});
