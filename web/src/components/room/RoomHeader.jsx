import React from 'react';
import PropTypes from 'prop-types';

/**
 * RoomHeader - Top navigation bar for room page
 *
 * Displays:
 * - Back button (left)
 * - Room name + participant language counts (center)
 * - VAD status indicator
 * - Menu button (right)
 */
export default function RoomHeader({
  roomId,
  languageCounts = {},
  languages = [],
  vadStatus = 'idle',
  vadReady = false,
  onBackClick,
  onMenuClick
}) {
  return (
    <div className="bg-card-dark border-b border-border-dark flex items-center justify-between gap-2 px-3 py-2 shrink-0"
         style={{ paddingTop: 'max(0.5rem, env(safe-area-inset-top))' }}>

      {/* Back button - left */}
      <button
        onClick={onBackClick}
        className="bg-[#2a2a2a] border border-[#444] rounded-lg text-white cursor-pointer px-3 py-2 text-lg flex items-center justify-center min-w-[40px] shrink-0 hover:bg-[#333] transition-colors"
        aria-label="Go back"
      >
        ←
      </button>

      {/* Room name and status - center */}
      <div className="flex-1 text-center min-w-0">
        <div className="text-sm font-semibold overflow-hidden text-ellipsis whitespace-nowrap flex items-center justify-center gap-2">
          <span>{roomId}</span>

          {/* Language participant counts */}
          {Object.keys(languageCounts).length > 0 && (
            <span className="text-[0.85rem] inline-flex gap-1 items-center">
              {Object.entries(languageCounts).map(([langCode, count]) => {
                const lang = languages.find(l => l.code === langCode);
                return (
                  <span
                    key={langCode}
                    className="inline-flex items-center gap-0.5 bg-white/10 px-1.5 py-0.5 rounded"
                  >
                    {lang?.flag || '🌐'} {count}
                  </span>
                );
              })}
            </span>
          )}
        </div>

        {/* VAD Status indicator */}
        {vadStatus !== 'idle' && (
          <div className={`text-[0.65rem] overflow-hidden text-ellipsis whitespace-nowrap ${
            vadReady ? 'text-green-600' : 'text-muted-dark'
          }`}>
            {vadStatus}
          </div>
        )}
      </div>

      {/* Menu button - right */}
      <button
        onClick={onMenuClick}
        className="bg-[#2a2a2a] border border-[#444] rounded-lg text-white cursor-pointer px-3 py-2 text-lg flex items-center justify-center min-w-[40px] shrink-0 hover:bg-[#333] transition-colors"
        title="Menu"
        aria-label="Open menu"
      >
        ⋮
      </button>
    </div>
  );
}

RoomHeader.propTypes = {
  roomId: PropTypes.string.isRequired,
  languageCounts: PropTypes.object,
  languages: PropTypes.arrayOf(PropTypes.shape({
    code: PropTypes.string,
    flag: PropTypes.string,
    name: PropTypes.string
  })),
  vadStatus: PropTypes.string,
  vadReady: PropTypes.bool,
  onBackClick: PropTypes.func.isRequired,
  onMenuClick: PropTypes.func.isRequired
};
