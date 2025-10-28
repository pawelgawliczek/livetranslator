import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import QuickRoomModal from "../components/QuickRoomModal";
import RoomsMenu from "../components/RoomsMenu";
import LanguageSelector from "../components/LanguageSelector";
import ThemeToggle from "../components/ThemeToggle";
import Footer from "../components/Footer";
import Card from "../components/ui/Card";
import Button from "../components/ui/Button";
import TagPill from "../components/ui/TagPill";

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
    <div className="min-h-screen bg-bg flex flex-col">
      <div className="flex-1 p-4">
        <div className="max-w-4xl mx-auto">
          {/* Header */}
          <div className="flex justify-between items-start mb-6 gap-4 flex-wrap">
            <div className="flex-1 min-w-0">
              <h1 className="text-2xl md:text-3xl font-bold text-fg mb-1">
                {t('rooms.title')}
              </h1>
              <p className="text-muted text-sm truncate">
                {t('common.login')} {userEmail}
              </p>
            </div>
            <div className="flex gap-2 items-center flex-shrink-0">
              <ThemeToggle />
              <LanguageSelector token={token} />
              <button
                onClick={() => setShowMenu(true)}
                className="p-3 bg-card border border-border rounded-lg text-fg hover:bg-bg-secondary transition-colors text-xl min-w-[48px] min-h-[48px] flex items-center justify-center"
              >
                ⚙️
              </button>
            </div>
          </div>

          {/* Create Room Section */}
          <Card className="mb-8">
            <h2 className="text-xl font-semibold text-fg mb-4">
              {t('rooms.createRoom')}
            </h2>

            {/* Quick Room Button */}
            <div className="mb-4">
              <button
                onClick={() => setShowQuickRoom(true)}
                className="w-full p-4 bg-gradient-to-r from-accent to-accent-dark text-accent-fg rounded-lg font-semibold text-lg flex items-center justify-center gap-2 transition-all hover:shadow-lg hover:-translate-y-0.5"
              >
                <span className="text-2xl">⚡</span>
                {t('rooms.quickRoom')} ({t('quickRoom.createButton')})
              </button>
            </div>

            <div className="text-center text-muted text-sm my-4">
              {t('common.or')} {t('rooms.createRoom').toLowerCase()}
            </div>

            <div className="flex gap-3 flex-wrap">
              <input
                type="text"
                placeholder={t('rooms.roomName') + "..."}
                value={newRoomName}
                onChange={e => setNewRoomName(e.target.value)}
                onKeyDown={e => e.key === "Enter" && createRoom()}
                className="flex-1 min-w-[200px] px-4 py-3 bg-bg-secondary border border-border rounded-lg text-fg focus:border-accent focus:ring-2 focus:ring-ring transition-colors"
              />
              <Button
                onClick={createRoom}
                variant="primary"
                className="whitespace-nowrap"
              >
                {t('rooms.createRoom')}
              </Button>
            </div>
          </Card>

          {/* Rooms List */}
          <div>
            <h2 className="text-xl font-semibold text-fg mb-4">
              {t('nav.rooms')}
            </h2>
            {loading ? (
              <div className="text-center text-muted py-8">
                {t('common.loading')}
              </div>
            ) : rooms.length === 0 ? (
              <Card className="text-center">
                <p className="text-muted">
                  {t('rooms.noRooms')}. {t('rooms.createFirst')}
                </p>
              </Card>
            ) : (
              <div className="flex flex-col gap-4">
                {rooms.map(room => (
                  <Card
                    key={room.id}
                    hoverable
                    onClick={() => navigate(`/room/${room.code}`)}
                    className="cursor-pointer"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-lg font-semibold text-fg">
                        {room.code}
                      </div>
                      <div className="flex gap-2 items-center flex-wrap">
                        {room.is_public && (
                          <TagPill variant="success">
                            <span>🌍</span>
                            <span>{t('rooms.public')}</span>
                          </TagPill>
                        )}
                        {!room.is_public && (
                          <TagPill>
                            <span>🔒</span>
                            <span>{t('rooms.private')}</span>
                          </TagPill>
                        )}
                        {!room.is_owner && (
                          <TagPill>
                            <span>👥</span>
                            <span>{t('rooms.shared')}</span>
                          </TagPill>
                        )}
                      </div>
                    </div>
                    <div className="text-muted text-sm">
                      {t('rooms.created')} {new Date(room.created_at).toLocaleDateString()}
                    </div>
                  </Card>
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
