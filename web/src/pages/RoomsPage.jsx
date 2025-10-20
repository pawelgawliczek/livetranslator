import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function RoomsPage({ token, onLogout }) {
  const navigate = useNavigate();
  const [newRoomName, setNewRoomName] = useState("");
  const [userEmail, setUserEmail] = useState("");
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  
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
  
  function createRoom() {
    if (!newRoomName.trim()) {
      alert("Please enter a room name");
      return;
    }
    const roomId = newRoomName.toLowerCase().replace(/[^a-z0-9]+/g, '-');
    navigate(`/room/${roomId}`);
  }
  
  function joinRoom(roomId) {
    navigate(`/room/${roomId}`);
  }
  
  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0a0a",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif",
      paddingBottom: "2rem"
    }}>
      {/* Mobile Header */}
      <div style={{
        background: "#1a1a1a",
        borderBottom: "1px solid #333",
        padding: "1rem",
        position: "sticky",
        top: 0,
        zIndex: 10
      }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "0.5rem"
        }}>
          <h1 style={{fontSize: "1.5rem", margin: 0}}>LiveTranslator</h1>
          <button
            onClick={onLogout}
            style={{
              padding: "0.5rem 1rem",
              background: "transparent",
              border: "1px solid #666",
              borderRadius: "8px",
              color: "white",
              cursor: "pointer",
              fontSize: "0.9rem"
            }}
          >
            Logout
          </button>
        </div>
        <p style={{color: "#999", fontSize: "0.85rem", margin: 0}}>
          {userEmail}
        </p>
      </div>
      
      <div style={{padding: "1rem"}}>
        {/* Create New Room */}
        <div style={{
          background: "#1a1a1a",
          border: "1px solid #333",
          borderRadius: "12px",
          padding: "1.5rem",
          marginBottom: "1.5rem"
        }}>
          <h2 style={{fontSize: "1.25rem", marginBottom: "0.5rem"}}>
            ➕ Create New Room
          </h2>
          <p style={{color: "#999", marginBottom: "1rem", fontSize: "0.9rem"}}>
            Start a new translation session
          </p>
          
          <div style={{display: "flex", flexDirection: "column", gap: "0.75rem"}}>
            <input
              type="text"
              placeholder="Enter room name..."
              value={newRoomName}
              onChange={e => setNewRoomName(e.target.value)}
              onKeyPress={e => e.key === 'Enter' && createRoom()}
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
            <button
              onClick={createRoom}
              style={{
                padding: "1rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "12px",
                fontSize: "1rem",
                fontWeight: "600",
                cursor: "pointer",
                width: "100%",
                WebkitAppearance: "none"
              }}
            >
              Create Room
            </button>
          </div>
        </div>
        
        {/* Available Rooms */}
        <h2 style={{fontSize: "1.25rem", marginBottom: "1rem"}}>Available Rooms</h2>
        
        {loading ? (
          <div style={{textAlign: "center", color: "#666", padding: "2rem"}}>
            Loading rooms...
          </div>
        ) : rooms.length === 0 ? (
          <div style={{
            background: "#1a1a1a",
            border: "1px solid #333",
            borderRadius: "12px",
            padding: "2rem",
            textAlign: "center",
            color: "#666"
          }}>
            No rooms available. Create one to get started!
          </div>
        ) : (
          <div style={{
            display: "flex",
            flexDirection: "column",
            gap: "1rem"
          }}>
            {rooms.map(room => (
              <div
                key={room.code}
                onClick={() => joinRoom(room.code)}
                style={{
                  background: "#1a1a1a",
                  border: "1px solid #333",
                  borderRadius: "12px",
                  padding: "1.25rem",
                  cursor: "pointer"
                }}
              >
                <h3 style={{fontSize: "1.1rem", marginBottom: "0.5rem"}}>{room.code}</h3>
                <p style={{color: "#999", fontSize: "0.85rem", marginBottom: "1rem"}}>
                  Translation room
                </p>
                <div style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center"
                }}>
                  <span style={{color: "#666", fontSize: "0.8rem"}}>
                    Created {new Date(room.created_at).toLocaleDateString()}
                  </span>
                  <button
                    style={{
                      padding: "0.5rem 1rem",
                      background: "#3b82f6",
                      color: "white",
                      border: "none",
                      borderRadius: "8px",
                      fontSize: "0.85rem",
                      fontWeight: "600",
                      cursor: "pointer"
                    }}
                  >
                    Join
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
