import React, {useRef, useState, useEffect} from "react";
import { createRoot } from "react-dom/client";
import { MicVAD } from "@ricky0123/vad-web";

function App(){
  const [email,setEmail]=useState("");
  const [pass,setPass]=useState("");
  const [token,setToken]=useState("");
  const [room,setRoom]=useState("demo");
  const [status,setStatus]=useState("idle");
  const [vadStatus,setVadStatus]=useState("idle");
  const [vadReady,setVadReady]=useState(false);
  const [lines,setLines]=useState([]);
  const [costs,setCosts]=useState(null);
  const [showCosts,setShowCosts]=useState(false);

  const wsRef=useRef(null);
  const seqRef=useRef(1);
  const isRecordingRef=useRef(false);
  const vadRef=useRef(null);
  
  // For partials: use AudioContext ScriptProcessor
  const audioContextRef=useRef(null);
  const scriptProcessorRef=useRef(null);
  const partialBufferRef=useRef(new Float32Array(0));
  const isSpeakingRef=useRef(false);
  const lastPartialSentRef=useRef(0);
  const currentSegmentHintRef=useRef(null);

  // segment store and throttled render
  const segsRef=useRef(new Map());
  const dirtyRef=useRef(false);
  function scheduleRender(){
    if(dirtyRef.current) return;
    dirtyRef.current = true;
    setTimeout(()=>{
      const segments = new Map();
      
      // Group by segment_id, but partials can update
      for(const [key, msg] of segsRef.current.entries()){
        const segId = msg.segment_id;
        if(!segments.has(segId)){
          segments.set(segId, {source: null, translation: null});
        }
        const seg = segments.get(segId);
        
        if(msg.type && msg.type.startsWith("translation")){
          if(!seg.translation || msg.final || !msg.final && !seg.translation.final){
            seg.translation = msg;
          }
        } else {
          if(!seg.source || msg.final || !msg.final && !seg.source.final){
            seg.source = msg;
          }
        }
      }
      
      // Convert to sorted array
      const arr = Array.from(segments.entries())
        .sort((a,b) => a[0] - b[0])
        .slice(-40);
      
      setLines(arr);
      dirtyRef.current = false;
    }, 200);
  }

  async function postJSON(path, body){
    const r = await fetch(`${location.protocol}//${location.host}${path}`, {
      method:"POST", headers:{"content-type":"application/json"}, body:JSON.stringify(body),
    });
    if(!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json();
  }
  async function postForm(path, kv){
    const r = await fetch(`${location.protocol}//${location.host}${path}`, {
      method:"POST", headers:{"content-type":"application/x-www-form-urlencoded"}, body:new URLSearchParams(kv),
    });
    if(!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json();
  }

  async function signup(){
    try{ const res=await postJSON("/auth/signup",{email,password:pass}); setToken(res.access_token||""); setStatus("signed up"); }
    catch{ setStatus("signup error"); }
  }
  async function login(){
    try{ const res=await postForm("/auth/login",{username:email,password:pass}); setToken(res.access_token||""); setStatus("logged in"); }
    catch{ setStatus("login error"); }
  }

  async function fetchCosts(){
    try{
      const r = await fetch(`${location.protocol}//${location.host}/costs/room/${encodeURIComponent(room)}`);
      if(r.ok){
        const data = await r.json();
        setCosts(data);
      }
    }catch(e){
      console.error("Failed to fetch costs:", e);
    }
  }

  useEffect(() => {
    if(showCosts && room){
      fetchCosts();
      const interval = setInterval(fetchCosts, 5000);
      return () => clearInterval(interval);
    }
  }, [showCosts, room]);

  function onMsg(ev){
    try{
      const m = JSON.parse(ev.data);
      if(!m.text) return; 
      m.segment_id = m.segment_id || Date.now();
      const id = m.segment_id|0;
      
      if(m.type==="translation_partial"||m.type==="translation_final"){
        segsRef.current.set(`t-${id}`, m);
      }else if(m.type==="partial" || m.type==="stt_partial"||m.type==="final" || m.type==="stt_final"){
        segsRef.current.set(`s-${id}`, m);
      }else{
        return;
      }
      scheduleRender();
    }catch{}
  }

  function floatTo16(f){
    const o=new Int16Array(f.length);
    for(let i=0;i<f.length;i++){ const s=Math.max(-1,Math.min(1,f[i])); o[i]=s<0?s*0x8000:s*0x7FFF; }
    return o;
  }
  
  function resampleTo16k(input, inRate){
    if(inRate===16000) return input;
    const ratio=16000/inRate, out=new Float32Array(Math.floor(input.length*ratio));
    for(let i=0;i<out.length;i++){
      const x=i/ratio; const i0=Math.floor(x), i1=Math.min(i0+1,input.length-1); const t=x-i0;
      out[i]=input[i0]*(1-t)+input[i1]*t;
    }
    return out;
  }

  function sendPartialIfReady(){
    const now = Date.now();
    if(!isSpeakingRef.current) return;
    if(now - lastPartialSentRef.current < 2000) return;
    if(partialBufferRef.current.length < 16000) return;
    
    try {
      const pcm16 = floatTo16(partialBufferRef.current);
      const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
      
      if(wsRef.current && wsRef.current.readyState === 1){
        wsRef.current.send(JSON.stringify({
          type:"audio_chunk_partial", 
          roomId:room, 
          device:"web",
          segment_hint: currentSegmentHintRef.current,
          seq:seqRef.current++, 
          pcm16_base64:b64
        }));
      }
      
      lastPartialSentRef.current = now;
      const keepSamples = 8000;
      if(partialBufferRef.current.length > keepSamples){
        partialBufferRef.current = partialBufferRef.current.slice(-keepSamples);
      }
    } catch(e){
      console.error("Partial send failed:", e);
    }
  }

  async function start(){
    if(!token){ alert("Login first"); return; }
    if(isRecordingRef.current) return;
    
    setStatus("connecting");
    setVadStatus("⏳ Loading VAD models...");
    setVadReady(false);

    const wsUrl=(location.protocol==="https:"?"wss://":"ws://")+location.host+`/ws/rooms/${encodeURIComponent(room)}?token=${encodeURIComponent(token)}`;
    const ws=new WebSocket(wsUrl);
    ws.onmessage=onMsg;
    ws.onopen=()=>{
      setStatus("streaming");
    };
    ws.onclose=()=>{
      setStatus("idle");
      setVadStatus("idle");
      setVadReady(false);
    };
    ws.onerror=()=>setStatus("ws error");
    wsRef.current=ws;

    seqRef.current=1;
    segsRef.current.clear();
    scheduleRender();

    const stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount:1, sampleRate:48000}});
    const audioContext = new (window.AudioContext || window.webkitAudioContext)({sampleRate: 48000});
    const source = audioContext.createMediaStreamSource(stream);
    const processor = audioContext.createScriptProcessor(4096, 1, 1);
    
    processor.onaudioprocess = (e) => {
      if(!isSpeakingRef.current) return;
      
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
      console.log("[VAD] Starting initialization...");
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
          
          if(wsRef.current && wsRef.current.readyState === 1 && isRecordingRef.current){
            const pcm16 = floatTo16(audio);
            const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
            wsRef.current.send(JSON.stringify({
              type:"audio_chunk", 
              roomId:room, 
              device:"web", 
              seq:seqRef.current++, 
              pcm16_base64:b64
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
      
      console.log("[VAD] Initialization complete!");
      vadRef.current = vad;
      isRecordingRef.current = true;
      
      // Start VAD
      await vad.start();
      
      // Mark as ready
      setVadReady(true);
      setVadStatus("👂 Listening...");
      
    } catch(err) {
      console.error("VAD initialization failed:", err);
      setStatus("VAD error");
      setVadStatus("Failed to initialize");
      setVadReady(false);
    }
  }

  function stop(){
    isRecordingRef.current = false;
    isSpeakingRef.current = false;
    setVadReady(false);
    
    if(vadRef.current) {
      vadRef.current.pause();
      vadRef.current = null;
    }
    
    if(scriptProcessorRef.current) {
      scriptProcessorRef.current.disconnect();
      scriptProcessorRef.current = null;
    }
    
    if(audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    try{
      if(wsRef.current && wsRef.current.readyState===1){
        wsRef.current.send(JSON.stringify({type:"audio_end", roomId:room, device:"web"}));
      }
    }catch{}
    
    setStatus("idle");
    setVadStatus("idle");
  }

  return (
    <div style={{fontFamily:"system-ui",margin:"1rem",maxWidth:900}}>
      <h1>LiveTranslator</h1>

      <h3>Auth</h3>
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        <input placeholder="email" value={email} onChange={e=>setEmail(e.target.value)} />
        <input placeholder="password" type="password" value={pass} onChange={e=>setPass(e.target.value)} />
        <button onClick={signup}>Sign up</button>
        <button onClick={login}>Login</button>
        <span style={{marginLeft:8}}>token: {token ? "yes" : "no"}</span>
      </div>

      <h3>Room</h3>
      <div style={{display:"flex",gap:8,flexWrap:"wrap",alignItems:"center"}}>
        <input value={room} onChange={e=>setRoom(e.target.value)} />
        <button onClick={status==="idle"?start:stop}>{status==="idle"?"Start VAD":"Stop"}</button>
        <button onClick={()=>setShowCosts(!showCosts)}>{showCosts?"Hide":"Show"} Costs</button>
        <span>Status: {status}</span>
        {vadStatus !== "idle" && (
          <span style={{
            marginLeft:8,
            fontWeight:"bold",
            color: vadReady ? "#16a34a" : "#ea580c"
          }}>
            {vadStatus}
          </span>
        )}
      </div>

      {showCosts && costs && (
        <div style={{marginTop:"1rem",padding:"1rem",background:"#f5f5f5",borderRadius:8}}>
          <h3 style={{marginTop:0}}>💰 Cost Dashboard - Room: {costs.room_id}</h3>
          <div style={{fontSize:"1.5rem",fontWeight:"bold",color:"#2563eb",marginBottom:"1rem"}}>
            Total: ${costs.total_cost_usd.toFixed(6)} USD
          </div>
          
          <div style={{display:"grid",gap:"1rem"}}>
            {Object.entries(costs.breakdown || {}).map(([pipeline, data]) => (
              <div key={pipeline} style={{background:"white",padding:"1rem",borderRadius:6,border:"1px solid #ddd"}}>
                <div style={{fontWeight:"bold",marginBottom:"0.5rem",textTransform:"uppercase",color:"#666"}}>
                  {pipeline === "mt" ? "🔤 Translation" : pipeline === "stt_final" ? "🎤 Speech-to-Text (Final)" : "🎤 Speech-to-Text (Partial)"}
                </div>
                <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"0.5rem",fontSize:"0.9rem"}}>
                  <div><strong>Events:</strong> {data.events}</div>
                  <div><strong>Cost:</strong> ${data.cost_usd.toFixed(6)}</div>
                  <div><strong>Mode:</strong> {data.mode}</div>
                  <div><strong>Units:</strong> {data.total_units} {pipeline === "mt" ? "tokens" : "seconds"}</div>
                </div>
              </div>
            ))}
          </div>
          
          <button onClick={fetchCosts} style={{marginTop:"1rem",padding:"0.5rem 1rem",background:"#2563eb",color:"white",border:"none",borderRadius:4,cursor:"pointer"}}>
            🔄 Refresh
          </button>
        </div>
      )}

     <h3>Transcripts</h3>
      <div>
        {lines.map(([segId, seg]) => (
          <div key={segId} style={{marginBottom:"1rem",paddingBottom:"0.5rem",borderBottom:"1px solid #eee"}}>
            {seg.source && (
              <>
                {seg.source.speaker && seg.source.speaker !== "system" && (
                  <div style={{fontSize:"0.85em",color:"#2563eb",fontWeight:"600",marginBottom:"0.25rem"}}>
                    👤 {seg.source.speaker}
                  </div>
                )}
                <div style={{
                  color: seg.source.final ? "#333" : "#999",
                  marginBottom:"0.25rem",
                  fontStyle: seg.source.final ? "normal" : "italic"
                }}>
                  <strong>[{seg.source.lang||""}]</strong> {seg.source.text}
                  {!seg.source.final && <span style={{marginLeft:"0.5rem",fontSize:"0.8em"}}>⋯</span>}
                </div>
              </>
            )}
            {seg.translation && (
              <div style={{
                color: seg.translation.final ? "#666" : "#aaa",
                fontStyle:"italic",
                marginLeft:"1rem"
              }}>
                → {seg.translation.text}
                {!seg.translation.final && <span style={{marginLeft:"0.5rem",fontSize:"0.8em"}}>⋯</span>}
              </div>
            )}
          </div>
        ))}
      </div>

    </div>
  );
}

createRoot(document.getElementById("root")).render(<App/>);
