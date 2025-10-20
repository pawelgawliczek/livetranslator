import React, { useRef, useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { MicVAD } from "@ricky0123/vad-web";

export default function RoomPage({ token, onLogout }) {
  const { roomId } = useParams();
  const navigate = useNavigate();
  
  const [status, setStatus] = useState("idle");
  const [vadStatus, setVadStatus] = useState("idle");
  const [vadReady, setVadReady] = useState(false);
  const [lines, setLines] = useState([]);
  const [costs, setCosts] = useState(null);
  const [showCosts, setShowCosts] = useState(false);
  const [history, setHistory] = useState(null);
  const [showHistory, setShowHistory] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [sourceLang, setSourceLang] = useState("auto");
  const [targetLang, setTargetLang] = useState("en");
  
  const wsRef = useRef(null);
  const seqRef = useRef(1);
  const isRecordingRef = useRef(false);
  const vadRef = useRef(null);
  const audioContextRef = useRef(null);
  const scriptProcessorRef = useRef(null);
  const partialBufferRef = useRef(new Float32Array(0));
  const isSpeakingRef = useRef(false);
  const lastPartialSentRef = useRef(0);
  const currentSegmentHintRef = useRef(null);
  
  const segsRef = useRef(new Map());
  const dirtyRef = useRef(false);
  
  const languages = [
    { code: "auto", name: "Auto Detect" },
    { code: "en", name: "English" },
    { code: "pl", name: "Polish" },
    { code: "ar", name: "Arabic (Egyptian)" }
  ];
  
  useEffect(() => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUserEmail(payload.email || "User");
    } catch (e) {
      console.error("Failed to decode token:", e);
    }
  }, [token]);
  
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
          if (!seg.translation || msg.final || (!msg.final && !seg.translation.final)) {
            seg.translation = msg;
          }
        } else {
          if (!seg.source || msg.final || (!msg.final && !seg.source.final)) {
            seg.source = msg;
          }
        }
      }
      
      const arr = Array.from(segments.entries())
        .sort((a, b) => a[0] - b[0])
        .slice(-40);
      
      setLines(arr);
      dirtyRef.current = false;
    }, 200);
  }
  
  function onMsg(ev) {
    try {
      const m = JSON.parse(ev.data);
      if (!m.text) return;
      m.segment_id = m.segment_id || Date.now();
      const id = m.segment_id | 0;
      
      if (m.type === "translation_partial" || m.type === "translation_final") {
        segsRef.current.set(`t-${id}`, m);
      } else if (m.type === "partial" || m.type === "stt_partial" || m.type === "final" || m.type === "stt_final") {
        segsRef.current.set(`s-${id}`, m);
      } else {
        return;
      }
      scheduleRender();
    } catch {}
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
    if (now - lastPartialSentRef.current < 2000) return;
    if (partialBufferRef.current.length < 16000) return;
    
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
          source_lang: sourceLang,
          target_lang: targetLang
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
  
  async function start() {
    if (isRecordingRef.current) return;
    
    setStatus("connecting");
    setVadStatus("⏳ Loading...");
    setVadReady(false);
    
    const wsUrl = (location.protocol === "https:" ? "wss://" : "ws://") + 
      location.host + `/ws/rooms/${encodeURIComponent(roomId)}?token=${encodeURIComponent(token)}`;
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
    segsRef.current.clear();
    scheduleRender();
    
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, sampleRate: 48000 } });
    const audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 48000 });
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    
    processor.onaudioprocess = (e) => {
      if (!isSpeakingRef.current) return;
      
      const inputData = e.inputBuffer.getChannelData(0);
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
    
    try {
      const vad = await MicVAD.new({
        positiveSpeechThreshold: 0.8,
        negativeSpeechThreshold: 0.75,
        minSpeechFrames: 5,
        redemptionFrames: 10,
        preSpeechPadFrames: 1,
        onSpeechStart: () => {
          setVadStatus("🎤 Speaking...");
          isSpeakingRef.current = true;
          partialBufferRef.current = new Float32Array(0);
          lastPartialSentRef.current = 0;
          currentSegmentHintRef.current = Date.now();
        },
        onSpeechEnd: (audio) => {
          setVadStatus("✅ Processing...");
          isSpeakingRef.current = false;
          
          if (wsRef.current && wsRef.current.readyState === 1 && isRecordingRef.current) {
            const pcm16 = floatTo16(audio);
            const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
            wsRef.current.send(JSON.stringify({
              type: "audio_chunk",
              roomId: roomId,
              device: "web",
              seq: seqRef.current++,
              pcm16_base64: b64,
              source_lang: sourceLang,
              target_lang: targetLang
            }));
          }
          
          partialBufferRef.current = new Float32Array(0);
          currentSegmentHintRef.current = null;
          setTimeout(() => setVadStatus("👂 Listening..."), 300);
        },
        onVADMisfire: () => {
          setVadStatus("👂 Listening...");
          isSpeakingRef.current = false;
          partialBufferRef.current = new Float32Array(0);
          currentSegmentHintRef.current = null;
        },
      });
      
      vadRef.current = vad;
      isRecordingRef.current = true;
      
      await vad.start();
      
      setVadReady(true);
      setVadStatus("👂 Listening...");
      
    } catch (err) {
      console.error("VAD initialization failed:", err);
      setStatus("VAD error");
      setVadStatus("Failed");
      setVadReady(false);
    }
  }
  
  function stop() {
    isRecordingRef.current = false;
    isSpeakingRef.current = false;
    setVadReady(false);
    
    if (vadRef.current) {
      vadRef.current.pause();
      vadRef.current = null;
    }
    
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
      const r = await fetch(`/costs/room/${encodeURIComponent(roomId)}`);
      if (r.ok) setCosts(await r.json());
    } catch (e) {
      console.error("Failed to fetch costs:", e);
    }
  }
  
  async function fetchHistory() {
    try {
      const r = await fetch(`/history/room/${encodeURIComponent(roomId)}`);
      if (r.ok) setHistory(await r.json());
    } catch (e) {
      console.error("Failed to fetch history:", e);
    }
  }
  
  useEffect(() => {
    if (showCosts && roomId) {
      fetchCosts();
      const interval = setInterval(fetchCosts, 5000);
      return () => clearInterval(interval);
    }
  }, [showCosts, roomId]);
  
  useEffect(() => {
    if (showHistory && roomId) {
      fetchHistory();
    }
  }, [showHistory, roomId]);
  
  return (
    <div style={{
      minHeight: "100vh",
      background: "#0a0a0a",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif",
      paddingBottom: "5rem"
    }}>
      {/* Mobile Header - Sticky */}
      <div style={{
        background: "#1a1a1a",
        borderBottom: "1px solid #333",
        padding: "1rem",
        position: "sticky",
        top: 0,
        zIndex: 10
      }}>
        <div style={{display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.5rem"}}>
          <button
            onClick={() => navigate("/rooms")}
            style={{
              padding: "0.5rem",
              background: "transparent",
              border: "1px solid #666",
              borderRadius: "8px",
              color: "white",
              cursor: "pointer",
              fontSize: "1.25rem",
              lineHeight: 1
            }}
          >
            ←
          </button>
          <h1 style={{fontSize: "1.1rem", margin: 0, flex: 1, textAlign: "center"}}>
            {roomId}
          </h1>
          <button
            onClick={onLogout}
            style={{
              padding: "0.5rem 0.75rem",
              background: "transparent",
              border: "1px solid #666",
              borderRadius: "8px",
              color: "white",
              cursor: "pointer",
              fontSize: "0.85rem"
            }}
          >
            ↪
          </button>
        </div>
        
        {vadStatus !== "idle" && (
          <div style={{
            textAlign: "center",
            fontSize: "0.9rem",
            fontWeight: "bold",
            color: vadReady ? "#16a34a" : "#ea580c"
          }}>
            {vadStatus}
          </div>
        )}
      </div>
      
      <div style={{padding: "1rem"}}>
        {/* Language Selection */}
        <div style={{
          background: "#1a1a1a",
          border: "1px solid #333",
          borderRadius: "12px",
          padding: "1rem",
          marginBottom: "1rem"
        }}>
          <div style={{marginBottom: "1rem"}}>
            <label style={{
              display: "block",
              fontSize: "0.9rem",
              color: "#999",
              marginBottom: "0.5rem"
            }}>
              Source Language
            </label>
            <select
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              disabled={status !== "idle"}
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#2a2a2a",
                border: "1px solid #444",
                borderRadius: "8px",
                color: "white",
                fontSize: "1rem",
                cursor: status === "idle" ? "pointer" : "not-allowed",
                opacity: status === "idle" ? 1 : 0.6
              }}
            >
              {languages.map(lang => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </div>
          
          <div>
            <label style={{
              display: "block",
              fontSize: "0.9rem",
              color: "#999",
              marginBottom: "0.5rem"
            }}>
              Target Language
            </label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              disabled={status !== "idle"}
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#2a2a2a",
                border: "1px solid #444",
                borderRadius: "8px",
                color: "white",
                fontSize: "1rem",
                cursor: status === "idle" ? "pointer" : "not-allowed",
                opacity: status === "idle" ? 1 : 0.6
              }}
            >
              {languages.filter(l => l.code !== "auto").map(lang => (
                <option key={lang.code} value={lang.code}>
                  {lang.name}
                </option>
              ))}
            </select>
          </div>
        </div>
        
        {/* Action Buttons */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: "0.5rem",
          marginBottom: "1rem"
        }}>
          <button
            onClick={() => setShowCosts(!showCosts)}
            style={{
              padding: "0.75rem",
              background: showCosts ? "#3b82f6" : "#2a2a2a",
              border: "1px solid #444",
              borderRadius: "8px",
              color: "white",
              cursor: "pointer",
              fontSize: "0.85rem"
            }}
          >
            💰 Costs
          </button>
          <button
            onClick={() => setShowHistory(!showHistory)}
            style={{
              padding: "0.75rem",
              background: showHistory ? "#3b82f6" : "#2a2a2a",
              border: "1px solid #444",
              borderRadius: "8px",
              color: "white",
              cursor: "pointer",
              fontSize: "0.85rem"
            }}
          >
            📜 History
          </button>
          <button
            onClick={status === "idle" ? start : stop}
            style={{
              padding: "0.75rem",
              background: status === "idle" ? "#16a34a" : "#dc2626",
              color: "white",
              border: "none",
              borderRadius: "8px",
              fontSize: "0.9rem",
              fontWeight: "600",
              cursor: "pointer"
            }}
          >
            {status === "idle" ? "▶ Start" : "⏹ Stop"}
          </button>
        </div>
        
        {/* Costs Panel */}
        {showCosts && costs && (
          <div style={{
            background: "#1a1a1a",
            border: "1px solid #333",
            borderRadius: "12px",
            padding: "1rem",
            marginBottom: "1rem"
          }}>
            <h3 style={{margin: "0 0 0.5rem 0", fontSize: "1.1rem"}}>💰 Costs</h3>
            <div style={{fontSize: "1.25rem", fontWeight: "bold", color: "#3b82f6", marginBottom: "1rem"}}>
              ${costs.total_cost_usd.toFixed(6)}
            </div>
            
            <div style={{display: "flex", flexDirection: "column", gap: "0.75rem"}}>
              {Object.entries(costs.breakdown || {}).map(([pipeline, data]) => (
                <div key={pipeline} style={{background: "#2a2a2a", padding: "0.75rem", borderRadius: "8px"}}>
                  <div style={{fontWeight: "bold", fontSize: "0.9rem", marginBottom: "0.25rem"}}>
                    {pipeline === "mt" ? "🔤 Translation" : "🎤 STT"}
                  </div>
                  <div style={{fontSize: "0.8rem", color: "#999"}}>
                    {data.events} events • ${data.cost_usd.toFixed(6)}
                  </div>
                </div>
              ))}
            </div>
            
            <button onClick={fetchCosts} style={{
              marginTop: "0.75rem",
              padding: "0.5rem",
              background: "#3b82f6",
              color: "white",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              width: "100%",
              fontSize: "0.85rem"
            }}>
              🔄 Refresh
            </button>
          </div>
        )}
        
        {/* History Panel */}
        {showHistory && history && (
          <div style={{
            background: "#1a1a1a",
            border: "1px solid #333",
            borderRadius: "12px",
            padding: "1rem",
            marginBottom: "1rem",
            maxHeight: "300px",
            overflowY: "auto"
          }}>
            <h3 style={{margin: "0 0 0.5rem 0", fontSize: "1.1rem"}}>📜 History</h3>
            <div style={{fontSize: "0.8rem", color: "#666", marginBottom: "0.75rem"}}>
              {history.segments?.length || 0} segments
            </div>
            
            <div>
              {history.segments?.map((seg, idx) => (
                <div key={idx} style={{
                  marginBottom: "0.75rem",
                  paddingBottom: "0.75rem",
                  borderBottom: "1px solid #333"
                }}>
                  {seg.speaker && seg.speaker !== "system" && (
                    <div style={{fontSize: "0.75rem", color: "#3b82f6", fontWeight: "600", marginBottom: "0.25rem"}}>
                      👤 {seg.speaker}
                    </div>
                  )}
                  <div style={{fontSize: "0.85rem", marginBottom: "0.25rem"}}>
                    <strong>[{seg.lang}]</strong> {seg.text}
                  </div>
                  <div style={{fontSize: "0.7rem", color: "#666"}}>
                    {new Date(seg.timestamp).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
            
            <button onClick={fetchHistory} style={{
              marginTop: "0.75rem",
              padding: "0.5rem",
              background: "#3b82f6",
              color: "white",
              border: "none",
              borderRadius: "8px",
              cursor: "pointer",
              width: "100%",
              fontSize: "0.85rem"
            }}>
              🔄 Refresh
            </button>
          </div>
        )}
        
        {/* Live Transcripts */}
        <div style={{
          background: "#1a1a1a",
          border: "1px solid #333",
          borderRadius: "12px",
          padding: "1rem"
        }}>
          <h3 style={{margin: "0 0 1rem 0", fontSize: "1.1rem"}}>Live Transcript</h3>
          
          <div>
            {lines.length === 0 && (
              <div style={{textAlign: "center", color: "#666", padding: "2rem 0"}}>
                Press Start to begin translation
              </div>
            )}
            
            {lines.map(([segId, seg]) => (
              <div key={segId} style={{
                marginBottom: "1rem",
                paddingBottom: "1rem",
                borderBottom: "1px solid #333"
              }}>
                {seg.source && (
                  <>
                    {seg.source.speaker && seg.source.speaker !== "system" && (
                      <div style={{
                        fontSize: "0.8rem",
                        color: "#3b82f6",
                        fontWeight: "600",
                        marginBottom: "0.25rem"
                      }}>
                        👤 {seg.source.speaker}
                      </div>
                    )}
                    <div style={{
                      color: seg.source.final ? "#fff" : "#999",
                      marginBottom: "0.5rem",
                      fontStyle: seg.source.final ? "normal" : "italic",
                      fontSize: "0.95rem"
                    }}>
                      <strong>[{seg.source.lang || ""}]</strong> {seg.source.text}
                      {!seg.source.final && <span style={{marginLeft: "0.5rem"}}>⋯</span>}
                    </div>
                  </>
                )}
                {seg.translation && (
                  <div style={{
                    color: seg.translation.final ? "#999" : "#666",
                    fontStyle: "italic",
                    marginLeft: "1rem",
                    fontSize: "0.9rem"
                  }}>
                    → {seg.translation.text}
                    {!seg.translation.final && <span style={{marginLeft: "0.5rem"}}>⋯</span>}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
