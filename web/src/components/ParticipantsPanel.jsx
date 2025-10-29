import React from "react";
import { useTranslation } from "react-i18next";

/**
 * Collapsible sidebar showing active participants.
 *
 * Features:
 * - Shows all active participants with language flags
 * - Displays user names and languages
 * - Guest indicator
 * - Slide-in/out animation
 */
export default function ParticipantsPanel({
  participants,
  languages,
  isOpen,
  onToggle,
}) {
  const { t } = useTranslation();
  return (
    <>
      {/* Sidebar Panel */}
      <div
        className={`fixed right-0 top-0 h-screen w-[min(300px,85vw)] max-w-[300px] bg-card border-l border-border
                    transition-transform duration-300 ease-in-out z-[1001] flex flex-col shadow-2xl
                    ${isOpen ? "translate-x-0" : "translate-x-full"}`}
      >
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-border">
          <h3 className="m-0 text-lg font-semibold text-fg">
            {t('participants.panelTitle')} ({participants.length})
          </h3>
          <button
            onClick={onToggle}
            className="bg-transparent border-none text-muted text-2xl cursor-pointer p-1 leading-none
                       hover:text-fg transition-colors"
          >
            ✕
          </button>
        </div>

        {/* Participants List */}
        <div className="flex-1 overflow-y-auto p-2">
          {participants.length === 0 ? (
            <div className="py-8 px-4 text-center text-muted text-sm">
              {t('participants.empty')}
            </div>
          ) : (
            participants.map((p) => {
              // Normalize language code to base language (e.g., "en-GB" -> "en")
              const baseLang = p.language?.split('-')[0] || p.language;
              const lang = languages.find((l) => l.code === baseLang);
              return (
                <div
                  key={p.user_id}
                  className="p-3 rounded-lg mb-2 transition-colors hover:bg-bg-secondary cursor-default"
                >
                  <div className="flex items-center gap-3">
                    <span className="text-2xl flex-shrink-0">{lang?.flag || "🌐"}</span>
                    <div className="flex flex-col gap-1 min-w-0 flex-1">
                      <span className="text-fg text-[0.95rem] font-medium overflow-hidden text-ellipsis whitespace-nowrap">
                        {p.display_name}
                        {p.is_guest && (
                          <span className="ml-2 text-muted text-xs font-normal">
                            {t('participants.guestLabel')}
                          </span>
                        )}
                      </span>
                      <span className="text-muted text-[0.85rem]">
                        {lang?.name || p.language}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Overlay when panel is open */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-[1000]"
          onClick={onToggle}
        />
      )}
    </>
  );
}
