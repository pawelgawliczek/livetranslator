import React from "react";

/**
 * TagPill component - Small badge/label for displaying metadata
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Tag content
 * @param {string} props.className - Additional CSS classes
 * @param {"default"|"success"|"warning"|"error"|"purple"|"blue"} props.variant - Color variant
 */
export default function TagPill({ children, className = "", variant = "default", ...props }) {
  const variantClasses = {
    default: "bg-accent/10 text-accent border-accent/20",
    success: "bg-green-500/10 text-green-600 border-green-500/20",
    warning: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    error: "bg-red-500/10 text-red-600 border-red-500/20",
    purple: "bg-purple-500/10 text-purple-600 border-purple-500/20",
    blue: "bg-blue-500/10 text-blue-600 border-blue-500/20",
  };

  return (
    <span
      className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${variantClasses[variant]} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}
