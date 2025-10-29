import React from "react";
import { useTranslation } from "react-i18next";
import { setUserLanguage, syncLanguageWithProfile } from "../utils/languageSync";

const SUPPORTED_LANGUAGES = [
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

export default function LanguageSelector({ style, token }) {
  const { i18n } = useTranslation();
  const [isOpen, setIsOpen] = React.useState(false);

  const currentLanguage = SUPPORTED_LANGUAGES.find(
    lang => lang.code === i18n.language
  ) || SUPPORTED_LANGUAGES[0];

  const changeLanguage = async (langCode) => {
    // Use unified language sync system
    setUserLanguage(langCode);

    // Sync with backend profile if token available
    if (token) {
      await syncLanguageWithProfile(token, langCode);
    }

    setIsOpen(false);
  };

  return (
    <div className="relative" style={style}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-4 py-2 bg-card border border-border rounded-lg text-fg cursor-pointer text-sm font-medium transition-all hover:bg-bg-secondary"
      >
        <span>{currentLanguage.flag}</span>
        <span>{currentLanguage.name}</span>
        <span className="text-xs opacity-70">
          {isOpen ? "▲" : "▼"}
        </span>
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setIsOpen(false)}
            className="fixed inset-0 z-[999]"
          />

          {/* Dropdown */}
          <div className="absolute top-[calc(100%+0.5rem)] right-0 bg-card border border-border rounded-lg shadow-lg z-[1000] min-w-[200px] max-h-[400px] overflow-y-auto">
            {SUPPORTED_LANGUAGES.map(lang => (
              <button
                key={lang.code}
                onClick={() => changeLanguage(lang.code)}
                className={`w-full flex items-center gap-3 px-4 py-3 border-b border-border text-fg cursor-pointer text-sm text-left transition-colors ${
                  i18n.language === lang.code ? 'bg-bg-secondary' : 'hover:bg-bg-secondary/50'
                }`}
              >
                <span className="text-2xl">{lang.flag}</span>
                <span className="flex-1">{lang.name}</span>
                {i18n.language === lang.code && (
                  <span className="text-blue-500">✓</span>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
