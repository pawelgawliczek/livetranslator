/**
 * useAudioStream Hook
 *
 * Manages audio capture, VAD (Voice Activity Detection), and WebSocket audio streaming.
 *
 * Features:
 * - MediaStream acquisition (getUserMedia)
 * - Audio processing with ScriptProcessor
 * - Voice Activity Detection (energy-based)
 * - Audio resampling (source rate → 16kHz)
 * - Push-to-talk mode support
 * - Adaptive send rate based on network quality
 * - Safety timeouts (30s max recording)
 * - Proper cleanup of audio resources
 *
 * @param {Object} options
 * @param {WebSocket} options.ws - WebSocket connection for audio streaming
 * @param {string} options.roomId - Room identifier
 * @param {string} options.myLanguage - Current user's language
 * @param {boolean} options.pushToTalk - Push-to-talk mode enabled
 * @param {boolean} options.isPressing - PTT button is pressed
 * @param {number} options.sendInterval - Interval between audio chunk sends (ms)
 * @param {string} options.networkQuality - Network quality ('high', 'medium', 'low')
 * @param {Function} options.onStatusChange - Callback when recording status changes
 * @param {Function} options.onVadStatusChange - Callback when VAD status changes
 *
 * @returns {Object} Audio stream state and controls
 */

import { useEffect, useRef, useState } from 'react';

// VAD Configuration
const SILENCE_THRESHOLD = 20;  // frames
const SPEECH_THRESHOLD = 5;    // frames
const ENERGY_THRESHOLD = 0.02; // RMS level
const MAX_RECORDING_TIME = 30000; // 30 seconds safety timeout

