import React from "react";

/**
 * Card component - A surface for displaying content with elevation
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Content to display inside the card
 * @param {string} props.className - Additional CSS classes
 * @param {Function} props.onClick - Optional click handler
 * @param {boolean} props.hoverable - Whether to show hover effects
 */
export default function Card({ children, className = "", onClick, hoverable = false, ...props }) {
  const baseClasses = "bg-card border border-border rounded-lg shadow-md p-6 transition-all";
  const hoverClasses = hoverable ? "hover:shadow-lg hover:scale-[1.02] cursor-pointer" : "";

  return (
    <div
      className={`${baseClasses} ${hoverClasses} ${className}`}
      onClick={onClick}
      {...props}
    >
      {children}
    </div>
  );
}
