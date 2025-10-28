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
      colorClass: "text-yellow-500"
    }] : []),
    {
      icon: "👤",
      label: t('common.profile'),
      onClick: onProfileClick,
      colorClass: "text-accent"
    },
    {
      icon: "🚪",
      label: t('common.logout'),
      onClick: onLogout,
      colorClass: "text-red-500"
    }
  ];

  return (
    <div
      className="fixed inset-0 bg-black/85 z-[1000] flex items-start justify-end p-2 pt-[max(3.5rem,calc(env(safe-area-inset-top)+3.5rem))]"
      onClick={onClose}
    >
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
                item.onClick();
                onClose();
              }}
              className={`w-full px-4 py-3.5 bg-transparent border-none cursor-pointer flex items-center gap-3 text-base transition-colors hover:bg-bg-secondary ${item.colorClass}`}
            >
              <span className="text-xl w-6 text-center">
                {item.icon}
              </span>
              <span className="flex-1 text-left">
                {item.label}
              </span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
