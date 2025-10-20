import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

export default function LoginPage({ onLogin }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  
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
  
  return (
    <div style={{
      minHeight: "100vh",
      height: "100vh",
      background: "#0a0a0a",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "system-ui, -apple-system, sans-serif",
      padding: "1rem",
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      overflow: "auto"
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
          Welcome Back
        </h1>
        <p style={{color: "#999", marginBottom: "2rem", fontSize: "0.95rem"}}>
          Sign in to your LiveTranslator account
        </p>
        
        <form onSubmit={handleSubmit}>
          <div style={{marginBottom: "1.5rem"}}>
            <label style={{
              color: "white",
              display: "block",
              marginBottom: "0.5rem",
              fontSize: "0.95rem"
            }}>
              Email
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
              Password
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
            {loading ? "Signing in..." : "Sign In"}
          </button>
        </form>
        
        <p style={{
          color: "#999",
          textAlign: "center",
          marginTop: "1.5rem",
          fontSize: "0.9rem"
        }}>
          Don't have an account?{" "}
          <span
            onClick={() => navigate("/signup")}
            style={{
              color: "#3b82f6",
              cursor: "pointer",
              textDecoration: "underline"
            }}
          >
            Sign up
          </span>
        </p>
      </div>
    </div>
  );
}
