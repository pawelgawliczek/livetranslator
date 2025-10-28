import React from "react";

/**
 * Button component - Styled button with variants
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Button content
 * @param {"primary"|"secondary"|"ghost"} props.variant - Button style variant
 * @param {string} props.className - Additional CSS classes
 * @param {boolean} props.disabled - Whether button is disabled
 * @param {Function} props.onClick - Click handler
 * @param {string} props.type - Button type (button, submit, reset)
 */
export default function Button({
  children,
  variant = "primary",
  className = "",
  disabled = false,
  onClick,
  type = "button",
  ...props
}) {
  const variantClasses = {
    primary: "btn-primary",
    secondary: "btn-secondary",
    ghost: "btn-ghost",
  };

  return (
    <button
      type={type}
      className={`${variantClasses[variant]} ${className}`}
      disabled={disabled}
      onClick={onClick}
      {...props}
    >
      {children}
    </button>
  );
}
