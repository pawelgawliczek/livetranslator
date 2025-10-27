import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import QuickRoomModal from "../components/QuickRoomModal";
import RoomsMenu from "../components/RoomsMenu";
import LanguageSelector from "../components/LanguageSelector";
import Footer from "../components/Footer";

export default function RoomsPage({ token, onLogout, onLogin }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const [newRoomName, setNewRoomName] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [isAdmin, setIsAdmin] = useState(false);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showQuickRoom, setShowQuickRoom] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  
  // Check for token in URL (from Google OAuth redirect)
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const urlToken = params.get('token');
    if (urlToken && !token) {
      // If there's a token in URL and we don't have one yet
      onLogin(urlToken);
    }
  }, [location, token]);
  
  useEffect(() => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUserEmail(payload.email || "User");
    } catch (e) {
      console.error("Failed to decode token:", e);
    }
  }, [token]);
  
  useEffect(() => {
    fetchRooms();
    fetchProfile();
  }, []);

  async function fetchProfile() {
    try {
      const response = await fetch("/api/profile", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      if (response.ok) {
        const data = await response.json();
        setIsAdmin(data.is_admin || false);
      }
    } catch (e) {
      console.error("Failed to fetch profile:", e);
    }
  }
  
  async function fetchRooms() {
    try {
      setLoading(true);
      // Fetch list of available rooms from backend
      const response = await fetch("/api/history/rooms", {
        headers: { "Authorization": `Bearer ${token}` }
      });
      
      if (response.ok) {
        const data = await response.json();
        setRooms(data.rooms || []);
      }
    } catch (e) {
      console.error("Failed to fetch rooms:", e);
    } finally {
      setLoading(false);
    }
  }
  
  async function createRoom() {
    if (!newRoomName.trim()) return;
    
    try {
      const response = await fetch("/api/rooms", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`
        },
        body: JSON.stringify({ code: newRoomName })
      });
      
      if (response.ok) {
        setNewRoomName("");
        fetchRooms();
      }
    } catch (e) {
      console.error("Failed to create room:", e);
    }
  }
  
  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0a0a",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif",
      display: "flex",
      flexDirection: "column"
    }}>
      <div style={{
        flex: 1,
        padding: "1rem"
      }}>
        <div style={{
          maxWidth: "800px",
          margin: "0 auto"
        }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "1.5rem",
          gap: "1rem",
          flexWrap: "wrap"
        }}>
          <div style={{ flex: "1 1 200px", minWidth: 0 }}>
            <h1 style={{fontSize: "clamp(1.5rem, 5vw, 2rem)", marginBottom: "0.5rem"}}>{t('rooms.title')}</h1>
            <p style={{color: "#999", fontSize: "0.9rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap"}}>{t('common.login')} {userEmail}</p>
          </div>
          <div style={{ display: "flex", gap: "10px", alignItems: "center", flexShrink: 0 }}>
            <LanguageSelector token={token} />
            <button
              onClick={() => setShowMenu(true)}
              style={{
                padding: "0.75rem 1rem",
                background: "#2a2a2a",
                color: "white",
                border: "1px solid #444",
                borderRadius: "8px",
                cursor: "pointer",
                fontSize: "1.25rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                transition: "all 0.2s",
                minWidth: "48px",
                minHeight: "48px"
              }}
              onMouseEnter={e => {
                e.currentTarget.style.background = "#3a3a3a";
                e.currentTarget.style.borderColor = "#666";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.background = "#2a2a2a";
                e.currentTarget.style.borderColor = "#444";
              }}
            >
              ⚙️
            </button>
          </div>
        </div>
        
        <div style={{
          background: "#1a1a1a",
          borderRadius: "12px",
          padding: "1.5rem",
          marginBottom: "2rem",
          border: "1px solid #333"
        }}>
          <h2 style={{fontSize: "1.25rem", marginBottom: "1rem"}}>{t('rooms.createRoom')}</h2>

          {/* Quick Room Button */}
          <div style={{marginBottom: "1rem"}}>
            <button
              onClick={() => setShowQuickRoom(true)}
              style={{
                width: "100%",
                padding: "1rem 1.5rem",
                background: "linear-gradient(135deg, #6366f1 0%, #3b82f6 100%)",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontWeight: "600",
                fontSize: "1.05rem",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
                transition: "transform 0.2s, box-shadow 0.2s",
                boxShadow: "0 4px 12px rgba(59, 130, 246, 0.3)"
              }}
              onMouseEnter={e => {
                e.currentTarget.style.transform = "translateY(-2px)";
                e.currentTarget.style.boxShadow = "0 6px 20px rgba(59, 130, 246, 0.4)";
              }}
              onMouseLeave={e => {
                e.currentTarget.style.transform = "translateY(0)";
                e.currentTarget.style.boxShadow = "0 4px 12px rgba(59, 130, 246, 0.3)";
              }}
            >
              <span style={{fontSize: "1.5rem"}}>⚡</span>
              {t('rooms.quickRoom')} ({t('quickRoom.createButton')})
            </button>
          </div>

          <div style={{
            textAlign: "center",
            color: "#666",
            fontSize: "0.85rem",
            margin: "1rem 0"
          }}>
            {t('common.or')} {t('rooms.createRoom').toLowerCase()}
          </div>

          <div style={{display: "flex", gap: "0.75rem", flexWrap: "wrap"}}>
            <input
              type="text"
              placeholder={t('rooms.roomName') + "..."}
              value={newRoomName}
              onChange={e => setNewRoomName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && createRoom()}
              style={{
                flex: "1 1 200px",
                minWidth: "200px",
                padding: "0.75rem",
                background: "#2a2a2a",
                border: "1px solid #444",
                borderRadius: "8px",
                color: "white",
                fontSize: "1rem"
              }}
            />
            <button
              onClick={createRoom}
              style={{
                padding: "0.75rem 1.5rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontWeight: "600",
                flex: "0 1 auto",
                whiteSpace: "nowrap"
              }}
            >
              {t('rooms.createRoom')}
            </button>
          </div>
        </div>
        
        <div>
          <h2 style={{fontSize: "1.25rem", marginBottom: "1rem"}}>{t('nav.rooms')}</h2>
          {loading ? (
            <div style={{textAlign: "center", color: "#666", padding: "2rem"}}>
              {t('common.loading')}
            </div>
          ) : rooms.length === 0 ? (
            <div style={{textAlign: "center", color: "#666", padding: "2rem"}}>
              {t('rooms.noRooms')}. {t('rooms.createFirst')}
            </div>
          ) : (
            <div style={{display: "flex", flexDirection: "column", gap: "1rem"}}>
              {rooms.map(room => (
                <div
                  key={room.id}
                  onClick={() => navigate(`/room/${room.code}`)}
                  style={{
                    background: "#1a1a1a",
                    border: "1px solid #333",
                    borderRadius: "12px",
                    padding: "1.5rem",
                    cursor: "pointer",
                    transition: "all 0.2s"
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = "#2a2a2a";
                    e.currentTarget.style.borderColor = "#3b82f6";
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = "#1a1a1a";
                    e.currentTarget.style.borderColor = "#333";
                  }}
                >
                  <div style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: "0.5rem"
                  }}>
                    <div style={{fontSize: "1.1rem", fontWeight: "600"}}>
                      {room.code}
                    </div>
                    <div style={{display: "flex", gap: "0.5rem", alignItems: "center"}}>
                      {room.is_public && (
                        <span style={{
                          fontSize: "0.75rem",
                          padding: "0.25rem 0.5rem",
                          background: "#22c55e20",
                          color: "#22c55e",
                          borderRadius: "4px",
                          fontWeight: "500",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.25rem"
                        }}>
                          <span>🌍</span>
                          {t('rooms.public')}
                        </span>
                      )}
                      {!room.is_public && (
                        <span style={{
                          fontSize: "0.75rem",
                          padding: "0.25rem 0.5rem",
                          background: "#64748b20",
                          color: "#94a3b8",
                          borderRadius: "4px",
                          fontWeight: "500",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.25rem"
                        }}>
                          <span>🔒</span>
                          {t('rooms.private')}
                        </span>
                      )}
                      {!room.is_owner && (
                        <span style={{
                          fontSize: "0.75rem",
                          padding: "0.25rem 0.5rem",
                          background: "#3b82f620",
                          color: "#3b82f6",
                          borderRadius: "4px",
                          fontWeight: "500",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.25rem"
                        }}>
                          <span>👥</span>
                          {t('rooms.shared')}
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{color: "#999", fontSize: "0.85rem"}}>
                    {t('rooms.created')} {new Date(room.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
        </div>
      </div>

      {/* Quick Room Modal */}
      {showQuickRoom && (
        <QuickRoomModal
          token={token}
          onClose={() => setShowQuickRoom(false)}
        />
      )}

      {/* Rooms Menu */}
      <RoomsMenu
        isOpen={showMenu}
        onClose={() => setShowMenu(false)}
        isAdmin={isAdmin}
        onAdminClick={() => navigate("/admin")}
        onProfileClick={() => navigate("/profile")}
        onLogout={onLogout}
      />

      <Footer />
    </div>
  );
}
