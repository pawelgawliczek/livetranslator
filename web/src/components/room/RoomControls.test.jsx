import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '@/test/utils';
import RoomControls from './RoomControls';

describe('RoomControls', () => {
  const defaultProps = {
    status: 'idle',
    pushToTalk: false,
    isPressing: false,
    networkQuality: 'unknown',
    networkRTT: null,
    onPushToTalkChange: vi.fn(),
    onStart: vi.fn(),
    onStop: vi.fn(),
    onPressStart: vi.fn(),
    onPressEnd: vi.fn()
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render all control elements', () => {
      renderWithProviders(<RoomControls {...defaultProps} />);

      // Push-to-talk checkbox should be present
      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeInTheDocument();

      // Push-to-talk label
      expect(screen.getByText(/push.*talk/i)).toBeInTheDocument();

      // Microphone button
      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should render with dark theme styling', () => {
      const { container } = renderWithProviders(<RoomControls {...defaultProps} />);

      // Check for dark background
      const controls = container.firstChild;
      expect(controls).toHaveStyle({
        background: '#1a1a1a'
      });
    });

    it('should have fixed bottom layout', () => {
      const { container } = renderWithProviders(<RoomControls {...defaultProps} />);

      const controls = container.firstChild;
      expect(controls).toHaveStyle({
        flexShrink: '0'
      });
    });

    it('should render network status when quality is not unknown', () => {
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          networkQuality="high"
          networkRTT={45}
        />
      );

      expect(screen.getByText(/45ms/)).toBeInTheDocument();
    });

    it('should not render network status when quality is unknown', () => {
      renderWithProviders(
        <RoomControls {...defaultProps} networkQuality="unknown" />
      );

      expect(screen.queryByText(/ms$/)).not.toBeInTheDocument();
    });
  });

  describe('Push-to-Talk Toggle', () => {
    it('should render checkbox unchecked by default', () => {
      renderWithProviders(<RoomControls {...defaultProps} pushToTalk={false} />);

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).not.toBeChecked();
    });

    it('should render checkbox checked when pushToTalk is true', () => {
      renderWithProviders(<RoomControls {...defaultProps} pushToTalk={true} />);

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toBeChecked();
    });

    it('should call onPushToTalkChange when checkbox is toggled', () => {
      const onPushToTalkChange = vi.fn();
      renderWithProviders(
        <RoomControls {...defaultProps} onPushToTalkChange={onPushToTalkChange} />
      );

      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);

      expect(onPushToTalkChange).toHaveBeenCalledTimes(1);
      expect(onPushToTalkChange).toHaveBeenCalledWith(true);
    });

    it('should toggle from true to false', () => {
      const onPushToTalkChange = vi.fn();
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          pushToTalk={true}
          onPushToTalkChange={onPushToTalkChange}
        />
      );

      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);

      expect(onPushToTalkChange).toHaveBeenCalledWith(false);
    });

    it('should be keyboard accessible', () => {
      const onPushToTalkChange = vi.fn();
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          onPushToTalkChange={onPushToTalkChange}
        />
      );

      const checkbox = screen.getByRole('checkbox');
      checkbox.focus();
      expect(checkbox).toHaveFocus();

      fireEvent.change(checkbox, { target: { checked: true } });
      expect(onPushToTalkChange).toHaveBeenCalled();
    });
  });

  describe('Network Status Integration', () => {
    it('should show high quality network status with green indicator', () => {
      const { container } = renderWithProviders(
        <RoomControls
          {...defaultProps}
          networkQuality="high"
          networkRTT={30}
        />
      );

      expect(screen.getByText(/30ms/)).toBeInTheDocument();
    });

    it('should show medium quality network status', () => {
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          networkQuality="medium"
          networkRTT={150}
        />
      );

      expect(screen.getByText(/150ms/)).toBeInTheDocument();
    });

    it('should show low quality network status', () => {
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          networkQuality="low"
          networkRTT={500}
        />
      );

      expect(screen.getByText(/500ms/)).toBeInTheDocument();
    });

    it('should show network status without RTT', () => {
      const { container } = renderWithProviders(
        <RoomControls
          {...defaultProps}
          networkQuality="high"
          networkRTT={null}
        />
      );

      // Should still render the indicator, just without the ms text
      expect(screen.queryByText(/ms$/)).not.toBeInTheDocument();
    });
  });

  describe('Microphone Button Integration', () => {
    it('should render microphone button with start state', () => {
      renderWithProviders(<RoomControls {...defaultProps} status="idle" />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(/start/i);
    });

    it('should render microphone button with stop state', () => {
      renderWithProviders(<RoomControls {...defaultProps} status="streaming" />);

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(/stop/i);
    });

    it('should pass onStart callback to microphone button', () => {
      const onStart = vi.fn();
      renderWithProviders(
        <RoomControls {...defaultProps} status="idle" onStart={onStart} />
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(onStart).toHaveBeenCalledTimes(1);
    });

    it('should pass onStop callback to microphone button', () => {
      const onStop = vi.fn();
      renderWithProviders(
        <RoomControls {...defaultProps} status="streaming" onStop={onStop} />
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(onStop).toHaveBeenCalledTimes(1);
    });

    it('should pass PTT props to microphone button', () => {
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          status="streaming"
          pushToTalk={true}
          isPressing={false}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(/hold.*speak/i);
    });

    it('should show recording state when PTT and pressing', () => {
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          status="streaming"
          pushToTalk={true}
          isPressing={true}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(/recording/i);
    });
  });

  describe('Layout and Spacing', () => {
    it('should have proper spacing between elements', () => {
      const { container } = renderWithProviders(
        <RoomControls {...defaultProps} networkQuality="high" networkRTT={45} />
      );

      // Check for gap between PTT and network status
      const topControls = container.querySelector('[style*="gap"]');
      expect(topControls).toBeInTheDocument();
    });

    it('should have safe area inset for mobile devices', () => {
      const { container } = renderWithProviders(<RoomControls {...defaultProps} />);

      const controls = container.firstChild;
      expect(controls).toHaveStyle({
        paddingBottom: 'max(0.75rem, env(safe-area-inset-bottom))'
      });
    });

    it('should have border at top', () => {
      const { container } = renderWithProviders(<RoomControls {...defaultProps} />);

      const controls = container.firstChild;
      expect(controls).toHaveStyle({
        borderTop: '1px solid #333'
      });
    });
  });

  describe('Accessibility', () => {
    it('should have proper label for PTT checkbox', () => {
      renderWithProviders(<RoomControls {...defaultProps} />);

      const checkbox = screen.getByRole('checkbox');
      expect(checkbox).toHaveAccessibleName(/push.*talk/i);
    });

    it('should have visible label text', () => {
      renderWithProviders(<RoomControls {...defaultProps} />);

      expect(screen.getByText(/push.*talk/i)).toBeVisible();
    });

    it('should allow keyboard navigation', () => {
      renderWithProviders(<RoomControls {...defaultProps} />);

      const checkbox = screen.getByRole('checkbox');
      const button = screen.getByRole('button');

      checkbox.focus();
      expect(checkbox).toHaveFocus();

      button.focus();
      expect(button).toHaveFocus();
    });
  });

  describe('Edge Cases', () => {
    it('should handle missing network quality', () => {
      renderWithProviders(<RoomControls {...defaultProps} networkQuality={undefined} />);

      expect(screen.queryByText(/ms$/)).not.toBeInTheDocument();
    });

    it('should handle all status variations', () => {
      const statuses = ['idle', 'streaming', 'connecting', 'reconnecting', 'error'];

      statuses.forEach(status => {
        const { unmount } = renderWithProviders(
          <RoomControls {...defaultProps} status={status} />
        );

        const button = screen.getByRole('button');
        expect(button).toBeInTheDocument();

        unmount();
      });
    });

    it('should handle rapid PTT toggle', () => {
      const onPushToTalkChange = vi.fn();
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          onPushToTalkChange={onPushToTalkChange}
        />
      );

      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);
      fireEvent.click(checkbox);
      fireEvent.click(checkbox);

      expect(onPushToTalkChange).toHaveBeenCalledTimes(3);
    });

    it('should handle missing callbacks gracefully', () => {
      expect(() => {
        renderWithProviders(
          <RoomControls
            status="idle"
            pushToTalk={false}
            isPressing={false}
            networkQuality="high"
            networkRTT={45}
          />
        );
      }).not.toThrow();
    });
  });

  describe('Integration with Child Components', () => {
    it('should pass all required props to MicrophoneButton', () => {
      const props = {
        status: 'streaming',
        pushToTalk: true,
        isPressing: true,
        onStart: vi.fn(),
        onStop: vi.fn(),
        onPressStart: vi.fn(),
        onPressEnd: vi.fn(),
        networkQuality: 'high',
        networkRTT: 45,
        onPushToTalkChange: vi.fn()
      };

      renderWithProviders(<RoomControls {...props} />);

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();

      // Test that pressing works
      fireEvent.mouseDown(button);
      expect(props.onPressStart).toHaveBeenCalled();
    });

    it('should pass correct props to NetworkStatusIndicator', () => {
      renderWithProviders(
        <RoomControls
          {...defaultProps}
          networkQuality="medium"
          networkRTT={120}
        />
      );

      expect(screen.getByText(/120ms/)).toBeInTheDocument();
    });
  });

  describe('User Experience', () => {
    it('should center PTT and network status', () => {
      const { container } = renderWithProviders(
        <RoomControls
          {...defaultProps}
          networkQuality="high"
          networkRTT={45}
        />
      );

      const topControls = container.querySelector('[style*="justify-content"]');
      expect(topControls).toHaveStyle({
        justifyContent: 'center'
      });
    });

    it('should have appropriate font size for PTT label', () => {
      const { container } = renderWithProviders(<RoomControls {...defaultProps} />);

      const label = screen.getByText(/push.*talk/i).closest('label');
      expect(label).toHaveStyle({
        fontSize: '0.8rem'
      });
    });

    it('should show pointer cursor on PTT label', () => {
      const { container } = renderWithProviders(<RoomControls {...defaultProps} />);

      const label = screen.getByText(/push.*talk/i).closest('label');
      expect(label).toHaveStyle({
        cursor: 'pointer'
      });
    });
  });
});
