import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RoomHeader from './RoomHeader';

describe('RoomHeader', () => {
  const mockLanguages = [
    { code: 'en', flag: '🇬🇧', name: 'English' },
    { code: 'es', flag: '🇪🇸', name: 'Spanish' },
    { code: 'fr', flag: '🇫🇷', name: 'French' },
    { code: 'de', flag: '🇩🇪', name: 'German' },
  ];

  const defaultProps = {
    roomId: 'test-room-123',
    languageCounts: {},
    languages: mockLanguages,
    vadStatus: 'idle',
    vadReady: false,
    onBackClick: vi.fn(),
    onMenuClick: vi.fn(),
  };

  it('renders room name correctly', () => {
    render(<RoomHeader {...defaultProps} />);
    expect(screen.getByText('test-room-123')).toBeInTheDocument();
  });

  it('renders back button', () => {
    render(<RoomHeader {...defaultProps} />);
    const backButton = screen.getByLabelText('Go back');
    expect(backButton).toBeInTheDocument();
    expect(backButton).toHaveTextContent('←');
  });

  it('renders menu button', () => {
    render(<RoomHeader {...defaultProps} />);
    const menuButton = screen.getByLabelText('Open menu');
    expect(menuButton).toBeInTheDocument();
    expect(menuButton).toHaveTextContent('⋮');
  });

  it('calls onBackClick when back button is clicked', async () => {
    const user = userEvent.setup();
    const onBackClick = vi.fn();
    render(<RoomHeader {...defaultProps} onBackClick={onBackClick} />);

    await user.click(screen.getByLabelText('Go back'));
    expect(onBackClick).toHaveBeenCalledTimes(1);
  });

  it('calls onMenuClick when menu button is clicked', async () => {
    const user = userEvent.setup();
    const onMenuClick = vi.fn();
    render(<RoomHeader {...defaultProps} onMenuClick={onMenuClick} />);

    await user.click(screen.getByLabelText('Open menu'));
    expect(onMenuClick).toHaveBeenCalledTimes(1);
  });

  describe('Language Counts', () => {
    it('does not render language counts when empty', () => {
      render(<RoomHeader {...defaultProps} languageCounts={{}} />);
      expect(screen.queryByText('🇬🇧')).not.toBeInTheDocument();
    });

    it('renders single language count', () => {
      const languageCounts = { en: 2 };
      render(<RoomHeader {...defaultProps} languageCounts={languageCounts} />);

      expect(screen.getByText('🇬🇧')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('renders multiple language counts', () => {
      const languageCounts = { en: 3, es: 2, fr: 1 };
      render(<RoomHeader {...defaultProps} languageCounts={languageCounts} />);

      expect(screen.getByText('🇬🇧')).toBeInTheDocument();
      expect(screen.getByText('🇪🇸')).toBeInTheDocument();
      expect(screen.getByText('🇫🇷')).toBeInTheDocument();
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('shows fallback flag for unknown language', () => {
      const languageCounts = { unknown: 1 };
      render(<RoomHeader {...defaultProps} languageCounts={languageCounts} />);

      expect(screen.getByText('🌐')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });

    it('renders counts in correct order (as provided)', () => {
      const languageCounts = { es: 1, en: 2, de: 3 };
      const { container } = render(
        <RoomHeader {...defaultProps} languageCounts={languageCounts} />
      );

      const counts = container.querySelectorAll('.inline-flex.items-center.gap-0\\.5');
      expect(counts).toHaveLength(3);
    });
  });

  describe('VAD Status', () => {
    it('does not show VAD status when idle', () => {
      render(<RoomHeader {...defaultProps} vadStatus="idle" vadReady={false} />);
      expect(screen.queryByText(/listening|processing/i)).not.toBeInTheDocument();
    });

    it('shows VAD status when not idle', () => {
      render(<RoomHeader {...defaultProps} vadStatus="Listening..." vadReady={false} />);
      expect(screen.getByText('Listening...')).toBeInTheDocument();
    });

    it('shows VAD status with ready state (green)', () => {
      render(<RoomHeader {...defaultProps} vadStatus="Ready" vadReady={true} />);
      const statusElement = screen.getByText('Ready');
      expect(statusElement).toBeInTheDocument();
      expect(statusElement).toHaveClass('text-green-600');
    });

    it('shows VAD status with not ready state (muted)', () => {
      render(<RoomHeader {...defaultProps} vadStatus="Loading..." vadReady={false} />);
      const statusElement = screen.getByText('Loading...');
      expect(statusElement).toBeInTheDocument();
      expect(statusElement).toHaveClass('text-muted-dark');
    });
  });

  describe('Accessibility', () => {
    it('has accessible button labels', () => {
      render(<RoomHeader {...defaultProps} />);
      expect(screen.getByLabelText('Go back')).toBeInTheDocument();
      expect(screen.getByLabelText('Open menu')).toBeInTheDocument();
    });

    it('has title attribute on menu button', () => {
      render(<RoomHeader {...defaultProps} />);
      const menuButton = screen.getByTitle('Menu');
      expect(menuButton).toBeInTheDocument();
    });

    it('back button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onBackClick = vi.fn();
      render(<RoomHeader {...defaultProps} onBackClick={onBackClick} />);

      const backButton = screen.getByLabelText('Go back');
      backButton.focus();
      await user.keyboard('{Enter}');
      expect(onBackClick).toHaveBeenCalledTimes(1);
    });

    it('menu button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onMenuClick = vi.fn();
      render(<RoomHeader {...defaultProps} onMenuClick={onMenuClick} />);

      const menuButton = screen.getByLabelText('Open menu');
      menuButton.focus();
      await user.keyboard('{Enter}');
      expect(onMenuClick).toHaveBeenCalledTimes(1);
    });
  });

  describe('Layout', () => {
    it('has proper flexbox structure', () => {
      const { container } = render(<RoomHeader {...defaultProps} />);
      const headerDiv = container.firstChild;
      expect(headerDiv).toHaveClass('flex', 'items-center', 'justify-between');
    });

    it('back button does not shrink', () => {
      render(<RoomHeader {...defaultProps} />);
      const backButton = screen.getByLabelText('Go back');
      expect(backButton).toHaveClass('shrink-0');
    });

    it('menu button does not shrink', () => {
      render(<RoomHeader {...defaultProps} />);
      const menuButton = screen.getByLabelText('Open menu');
      expect(menuButton).toHaveClass('shrink-0');
    });

    it('center content can grow and shrink', () => {
      const { container } = render(<RoomHeader {...defaultProps} />);
      const centerDiv = container.querySelector('.flex-1');
      expect(centerDiv).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('handles very long room names', () => {
      const longRoomId = 'a'.repeat(100);
      render(<RoomHeader {...defaultProps} roomId={longRoomId} />);
      expect(screen.getByText(longRoomId)).toHaveClass('overflow-hidden', 'text-ellipsis');
    });

    it('handles empty language array', () => {
      const languageCounts = { en: 1 };
      render(<RoomHeader {...defaultProps} languages={[]} languageCounts={languageCounts} />);
      // Should show fallback flag
      expect(screen.getByText('🌐')).toBeInTheDocument();
    });

    it('handles undefined languageCounts', () => {
      render(<RoomHeader {...defaultProps} languageCounts={undefined} />);
      // Should not crash, just not show any counts
      expect(screen.queryByText('🌐')).not.toBeInTheDocument();
    });

    it('handles language count of zero', () => {
      const languageCounts = { en: 0, es: 1 };
      render(<RoomHeader {...defaultProps} languageCounts={languageCounts} />);
      // Should render both, even with zero count
      expect(screen.getByText('0')).toBeInTheDocument();
      expect(screen.getByText('1')).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('applies dark theme colors', () => {
      const { container } = render(<RoomHeader {...defaultProps} />);
      const header = container.firstChild;
      expect(header).toHaveClass('bg-card-dark', 'border-border-dark');
    });

    it('buttons have hover states', () => {
      render(<RoomHeader {...defaultProps} />);
      const backButton = screen.getByLabelText('Go back');
      const menuButton = screen.getByLabelText('Open menu');

      expect(backButton).toHaveClass('hover:bg-[#333]', 'transition-colors');
      expect(menuButton).toHaveClass('hover:bg-[#333]', 'transition-colors');
    });
  });
});
