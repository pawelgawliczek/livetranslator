import { useState, useEffect } from 'react';

/**
 * Custom hook to enumerate and manage audio input devices (microphones)
 * @returns {Object} - { devices: AudioDevice[], selectedDeviceId: string|null, error: string|null, refreshDevices: Function }
 */
export function useAudioDevices() {
  const [devices, setDevices] = useState([]);
  const [error, setError] = useState(null);

  const enumerateDevices = async () => {
    try {
      // Request microphone permission first to get device labels
      await navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
          // Stop all tracks immediately after getting permission
          stream.getTracks().forEach(track => track.stop());
        });

      // Now enumerate devices - labels will be available after permission is granted
      const allDevices = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = allDevices.filter(device => device.kind === 'audioinput');

      setDevices(audioInputs.map(device => ({
        deviceId: device.deviceId,
        label: device.label || `Microphone ${device.deviceId.slice(0, 8)}`,
        groupId: device.groupId
      })));
      setError(null);
    } catch (err) {
      console.error('Error enumerating audio devices:', err);
      setError(err.message);
      setDevices([]);
    }
  };

  useEffect(() => {
    enumerateDevices();

    // Listen for device changes (plugging/unplugging microphones)
    const handleDeviceChange = () => {
      enumerateDevices();
    };

    navigator.mediaDevices.addEventListener('devicechange', handleDeviceChange);

    return () => {
      navigator.mediaDevices.removeEventListener('devicechange', handleDeviceChange);
    };
  }, []);

  return {
    devices,
    error,
    refreshDevices: enumerateDevices
  };
}
