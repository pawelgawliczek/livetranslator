import React, { useRef, useState, useEffect } from "react";
import { useParams, useNavigate, useLocation } from "react-router-dom";
import InviteModal from "../components/InviteModal";
import ParticipantsModal from "../components/ParticipantsModal";
import SettingsMenu from "../components/SettingsMenu";

export default function RoomPage({ token, onLogout }) {
  const { roomId } = useParams();
  const navigate = useNavigate();
  const location = useLocation();

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
  const [userEmail, setUserEmail] = useState("");
  const [myLanguage, setMyLanguage] = useState(() => {
    const stored = isGuest ? guestLang : localStorage.getItem('lt_my_language');
    // If no language stored, we'll force selection via modal
    return stored || null;
  });
  const [pushToTalk, setPushToTalk] = useState(() => {
    return localStorage.getItem('lt_push_to_talk') === 'true';
  });
  const [persistenceEnabled, setPersistenceEnabled] = useState(() => {
    return localStorage.getItem('lt_persistence_enabled') === 'true';
  });
  const [isPressing, setIsPressing] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [isRoomAdmin, setIsRoomAdmin] = useState(false);
  const [showAdminLeaveWarning, setShowAdminLeaveWarning] = useState(false);

  const wsRef = useRef(null);
  const presenceWsRef = useRef(null); // Persistent presence WebSocket
  const seqRef = useRef(1);
  const isRecordingRef = useRef(false);
  const audioContextRef = useRef(null);
  const scriptProcessorRef = useRef(null);
  const partialBufferRef = useRef(new Float32Array(0));
  const isSpeakingRef = useRef(false);
  const lastPartialSentRef = useRef(0);
  const currentSegmentHintRef = useRef(null);
  const chatEndRef = useRef(null);

  const segsRef = useRef(new Map());
  const dirtyRef = useRef(false);

  // VAD state
  const vadSpeechFramesRef = useRef(0);
  const vadSilenceFramesRef = useRef(0);
  const vadIsDetectedRef = useRef(false);

  const languages = [
    { code: "auto", name: "Auto", flag: "🌐" },
    { code: "en", name: "English", flag: "🇬🇧" },
    { code: "pl", name: "Polish", flag: "🇵🇱" },
    { code: "ar", name: "Arabic", flag: "🇪🇬" }
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
    if (!isGuest && token) {
      localStorage.setItem('lt_persistence_enabled', persistenceEnabled.toString());

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
  }, [persistenceEnabled, isGuest, token, roomId]);

  // Check if current user is the room admin
  useEffect(() => {
    if (!isGuest && token) {
      fetch(`/api/rooms/${roomId}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      })
        .then(res => res.json())
        .then(data => {
          try {
            const payload = JSON.parse(atob(token.split('.')[1]));
            const userId = parseInt(payload.sub);
            setIsRoomAdmin(data.owner_id === userId);
          } catch (e) {
            console.error('Failed to check admin status:', e);
          }
        })
        .catch(err => console.error('Failed to fetch room info:', err));
    }
  }, [roomId, token, isGuest]);

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
        }
      };

      presenceWs.onmessage = (event) => {
        // Process STT and translation messages on presence WebSocket too
        try {
          const data = JSON.parse(event.data);
          // Only process translation and STT messages, ignore other types
          if (data.type && (data.type.includes('translation') || data.type.includes('stt') || data.type.includes('partial') || data.type.includes('final'))) {
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
      if (!m.text) {
        console.log('[WS] Rejected: no text field');
        return;
      }
      m.segment_id = m.segment_id || Date.now();
      m.ts_iso = m.ts_iso || new Date().toISOString();
      const id = m.segment_id | 0;
      
      console.log('[WS] Processing:', m.type, 'segment:', id, 'speaker:', m.speaker);
      
      if (m.type === "translation_partial" || m.type === "translation_final") {
        segsRef.current.set(`t-${id}`, m);
      } else if (m.type === "partial" || m.type === "stt_partial" || m.type === "final" || m.type === "stt_final") {
        segsRef.current.set(`s-${id}`, m);
      } else {
        console.log('[WS] Unknown type:', m.type);
        return;
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
    if (now - lastPartialSentRef.current < 800) return;  // Send every 800ms for faster updates
    if (partialBufferRef.current.length < 8000) return;  // Minimum 0.5s of audio

    try {
      const pcm16 = floatTo16(partialBufferRef.current);
      const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));

      if (wsRef.current && wsRef.current.readyState === 1) {
        wsRef.current.send(JSON.stringify({
          type: "audio_chunk_partial",
          roomId: roomId,
          device: "web",
          segment_hint: currentSegmentHintRef.current,
          seq: seqRef.current++,
          pcm16_base64: b64,
          language: myLanguage || "auto"  // Use "auto" if language not yet selected
        }));
      }

      lastPartialSentRef.current = now;
      const keepSamples = 8000;
      if (partialBufferRef.current.length > keepSamples) {
        partialBufferRef.current = partialBufferRef.current.slice(-keepSamples);
      }
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
    
    // Request microphone with Chrome-compatible constraints
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,  // Enable AGC - Chrome might need this for proper levels
        channelCount: 1,
        sampleRate: 48000
      }
    });

    const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });

    // Resume audio context (required in Chrome)
    if (audioContext.state === 'suspended') {
      await audioContext.resume();
    }

    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);

    // Debug microphone stream
    const audioTracks = stream.getAudioTracks();
    console.log('[VAD] Audio context created, state:', audioContext.state, 'sampleRate:', audioContext.sampleRate);
    console.log('[VAD] Audio tracks:', audioTracks.length, audioTracks.map(t => ({
      label: t.label,
      enabled: t.enabled,
      muted: t.muted,
      readyState: t.readyState,
      settings: t.getSettings()
    })));

    let audioProcessCallCount = 0;
    processor.onaudioprocess = (e) => {
      audioProcessCallCount++;

      // Log first few callbacks to confirm it's working
      if (audioProcessCallCount <= 3) {
        console.log(`[VAD] Audio process callback #${audioProcessCallCount} fired`);
      }

      const inputData = e.inputBuffer.getChannelData(0);

      // Calculate audio energy for VAD
      let energy = 0;
      for (let i = 0; i < inputData.length; i++) {
        energy += inputData[i] * inputData[i];
      }
      energy = Math.sqrt(energy / inputData.length);

      // Much more sensitive threshold for Chrome
      const energyThreshold = 0.0001; // Very sensitive
      const isSpeech = energy > energyThreshold;

      // Log energy more frequently for debugging
      if (audioProcessCallCount % 100 === 0) {
        const maxSample = Math.max(...inputData.map(Math.abs));
        console.log(`[VAD Debug #${audioProcessCallCount}] Energy: ${energy.toFixed(6)}, Max sample: ${maxSample.toFixed(6)}, Threshold: ${energyThreshold}, isSpeech: ${isSpeech}`);
      }

      if (isSpeech) {
        vadSpeechFramesRef.current++;
        vadSilenceFramesRef.current = 0;

        // Start speech if threshold reached
        if (!vadIsDetectedRef.current && vadSpeechFramesRef.current >= 5) {
          vadIsDetectedRef.current = true;
          setVadStatus("🎤 Speaking...");
          isSpeakingRef.current = true;
          partialBufferRef.current = new Float32Array(0);
          lastPartialSentRef.current = 0;
          currentSegmentHintRef.current = Date.now();
        }
      } else {
        vadSilenceFramesRef.current++;

        if (vadIsDetectedRef.current) {
          // End speech if silence threshold reached (8 frames = ~800ms)
          if (vadSilenceFramesRef.current >= 8) {
            vadIsDetectedRef.current = false;
            vadSpeechFramesRef.current = 0;
            setVadStatus("✅ Processing...");
            isSpeakingRef.current = false;

            // Send audio_end to finalize accumulated partials
            sendFinalTranscription();

            // Clear buffers
            partialBufferRef.current = new Float32Array(0);
            currentSegmentHintRef.current = null;

            // Return to listening status after a delay
            setTimeout(() => setVadStatus("👂 Listening..."), 300);
          }
        } else {
          vadSpeechFramesRef.current = Math.max(0, vadSpeechFramesRef.current - 1);
        }
      }

      // Only process audio for transmission when speaking is detected
      if (!isSpeakingRef.current) return;

      const resampled = resampleTo16k(inputData, 48000);

      const oldLen = partialBufferRef.current.length;
      const newBuffer = new Float32Array(oldLen + resampled.length);
      newBuffer.set(partialBufferRef.current);
      newBuffer.set(resampled, oldLen);
      partialBufferRef.current = newBuffer;

      sendPartialIfReady();
    };
    
    source.connect(processor);
    processor.connect(audioContext.destination);

    audioContextRef.current = audioContext;
    scriptProcessorRef.current = processor;
    partialBufferRef.current = new Float32Array(0);
    lastPartialSentRef.current = 0;

    // Initialize VAD state
    vadSpeechFramesRef.current = 0;
    vadSilenceFramesRef.current = 0;
    vadIsDetectedRef.current = false;
    setVadStatus("👂 Listening...");
    console.log('[VAD] Initialized and ready');

    isRecordingRef.current = true;
    setVadReady(true);
    setVadStatus("👂 Listening...");
  }
  
  function stop() {
    isRecordingRef.current = false;
    isSpeakingRef.current = false;
    setVadReady(false);

    // Reset VAD state
    vadSpeechFramesRef.current = 0;
    vadSilenceFramesRef.current = 0;
    vadIsDetectedRef.current = false;

    if (scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    try {
      if (wsRef.current && wsRef.current.readyState === 1) {
        wsRef.current.send(JSON.stringify({ type: "audio_end", roomId: roomId, device: "web" }));
      }
    } catch {}

    setStatus("idle");
    setVadStatus("idle");
  }
  
  async function fetchCosts() {
    try {
      const r = await fetch(`/costs/room/${encodeURIComponent(roomId)}`, {
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
  
  const myLang = languages.find(l => l.code === myLanguage);

  return (
    <div style={{
      height: "100vh",
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
          onClick={() => navigate("/rooms")}
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
            whiteSpace: "nowrap"
          }}>
            {roomId}
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
          return (
            <div key={segId} style={{
              background: "#1a1a1a",
              borderRadius: "14px",
              padding: "0.85rem",
              border: "1px solid #333"
            }}>
              <div style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "0.5rem"
              }}>
                {seg.source && seg.source.speaker && seg.source.speaker !== "system" && (
                  <div style={{
                    fontSize: "0.7rem",
                    color: "#3b82f6",
                    fontWeight: "600"
                  }}>
                    👤 {seg.source.speaker.split('@')[0]}
                  </div>
                )}
                {timestamp && (
                  <div style={{
                    fontSize: "0.65rem",
                    color: "#666",
                    marginLeft: "auto"
                  }}>
                    {formatTime(timestamp)}
                  </div>
                )}
              </div>
              
              {seg.translation ? (
                <>
                  {/* Translation - large font */}
                  <div style={{
                    color: seg.translation.final ? "#fff" : "#bbb",
                    fontSize: "1rem",
                    fontWeight: "500",
                    marginBottom: "0.4rem",
                    lineHeight: "1.45"
                  }}>
                    {seg.translation.text}
                    {!seg.translation.final && <span style={{marginLeft: "0.5rem", color: "#666"}}>⋯</span>}
                  </div>
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
                  {/* No translation - show source in large font (own message) */}
                  {seg.source && (
                    <div style={{
                      color: seg.source.final ? "#fff" : "#bbb",
                      fontSize: "1rem",
                      fontWeight: "500",
                      lineHeight: "1.45"
                    }}>
                      {seg.source.text}
                      {!seg.source.final && <span style={{marginLeft: "0.5rem", color: "#666"}}>⋯</span>}
                    </div>
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
        {/* Push to talk checkbox */}
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
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
        onLanguageChange={(lang) => {
          setMyLanguage(lang);
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
        onLogout={onLogout}
        canChangeLanguage={status === "idle"}
        persistenceEnabled={persistenceEnabled}
        onTogglePersistence={() => setPersistenceEnabled(!persistenceEnabled)}
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
    </div>
  );
}
