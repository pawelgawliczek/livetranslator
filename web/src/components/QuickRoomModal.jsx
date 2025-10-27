import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";

export default function QuickRoomModal({ token, onClose }) {
  const navigate = useNavigate();
  const [step, setStep] = useState("creating"); // creating, waiting, joining
  const [roomCode, setRoomCode] = useState(null);
  const [inviteData, setInviteData] = useState(null);
  const [error, setError] = useState(null);
  const [wsConnected, setWsConnected] = useState(false);
  const wsRef = React.useRef(null);

  useEffect(() => {
    createQuickRoom();
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Monitor room for guest joining
  useEffect(() => {
    if (!roomCode || step !== "waiting" || !token) return;

    const connectWs = () => {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/rooms/${encodeURIComponent(roomCode)}?token=${encodeURIComponent(token)}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[QuickRoom] WebSocket connected, waiting for guest...');
        setWsConnected(true);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          console.log('[QuickRoom] Received message:', msg);

          // Detect when another participant joins
          if (msg.type === "user_joined" && msg.triggered_by_user_id) {
            // Check if it's not us joining (compare with our user ID from token)
            try {
              const payload = JSON.parse(atob(token.split('.')[1]));
              const myUserId = payload.sub || payload.user_id;

              if (msg.triggered_by_user_id !== myUserId) {
                // Guest has joined, auto-navigate to room
                console.log('[QuickRoom] Guest joined! Navigating to room...');
                setStep("joining");
                setTimeout(() => {
                  navigate(`/room/${roomCode}`);
                }, 500);
              }
            } catch (e) {
              console.error('[QuickRoom] Failed to decode token:', e);
            }
          }
        } catch (e) {
          console.error("Failed to parse WS message:", e);
        }
      };

      ws.onerror = (err) => {
        console.error('[QuickRoom] WebSocket error:', err);
        setWsConnected(false);
      };

      ws.onclose = () => {
        console.log('[QuickRoom] WebSocket closed');
        setWsConnected(false);
      };
    };

    connectWs();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [roomCode, step, token, navigate]);

  async function createQuickRoom() {
    try {
      // Generate a unique room code (max 12 chars)
      // Format: q-XXXXX where X is base36 timestamp + random suffix
      // Retry up to 3 times if code already exists
      let quickRoomCode;
      let createResp;
      let attempts = 0;
      const maxAttempts = 3;

      while (attempts < maxAttempts) {
        attempts++;

        // Generate code with timestamp + random suffix for uniqueness
        const timestamp = Date.now();
        const random = Math.floor(Math.random() * 1000); // 0-999
        const shortCode = timestamp.toString(36) + random.toString(36);
        quickRoomCode = `q-${shortCode}`.substring(0, 12); // Ensure max 12 chars

        // Create the room
        createResp = await fetch("/api/rooms", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ code: quickRoomCode })
        });

        if (createResp.ok) {
          break; // Success!
        }

        // Check if it's a conflict error
        const errorData = await createResp.json().catch(() => ({}));
        if (createResp.status === 400 && errorData.detail?.includes("already exists")) {
          console.log(`[QuickRoom] Code collision detected (attempt ${attempts}/${maxAttempts}), retrying...`);
          if (attempts >= maxAttempts) {
            throw new Error("Failed to generate unique room code after multiple attempts");
          }
          continue; // Retry with new code
        } else {
          // Different error, don't retry
          throw new Error("Failed to create room");
        }
      }

      if (!createResp.ok) {
        throw new Error("Failed to create room");
      }

      setRoomCode(quickRoomCode);

      // Generate invite code with QR
      const inviteResp = await fetch(`/api/invites/generate/${quickRoomCode}`, {
        method: "POST"
      });

      if (!inviteResp.ok) {
        throw new Error("Failed to generate invite");
      }

      const inviteData = await inviteResp.json();
      setInviteData(inviteData);
      setStep("waiting");

    } catch (e) {
      console.error("Failed to create quick room:", e);
      setError(e.message);
    }
  }

  function copyInviteLink() {
    if (!inviteData) return;
    navigator.clipboard.writeText(inviteData.invite_url);
    // Could add a toast notification here
  }

  if (step === "creating") {
    return (
      <div style={styles.overlay} onClick={onClose}>
        <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
          <div style={styles.modalHeader}>
            <h2 style={styles.modalTitle}>Creating Quick Room...</h2>
            <button style={styles.closeButton} onClick={onClose}>✕</button>
          </div>
          <div style={styles.modalBody}>
            <div style={styles.loadingSpinner}>
              <div style={styles.spinner}></div>
              <p style={styles.loadingText}>Setting up your room...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={styles.overlay} onClick={onClose}>
        <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
          <div style={styles.modalHeader}>
            <h2 style={styles.modalTitle}>Error</h2>
            <button style={styles.closeButton} onClick={onClose}>✕</button>
          </div>
          <div style={styles.modalBody}>
            <p style={{color: "#ef4444", textAlign: "center"}}>
              {error}
            </p>
            <button style={styles.primaryButton} onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      </div>
    );
  }

  if (step === "joining") {
    return (
      <div style={styles.overlay}>
        <div style={styles.modal}>
          <div style={styles.modalBody}>
            <div style={styles.loadingSpinner}>
              <div style={styles.spinner}></div>
              <p style={styles.loadingText}>Guest joined! Entering room...</p>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={styles.overlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <h2 style={styles.modalTitle}>Scan to Join</h2>
          <button style={styles.closeButton} onClick={onClose}>✕</button>
        </div>

        <div style={styles.modalBody}>
          <p style={styles.instructionText}>
            Share this QR code with someone to start translating together.
            You'll both be automatically taken to the room when they scan it.
          </p>

          {inviteData && (
            <div style={styles.qrContainer}>
              <img
                src={inviteData.qr_code}
                alt="QR Code"
                style={styles.qrCode}
              />
            </div>
          )}

          <div style={styles.roomCodeContainer}>
            <span style={styles.roomCodeLabel}>Room:</span>
            <code style={styles.roomCode}>{roomCode}</code>
          </div>

          <div style={styles.wsStatus}>
            {wsConnected ? (
              <span style={styles.statusConnected}>● Waiting for guest...</span>
            ) : (
              <span style={styles.statusDisconnected}>○ Connecting...</span>
            )}
          </div>

          <div style={styles.buttonGroup}>
            <button style={styles.secondaryButton} onClick={copyInviteLink}>
              📋 Copy Link
            </button>
            <button
              style={styles.primaryButton}
              onClick={() => navigate(`/room/${roomCode}`)}
            >
              Enter Room Now
            </button>
          </div>

          <p style={styles.expiryText}>
            This invite expires in {inviteData?.expires_in_minutes || 30} minutes
          </p>
        </div>
      </div>
    </div>
  );
}

const styles = {
  overlay: {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: "rgba(0, 0, 0, 0.8)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1000,
    padding: "1rem"
  },
  modal: {
    background: "#1a1a1a",
    borderRadius: "16px",
    border: "1px solid #333",
    maxWidth: "500px",
    width: "100%",
    maxHeight: "90vh",
    overflow: "auto",
    boxShadow: "0 20px 60px rgba(0,0,0,0.5)"
  },
  modalHeader: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "1.5rem",
    borderBottom: "1px solid #333"
  },
  modalTitle: {
    fontSize: "1.5rem",
    margin: 0,
    color: "white"
  },
  closeButton: {
    background: "none",
    border: "none",
    color: "#999",
    fontSize: "1.5rem",
    cursor: "pointer",
    padding: "0.25rem",
    lineHeight: 1,
    transition: "color 0.2s"
  },
  modalBody: {
    padding: "1.5rem"
  },
  instructionText: {
    color: "#ccc",
    fontSize: "0.95rem",
    lineHeight: "1.5",
    marginBottom: "1.5rem",
    textAlign: "center"
  },
  qrContainer: {
    display: "flex",
    justifyContent: "center",
    marginBottom: "1.5rem"
  },
  qrCode: {
    width: "280px",
    height: "280px",
    borderRadius: "12px",
    border: "2px solid #333",
    background: "white",
    padding: "0.75rem"
  },
  roomCodeContainer: {
    background: "#2a2a2a",
    borderRadius: "8px",
    padding: "0.75rem 1rem",
    marginBottom: "1rem",
    textAlign: "center",
    border: "1px solid #444"
  },
  roomCodeLabel: {
    color: "#999",
    fontSize: "0.85rem",
    marginRight: "0.5rem"
  },
  roomCode: {
    color: "#3b82f6",
    fontSize: "1rem",
    fontFamily: "monospace",
    fontWeight: "600"
  },
  wsStatus: {
    textAlign: "center",
    marginBottom: "1.5rem",
    fontSize: "0.9rem"
  },
  statusConnected: {
    color: "#10b981"
  },
  statusDisconnected: {
    color: "#999"
  },
  buttonGroup: {
    display: "flex",
    gap: "0.75rem",
    marginBottom: "1rem"
  },
  primaryButton: {
    flex: 1,
    padding: "0.875rem 1.5rem",
    background: "#3b82f6",
    color: "white",
    border: "none",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "1rem",
    transition: "background 0.2s"
  },
  secondaryButton: {
    flex: 1,
    padding: "0.875rem 1.5rem",
    background: "#2a2a2a",
    color: "white",
    border: "1px solid #444",
    borderRadius: "8px",
    cursor: "pointer",
    fontWeight: "600",
    fontSize: "1rem",
    transition: "all 0.2s"
  },
  expiryText: {
    color: "#666",
    fontSize: "0.8rem",
    textAlign: "center",
    margin: 0
  },
  loadingSpinner: {
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "1rem",
    padding: "3rem 1rem"
  },
  spinner: {
    width: "50px",
    height: "50px",
    border: "4px solid #333",
    borderTop: "4px solid #3b82f6",
    borderRadius: "50%",
    animation: "spin 1s linear infinite"
  },
  loadingText: {
    color: "#999",
    margin: 0
  }
};

// Add keyframes for spinner animation
if (typeof document !== 'undefined') {
  const styleSheet = document.createElement("style");
  styleSheet.textContent = `
    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(styleSheet);
}
