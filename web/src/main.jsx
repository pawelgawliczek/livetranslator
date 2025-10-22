import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./i18n";
import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import SignupPage from "./pages/SignupPage";
import RoomsPage from "./pages/RoomsPage";
import RoomPage from "./pages/RoomPage";
import JoinPage from "./pages/JoinPage";
import ProfilePage from "./pages/ProfilePage";

function App() {
  const [token, setToken] = React.useState(localStorage.getItem("token") || "");
  
  const login = (newToken) => {
    setToken(newToken);
    localStorage.setItem("token", newToken);
  };
  
  const logout = () => {
    setToken("");
    localStorage.removeItem("token");
  };
  
  return (
    <BrowserRouter>
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
          element={<RoomPage token={token} onLogout={logout} />}
        />
        <Route
          path="/profile"
          element={token ? <ProfilePage token={token} onLogout={logout} /> : <Navigate to="/login" />}
        />
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<App />);
