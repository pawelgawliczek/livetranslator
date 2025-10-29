/**
 * usePresenceWebSocket Hook
 *
 * Manages the persistent presence WebSocket connection for a room.
 *
 * Features:
 * - WebSocket connection management
 * - Presence events (user_joined, user_left, language_changed, presence_snapshot)
 * - Network monitoring (ping/pong, RTT measurement, quality classification)
 * - Participant and language count tracking
 * - Welcome banner and toast notifications
 *
 * @param {Object} options
 * @param {string} options.roomId - Room identifier
 * @param {string} options.token - Authentication token
 * @param {boolean} options.isGuest - Whether user is a guest
 * @param {string} options.myLanguage - Current user's language preference
 * @param {string} options.initialLanguage - Initial language to set on connection
 * @param {Function} options.onMessage - Callback for STT/translation messages
 *
 * @returns {Object} Presence state and methods
 */

import { useEffect, useRef, useState } from 'react';
import { LANGUAGES } from '../constants/languages';

export default function usePresenceWebSocket({
  roomId,
  token,
  isGuest,
  myLanguage,
  initialLanguage,
  onMessage
}) {
  // Connection state
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef(null);

  // Presence state
  const [participants, setParticipants] = useState([]);
  const [languageCounts, setLanguageCounts] = useState({});
  const [showWelcome, setShowWelcome] = useState(false);
  const [notifications, setNotifications] = useState([]);

  // Network monitoring state
  const [networkQuality, setNetworkQuality] = useState('unknown');
  const [networkRTT, setNetworkRTT] = useState(null);

  // Network monitoring refs
  const pingIntervalRef = useRef(null);
  const pingTimeoutRef = useRef(null);
  const pendingPingRef = useRef(null);
  const rttMeasurements = useRef([]);
  const networkQualityRef = useRef('unknown');

  // Notification debouncing
  const notificationDebounce = useRef(new Map());

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

    // Log quality change and update state
    if (quality !== networkQualityRef.current && networkQualityRef.current !== 'unknown') {
      console.log(`[Network] Quality changed: ${networkQualityRef.current} → ${quality} (${Math.round(avgRTT)}ms avg RTT)`);
    }
    networkQualityRef.current = quality;
    setNetworkQuality(quality);
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
    setNetworkQuality('unknown');
    setNetworkRTT(null);
  };

  // Presence event handlers
  const handlePresenceSnapshot = (data) => {
    if (data.participants && Array.isArray(data.participants)) {
      setParticipants(data.participants);
    }
    if (data.language_counts) {
      setLanguageCounts(data.language_counts);
    }

    // Show welcome banner on first snapshot
    if (!showWelcome) {
      setShowWelcome(true);
      setTimeout(() => setShowWelcome(false), 10000); // Auto-dismiss after 10s
    }
  };

  const handleUserJoined = (data) => {
    if (data.participants && Array.isArray(data.participants)) {
      setParticipants(data.participants);
    }
    if (data.language_counts) {
      setLanguageCounts(data.language_counts);
    }

    // Show notification with debouncing
    showPresenceNotification(data, 'joined');
  };

  const handleUserLeft = (data) => {
    if (data.participants && Array.isArray(data.participants)) {
      setParticipants(data.participants);
    }
    if (data.language_counts) {
      setLanguageCounts(data.language_counts);
    }

    // Show notification with debouncing
    showPresenceNotification(data, 'left');
  };

  const handleLanguageChanged = (data) => {
    if (data.participants && Array.isArray(data.participants)) {
      setParticipants(data.participants);
    }
    if (data.language_counts) {
      setLanguageCounts(data.language_counts);
    }

    // Show notification (no debouncing for language changes)
    showPresenceNotification(data, 'language_changed');
  };

  const showPresenceNotification = (data, eventType) => {
    if (!data.triggered_by_user_id) return;

    const triggeredBy = data.triggered_by_user_id;
    const now = Date.now();
    const lastNotification = notificationDebounce.current.get(triggeredBy);

    // Debounce for join/left events only (to avoid spam during reconnections)
    // Language changes always show notification
    const isLanguageChange = eventType === 'language_changed';
    const shouldShowNotification = isLanguageChange || !lastNotification || now - lastNotification > 10000;

    if (!shouldShowNotification) return;

    // Only update debounce timestamp for join/leave events
    if (!isLanguageChange) {
      notificationDebounce.current.set(triggeredBy, now);
    }

    // For user_left events, use the left_user info from the event
    // For other events, find participant info from current participants
    let participant;
    if (eventType === 'left' && data.left_user) {
      participant = data.left_user;
    } else {
      participant = data.participants?.find(p => p.user_id === triggeredBy);
    }

    if (!participant) return;

    const name = participant.display_name;
    // Normalize language code to base language (e.g., "en-GB" -> "en")
    const baseLang = participant.language?.split('-')[0] || participant.language;
    const lang = LANGUAGES.find(l => l.code === baseLang);

    let message = '';
    if (eventType === 'joined') {
      message = `${lang?.flag || '🌐'} ${name}${participant.is_guest ? ' (guest)' : ''} joined with ${lang?.name || participant.language}`;
    } else if (eventType === 'left') {
      message = `${name}${participant.is_guest ? ' (guest)' : ''} left the room`;
    } else if (eventType === 'language_changed') {
      // Normalize language code for language change as well
      const baseNewLang = data.new_language?.split('-')[0] || data.new_language;
      const newLang = LANGUAGES.find(l => l.code === baseNewLang);
      message = `${newLang?.flag || '🌐'} ${name}${participant.is_guest ? ' (guest)' : ''} changed to ${newLang?.name || data.new_language}`;
    }

    if (message) {
      const notif = { id: Date.now(), message };
      setNotifications(prev => [...prev, notif].slice(-3)); // Keep last 3

      // Auto-dismiss after 5 seconds
      setTimeout(() => {
        setNotifications(prev => prev.filter(n => n.id !== notif.id));
      }, 5000);
    }
  };

  // Establish WebSocket connection
  useEffect(() => {
    let authToken = token;
    if (isGuest) {
      authToken = sessionStorage.getItem('guest_token');
    }

    if (!authToken) {
      console.log('[usePresenceWebSocket] No auth token, skipping connection');
      return;
    }

    try {
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const wsUrl = `${protocol}//${window.location.host}/ws/rooms/${encodeURIComponent(roomId)}?token=${encodeURIComponent(authToken)}`;
      console.log('[usePresenceWebSocket] Opening WebSocket:', wsUrl);

      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[usePresenceWebSocket] Connected');
        setIsConnected(true);

        // Send initial language preference (if provided)
        const langToSend = initialLanguage || myLanguage;
        if (langToSend) {
          ws.send(JSON.stringify({
            type: "set_language",
            language: langToSend
          }));
          console.log('[usePresenceWebSocket] Sent initial language:', langToSend);
        }

        // Start network monitoring
        startNetworkMonitoring(ws);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Handle ping-pong for network monitoring
          if (data.type === 'pong') {
            handlePong(data);
            return;
          }

          // Handle presence events
          if (data.type === 'presence_snapshot') {
            handlePresenceSnapshot(data);
          } else if (data.type === 'user_joined') {
            handleUserJoined(data);
          } else if (data.type === 'user_left') {
            handleUserLeft(data);
          } else if (data.type === 'language_changed') {
            handleLanguageChanged(data);
          }
          // Forward STT/translation messages to parent handler
          else if (onMessage && (
            data.type?.includes('translation') ||
            data.type?.includes('stt') ||
            data.type?.includes('partial') ||
            data.type?.includes('final') ||
            data.type === 'speech_started'
          )) {
            onMessage(event);
          }
        } catch (e) {
          console.log('[usePresenceWebSocket] Received non-JSON:', event.data);
        }
      };

      ws.onerror = (err) => {
        console.error('[usePresenceWebSocket] Error:', err);
      };

      ws.onclose = () => {
        console.log('[usePresenceWebSocket] Closed');
        setIsConnected(false);
      };
    } catch (e) {
      console.error('[usePresenceWebSocket] Failed to create WebSocket:', e);
    }

    // Cleanup: close WebSocket on unmount
    return () => {
      stopNetworkMonitoring();
      if (wsRef.current) {
        console.log('[usePresenceWebSocket] Closing on unmount');
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [roomId, token, isGuest]);

  // Send language updates when myLanguage changes
  useEffect(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN && myLanguage) {
      wsRef.current.send(JSON.stringify({
        type: "set_language",
        language: myLanguage
      }));
      console.log('[usePresenceWebSocket] Sent language update:', myLanguage);
    }
  }, [myLanguage]);

  return {
    // Connection
    isConnected,
    ws: wsRef.current,

    // Presence
    participants,
    languageCounts,
    showWelcome,
    dismissWelcome: () => setShowWelcome(false),
    notifications,

    // Network
    networkQuality,
    networkRTT
  };
}
