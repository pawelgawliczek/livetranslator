import { render } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from 'i18next';

// Initialize i18n for tests
i18n.init({
  lng: 'en',
  fallbackLng: 'en',
  ns: ['translation'],
  defaultNS: 'translation',
  resources: {
    en: {
      translation: {
        room: {
          start: 'Start',
          stop: 'Stop',
          recording: 'Recording',
          holdToSpeak: 'Hold to Speak',
          pushToTalk: 'Push to Talk',
        },
        settings: {
          myLanguage: 'My Language',
          roomSettings: 'Room Settings',
        }
      }
    }
  }
});

/**
 * Custom render function that wraps components with necessary providers
 */
export function renderWithProviders(ui, options = {}) {
  const {
    route = '/',
    i18nInstance = i18n,
    ...renderOptions
  } = options;

  // Set the route if provided
  if (route !== '/') {
    window.history.pushState({}, 'Test page', route);
  }

  function Wrapper({ children }) {
    return (
      <BrowserRouter>
        <I18nextProvider i18n={i18nInstance}>
          {children}
        </I18nextProvider>
      </BrowserRouter>
    );
  }

  return {
    ...render(ui, { wrapper: Wrapper, ...renderOptions }),
    i18n: i18nInstance
  };
}

/**
 * Mock WebSocket for testing
 */
export class MockWebSocket {
  constructor(url) {
    this.url = url;
    this.readyState = MockWebSocket.CONNECTING;
    this.onopen = null;
    this.onclose = null;
    this.onmessage = null;
    this.onerror = null;

    // Simulate connection
    setTimeout(() => {
      this.readyState = MockWebSocket.OPEN;
      if (this.onopen) this.onopen({ type: 'open' });
    }, 0);
  }

  send(data) {
    if (this.readyState !== MockWebSocket.OPEN) {
      throw new Error('WebSocket is not open');
    }
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    if (this.onclose) this.onclose({ type: 'close' });
  }

  // Simulate receiving a message
  simulateMessage(data) {
    if (this.onmessage) {
      this.onmessage({ data: JSON.stringify(data) });
    }
  }

  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;
}

/**
 * Create mock room data
 */
export function createMockRoom(overrides = {}) {
  return {
    roomId: 'test-room',
    isAdmin: false,
    isPublic: false,
    persistenceEnabled: false,
    participants: [],
    languageCounts: {},
    ...overrides
  };
}

/**
 * Create mock message data
 */
export function createMockMessage(overrides = {}) {
  return {
    key: 'user1-segment1',
    speaker: 'user1@example.com',
    speaker_language: 'en',
    text_original: 'Hello world',
    segment_id: '1',
    source_mode: 'final',
    translations: {
      es: { text: 'Hola mundo', mode: 'final' },
      fr: { text: 'Bonjour le monde', mode: 'final' }
    },
    ...overrides
  };
}

export { i18n };
