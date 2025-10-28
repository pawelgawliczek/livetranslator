import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";
import ThemeToggle from "../components/ThemeToggle";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";

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
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Theme Toggle - Top Right */}
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle />
      </div>

      <div className="flex-1 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <h1 className="text-3xl font-bold text-fg mb-2">
            {t('auth.welcomeBack')}
          </h1>
          <p className="text-muted mb-8 text-base">
            {t('auth.signInSubtitle')}
          </p>

          {/* Google Sign In Button */}
          <button
            onClick={handleGoogleLogin}
            className="w-full p-4 bg-card border border-border rounded-lg text-base font-semibold cursor-pointer mb-6 flex items-center justify-center gap-3 hover:bg-bg-secondary transition-colors"
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
          <div className="flex items-center mb-6">
            <div className="flex-1 h-px bg-border"></div>
            <span className="px-4 text-muted text-sm">or</span>
            <div className="flex-1 h-px bg-border"></div>
          </div>

          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-fg text-sm font-medium mb-2">
                {t('auth.email')}
              </label>
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                autoComplete="email"
                className="w-full px-4 py-3 bg-bg-secondary border border-border rounded-lg text-fg focus:border-accent focus:ring-2 focus:ring-ring transition-colors"
              />
            </div>

            <div>
              <label className="block text-fg text-sm font-medium mb-2">
                {t('auth.password')}
              </label>
              <input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                className="w-full px-4 py-3 bg-bg-secondary border border-border rounded-lg text-fg focus:border-accent focus:ring-2 focus:ring-ring transition-colors"
              />
            </div>

            {error && (
              <div className="bg-red-500/10 border border-red-500/20 text-red-600 px-4 py-3 rounded-lg text-sm">
                {error}
              </div>
            )}

            <Button
              type="submit"
              variant="primary"
              disabled={loading}
              className="w-full"
            >
              {loading ? t('auth.signingIn') : t('auth.signInButton')}
            </Button>
          </form>

          <p className="text-muted text-center mt-6 text-sm">
            {t('auth.noAccount')}{" "}
            <span
              onClick={() => navigate("/signup")}
              className="text-accent hover:text-accent-dark cursor-pointer font-semibold transition-colors"
            >
              {t('auth.signUp')}
            </span>
          </p>
        </Card>
      </div>
      <Footer />
    </div>
  );
}
