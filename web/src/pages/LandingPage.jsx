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
        padding: "2rem 2rem 1rem 2rem",
        maxWidth: "1200px",
        margin: "0 auto",
        width: "100%"
      }}>
        {/* Main Title */}
        <div style={{
          background: "rgba(255,255,255,0.15)",
          padding: "0.5rem 1.5rem",
          borderRadius: "50px",
          marginBottom: "1.5rem",
          fontSize: "0.9rem",
          fontWeight: "600",
          backdropFilter: "blur(10px)"
        }}>
          🌍 Real-time Translation Platform
        </div>

        <h1 style={{
          fontSize: "clamp(2.5rem, 8vw, 4rem)",
          fontWeight: "bold",
          marginBottom: "1rem",
          textAlign: "center",
          lineHeight: "1.1"
        }}>
          {t('landing.title')}
        </h1>

        <p style={{
          fontSize: "clamp(1.1rem, 3vw, 1.5rem)",
          marginBottom: "2rem",
          textAlign: "center",
          maxWidth: "700px",
          lineHeight: "1.5"
        }}>
          {t('landing.subtitle')}
        </p>

        {/* Features Grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(250px, 1fr))",
          gap: "1.5rem",
          width: "100%",
          maxWidth: "900px",
          marginBottom: "2.5rem"
        }}>
          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "1.5rem",
            borderRadius: "12px",
            textAlign: "center",
            backdropFilter: "blur(10px)"
          }}>
            <div style={{fontSize: "2.5rem", marginBottom: "0.5rem"}}>🗣️</div>
            <h3 style={{fontSize: "1.1rem", fontWeight: "600", marginBottom: "0.5rem"}}>
              Real-time Speech
            </h3>
            <p style={{fontSize: "0.9rem", opacity: 0.9}}>
              Instant voice-to-text translation as you speak
            </p>
          </div>

          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "1.5rem",
            borderRadius: "12px",
            textAlign: "center",
            backdropFilter: "blur(10px)"
          }}>
            <div style={{fontSize: "2.5rem", marginBottom: "0.5rem"}}>🌐</div>
            <h3 style={{fontSize: "1.1rem", fontWeight: "600", marginBottom: "0.5rem"}}>
              12+ Languages
            </h3>
            <p style={{fontSize: "0.9rem", opacity: 0.9}}>
              English, Polish, Arabic, Spanish, French, German & more
            </p>
          </div>

          <div style={{
            background: "rgba(255,255,255,0.15)",
            padding: "1.5rem",
            borderRadius: "12px",
            textAlign: "center",
            backdropFilter: "blur(10px)"
          }}>
            <div style={{fontSize: "2.5rem", marginBottom: "0.5rem"}}>👥</div>
            <h3 style={{fontSize: "1.1rem", fontWeight: "600", marginBottom: "0.5rem"}}>
              Multi-participant
            </h3>
            <p style={{fontSize: "0.9rem", opacity: 0.9}}>
              Connect multiple people in different languages
            </p>
          </div>
        </div>

        {/* CTA Buttons */}
        <div style={{display: "flex", gap: "1rem", flexWrap: "wrap", justifyContent: "center", marginBottom: "2rem"}}>
          <button
            onClick={() => navigate("/login")}
            style={{
              padding: "1rem 2rem",
              background: "white",
              color: "#667eea",
              border: "none",
              borderRadius: "12px",
              fontSize: "1.1rem",
              fontWeight: "600",
              cursor: "pointer",
              minWidth: "150px",
              boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
            }}
          >
            {t('landing.signIn')}
          </button>

          <button
            onClick={() => navigate("/signup")}
            style={{
              padding: "1rem 2rem",
              background: "rgba(255,255,255,0.2)",
              color: "white",
              border: "2px solid white",
              borderRadius: "12px",
              fontSize: "1.1rem",
              fontWeight: "600",
              cursor: "pointer",
              minWidth: "150px"
            }}
          >
            {t('landing.createAccount')}
          </button>
        </div>

        {/* Creator Info */}
        <div style={{
          marginTop: "1rem",
          fontSize: "0.9rem",
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
