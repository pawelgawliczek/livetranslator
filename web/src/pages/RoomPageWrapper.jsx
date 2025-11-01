/**
 * RoomPageWrapper - Simple wrapper to pass props to RoomPage
 */

import React from 'react';
import RoomPage from './RoomPage';

export default function RoomPageWrapper({ token, onLogout }) {
  return <RoomPage token={token} onLogout={onLogout} />;
}
