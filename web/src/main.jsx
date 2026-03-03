import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./index.css";
import "./i18n";
import { loadLanguageFromProfile } from "./utils/languageSync";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import RoomsPage from "./pages/RoomsPage";
import RoomPageWrapper from "./pages/RoomPageWrapper";
import JoinPage from "./pages/JoinPage";
import ProfilePage from "./pages/ProfilePage";
import AdminSettingsPage from "./pages/AdminSettingsPage";
import AdminCostAnalyticsPage from "./pages/AdminCostAnalyticsPage";
import AdminMultiSpeakerPage from "./pages/AdminMultiSpeakerPage";
import ProtectedAdminRoute from "./components/admin/ProtectedAdminRoute";
import AdminOverviewPage from "./pages/AdminOverviewPage";
import AdminUsersPage from "./pages/AdminUsersPage";
import AdminMetricsPage from "./pages/AdminMetricsPage";
import AdminSystemPage from "./pages/AdminSystemPage";
import AdminToolsPage from "./pages/AdminToolsPage";
import AdminNotificationsPage from "./pages/AdminNotificationsPage";
import NotificationsPage from "./pages/NotificationsPage";
import NotificationToast from "./components/NotificationToast";

function App() {
  const [token, setToken] = React.useState(localStorage.getItem("token") || "");
  const [toast, setToast] = React.useState(null);

  const login = async (newToken) => {
    setToken(newToken);
    localStorage.setItem("token", newToken);

    // Load user's preferred language from their profile
    await loadLanguageFromProfile(newToken);
  };

  const logout = () => {
    setToken("");
    localStorage.removeItem("token");
  };

  const showToast = (message, type = 'error') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 5000);
  };
  
  return (
    <BrowserRouter>
      {toast && <NotificationToast message={toast.message} type={toast.type} />}
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage onLogin={login} />} />
        <Route path="/signup" element={<SignupPage onSignup={login} />} />
        <Route path="/join/:inviteCode" element={<JoinPage token={token} onLogin={login} />} />
        <Route
          path="/rooms"
          element={token ? <RoomsPage token={token} onLogout={logout} onLogin={login} /> : <Navigate to="/login" />}
        />
        <Route
          path="/room/:roomId"
          element={<RoomPageWrapper token={token} onLogout={logout} />}
        />
        <Route
          path="/profile"
          element={token ? <ProfilePage token={token} onLogout={logout} /> : <Navigate to="/login" />}
        />

        {/* Legacy admin routes - keep for backward compatibility */}
        <Route
          path="/admin"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminSettingsPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/costs"
          element={<Navigate to="/admin/cost-analytics" replace />}
        />

        {/* Phase 3A: New Admin Panel Routes */}
        <Route
          path="/admin/overview"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminOverviewPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/users"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminUsersPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/metrics"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminMetricsPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/system"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminSystemPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/tools"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminToolsPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/notifications"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminNotificationsPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/cost-analytics"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminCostAnalyticsPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />
        <Route
          path="/admin/costs/multi-speaker"
          element={
            token ? (
              <ProtectedAdminRoute token={token} onUnauthorized={showToast}>
                <AdminMultiSpeakerPage token={token} onLogout={logout} />
              </ProtectedAdminRoute>
            ) : (
              <Navigate to="/login" />
            )
          }
        />

        {/* User notifications page */}
        <Route
          path="/notifications"
          element={token ? <NotificationsPage token={token} onLogout={logout} /> : <Navigate to="/login" />}
        />

      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<App />);
