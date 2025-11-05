/**
 * RoomPage - Real-time Translation Room
 *
 * Refactored version using extracted components and custom hooks.
 * Orchestrates all room functionality with clean separation of concerns.
 */

import React, { useRef, useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

// Legacy components (not yet extracted)
import InviteModal from "../components/InviteModal";
import SettingsMenu from "../components/SettingsMenu";
import SoundSettingsModal from "../components/SoundSettingsModal";
import ParticipantsPanel from "../components/ParticipantsPanel";
import MessageDebugModal from "../components/MessageDebugModal";
import { TTSControls } from "../components/TTSControls";

// Extracted Room Components
import RoomHeader from "../components/room/RoomHeader";
import NetworkStatusIndicator from "../components/room/NetworkStatusIndicator";
import LanguagePickerModal from "../components/room/LanguagePickerModal";
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
import { useTTS } from "../hooks/useTTS";

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

  // Add animations for processing indicator and speaking status
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
      }
      .processing-spinner {
        display: inline-block;
        animation: spin 1s linear infinite;
      }
      .debug-icon {
        position: absolute;
        top: 0.35rem;
        right: 0.35rem;
        font-size: 0.8rem;
        cursor: pointer;
        opacity: 0.4;
        transition: opacity 0.2s ease, transform 0.2s ease;
        padding: 0.2rem;
        line-height: 1;
        user-select: none;
        z-index: 10;
      }
      .debug-icon:hover {
        opacity: 1;
        transform: scale(1.15);
      }
    `;
    document.head.appendChild(style);
    return () => document.head.removeChild(style);
  }, []);

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
  const [showInvite, setShowInvite] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showSoundSettings, setShowSoundSettings] = useState(false);
  const [showTTSSettings, setShowTTSSettings] = useState(false);
  const [showAdminLeaveWarning, setShowAdminLeaveWarning] = useState(false);
  const [showExpirationModal, setShowExpirationModal] = useState(false);
  const [showParticipantsPanel, setShowParticipantsPanel] = useState(false);

  // Debug modal state
  const [debugModalOpen, setDebugModalOpen] = useState(false);
  const [debugSegmentId, setDebugSegmentId] = useState(null);

  // Test mode for Sound Settings
  const [testMode, setTestMode] = useState(false);
  const testAudioContextRef = useRef(null);
  const testProcessorRef = useRef(null);
  const testStreamRef = useRef(null);
  const [audioLevel, setAudioLevel] = useState(0);
  const [audioThreshold, setAudioThreshold] = useState(0.02);
  const [selectedMicDeviceId, setSelectedMicDeviceId] = useState(null);

  // TTS state
  const [ttsEnabled, setTtsEnabled] = useState(false);
  const [ttsVoices, setTtsVoices] = useState({});
  const [userTTSSettings, setUserTTSSettings] = useState({ volume: 0.8 });

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
    onMessage: roomWebSocket.onMessage  // Forward STT/translation messages
  });

  // Audio Stream (handles audio capture, VAD, and streaming)
  const audioStream = useAudioStream({
    ws: presenceWs,
    roomId,
    userEmail,
    myLanguage,
    pushToTalk,
    isPressing,
    sendInterval: getSendIntervalForQuality(networkQuality),
    networkQuality,
    onStatusChange: setStatus,
    onVadStatusChange: setVadStatus,
    threshold: audioThreshold,
    deviceId: selectedMicDeviceId
  });

  // TTS Hook (handles text-to-speech audio playback)
  const { playAudio, isPlaying } = useTTS({
    enabled: ttsEnabled,
    volume: userTTSSettings.volume || 0.8
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

  const formatTime = useCallback((isoString) => {
    if (!isoString) return "";
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
    } catch {
      return "";
    }
  }, []);

  const formatCountdown = useCallback((milliseconds) => {
    if (milliseconds === null || milliseconds === undefined) return "";
    const minutes = Math.floor(milliseconds / 60000);
    const seconds = Math.floor((milliseconds % 60000) / 1000);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  }, []);

  const handleDebugClick = useCallback((segmentId) => {
    setDebugSegmentId(segmentId);
    setDebugModalOpen(true);
  }, [isAdmin]);

  // ============================================================================
  // Adaptive Send Interval Logging
  // ============================================================================

  const prevSendIntervalRef = useRef(null);

  useEffect(() => {
    const newInterval = getSendIntervalForQuality(networkQuality);

    if (prevSendIntervalRef.current !== null && newInterval !== prevSendIntervalRef.current) {
      console.log(`[Adaptive] Changing send interval: ${prevSendIntervalRef.current}ms → ${newInterval}ms (quality: ${networkQuality})`);
    }

    prevSendIntervalRef.current = newInterval;
  }, [networkQuality]);

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

        // Load audio settings from profile
        if (data.audio_threshold !== undefined && data.audio_threshold !== null) {
          setAudioThreshold(data.audio_threshold);
        }
        if (data.preferred_mic_device_id) {
          setSelectedMicDeviceId(data.preferred_mic_device_id);
        }
      })
      .catch(e => console.error('[Profile] Failed to load:', e));
  }, [token, isGuest, guestName]);

  // ============================================================================
  // TTS Settings Loading
  // ============================================================================

  useEffect(() => {
    if (!roomId) return;

    if (isGuest) {
      // Guest: load from localStorage
      const storedEnabled = localStorage.getItem(`tts_enabled_${roomId}`);
      const storedVoices = localStorage.getItem(`tts_voices_${roomId}`);

      if (storedEnabled !== null) {
        setTtsEnabled(JSON.parse(storedEnabled));
      }
      if (storedVoices) {
        setTtsVoices(JSON.parse(storedVoices));
      }
      console.log('[TTS] Guest settings loaded from localStorage');
    } else if (token) {
      // Logged-in user: load from API
      fetch(`/api/rooms/${encodeURIComponent(roomId)}/tts/settings`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          setTtsEnabled(data.tts_enabled || false);
          setTtsVoices(data.tts_voice_overrides || {});
          console.log('[TTS] Room settings loaded:', data);
        })
        .catch(err => console.error('[TTS] Failed to load room settings:', err));

      // Load user TTS preferences
      fetch('/api/profile/tts', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          setUserTTSSettings(data);
          console.log('[TTS] User settings loaded:', data);
        })
        .catch(err => console.error('[TTS] Failed to load user settings:', err));
    }
  }, [roomId, token, isGuest]);

  // ============================================================================
  // TTS Audio Event Handler
  // ============================================================================

  useEffect(() => {
    if (!presenceWs) return;

    const handleMessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        // Handle TTS audio events
        if (data.type === 'tts_audio') {
          console.log('[TTS] Received audio for segment', data.segment_id);
          playAudio(data.audio_base64, data.format);
        }
      } catch (error) {
        console.error('[TTS] Failed to parse WebSocket message:', error);
      }
    };

    presenceWs.addEventListener('message', handleMessage);
    return () => presenceWs.removeEventListener('message', handleMessage);
  }, [presenceWs, playAudio]);

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

    // Get current user ID from token
    const getUserIdFromToken = (token) => {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return payload.sub;
      } catch (e) {
        console.error('[RoomOwner] Failed to parse token:', e);
        return null;
      }
    };

    const currentUserId = getUserIdFromToken(token);
    if (!currentUserId) return;

    fetch(`/api/rooms/${encodeURIComponent(roomId)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        setIsRoomOwner(data.owner_id === parseInt(currentUserId));
      })
      .catch(e => console.error('[RoomOwner] Failed to check:', e));
  }, [roomId, token, isGuest]);

  // ============================================================================
  // Persistence Settings
  // ============================================================================

  useEffect(() => {
    if (!roomId) return;

    // Guests don't have persistence, mark as initialized immediately
    if (isGuest || !token) {
      setPersistenceEnabled(false);
      setPersistenceInitialized(true);
      return;
    }

    fetch(`/api/rooms/${encodeURIComponent(roomId)}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(r => r.json())
      .then(data => {
        setPersistenceEnabled(data.recording || false);
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
      // Navigate to rooms list if logged in, otherwise home
      navigate(isGuest ? '/' : '/rooms');
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
  // Audio Settings Handlers
  // ============================================================================

  const handleThresholdChange = async (newThreshold) => {
    setAudioThreshold(newThreshold);

    // Save to backend for authenticated users
    if (!isGuest && token) {
      try {
        await fetch('/api/profile', {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ audio_threshold: newThreshold })
        });
      } catch (error) {
        console.error('[AudioSettings] Failed to save threshold:', error);
      }
    }
  };

  const handleDeviceChange = async (newDeviceId) => {
    setSelectedMicDeviceId(newDeviceId);

    // Save to backend for authenticated users
    if (!isGuest && token) {
      try {
        await fetch('/api/profile', {
          method: 'PATCH',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ preferred_mic_device_id: newDeviceId })
        });
      } catch (error) {
        console.error('[AudioSettings] Failed to save device:', error);
      }
    }
  };

  // ============================================================================
  // TTS Handlers
  // ============================================================================

  const handleTTSToggle = async (enabled) => {
    try {
      if (isGuest) {
        // Guest: save to localStorage
        localStorage.setItem(`tts_enabled_${roomId}`, JSON.stringify(enabled));
        setTtsEnabled(enabled);
        console.log(`[TTS] ${enabled ? 'Enabled' : 'Disabled'} for room (guest)`);
      } else {
        // Logged-in user: save to API
        const endpoint = enabled ? 'enable' : 'disable';
        const response = await fetch(`/api/rooms/${encodeURIComponent(roomId)}/tts/${endpoint}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (response.ok) {
          setTtsEnabled(enabled);
          console.log(`[TTS] ${enabled ? 'Enabled' : 'Disabled'} for room`);
        }
      }
    } catch (error) {
      console.error('[TTS] Toggle failed:', error);
    }
  };

  const handleVoiceChange = async (lang, voice) => {
    try {
      const newVoices = { ...ttsVoices, [lang]: voice };

      if (isGuest) {
        // Guest: save to localStorage
        localStorage.setItem(`tts_voices_${roomId}`, JSON.stringify(newVoices));
        setTtsVoices(newVoices);
        console.log('[TTS] Voice updated (guest):', lang, voice);
      } else {
        // Logged-in user: save to API
        const response = await fetch(`/api/rooms/${encodeURIComponent(roomId)}/tts/settings`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ voice_overrides: newVoices })
        });

        if (response.ok) {
          setTtsVoices(newVoices);
          console.log('[TTS] Voice updated:', lang, voice);
        }
      }
    } catch (error) {
      console.error('[TTS] Voice change failed:', error);
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
    <div
      className="flex flex-col bg-bg text-fg font-sans overflow-hidden"
      style={{
        height: '100vh',
        height: '100dvh', // Modern browsers: dynamic viewport height (accounts for mobile toolbars)
        maxHeight: '-webkit-fill-available' // Safari/iOS fallback
      }}
    >
      {/* Room Header */}
      <RoomHeader
        roomId={roomId}
        vadStatus={vadStatus}
        vadReady={audioStream.vadReady}
        languageCounts={languageCounts}
        languages={LANGUAGES}
        onBackClick={handleBackClick}
        onMenuClick={() => setShowSettings(true)}
      />

      {/* Welcome Banner */}
      {showWelcome && (
        <WelcomeBanner
          isOpen={showWelcome}
          roomId={roomId}
          participants={participants}
          currentUserId={userEmail}
          isGuest={isGuest}
          onClose={dismissWelcome}
        />
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
          isOpen={showLangPicker}
          currentLanguage={myLanguage}
          onLanguageChange={(lang) => {
            handleLanguageChange(lang);
          }}
          onClose={() => setShowLangPicker(false)}
        />
      )}


      {/* Chat Messages */}
      <ChatMessageList
        messages={roomWebSocket.lines}
        isAdmin={isAdmin}
        loadingHistory={loadingHistory}
        formatTime={formatTime}
        chatEndRef={chatEndRef}
        onDebugClick={handleDebugClick}
        showAdminLeftToast={roomStatus && !roomStatus.admin_present && !isRoomAdmin}
        timeRemaining={timeRemaining}
        formatCountdown={formatCountdown}
      />

      {/* Room Controls (includes PTT toggle, network status, and microphone button) */}
      <RoomControls
        status={status}
        pushToTalk={pushToTalk}
        isPressing={isPressing}
        networkQuality={networkQuality}
        networkRTT={networkRTT}
        onPushToTalkChange={(enabled) => {
          setPushToTalk(enabled);
          localStorage.setItem('lt_push_to_talk', enabled.toString());
        }}
        onStart={handleStart}
        onStop={handleStop}
        onPressStart={() => setIsPressing(true)}
        onPressEnd={() => setIsPressing(false)}
      />

      {/* Legacy Modals (not yet refactored) */}
      {showInvite && (
        <InviteModal
          roomCode={roomId}
          onClose={() => setShowInvite(false)}
        />
      )}

      {showSettings && (
        <SettingsMenu
          isOpen={showSettings}
          onClose={() => setShowSettings(false)}
          isGuest={isGuest}
          myLanguage={myLanguage}
          languages={LANGUAGES}
          onLanguageChange={() => {
            setShowSettings(false);
            setShowLangPicker(true);
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
            navigate(`/admin/cost-analytics?room_id=${encodeURIComponent(roomId)}`);
          }}
          onShowSound={() => {
            setShowSettings(false);
            setShowSoundSettings(true);
          }}
          onShowTTS={() => {
            setShowSettings(false);
            setShowTTSSettings(true);
          }}
          onLogout={onLogout}
          canChangeLanguage={status === 'idle'}
          persistenceEnabled={persistenceEnabled}
          onTogglePersistence={async (enabled) => {
            setPersistenceEnabled(enabled);
            try {
              await fetch(`/api/rooms/${encodeURIComponent(roomId)}/recording`, {
                method: 'PATCH',
                headers: {
                  'Authorization': `Bearer ${token}`,
                  'Content-Type': 'application/json'
                },
                body: JSON.stringify({ recording: enabled })
              });
              if (enabled && persistenceInitialized) {
                fetchHistory();
              }
            } catch (error) {
              console.error('[Persistence] Failed to toggle:', error);
              setPersistenceEnabled(!enabled); // Revert on error
            }
          }}
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
              setIsPublic(!newValue); // Revert on error
            }
          }}
        />
      )}

      {showTTSSettings && (
        <div
          className="fixed inset-0 bg-black/85 z-[1000] flex items-center justify-center p-4"
          onClick={() => setShowTTSSettings(false)}
        >
          <div
            className="bg-card border border-border rounded-xl max-w-md w-full p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl font-bold text-fg">{t('tts.settings')}</h2>
              <button
                onClick={() => setShowTTSSettings(false)}
                className="text-muted hover:text-fg transition-colors text-2xl w-8 h-8 flex items-center justify-center"
              >
                ×
              </button>
            </div>
            <TTSControls
              roomCode={roomId}
              enabled={ttsEnabled}
              voices={ttsVoices}
              onToggle={handleTTSToggle}
              onVoiceChange={handleVoiceChange}
            />
            {isPlaying && (
              <div className="mt-4 text-accent text-sm text-center">
                🔊 {t('tts.playing')}
              </div>
            )}
          </div>
        </div>
      )}

      {showSoundSettings && (
        <SoundSettingsModal
          isOpen={showSoundSettings}
          onClose={() => setShowSoundSettings(false)}
          currentLevel={audioLevel}
          threshold={audioThreshold}
          onThresholdChange={handleThresholdChange}
          isActive={status === 'recording'}
          status={vadStatus}
          onTest={handleTestMode}
          selectedDeviceId={selectedMicDeviceId}
          onDeviceChange={handleDeviceChange}
        />
      )}

      {showParticipantsPanel && (
        <ParticipantsPanel
          participants={participants}
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
