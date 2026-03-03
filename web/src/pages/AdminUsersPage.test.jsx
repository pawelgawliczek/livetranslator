import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '../i18n';
import AdminUsersPage from './AdminUsersPage';
import * as adminApi from '../utils/adminApi';

jest.mock('../utils/adminApi');

describe('AdminUsersPage', () => {
  const mockToken = 'test-token';
  const mockOnLogout = jest.fn();

  const mockSearchResults = {
    results: [
      {
        user_id: 123,
        email: 'test@example.com',
        display_name: 'Test User',
        signup_date: '2024-01-15T10:30:00Z',
      },
    ],
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('renders search input', () => {
    render(
      <I18nextProvider i18n={i18n}>
        <AdminUsersPage token={mockToken} onLogout={mockOnLogout} />
      </I18nextProvider>
    );

    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it('performs search when search button clicked', async () => {
    adminApi.searchUsers.mockResolvedValue(mockSearchResults);

    render(
      <I18nextProvider i18n={i18n}>
        <AdminUsersPage token={mockToken} onLogout={mockOnLogout} />
      </I18nextProvider>
    );

    const input = screen.getByPlaceholderText(/search/i);
    const searchButton = screen.getByRole('button', { name: /search/i });

    fireEvent.change(input, { target: { value: 'test@example.com' } });
    fireEvent.click(searchButton);

    await waitFor(() => {
      expect(adminApi.searchUsers).toHaveBeenCalledWith(mockToken, 'test@example.com');
    });
  });

  it('displays search results', async () => {
    adminApi.searchUsers.mockResolvedValue(mockSearchResults);

    render(
      <I18nextProvider i18n={i18n}>
        <AdminUsersPage token={mockToken} onLogout={mockOnLogout} />
      </I18nextProvider>
    );

    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: 'test@example.com' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });
  });

  it('displays empty state when no results', async () => {
    adminApi.searchUsers.mockResolvedValue({ results: [] });

    render(
      <I18nextProvider i18n={i18n}>
        <AdminUsersPage token={mockToken} onLogout={mockOnLogout} />
      </I18nextProvider>
    );

    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: 'nonexistent' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/no users found/i)).toBeInTheDocument();
    });
  });

  it('displays error message on API failure', async () => {
    adminApi.searchUsers.mockRejectedValue(new Error('API Error'));

    render(
      <I18nextProvider i18n={i18n}>
        <AdminUsersPage token={mockToken} onLogout={mockOnLogout} />
      </I18nextProvider>
    );

    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: 'test' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText(/search failed/i)).toBeInTheDocument();
    });
  });

  it('clears results when clear button clicked', async () => {
    adminApi.searchUsers.mockResolvedValue(mockSearchResults);

    render(
      <I18nextProvider i18n={i18n}>
        <AdminUsersPage token={mockToken} onLogout={mockOnLogout} />
      </I18nextProvider>
    );

    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.change(input, { target: { value: 'test' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(screen.getByText('test@example.com')).toBeInTheDocument();
    });

    const clearButton = screen.getByRole('button', { name: /clear/i });
    fireEvent.click(clearButton);

    expect(screen.queryByText('test@example.com')).not.toBeInTheDocument();
  });
});
