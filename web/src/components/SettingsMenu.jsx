import React from "react";

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
  onLogout,
  canChangeLanguage = true,
  persistenceEnabled = false,
  onTogglePersistence,
  isRoomAdmin = false,
  isPublic = false,
  onTogglePublic,
  onShowRoomAdminSettings
}) {
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
      label: "My Language",
      value: myLanguage ? (languages.find(l => l.code === myLanguage)?.name || "English") : "Select...",
      onClick: onLanguageChange,
      hasSubMenu: true,
      disabled: !canChangeLanguage
    },
    {
      icon: "👥",
      label: "Participants",
      onClick: onShowParticipants
    },
    {
      icon: "✉️",
      label: "Invite",
      onClick: onShowInvite
    },
    {
      icon: "💰",
      label: "Costs",
      onClick: onShowCosts
    },
    // Only show persistence toggle for logged-in users
    ...(!isGuest ? [{
      icon: "💾",
      label: "Save History",
      onClick: onTogglePersistence,
      isToggle: true,
      toggleValue: persistenceEnabled
    }] : []),
    // Only show public/private toggle for room admins
    ...(isRoomAdmin ? [{
      icon: isPublic ? "🌍" : "🔒",
      label: isPublic ? "Public Room" : "Private Room",
      onClick: onTogglePublic,
      isToggle: true,
      toggleValue: isPublic
    }] : []),
    // Only show Room Admin Settings for room admins (and not guests)
    ...(!isGuest && isRoomAdmin && onShowRoomAdminSettings ? [{
      icon: "⚙️",
      label: "Room Admin Settings",
      onClick: onShowRoomAdminSettings
    }] : []),
    {
      icon: isGuest ? "🔑" : "🚪",
      label: isGuest ? "Sign In" : "Sign Out",
      onClick: isGuest ? () => window.location.href = "/login" : onLogout,
      color: isGuest ? "#3b82f6" : "#ef4444"
    }
  ];

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0,0,0,0.85)",
        zIndex: 1000,
        display: "flex",
        alignItems: "flex-start",
        justifyContent: "flex-end",
        padding: "0.5rem",
        paddingTop: "max(3.5rem, calc(env(safe-area-inset-top) + 3.5rem))"
      }}
      onClick={handleClose}
    >
      {!canClose && (
        <div style={{
          position: "absolute",
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
          background: "#ef4444",
          color: "white",
          padding: "1rem 1.5rem",
          borderRadius: "8px",
          fontSize: "0.9rem",
          fontWeight: "500",
          pointerEvents: "none",
          opacity: 0,
          animation: "fadeIn 0.3s forwards"
        }}>
          Please select a language first
        </div>
      )}
      <div
        style={{
          background: "#1a1a1a",
          borderRadius: "12px",
          border: "1px solid #333",
          minWidth: "280px",
          maxWidth: "320px",
          overflow: "hidden",
          boxShadow: "0 4px 12px rgba(0,0,0,0.5)"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Menu Items */}
        <div style={{ padding: "0.5rem 0" }}>
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
              style={{
                width: "100%",
                padding: "0.875rem 1rem",
                background: "transparent",
                border: "none",
                color: item.color || "white",
                cursor: item.disabled ? "not-allowed" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                fontSize: "0.95rem",
                transition: "background 0.15s",
                opacity: item.disabled ? 0.5 : 1
              }}
              onMouseOver={(e) => !item.disabled && (e.currentTarget.style.background = "#2a2a2a")}
              onMouseOut={(e) => e.currentTarget.style.background = "transparent"}
            >
              <span style={{ fontSize: "1.25rem", width: "24px", textAlign: "center" }}>
                {item.icon}
              </span>
              <span style={{ flex: 1, textAlign: "left" }}>
                {item.label}
              </span>
              {item.value && (
                <span style={{ fontSize: "0.85rem", color: "#999" }}>
                  {item.value}
                </span>
              )}
              {item.isToggle && (
                <div
                  style={{
                    width: "44px",
                    height: "24px",
                    borderRadius: "12px",
                    background: item.toggleValue ? "#22c55e" : "#444",
                    position: "relative",
                    transition: "background 0.2s",
                    cursor: "pointer"
                  }}
                  onClick={(e) => {
                    e.stopPropagation();
                    item.onClick();
                  }}
                >
                  <div
                    style={{
                      width: "20px",
                      height: "20px",
                      borderRadius: "50%",
                      background: "white",
                      position: "absolute",
                      top: "2px",
                      left: item.toggleValue ? "22px" : "2px",
                      transition: "left 0.2s"
                    }}
                  />
                </div>
              )}
              {item.hasSubMenu && (
                <span style={{ color: "#666" }}>›</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
