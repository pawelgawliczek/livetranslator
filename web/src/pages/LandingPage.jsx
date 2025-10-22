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
        padding: "2rem 2rem 1rem 2rem"
      }}>
        <h1 style={{
          fontSize: "clamp(2.5rem, 8vw, 4rem)",
          fontWeight: "bold",
          marginBottom: "1rem",
          textAlign: "center"
        }}>
          {t('landing.title')}
        </h1>

        <p style={{
          fontSize: "clamp(1.1rem, 3vw, 1.5rem)",
          marginBottom: "3rem",
          textAlign: "center",
          maxWidth: "600px"
        }}>
          {t('landing.subtitle')}
        </p>

        <div style={{display: "flex", gap: "1rem", flexWrap: "wrap", justifyContent: "center"}}>
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
              minWidth: "150px"
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
      </div>
      <Footer />
    </div>
  );
}
