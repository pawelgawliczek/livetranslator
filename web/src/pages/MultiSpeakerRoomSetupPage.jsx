import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

/**
 * MultiSpeakerRoomSetupPage - Dedicated page for creating multi-speaker rooms
 *
 * Flow:
 * 1. Create room automatically with discovery mode enabled
 * 2. Redirect to room page with showDiscovery flag
 * 3. Room page handles audio capture and discovery modal
 */
export default function MultiSpeakerRoomSetupPage({ token }) {
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  /**
   * Create multi-speaker room on mount and redirect to room
   */
  useEffect(() => {
    const createMultiSpeakerRoom = async () => {
      setLoading(true);
      setError(null);

      try {
        // Generate random room code
        const randomCode = 'MS-' + Math.random().toString(36).substring(2, 8).toUpperCase();

        // Create room via API
        const response = await fetch('/api/rooms/multi-speaker', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({ code: randomCode })
        });

        if (!response.ok) {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Failed to create multi-speaker room');
        }

        const data = await response.json();

        // Redirect directly to room page with discovery param
        navigate(`/room/${data.code}?showDiscovery=true`);
      } catch (err) {
        console.error('Failed to create multi-speaker room:', err);
        setError(err.message);
        setLoading(false);
      }
    };

    createMultiSpeakerRoom();
  }, [token, navigate]);

  /**
   * Handle cancel - go back to rooms list
   */
  const handleCancel = () => {
    navigate('/');
  };

  if (!token) {
    navigate('/login');
    return null;
  }

  return (
    <div className="min-h-screen bg-bg flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        {loading && (
          <div className="bg-card border border-border rounded-lg p-8 text-center">
            <div className="text-6xl mb-4">🎤</div>
            <h2 className="text-2xl font-bold text-fg mb-2">
              {t('multiSpeaker.creating', 'Creating Multi-Speaker Room...')}
            </h2>
            <p className="text-muted">
              {t('multiSpeaker.settingUp', 'Setting up your multi-speaker session')}
            </p>
          </div>
        )}

        {error && (
          <div className="bg-card border border-border rounded-lg p-8 text-center">
            <div className="text-6xl mb-4">⚠️</div>
            <h2 className="text-2xl font-bold text-red-400 mb-2">
              {t('multiSpeaker.error', 'Error')}
            </h2>
            <p className="text-muted mb-4">{error}</p>
            <button
              onClick={handleCancel}
              className="px-6 py-3 bg-accent text-white rounded-lg font-semibold hover:bg-accent/90 transition-colors"
            >
              {t('common.back', 'Go Back')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
