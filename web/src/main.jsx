import React, {useEffect, useRef, useState} from "react"
import { createRoot } from "react-dom/client"

function App(){
  const [room,setRoom]=useState("demo")
  const [tgt,setTgt]=useState("en")
  const [status,setStatus]=useState("idle")
  const [lines,setLines]=useState([])
  const wsRef=useRef(null); const acRef=useRef(null); const procRef=useRef(null)
  const bufRef=useRef(new Float32Array(0)); const seqRef=useRef(1)

  function floatTo16(floats){
    const out=new Int16Array(floats.length)
    for(let i=0;i<floats.length;i++){ let s=Math.max(-1,Math.min(1,floats[i])); out[i]=s<0?s*0x8000:s*0x7fff }
    return out
  }
  // naive resample to 16k
  function resampleTo16k(input, inRate){
    if(inRate===16000) return input
    const ratio=16000/inRate, out=new Float32Array(Math.floor(input.length*ratio))
    for(let i=0;i<out.length;i++){ const x=i/ratio; const i0=Math.floor(x), i1=Math.min(i0+1, input.length-1)
      const t=x-i0; out[i]=input[i0]*(1-t)+input[i1]*t }
    return out
  }
  function onMsg(ev){
    try{
      const m=JSON.parse(ev.data)
      if(m.type==="partial"||m.type==="final"){
        setLines(ls=>[...ls.filter(x=>x.segment_id!==m.segment_id && !(x.type==="partial"&&m.type==="final")),
                      m])
      }else if(m.type==="translation_final"){
        setLines(ls=>[...ls, {...m, text:`[${m.tgt}] ${m.text}`}])
      }
    }catch{}
  }
  async function start(){
    if(wsRef.current) return
    setStatus("connecting")
    const wsUrl=(location.protocol==="https:"?"wss://":"ws://")+location.host+`/ws/rooms/${room}`
    const ws=new WebSocket(wsUrl); ws.onmessage=onMsg; ws.onopen=()=>setStatus("streaming"); ws.onclose=()=>setStatus("idle")
    wsRef.current=ws

    const stream=await navigator.mediaDevices.getUserMedia({audio:true})
    const ac=new (window.AudioContext||window.webkitAudioContext)({sampleRate:48000}); acRef.current=ac
    const src=ac.createMediaStreamSource(stream)
    const proc=ac.createScriptProcessor(4096,1,1); procRef.current=proc
    const started=performance.now()
    proc.onaudioprocess=(e)=>{
      const ch=e.inputBuffer.getChannelData(0)
      // append to buffer
      const old=bufRef.current, neu=new Float32Array(old.length+ch.length); neu.set(old); neu.set(ch, old.length); bufRef.current=neu
      // every ~400ms at 48k = 19200 samples
      if(bufRef.current.length>=19200){
        const chunk=bufRef.current.slice(0,19200); bufRef.current=bufRef.current.slice(19200)
        const r16k=resampleTo16k(chunk, 48000)
        const pcm16=floatTo16(r16k)
        const b64=btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)))
        ws.send(JSON.stringify({type:"audio_chunk", roomId:room, device:"web", seq:seqRef.current++, pcm16_base64:b64}))
      }
    }
    src.connect(proc); proc.connect(ac.destination)
  }
  function stop(){
    if(procRef.current){ procRef.current.disconnect(); procRef.current=null }
    if(acRef.current){ acRef.current.close(); acRef.current=null }
    if(wsRef.current){ wsRef.current.close(); wsRef.current=null }
    setStatus("idle")
  }

  return <div style={{fontFamily:"system-ui",margin:"1rem"}}>
    <h1>LiveTranslator</h1>
    <div>Room:
      <input value={room} onChange={e=>setRoom(e.target.value)} style={{marginLeft:8}}/>
      <button onClick={status==="idle"?start:stop} style={{marginLeft:8}}>
        {status==="idle"?"Start mic":"Stop"}
      </button>
    </div>
    <p>Status: {status}</p>
    <ul>
      {lines.slice(-50).map((l,i)=>(
        <li key={i} style={{color: l.type==="partial"?"#666":"#000"}}>
          {l.type==="translation_final"?"": `[${l.lang||l.tgt}] `}{l.text}
        </li>
      ))}
    </ul>
  </div>
}

createRoot(document.getElementById("root")).render(<App/>)
