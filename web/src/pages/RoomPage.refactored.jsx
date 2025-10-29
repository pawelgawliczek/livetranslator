/**
 * RoomPage - Real-time Translation Room
 *
 * Refactored version using extracted components and custom hooks.
 * Orchestrates all room functionality with clean separation of concerns.
 */

import React, { useRef, useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

// Legacy components (not yet extracted)
import InviteModal from "../components/InviteModal";
import SettingsMenu from "../components/SettingsMenu";
import SoundSettingsModal from "../components/SoundSettingsModal";
import ParticipantsPanel from "../components/ParticipantsPanel";
import MessageDebugModal from "../components/MessageDebugModal";

// Extracted Room Components
import RoomHeader from "../components/room/RoomHeader";
import NetworkStatusIndicator from "../components/room/NetworkStatusIndicator";
import LanguagePickerModal from "../components/room/LanguagePickerModal";
import CostsModal from "../components/room/CostsModal";
import WelcomeBanner from "../components/room/WelcomeBanner";
import AdminLeaveModal from "../components/room/AdminLeaveModal";
import RoomExpirationModal from "../components/room/RoomExpirationModal";
import MicrophoneButton from "../components/room/MicrophoneButton";
import RoomControls from "../components/room/RoomControls";
import ChatMessageList from "../components/room/ChatMessageList";

// Legacy toast components
import NotificationToast from "../components/NotificationToast";
import AdminLeftToast from "../components/AdminLeftToast";

// Custom Hooks
import usePresenceWebSocket from "../hooks/usePresenceWebSocket";
import useRoomWebSocket from "../hooks/useRoomWebSocket";
import useAudioStream from "../hooks/useAudioStream";

// Utils
import { getUserLanguage, setUserLanguage, syncLanguageWithProfile } from "../utils/languageSync";
import { LANGUAGES, getSelectableLanguages } from "../constants/languages";

export default function RoomPage({ token, onLogout }) {
  const { t } = useTranslation();
  const { roomId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  // ============================================================================
  // Guest Detection
  // ============================================================================
  const isGuest = sessionStorage.getItem('is_guest') === 'true';
  const guestName = sessionStorage.getItem('guest_display_name') || 'Guest';
  const guestLang = sessionStorage.getItem('guest_language') || 'en';

  // If no token and not a guest, redirect to login
  useEffect(() => {
    if (!token && !isGuest) {
      navigate('/login');
    }
  }, [token, isGuest, navigate]);

  // ============================================================================
  // Core State
  // ============================================================================
  const [status, setStatus] = useState("idle");
  const [vadStatus, setVadStatus] = useState("idle");
  const [userEmail, setUserEmail] = useState("");

  // Language state
  const [myLanguage, setMyLanguage] = useState(() => {
    // For guests, use their session language; for logged-in users, use unified language
    const stored = isGuest ? guestLang : getUserLanguage();
    return stored || null;
  });

  // Push-to-talk state
  const [pushToTalk, setPushToTalk] = useState(() => {
    const savedPreference = localStorage.getItem('lt_push_to_talk');
    if (savedPreference !== null) {
      return savedPreference === 'true';
    }
    // Default based on device type: mobile = enabled, desktop = disabled
    const isMobile = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) ||
                     (navigator.maxTouchPoints && navigator.maxTouchPoints > 1);
    return isMobile;
  });
  const [isPressing, setIsPressing] = useState(false);

  // Room state
  const [isRoomOwner, setIsRoomOwner] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isRoomAdmin, setIsRoomAdmin] = useState(false);
  const [roomStatus, setRoomStatus] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [isPublic, setIsPublic] = useState(false);
  const [isPublicInitialized, setIsPublicInitialized] = useState(false);

  // Persistence state
  const [persistenceEnabled, setPersistenceEnabled] = useState(false);
  const [persistenceInitialized, setPersistenceInitialized] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);

  // Modal state
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [showCosts, setShowCosts] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showSoundSettings, setShowSoundSettings] = useState(false);
  const [showAdminLeaveWarning, setShowAdminLeaveWarning] = useState(false);
  const [showExpirationModal, setShowExpirationModal] = useState(false);
  const [showParticipantsPanel, setShowParticipantsPanel] = useState(false);

  // Debug modal state
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const [debugSegmentId, setDebugSegmentId] = useState(null);

  // Costs state
  const [costs, setCosts] = useState(null);

  // Test mode for Sound Settings
  const [testMode, setTestMode] = useState(false);
  const testAudioContextRef = useRef(null);
  const testProcessorRef = useRef(null);
  const testStreamRef = useRef(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const [audioThreshold, setAudioThreshold] = useState(0.02);

  // Refs
  const chatEndRef = useRef(null);

  // ============================================================================
  // Custom Hooks
  // ============================================================================

  // Room WebSocket (handles message processing and segment rendering)
  const roomWebSocket = useRoomWebSocket({
    myLanguage,
    userEmail
  });

  // Presence WebSocket (handles presence events, network monitoring, notifications)
  const {
    isConnected: presenceConnected,
    ws: presenceWs,
    participants,
    languageCounts,
    showWelcome,
    notifications,
    networkQuality,
    networkRTT
  } = usePresenceWebSocket({
    roomId,
    token,
    isGuest,
    myLanguage,
    initialLanguage: myLanguage,
    onMessage: roomWebSocket.onMessage  // Forward STT/translation messages
  });

  // Audio Stream (handles audio capture, VAD, and streaming)
  const audioStream = useAudioStream({
    ws: presenceWs,
    roomId,
    myLanguage,
    pushToTalk,
    isPressing,
    sendInterval: getSendIntervalForQuality(networkQuality),
    networkQuality,
    onStatusChange: setStatus,
    onVadStatusChange: setVadStatus
  });

  // ============================================================================
  // Helper Functions
  // ============================================================================

  function getSendIntervalForQuality(quality) {
    switch (quality) {
      case 'high':
        return 300;  // ~256 Kbps
      case 'medium':
        return 600;  // ~128 Kbps
      case 'low':
        return 1000; // ~77 Kbps
      default:
        return 300;
    }
  }

  function formatTime(isoString) {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return "";
    }
  }

  function formatCountdown(milliseconds) {
    if (milliseconds === null || milliseconds === undefined) return "";
    const minutes = Math.floor(milliseconds / 60000);
    const seconds = Math.floor((milliseconds % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }

  // ============================================================================
  // User Profile Loading
  // ============================================================================

  useEffect(() => {
    if (isGuest) {
      setUserEmail(guestName);
      return;
    }

    if (!token) return;

    fetch('/api/profile', {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => {
        if (!r.ok) throw new Error('Failed to fetch profile');
        return r.json();
      })
      .then(data => {
        setUserEmail(data.email || 'User');
        setIsAdmin(data.is_admin || false);
      })
      .catch(e => console.error('[Profile] Failed to load:', e));
  }, [token, isGuest, guestName]);

  // ============================================================================
  // Room Status Polling
  // ============================================================================

  useEffect(() => {
    if (!roomId || !token) return;

    const fetchRoomStatus = async () => {
      try {
        const response = await fetch(`/api/rooms/${encodeURIComponent(roomId)}/status`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!response.ok) return;

        const data = await response.json();
        setRoomStatus(data);
        setIsRoomAdmin(data.is_admin || false);

        // Calculate time remaining
        if (!data.admin_present && data.admin_left_at) {
          const adminLeftTime = new Date(data.admin_left_at).getTime();
          const expiresAt = adminLeftTime + (15 * 60 * 1000); // 15 minutes
          const remaining = expiresAt - Date.now();
          setTimeRemaining(remaining > 0 ? remaining : 0);
        } else {
          setTimeRemaining(null);
        }
      } catch (error) {
        console.error('[RoomStatus] Failed to fetch:', error);
      }
    };

    fetchRoomStatus();
    const interval = setInterval(fetchRoomStatus, 10000); // Poll every 10s

    return () => clearInterval(interval);
  }, [roomId, token]);

  // ============================================================================
  // Room Expiration Countdown
  // ============================================================================

  useEffect(() => {
    if (!roomStatus || roomStatus.admin_present || !roomStatus.admin_left_at) {
      setShowExpirationModal(false);
      return;
    }

    const updateCountdown = () => {
      const adminLeftTime = new Date(roomStatus.admin_left_at).getTime();
      const expiresAt = adminLeftTime + (15 * 60 * 1000);
      const remaining = expiresAt - Date.now();

      if (remaining <= 0) {
        setTimeRemaining(0);
        setShowExpirationModal(true);
      } else {
        setTimeRemaining(remaining);
        if (remaining <= 60000 && !isRoomAdmin) {
          setShowExpirationModal(true);
        }
      }
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);

    return () => clearInterval(interval);
  }, [roomStatus, isRoomAdmin]);

  // ============================================================================
  // Room Owner Check
  // ============================================================================

  useEffect(() => {
    if (!roomId || !token || isGuest) return;

    fetch(`/api/rooms/${encodeURIComponent(roomId)}/check-owner`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        setIsRoomOwner(data.is_owner || false);
      })
      .catch(e => console.error('[RoomOwner] Failed to check:', e));
  }, [roomId, token, isGuest]);

  // ============================================================================
  // Persistence Settings
  // ============================================================================

  useEffect(() => {
    if (!roomId || !token || isGuest) return;

    fetch(`/api/rooms/${encodeURIComponent(roomId)}/persistence`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        setPersistenceEnabled(data.enabled || false);
        setPersistenceInitialized(true);
      })
      .catch(e => {
        console.error('[Persistence] Failed to fetch:', e);
        setPersistenceInitialized(true);
      });
  }, [roomId, token, isGuest]);

  // ============================================================================
  // Public/Private Room Setting
  // ============================================================================

  useEffect(() => {
    if (!roomId || !token || isGuest) return;

    fetch(`/api/rooms/${encodeURIComponent(roomId)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        setIsPublic(data.is_public || false);
        setIsPublicInitialized(true);
      })
      .catch(e => {
        console.error('[RoomPublic] Failed to fetch:', e);
        setIsPublicInitialized(true);
      });
  }, [roomId, token, isGuest]);

  // ============================================================================
  // History Loading
  // ============================================================================

  const fetchHistory = async () => {
    if (!roomId || !myLanguage || isGuest) {
      setLoadingHistory(false);
      return;
    }

    if (!persistenceEnabled) {
      setLoadingHistory(false);
      return;
    }

    setLoadingHistory(true);

    try {
      console.log(`[History] Fetching: room=${roomId}, target=${myLanguage}`);
      const response = await fetch(
        `/api/history/room/${encodeURIComponent(roomId)}?target_lang=${encodeURIComponent(myLanguage)}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );

      if (!response.ok) {
        console.error(`[History] HTTP ${response.status}: ${response.statusText}`);
        setLoadingHistory(false);
        return;
      }

      const data = await response.json();
      console.log(`[History] Loaded ${data.count} segments`);

      // Clear old history segments (keep live segments from current session)
      const now = Date.now();
      const recentThreshold = now - 30000;
      const keysToDelete = [];

      for (const [key, msg] of roomWebSocket.segsRef.current.entries()) {
        const msgTime = msg.ts_iso ? new Date(msg.ts_iso).getTime() : now;
        if (msgTime < recentThreshold) {
          keysToDelete.push(key);
        }
      }

      keysToDelete.forEach(key => roomWebSocket.segsRef.current.delete(key));

      // Load history into chat
      if (data.segments && data.segments.length > 0) {
        data.segments.forEach(seg => {
          const id = parseInt(seg.segment_id) || Date.now();

          roomWebSocket.segsRef.current.set(`s-${id}`, {
            type: "stt_final",
            segment_id: id,
            text: seg.original_text,
            lang: seg.source_lang,
            final: true,
            speaker: seg.speaker,
            ts_iso: seg.timestamp
          });

          if (seg.translated_text && seg.translated_text !== seg.original_text) {
            roomWebSocket.segsRef.current.set(`t-${id}`, {
              type: "translation_final",
              segment_id: id,
              text: seg.translated_text,
              src: seg.source_lang,
              tgt: seg.target_lang,
              final: true,
              ts_iso: seg.timestamp
            });
          }
        });
        roomWebSocket.scheduleRender();
      }
    } catch (e) {
      console.error("[History] Failed to fetch:", e);
    } finally {
      setLoadingHistory(false);
    }
  };

  useEffect(() => {
    if (persistenceInitialized) {
      fetchHistory();
    }
  }, [roomId, myLanguage, persistenceEnabled, persistenceInitialized]);

  // ============================================================================
  // Language Change Handler
  // ============================================================================

  const handleLanguageChange = async (newLanguage) => {
    // Update local state
    setMyLanguage(newLanguage);

    // For logged-in users, sync language to UI, localStorage, and backend
    if (!isGuest) {
      setUserLanguage(newLanguage);

      // Sync with backend profile if user has token
      if (token) {
        await syncLanguageWithProfile(token, newLanguage);
      }
    } else {
      // For guests, update session storage and also sync to localStorage for next visit
      sessionStorage.setItem('guest_language', newLanguage);
      setUserLanguage(newLanguage);
    }

    console.log('[RoomPage] Language changed to:', newLanguage);
  };

  // ============================================================================
  // Recording Controls
  // ============================================================================

  const handleStart = async () => {
    if (audioStream.isRecording) return;

    // Stop test mode if active
    if (testMode) {
      await handleTestMode(false);
    }

    // Prevent starting if room is about to expire
    if (!isRoomAdmin && roomStatus && !roomStatus.admin_present && timeRemaining !== null && timeRemaining < 60000) {
      alert("Cannot start recording: Room is closing soon. Recording will be available if the admin rejoins.");
      return;
    }

    await audioStream.start();
  };

  const handleStop = () => {
    audioStream.stop();
  };

  // ============================================================================
  // Back Button Handler
  // ============================================================================

  const handleBackClick = () => {
    if (isRoomAdmin && audioStream.isRecording) {
      setShowAdminLeaveWarning(true);
    } else {
      navigate('/');
    }
  };

  // ============================================================================
  // Test Mode (Sound Settings)
  // ============================================================================

  const handleTestMode = async (enabled) => {
    if (enabled) {
      // Stop recording if active
      if (audioStream.isRecording) {
        audioStream.stop();
      }

      // Start test audio capture
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: { ideal: 48000 },
            echoCancellation: true,
            noiseSuppression: false,
            autoGainControl: true
          }
        });

        testStreamRef.current = stream;

        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(4096, 1, 1);

        testAudioContextRef.current = audioContext;
        testProcessorRef.current = processor;

        processor.onaudioprocess = (e) => {
          const inputData = e.inputBuffer.getChannelData(0);
          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i];
          }
          const rms = Math.sqrt(sum / inputData.length);
          setAudioLevel(rms);
        };

        source.connect(processor);
        processor.connect(audioContext.destination);

        setTestMode(true);
      } catch (error) {
        console.error('[TestMode] Failed to start:', error);
        alert('Failed to access microphone for test mode');
      }
    } else {
      // Stop test audio capture
      if (testStreamRef.current) {
        testStreamRef.current.getTracks().forEach(track => track.stop());
        testStreamRef.current = null;
      }
      if (testProcessorRef.current) {
        testProcessorRef.current.disconnect();
        testProcessorRef.current = null;
      }
      if (testAudioContextRef.current) {
        testAudioContextRef.current.close();
        testAudioContextRef.current = null;
      }
      setAudioLevel(0);
      setTestMode(false);
    }
  };

  // ============================================================================
  // Auto-scroll
  // ============================================================================

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [roomWebSocket.lines]);

  // ============================================================================
  // Render
  // ============================================================================

  const myLang = LANGUAGES.find(l => l.code === myLanguage);

  return (
    <div className="h-screen flex flex-col bg-gray-950 text-white font-sans overflow-hidden">
      {/* Room Header */}
      <RoomHeader
        roomId={roomId}
        vadStatus={vadStatus}
        vadReady={audioStream.vadReady}
        languageCounts={languageCounts}
        onBackClick={handleBackClick}
        onMenuClick={() => setShowSettings(true)}
      />

      {/* Network Status Indicator */}
      {networkQuality !== 'unknown' && (
        <NetworkStatusIndicator
          quality={networkQuality}
          rtt={networkRTT}
        />
      )}

      {/* Welcome Banner */}
      {showWelcome && (
        <WelcomeBanner onDismiss={() => {}} />
      )}

      {/* Admin Leave Warning Modal */}
      {showAdminLeaveWarning && (
        <AdminLeaveModal
          onCancel={() => setShowAdminLeaveWarning(false)}
          onConfirm={() => {
            setShowAdminLeaveWarning(false);
            navigate('/');
          }}
        />
      )}

      {/* Room Expiration Modal */}
      {showExpirationModal && timeRemaining !== null && (
        <RoomExpirationModal
          timeRemaining={timeRemaining}
          formatCountdown={formatCountdown}
          onClose={() => navigate('/')}
        />
      )}

      {/* Language Picker Modal */}
      {showLangPicker && (
        <LanguagePickerModal
          currentLanguage={myLanguage}
          onSelectLanguage={(lang) => {
            handleLanguageChange(lang);
            setShowLangPicker(false);
          }}
          onClose={() => setShowLangPicker(false)}
        />
      )}

      {/* Costs Modal */}
      {showCosts && (
        <CostsModal
          costs={costs}
          onClose={() => setShowCosts(false)}
        />
      )}

      {/* Chat Messages */}
      <ChatMessageList
        messages={roomWebSocket.lines}
        isAdmin={isAdmin}
        loadingHistory={loadingHistory}
        formatTime={formatTime}
        chatEndRef={chatEndRef}
        onDebugClick={(segmentId) => {
          setDebugSegmentId(segmentId);
          setDebugModalOpen(true);
        }}
        showAdminLeftToast={roomStatus && !roomStatus.admin_present && !isRoomAdmin}
        timeRemaining={timeRemaining}
        formatCountdown={formatCountdown}
      />

      {/* Room Controls */}
      <RoomControls
        myLanguage={myLanguage}
        myLang={myLang}
        onLanguageClick={() => setShowLangPicker(true)}
        onParticipantsClick={() => setShowParticipantsPanel(true)}
        onCostsClick={async () => {
          try {
            const response = await fetch(`/api/costs/room/${encodeURIComponent(roomId)}`, {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            const data = await response.json();
            setCosts(data);
            setShowCosts(true);
          } catch (error) {
            console.error('[Costs] Failed to fetch:', error);
          }
        }}
      />

      {/* Microphone Button */}
      <MicrophoneButton
        status={status}
        vadReady={audioStream.vadReady}
        pushToTalk={pushToTalk}
        isPressing={isPressing}
        onStart={handleStart}
        onStop={handleStop}
        onPressStart={() => setIsPressing(true)}
        onPressEnd={() => setIsPressing(false)}
      />

      {/* Legacy Modals (not yet refactored) */}
      {showInvite && (
        <InviteModal
          roomId={roomId}
          onClose={() => setShowInvite(false)}
        />
      )}

      {showSettings && (
        <SettingsMenu
          onClose={() => setShowSettings(false)}
          onInvite={() => {
            setShowSettings(false);
            setShowInvite(true);
          }}
          onSoundSettings={() => {
            setShowSettings(false);
            setShowSoundSettings(true);
          }}
          onLogout={onLogout}
          token={token}
          roomId={roomId}
          isRoomOwner={isRoomOwner}
          persistenceEnabled={persistenceEnabled}
          setPersistenceEnabled={setPersistenceEnabled}
          onPersistenceChange={(enabled) => {
            setPersistenceEnabled(enabled);
            if (enabled && persistenceInitialized) {
              fetchHistory();
            }
          }}
          isPublic={isPublic}
          setIsPublic={setIsPublic}
          isPublicInitialized={isPublicInitialized}
          isGuest={isGuest}
        />
      )}

      {showSoundSettings && (
        <SoundSettingsModal
          onClose={() => setShowSoundSettings(false)}
          audioLevel={audioLevel}
          audioThreshold={audioThreshold}
          setAudioThreshold={setAudioThreshold}
          testMode={testMode}
          setTestMode={handleTestMode}
          pushToTalk={pushToTalk}
          setPushToTalk={(enabled) => {
            setPushToTalk(enabled);
            localStorage.setItem('lt_push_to_talk', enabled.toString());
          }}
        />
      )}

      {showParticipantsPanel && (
        <ParticipantsPanel
          participants={participants}
          onClose={() => setShowParticipantsPanel(false)}
        />
      )}

      {debugModalOpen && (
        <MessageDebugModal
          segmentId={debugSegmentId}
          messages={roomWebSocket.segsRef.current}
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
