import React from "react";
import { useNavigate } from "react-router-dom";

export default function LandingPage() {
  const navigate = useNavigate();
  
  return (
    <div style={{
      minHeight: "100vh",
      height: "100vh",
      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif",
      padding: "2rem",
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      overflow: "auto"
    }}>
      <h1 style={{
        fontSize: "clamp(2.5rem, 8vw, 4rem)",
        fontWeight: "bold",
        marginBottom: "1rem",
        textAlign: "center"
      }}>
        LiveTranslator
      </h1>
      
      <p style={{
        fontSize: "clamp(1rem, 3vw, 1.5rem)",
        color: "rgba(255,255,255,0.9)",
        marginBottom: "3rem",
        textAlign: "center",
        maxWidth: "600px"
      }}>
        Real-time multilingual speech collaboration platform
      </p>
      
      <div style={{
        display: "flex",
        flexDirection: "column",
        gap: "1rem",
        width: "100%",
        maxWidth: "400px",
        marginBottom: "3rem"
      }}>
        <button
          onClick={() => navigate("/login")}
          style={{
            padding: "1rem 2rem",
            fontSize: "1.1rem",
            background: "#3b82f6",
            color: "white",
            border: "none",
            borderRadius: "12px",
            cursor: "pointer",
            fontWeight: "600",
            width: "100%"
          }}
        >
          Sign In
        </button>
        
        <button
          onClick={() => navigate("/signup")}
          style={{
            padding: "1rem 2rem",
            fontSize: "1.1rem",
            background: "rgba(255,255,255,0.2)",
            color: "white",
            border: "2px solid white",
            borderRadius: "12px",
            cursor: "pointer",
            fontWeight: "600",
            width: "100%"
          }}
        >
          Create Account
        </button>
      </div>
      
      <div style={{
        display: "grid",
        gridTemplateColumns: "1fr",
        gap: "1.5rem",
        maxWidth: "600px",
        marginTop: "2rem"
      }}>
        <div style={{textAlign: "center"}}>
          <h3 style={{fontSize: "1.25rem", marginBottom: "0.5rem"}}>🎤 Real-time Translation</h3>
          <p style={{color: "rgba(255,255,255,0.8)", fontSize: "0.95rem"}}>
            Instant speech-to-text and machine translation
          </p>
        </div>
        
        <div style={{textAlign: "center"}}>
          <h3 style={{fontSize: "1.25rem", marginBottom: "0.5rem"}}>🌍 Multi-language Support</h3>
          <p style={{color: "rgba(255,255,255,0.8)", fontSize: "0.95rem"}}>
            Collaborate across language barriers
          </p>
        </div>
        
        <div style={{textAlign: "center"}}>
          <h3 style={{fontSize: "1.25rem", marginBottom: "0.5rem"}}>📱 Cross-platform</h3>
          <p style={{color: "rgba(255,255,255,0.8)", fontSize: "0.95rem"}}>
            Works on desktop, tablet, and mobile
          </p>
        </div>
      </div>
    </div>
  );
}
