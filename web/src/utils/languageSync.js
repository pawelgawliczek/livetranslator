/**
 * Unified Language Synchronization System
 *
 * This ensures ONE language setting controls:
 * - UI language (i18n)
 * - STT/Translation language (room/profile)
 * - Profile preferred_lang (backend)
 */

import i18n from '../i18n';

const LANGUAGE_KEY = 'lt_user_language'; // Single source of truth

/**
 * Get the current user's language
 */
export function getUserLanguage() {
  // Check localStorage first
  const stored = localStorage.getItem(LANGUAGE_KEY);
  if (stored) {
    return stored;
  }

  // Fall back to browser language if supported
  const browserLang = navigator.language.split('-')[0];
  const supported = ['en', 'pl', 'ar', 'es', 'fr', 'de', 'it', 'pt', 'ru', 'zh', 'ja', 'ko'];
  if (supported.includes(browserLang)) {
    return browserLang;
  }

  return 'en'; // Default fallback
}

/**
 * Set the user's language - syncs everywhere
 */
export function setUserLanguage(languageCode) {
  // 1. Store in localStorage (single source of truth)
  localStorage.setItem(LANGUAGE_KEY, languageCode);

  // 2. Update i18n UI language
  i18n.changeLanguage(languageCode);

  // 3. Legacy compatibility - keep old keys in sync
  localStorage.setItem('lt_my_language', languageCode);
  localStorage.setItem('lt_ui_language', languageCode);

  console.log(`[LanguageSync] Language set to: ${languageCode}`);
}

/**
 * Initialize language on app load
 */
export function initializeLanguage() {
  const lang = getUserLanguage();

  // Sync i18n
  i18n.changeLanguage(lang);

  // Ensure legacy keys are in sync
  localStorage.setItem('lt_my_language', lang);
  localStorage.setItem('lt_ui_language', lang);

  console.log(`[LanguageSync] Initialized with language: ${lang}`);

  return lang;
}

/**
 * Sync language with backend profile
 */
export async function syncLanguageWithProfile(token, languageCode) {
  try {
    const response = await fetch('/api/profile', {
      method: 'PATCH',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        preferred_lang: languageCode
      })
    });

    if (response.ok) {
      console.log(`[LanguageSync] Synced language ${languageCode} with profile`);
      return true;
    } else {
      console.error('[LanguageSync] Failed to sync with profile');
      return false;
    }
  } catch (error) {
    console.error('[LanguageSync] Error syncing with profile:', error);
    return false;
  }
}

/**
 * Load language from profile on login
 */
export async function loadLanguageFromProfile(token) {
  try {
    const response = await fetch('/api/profile', {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (response.ok) {
      const profile = await response.json();
      if (profile.preferred_lang) {
        setUserLanguage(profile.preferred_lang);
        console.log(`[LanguageSync] Loaded language from profile: ${profile.preferred_lang}`);
        return profile.preferred_lang;
      }
    }
  } catch (error) {
    console.error('[LanguageSync] Error loading language from profile:', error);
  }

  return getUserLanguage();
}

/**
 * Check if user has selected a language (for forced selection)
 */
export function hasSelectedLanguage() {
  return !!localStorage.getItem(LANGUAGE_KEY);
}

/**
 * Force language selection (for first-time users)
 */
export function requireLanguageSelection() {
  return !hasSelectedLanguage();
}
