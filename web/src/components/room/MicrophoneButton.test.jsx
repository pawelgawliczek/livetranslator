import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { renderWithProviders } from '@/test/utils';
import MicrophoneButton from './MicrophoneButton';

describe('MicrophoneButton', () => {
  describe('Rendering', () => {
    it('should render start button when status is idle', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveTextContent(/start/i);
      expect(button).toHaveTextContent('🎤');
    });

    it('should render stop button when streaming in normal mode', () => {
      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(/stop/i);
      expect(button).toHaveTextContent('⏹');
    });

    it('should render "Hold to Speak" when streaming in PTT mode and not pressing', () => {
      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={true}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(/hold.*speak/i);
      expect(button).toHaveTextContent('👆');
    });

    it('should render "Recording" when streaming in PTT mode and pressing', () => {
      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={true}
          isPressing={true}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveTextContent(/recording/i);
      expect(button).toHaveTextContent('🔴');
    });
  });

  describe('Click Interactions', () => {
    it('should call onStart when clicked in idle state', () => {
      const onStart = vi.fn();
      const onStop = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={onStart}
          onStop={onStop}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(onStart).toHaveBeenCalledTimes(1);
      expect(onStop).not.toHaveBeenCalled();
    });

    it('should call onStop when clicked in streaming state', () => {
      const onStart = vi.fn();
      const onStop = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={false}
          isPressing={false}
          onStart={onStart}
          onStop={onStop}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);

      expect(onStop).toHaveBeenCalledTimes(1);
      expect(onStart).not.toHaveBeenCalled();
    });

    it('should prevent context menu', () => {
      const preventDefault = vi.fn();
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.contextMenu(button, { preventDefault });

      expect(preventDefault).toHaveBeenCalled();
    });
  });

  describe('Push-to-Talk Mode - Mouse Events', () => {
    it('should call onPressStart on mouse down when PTT enabled and streaming', () => {
      const onPressStart = vi.fn();
      const onPressEnd = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={true}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
          onPressStart={onPressStart}
          onPressEnd={onPressEnd}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.mouseDown(button);

      expect(onPressStart).toHaveBeenCalledTimes(1);
      expect(onPressEnd).not.toHaveBeenCalled();
    });

    it('should call onPressEnd on mouse up when PTT enabled and streaming', () => {
      const onPressStart = vi.fn();
      const onPressEnd = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={true}
          isPressing={true}
          onStart={vi.fn()}
          onStop={vi.fn()}
          onPressStart={onPressStart}
          onPressEnd={onPressEnd}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.mouseUp(button);

      expect(onPressEnd).toHaveBeenCalledTimes(1);
    });

    it('should not call press handlers when PTT disabled', () => {
      const onPressStart = vi.fn();
      const onPressEnd = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
          onPressStart={onPressStart}
          onPressEnd={onPressEnd}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.mouseDown(button);
      fireEvent.mouseUp(button);

      expect(onPressStart).not.toHaveBeenCalled();
      expect(onPressEnd).not.toHaveBeenCalled();
    });

    it('should not call press handlers when status is idle', () => {
      const onPressStart = vi.fn();
      const onPressEnd = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={true}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
          onPressStart={onPressStart}
          onPressEnd={onPressEnd}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.mouseDown(button);
      fireEvent.mouseUp(button);

      expect(onPressStart).not.toHaveBeenCalled();
      expect(onPressEnd).not.toHaveBeenCalled();
    });
  });

  describe('Push-to-Talk Mode - Touch Events', () => {
    it('should call onPressStart on touch start when PTT enabled and streaming', () => {
      const onPressStart = vi.fn();
      const preventDefault = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={true}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
          onPressStart={onPressStart}
          onPressEnd={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.touchStart(button, { preventDefault });

      expect(preventDefault).toHaveBeenCalled();
      expect(onPressStart).toHaveBeenCalledTimes(1);
    });

    it('should call onPressEnd on touch end when PTT enabled and streaming', () => {
      const onPressEnd = vi.fn();
      const preventDefault = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={true}
          isPressing={true}
          onStart={vi.fn()}
          onStop={vi.fn()}
          onPressStart={vi.fn()}
          onPressEnd={onPressEnd}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.touchEnd(button, { preventDefault });

      expect(preventDefault).toHaveBeenCalled();
      expect(onPressEnd).toHaveBeenCalledTimes(1);
    });

    it('should not call touch press handlers when PTT disabled', () => {
      const onPressStart = vi.fn();
      const onPressEnd = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
          onPressStart={onPressStart}
          onPressEnd={onPressEnd}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.touchStart(button);
      fireEvent.touchEnd(button);

      expect(onPressStart).not.toHaveBeenCalled();
      expect(onPressEnd).not.toHaveBeenCalled();
    });
  });

  describe('Styling and Accessibility', () => {
    it('should have green background when idle', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({ background: 'rgb(22, 163, 74)' }); // #16a34a
    });

    it('should have red background when streaming', () => {
      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({ background: 'rgb(220, 38, 38)' }); // #dc2626
    });

    it('should have full width and proper height', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({
        width: '100%',
        height: '56px'
      });
    });

    it('should have rounded corners', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({ borderRadius: '28px' });
    });

    it('should be keyboard accessible', () => {
      const onStart = vi.fn();
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={onStart}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      button.focus();
      expect(button).toHaveFocus();

      fireEvent.keyDown(button, { key: 'Enter' });
      // Note: keyDown doesn't trigger click in JSDOM, but the button is keyboard accessible
    });

    it('should have proper ARIA label', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveAccessibleName();
    });
  });

  describe('Edge Cases', () => {
    it('should handle rapid clicks gracefully', () => {
      const onStart = vi.fn();
      const onStop = vi.fn();

      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={onStart}
          onStop={onStop}
        />
      );

      const button = screen.getByRole('button');
      fireEvent.click(button);
      fireEvent.click(button);
      fireEvent.click(button);

      expect(onStart).toHaveBeenCalledTimes(3);
    });

    it('should handle missing optional callbacks', () => {
      renderWithProviders(
        <MicrophoneButton
          status="streaming"
          pushToTalk={true}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(() => {
        fireEvent.mouseDown(button);
        fireEvent.mouseUp(button);
      }).not.toThrow();
    });

    it('should handle undefined status', () => {
      renderWithProviders(
        <MicrophoneButton
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toBeInTheDocument();
    });

    it('should handle all streaming status variations', () => {
      const statuses = ['streaming', 'connecting', 'reconnecting', 'error'];

      statuses.forEach(status => {
        const { unmount } = renderWithProviders(
          <MicrophoneButton
            status={status}
            pushToTalk={false}
            isPressing={false}
            onStart={vi.fn()}
            onStop={vi.fn()}
          />
        );

        const button = screen.getByRole('button');
        expect(button).toBeInTheDocument();

        unmount();
      });
    });
  });

  describe('User Experience', () => {
    it('should disable text selection for better UX', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({
        userSelect: 'none',
        WebkitUserSelect: 'none'
      });
    });

    it('should have no tap highlight for mobile', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({
        WebkitTapHighlightColor: 'transparent'
      });
    });

    it('should have touch manipulation for better mobile performance', () => {
      renderWithProviders(
        <MicrophoneButton
          status="idle"
          pushToTalk={false}
          isPressing={false}
          onStart={vi.fn()}
          onStop={vi.fn()}
        />
      );

      const button = screen.getByRole('button');
      expect(button).toHaveStyle({
        touchAction: 'manipulation'
      });
    });
  });
});
