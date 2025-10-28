import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import Modal from "./ui/Modal";
import Button from "./ui/Button";

export default function QuickRoomModal({ token, onClose }) {
  const { t } = useTranslation();
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
            try {
              const payload = JSON.parse(atob(token.split('.')[1]));
              const myUserId = payload.sub || payload.user_id;

              if (msg.triggered_by_user_id !== myUserId) {
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
      let quickRoomCode;
      let createResp;
      let attempts = 0;
      const maxAttempts = 3;

      while (attempts < maxAttempts) {
        attempts++;

        const timestamp = Date.now();
        const random = Math.floor(Math.random() * 1000);
        const shortCode = timestamp.toString(36) + random.toString(36);
        quickRoomCode = `q-${shortCode}`.substring(0, 12);

        createResp = await fetch("/api/rooms", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`
          },
          body: JSON.stringify({ code: quickRoomCode })
        });

        if (createResp.ok) {
          break;
        }

        const errorData = await createResp.json().catch(() => ({}));
        if (createResp.status === 400 && errorData.detail?.includes("already exists")) {
          console.log(`[QuickRoom] Code collision detected (attempt ${attempts}/${maxAttempts}), retrying...`);
          if (attempts >= maxAttempts) {
            throw new Error("Failed to generate unique room code after multiple attempts");
          }
          continue;
        } else {
          throw new Error("Failed to create room");
        }
      }

      if (!createResp.ok) {
        throw new Error("Failed to create room");
      }

      setRoomCode(quickRoomCode);

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
  }

  if (step === "creating") {
    return (
      <Modal isOpen={true} onClose={onClose} title={t('quickRoom.creatingTitle')}>
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="w-12 h-12 border-4 border-border border-t-accent rounded-full animate-spin"></div>
          <p className="text-muted">{t('quickRoom.settingUp')}</p>
        </div>
      </Modal>
    );
  }

  if (error) {
    return (
      <Modal isOpen={true} onClose={onClose} title={t('quickRoom.error')}>
        <p className="text-red-500 text-center mb-6">{error}</p>
        <Button variant="primary" onClick={onClose} className="w-full">
          Close
        </Button>
      </Modal>
    );
  }

  if (step === "joining") {
    return (
      <Modal isOpen={true} onClose={() => {}} title="">
        <div className="flex flex-col items-center gap-4 py-12">
          <div className="w-12 h-12 border-4 border-border border-t-accent rounded-full animate-spin"></div>
          <p className="text-muted">{t('quickRoom.guestJoined')}</p>
        </div>
      </Modal>
    );
  }

  return (
    <Modal isOpen={true} onClose={onClose} title={t('quickRoom.scanTitle')}>
      <p className="text-muted text-center mb-6 leading-relaxed">
        {t('quickRoom.qrInstructions')}
      </p>

      {inviteData && (
        <div className="flex justify-center mb-6">
          <img
            src={inviteData.qr_code}
            alt="QR Code"
            className="w-[min(280px,70vw)] h-[min(280px,70vw)] rounded-lg border-2 border-border bg-white p-3"
          />
        </div>
      )}

      <div className="bg-bg-secondary rounded-lg p-3 mb-4 text-center border border-border">
        <span className="text-muted text-sm mr-2">{t('quickRoom.roomLabel')}</span>
        <code className="text-accent text-base font-mono font-semibold">{roomCode}</code>
      </div>

      <div className="text-center mb-6 text-sm">
        {wsConnected ? (
          <span className="text-green-500">● {t('quickRoom.waitingForGuest')}</span>
        ) : (
          <span className="text-muted">○ {t('quickRoom.connecting')}</span>
        )}
      </div>

      <div className="flex gap-3 mb-4 flex-wrap">
        <Button
          variant="secondary"
          onClick={copyInviteLink}
          className="flex-1 min-w-[150px]"
        >
          {t('quickRoom.copyLink')}
        </Button>
        <Button
          variant="primary"
          onClick={() => navigate(`/room/${roomCode}`)}
          className="flex-1 min-w-[150px]"
        >
          {t('quickRoom.enterNow')}
        </Button>
      </div>

      <p className="text-muted text-xs text-center">
        {t('quickRoom.expiresInMinutes', { minutes: inviteData?.expires_in_minutes || 30 })}
      </p>
    </Modal>
  );
}
