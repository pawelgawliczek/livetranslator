import React, { useRef, useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import InviteModal from "../components/InviteModal";
import ParticipantsModal from "../components/ParticipantsModal";
import SettingsMenu from "../components/SettingsMenu";
import SoundSettingsModal from "../components/SoundSettingsModal";

export default function RoomPage({ token, onLogout }) {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

  // Add animations for processing indicator and speaking status
  React.useEffect(() => {
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
      @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.6; }
      }
    `;
    document.head.appendChild(style);
    return () => document.head.removeChild(style);
  }, []);

  // Translations for "Refining quality..." in different languages
  const getProcessingText = (lang) => {
    const translations = {
      'en': 'Refining quality...',
      'es': 'Mejorando calidad...',
      'fr': 'Amélioration de la qualité...',
      'de': 'Qualität verbessern...',
      'it': 'Miglioramento qualità...',
      'pt': 'Melhorando qualidade...',
      'ru': 'Улучшение качества...',
      'zh': '提高质量中...',
      'ja': '品質向上中...',
      'ko': '품질 개선 중...',
      'ar': '...تحسين الجودة',
      'hi': 'गुणवत्ता में सुधार...',
      'pl': 'Poprawa jakości...',
      'nl': 'Kwaliteit verbeteren...',
      'tr': 'Kalite iyileştiriliyor...',
      'sv': 'Förbättrar kvalitet...',
      'da': 'Forbedrer kvalitet...',
      'fi': 'Parannetaan laatua...',
      'no': 'Forbedrer kvalitet...',
      'cs': 'Zlepšování kvality...',
      'ro': 'Îmbunătățire calitate...',
      'hu': 'Minőség javítása...',
      'uk': 'Покращення якості...',
      'el': 'Βελτίωση ποιότητας...',
      'he': '...שיפור איכות',
      'th': 'กำลังปรับปรุงคุณภาพ...',
      'vi': 'Cải thiện chất lượng...',
      'id': 'Meningkatkan kualitas...',
      'ms': 'Meningkatkan kualiti...',
    };
    return translations[lang] || translations['en'];
  };

  // Check if this is a guest session
  const isGuest = sessionStorage.getItem('is_guest') === 'true';
  const guestName = sessionStorage.getItem('guest_display_name') || 'Guest';
  const guestLang = sessionStorage.getItem('guest_language') || 'en';

  // If no token and not a guest, redirect to login
  React.useEffect(() => {
    if (!token && !isGuest) {
      navigate('/login');
    }
  }, [token, isGuest, navigate]);

  const [status, setStatus] = useState("idle");
  const [vadStatus, setVadStatus] = useState("idle");
  const [vadReady, setVadReady] = useState(false);
  const [lines, setLines] = useState([]);
  const [costs, setCosts] = useState(null);
  const [showCosts, setShowCosts] = useState(false);
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [showInvite, setShowInvite] = useState(false);
  const [showParticipants, setShowParticipants] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showSoundSettings, setShowSoundSettings] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [myLanguage, setMyLanguage] = useState(() => {
    const stored = isGuest ? guestLang : localStorage.getItem('lt_my_language');
    // If no language stored, we'll force selection via modal
    return stored || null;
  });
  const [pushToTalk, setPushToTalk] = useState(() => {
    return localStorage.getItem('lt_push_to_talk') === 'true';
  });
  const [persistenceEnabled, setPersistenceEnabled] = useState(false); // Will be loaded from database
  const [persistenceInitialized, setPersistenceInitialized] = useState(false);
  const [isPublic, setIsPublic] = useState(false);
  const [isPublicInitialized, setIsPublicInitialized] = useState(false);
  const [isRoomOwner, setIsRoomOwner] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [isPressing, setIsPressing] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [isRoomAdmin, setIsRoomAdmin] = useState(false);
  const [showAdminLeaveWarning, setShowAdminLeaveWarning] = useState(false);
  const [roomStatus, setRoomStatus] = useState(null);
  const [showExpirationModal, setShowExpirationModal] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(null);
  const [showAdminLeftNotification, setShowAdminLeftNotification] = useState(false);
  const [activeLanguages, setActiveLanguages] = useState(new Set());
  const recentJoinsRef = useRef(new Map()); // Track recent joins to filter duplicate language change events

  // Network quality monitoring
  const [networkQuality, setNetworkQuality] = useState('unknown'); // 'high', 'medium', 'low', 'unknown'
  const [networkRTT, setNetworkRTT] = useState(null); // milliseconds
  const rttMeasurements = useRef([]); // Store last 5 measurements
  const networkQualityRef = useRef('unknown'); // Track current quality without closure issues
  const pingIntervalRef = useRef(null);
  const pendingPingRef = useRef(null);
  const pingTimeoutRef = useRef(null);

  // Adaptive send rate
  const [sendInterval, setSendInterval] = useState(300); // milliseconds
  const sendIntervalRef = useRef(300);
  const bytesSentRef = useRef(0);
  const bandwidthRef = useRef(0);
  const lastBandwidthCheckRef = useRef(Date.now());

  // Audio level monitoring for Sound Settings
  const [audioLevel, setAudioLevel] = useState(0); // Current RMS energy (0.0 - 1.0)
  const [audioThreshold, setAudioThreshold] = useState(0.02); // Adjustable ENERGY_THRESHOLD
  const audioLevelRef = useRef(0);

  // Test mode for Sound Settings
  const [testMode, setTestMode] = useState(false);
  const testAudioContextRef = useRef(null);
  const testProcessorRef = useRef(null);
  const testStreamRef = useRef(null);

  const wsRef = useRef(null);
  const presenceWsRef = useRef(null); // Persistent presence WebSocket
  const seqRef = useRef(1);
  const hasSeenAdminLeftNotificationRef = useRef(false); // Use ref for immediate updates
  const isRecordingRef = useRef(false);
  const audioContextRef = useRef(null);
  const scriptProcessorRef = useRef(null);
  const streamRef = useRef(null);
  const partialBufferRef = useRef(new Float32Array(0));
  const isSpeakingRef = useRef(false);
  const lastPartialSentRef = useRef(0);
  const currentSegmentHintRef = useRef(null);
  const chatEndRef = useRef(null);
  const placeholderSegmentKeyRef = useRef(null); // Track current placeholder for removal

  const segsRef = useRef(new Map());
  const dirtyRef = useRef(false);

  // VAD state - will be replaced by ML VAD
  const vadSpeechFramesRef = useRef(0);
  const vadSilenceFramesRef = useRef(0);
  const vadIsDetectedRef = useRef(false);

  // Improved VAD configuration - stricter silence detection to prevent repetitions
  const silenceFramesRef = useRef(0);  // Count consecutive silent frames
  const speechFramesRef = useRef(0);   // Count consecutive speech frames
  const ringBufferRef = useRef(new Float32Array(0));  // Pre-buffer to capture speech onset
  const SILENCE_THRESHOLD = 20;        // 20 frames (~200ms) of silence before stopping
  const SPEECH_THRESHOLD = 5;          // 5 frames (~50ms) of speech to start
  const ENERGY_THRESHOLD = 0.02;       // VAD energy threshold (Phase 0.8 default)
  const RING_BUFFER_MS = 500;          // Keep 500ms of audio before speech detection

  const languages = [
    { code: "auto", name: "Auto", flag: "🌐" },
    { code: "en", name: "English", flag: "🇬🇧" },
    { code: "pl", name: "Polski", flag: "🇵🇱" },
    { code: "ar", name: "العربية", flag: "🇸🇦" },
    { code: "es", name: "Español", flag: "🇪🇸" },
    { code: "fr", name: "Français", flag: "🇫🇷" },
    { code: "de", name: "Deutsch", flag: "🇩🇪" },
    { code: "it", name: "Italiano", flag: "🇮🇹" },
    { code: "pt", name: "Português", flag: "🇵🇹" },
    { code: "ru", name: "Русский", flag: "🇷🇺" },
    { code: "zh", name: "中文", flag: "🇨🇳" },
    { code: "ja", name: "日本語", flag: "🇯🇵" },
    { code: "ko", name: "한국어", flag: "🇰🇷" }
  ];
  
  useEffect(() => {
    if (isGuest) {
      setUserEmail(guestName);
    } else if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        setUserEmail(payload.email || "User");
      } catch (e) {
        console.error("Failed to decode token:", e);
      }
    }
  }, [token, isGuest, guestName]);

  // Force language selection if not set
  useEffect(() => {
    if (!myLanguage) {
      setShowSettings(true);
      console.log('[Language] No language set, forcing selection modal');
    }
  }, [myLanguage]);

  // Save language preference to localStorage
  useEffect(() => {
    if (!isGuest && myLanguage) {
      localStorage.setItem('lt_my_language', myLanguage);
    }
  }, [myLanguage, isGuest]);

  useEffect(() => {
    localStorage.setItem('lt_push_to_talk', pushToTalk.toString());
  }, [pushToTalk]);

  useEffect(() => {
    // Only update server if persistenceEnabled has been initialized from database
    if (!isGuest && token && persistenceInitialized) {
      // Call API to update persistence setting on server
      fetch(`/api/rooms/${roomId}/recording`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ recording: persistenceEnabled })
      })
        .then(response => {
          if (!response.ok) {
            throw new Error('Failed to update recording setting');
          }
          return response.json();
        })
        .then(data => {
          console.log('[Persistence] ✓ Recording setting updated on server:', persistenceEnabled);
        })
        .catch(error => {
          console.error('[Persistence] Failed to update server:', error);
        });
    }
  }, [persistenceEnabled, isGuest, token, roomId, persistenceInitialized]);

  // Handle public/private toggle
  useEffect(() => {
    if (!isGuest && token && isRoomAdmin && isPublicInitialized) {
      // Call API to update public setting on server
      fetch(`/api/rooms/${roomId}/public`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ is_public: isPublic })
      })
        .then(response => {
          if (!response.ok) {
            throw new Error('Failed to update public setting');
          }
          return response.json();
        })
        .then(data => {
          console.log('[Public] ✓ Public setting updated on server:', isPublic);
        })
        .catch(error => {
          console.error('[Public] Failed to update server:', error);
        });
    }
  }, [isPublic, isGuest, token, roomId, isRoomAdmin, isPublicInitialized]);

  // Check if current user is the room admin and fetch user profile
  useEffect(() => {
    if (!isGuest && token) {
      // Fetch room info
      fetch(`/api/rooms/${roomId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            const userId = parseInt(payload.sub);
            const isOwner = data.owner_id === userId;
            console.log('[Room Admin Check]', {
              userId,
              ownerId: data.owner_id,
              isOwner,
              isPublic: data.is_public,
              recording: data.recording
            });
            setIsRoomAdmin(isOwner);
            setIsRoomOwner(isOwner);
            setIsPublic(data.is_public || false);
            setIsPublicInitialized(true); // Mark as initialized after first fetch
            setPersistenceEnabled(data.recording || false);
            setPersistenceInitialized(true); // Mark as initialized after first fetch
          } catch (e) {
            console.error('Failed to check admin status:', e);
          }
        })
        .catch(err => console.error('Failed to fetch room info:', err));

      // Fetch user profile to check if admin
      fetch('/api/profile', {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          setIsAdmin(data.is_admin || false);
        })
        .catch(err => console.error('Failed to fetch user profile:', err));
    }
  }, [roomId, token, isGuest]);

  // Fetch STT settings for the room on mount
  // NOTE: STT settings removed - now using language-based routing (Migration 006)

  // Poll room status every 5 seconds to check admin presence
  useEffect(() => {
    // Get the appropriate token (regular user or guest)
    let authToken = token;
    if (isGuest) {
      authToken = sessionStorage.getItem('guest_token');
    }

    if (!authToken) return;

    const pollRoomStatus = async () => {
      try {
        const res = await fetch(`/api/rooms/${roomId}/status`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });

        if (res.ok) {
          const status = await res.json();
          setRoomStatus(status);

          // Calculate time remaining if admin is absent
          if (!status.admin_present && status.expires_at) {
            // Parse expires_at as UTC and convert to local time for comparison
            const expiresAt = new Date(status.expires_at);
            const now = new Date();

            const remaining = Math.max(0, expiresAt - now);
            setTimeRemaining(remaining);

            // Show one-time notification when admin first leaves (for non-admin users only)
            if (!isRoomAdmin && !hasSeenAdminLeftNotificationRef.current && remaining > 0) {
              setShowAdminLeftNotification(true);
              hasSeenAdminLeftNotificationRef.current = true; // Set immediately
            }

            // Show expiration modal if time is up
            if (remaining === 0 && !isRoomAdmin) {
              setShowExpirationModal(true);
            }
          } else {
            setTimeRemaining(null);
            // Reset notification flag when admin returns
            if (status.admin_present) {
              hasSeenAdminLeftNotificationRef.current = false;
              setShowAdminLeftNotification(false);
            }
          }
        }
      } catch (err) {
        console.error('Failed to fetch room status:', err);
      }
    };

    // Poll immediately and then every 5 seconds
    pollRoomStatus();
    const interval = setInterval(pollRoomStatus, 5000);

    return () => clearInterval(interval);
  }, [roomId, token, isGuest, isRoomAdmin]);

  // Warn admin before leaving
  useEffect(() => {
    if (isRoomAdmin) {
      const handleBeforeUnload = (e) => {
        e.preventDefault();
        e.returnValue = 'Room will be automatically deleted 30 minutes after you leave. Are you sure?';
        return e.returnValue;
      };

      window.addEventListener('beforeunload', handleBeforeUnload);
      return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }
  }, [isRoomAdmin]);

  // Custom back button handler for admin
  const handleBackClick = () => {
    if (isRoomAdmin) {
      setShowAdminLeaveWarning(true);
    } else {
      navigate("/rooms");
    }
  };

  // Load history on mount and when my language changes
  useEffect(() => {
    fetchHistory();
  }, [roomId, myLanguage]);

  // Send language update to server when it changes
  useEffect(() => {
    if (presenceWsRef.current && presenceWsRef.current.readyState === 1 && myLanguage) {
      presenceWsRef.current.send(JSON.stringify({
        type: "set_language",
        language: myLanguage
      }));
      console.log('[RoomPage] Sent language update:', myLanguage);
    }
  }, [myLanguage]);

  // Network monitoring functions
  const recordRTT = (rtt) => {
    // Add to measurements array (keep last 5)
    rttMeasurements.current.push(rtt);
    if (rttMeasurements.current.length > 5) {
      rttMeasurements.current.shift();
    }

    // Calculate moving average
    const avgRTT = rttMeasurements.current.reduce((a, b) => a + b, 0) / rttMeasurements.current.length;
    setNetworkRTT(Math.round(avgRTT));

    // Classify network quality
    let quality;
    if (avgRTT < 150) {
      quality = 'high';
    } else if (avgRTT < 400) {
      quality = 'medium';
    } else {
      quality = 'low';
    }

    // Only update state if quality changed (use ref to avoid stale closures)
    if (quality !== networkQualityRef.current) {
      console.log(`[Network] Quality changed: ${networkQualityRef.current} → ${quality} (${Math.round(avgRTT)}ms avg RTT)`);
      networkQualityRef.current = quality;
      setNetworkQuality(quality);
    }
  };

  const sendPing = (ws) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      return;
    }

    const pingStart = Date.now();
    pendingPingRef.current = pingStart;

    ws.send(JSON.stringify({
      type: 'ping',
      timestamp: pingStart
    }));

    // Timeout after 5 seconds
    if (pingTimeoutRef.current) {
      clearTimeout(pingTimeoutRef.current);
    }
    pingTimeoutRef.current = setTimeout(() => {
      if (pendingPingRef.current === pingStart) {
        console.warn('[Network] Ping timeout - network may be degraded');
        recordRTT(5000); // Record as 5s RTT
        pendingPingRef.current = null;
      }
    }, 5000);
  };

  const handlePong = (data) => {
    if (pendingPingRef.current && data.timestamp === pendingPingRef.current) {
      if (pingTimeoutRef.current) {
        clearTimeout(pingTimeoutRef.current);
      }
      const rtt = Date.now() - pendingPingRef.current;
      recordRTT(rtt);
      pendingPingRef.current = null;
    }
  };

  const startNetworkMonitoring = (ws) => {
    // Send initial ping
    sendPing(ws);

    // Send ping every 2 seconds
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
    }
    pingIntervalRef.current = setInterval(() => sendPing(ws), 2000);
  };

  const stopNetworkMonitoring = () => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (pingTimeoutRef.current) {
      clearTimeout(pingTimeoutRef.current);
      pingTimeoutRef.current = null;
    }
    rttMeasurements.current = [];
    pendingPingRef.current = null;
    networkQualityRef.current = 'unknown';
    setNetworkQuality('unknown');
    setNetworkRTT(null);
  };

  // Adaptive send rate helper
  const getOptimalSendInterval = (quality) => {
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
  };

  // Bandwidth tracking helper
  const trackBandwidth = (bytesSent) => {
    bytesSentRef.current += bytesSent;

    const now = Date.now();
    const elapsed = (now - lastBandwidthCheckRef.current) / 1000; // seconds

    if (elapsed >= 5) { // Update every 5 seconds
      const bitsPerSecond = (bytesSentRef.current * 8) / elapsed;
      const kbps = Math.round(bitsPerSecond / 1000);
      bandwidthRef.current = kbps;

      // Reset counters
      bytesSentRef.current = 0;
      lastBandwidthCheckRef.current = now;
    }
  };

  // Update send interval when network quality changes
  useEffect(() => {
    const newInterval = getOptimalSendInterval(networkQuality);

    if (newInterval !== sendIntervalRef.current) {
      console.log(`[Adaptive] Changing send interval: ${sendIntervalRef.current}ms → ${newInterval}ms (quality: ${networkQuality})`);
      setSendInterval(newInterval);
      sendIntervalRef.current = newInterval;
    }
  }, [networkQuality]);

  // Establish persistent presence WebSocket when room page loads
  useEffect(() => {
    let authToken = token;
    if (isGuest) {
      authToken = sessionStorage.getItem('guest_token');
    }

    if (!authToken) {
      console.log('[RoomPage] No auth token, skipping presence WebSocket');
      return;
    }

    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/rooms/${encodeURIComponent(roomId)}?token=${encodeURIComponent(authToken)}`;
      console.log('[RoomPage] Opening persistent presence WebSocket:', wsUrl);

      const presenceWs = new WebSocket(wsUrl);
      presenceWsRef.current = presenceWs;

      presenceWs.onopen = () => {
        console.log('[RoomPage] Presence WebSocket connected! User is now visible in participants list.');
        // Send initial language preference (if selected)
        if (myLanguage) {
          presenceWs.send(JSON.stringify({
            type: "set_language",
            language: myLanguage
          }));
          console.log('[RoomPage] Sent initial language to server:', myLanguage);
          // Add our own language to active languages
          setActiveLanguages(prev => new Set([...prev, myLanguage]));
        }
        // Start network monitoring
        startNetworkMonitoring(presenceWs);
      };

      presenceWs.onmessage = (event) => {
        // Process STT and translation messages on presence WebSocket too
        try {
          const data = JSON.parse(event.data);

          // DEBUG: Log all received WebSocket messages
          console.log('[PresenceWS] Received message:', data.type, data);

          // Handle ping-pong for network monitoring
          if (data.type === 'pong') {
            handlePong(data);
            return;
          }

          // Handle participant join/leave/language change events as system messages
          if (data.type === 'participant_joined' || data.type === 'participant_left' || data.type === 'participant_language_changed') {
            console.log('[PresenceWS] Processing participant event:', data.type);
            // Get user's display name from email or user_id
            let displayName = 'Someone';
            let isGuest = false;
            if (data.user_email && data.user_email !== 'unknown') {
              displayName = data.user_email.split('@')[0];
            } else if (data.user_id && String(data.user_id).startsWith('guest:')) {
              const parts = String(data.user_id).split(':', 2);
              displayName = parts[1] || 'Guest';
              isGuest = true;
            }

            // Don't show our own join/language change messages
            try {
              const ourEmail = authToken ? JSON.parse(atob(authToken.split('.')[1])).email : null;
              const isOurMessage = data.user_email === ourEmail;

              if (isOurMessage && (data.type === 'participant_joined' || data.type === 'participant_language_changed')) {
                // Still update active languages for ourselves
                if (data.preferred_lang) {
                  setActiveLanguages(prev => new Set([...prev, data.preferred_lang]));
                }
                console.log('[PresenceWS] Skipping our own', data.type, 'message');
                return;
              }
            } catch (e) {
              // Ignore token parsing errors
            }

            // Get language info
            const langCode = data.preferred_lang || 'en';
            const langInfo = languages.find(l => l.code === langCode);
            const langFlag = langInfo ? langInfo.flag : '🌐';
            const langName = langInfo ? langInfo.name : langCode;

            // Track recent joins to filter duplicate language change events
            const userId = data.user_id || data.user_email;

            if (data.type === 'participant_joined') {
              // Store join info with language and timestamp
              recentJoinsRef.current.set(userId, {
                language: langCode,
                timestamp: Date.now()
              });
              // Clean up after 5 seconds
              setTimeout(() => {
                recentJoinsRef.current.delete(userId);
              }, 5000);
            }

            // Filter out language change events if:
            // 1. User just joined with the same language (within 5 seconds)
            // 2. Language didn't actually change
            if (data.type === 'participant_language_changed') {
              const recentJoin = recentJoinsRef.current.get(userId);
              if (recentJoin) {
                const timeSinceJoin = Date.now() - recentJoin.timestamp;
                // Skip if same language within 5 seconds of joining
                if (recentJoin.language === langCode && timeSinceJoin < 5000) {
                  console.log('[PresenceWS] Skipping duplicate language change (same as join)');
                  return;
                }
              }
            }

            // Create system message text
            let messageText = '';
            if (data.type === 'participant_joined') {
              messageText = `${langFlag} ${displayName}${isGuest ? ' (guest)' : ''} joined with ${langName}`;
              setActiveLanguages(prev => new Set([...prev, langCode]));
            } else if (data.type === 'participant_left') {
              messageText = `${displayName}${isGuest ? ' (guest)' : ''} left the room`;
              // Don't remove language immediately - let the TTL expire naturally
            } else if (data.type === 'participant_language_changed') {
              messageText = `${langFlag} ${displayName}${isGuest ? ' (guest)' : ''} changed to ${langName}`;
              setActiveLanguages(prev => new Set([...prev, langCode]));
            }

            // Create a system message (flat structure like regular messages)
            const systemMessage = {
              type: 'stt_final',
              segment_id: Date.now(),
              ts_iso: new Date().toISOString(),
              text: messageText,
              is_system: true,
              final: true
            };

            // Add to segments (same format as regular STT messages)
            segsRef.current.set(`s-${systemMessage.segment_id}`, systemMessage);
            scheduleRender();
          }
          // Handle speech_started events
          else if (data.type === 'speech_started') {
            console.log('[RoomPage] Speech started from:', data.speaker, 'segment_id:', data.segment_id);

            // Use the real segment ID from the backend
            const segmentId = data.segment_id;
            const placeholderKey = `s-${segmentId}`;

            // Only track our own placeholder for removal
            if (data.speaker === (userEmail || 'Guest')) {
              placeholderSegmentKeyRef.current = placeholderKey;
            }

            segsRef.current.set(placeholderKey, {
              segment_id: segmentId,
              type: 'stt_partial',
              text: '___SPEAKING___',
              speaker: data.speaker,
              final: false,
              ts_iso: new Date().toISOString(),
              is_placeholder: true
            });
            scheduleRender();

            // Auto-remove placeholder after 5 seconds if no text arrives
            setTimeout(() => {
              const segment = segsRef.current.get(placeholderKey);
              // Only delete if it's still a placeholder (not replaced by real text)
              if (segment && segment.is_placeholder) {
                segsRef.current.delete(placeholderKey);
                if (placeholderSegmentKeyRef.current === placeholderKey) {
                  placeholderSegmentKeyRef.current = null;
                }
                scheduleRender();
                console.log('[VAD] Removed stale placeholder after timeout for:', data.speaker);
              } else if (segment) {
                console.log('[VAD] Placeholder already replaced with real text, keeping it for:', data.speaker);
              }
            }, 5000);
          }
          // Process translation and STT messages
          else if (data.type && (data.type.includes('translation') || data.type.includes('stt') || data.type.includes('partial') || data.type.includes('final'))) {
            onMsg(event);
          } else {
            console.log('[RoomPage] Presence WS received (ignored):', data.type);
          }
        } catch (e) {
          console.log('[RoomPage] Presence WS received non-JSON:', event.data);
        }
      };

      presenceWs.onerror = (err) => {
        console.error('[RoomPage] Presence WebSocket error:', err);
      };

      presenceWs.onclose = () => {
        console.log('[RoomPage] Presence WebSocket closed');
      };
    } catch (e) {
      console.error('[RoomPage] Failed to create presence WebSocket:', e);
    }

    // Cleanup: close presence WebSocket when component unmounts
    return () => {
      stopNetworkMonitoring();
      if (presenceWsRef.current) {
        console.log('[RoomPage] Closing presence WebSocket on unmount');
        presenceWsRef.current.close();
        presenceWsRef.current = null;
      }
    };
  }, [roomId, token, isGuest]);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);
  
  function scheduleRender() {
    if (dirtyRef.current) return;
    dirtyRef.current = true;
    setTimeout(() => {
      const segments = new Map();
      
      for (const [key, msg] of segsRef.current.entries()) {
        const segId = msg.segment_id;
        if (!segments.has(segId)) {
          segments.set(segId, { source: null, translation: null });
        }
        const seg = segments.get(segId);

        if (msg.type && msg.type.startsWith("translation")) {
          // Only store translation if it matches my language
          console.log(`[Translation Filter] myLanguage=${myLanguage}, msg.tgt=${msg.tgt}, match=${msg.tgt === myLanguage}`);
          if (msg.tgt === myLanguage) {
            if (!seg.translation || msg.final || (!msg.final && !seg.translation.final)) {
              seg.translation = msg;
              console.log(`[Translation] Stored translation for segment ${segId}`);
            }
          } else {
            console.log(`[Translation] Skipped translation (tgt=${msg.tgt} !== myLang=${myLanguage})`);
          }
        } else {
          if (!seg.source || msg.final || (!msg.final && !seg.source.final)) {
            seg.source = msg;
          }
        }
      }
      
      const arr = Array.from(segments.entries())
        .filter(([segId, seg]) => {
          // Filter out empty segments, but keep speaking placeholders
          const hasSourceText = seg.source && seg.source.text && seg.source.text.trim().length > 0;
          const hasTranslationText = seg.translation && seg.translation.text && seg.translation.text.trim().length > 0;
          const isPlaceholder = seg.source?.text === '___SPEAKING___' || seg.translation?.text === '___SPEAKING___';
          return hasSourceText || hasTranslationText || isPlaceholder;
        })
        .sort((a, b) => {
          const tsA = a[1].source?.ts_iso || a[1].translation?.ts_iso || "";
          const tsB = b[1].source?.ts_iso || b[1].translation?.ts_iso || "";
          return tsA.localeCompare(tsB) || (a[0] - b[0]);
        })
        .slice(-100);

      setLines(arr);
      dirtyRef.current = false;
    }, 200);
  }
  
  function onMsg(ev) {
    try {
      const m = JSON.parse(ev.data);
      console.log('[WS] Received:', m);

      // Silently ignore non-STT/translation messages (they're handled by presenceWs)
      const messageTypes = ["translation_partial", "translation_final", "partial", "stt_partial", "final", "stt_final", "stt_finalize"];
      if (!messageTypes.includes(m.type)) {
        return;
      }

      // Handle finalization marker (no text, just marks last partial as final)
      if (m.type === "stt_finalize") {
        const frontend_timestamp = Date.now() / 1000; // Convert to seconds
        const id = m.segment_id | 0;
        const existingSegment = segsRef.current.get(`s-${id}`);
        if (existingSegment) {
          const sync_delay = m.backend_timestamp ? (frontend_timestamp - m.backend_timestamp) : null;
          console.log(`[WS] ✅ Finalizing segment ${id} (sync delay: ${sync_delay ? (sync_delay * 1000).toFixed(0) + 'ms' : 'N/A'})`);
          console.log(`[WS]    Backend sent at: ${m.backend_timestamp ? new Date(m.backend_timestamp * 1000).toISOString() : 'N/A'}`);
          console.log(`[WS]    Frontend received at: ${new Date(frontend_timestamp * 1000).toISOString()}`);
          // Mark existing partial as final
          existingSegment.final = true;
          existingSegment.processing = false;
          existingSegment.type = "stt_final";
          segsRef.current.set(`s-${id}`, existingSegment);
          scheduleRender();
        } else {
          console.warn(`[WS] ⚠️ Cannot finalize segment ${id} - not found in segsRef`);
        }
        return;
      }

      // Check if text field exists (not undefined)
      if (!('text' in m)) {
        console.log('[WS] Rejected: no text field');
        return;
      }

      // Skip messages with empty text (but log them)
      if (!m.text || m.text.trim() === '') {
        console.log('[WS] Skipping empty text message:', m.type, 'segment:', m.segment_id);
        return;
      }

      m.segment_id = m.segment_id || Date.now();
      m.ts_iso = m.ts_iso || new Date().toISOString();
      const id = m.segment_id | 0;

      console.log('[WS] Processing:', m.type, 'segment:', id, 'speaker:', m.speaker);

      // Remove placeholder segment when real text arrives (only if it matches this segment AND is still a placeholder)
      if (placeholderSegmentKeyRef.current) {
        const placeholderSegmentKey = `s-${id}`;
        if (placeholderSegmentKeyRef.current === placeholderSegmentKey) {
          const existingSegment = segsRef.current.get(placeholderSegmentKeyRef.current);
          if (existingSegment && existingSegment.is_placeholder) {
            segsRef.current.delete(placeholderSegmentKeyRef.current);
            console.log('[WS] Removed placeholder segment:', placeholderSegmentKeyRef.current);
          } else {
            console.log('[WS] Placeholder already replaced, keeping real segment:', placeholderSegmentKeyRef.current);
          }
          placeholderSegmentKeyRef.current = null;
        } else {
          console.log('[WS] Skipping placeholder removal - segment mismatch:', placeholderSegmentKeyRef.current, 'vs', placeholderSegmentKey);
        }
      }

      if (m.type === "translation_partial" || m.type === "translation_final") {
        segsRef.current.set(`t-${id}`, { ...m, is_placeholder: false });
      } else if (m.type === "partial" || m.type === "stt_partial" || m.type === "final" || m.type === "stt_final") {
        segsRef.current.set(`s-${id}`, { ...m, is_placeholder: false });
      }
      scheduleRender();
    } catch (e) {
      console.error('[WS] Error:', e);
    }
  }
  
  function floatTo16(f) {
    const o = new Int16Array(f.length);
    for (let i = 0; i < f.length; i++) {
      const s = Math.max(-1, Math.min(1, f[i]));
      o[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return o;
  }
  
  function resampleTo16k(input, inRate) {
    if (inRate === 16000) return input;
    const ratio = 16000 / inRate;
    const out = new Float32Array(Math.floor(input.length * ratio));
    for (let i = 0; i < out.length; i++) {
      const x = i / ratio;
      const i0 = Math.floor(x);
      const i1 = Math.min(i0 + 1, input.length - 1);
      const t = x - i0;
      out[i] = input[i0] * (1 - t) + input[i1] * t;
    }
    return out;
  }
  
  function sendPartialIfReady() {
    const now = Date.now();
    if (!isSpeakingRef.current) return;

    // Use dynamic send interval based on network quality
    const interval = sendIntervalRef.current;
    if (now - lastPartialSentRef.current < interval) return;

    // Adjust minimum buffer size based on interval
    // Minimum = 0.2s of audio, but scale with interval
    const minBufferSamples = Math.max(3200, Math.floor((interval / 1000) * 16000 * 0.2));
    if (partialBufferRef.current.length < minBufferSamples) return;

    try {
      const pcm16 = floatTo16(partialBufferRef.current);
      const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));

      if (wsRef.current && wsRef.current.readyState === 1) {
        const payload = JSON.stringify({
          type: "audio_chunk_partial",
          roomId: roomId,
          device: "web",
          segment_hint: currentSegmentHintRef.current,
          seq: seqRef.current++,
          pcm16_base64: b64,
          language: myLanguage || "auto"  // Use "auto" if language not yet selected
        });

        wsRef.current.send(payload);
        trackBandwidth(payload.length); // Track bytes sent
      }

      lastPartialSentRef.current = now;
      // Clear buffer after sending - don't keep overlapping audio for streaming STT
      // Overlapping windows cause audio duplications in the accumulated buffer
      partialBufferRef.current = new Float32Array(0);
    } catch (e) {
      console.error("Partial send failed:", e);
    }
  }

  function sendFinalTranscription() {
    // Send any remaining buffered audio first, then audio_end
    try {
      if (wsRef.current && wsRef.current.readyState === 1) {
        // Send any remaining audio in the buffer (even if below minimum threshold)
        if (partialBufferRef.current.length > 0) {
          const pcm16 = floatTo16(partialBufferRef.current);
          const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));

          wsRef.current.send(JSON.stringify({
            type: "audio_chunk_partial",
            roomId: roomId,
            device: "web",
            segment_hint: currentSegmentHintRef.current,
            seq: seqRef.current++,
            pcm16_base64: b64,
            language: myLanguage || "auto"
          }));
          console.log("[VAD] Sent final partial chunk before audio_end");
        }

        // Then send audio_end to trigger finalization
        wsRef.current.send(JSON.stringify({
          type: "audio_end",
          roomId: roomId,
          device: "web"
        }));
        console.log("[VAD] Sent audio_end to finalize segment");
      }
    } catch (e) {
      console.error("Final send failed:", e);
    }
  }
  
  async function start() {
    if (isRecordingRef.current) return;

    // Stop test mode if it's active
    if (testMode) {
      await handleTestMode(false);
    }

    // Prevent starting only if room is about to expire (less than 1 minute remaining)
    if (!isRoomAdmin && roomStatus && !roomStatus.admin_present && timeRemaining !== null && timeRemaining < 60000) {
      alert("Cannot start recording: Room is closing soon. Recording will be available if the admin rejoins.");
      return;
    }

    setStatus("connecting");
    setVadStatus("⏳ Loading...");
    setVadReady(false);

    // Determine which token to use
    let authToken = token;
    if (isGuest) {
      authToken = sessionStorage.getItem('guest_token');
      if (!authToken) {
        alert("Guest token not found. Please scan the invite QR code again.");
        navigate('/');
        return;
      }
    }

    const wsUrl = (window.location.protocol === "https:" ? "wss://" : "ws://") +
      window.location.host + `/ws/rooms/${encodeURIComponent(roomId)}?token=${encodeURIComponent(authToken)}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = onMsg;
    ws.onopen = () => setStatus("streaming");
    ws.onclose = () => {
      setStatus("idle");
      setVadStatus("idle");
      setVadReady(false);
    };
    ws.onerror = () => setStatus("ws error");
    wsRef.current = ws;
    
    seqRef.current = 1;

    // Start improved energy-based VAD
    console.log('[VAD] Starting voice activity detection...');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: { ideal: 48000 },  // Higher quality, browser will downsample if needed
          echoCancellation: true,
          noiseSuppression: false,       // Disable to preserve speech quality
          autoGainControl: true          // Enable automatic gain control
        }
      });
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      const sourceSampleRate = audioContext.sampleRate;
      const targetSampleRate = 16000;
      console.log(`[VAD] Audio context sample rate: ${sourceSampleRate}Hz -> resampling to ${targetSampleRate}Hz`);

      // Reset VAD state
      silenceFramesRef.current = 0;
      speechFramesRef.current = 0;
      isSpeakingRef.current = false;
      partialBufferRef.current = new Float32Array(0);
      ringBufferRef.current = new Float32Array(0);
      lastPartialSentRef.current = 0;

      processor.onaudioprocess = (e) => {
        if (!isRecordingRef.current || !wsRef.current) return;

        const inputData = e.inputBuffer.getChannelData(0);

        // Resample to 16kHz using simple linear interpolation
        const resampledLength = Math.floor(inputData.length * targetSampleRate / sourceSampleRate);
        const resampled = new Float32Array(resampledLength);
        const ratio = (inputData.length - 1) / (resampledLength - 1);

        for (let i = 0; i < resampledLength; i++) {
          const srcIndex = i * ratio;
          const srcIndexFloor = Math.floor(srcIndex);
          const srcIndexCeil = Math.min(srcIndexFloor + 1, inputData.length - 1);
          const fraction = srcIndex - srcIndexFloor;
          resampled[i] = inputData[srcIndexFloor] * (1 - fraction) + inputData[srcIndexCeil] * fraction;
        }

        // Calculate RMS energy on resampled data
        let sum = 0;
        for (let i = 0; i < resampled.length; i++) {
          sum += resampled[i] * resampled[i];
        }
        const rms = Math.sqrt(sum / resampled.length);

        // Update audio level for Sound Settings visualization
        audioLevelRef.current = rms;
        setAudioLevel(rms);

        // Speech/silence detection with hysteresis (use adjustable threshold)
        if (rms > audioThreshold) {
          speechFramesRef.current++;
          silenceFramesRef.current = 0;

          // Start speaking after SPEECH_THRESHOLD frames
          if (!isSpeakingRef.current && speechFramesRef.current >= SPEECH_THRESHOLD) {
            console.log('[VAD] 🎤 Speech started');
            setVadStatus("🎤 Speaking...");
            isSpeakingRef.current = true;
            // Start with ring buffer content to capture beginning of first word
            partialBufferRef.current = new Float32Array(ringBufferRef.current);
            console.log(`[VAD] Pre-buffered ${ringBufferRef.current.length} samples (${(ringBufferRef.current.length / 16000 * 1000).toFixed(0)}ms)`);
            lastPartialSentRef.current = 0;
            currentSegmentHintRef.current = Date.now();

            // Broadcast speech_started to all clients in the room
            const speaker = userEmail || 'Guest';
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({
                type: "speech_started",
                room_id: roomId,
                speaker: speaker,
                timestamp: Date.now()
              }));
              console.log('[VAD] Sent speech_started event for:', speaker);
            }
          }
        } else {
          silenceFramesRef.current++;
          speechFramesRef.current = 0;

          // Stop speaking after SILENCE_THRESHOLD frames
          if (isSpeakingRef.current && silenceFramesRef.current >= SILENCE_THRESHOLD) {
            console.log('[VAD] ✅ Speech ended (silence detected)');
            setVadStatus("✅ Processing...");
            isSpeakingRef.current = false;

            // Send audio_end signal to prevent repetitions
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({
                type: "audio_end",
                room_id: roomId,
                seq: 0
              }));
              console.log('[VAD] Sent audio_end signal');
            }

            partialBufferRef.current = new Float32Array(0);
            ringBufferRef.current = new Float32Array(0);  // Clear ring buffer to prevent previous audio contamination
            currentSegmentHintRef.current = null;
            setTimeout(() => setVadStatus("👂 Listening..."), 300);
          }
        }

        // SAFETY: Force stop if recording exceeds 30 seconds
        if (isSpeakingRef.current && currentSegmentHintRef.current) {
          const recordingDuration = Date.now() - currentSegmentHintRef.current;
          if (recordingDuration > 30000) {
            console.log(`[VAD] ⚠️ Force stopping - exceeded 30s limit (${recordingDuration}ms)`);
            isSpeakingRef.current = false;

            // Send audio_end signal
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              wsRef.current.send(JSON.stringify({
                type: "audio_end",
                room_id: roomId,
                seq: 0
              }));
              console.log('[VAD] Sent audio_end signal (force stop)');
            }

            partialBufferRef.current = new Float32Array(0);
            ringBufferRef.current = new Float32Array(0);  // Clear ring buffer
            currentSegmentHintRef.current = null;
            setVadStatus("⚠️ Auto-stopped");
            setTimeout(() => setVadStatus("👂 Listening..."), 1000);
          }
        }

        // Always update ring buffer (even when not speaking) to capture speech onset
        const ringBufferSize = Math.floor(targetSampleRate * RING_BUFFER_MS / 1000); // 500ms at 16kHz = 8000 samples
        const oldRing = ringBufferRef.current;
        const newRing = new Float32Array(Math.min(oldRing.length + resampled.length, ringBufferSize));
        if (oldRing.length + resampled.length <= ringBufferSize) {
          // Buffer not full yet, just append
          newRing.set(oldRing);
          newRing.set(resampled, oldRing.length);
        } else {
          // Buffer full, shift and append (keep last ringBufferSize samples)
          const offset = oldRing.length + resampled.length - ringBufferSize;
          newRing.set(oldRing.subarray(offset));
          newRing.set(resampled, newRing.length - resampled.length);
        }
        ringBufferRef.current = newRing;

        // Accumulate resampled audio during speech
        if (isSpeakingRef.current) {
          const oldLen = partialBufferRef.current.length;
          const newBuffer = new Float32Array(oldLen + resampled.length);
          newBuffer.set(partialBufferRef.current);
          newBuffer.set(resampled, oldLen);
          partialBufferRef.current = newBuffer;
          sendPartialIfReady();
        }
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      // Store references for cleanup
      audioContextRef.current = audioContext;
      scriptProcessorRef.current = processor;
      streamRef.current = stream;

      console.log('[VAD] ✅ Voice activity detection started successfully');
      setVadReady(true);
      setVadStatus("👂 Listening...");
      isRecordingRef.current = true;
    } catch (err) {
      console.error('[VAD] ❌ Failed to start:', err);
      setStatus("mic error");
      setVadStatus("❌ Microphone error");
      alert(`Failed to start microphone: ${err.message}`);
      return;
    }
  }

  function stop() {
    isRecordingRef.current = false;
    isSpeakingRef.current = false;
    setVadReady(false);

    // Stop custom VAD and clean up audio resources
    console.log('[VAD] Stopping voice activity detection...');

    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    console.log('[VAD] ✅ Voice activity detection stopped');

    try {
      if (wsRef.current && wsRef.current.readyState === 1) {
        wsRef.current.send(JSON.stringify({ type: "audio_end", roomId: roomId, device: "web" }));
      }
    } catch {}

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus("idle");
    setVadStatus("idle");
  }

  // Test mode for Sound Settings - starts microphone without sending to STT
  async function handleTestMode(shouldStart) {
    if (shouldStart) {
      // Check if recording is already active
      if (isRecordingRef.current) {
        // Already recording - just enable test mode flag to show we're in test view
        // Audio levels are already being monitored
        setTestMode(true);
        console.log('[Test Mode] Using active recording stream for monitoring');
        return;
      }

      // Start test mode with new stream
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,
            sampleRate: { ideal: 48000 },  // Same as recording mode
            echoCancellation: true,
            noiseSuppression: false,       // Same as recording mode
            autoGainControl: true          // Same as recording mode
          }
        });
        testStreamRef.current = stream;

        // Use browser's default sample rate (same as recording mode)
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        testAudioContextRef.current = audioContext;

        const source = audioContext.createMediaStreamSource(stream);
        const processor = audioContext.createScriptProcessor(4096, 1, 1);
        testProcessorRef.current = processor;

        processor.onaudioprocess = (e) => {
          const inputData = e.inputBuffer.getChannelData(0);

          // Calculate RMS energy (same as recording mode VAD)
          let sum = 0;
          for (let i = 0; i < inputData.length; i++) {
            sum += inputData[i] * inputData[i];
          }
          const rms = Math.sqrt(sum / inputData.length);

          // Update audio level
          audioLevelRef.current = rms;
          setAudioLevel(rms);
        };

        source.connect(processor);
        processor.connect(audioContext.destination);

        setTestMode(true);
        console.log('[Test Mode] Microphone test started');
      } catch (err) {
        console.error('[Test Mode] Failed to start:', err);

        // More specific error message
        let errorMsg = 'Could not access microphone. ';
        if (err.name === 'NotAllowedError') {
          errorMsg += 'Permission denied. Please allow microphone access in your browser settings.';
        } else if (err.name === 'NotFoundError') {
          errorMsg += 'No microphone found. Please connect a microphone.';
        } else if (err.name === 'NotReadableError') {
          errorMsg += 'Microphone is already in use by another application.';
        } else {
          errorMsg += 'Error: ' + err.message;
        }
        alert(errorMsg);
      }
    } else {
      // Stop test mode
      if (isRecordingRef.current) {
        // If recording is active, just turn off test mode flag
        // Don't clean up streams since they're being used by recording
        setTestMode(false);
        console.log('[Test Mode] Exited test mode (recording still active)');
        return;
      }

      // Clean up test mode resources
      if (testProcessorRef.current) {
        testProcessorRef.current.disconnect();
        testProcessorRef.current = null;
      }

      if (testStreamRef.current) {
        testStreamRef.current.getTracks().forEach(track => track.stop());
        testStreamRef.current = null;
      }

      if (testAudioContextRef.current) {
        testAudioContextRef.current.close();
        testAudioContextRef.current = null;
      }

      setTestMode(false);
      setAudioLevel(0);
      console.log('[Test Mode] Microphone test stopped');
    }
  }

  async function fetchCosts() {
    try {
      const r = await fetch(`/api/costs/room/${encodeURIComponent(roomId)}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (r.ok) setCosts(await r.json());
    } catch (e) {
      console.error("Failed to fetch costs:", e);
    }
  }
  
  async function fetchHistory() {
    // Show loading when changing language with existing messages
    if (segsRef.current.size > 0) {
      setLines([]);
    }
    setLoadingHistory(true);
    
    try {
      console.log(`[History] Fetching: room=${roomId}, target=${myLanguage}`);
      const r = await fetch(
        `/history/room/${encodeURIComponent(roomId)}?target_lang=${encodeURIComponent(myLanguage)}`,
        {
          headers: { 'Authorization': `Bearer ${token}` }
        }
      );
      
      if (!r.ok) {
        console.error(`[History] HTTP ${r.status}: ${r.statusText}`);
        setLoadingHistory(false);
        return;
      }
      
      const data = await r.json();
      console.log(`[History] Loaded ${data.count} segments`);
      
      // Clear old history segments (keep live segments from current session)
      const now = Date.now();
      const recentThreshold = now - 30000;
      const keysToDelete = [];
      
      for (const [key, msg] of segsRef.current.entries()) {
        const msgTime = msg.ts_iso ? new Date(msg.ts_iso).getTime() : now;
        if (msgTime < recentThreshold) {
          keysToDelete.push(key);
        }
      }
      
      keysToDelete.forEach(key => segsRef.current.delete(key));
      
      // Load history into chat
      if (data.segments && data.segments.length > 0) {
        data.segments.forEach(seg => {
          const id = parseInt(seg.segment_id) || Date.now();
          
          segsRef.current.set(`s-${id}`, {
            type: "stt_final",
            segment_id: id,
            text: seg.original_text,
            lang: seg.source_lang,
            final: true,
            speaker: seg.speaker,
            ts_iso: seg.timestamp
          });
          
          if (seg.translated_text && seg.translated_text !== seg.original_text) {
            segsRef.current.set(`t-${id}`, {
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
        scheduleRender();
      }
    } catch (e) {
      console.error("[History] Failed to fetch:", e);
    } finally {
      setLoadingHistory(false);
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
  
  const myLang = languages.find(l => l.code === myLanguage);

  return (
    <div style={{
      height: "100dvh",
      display: "flex",
      flexDirection: "column",
      background: "#0a0a0a",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif",
      overflow: "hidden"
    }}>
      {/* Top header - back, centered room name, language, costs */}
      <div style={{
        background: "#1a1a1a",
        borderBottom: "1px solid #333",
        padding: "0.5rem 0.75rem",
        paddingTop: "max(0.5rem, env(safe-area-inset-top))",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "0.5rem",
        flexShrink: 0
      }}>
        {/* Back button - left */}
        <button
          onClick={handleBackClick}
          style={{
            background: "#2a2a2a",
            border: "1px solid #444",
            borderRadius: "8px",
            color: "white",
            cursor: "pointer",
            padding: "0.5rem 0.75rem",
            fontSize: "1.1rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minWidth: "40px",
            flexShrink: 0
          }}
        >
          ←
        </button>
        
        {/* Room name and status - center */}
        <div style={{
          flex: 1,
          textAlign: "center",
          minWidth: 0
        }}>
          <div style={{
            fontSize: "0.9rem",
            fontWeight: "600",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.4rem"
          }}>
            <span>{roomId}</span>
            {activeLanguages.size > 0 && (
              <span style={{
                fontSize: "0.85rem",
                display: "inline-flex",
                gap: "0.2rem"
              }}>
                {Array.from(activeLanguages).map(langCode => {
                  const lang = languages.find(l => l.code === langCode);
                  return lang ? lang.flag : null;
                })}
              </span>
            )}
          </div>
          {vadStatus !== "idle" && (
            <div style={{
              fontSize: "0.65rem",
              color: vadReady ? "#16a34a" : "#999",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap"
            }}>
              {vadStatus}
            </div>
          )}
        </div>
        
        {/* Menu button - right */}
        <button
          onClick={() => setShowSettings(true)}
          style={{
            background: "#2a2a2a",
            border: "1px solid #444",
            borderRadius: "8px",
            color: "white",
            cursor: "pointer",
            padding: "0.5rem 0.75rem",
            fontSize: "1.1rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            minWidth: "40px",
            flexShrink: 0
          }}
          title="Menu"
        >
          ⋮
        </button>
      </div>

      {/* Admin Absence Banner - Countdown Timer */}
      {!isRoomAdmin && roomStatus && !roomStatus.admin_present && timeRemaining !== null && timeRemaining > 0 && (
        <div style={{
          background: timeRemaining < 60000
            ? "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)"
            : "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
          padding: "0.75rem 1rem",
          color: "white",
          fontSize: "0.85rem",
          fontWeight: "600",
          textAlign: "center",
          borderBottom: "1px solid rgba(255,255,255,0.2)",
          boxShadow: "0 2px 8px rgba(0,0,0,0.3)"
        }}>
          <div style={{ marginBottom: "0.25rem" }}>
            ⚠️ Room admin has left
          </div>
          <div style={{ fontSize: "0.75rem", fontWeight: "normal", opacity: 0.95 }}>
            Room will close in {formatCountdown(timeRemaining)}
          </div>
          {timeRemaining < 60000 && (
            <div style={{ fontSize: "0.7rem", fontWeight: "normal", opacity: 0.85, marginTop: "0.25rem" }}>
              Recording and translation will be disabled soon
            </div>
          )}
        </div>
      )}

      {/* Language Picker Modal */}
      {showLangPicker && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.85)",
          zIndex: 100,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1rem"
        }}
        onClick={() => setShowLangPicker(false)}
        >
          <div style={{
            background: "#1a1a1a",
            borderRadius: "16px",
            padding: "1.5rem",
            maxWidth: "400px",
            width: "100%",
            border: "1px solid #333"
          }}
          onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{margin: "0 0 1rem 0", fontSize: "1.2rem"}}>My Language</h3>
            <p style={{margin: "0 0 1rem 0", fontSize: "0.85rem", color: "#999"}}>
              Select the language you speak and want to read messages in.
              Messages will be automatically translated to your language.
            </p>

            <div style={{marginBottom: "1.5rem"}}>
              <label style={{display: "block", fontSize: "0.85rem", color: "#999", marginBottom: "0.5rem"}}>
                I speak and want to read
              </label>
              <select
                value={myLanguage}
                onChange={(e) => setMyLanguage(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.85rem",
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  borderRadius: "10px",
                  color: "white",
                  fontSize: "1rem"
                }}
              >
                {languages.filter(l => l.code !== "auto").map(lang => (
                  <option key={lang.code} value={lang.code}>
                    {lang.flag} {lang.name}
                  </option>
                ))}
              </select>
            </div>
            
            <button
              onClick={() => setShowLangPicker(false)}
              style={{
                width: "100%",
                padding: "0.85rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
                fontWeight: "600",
                fontSize: "1rem"
              }}
            >
              Done
            </button>
          </div>
        </div>
      )}
      
      {/* Costs Modal */}
      {showCosts && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.85)",
          zIndex: 100,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1rem"
        }}
        onClick={() => setShowCosts(false)}
        >
          <div style={{
            background: "#1a1a1a",
            borderRadius: "16px",
            padding: "1.5rem",
            maxWidth: "400px",
            width: "100%",
            border: "1px solid #333"
          }}
          onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{margin: "0 0 0.75rem 0", fontSize: "1.2rem"}}>💰 Costs</h3>
            {!costs ? (
              <div style={{textAlign: "center", color: "#999", padding: "2rem", fontSize: "0.9rem"}}>
                Loading costs...
              </div>
            ) : (
              <>
                <div style={{fontSize: "1.75rem", fontWeight: "bold", color: "#3b82f6", marginBottom: "1rem"}}>
                  ${costs.total_cost_usd.toFixed(6)}
                </div>
                
                <div style={{display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem"}}>
                  {Object.entries(costs.breakdown || {}).map(([pipeline, data]) => (
                    <div key={pipeline} style={{background: "#2a2a2a", padding: "0.85rem", borderRadius: "10px"}}>
                      <div style={{fontWeight: "600", fontSize: "0.95rem", marginBottom: "0.25rem"}}>
                        {pipeline === "mt" ? "🔤 Translation" : "🎤 STT"}
                      </div>
                      <div style={{fontSize: "0.8rem", color: "#999"}}>
                        {data.events} events • ${data.cost_usd.toFixed(6)}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
            
            <button
              onClick={() => setShowCosts(false)}
              style={{
                width: "100%",
                padding: "0.85rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
                fontWeight: "600",
                fontSize: "1rem"
              }}
            >
              Close
            </button>
          </div>
        </div>
      )}
      
      {/* Chat Messages - Scrollable */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        overflowX: "hidden",
        padding: "0.75rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem",
        WebkitOverflowScrolling: "touch"
      }}>
        {loadingHistory && lines.length === 0 && (
          <div style={{
            textAlign: "center",
            color: "#666",
            padding: "2rem 1rem",
            margin: "auto",
            fontSize: "0.9rem"
          }}>
            📜 Loading history...
          </div>
        )}

        {!loadingHistory && lines.length === 0 && (
          <div style={{
            textAlign: "center",
            color: "#666",
            padding: "2rem 1rem",
            margin: "auto",
            fontSize: "0.9rem"
          }}>
            Press the microphone to start
          </div>
        )}

        {lines.map(([segId, seg]) => {
          const timestamp = seg.source?.ts_iso || seg.translation?.ts_iso;

          // Check if this is a system message
          const isSystemMessage = seg.source?.is_system === true;

          // Render system messages differently - smaller and less prominent
          if (isSystemMessage) {
            return (
              <div key={segId} style={{
                textAlign: "center",
                padding: "0.25rem",
                color: "#666",
                fontSize: "0.7rem",
                fontStyle: "italic"
              }}>
                <span style={{
                  background: "rgba(42, 42, 42, 0.5)",
                  padding: "0.25rem 0.6rem",
                  borderRadius: "10px",
                  display: "inline-block",
                  border: "1px solid rgba(255, 255, 255, 0.05)"
                }}>
                  {seg.source.text}
                </span>
              </div>
            );
          }

          return (
            <div key={segId} style={{
              background: "#1a1a1a",
              borderRadius: "12px",
              padding: "0.5rem 0.65rem",
              border: "1px solid #333"
            }}>
              {seg.translation ? (
                <>
                  {/* Translation - large font with username/time on left */}
                  <div style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "0.5rem"
                  }}>
                    {/* Username and timestamp column */}
                    {seg.source && seg.source.speaker && seg.source.speaker !== "system" && (
                      <div style={{
                        display: "flex",
                        flexDirection: "column",
                        flexShrink: 0,
                        minWidth: "fit-content"
                      }}>
                        <span style={{
                          fontSize: "0.65rem",
                          color: "#3b82f6",
                          fontWeight: "600",
                          lineHeight: "1.2"
                        }}>
                          👤 {seg.source.speaker.split('@')[0]}
                        </span>
                        {timestamp && (
                          <span style={{
                            fontSize: "0.6rem",
                            color: "#666",
                            lineHeight: "1.2"
                          }}>
                            {formatTime(timestamp)}
                          </span>
                        )}
                      </div>
                    )}
                    {/* Message text */}
                    <span style={{
                      color: seg.translation.final ? "#fff" : "#bbb",
                      fontSize: "1rem",
                      fontWeight: "500",
                      lineHeight: "1.45",
                      flex: 1,
                      minWidth: 0
                    }}>
                      {seg.translation.text === '___SPEAKING___' ? (
                        <>
                          <span className="processing-spinner" style={{ color: "#3b82f6" }}>🎤</span>
                          <span style={{ fontStyle: "italic" }}> Speaking...</span>
                        </>
                      ) : (
                        <>
                          {seg.translation.text}
                          {!seg.translation.final && (
                            <span className="processing-spinner" style={{marginLeft: "0.5rem", color: "#3b82f6"}}>⋯</span>
                          )}
                        </>
                      )}
                    </span>
                  </div>
                  {seg.translation.final && seg.translation.processing && (
                    <div style={{
                      fontSize: "0.75rem",
                      color: "#888",
                      marginTop: "0.25rem",
                      display: "flex",
                      alignItems: "center",
                      gap: "0.4rem"
                    }}>
                      <span className="processing-spinner">⚙️</span>
                      <span>{getProcessingText(myLanguage || 'en')}</span>
                    </div>
                  )}
                  {/* Original text - small font below */}
                  {seg.source && (
                    <div style={{
                      color: "#666",
                      fontSize: "0.8rem",
                      fontStyle: "italic",
                      lineHeight: "1.35"
                    }}>
                      {seg.source.text}
                    </div>
                  )}
                </>
              ) : (
                <>
                  {/* No translation - show source in large font (own message) with username/time on left */}
                  {seg.source && (
                    <>
                      <div style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: "0.5rem"
                      }}>
                        {/* Username and timestamp column */}
                        {seg.source.speaker && seg.source.speaker !== "system" && (
                          <div style={{
                            display: "flex",
                            flexDirection: "column",
                            flexShrink: 0,
                            minWidth: "fit-content"
                          }}>
                            <span style={{
                              fontSize: "0.65rem",
                              color: "#3b82f6",
                              fontWeight: "600",
                              lineHeight: "1.2"
                            }}>
                              👤 {seg.source.speaker.split('@')[0]}
                            </span>
                            {timestamp && (
                              <span style={{
                                fontSize: "0.6rem",
                                color: "#666",
                                lineHeight: "1.2"
                              }}>
                                {formatTime(timestamp)}
                              </span>
                            )}
                          </div>
                        )}
                        {/* Message text */}
                        <span style={{
                          color: seg.source.final ? "#fff" : "#bbb",
                          fontSize: "1rem",
                          fontWeight: "500",
                          lineHeight: "1.45",
                          flex: 1,
                          minWidth: 0
                        }}>
                          {seg.source.text === '___SPEAKING___' ? (
                            <>
                              <span className="processing-spinner" style={{ color: "#3b82f6" }}>🎤</span>
                              <span style={{ fontStyle: "italic" }}> Speaking...</span>
                            </>
                          ) : (
                            <>
                              {seg.source.text}
                              {!seg.source.final && (
                                <span className="processing-spinner" style={{marginLeft: "0.5rem", color: "#3b82f6"}}>⋯</span>
                              )}
                            </>
                          )}
                        </span>
                      </div>
                      {seg.source.final && seg.source.processing && (
                        <div style={{
                          fontSize: "0.75rem",
                          color: "#888",
                          marginTop: "0.25rem",
                          display: "flex",
                          alignItems: "center",
                          gap: "0.4rem"
                        }}>
                          <span className="processing-spinner">⚙️</span>
                          <span>{getProcessingText(myLanguage || 'en')}</span>
                        </div>
                      )}
                    </>
                  )}
                </>
              )}
            </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>
      
      {/* Bottom Controls - Fixed at bottom */}
      <div style={{
        background: "#1a1a1a",
        borderTop: "1px solid #333",
        padding: "0.75rem",
        paddingBottom: "max(0.75rem, env(safe-area-inset-bottom))",
        flexShrink: 0
      }}>
        {/* Push to talk checkbox and Network Status */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: "1rem",
          marginBottom: "0.65rem"
        }}>
          <label style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            fontSize: "0.8rem",
            color: "#999",
            cursor: "pointer"
          }}>
            <input
              type="checkbox"
              checked={pushToTalk}
              onChange={(e) => setPushToTalk(e.target.checked)}
              disabled={status !== "idle"}
              style={{
                cursor: status === "idle" ? "pointer" : "not-allowed",
                width: "18px",
                height: "18px"
              }}
            />
            Push to talk
          </label>

          {/* Network Status Indicator - Inline */}
          {networkQuality !== 'unknown' && (
            <div style={{
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
              padding: "0.25rem 0.5rem",
              borderRadius: "12px",
              backgroundColor: "rgba(255, 255, 255, 0.05)",
              fontSize: "0.75rem",
              color: "#999"
            }}>
              <div style={{
                width: "12px",
                height: "12px",
                borderRadius: "50%",
                backgroundColor: networkQuality === 'high' ? '#10b981' : networkQuality === 'medium' ? '#f59e0b' : '#ef4444',
                boxShadow: `0 0 6px ${networkQuality === 'high' ? '#10b981' : networkQuality === 'medium' ? '#f59e0b' : '#ef4444'}`
              }} />
              {networkRTT !== null && (
                <span>{networkRTT}ms</span>
              )}
            </div>
          )}
        </div>
        
        {/* Microphone button */}
        <button
          onClick={status === "idle" ? start : stop}
          onTouchStart={pushToTalk && status === "streaming" ? () => setIsPressing(true) : undefined}
          onTouchEnd={pushToTalk && status === "streaming" ? () => setIsPressing(false) : undefined}
          onMouseDown={pushToTalk && status === "streaming" ? () => setIsPressing(true) : undefined}
          onMouseUp={pushToTalk && status === "streaming" ? () => setIsPressing(false) : undefined}
          style={{
            width: "100%",
            height: "56px",
            borderRadius: "28px",
            background: status === "idle" 
              ? "#16a34a" 
              : (pushToTalk && isPressing) 
                ? "#dc2626"
                : "#dc2626",
            color: "white",
            border: "none",
            fontSize: "1.05rem",
            fontWeight: "600",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            boxShadow: "0 4px 12px rgba(0,0,0,0.4)",
            WebkitTapHighlightColor: "transparent"
          }}
        >
          {status === "idle" ? (
            <>🎤 Start</>
          ) : pushToTalk ? (
            isPressing ? <>🔴 Recording</> : <>👆 Hold to Speak</>
          ) : (
            <>⏹ Stop</>
          )}
        </button>
      </div>

      {/* Settings Menu */}
      <SettingsMenu
        isOpen={showSettings}
        onClose={() => setShowSettings(false)}
        isGuest={isGuest}
        myLanguage={myLanguage}
        languages={languages}
        onLanguageChange={() => {
          setShowSettings(false);
          setShowLangPicker(true);
        }}
        onShowParticipants={() => {
          setShowSettings(false);
          setShowParticipants(true);
        }}
        onShowInvite={() => {
          setShowSettings(false);
          setShowInvite(true);
        }}
        onShowCosts={() => {
          setShowSettings(false);
          fetchCosts();
          setShowCosts(true);
        }}
        onShowSound={() => {
          setShowSettings(false);
          setShowSoundSettings(true);
        }}
        onLogout={onLogout}
        canChangeLanguage={status === "idle"}
        persistenceEnabled={persistenceEnabled}
        onTogglePersistence={() => setPersistenceEnabled(!persistenceEnabled)}
        isRoomAdmin={isRoomAdmin}
        isPublic={isPublic}
        onTogglePublic={() => setIsPublic(!isPublic)}
        onShowRoomAdminSettings={() => {
          setShowSettings(false);
          setShowRoomAdminSettings(true);
        }}
      />

      {/* Invite Modal */}
      {showInvite && (
        <InviteModal
          roomCode={roomId}
          onClose={() => setShowInvite(false)}
        />
      )}

      {/* Participants Modal */}
      {showParticipants && (
        <ParticipantsModal
          roomCode={roomId}
          token={token}
          isOpen={showParticipants}
          onClose={() => setShowParticipants(false)}
        />
      )}

      {/* Sound Settings Modal */}
      <SoundSettingsModal
        isOpen={showSoundSettings}
        onClose={() => setShowSoundSettings(false)}
        currentLevel={audioLevel}
        threshold={audioThreshold}
        onThresholdChange={setAudioThreshold}
        isActive={isSpeakingRef.current}
        status={vadStatus}
        onTest={handleTestMode}
      />

      {/* Admin Leave Warning Modal */}
      {showAdminLeaveWarning && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.9)",
          zIndex: 150,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1rem"
        }}>
          <div style={{
            background: "#1a1a1a",
            borderRadius: "16px",
            padding: "2rem",
            maxWidth: "400px",
            width: "100%",
            border: "2px solid #f59e0b"
          }}>
            <div style={{ fontSize: "2.5rem", textAlign: "center", marginBottom: "1rem" }}>
              ⚠️
            </div>
            <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.3rem", textAlign: "center" }}>
              Are you sure you want to leave?
            </h3>
            <p style={{ margin: "0 0 1.5rem 0", fontSize: "0.95rem", color: "#ccc", lineHeight: "1.5" }}>
              As the room admin, when you leave:
            </p>
            <ul style={{ margin: "0 0 1.5rem 0", fontSize: "0.9rem", color: "#ccc", lineHeight: "1.6", paddingLeft: "1.5rem" }}>
              <li>Other participants will be notified</li>
              <li>Recording and translation will be disabled</li>
              <li>The room will <strong style={{ color: "#f59e0b" }}>automatically close in 30 minutes</strong></li>
              <li>All participants will be removed when time expires</li>
            </ul>
            <p style={{ margin: "0 0 1.5rem 0", fontSize: "0.85rem", color: "#999", fontStyle: "italic" }}>
              You can rejoin anytime within 30 minutes to reset the timer.
            </p>
            <div style={{ display: "flex", gap: "0.75rem" }}>
              <button
                onClick={() => setShowAdminLeaveWarning(false)}
                style={{
                  flex: 1,
                  padding: "0.85rem",
                  background: "#3b82f6",
                  color: "white",
                  border: "none",
                  borderRadius: "10px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "1rem"
                }}
              >
                Stay
              </button>
              <button
                onClick={() => {
                  setShowAdminLeaveWarning(false);
                  navigate("/rooms");
                }}
                style={{
                  flex: 1,
                  padding: "0.85rem",
                  background: "#dc2626",
                  color: "white",
                  border: "none",
                  borderRadius: "10px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "1rem"
                }}
              >
                Leave Anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Admin Left Notification - Dismissible */}
      {showAdminLeftNotification && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.85)",
          zIndex: 150,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1rem"
        }}
        onClick={() => setShowAdminLeftNotification(false)}
        >
          <div style={{
            background: "#1a1a1a",
            borderRadius: "16px",
            padding: "2rem",
            maxWidth: "400px",
            width: "100%",
            border: "2px solid #f59e0b"
          }}
          onClick={(e) => e.stopPropagation()}
          >
            <div style={{ fontSize: "2.5rem", textAlign: "center", marginBottom: "1rem" }}>
              ⚠️
            </div>
            <h3 style={{ margin: "0 0 1rem 0", fontSize: "1.3rem", textAlign: "center" }}>
              Room Admin Has Left
            </h3>
            <p style={{ margin: "0 0 1.5rem 0", fontSize: "0.95rem", color: "#ccc", lineHeight: "1.5", textAlign: "center" }}>
              The room creator has disconnected from this session.
            </p>
            <div style={{ background: "#2a2a2a", padding: "1rem", borderRadius: "12px", marginBottom: "1.5rem" }}>
              <p style={{ margin: "0 0 0.5rem 0", fontSize: "0.9rem", color: "#fff", fontWeight: "600" }}>
                What happens next:
              </p>
              <ul style={{ margin: "0", fontSize: "0.85rem", color: "#ccc", lineHeight: "1.6", paddingLeft: "1.5rem" }}>
                <li>You can continue using the room</li>
                <li>A countdown timer will be visible at the top</li>
                <li>The room will close automatically in <strong style={{ color: "#f59e0b" }}>30 minutes</strong></li>
                <li>If the admin rejoins, the timer will reset</li>
              </ul>
            </div>
            <button
              onClick={() => setShowAdminLeftNotification(false)}
              style={{
                width: "100%",
                padding: "0.85rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "10px",
                cursor: "pointer",
                fontWeight: "600",
                fontSize: "1rem"
              }}
            >
              Got it
            </button>
          </div>
        </div>
      )}

      {/* Room Expiration Modal */}
      {showExpirationModal && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          background: "rgba(0,0,0,0.95)",
          zIndex: 200,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "1rem"
        }}>
          <div style={{
            background: "#1a1a1a",
            borderRadius: "16px",
            padding: "2.5rem 2rem",
            maxWidth: "450px",
            width: "100%",
            border: "2px solid #dc2626",
            textAlign: "center"
          }}>
            <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>
              👋
            </div>
            <h2 style={{ margin: "0 0 1rem 0", fontSize: "1.5rem", color: "white" }}>
              Thank you for joining!
            </h2>
            <p style={{ margin: "0 0 1.5rem 0", fontSize: "1rem", color: "#ccc", lineHeight: "1.6" }}>
              This room has been closed because the admin has been away for 30 minutes.
            </p>
            <p style={{ margin: "0 0 2rem 0", fontSize: "0.9rem", color: "#999" }}>
              Create your own account to host unlimited translation rooms.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <button
                onClick={() => navigate("/register")}
                style={{
                  width: "100%",
                  padding: "1rem",
                  background: "#3b82f6",
                  color: "white",
                  border: "none",
                  borderRadius: "12px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "1.05rem"
                }}
              >
                Create Account
              </button>
              <button
                onClick={() => navigate("/login")}
                style={{
                  width: "100%",
                  padding: "1rem",
                  background: "#2a2a2a",
                  color: "white",
                  border: "1px solid #444",
                  borderRadius: "12px",
                  cursor: "pointer",
                  fontWeight: "600",
                  fontSize: "1.05rem"
                }}
              >
                Sign In
              </button>
            </div>
          </div>
        </div>
      )}

      {/* NOTE: Room Admin Settings removed - using language-based routing (Migration 006) */}
    </div>
  );
}
