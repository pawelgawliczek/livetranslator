import React from "react";

export default function Footer() {
  return (
    <footer className="p-2 text-center text-xs text-muted mt-auto flex-shrink-0">
      Created by{" "}
      <a
        href="https://pawelgawliczek.cloud/"
        target="_blank"
        rel="noopener noreferrer"
        className="text-accent hover:text-accent-dark font-semibold transition-colors no-underline"
      >
        Pawel Gawliczek
      </a>{" "}
      @ 2025
    </footer>
  );
}
