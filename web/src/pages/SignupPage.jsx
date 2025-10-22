import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";

export default function SignupPage({ onSignup }) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    
    try {
      const response = await fetch("/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          email, 
          password,
          display_name: displayName || email.split('@')[0]
        })
      });
      
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Signup failed");
      }
      
      const data = await response.json();
      onSignup(data.access_token);
      navigate("/rooms");
    } catch (err) {
      setError(err.message || "Signup failed");
    } finally {
      setLoading(false);
    }
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
          {t('auth.createAccount')}
        </h1>
        <p style={{color: "#999", marginBottom: "2rem", fontSize: "0.95rem"}}>
          {t('auth.joinSubtitle')}
        </p>
        
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
          
          <div style={{marginBottom: "1.5rem"}}>
            <label style={{
              color: "white",
              display: "block",
              marginBottom: "0.5rem",
              fontSize: "0.95rem"
            }}>
              {t('auth.displayNameOptional')}
            </label>
            <input
              type="text"
              placeholder={t('auth.yourName')}
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
              autoComplete="name"
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
              minLength={6}
              autoComplete="new-password"
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
            {loading ? t('auth.creatingAccount') : t('auth.createAccount')}
          </button>
        </form>
        
        <p style={{
          color: "#999",
          textAlign: "center",
          marginTop: "1.5rem",
          fontSize: "0.9rem"
        }}>
          {t('auth.hasAccount')}{" "}
          <span
            onClick={() => navigate("/login")}
            style={{
              color: "#3b82f6",
              cursor: "pointer",
              textDecoration: "underline"
            }}
          >
            {t('auth.signIn')}
          </span>
        </p>
        </div>
      </div>
      <Footer />
    </div>
  );
}
