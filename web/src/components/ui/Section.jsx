import React from "react";

/**
 * Section component - Container for page sections with consistent styling
 *
 * @param {Object} props
 * @param {React.ReactNode} props.children - Section content
 * @param {string} props.className - Additional CSS classes
 * @param {string} props.maxWidth - Max width variant (sm, md, lg, xl)
 */
export default function Section({ children, className = "", maxWidth = "lg", ...props }) {
  const maxWidthClasses = {
    sm: "max-w-container-sm",
    md: "max-w-container-md",
    lg: "max-w-container-lg",
    xl: "max-w-container-xl",
  };

  return (
    <section
      className={`bg-card rounded-xl p-8 ${maxWidthClasses[maxWidth]} mx-auto ${className}`}
      {...props}
    >
      {children}
    </section>
  );
}
