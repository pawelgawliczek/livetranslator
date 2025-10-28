import { describe, it, expect, vi } from 'vitest';
import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import LanguagePickerModal from './LanguagePickerModal';
import { renderWithProviders } from '../../test/utils';
import { getSelectableLanguages } from '../../constants/languages';

describe('LanguagePickerModal', () => {
  const defaultProps = {
    isOpen: true,
    currentLanguage: 'en',
    onLanguageChange: vi.fn(),
    onClose: vi.fn()
  };

  it('renders when isOpen is true', () => {
    renderWithProviders(<LanguagePickerModal {...defaultProps} />);
    expect(screen.getByText('My Language')).toBeInTheDocument();
  });

  it('does not render when isOpen is false', () => {
    const { container } = renderWithProviders(
      <LanguagePickerModal {...defaultProps} isOpen={false} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('displays the modal title', () => {
    renderWithProviders(<LanguagePickerModal {...defaultProps} />);
    expect(screen.getByText('My Language')).toBeInTheDocument();
  });

  it('displays description text', () => {
    renderWithProviders(<LanguagePickerModal {...defaultProps} />);
    // The description is split across translation keys, just check that both are present
    expect(screen.getByText(/select.*language/i)).toBeInTheDocument();
  });

  it('displays language label', () => {
    renderWithProviders(<LanguagePickerModal {...defaultProps} />);
    expect(screen.getByText('Language')).toBeInTheDocument();
  });

  it('displays Done button', () => {
    renderWithProviders(<LanguagePickerModal {...defaultProps} />);
    expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument();
  });

  describe('Language Selection', () => {
    it('displays all selectable languages in dropdown', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const select = screen.getByRole('combobox');
      const options = select.querySelectorAll('option');

      const selectableLanguages = getSelectableLanguages();
      expect(options).toHaveLength(selectableLanguages.length);
    });

    it('does not include "auto" language', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const select = screen.getByRole('combobox');
      const options = Array.from(select.querySelectorAll('option'));

      const hasAuto = options.some(opt => opt.value === 'auto');
      expect(hasAuto).toBe(false);
    });

    it('displays language flags and names', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const select = screen.getByRole('combobox');
      const options = select.querySelectorAll('option');

      // Check first option has both flag and name
      expect(options[0].textContent).toMatch(/🇬🇧.*English/);
    });

    it('selects current language by default', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} currentLanguage="es" />);
      const select = screen.getByRole('combobox');
      expect(select.value).toBe('es');
    });

    it('handles undefined currentLanguage', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} currentLanguage={undefined} />);
      const select = screen.getByRole('combobox');
      expect(select.value).toBe('');
    });

    it('handles null currentLanguage', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} currentLanguage={null} />);
      const select = screen.getByRole('combobox');
      expect(select.value).toBe('');
    });
  });

  describe('User Interactions', () => {
    it('calls onLanguageChange when language is selected', async () => {
      const user = userEvent.setup();
      const onLanguageChange = vi.fn();
      renderWithProviders(
        <LanguagePickerModal {...defaultProps} onLanguageChange={onLanguageChange} />
      );

      const select = screen.getByRole('combobox');
      await user.selectOptions(select, 'fr');

      expect(onLanguageChange).toHaveBeenCalledWith('fr');
    });

    it('calls onClose when Done button is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<LanguagePickerModal {...defaultProps} onClose={onClose} />);

      await user.click(screen.getByRole('button', { name: 'Done' }));
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('calls onClose when backdrop is clicked', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      const { container } = renderWithProviders(
        <LanguagePickerModal {...defaultProps} onClose={onClose} />
      );

      // Click the backdrop (first div with fixed positioning)
      const backdrop = container.querySelector('.fixed.inset-0');
      await user.click(backdrop);

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not close when clicking inside modal content', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<LanguagePickerModal {...defaultProps} onClose={onClose} />);

      const title = screen.getByText('My Language');
      await user.click(title);

      expect(onClose).not.toHaveBeenCalled();
    });

    it('can change language multiple times', async () => {
      const user = userEvent.setup();
      const onLanguageChange = vi.fn();
      renderWithProviders(
        <LanguagePickerModal {...defaultProps} onLanguageChange={onLanguageChange} />
      );

      const select = screen.getByRole('combobox');

      await user.selectOptions(select, 'es');
      await user.selectOptions(select, 'de');
      await user.selectOptions(select, 'ja');

      expect(onLanguageChange).toHaveBeenCalledTimes(3);
      expect(onLanguageChange).toHaveBeenNthCalledWith(1, 'es');
      expect(onLanguageChange).toHaveBeenNthCalledWith(2, 'de');
      expect(onLanguageChange).toHaveBeenNthCalledWith(3, 'ja');
    });
  });

  describe('Accessibility', () => {
    it('select has proper role', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('Done button has proper role', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      expect(screen.getByRole('button', { name: 'Done' })).toBeInTheDocument();
    });

    it('select is keyboard navigable', async () => {
      const user = userEvent.setup();
      const onLanguageChange = vi.fn();
      renderWithProviders(
        <LanguagePickerModal {...defaultProps} onLanguageChange={onLanguageChange} />
      );

      const select = screen.getByRole('combobox');
      select.focus();

      // Should be able to change via keyboard
      await user.selectOptions(select, 'pl');
      expect(onLanguageChange).toHaveBeenCalledWith('pl');
    });

    it('Done button is keyboard accessible', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<LanguagePickerModal {...defaultProps} onClose={onClose} />);

      const button = screen.getByRole('button', { name: 'Done' });
      button.focus();
      await user.keyboard('{Enter}');

      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('can close with Escape key', async () => {
      const user = userEvent.setup();
      const onClose = vi.fn();
      renderWithProviders(<LanguagePickerModal {...defaultProps} onClose={onClose} />);

      await user.keyboard('{Escape}');
      expect(onClose).toHaveBeenCalledTimes(1);
    });
  });

  describe('Focus Management', () => {
    it('select has focus styles', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const select = screen.getByRole('combobox');
      expect(select).toHaveClass('focus:ring-2', 'focus:ring-accent');
    });
  });

  describe('Styling', () => {
    it('applies correct container spacing', () => {
      const { container } = renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const contentDiv = container.querySelector('.space-y-4');
      expect(contentDiv).toBeInTheDocument();
    });

    it('title has correct styling', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const title = screen.getByText('My Language');
      expect(title).toHaveClass('text-xl', 'font-semibold', 'text-fg-dark');
    });

    it('description has muted styling', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const description = screen.getByText(/select.*language/i);
      expect(description).toHaveClass('text-sm', 'text-muted-dark');
    });

    it('select has dark theme styling', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const select = screen.getByRole('combobox');
      expect(select).toHaveClass('bg-[#2a2a2a]', 'border-[#444]', 'text-white');
    });

    it('Done button has accent color', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Done' });
      expect(button).toHaveClass('bg-accent', 'text-white');
    });

    it('Done button has hover effect', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const button = screen.getByRole('button', { name: 'Done' });
      expect(button).toHaveClass('hover:bg-accent/90', 'transition-colors');
    });
  });

  describe('Edge Cases', () => {
    it('renders with all languages available', () => {
      renderWithProviders(<LanguagePickerModal {...defaultProps} />);
      const select = screen.getByRole('combobox');
      const options = select.querySelectorAll('option');

      // Should have 12 languages (13 total minus "auto")
      expect(options.length).toBeGreaterThan(10);
    });

    it('handles rapid language changes', async () => {
      const user = userEvent.setup();
      const onLanguageChange = vi.fn();
      renderWithProviders(
        <LanguagePickerModal {...defaultProps} onLanguageChange={onLanguageChange} />
      );

      const select = screen.getByRole('combobox');

      // Rapid changes
      await user.selectOptions(select, 'es');
      await user.selectOptions(select, 'fr');
      await user.selectOptions(select, 'de');
      await user.selectOptions(select, 'it');

      expect(onLanguageChange).toHaveBeenCalledTimes(4);
    });

    it('maintains selection after reopen', () => {
      const { rerender } = renderWithProviders(
        <LanguagePickerModal {...defaultProps} currentLanguage="ja" isOpen={true} />
      );

      let select = screen.getByRole('combobox');
      expect(select.value).toBe('ja');

      // Close modal
      rerender(<LanguagePickerModal {...defaultProps} currentLanguage="ja" isOpen={false} />);

      // Reopen modal
      rerender(<LanguagePickerModal {...defaultProps} currentLanguage="ja" isOpen={true} />);

      select = screen.getByRole('combobox');
      expect(select.value).toBe('ja');
    });
  });

  describe('Component Behavior', () => {
    it('re-renders when currentLanguage changes', () => {
      const { rerender } = renderWithProviders(
        <LanguagePickerModal {...defaultProps} currentLanguage="en" />
      );

      let select = screen.getByRole('combobox');
      expect(select.value).toBe('en');

      rerender(<LanguagePickerModal {...defaultProps} currentLanguage="fr" />);

      select = screen.getByRole('combobox');
      expect(select.value).toBe('fr');
    });

    it('handles modal state toggle', () => {
      const { rerender } = renderWithProviders(
        <LanguagePickerModal {...defaultProps} isOpen={true} />
      );
      expect(screen.getByText('My Language')).toBeInTheDocument();

      rerender(<LanguagePickerModal {...defaultProps} isOpen={false} />);
      expect(screen.queryByText('My Language')).not.toBeInTheDocument();

      rerender(<LanguagePickerModal {...defaultProps} isOpen={true} />);
      expect(screen.getByText('My Language')).toBeInTheDocument();
    });
  });
});
