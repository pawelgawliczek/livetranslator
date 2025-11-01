import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import RoomPageWrapper from './RoomPageWrapper';

// Mock child component
vi.mock('./RoomPage', () => ({
  default: vi.fn(() => <div data-testid="room-page">Room Page</div>)
}));

describe('RoomPageWrapper', () => {
  const defaultProps = {
    token: 'test-token',
    onLogout: vi.fn()
  };

  it('renders RoomPage', () => {
    render(
      <BrowserRouter>
        <RoomPageWrapper {...defaultProps} />
      </BrowserRouter>
    );

    expect(screen.getByTestId('room-page')).toBeInTheDocument();
  });

  it('passes token prop to RoomPage', async () => {
    const RoomPage = (await import('./RoomPage')).default;

    render(
      <BrowserRouter>
        <RoomPageWrapper token="test-token-123" onLogout={vi.fn()} />
      </BrowserRouter>
    );

    expect(RoomPage).toHaveBeenCalledWith(
      expect.objectContaining({
        token: 'test-token-123'
      }),
      expect.any(Object)
    );
  });

  it('passes onLogout prop to RoomPage', async () => {
    const RoomPage = (await import('./RoomPage')).default;
    const onLogout = vi.fn();

    render(
      <BrowserRouter>
        <RoomPageWrapper token="test-token" onLogout={onLogout} />
      </BrowserRouter>
    );

    expect(RoomPage).toHaveBeenCalledWith(
      expect.objectContaining({
        onLogout: onLogout
      }),
      expect.any(Object)
    );
  });
});
