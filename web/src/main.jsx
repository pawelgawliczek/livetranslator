import React, {useRef, useState} from "react";
import { createRoot } from "react-dom/client";

function App(){
  const [email,setEmail]=useState("");
  const [pass,setPass]=useState("");
  const [token,setToken]=useState("");
  const [room,setRoom]=useState("demo");
  const [status,setStatus]=useState("idle");
  const [lines,setLines]=useState([]);
  const wsRef=useRef(null); const acRef=useRef(null); const procRef=useRef(null);
  const bufRef=useRef(new Float32Array(0)); const seqRef=useRef(1);

  async function postJSON(path, body){
    const r = await fetch(`${location.protocol}//${location.host}${path}`, {
      method:"POST",
      headers:{"content-type":"application/json"},
      body:JSON.stringify(body),
    });
    if(!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json();
  }
  async function postForm(path, kv){
    const r = await fetch(`${location.protocol}//${location.host}${path}`, {
      method:"POST",
      headers:{"content-type":"application/x-www-form-urlencoded"},
      body:new URLSearchParams(kv),
    });
    if(!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json();
  }

  async function signup(){
    try{
      const res = await postJSON("/auth/signup", { email, password: pass });
      setToken(res.access_token || "");
      setStatus("signed up");
    }catch(e){ setStatus("signup error"); console.log(e); }
  }
  async function login(){
    try{
      const res = await postForm("/auth/login", { username: email, password: pass });
      setToken(res.access_token || "");
      setStatus("logged in");
    }catch(e){ setStatus("login error"); console.log(e); }
  }

  function onMsg(ev){
    try{
      const m = JSON.parse(ev.data);
      if(m.type==="partial"||m.type==="final"){
        setLines(ls=>[
          ...ls.filter(x=>x.segment_id!==m.segment_id || x.type==="final"),
          m
        ]);
      }else if(m.type==="translation_final"){
        setLines(ls=>[...ls, {...m, text:`[${m.tgt}] ${m.text}`}]);
      }
    }catch{}
  }

  async function start(){
    if(!token){ alert("Login first"); return; }
    if(wsRef.current) return;
    setStatus("connecting");

    const wsUrl = (location.protocol==="https:"?"wss://":"ws://")
      + location.host + `/ws/rooms/${encodeURIComponent(room)}?token=${encodeURIComponent(token)}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = onMsg;
    ws.onopen    = ()=>setStatus("streaming");
    ws.onclose   = ()=>{ setStatus("idle"); wsRef.current=null; };
    ws.onerror   = ()=>setStatus("ws error");
    wsRef.current = ws;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount:1, sampleRate:48000 }});
    const ac = new (window.AudioContext||window.webkitAudioContext)({ sampleRate:48000 });
    acRef.current = ac;
    const src = ac.createMediaStreamSource(stream);
    const proc = ac.createScriptProcessor(4096,1,1);
    procRef.current = proc;

    proc.onaudioprocess = (e)=>{
      const ch = e.inputBuffer.getChannelData(0);
      const old = bufRef.current, neu = new Float32Array(old.length+ch.length);
      neu.set(old); neu.set(ch, old.length); bufRef.current = neu;

      if(bufRef.current.length >= 19200){ // ~400ms @ 48k
        const chunk = bufRef.current.slice(0,19200);
        bufRef.current = bufRef.current.slice(19200);
        const r16k = resampleTo16k(chunk, 48000);
        const pcm16 = floatTo16(r16k);
        const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));
        ws.send(JSON.stringify({type:"audio_chunk", roomId:room, device:"web", seq:seqRef.current++, pcm16_base64:b64}));
      }
    };
    src.connect(proc); proc.connect(ac.destination);
  }

  function stop(){
    try{ procRef.current?.disconnect(); }catch{}
    try{ acRef.current?.close(); }catch{}
    try{ wsRef.current?.close(); }catch{}
    procRef.current=null; acRef.current=null; wsRef.current=null;
    setStatus("idle");
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
      <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
        <input value={room} onChange={e=>setRoom(e.target.value)} />
        <button onClick={status==="idle"?start:stop}>{status==="idle"?"Start mic":"Stop"}</button>
        <span>Status: {status}</span>
      </div>

      <h3>Transcripts</h3>
      <ul>
        {lines.slice(-50).map((l,i)=>(
          <li key={i} style={{color:l.type==="partial"?"#666":"#000"}}>
            {l.type==="translation_final"?"":`[${l.lang||l.tgt||""}] `}{l.text}
          </li>
        ))}
      </ul>
    </div>
  );
}

createRoot(document.getElementById("root")).render(<App/>);
