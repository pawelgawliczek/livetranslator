import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";
import ThemeToggle from "../components/ThemeToggle";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";

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
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Theme Toggle - Top Right */}
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle />
      </div>

      <div className="flex-1 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <h1 className="text-3xl font-bold text-fg mb-2">
            {t('auth.createAccount')}
          </h1>
          <p className="text-muted mb-8 text-base">
            {t('auth.joinSubtitle')}
          </p>

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
                {t('auth.displayNameOptional')}
              </label>
              <input
                type="text"
                placeholder={t('auth.yourName')}
                value={displayName}
                onChange={e => setDisplayName(e.target.value)}
                autoComplete="name"
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
                minLength={6}
                autoComplete="new-password"
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
              {loading ? t('auth.creatingAccount') : t('auth.createAccount')}
            </Button>
          </form>

          <p className="text-muted text-center mt-6 text-sm">
            {t('auth.hasAccount')}{" "}
            <span
              onClick={() => navigate("/login")}
              className="text-accent hover:text-accent-dark cursor-pointer font-semibold transition-colors"
            >
              {t('auth.signIn')}
            </span>
          </p>
        </Card>
      </div>
      <Footer />
    </div>
  );
}
