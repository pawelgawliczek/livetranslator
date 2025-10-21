import React, { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import QuickRoomModal from "../components/QuickRoomModal";

export default function RoomsPage({ token, onLogout, onLogin }) {
  const navigate = useNavigate();
  const location = useLocation();
  const [newRoomName, setNewRoomName] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showQuickRoom, setShowQuickRoom] = useState(false);
  
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
  }, []);
  
  async function fetchRooms() {
    try {
      setLoading(true);
      // Fetch list of available rooms from backend
      const response = await fetch("/history/rooms", {
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
      const response = await fetch("/rooms", {
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
      padding: "2rem"
    }}>
      <div style={{
        maxWidth: "800px",
        margin: "0 auto"
      }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "2rem"
        }}>
          <div>
            <h1 style={{fontSize: "2rem", marginBottom: "0.5rem"}}>Rooms</h1>
            <p style={{color: "#999", fontSize: "0.9rem"}}>Logged in as {userEmail}</p>
          </div>
          <div style={{ display: "flex", gap: "10px" }}>
            <button
              onClick={() => navigate("/profile")}
              style={{
                padding: "0.75rem 1.5rem",
                background: "#6366f1",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontWeight: "600"
              }}
            >
              Profile
            </button>
            <button
              onClick={onLogout}
              style={{
                padding: "0.75rem 1.5rem",
                background: "#dc2626",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontWeight: "600"
              }}
            >
              Logout
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
          <h2 style={{fontSize: "1.25rem", marginBottom: "1rem"}}>Create New Room</h2>

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
              Quick Room (Instant QR Code)
            </button>
          </div>

          <div style={{
            textAlign: "center",
            color: "#666",
            fontSize: "0.85rem",
            margin: "1rem 0"
          }}>
            or create a named room
          </div>

          <div style={{display: "flex", gap: "1rem"}}>
            <input
              type="text"
              placeholder="Room name..."
              value={newRoomName}
              onChange={e => setNewRoomName(e.target.value)}
              onKeyDown={e => e.key === "Enter" && createRoom()}
              style={{
                flex: 1,
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
                fontWeight: "600"
              }}
            >
              Create
            </button>
          </div>
        </div>
        
        <div>
          <h2 style={{fontSize: "1.25rem", marginBottom: "1rem"}}>Available Rooms</h2>
          {loading ? (
            <div style={{textAlign: "center", color: "#666", padding: "2rem"}}>
              Loading rooms...
            </div>
          ) : rooms.length === 0 ? (
            <div style={{textAlign: "center", color: "#666", padding: "2rem"}}>
              No rooms yet. Create one above!
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
                  <div style={{fontSize: "1.1rem", fontWeight: "600", marginBottom: "0.5rem"}}>
                    {room.code}
                  </div>
                  <div style={{color: "#999", fontSize: "0.85rem"}}>
                    Created {new Date(room.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Room Modal */}
      {showQuickRoom && (
        <QuickRoomModal
          token={token}
          onClose={() => setShowQuickRoom(false)}
        />
      )}
    </div>
  );
}
