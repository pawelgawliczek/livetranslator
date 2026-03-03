import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../../i18n';
import UserProfileModal from './UserProfileModal';

describe('UserProfileModal', () => {
  const mockUser = {
    user_id: 123,
    email: 'test@example.com',
    display_name: 'Test User',
    signup_date: '2024-01-15T10:30:00Z',
  };

  const mockOnClose = jest.fn();

  beforeEach(() => {
    mockOnClose.mockClear();
  });

  it('renders user profile information', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <UserProfileModal user={mockUser} onClose={mockOnClose} />
      </I18nextProvider>
    );

    expect(screen.getByText('User Details')).toBeInTheDocument();
    expect(screen.getByText('test@example.com')).toBeInTheDocument();
    expect(screen.getByText('Test User')).toBeInTheDocument();
    expect(screen.getByText('123')).toBeInTheDocument();
  });

  it('closes modal when close button clicked', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <UserProfileModal user={mockUser} onClose={mockOnClose} />
      </I18nextProvider>
    );

    const closeButton = screen.getByText('Close');
    fireEvent.click(closeButton);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('closes modal when backdrop clicked', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <UserProfileModal user={mockUser} onClose={mockOnClose} />
      </I18nextProvider>
    );

    const backdrop = screen.getByRole('dialog').parentElement;
    fireEvent.click(backdrop);

    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('does not close when modal content clicked', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <UserProfileModal user={mockUser} onClose={mockOnClose} />
      </I18nextProvider>
    );

    const modalContent = screen.getByRole('dialog');
    fireEvent.click(modalContent);

    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('formats signup date correctly', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <UserProfileModal user={mockUser} onClose={mockOnClose} />
      </I18nextProvider>
    );

    // Check that date is formatted (not raw ISO string)
    expect(screen.queryByText('2024-01-15T10:30:00Z')).not.toBeInTheDocument();
    expect(screen.getByText(/Jan|January/)).toBeInTheDocument();
  });

  it('handles missing optional fields gracefully', () => {
    const userWithMissingFields = {
      user_id: 456,
      email: 'incomplete@example.com',
      display_name: '',
      signup_date: null,
    };

    render(
      <I18nextProvider i18n={i18n}>
        <UserProfileModal user={userWithMissingFields} onClose={mockOnClose} />
      </I18nextProvider>
    );

    expect(screen.getByText('incomplete@example.com')).toBeInTheDocument();
    expect(screen.getByText('456')).toBeInTheDocument();
  });
});
