import React, { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";

export default function LandingPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  
  // Check for token in URL (from Google OAuth redirect)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    if (token) {
      // Redirect to login page with token
      navigate(`/login?token=${token}`);
    }
  }, [location, navigate]);
  
  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #667eea 0%, #764ba2 100%)",
      display: "flex",
      flexDirection: "column",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif"
    }}>
      <div style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "0.5rem 1.25rem 0.5rem 1.25rem",
        maxWidth: "1200px",
        margin: "0 auto",
        width: "100%",
        boxSizing: "border-box"
      }}>
        {/* Main Title */}
        <div style={{
          background: "rgba(255,255,255,0.15)",
          padding: "0.35rem 0.9rem",
          borderRadius: "50px",
          marginBottom: "0.5rem",
          fontSize: "0.75rem",
          fontWeight: "600",
          backdropFilter: "blur(10px)",
          maxWidth: "100%",
          boxSizing: "border-box"
        }}>
          🌍 Real-time Translation Platform
        </div>

        <h1 style={{
          fontSize: "clamp(1.8rem, 8vw, 4rem)",
          fontWeight: "bold",
          marginBottom: "0.4rem",
          textAlign: "center",
          lineHeight: "1.1",
          width: "100%",
          boxSizing: "border-box"
        }}>
          {t('landing.title')}
        </h1>

        <p style={{
          fontSize: "clamp(0.9rem, 3vw, 1.5rem)",
          marginBottom: "0.75rem",
          textAlign: "center",
          maxWidth: "100%",
          lineHeight: "1.3",
          boxSizing: "border-box"
        }}>
          {t('landing.subtitle')}
        </p>

        {/* Features - Compact single column */}
        <div style={{
          display: "flex",
          flexDirection: "column",
          gap: "0.4rem",
          width: "100%",
          maxWidth: "100%",
          marginBottom: "0.6rem"
        }}>
          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "0.6rem 0.75rem",
            borderRadius: "8px",
            backdropFilter: "blur(10px)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.35rem",
            boxSizing: "border-box",
            textAlign: "center"
          }}>
            <div style={{fontSize: "1.4rem", lineHeight: 1}}>🗣️</div>
            <div>
              <h3 style={{fontSize: "0.85rem", fontWeight: "600", marginBottom: "0.1rem", margin: 0}}>
                Real-time Speech
              </h3>
              <p style={{fontSize: "0.7rem", opacity: 0.9, lineHeight: "1.2", margin: 0}}>
                Instant translation
              </p>
            </div>
          </div>

          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "0.6rem 0.75rem",
            borderRadius: "8px",
            backdropFilter: "blur(10px)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.35rem",
            boxSizing: "border-box",
            textAlign: "center"
          }}>
            <div style={{fontSize: "1.4rem", lineHeight: 1}}>🌐</div>
            <div>
              <h3 style={{fontSize: "0.85rem", fontWeight: "600", marginBottom: "0.1rem", margin: 0}}>
                12+ Languages
              </h3>
              <p style={{fontSize: "0.7rem", opacity: 0.9, lineHeight: "1.2", margin: 0}}>
                Worldwide support
              </p>
            </div>
          </div>

          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "0.6rem 0.75rem",
            borderRadius: "8px",
            backdropFilter: "blur(10px)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.35rem",
            boxSizing: "border-box",
            textAlign: "center"
          }}>
            <div style={{fontSize: "1.4rem", lineHeight: 1}}>👥</div>
            <div>
              <h3 style={{fontSize: "0.85rem", fontWeight: "600", marginBottom: "0.1rem", margin: 0}}>
                Multi-participant
              </h3>
              <p style={{fontSize: "0.7rem", opacity: 0.9, lineHeight: "1.2", margin: 0}}>
                Connect anyone
              </p>
            </div>
          </div>
        </div>

        {/* CTA Buttons */}
        <div style={{
          display: "flex",
          gap: "0.6rem",
          flexWrap: "wrap",
          justifyContent: "center",
          marginBottom: "0.6rem",
          width: "100%",
          boxSizing: "border-box"
        }}>
          <button
            onClick={() => navigate("/login")}
            style={{
              padding: "0.75rem 1.3rem",
              background: "white",
              color: "#667eea",
              border: "none",
              borderRadius: "10px",
              fontSize: "0.95rem",
              fontWeight: "600",
              cursor: "pointer",
              flex: "1 1 130px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)",
              boxSizing: "border-box"
            }}
          >
            {t('landing.signIn')}
          </button>

          <button
            onClick={() => navigate("/signup")}
            style={{
              padding: "0.75rem 1.3rem",
              background: "rgba(255,255,255,0.2)",
              color: "white",
              border: "2px solid white",
              borderRadius: "10px",
              fontSize: "0.95rem",
              fontWeight: "600",
              cursor: "pointer",
              flex: "1 1 130px",
              boxSizing: "border-box"
            }}
          >
            {t('landing.createAccount')}
          </button>
        </div>

        {/* Creator Info */}
        <div style={{
          marginTop: "0.25rem",
          fontSize: "0.75rem",
          opacity: 0.9,
          textAlign: "center"
        }}>
          Created by{" "}
          <a
            href="https://pawelgawliczek.cloud/"
            target="_blank"
            rel="noopener noreferrer"
            style={{
              color: "white",
              textDecoration: "underline",
              fontWeight: "600"
            }}
          >
            Pawel Gawliczek
          </a>
        </div>
      </div>
      <Footer />
    </div>
  );
}
