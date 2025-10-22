import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";

export default function LoginPage({ onLogin }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  // Check for token in URL (from Google OAuth redirect)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    if (token) {
      onLogin(token);
      navigate('/rooms');
    }
  }, [location, onLogin, navigate]);
  
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    
    try {
      const response = await fetch("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({ username: email, password })
      });
      
      if (!response.ok) {
        throw new Error("Invalid credentials");
      }
      
      const data = await response.json();
      onLogin(data.access_token);
      navigate("/rooms");
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }
  
  function handleGoogleLogin() {
    window.location.href = "/auth/google/login";
  }
  
  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0a0a",
      display: "flex",
      flexDirection: "column",
      fontFamily: "system-ui, -apple-system, sans-serif"
    }}>
      <div style={{
        flex: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem 1rem 0.5rem 1rem"
      }}>
        <div style={{
        maxWidth: "450px",
        width: "100%",
        background: "#1a1a1a",
        borderRadius: "16px",
        padding: "2rem",
        border: "1px solid #333"
      }}>
        <h1 style={{
          color: "white",
          fontSize: "clamp(1.75rem, 5vw, 2rem)",
          marginBottom: "0.5rem"
        }}>
          {t('auth.welcomeBack')}
        </h1>
        <p style={{color: "#999", marginBottom: "2rem", fontSize: "0.95rem"}}>
          {t('auth.signInSubtitle')}
        </p>
        
        {/* Google Sign In Button */}
        <button
          onClick={handleGoogleLogin}
          style={{
            width: "100%",
            padding: "1rem",
            background: "white",
            color: "#1a1a1a",
            border: "1px solid #444",
            borderRadius: "12px",
            fontSize: "1rem",
            fontWeight: "600",
            cursor: "pointer",
            marginBottom: "1.5rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.75rem",
            WebkitAppearance: "none"
          }}
        >
          <svg width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9.003 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.96v2.332C2.44 15.983 5.485 18 9.003 18z" fill="#34A853"/>
            <path d="M3.964 10.71c-.18-.54-.282-1.117-.282-1.71 0-.593.102-1.17.282-1.71V4.958H.957C.347 6.173 0 7.548 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9.003 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.464.891 11.426 0 9.003 0 5.485 0 2.44 2.017.96 4.958L3.967 7.29c.708-2.127 2.692-3.71 5.036-3.71z" fill="#EA4335"/>
          </svg>
          {t('auth.continueWithGoogle')}
        </button>
        
        {/* Divider */}
        <div style={{
          display: "flex",
          alignItems: "center",
          marginBottom: "1.5rem"
        }}>
          <div style={{flex: 1, height: "1px", background: "#333"}}></div>
          <span style={{padding: "0 1rem", color: "#666", fontSize: "0.85rem"}}>or</span>
          <div style={{flex: 1, height: "1px", background: "#333"}}></div>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div style={{marginBottom: "1.5rem"}}>
            <label style={{
              color: "white",
              display: "block",
              marginBottom: "0.5rem",
              fontSize: "0.95rem"
            }}>
              {t('auth.email')}
            </label>
            <input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={e => setEmail(e.target.value)}
              required
              autoComplete="email"
              style={{
                width: "100%",
                padding: "1rem",
                background: "#2a2a2a",
                border: "1px solid #444",
                borderRadius: "12px",
                color: "white",
                fontSize: "1rem",
                WebkitAppearance: "none"
              }}
            />
          </div>
          
          <div style={{marginBottom: "2rem"}}>
            <label style={{
              color: "white",
              display: "block",
              marginBottom: "0.5rem",
              fontSize: "0.95rem"
            }}>
              {t('auth.password')}
            </label>
            <input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={e => setPassword(e.target.value)}
              required
              autoComplete="current-password"
              style={{
                width: "100%",
                padding: "1rem",
                background: "#2a2a2a",
                border: "1px solid #444",
                borderRadius: "12px",
                color: "white",
                fontSize: "1rem",
                WebkitAppearance: "none"
              }}
            />
          </div>
          
          {error && (
            <div style={{
              background: "#dc2626",
              color: "white",
              padding: "1rem",
              borderRadius: "12px",
              marginBottom: "1rem",
              fontSize: "0.9rem"
            }}>
              {error}
            </div>
          )}
          
          <button
            type="submit"
            disabled={loading}
            style={{
              width: "100%",
              padding: "1rem",
              background: "#3b82f6",
              color: "white",
              border: "none",
              borderRadius: "12px",
              fontSize: "1rem",
              fontWeight: "600",
              cursor: loading ? "not-allowed" : "pointer",
              opacity: loading ? 0.7 : 1,
              WebkitAppearance: "none"
            }}
          >
            {loading ? t('auth.signingIn') : t('auth.signInButton')}
          </button>
        </form>
        
        <p style={{
          color: "#999",
          textAlign: "center",
          marginTop: "1.5rem",
          fontSize: "0.9rem"
        }}>
          {t('auth.noAccount')}{" "}
          <span
            onClick={() => navigate("/signup")}
            style={{
              color: "#3b82f6",
              cursor: "pointer",
              textDecoration: "underline"
            }}
          >
            {t('auth.signUp')}
          </span>
        </p>
        </div>
      </div>
      <Footer />
    </div>
  );
}