export default function useAudioStream({
  ws,
  roomId,
  myLanguage,
  pushToTalk,
  isPressing,
  sendInterval,
  networkQuality,
  onStatusChange,
  onVadStatusChange
}) {
  // Audio state
  const [isRecording, setIsRecording] = useState(false);
  const [vadReady, setVadReady] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);

  // Audio refs
  const streamRef = useRef(null);
  const audioContextRef = useRef(null);
  const processorRef = useRef(null);
  const seqRef = useRef(1);
  const currentSegmentHintRef = useRef(Date.now());

  // VAD state refs
  const silenceFramesRef = useRef(0);
  const speechFramesRef = useRef(0);
  const isSpeakingRef = useRef(false);
  const partialBufferRef = useRef(new Float32Array(0));
  const ringBufferRef = useRef(new Float32Array(0));
  const lastPartialSentRef = useRef(0);

  // Push-to-talk refs
  const isRecordingRef = useRef(false);
  const pushToTalkRef = useRef(pushToTalk);
  const isPressingRef = useRef(isPressing);
  const sendIntervalRef = useRef(sendInterval);

  // Safety timeout
  const safetyTimeoutRef = useRef(null);

  // Bandwidth tracking
  const bytesSentRef = useRef(0);
  const lastBandwidthCheckRef = useRef(Date.now());
  const bandwidthRef = useRef(0);

  // Keep refs in sync
  useEffect(() => {
    isRecordingRef.current = isRecording;
  }, [isRecording]);

  useEffect(() => {
    pushToTalkRef.current = pushToTalk;
  }, [pushToTalk]);

  useEffect(() => {
    isPressingRef.current = isPressing;
  }, [isPressing]);

  useEffect(() => {
    sendIntervalRef.current = sendInterval;
  }, [sendInterval]);

  /**
   * Float32Array to Int16Array (PCM16) conversion
   */
  function floatTo16(f) {
    const o = new Int16Array(f.length);
    for (let i = 0; i < f.length; i++) {
      const s = Math.max(-1, Math.min(1, f[i]));
      o[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return o;
  }

  /**
   * Resample audio to 16kHz (for STT providers)
   */
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

  /**
   * Calculate RMS (Root Mean Square) energy level
   */
  function calculateRMS(samples) {
    let sum = 0;
    for (let i = 0; i < samples.length; i++) {
      sum += samples[i] * samples[i];
    }
    return Math.sqrt(sum / samples.length);
  }

  /**
   * Send partial audio chunk (during speech)
   */
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

      if (ws && ws.readyState === 1) {
        const payload = JSON.stringify({
          type: "audio_chunk_partial",
          roomId: roomId,
          device: "web",
          segment_hint: currentSegmentHintRef.current,
          seq: seqRef.current++,
          pcm16_base64: b64,
          language: myLanguage || "auto"
        });

        ws.send(payload);
        trackBandwidth(payload.length);
      }

      lastPartialSentRef.current = now;
      // Clear buffer after sending - don't keep overlapping audio for streaming STT
      partialBufferRef.current = new Float32Array(0);
    } catch (e) {
      console.error("Partial send failed:", e);
    }
  }

  /**
   * Send final transcription signal
   */
  function sendFinalTranscription() {
    try {
      if (ws && ws.readyState === 1) {
        // Send any remaining audio in the buffer
        if (partialBufferRef.current.length > 0) {
          const pcm16 = floatTo16(partialBufferRef.current);
          const b64 = btoa(String.fromCharCode(...new Uint8Array(pcm16.buffer)));

          ws.send(JSON.stringify({
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
        ws.send(JSON.stringify({
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

  /**
   * Track bandwidth usage
   */
  function trackBandwidth(bytesSent) {
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
  }

  /**
   * Start audio recording and VAD
   */
  async function start() {
    if (isRecordingRef.current) return;

    try {
      if (onStatusChange) onStatusChange("connecting");
      if (onVadStatusChange) onVadStatusChange("⏳ Loading...");
      setVadReady(false);

      console.log('[VAD] Starting voice activity detection...');

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: { ideal: 48000 },
          echoCancellation: true,
          noiseSuppression: false,
          autoGainControl: true
        }
      });

      streamRef.current = stream;

      // Create audio context and processor
      const audioContext = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);

      audioContextRef.current = audioContext;
      processorRef.current = processor;

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
      currentSegmentHintRef.current = Date.now();

      // Audio processing
      let wasPressing = false;

      processor.onaudioprocess = (e) => {
        if (!isRecordingRef.current || !ws) return;

        // In push-to-talk mode, only process audio when button is pressed
        if (pushToTalkRef.current && !isPressingRef.current) {
          // Button released - finalize if was speaking
          if (wasPressing && isSpeakingRef.current) {
            sendFinalTranscription();
            isSpeakingRef.current = false;
            partialBufferRef.current = new Float32Array(0);
            ringBufferRef.current = new Float32Array(0);
            if (onVadStatusChange) onVadStatusChange("idle");
          }
          wasPressing = false;
          return;
        }

        wasPressing = isPressingRef.current;

        const inputData = e.inputBuffer.getChannelData(0);
        const resampled = resampleTo16k(inputData, sourceSampleRate);

        // Calculate energy
        const rms = calculateRMS(resampled);
        setAudioLevel(rms);

        const isSpeech = rms > ENERGY_THRESHOLD;

        // Update VAD state
        if (isSpeech) {
          speechFramesRef.current++;
          silenceFramesRef.current = 0;
        } else {
          silenceFramesRef.current++;
          speechFramesRef.current = 0;
        }

        // Detect speech start
        if (!isSpeakingRef.current && speechFramesRef.current >= SPEECH_THRESHOLD) {
          console.log('[VAD] Speech started');
          isSpeakingRef.current = true;
          currentSegmentHintRef.current = Date.now();

          // Add ring buffer (pre-speech audio)
          if (ringBufferRef.current.length > 0) {
            const temp = new Float32Array(partialBufferRef.current.length + ringBufferRef.current.length);
            temp.set(ringBufferRef.current);
            temp.set(partialBufferRef.current, ringBufferRef.current.length);
            partialBufferRef.current = temp;
          }

          if (onVadStatusChange) onVadStatusChange("🎤 Speaking...");
        }

        // Detect speech end
        if (isSpeakingRef.current && silenceFramesRef.current >= SILENCE_THRESHOLD) {
          console.log('[VAD] Speech ended');
          sendFinalTranscription();
          isSpeakingRef.current = false;
          partialBufferRef.current = new Float32Array(0);
          ringBufferRef.current = new Float32Array(0);
          if (onVadStatusChange) onVadStatusChange("idle");
        }

        // Update ring buffer (keep last 500ms for pre-speech capture)
        if (!isSpeakingRef.current) {
          const ringBufferSize = Math.floor(targetSampleRate * 0.5); // 500ms
          const temp = new Float32Array(ringBufferRef.current.length + resampled.length);
          temp.set(ringBufferRef.current);
          temp.set(resampled, ringBufferRef.current.length);
          ringBufferRef.current = temp.slice(-ringBufferSize);
        }

        // Accumulate audio during speech
        if (isSpeakingRef.current) {
          const temp = new Float32Array(partialBufferRef.current.length + resampled.length);
          temp.set(partialBufferRef.current);
          temp.set(resampled, partialBufferRef.current.length);
          partialBufferRef.current = temp;

          // Send partial chunks
          sendPartialIfReady();
        }
      };

      // Connect audio nodes
      source.connect(processor);
      processor.connect(audioContext.destination);

      setIsRecording(true);
      setVadReady(true);
      if (onStatusChange) onStatusChange("streaming");
      if (onVadStatusChange) onVadStatusChange("idle");

      console.log('[VAD] Ready');

      // Safety timeout (30 seconds max)
      safetyTimeoutRef.current = setTimeout(() => {
        console.warn('[VAD] Safety timeout - stopping recording');
        stop();
      }, MAX_RECORDING_TIME);

    } catch (error) {
      console.error('[VAD] Failed to start:', error);
      if (onStatusChange) onStatusChange("error");
      if (onVadStatusChange) onVadStatusChange("❌ Error");
    }
  }

  /**
   * Stop audio recording and cleanup
   */
  function stop() {
    console.log('[VAD] Stopping...');

    // Clear safety timeout
    if (safetyTimeoutRef.current) {
      clearTimeout(safetyTimeoutRef.current);
      safetyTimeoutRef.current = null;
    }

    // Stop media stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    // Disconnect and close audio context
    if (processorRef.current) {
      processorRef.current.disconnect();
      processorRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Reset state
    setIsRecording(false);
    setVadReady(false);
    setAudioLevel(0);
    if (onStatusChange) onStatusChange("idle");
    if (onVadStatusChange) onVadStatusChange("idle");

    // Reset VAD state
    silenceFramesRef.current = 0;
    speechFramesRef.current = 0;
    isSpeakingRef.current = false;
    partialBufferRef.current = new Float32Array(0);
    ringBufferRef.current = new Float32Array(0);

    console.log('[VAD] Stopped');
  }

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stop();
    };
  }, []);

  return {
    // State
    isRecording,
    vadReady,
    audioLevel,
    bandwidth: bandwidthRef.current,

    // Controls
    start,
    stop
  };
}
