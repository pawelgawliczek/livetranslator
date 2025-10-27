import React from "react";
import { useTranslation } from "react-i18next";

export default function RoomsMenu({
  isOpen,
  onClose,
  isAdmin,
  onAdminClick,
  onProfileClick,
  onLogout
}) {
  const { t } = useTranslation();
  if (!isOpen) return null;

  const menuItems = [
    ...(isAdmin ? [{
      icon: "🛠️",
      label: t('common.admin'),
      onClick: onAdminClick,
      color: "#f59e0b"
    }] : []),
    {
      icon: "👤",
      label: t('common.profile'),
      onClick: onProfileClick,
      color: "#6366f1"
    },
    {
      icon: "🚪",
      label: t('common.logout'),
      onClick: onLogout,
      color: "#ef4444"
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
      onClick={onClose}
    >
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
                item.onClick();
                onClose();
              }}
              style={{
                width: "100%",
                padding: "0.875rem 1rem",
                background: "transparent",
                border: "none",
                color: item.color || "white",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: "0.75rem",
                fontSize: "0.95rem",
                transition: "background 0.15s"
              }}
              onMouseOver={(e) => e.currentTarget.style.background = "#2a2a2a"}
              onMouseOut={(e) => e.currentTarget.style.background = "transparent"}
            >
              <span style={{ fontSize: "1.25rem", width: "24px", textAlign: "center" }}>
                {item.icon}
              </span>
              <span style={{ flex: 1, textAlign: "left" }}>
                {item.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
