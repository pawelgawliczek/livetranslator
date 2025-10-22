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
    <div style={{ position: "relative", ...style }}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
          padding: "0.5rem 1rem",
          background: "#1a1a1a",
          border: "1px solid #444",
          borderRadius: "8px",
          color: "white",
          cursor: "pointer",
          fontSize: "0.9rem",
          fontWeight: "500",
          transition: "all 0.2s"
        }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = "#666";
          e.currentTarget.style.background = "#2a2a2a";
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = "#444";
          e.currentTarget.style.background = "#1a1a1a";
        }}
      >
        <span>{currentLanguage.flag}</span>
        <span>{currentLanguage.name}</span>
        <span style={{ fontSize: "0.7rem", opacity: 0.7 }}>
          {isOpen ? "▲" : "▼"}
        </span>
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div
            onClick={() => setIsOpen(false)}
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 999
            }}
          />

          {/* Dropdown */}
          <div
            style={{
              position: "absolute",
              top: "calc(100% + 0.5rem)",
              right: 0,
              background: "#1a1a1a",
              border: "1px solid #444",
              borderRadius: "8px",
              boxShadow: "0 4px 12px rgba(0, 0, 0, 0.5)",
              zIndex: 1000,
              minWidth: "200px",
              maxHeight: "400px",
              overflowY: "auto"
            }}
          >
            {SUPPORTED_LANGUAGES.map(lang => (
              <button
                key={lang.code}
                onClick={() => changeLanguage(lang.code)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  gap: "0.75rem",
                  padding: "0.75rem 1rem",
                  background: i18n.language === lang.code ? "#2a2a2a" : "transparent",
                  border: "none",
                  borderBottom: "1px solid #333",
                  color: "white",
                  cursor: "pointer",
                  fontSize: "0.9rem",
                  textAlign: "left",
                  transition: "background 0.2s"
                }}
                onMouseEnter={e => {
                  if (i18n.language !== lang.code) {
                    e.currentTarget.style.background = "#252525";
                  }
                }}
                onMouseLeave={e => {
                  if (i18n.language !== lang.code) {
                    e.currentTarget.style.background = "transparent";
                  }
                }}
              >
                <span style={{ fontSize: "1.5rem" }}>{lang.flag}</span>
                <span style={{ flex: 1 }}>{lang.name}</span>
                {i18n.language === lang.code && (
                  <span style={{ color: "#3b82f6" }}>✓</span>
                )}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
