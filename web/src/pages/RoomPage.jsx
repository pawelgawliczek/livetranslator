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
  const [showLangPicker, setShowLangPicker] = useState(false);
  const [userEmail, setUserEmail] = useState("");
  const [sourceLang, setSourceLang] = useState("auto");
  const [targetLang, setTargetLang] = useState("en");
  const [pushToTalk, setPushToTalk] = useState(false);
  const [isPressing, setIsPressing] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  
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
  const chatEndRef = useRef(null);
  
  const segsRef = useRef(new Map());
  const dirtyRef = useRef(false);
  
  const languages = [
    { code: "auto", name: "Auto", flag: "🌐" },
    { code: "en", name: "English", flag: "🇬🇧" },
    { code: "pl", name: "Polish", flag: "🇵🇱" },
    { code: "ar", name: "Arabic", flag: "🇪🇬" }
  ];
  
  useEffect(() => {
    try {
      const payload = JSON.parse(atob(token.split('.')[1]));
      setUserEmail(payload.email || "User");
    } catch (e) {
      console.error("Failed to decode token:", e);
    }
  }, [token]);
  
  // Load history on mount and when target language changes
  useEffect(() => {
    fetchHistory();
  }, [roomId, targetLang]);
  
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
      if (!m.text) return;
      m.segment_id = m.segment_id || Date.now();
      m.ts_iso = m.ts_iso || new Date().toISOString();
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
          if (pushToTalk && !isPressing) return;
          setVadStatus("🎤 Speaking...");
          isSpeakingRef.current = true;
          partialBufferRef.current = new Float32Array(0);
          lastPartialSentRef.current = 0;
          currentSegmentHintRef.current = Date.now();
        },
        onSpeechEnd: (audio) => {
          if (pushToTalk && !isPressing) return;
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
    // Show loading when changing language with existing messages
    if (segsRef.current.size > 0) {
      setLines([]);
    }
    setLoadingHistory(true);
    try {
      const r = await fetch(`/history/room/${encodeURIComponent(roomId)}?target_lang=${encodeURIComponent(targetLang)}`);
      if (r.ok) {
        const data = await r.json();
        
        // Clear old history segments (keep live segments from current session)
        const now = Date.now();
        const recentThreshold = now - 30000; // Keep segments from last 30 seconds
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
            
            // Add original text
            segsRef.current.set(`s-${id}`, {
              type: "stt_final",
              segment_id: id,
              text: seg.original_text,
              lang: seg.source_lang,
              final: true,
              speaker: seg.speaker,
              ts_iso: seg.timestamp
            });
            
            // Add translation
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
      }
    } catch (e) {
      console.error("Failed to fetch history:", e);
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
  
  const srcLang = languages.find(l => l.code === sourceLang);
  const tgtLang = languages.find(l => l.code === targetLang);
  
  return (
    <div style={{
      height: "100vh",
      display: "flex",
      flexDirection: "column",
      background: "#0a0a0a",
      color: "white",
      fontFamily: "system-ui, -apple-system, sans-serif"
    }}>
      {/* Compact Header */}
      <div style={{
        background: "#1a1a1a",
        borderBottom: "1px solid #333",
        padding: "0.75rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0
      }}>
        <button
          onClick={() => navigate("/rooms")}
          style={{
            padding: "0.5rem",
            background: "transparent",
            border: "none",
            color: "white",
            cursor: "pointer",
            fontSize: "1.25rem"
          }}
        >
          ←
        </button>
        
        <div style={{flex: 1, textAlign: "center"}}>
          <div style={{fontSize: "0.95rem", fontWeight: "600"}}>{roomId}</div>
          {vadStatus !== "idle" && (
            <div style={{fontSize: "0.7rem", color: vadReady ? "#16a34a" : "#999"}}>
              {vadStatus}
            </div>
          )}
        </div>
        
        <div style={{display: "flex", gap: "0.5rem", alignItems: "center"}}>
          <button
            onClick={() => { setShowCosts(!showCosts); if (!showCosts) fetchCosts(); }}
            style={{
              padding: "0.5rem",
              background: "transparent",
              border: "none",
              color: "#999",
              cursor: "pointer",
              fontSize: "1rem"
            }}
          >
            💰
          </button>
          <button
            onClick={onLogout}
            style={{
              padding: "0.5rem",
              background: "transparent",
              border: "none",
              color: "#999",
              cursor: "pointer",
              fontSize: "0.9rem"
            }}
          >
            ↪
          </button>
        </div>
      </div>
      
      {/* Language Bar */}
      <div style={{
        background: "#161616",
        padding: "0.5rem",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.5rem",
        fontSize: "0.85rem",
        borderBottom: "1px solid #333",
        flexShrink: 0
      }}>
        <button
          onClick={() => setShowLangPicker(!showLangPicker)}
          style={{
            background: "#2a2a2a",
            border: "1px solid #444",
            borderRadius: "6px",
            padding: "0.4rem 0.75rem",
            color: "white",
            cursor: status === "idle" ? "pointer" : "not-allowed",
            fontSize: "0.85rem",
            opacity: status === "idle" ? 1 : 0.6
          }}
        >
          {srcLang?.flag} {srcLang?.name} → {tgtLang?.flag} {tgtLang?.name}
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
          background: "rgba(0,0,0,0.8)",
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
            borderRadius: "12px",
            padding: "1.5rem",
            maxWidth: "400px",
            width: "100%",
            border: "1px solid #333"
          }}
          onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{margin: "0 0 1rem 0"}}>Select Languages</h3>
            
            <div style={{marginBottom: "1rem"}}>
              <label style={{display: "block", fontSize: "0.9rem", color: "#999", marginBottom: "0.5rem"}}>
                Source Language
              </label>
              <select
                value={sourceLang}
                onChange={(e) => setSourceLang(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.75rem",
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  borderRadius: "8px",
                  color: "white",
                  fontSize: "1rem"
                }}
              >
                {languages.map(lang => (
                  <option key={lang.code} value={lang.code}>
                    {lang.flag} {lang.name}
                  </option>
                ))}
              </select>
            </div>
            
            <div style={{marginBottom: "1.5rem"}}>
              <label style={{display: "block", fontSize: "0.9rem", color: "#999", marginBottom: "0.5rem"}}>
                Target Language
              </label>
              <select
                value={targetLang}
                onChange={(e) => setTargetLang(e.target.value)}
                style={{
                  width: "100%",
                  padding: "0.75rem",
                  background: "#2a2a2a",
                  border: "1px solid #444",
                  borderRadius: "8px",
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
                padding: "0.75rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontWeight: "600"
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
          background: "rgba(0,0,0,0.8)",
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
            borderRadius: "12px",
            padding: "1.5rem",
            maxWidth: "400px",
            width: "100%",
            border: "1px solid #333"
          }}
          onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{margin: "0 0 0.5rem 0"}}>💰 Costs</h3>
            {!costs ? (
              <div style={{textAlign: "center", color: "#999", padding: "2rem"}}>
                Loading costs...
              </div>
            ) : (
              <>
                <div style={{fontSize: "1.5rem", fontWeight: "bold", color: "#3b82f6", marginBottom: "1rem"}}>
                  ${costs.total_cost_usd.toFixed(6)}
                </div>
                
                <div style={{display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem"}}>
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
              </>
            )}
            
            <button
              onClick={() => setShowCosts(false)}
              style={{
                width: "100%",
                padding: "0.75rem",
                background: "#3b82f6",
                color: "white",
                border: "none",
                borderRadius: "8px",
                cursor: "pointer",
                fontWeight: "600"
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
        padding: "1rem",
        display: "flex",
        flexDirection: "column",
        gap: "0.75rem"
      }}>
        {loadingHistory && lines.length === 0 && (
          <div style={{
            textAlign: "center",
            color: "#666",
            padding: "2rem 0",
            margin: "auto"
          }}>
            📜 Loading history...
          </div>
        )}
        
        {!loadingHistory && lines.length === 0 && (
          <div style={{
            textAlign: "center",
            color: "#666",
            padding: "2rem 0",
            margin: "auto"
          }}>
            Press the microphone to start
          </div>
        )}
        
        {lines.map(([segId, seg]) => {
          const timestamp = seg.source?.ts_iso || seg.translation?.ts_iso;
          return (
            <div key={segId} style={{
              background: "#1a1a1a",
              borderRadius: "12px",
              padding: "0.75rem",
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
              
              {seg.translation && (
                <div style={{
                  color: seg.translation.final ? "#fff" : "#bbb",
                  fontSize: "1rem",
                  fontWeight: "500",
                  marginBottom: "0.35rem",
                  lineHeight: "1.4"
                }}>
                  {seg.translation.text}
                  {!seg.translation.final && <span style={{marginLeft: "0.5rem", color: "#666"}}>⋯</span>}
                </div>
              )}
              
              {seg.source && (
                <div style={{
                  color: "#666",
                  fontSize: "0.75rem",
                  fontStyle: "italic",
                  lineHeight: "1.3"
                }}>
                  {seg.source.text}
                </div>
              )}
            </div>
          );
        })}
        <div ref={chatEndRef} />
      </div>
      
      {/* Bottom Controls */}
      <div style={{
        background: "#1a1a1a",
        borderTop: "1px solid #333",
        padding: "1rem",
        flexShrink: 0
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "0.75rem",
          marginBottom: "0.75rem"
        }}>
          <label style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem",
            fontSize: "0.85rem",
            color: "#999",
            cursor: "pointer"
          }}>
            <input
              type="checkbox"
              checked={pushToTalk}
              onChange={(e) => setPushToTalk(e.target.checked)}
              disabled={status !== "idle"}
              style={{cursor: status === "idle" ? "pointer" : "not-allowed"}}
            />
            Push to talk
          </label>
        </div>
        
        <button
          onClick={status === "idle" ? start : stop}
          onTouchStart={pushToTalk && status === "streaming" ? () => setIsPressing(true) : undefined}
          onTouchEnd={pushToTalk && status === "streaming" ? () => setIsPressing(false) : undefined}
          onMouseDown={pushToTalk && status === "streaming" ? () => setIsPressing(true) : undefined}
          onMouseUp={pushToTalk && status === "streaming" ? () => setIsPressing(false) : undefined}
          style={{
            width: "100%",
            height: "60px",
            borderRadius: "30px",
            background: status === "idle" 
              ? "#16a34a" 
              : (pushToTalk && isPressing) 
                ? "#dc2626"
                : "#dc2626",
            color: "white",
            border: "none",
            fontSize: "1.1rem",
            fontWeight: "600",
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "0.5rem",
            boxShadow: "0 4px 12px rgba(0,0,0,0.3)"
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
    </div>
  );
}
