import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";

export default function ParticipantsModal({ roomCode, token, isOpen, onClose }) {
  const { t } = useTranslation();
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isOpen || !roomCode) return;

    fetchParticipants();
    // Refresh participants every 5 seconds while modal is open
    const interval = setInterval(fetchParticipants, 5000);

    return () => clearInterval(interval);
  }, [isOpen, roomCode]);

  async function fetchParticipants() {
    try {
      setLoading(true);
      const headers = token ? { "Authorization": `Bearer ${token}` } : {};
      const guestToken = sessionStorage.getItem('guest_token');
      if (guestToken && !token) {
        headers["Authorization"] = `Bearer ${guestToken}`;
      }

      const response = await fetch(`/api/rooms/${roomCode}/participants`, {
        headers
      });

      if (!response.ok) {
        throw new Error("Failed to fetch participants");
      }

      const data = await response.json();
      setParticipants(data.participants || []);
    } catch (e) {
      console.error("Failed to fetch participants:", e);
    } finally {
      setLoading(false);
    }
  }

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal max-w-2xl max-h-[80vh] flex flex-col" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex justify-between items-center p-6 border-b border-border">
          <h2 className="m-0 text-2xl font-bold text-fg">
            👥 {t('participants.connectedTitle')}
          </h2>
          <button
            onClick={onClose}
            className="bg-transparent border-none text-muted text-4xl cursor-pointer p-0 w-10 h-10
                       flex items-center justify-center rounded-lg hover:bg-bg-secondary transition-all"
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-6">
          {loading && participants.length === 0 ? (
            <div className="flex flex-col items-center gap-4 py-12 px-4">
              <div className="w-12 h-12 border-4 border-border border-t-accent rounded-full animate-spin"></div>
              <p className="text-muted m-0">{t('participants.loadingParticipants')}</p>
            </div>
          ) : participants.length === 0 ? (
            <div className="text-center py-12 px-4">
              <p className="text-muted text-base m-0">{t('participants.emptyState')}</p>
            </div>
          ) : (
            <div className="flex flex-col gap-3">
              {participants.map((participant, index) => (
                <div
                  key={index}
                  className="bg-bg-secondary border border-border rounded-xl p-4 flex justify-between items-center
                             transition-all hover:border-accent"
                >
                  <div className="flex-1">
                    <div className="text-fg text-base font-semibold mb-2 flex items-center gap-2">
                      {participant.is_guest && (
                        <span className="bg-accent text-accent-fg text-[0.65rem] font-bold px-2 py-1 rounded uppercase">
                          {t('participants.guestLabel')}
                        </span>
                      )}
                      {participant.display_name || participant.email}
                    </div>
                    <div className="flex flex-col gap-1">
                      <span className="text-muted text-sm">
                        🗣️ {getLanguageName(participant.preferred_lang || "en")}
                      </span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {participant.is_speaking ? (
                      <span className="bg-green-500 text-white text-xs font-semibold px-3 py-1.5 rounded-md animate-pulse">
                        🎤 {t('participants.speaking')}
                      </span>
                    ) : (
                      <span className="text-green-500 text-sm font-semibold">
                        ✓ {t('participants.connected')}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-4 border-t border-border bg-bg-secondary">
          <p className="m-0 text-muted text-sm text-center">
            {participants.length} participant{participants.length !== 1 ? 's' : ''} connected
          </p>
        </div>
      </div>
    </div>
  );
}

function getLanguageName(code) {
  const languages = {
    "auto": "Auto",
    "en": "English",
    "pl": "Polish",
    "ar": "Arabic",
    "es": "Spanish",
    "fr": "French",
    "de": "German"
  };
  // Normalize language code to base language (e.g., "en-GB" -> "en")
  const baseLang = code?.split('-')[0] || code;
  return languages[baseLang] || code.toUpperCase();
}
