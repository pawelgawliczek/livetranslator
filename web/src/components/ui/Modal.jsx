import React, { useEffect } from "react";

/**
 * Modal component - Overlay dialog for displaying content
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether modal is visible
 * @param {Function} props.onClose - Handler for closing modal
 * @param {React.ReactNode} props.children - Modal content
 * @param {string} props.title - Optional modal title
 * @param {string} props.className - Additional CSS classes for modal content
 * @param {boolean} props.closeOnBackdrop - Whether clicking backdrop closes modal (default: true)
 */
export default function Modal({
  isOpen,
  onClose,
  children,
  title,
  className = "",
  closeOnBackdrop = true,
  ...props
}) {
  // Handle ESC key to close modal
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === "Escape" && isOpen && onClose) {
        onClose();
      }
    };

    document.addEventListener("keydown", handleEscape);
    return () => document.removeEventListener("keydown", handleEscape);
  }, [isOpen, onClose]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }

    return () => {
      document.body.style.overflow = "";
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div
      className="modal-backdrop"
      onClick={closeOnBackdrop ? onClose : undefined}
      role="dialog"
      aria-modal="true"
      aria-labelledby={title ? "modal-title" : undefined}
    >
      <div
        className={`modal ${className}`}
        onClick={(e) => e.stopPropagation()}
        {...props}
      >
        {title && (
          <div className="mb-4 flex items-center justify-between">
            <h3 id="modal-title" className="text-2xl font-semibold">
              {title}
            </h3>
            {onClose && (
              <button
                onClick={onClose}
                className="text-muted hover:text-fg transition-colors p-1 rounded-md hover:bg-bg"
                aria-label="Close modal"
              >
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="24"
                  height="24"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <line x1="18" y1="6" x2="6" y2="18"></line>
                  <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
              </button>
            )}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
