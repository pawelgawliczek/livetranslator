import React from "react";

export default function Footer() {
  return (
    <footer
      style={{
        padding: "0.5rem",
        textAlign: "center",
        fontSize: "0.65rem",
        color: "#555",
        marginTop: "auto",
        flexShrink: 0,
      }}
    >
      Created by{" "}
      <a
        href="https://pawelgawliczek.cloud/"
        target="_blank"
        rel="noopener noreferrer"
        style={{
          color: "#667eea",
          textDecoration: "none",
        }}
      >
        Pawel Gawliczek
      </a>{" "}
      @ 2025
    </footer>
  );
}
