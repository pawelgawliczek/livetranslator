/**
 * MultiSpeakerRoomPage - Real-time Translation Room for Multi-Speaker Sessions
 *
 * Specialized view for rooms with multiple speakers using diarization.
 * Shows speaker-centric UI with N × (N-1) translation display.
 */

import React, { useRef, useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

// Components
import RoomHeader from "../components/room/RoomHeader";
import NetworkStatusIndicator from "../components/room/NetworkStatusIndicator";
import MultiSpeakerMessage from "../components/room/MultiSpeakerMessage";
import MicrophoneButton from "../components/room/MicrophoneButton";
import RoomControls from "../components/room/RoomControls";
import SettingsMenu from "../components/SettingsMenu";
import SoundSettingsModal from "../components/SoundSettingsModal";
import SpeakerDiscoveryModal from "../components/SpeakerDiscoveryModal";
import InviteModal from "../components/InviteModal";
import ParticipantsPanel from "../components/ParticipantsPanel";
import MessageDebugModal from "../components/MessageDebugModal";
import NotificationToast from "../components/NotificationToast";
import AdminLeftToast from "../components/AdminLeftToast";

// Hooks
import usePresenceWebSocket from "../hooks/usePresenceWebSocket";
import useMultiSpeakerRoom from "../hooks/useMultiSpeakerRoom";
import useAudioStream from "../hooks/useAudioStream";

// Utils
import { getUserLanguage, setUserLanguage } from "../utils/languageSync";
import { LANGUAGES, getSelectableLanguages } from "../constants/languages";

export default function MultiSpeakerRoomPage({ token, onLogout }) {
  const { t } = useTranslation();
  const { roomId } = useParams();
  const navigate = useNavigate();

  // Guest Detection
  const isGuest = sessionStorage.getItem('is_guest') === 'true';
  const guestName = sessionStorage.getItem('guest_display_name') || 'Guest';
  const guestLang = sessionStorage.getItem('guest_language') || 'en';

  // Redirect if not authenticated
  useEffect(() => {
    if (!token && !isGuest) {
      navigate('/login');
    }
  }, [token, isGuest, navigate]);

  // Core State
  const [status, setStatus] = useState("idle");
  const [vadStatus, setVadStatus] = useState("idle");
  const [userEmail, setUserEmail] = useState("");
  const [myLanguage, setMyLanguage] = useState(() => {
    const stored = isGuest ? guestLang : getUserLanguage() || null;
    return stored;
  });

  // Sync language with localStorage on every mount and when dependencies change
  // This ensures language changes made outside the room are reflected when returning
  useEffect(() => {
    if (isGuest) {
      // Guests use session storage, no need to sync
      return;
    }

    const currentStoredLanguage = getUserLanguage();
    if (currentStoredLanguage && currentStoredLanguage !== myLanguage) {
      setMyLanguage(currentStoredLanguage);
    }
  }, [roomId, isGuest, myLanguage]); // Re-check when myLanguage changes too

  // Push-to-talk state
  const [pushToTalk, setPushToTalk] = useState(() => {
    const savedPreference = localStorage.getItem('lt_push_to_talk');
    if (savedPreference !== null) {
      return savedPreference === 'true';
    }
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                     (navigator.maxTouchPoints && navigator.maxTouchPoints > 1);
    return isMobile;
  });
  const [isPressing, setIsPressing] = useState(false);

  // Room state
  const [isRoomOwner, setIsRoomOwner] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isRoomAdmin, setIsRoomAdmin] = useState(false);
  const [isPublic, setIsPublic] = useState(false);

  // Modal state
  const [showSettings, setShowSettings] = useState(false);
  const [showSoundSettings, setShowSoundSettings] = useState(false);
  const [showSpeakerDiscovery, setShowSpeakerDiscovery] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [showParticipantsPanel, setShowParticipantsPanel] = useState(false);
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const [debugSegmentId, setDebugSegmentId] = useState(null);

  // Audio settings
  const [audioLevel, setAudioLevel] = useState(0);
  const [audioThreshold, setAudioThreshold] = useState(0.02);
  const [selectedMicDeviceId, setSelectedMicDeviceId] = useState(null);

  // Refs
  const chatEndRef = useRef(null);

  // Multi-speaker room hook
  const multiSpeakerRoom = useMultiSpeakerRoom({
    roomCode: roomId,
    token,
    isGuest,
    myLanguage,
    userEmail
  });

  // Presence WebSocket
  const {
    isConnected: presenceConnected,
    ws: presenceWs,
    participants,
    showWelcome,
    dismissWelcome,
    notifications,
    networkQuality,
    networkRTT
  } = usePresenceWebSocket({
    roomId,
    token,
    isGuest,
    myLanguage,
    initialLanguage: myLanguage,
    onMessage: multiSpeakerRoom.onMessage  // Forward messages to multi-speaker handler
  });

  // Audio Stream
  const audioStream = useAudioStream({
    ws: presenceWs,
    roomId,
    userEmail,
    myLanguage,
    pushToTalk,
    isPressing,
    onStatusChange: setStatus,
    onVADStatusChange: setVadStatus,
    onLevelChange: setAudioLevel,
    threshold: audioThreshold,
    selectedDeviceId: selectedMicDeviceId
  });

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [multiSpeakerRoom.messages]);

  // Fetch user profile
  useEffect(() => {
    if (!token || isGuest) return;

    fetch('/api/profile', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => {
        setUserEmail(data.email);
        setIsAdmin(data.is_admin || false);
      })
      .catch(err => console.error('[Profile] Failed to fetch:', err));
  }, [token, isGuest]);

  // Fetch room info
  useEffect(() => {
    if (!roomId) return;

    const headers = {};
    if (!isGuest && token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    fetch(`/api/rooms/${roomId}`, { headers })
      .then(res => res.json())
      .then(data => {
        console.log('[MultiSpeakerRoom] Room info:', { is_owner: data.is_owner, is_public: data.is_public });
        setIsRoomOwner(data.is_owner || false);
        setIsRoomAdmin(data.is_owner || false);
        setIsPublic(data.is_public || false);
      })
      .catch(err => console.error('[Room] Failed to fetch info:', err));
  }, [roomId, token, isGuest]);

  // Format time
  const formatTime = (isoString) => {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  // Handle language change
  const handleLanguageChange = (newLang) => {
    setMyLanguage(newLang);
    setUserLanguage(newLang);

    if (!isGuest) {
      // Update server
      fetch('/api/profile', {
        method: 'PATCH',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ language: newLang })
      }).catch(err => console.error('[Profile] Failed to update language:', err));
    }

    // Notify via WebSocket
    if (presenceWs && presenceWs.readyState === WebSocket.OPEN) {
      presenceWs.send(JSON.stringify({
        type: 'language_change',
        language: newLang
      }));
    }
  };

  // Detect speaker changes
  const detectSpeakerChanges = () => {
    const messagesWithChange = [];
    let lastSpeakerId = null;

    multiSpeakerRoom.messages.forEach((msg, index) => {
      const currentSpeakerId = msg.speakerInfo?.speaker_id;
      const isNewSpeaker = currentSpeakerId !== lastSpeakerId && index > 0;

      messagesWithChange.push({
        ...msg,
        isNewSpeaker
      });

      lastSpeakerId = currentSpeakerId;
    });

    return messagesWithChange;
  };

  const messagesWithSpeakerChanges = detectSpeakerChanges();

  // Check if we're in discovery phase (no speakers enrolled yet)
  const isInDiscovery = multiSpeakerRoom.speakers.length === 0 && !multiSpeakerRoom.loadingSpeakers;

  // Calculate language counts for header
  const languageCounts = multiSpeakerRoom.speakers.reduce((counts, speaker) => {
    counts[speaker.language] = (counts[speaker.language] || 0) + 1;
    return counts;
  }, {});

  return (
    <div className="h-screen w-screen flex flex-col bg-bg text-fg overflow-hidden">
      {/* Header - Hidden during discovery phase */}
      {!isInDiscovery && (
        <RoomHeader
          roomId={roomId}
          languageCounts={languageCounts}
          languages={LANGUAGES}
          vadStatus={vadStatus}
          vadReady={status === 'recording'}
          onBackClick={() => navigate('/rooms')}
          onMenuClick={() => setShowSettings(true)}
        />
      )}

      {/* Network Status Indicator - Hidden during discovery phase */}
      {!isInDiscovery && (
        <NetworkStatusIndicator
          isConnected={presenceConnected}
          networkQuality={networkQuality}
          networkRTT={networkRTT}
        />
      )}

      {/* Speakers Info Bar */}
      {!multiSpeakerRoom.loadingSpeakers && multiSpeakerRoom.speakers.length > 0 && (
        <div className="bg-card border-b border-border px-4 py-2 flex items-center gap-2 overflow-x-auto">
          <span className="text-xs text-muted flex-shrink-0">Speakers:</span>
          {multiSpeakerRoom.speakers.map(speaker => {
            const langInfo = LANGUAGES.find(l => l.code === speaker.language) || { flag: '🌐', name: speaker.language };
            return (
              <div
                key={speaker.speaker_id}
                className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-bg-secondary text-xs flex-shrink-0"
                style={{ borderLeft: `3px solid ${speaker.color}` }}
              >
                <span className="font-semibold">{speaker.display_name}</span>
                <span className="text-lg">{langInfo.flag}</span>
              </div>
            );
          })}
        </div>
      )}

      {/* Messages Area - Hidden during discovery phase */}
      {!isInDiscovery && (
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-3 flex flex-col gap-3">
          {/* Loading state */}
          {multiSpeakerRoom.loadingSpeakers && (
            <div className="text-center text-muted py-8 px-4 m-auto text-sm">
              Loading speakers...
            </div>
          )}

          {/* Empty state */}
          {!multiSpeakerRoom.loadingSpeakers && messagesWithSpeakerChanges.length === 0 && (
            <div className="text-center text-muted py-8 px-4 m-auto text-sm">
              {t('room.pressToStart')}
            </div>
          )}

          {/* Messages */}
          {messagesWithSpeakerChanges.map((msg) => (
            <MultiSpeakerMessage
              key={msg.segId}
              segId={msg.segId}
              segment={msg.segment}
              speakerInfo={msg.speakerInfo}
              allTranslations={msg.translations}
              isAdmin={isAdmin}
              formatTime={formatTime}
              onDebugClick={(segId) => {
                setDebugSegmentId(segId);
                setDebugModalOpen(true);
              }}
              isNewSpeaker={msg.isNewSpeaker}
            />
          ))}

          {/* Scroll anchor */}
          <div ref={chatEndRef} />
        </div>
      )}

      {/* Placeholder during discovery */}
      {isInDiscovery && (
        <div className="flex-1 flex items-center justify-center bg-bg">
          <div className="text-center text-muted px-4">
            <p className="text-lg mb-2">🎤</p>
            <p className="text-sm">
              {t('discovery.setupInProgress', 'Setting up multi-speaker room...')}
            </p>
          </div>
        </div>
      )}

      {/* Controls - Hidden during discovery phase */}
      {!isInDiscovery && (
        <RoomControls
        pushToTalk={pushToTalk}
        onPushToTalkToggle={() => {
          const newValue = !pushToTalk;
          setPushToTalk(newValue);
          localStorage.setItem('lt_push_to_talk', String(newValue));
        }}
        microphoneButton={
          <MicrophoneButton
            status={status}
            pushToTalk={pushToTalk}
            isPressing={isPressing}
            onPressStart={() => setIsPressing(true)}
            onPressEnd={() => setIsPressing(false)}
          />
        }
      />
      )}

      {/* Modals */}
      {showSettings && (
        <SettingsMenu
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          isGuest={isGuest}
          myLanguage={myLanguage}
          languages={LANGUAGES}
          onLanguageChange={() => {
            setShowSettings(false);
            // Open language picker if needed
          }}
          onShowParticipants={() => {
            setShowSettings(false);
            setShowParticipantsPanel(true);
          }}
          onShowInvite={() => {
            setShowSettings(false);
            setShowInvite(true);
          }}
          onShowCosts={() => {
            setShowSettings(false);
            navigate(`/admin/costs?room_id=${encodeURIComponent(roomId)}`);
          }}
          onShowSound={() => {
            setShowSettings(false);
            setShowSoundSettings(true);
          }}
          onShowSpeakerDiscovery={() => {
            setShowSettings(false);
            setShowSpeakerDiscovery(true);
          }}
          onLogout={onLogout}
          canChangeLanguage={status === 'idle'}
          isRoomAdmin={isRoomAdmin}
          isPublic={isPublic}
          onTogglePublic={async () => {
            const newValue = !isPublic;
            setIsPublic(newValue);
            try {
              await fetch(`/api/rooms/${encodeURIComponent(roomId)}/public`, {
                method: 'POST',
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify({ is_public: newValue })
              });
            } catch (error) {
              console.error('[Public] Failed to toggle:', error);
              setIsPublic(!newValue);
            }
          }}
        />
      )}

      {showSoundSettings && (
        <SoundSettingsModal
          isOpen={showSoundSettings}
          onClose={() => setShowSoundSettings(false)}
          currentLevel={audioLevel}
          threshold={audioThreshold}
          onThresholdChange={setAudioThreshold}
          isActive={status === 'recording'}
          status={vadStatus}
          selectedDeviceId={selectedMicDeviceId}
          onDeviceChange={setSelectedMicDeviceId}
        />
      )}

      {showSpeakerDiscovery && (
        <SpeakerDiscoveryModal
          isOpen={showSpeakerDiscovery}
          onClose={() => setShowSpeakerDiscovery(false)}
          onCancel={() => navigate('/rooms')}
          roomCode={roomId}
          token={token}
          isGuest={isGuest}
          ws={presenceWs}
          onComplete={(speakers) => {
            console.log('[SpeakerDiscovery] Discovery complete:', speakers);
            // Clear any messages accumulated during discovery
            multiSpeakerRoom.clearMessages();
            // Reload speakers from API
            multiSpeakerRoom.refetchSpeakers();
          }}
        />
      )}

      {showInvite && (
        <InviteModal
          isOpen={showInvite}
          onClose={() => setShowInvite(false)}
          roomCode={roomId}
        />
      )}

      {showParticipantsPanel && (
        <ParticipantsPanel
          participants={multiSpeakerRoom.speakers.map(speaker => ({
            email: speaker.display_name,
            language: speaker.language,
            is_speaking: false
          }))}
          languages={LANGUAGES}
          isOpen={showParticipantsPanel}
          onToggle={() => setShowParticipantsPanel(false)}
        />
      )}

      {debugModalOpen && (
        <MessageDebugModal
          isOpen={debugModalOpen}
          roomCode={roomId}
          segmentId={debugSegmentId}
          token={token}
          onClose={() => {
            setDebugModalOpen(false);
            setDebugSegmentId(null);
          }}
        />
      )}

      {/* Notification Toasts */}
      {notifications.map(notif => (
        <NotificationToast
          key={notif.id}
          message={notif.message}
        />
      ))}
    </div>
  );
}
