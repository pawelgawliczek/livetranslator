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
      <div className="fixed top-4 right-4 z-10">
        <ThemeToggle />
      </div>

      {/* Main Content */}
      <div className="flex-1 w-full flex flex-col">
        <div className="flex flex-col items-center justify-between flex-1 px-4 sm:px-6 py-4 sm:py-12 md:py-16 lg:py-20 max-w-container-lg mx-auto w-full">
          {/* Hero Section with Gradient Accent */}
          <div className="text-center mb-6 sm:mb-10 md:mb-12 relative w-full">
            {/* Decorative gradient blur */}
            <div className="absolute -top-10 sm:-top-20 left-1/2 -translate-x-1/2 w-64 h-64 sm:w-96 sm:h-96 bg-gradient-to-br from-gradient-from to-gradient-to opacity-10 blur-3xl rounded-full pointer-events-none"></div>

            <div className="relative">
              {/* Badge */}
              <div className="inline-flex items-center px-2.5 py-1 sm:px-4 sm:py-2 rounded-full bg-accent/10 border border-accent/20 text-accent text-xs sm:text-sm font-semibold mb-4 sm:mb-6">
                🌍 Real-time Translation Platform
              </div>

              {/* Main Heading */}
              <h1 className="text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-bold mb-2 sm:mb-4 text-fg leading-tight px-2">
                {t('landing.title')}
              </h1>

              {/* Subtitle */}
              <p className="text-sm sm:text-lg md:text-xl text-muted max-w-2xl mx-auto leading-snug sm:leading-relaxed px-4">
                {t('landing.subtitle')}
              </p>
            </div>
          </div>

          {/* Features Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 sm:gap-4 w-full mb-4 sm:mb-10 md:mb-12 max-w-3xl">
            <Card hoverable className="text-center py-3 sm:py-4">
              <div className="text-2xl sm:text-4xl mb-1 sm:mb-3">🗣️</div>
              <h3 className="text-sm sm:text-lg font-semibold mb-0.5 sm:mb-2 text-fg">{t('landing.features.realTimeTitle')}</h3>
              <p className="text-xs sm:text-sm text-muted leading-tight">{t('landing.features.realTimeDesc')}</p>
            </Card>

            <Card hoverable className="text-center py-3 sm:py-4">
              <div className="text-2xl sm:text-4xl mb-1 sm:mb-3">🌐</div>
              <h3 className="text-sm sm:text-lg font-semibold mb-0.5 sm:mb-2 text-fg">{t('landing.features.languagesTitle')}</h3>
              <p className="text-xs sm:text-sm text-muted leading-tight">{t('landing.features.languagesDesc')}</p>
            </Card>

            <Card hoverable className="text-center py-3 sm:py-4">
              <div className="text-2xl sm:text-4xl mb-1 sm:mb-3">👥</div>
              <h3 className="text-sm sm:text-lg font-semibold mb-0.5 sm:mb-2 text-fg">{t('landing.features.multiParticipantTitle')}</h3>
              <p className="text-xs sm:text-sm text-muted leading-tight">{t('landing.features.multiParticipantDesc')}</p>
            </Card>
          </div>

          {/* CTA Buttons */}
          <div className="flex gap-2.5 sm:gap-4 flex-wrap justify-center w-full max-w-md">
            <Button
              variant="primary"
              onClick={() => navigate("/login")}
              className="flex-1 min-w-[130px] sm:min-w-[140px] py-2 sm:py-2.5"
            >
              {t('landing.signIn')}
            </Button>

            <Button
              variant="secondary"
              onClick={() => navigate("/signup")}
              className="flex-1 min-w-[130px] sm:min-w-[140px] py-2 sm:py-2.5"
            >
              {t('landing.createAccount')}
            </Button>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
}
