import { useEffect, useRef, useState } from 'react';

/**
 * Custom hook for Text-to-Speech audio playback using Web Audio API
 *
 * @param {Object} options - Configuration options
 * @param {boolean} options.enabled - Whether TTS is enabled
 * @param {number} options.volume - Playback volume (0.0 - 2.0)
 * @returns {Object} - { playAudio, isPlaying }
 */
export function useTTS({ enabled = false, volume = 0.8 }) {
  const [isPlaying, setIsPlaying] = useState(false);
  const audioContextRef = useRef(null);
  const audioQueueRef = useRef([]);

  useEffect(() => {
    if (!enabled) return;

    // Initialize Web Audio API
    audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();

    return () => {
      audioContextRef.current?.close();
    };
  }, [enabled]);

  const playAudio = async (base64Audio, format = 'mp3') => {
    if (!enabled || !audioContextRef.current) return;

    try {
      // Decode base64 to ArrayBuffer
      const binaryString = atob(base64Audio);
      const bytes = new Uint8Array(binaryString.length);
      for (let i = 0; i < binaryString.length; i++) {
        bytes[i] = binaryString.charCodeAt(i);
      }

      // Decode audio data
      const audioBuffer = await audioContextRef.current.decodeAudioData(bytes.buffer);

      // Create audio source
      const source = audioContextRef.current.createBufferSource();
      const gainNode = audioContextRef.current.createGain();

      source.buffer = audioBuffer;
      gainNode.gain.value = volume;

      source.connect(gainNode);
      gainNode.connect(audioContextRef.current.destination);

      source.start(0);
      setIsPlaying(true);

      source.onended = () => {
        setIsPlaying(false);
      };
    } catch (error) {
      console.error('[TTS] Audio playback error:', error);
      setIsPlaying(false);
    }
  };

  return { playAudio, isPlaying };
}
