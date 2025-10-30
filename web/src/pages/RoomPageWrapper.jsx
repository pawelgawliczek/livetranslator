/**
 * RoomPageWrapper - Routes to appropriate room view based on multi-speaker mode
 *
 * Checks if room has multi-speaker mode enabled (speakers_locked = true)
 * and routes to either MultiSpeakerRoomPage or regular RoomPage.
 */

import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import RoomPage from './RoomPage';
import MultiSpeakerRoomPage from './MultiSpeakerRoomPage';

export default function RoomPageWrapper({ token, onLogout }) {
  const { roomId } = useParams();
  const [isMultiSpeaker, setIsMultiSpeaker] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Check if room is in multi-speaker mode
  useEffect(() => {
    if (!roomId) return;

    const isGuest = sessionStorage.getItem('is_guest') === 'true';
    const headers = {};

    if (!isGuest && token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    fetch(`/api/rooms/${roomId}`, { headers })
      .then(res => res.json())
      .then(data => {
        // Check if room has locked speakers (multi-speaker mode active)
        setIsMultiSpeaker(data.speakers_locked === true || data.discovery_mode === 'locked');
        setIsLoading(false);
      })
      .catch(err => {
        console.error('[RoomWrapper] Failed to check room mode:', err);
        setIsLoading(false);
        // Default to regular room on error
        setIsMultiSpeaker(false);
      });
  }, [roomId, token]);

  // Show loading state while checking room mode
  if (isLoading) {
    return (
      <div className="h-screen w-screen flex items-center justify-center bg-bg text-fg">
        <div className="text-center">
          <div className="text-4xl mb-4">🎤</div>
          <div className="text-lg">Loading room...</div>
        </div>
      </div>
    );
  }

  // Route to appropriate room view
  return isMultiSpeaker ? (
    <MultiSpeakerRoomPage token={token} onLogout={onLogout} />
  ) : (
    <RoomPage token={token} onLogout={onLogout} />
  );
}
