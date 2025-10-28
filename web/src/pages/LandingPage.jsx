import React, { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Footer from "../components/Footer";
import ThemeToggle from "../components/ThemeToggle";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";

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
    <div className="min-h-screen bg-bg flex flex-col">
      {/* Theme Toggle - Top Right */}
      <div className="absolute top-4 right-4 z-10">
        <ThemeToggle />
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col items-center justify-center px-5 py-16 max-w-container-lg mx-auto w-full">
        {/* Hero Section with Gradient Accent */}
        <div className="text-center mb-12 relative">
          {/* Decorative gradient blur */}
          <div className="absolute -top-20 left-1/2 -translate-x-1/2 w-96 h-96 bg-gradient-to-br from-gradient-from to-gradient-to opacity-10 blur-3xl rounded-full pointer-events-none"></div>

          <div className="relative">
            {/* Badge */}
            <div className="inline-flex items-center px-4 py-2 rounded-full bg-accent/10 border border-accent/20 text-accent text-sm font-semibold mb-6">
              🌍 Real-time Translation Platform
            </div>

            {/* Main Heading */}
            <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold mb-4 text-fg leading-tight">
              {t('landing.title')}
            </h1>

            {/* Subtitle */}
            <p className="text-lg md:text-xl text-muted max-w-2xl mx-auto leading-relaxed">
              {t('landing.subtitle')}
            </p>
          </div>
        </div>

        {/* Features Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 w-full mb-12 max-w-3xl">
          <Card hoverable className="text-center">
            <div className="text-4xl mb-3">🗣️</div>
            <h3 className="text-lg font-semibold mb-2 text-fg">Real-time Speech</h3>
            <p className="text-sm text-muted">Instant voice translation as you speak</p>
          </Card>

          <Card hoverable className="text-center">
            <div className="text-4xl mb-3">🌐</div>
            <h3 className="text-lg font-semibold mb-2 text-fg">12+ Languages</h3>
            <p className="text-sm text-muted">Connect with anyone worldwide</p>
          </Card>

          <Card hoverable className="text-center">
            <div className="text-4xl mb-3">👥</div>
            <h3 className="text-lg font-semibold mb-2 text-fg">Multi-participant</h3>
            <p className="text-sm text-muted">Collaborate with multiple users</p>
          </Card>
        </div>

        {/* CTA Buttons */}
        <div className="flex gap-4 flex-wrap justify-center w-full max-w-md">
          <Button
            variant="primary"
            onClick={() => navigate("/login")}
            className="flex-1 min-w-[140px]"
          >
            {t('landing.signIn')}
          </Button>

          <Button
            variant="secondary"
            onClick={() => navigate("/signup")}
            className="flex-1 min-w-[140px]"
          >
            {t('landing.createAccount')}
          </Button>
        </div>

        {/* Creator Info */}
        <div className="mt-8 text-sm text-muted text-center">
          Created by{" "}
          <a
            href="https://pawelgawliczek.cloud/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:text-accent-dark font-semibold transition-colors"
          >
            Pawel Gawliczek
          </a>
        </div>
      </div>

      <Footer />
    </div>
  );
}
