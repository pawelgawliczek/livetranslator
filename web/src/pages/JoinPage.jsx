import React, { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";
import { getUserLanguage, setUserLanguage, syncLanguageWithProfile } from "../utils/languageSync";

export default function JoinPage({ token, onLogin }) {
  const { t } = useTranslation();
  const { inviteCode } = useParams();
  const navigate = useNavigate();
  const [status, setStatus] = useState("validating"); // validating, valid, invalid, joining
  const [roomInfo, setRoomInfo] = useState(null);
  const [error, setError] = useState(null);
  const [displayName, setDisplayName] = useState("");
  const [language, setLanguage] = useState(() => getUserLanguage());
  const [userEmail, setUserEmail] = useState(null);

  // Decode token to get user email
  useEffect(() => {
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUserEmail(payload.email);
      } catch (e) {
        console.error('Failed to decode token:', e);
      }
    }
  }, [token]);

  const languages = [
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

  useEffect(() => {
    validateInvite();
  }, [inviteCode]);

  async function validateInvite() {
    try {
      setStatus("validating");
      const response = await fetch(`/api/invites/validate/${inviteCode}`);

      if (!response.ok) {
        throw new Error("Failed to validate invite");
      }

      const data = await response.json();

      if (!data.valid) {
        setStatus("invalid");
        setError("This invite link is invalid or has expired.");
        return;
      }

      setRoomInfo(data);
      setStatus("valid");
    } catch (e) {
      console.error("Failed to validate invite:", e);
      setStatus("invalid");
      setError("Failed to validate invite. Please try again.");
    }
  }

  // Handle language change with persistent sync
  async function handleLanguageChange(newLanguage) {
    setLanguage(newLanguage);

    // Sync language to UI and localStorage
    setUserLanguage(newLanguage);

    // If user is logged in, sync with backend profile
    if (token) {
      await syncLanguageWithProfile(token, newLanguage);
    }

    console.log('[JoinPage] Language changed to:', newLanguage);
  }

  async function joinRoom() {
    if (!displayName.trim()) {
      alert(t('joinPage.yourName'));
      return;
    }

    setStatus("joining");

    try {
      // If user is not logged in, create a guest token
      if (!token) {
        // Normalize language code (e.g., "en-GB" -> "en") for Speechmatics compatibility
        const normalizedLanguage = language ? language.split('-')[0] : 'en';

        const guestTokenResp = await fetch("/api/guest/token", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            display_name: displayName,
            room_code: roomInfo.room_code,
            invite_code: inviteCode,
            language: normalizedLanguage
          })
        });

        if (!guestTokenResp.ok) {
          throw new Error("Failed to create guest token");
        }

        const { token: guestToken } = await guestTokenResp.json();

        // Store guest token and info in sessionStorage
        sessionStorage.setItem('guest_token', guestToken);
        sessionStorage.setItem('guest_display_name', displayName);
        sessionStorage.setItem('guest_language', language);
        sessionStorage.setItem('is_guest', 'true');

        // Language is already synced via handleLanguageChange, but ensure it's set
        // This allows guests to have persistent language preference across sessions
        setUserLanguage(language);
      } else {
        // For logged-in users, ensure language is synced to profile
        await syncLanguageWithProfile(token, language);
      }

      // Navigate to room
      navigate(`/room/${roomInfo.room_code}`);
    } catch (e) {
      console.error("Failed to join room:", e);
      setError("Failed to join room. Please try again.");
      setStatus("valid");
    }
  }

  if (status === "validating") {
    return (
      <div style={styles.container}>
        <div style={styles.content}>
          <div style={styles.card}>
            <div style={styles.loadingSpinner}>
              <div style={styles.spinner}></div>
              <p style={styles.loadingText}>{t('joinPage.validatingInvite')}</p>
            </div>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  if (status === "invalid") {
    return (
      <div style={styles.container}>
        <div style={styles.content}>
          <div style={styles.card}>
            <div style={styles.errorIcon}>⚠️</div>
            <h1 style={styles.title}>{t('joinPage.invalidInvite')}</h1>
            <p style={styles.errorText}>{error}</p>
            <button
              style={styles.primaryButton}
              onClick={() => navigate("/")}
            >
              {t('joinPage.goToHome')}
            </button>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  if (status === "joining") {
    return (
      <div style={styles.container}>
        <div style={styles.content}>
          <div style={styles.card}>
            <div style={styles.loadingSpinner}>
              <div style={styles.spinner}></div>
              <p style={styles.loadingText}>{t('joinPage.joiningRoom')}</p>
            </div>
          </div>
        </div>
        <Footer />
      </div>
    );
  }

  return (
    <div style={styles.container}>
      <div style={styles.content}>
        <div style={styles.card}>
        <div style={styles.header}>
          <div style={styles.checkIcon}>✓</div>
          <h1 style={styles.title}>{t('joinPage.joinRoom')}</h1>
          <p style={styles.subtitle}>
            {t('joinPage.youAreInvited')} <strong>{roomInfo?.room_code}</strong>
          </p>
        </div>

        <div style={styles.form}>
          <div style={styles.formGroup}>
            <label style={styles.label}>{t('joinPage.yourName')}</label>
            <input
              type="text"
              placeholder={t('joinPage.enterDisplayName')}
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && joinRoom()}
              style={styles.input}
              autoFocus
            />
          </div>

          <div style={styles.formGroup}>
            <label style={styles.label}>{t('joinPage.yourLanguage')}</label>
            <select
              value={language}
              onChange={(e) => handleLanguageChange(e.target.value)}
              style={styles.select}
            >
              {languages.map(lang => (
                <option key={lang.code} value={lang.code}>
                  {lang.flag} {lang.name}
                </option>
              ))}
            </select>
            <p style={styles.hint}>
              {t('joinPage.messagesTranslated')}
            </p>
          </div>

          {!token ? (
            <>
              <button
                style={styles.primaryButton}
                onClick={joinRoom}
              >
                🚀 {t('joinPage.joinAsGuest')}
              </button>
              <p style={styles.guestHint}>
                {t('joinPage.guestNote')}
              </p>
              <div style={styles.divider}>
                <span style={styles.dividerText}>{t('common.or')}</span>
              </div>
              <button
                style={styles.secondaryButton}
                onClick={() => {
                  sessionStorage.setItem('join_after_login', JSON.stringify({
                    roomCode: roomInfo.room_code,
                    inviteCode: inviteCode,
                    displayName: displayName,
                    language: language
                  }));
                  navigate("/login");
                }}
              >
                🔐 {t('joinPage.loginToJoin')}
              </button>
              <p style={styles.loginHint}>
                {t('joinPage.loginNote')}
              </p>
            </>
          ) : (
            <>
              <button
                style={styles.primaryButton}
                onClick={joinRoom}
              >
                {t('joinPage.joinRoom')}
              </button>
              {userEmail && (
                <p style={styles.loginNote}>
                  {t('joinPage.joiningAs')} {userEmail}
                </p>
              )}
            </>
          )}
        </div>

        {roomInfo && (
          <div style={styles.roomInfo}>
            <div style={styles.roomInfoRow}>
              <span style={styles.infoLabel}>{t('joinPage.room')}:</span>
              <code style={styles.infoValue}>{roomInfo.room_code}</code>
            </div>
            {roomInfo.max_participants && (
              <div style={styles.roomInfoRow}>
                <span style={styles.infoLabel}>{t('joinPage.maxParticipants')}:</span>
                <span style={styles.infoValue}>{roomInfo.max_participants}</span>
              </div>
            )}
          </div>
        )}
        </div>
      </div>
      <Footer />
    </div>
  );
}

const styles = {
  container: {
    minHeight: "100vh",
    background: "#0a0a0a",
    color: "white",
    fontFamily: "system-ui, -apple-system, sans-serif",
    display: "flex",
    flexDirection: "column"
  },
  content: {
    flex: 1,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "1rem 1rem 0.5rem 1rem"
  },
  card: {
    background: "#1a1a1a",
    borderRadius: "16px",
    border: "1px solid #333",
    padding: "2rem",
    maxWidth: "500px",
    width: "100%",
    boxShadow: "0 20px 60px rgba(0,0,0,0.5)"
  },
  header: {
    textAlign: "center",
    marginBottom: "2rem"
  },
  checkIcon: {
    fontSize: "3rem",
    marginBottom: "1rem",
    color: "#10b981"
  },
  errorIcon: {
    fontSize: "3rem",
    marginBottom: "1rem",
    textAlign: "center"
  },
  title: {
    fontSize: "1.75rem",
    margin: "0 0 0.5rem 0",
    fontWeight: "700"
  },
  subtitle: {
    color: "#999",
    fontSize: "1rem",
    margin: 0
  },
  form: {
    display: "flex",
    flexDirection: "column",
    gap: "1.5rem"
  },
  formGroup: {
    display: "flex",
    flexDirection: "column",
    gap: "0.5rem"
  },
  label: {
    fontSize: "0.9rem",
    fontWeight: "600",
    color: "#ccc"
  },
  input: {
    padding: "0.875rem",
    background: "#2a2a2a",
    border: "1px solid #444",
    borderRadius: "8px",
    color: "white",
    fontSize: "1rem",
    outline: "none",
    transition: "border-color 0.2s"
  },
  select: {
    padding: "0.875rem",
    background: "#2a2a2a",
    border: "1px solid #444",
    borderRadius: "8px",
    color: "white",
    fontSize: "1rem",
    outline: "none",
    cursor: "pointer"
  },
  hint: {
    fontSize: "0.8rem",
    color: "#666",
    margin: 0
  },
  primaryButton: {
    width: "100%",
    padding: "1rem 1.5rem",
    background: "#3b82f6",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "1rem",
    transition: "background 0.2s"
  },
  linkButton: {
    background: "none",
    border: "none",
    color: "#3b82f6",
    cursor: "pointer",
    fontSize: "inherit",
    textDecoration: "underline",
    padding: 0
  },
  secondaryButton: {
    width: "100%",
    padding: "1rem 1.5rem",
    background: "#2a2a2a",
    color: "white",
    border: "1px solid #444",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "1rem",
    transition: "all 0.2s"
  },
  loginNote: {
    fontSize: "0.85rem",
    color: "#666",
    textAlign: "center",
    margin: "0.5rem 0 0 0"
  },
  guestHint: {
    fontSize: "0.85rem",
    color: "#999",
    textAlign: "center",
    margin: "0.5rem 0 1rem 0"
  },
  loginHint: {
    fontSize: "0.85rem",
    color: "#999",
    textAlign: "center",
    margin: "0.5rem 0 0 0"
  },
  divider: {
    display: "flex",
    alignItems: "center",
    textAlign: "center",
    margin: "1rem 0"
  },
  dividerText: {
    flex: 1,
    color: "#666",
    fontSize: "0.85rem",
    position: "relative",
    padding: "0 1rem",
    "&::before": {
      content: '""',
      position: "absolute",
      left: 0,
      right: "50%",
      height: "1px",
      background: "#444"
    }
  },
  roomInfo: {
    background: "#2a2a2a",
    borderRadius: "8px",
    padding: "1rem",
    marginTop: "1.5rem",
    border: "1px solid #444"
  },
  roomInfoRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "0.5rem 0"
  },
  infoLabel: {
    color: "#999",
    fontSize: "0.9rem"
  },
  infoValue: {
    color: "#3b82f6",
    fontSize: "0.9rem",
    fontFamily: "monospace",
    fontWeight: "600"
  },
  errorText: {
    color: "#ef4444",
    textAlign: "center",
    marginBottom: "1.5rem"
  },
  loadingSpinner: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "1rem",
    padding: "2rem"
  },
  spinner: {
    width: "50px",
    height: "50px",
    border: "4px solid #333",
    borderTop: "4px solid #3b82f6",
    borderRadius: "50%",
    animation: "spin 1s linear infinite"
  },
  loadingText: {
    color: "#999",
    margin: 0
  }
};
