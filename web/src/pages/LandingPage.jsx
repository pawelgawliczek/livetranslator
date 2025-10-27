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
        padding: "1rem 1rem 0.5rem 1rem",
        maxWidth: "1200px",
        margin: "0 auto",
        width: "100%"
      }}>
        {/* Main Title */}
        <div style={{
          background: "rgba(255,255,255,0.15)",
          padding: "0.4rem 1rem",
          borderRadius: "50px",
          marginBottom: "0.75rem",
          fontSize: "0.8rem",
          fontWeight: "600",
          backdropFilter: "blur(10px)"
        }}>
          🌍 Real-time Translation Platform
        </div>

        <h1 style={{
          fontSize: "clamp(2rem, 8vw, 4rem)",
          fontWeight: "bold",
          marginBottom: "0.5rem",
          textAlign: "center",
          lineHeight: "1.1"
        }}>
          {t('landing.title')}
        </h1>

        <p style={{
          fontSize: "clamp(0.95rem, 3vw, 1.5rem)",
          marginBottom: "1rem",
          textAlign: "center",
          maxWidth: "700px",
          lineHeight: "1.4"
        }}>
          {t('landing.subtitle')}
        </p>

        {/* Features Grid - Compact for mobile */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: "0.75rem",
          width: "100%",
          maxWidth: "900px",
          marginBottom: "1.25rem"
        }}>
          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "0.75rem",
            borderRadius: "10px",
            textAlign: "center",
            backdropFilter: "blur(10px)"
          }}>
            <div style={{fontSize: "1.75rem", marginBottom: "0.25rem"}}>🗣️</div>
            <h3 style={{fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.25rem"}}>
              Real-time Speech
            </h3>
            <p style={{fontSize: "0.75rem", opacity: 0.9, lineHeight: "1.3"}}>
              Instant translation
            </p>
          </div>

          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "0.75rem",
            borderRadius: "10px",
            textAlign: "center",
            backdropFilter: "blur(10px)"
          }}>
            <div style={{fontSize: "1.75rem", marginBottom: "0.25rem"}}>🌐</div>
            <h3 style={{fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.25rem"}}>
              12+ Languages
            </h3>
            <p style={{fontSize: "0.75rem", opacity: 0.9, lineHeight: "1.3"}}>
              Worldwide support
            </p>
          </div>

          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "0.75rem",
            borderRadius: "10px",
            textAlign: "center",
            backdropFilter: "blur(10px)"
          }}>
            <div style={{fontSize: "1.75rem", marginBottom: "0.25rem"}}>👥</div>
            <h3 style={{fontSize: "0.9rem", fontWeight: "600", marginBottom: "0.25rem"}}>
              Multi-participant
            </h3>
            <p style={{fontSize: "0.75rem", opacity: 0.9, lineHeight: "1.3"}}>
              Connect anyone
            </p>
          </div>
        </div>

        {/* CTA Buttons */}
        <div style={{display: "flex", gap: "0.75rem", flexWrap: "wrap", justifyContent: "center", marginBottom: "1rem"}}>
          <button
            onClick={() => navigate("/login")}
            style={{
              padding: "0.85rem 1.5rem",
              background: "white",
              color: "#667eea",
              border: "none",
              borderRadius: "10px",
              fontSize: "1rem",
              fontWeight: "600",
              cursor: "pointer",
              minWidth: "130px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
            }}
          >
            {t('landing.signIn')}
          </button>

          <button
            onClick={() => navigate("/signup")}
            style={{
              padding: "0.85rem 1.5rem",
              background: "rgba(255,255,255,0.2)",
              color: "white",
              border: "2px solid white",
              borderRadius: "10px",
              fontSize: "1rem",
              fontWeight: "600",
              cursor: "pointer",
              minWidth: "130px"
            }}
          >
            {t('landing.createAccount')}
          </button>
        </div>

        {/* Creator Info */}
        <div style={{
          marginTop: "0.5rem",
          fontSize: "0.8rem",
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
