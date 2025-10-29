/**
 * Supported languages for LiveTranslator
 * Used across the application for language selection and display
 */
export const LANGUAGES = [
  { code: "auto", name: "Auto", flag: "🌐" },
  { code: "en", name: "English", flag: "🇬🇧" },
  { code: "pl", name: "Polski", flag: "🇵🇱" },
  { code: "ar", name: "العربية", flag: "🇸🇦" },
  { code: "es", name: "Español", flag: "🇪🇸" },
  { code: "fr", name: "Français", flag: "🇫🇷" },
  { code: "de", name: "Deutsch", flag: "🇩🇪" },
  { code: "it", name: "Italiano", flag: "🇮🇹" },
  { code: "pt", name: "Português", flag: "🇵🇹" },
  { code: "ru", name: "Русский", flag: "🇷🇺" },
  { code: "zh", name: "中文", flag: "🇨🇳" },
  { code: "ja", name: "日本語", flag: "🇯🇵" },
  { code: "ko", name: "한국어", flag: "🇰🇷" }
];

/**
 * Get selectable languages (excludes "auto")
 */
export const getSelectableLanguages = () => {
  return LANGUAGES.filter(l => l.code !== "auto");
};

/**
 * Find language by code
 */
export const findLanguageByCode = (code) => {
  return LANGUAGES.find(l => l.code === code);
};

/**
 * Get language name by code
 */
export const getLanguageName = (code) => {
  const lang = findLanguageByCode(code);
  return lang ? lang.name : code;
};

/**
 * Get language flag by code
 */
export const getLanguageFlag = (code) => {
  const lang = findLanguageByCode(code);
  return lang ? lang.flag : '🌐';
};
