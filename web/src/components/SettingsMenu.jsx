import React, { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";

export default function SettingsMenu({
  isOpen,
  onClose,
  isGuest,
  myLanguage,
  languages,
  onLanguageChange,
  onShowParticipants,
  onShowInvite,
  onShowCosts,
  onShowSound,
  onLogout,
  canChangeLanguage = true,
  persistenceEnabled = false,
  onTogglePersistence,
  isRoomAdmin = false,
  isPublic = false,
  onTogglePublic,
  onShowRoomAdminSettings
}) {
  const { t } = useTranslation();
  const [isDarkMode, setIsDarkMode] = useState(false);

  // Initialize theme from localStorage or current setting
  useEffect(() => {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
    setIsDarkMode(currentTheme === "dark");
  }, [isOpen]);

  const toggleTheme = () => {
    const newTheme = isDarkMode ? "light" : "dark";
    setIsDarkMode(!isDarkMode);
    document.documentElement.setAttribute("data-theme", newTheme);
    localStorage.setItem("theme", newTheme);
  };

  if (!isOpen) return null;

  // Debug logging
  console.log('[SettingsMenu] Props:', { isGuest, isRoomAdmin, isPublic, persistenceEnabled });

  // Don't allow closing if no language is selected
  const canClose = !!myLanguage;

  const handleClose = () => {
    if (canClose) {
      onClose();
    } else {
      console.log('[Settings] Cannot close - language must be selected first');
    }
  };

  const menuItems = [
    {
      icon: "🌐",
      label: t('settings.myLanguage'),
      value: myLanguage ? (languages.find(l => l.code === myLanguage)?.name || "English") : t('settings.selectLanguage'),
      onClick: onLanguageChange,
      hasSubMenu: true,
      disabled: !canChangeLanguage
    },
    {
      icon: "👥",
      label: t('settings.participants'),
      onClick: onShowParticipants
    },
    {
      icon: "✉️",
      label: t('settings.invite'),
      onClick: onShowInvite
    },
    {
      icon: "💰",
      label: t('settings.costs'),
      onClick: onShowCosts
    },
    {
      icon: "🎙️",
      label: t('settings.soundSettings'),
      onClick: onShowSound
    },
    {
      icon: isDarkMode ? "🌙" : "☀️",
      label: isDarkMode ? "Dark Mode" : "Light Mode",
      onClick: toggleTheme,
      isToggle: true,
      toggleValue: isDarkMode
    },
    // Only show persistence toggle for logged-in users
    ...(!isGuest ? [{
      icon: "💾",
      label: t('settings.saveHistory'),
      onClick: onTogglePersistence,
      isToggle: true,
      toggleValue: persistenceEnabled
    }] : []),
    // Only show public/private toggle for room admins
    ...(isRoomAdmin ? [{
      icon: isPublic ? "🌍" : "🔒",
      label: isPublic ? t('settings.publicRoom') : t('settings.privateRoom'),
      onClick: onTogglePublic,
      isToggle: true,
      toggleValue: isPublic
    }] : []),
    // Only show Room Admin Settings for room admins (and not guests)
    ...(!isGuest && isRoomAdmin && onShowRoomAdminSettings ? [{
      icon: "⚙️",
      label: t('settings.roomAdminSettings'),
      onClick: onShowRoomAdminSettings
    }] : []),
    {
      icon: isGuest ? "🔑" : "🚪",
      label: isGuest ? t('settings.signIn') : t('settings.signOut'),
      onClick: isGuest ? () => window.location.href = "/login" : onLogout,
      color: isGuest ? "#3b82f6" : "#ef4444"
    }
  ];

  return (
    <div
      className="fixed inset-0 bg-black/85 z-[1000] flex items-start justify-end p-2 pt-[max(3.5rem,calc(env(safe-area-inset-top)+3.5rem))]"
      onClick={handleClose}
    >
      {!canClose && (
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-red-500 text-white px-6 py-4 rounded-lg text-sm font-medium pointer-events-none opacity-0 animate-fadeIn">
          Please select a language first
        </div>
      )}
      <div
        className="bg-card border border-border rounded-xl min-w-[280px] max-w-[320px] overflow-hidden shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Menu Items */}
        <div className="py-2">
          {menuItems.map((item, index) => (
            <button
              key={index}
              onClick={() => {
                if (item.disabled) return;
                item.onClick();
                if (!item.hasSubMenu) {
                  handleClose();
                }
              }}
              disabled={item.disabled}
              className={`w-full px-4 py-3.5 bg-transparent border-none ${
                item.color ? '' : 'text-fg'
              } cursor-pointer flex items-center gap-3 text-base transition-colors hover:bg-bg-secondary disabled:opacity-50 disabled:cursor-not-allowed`}
              style={item.color ? { color: item.color } : {}}
            >
              <span className="text-xl w-6 text-center">
                {item.icon}
              </span>
              <span className="flex-1 text-left">
                {item.label}
              </span>
              {item.value && (
                <span className="text-sm text-muted">
                  {item.value}
                </span>
              )}
              {item.isToggle && (
                <div
                  className={`w-11 h-6 rounded-full relative transition-colors cursor-pointer ${
                    item.toggleValue ? 'bg-green-500' : 'bg-border'
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    item.onClick();
                  }}
                >
                  <div
                    className={`w-5 h-5 rounded-full bg-white absolute top-0.5 transition-all ${
                      item.toggleValue ? 'left-[22px]' : 'left-0.5'
                    }`}
                  />
                </div>
              )}
              {item.hasSubMenu && (
                <span className="text-muted">›</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
