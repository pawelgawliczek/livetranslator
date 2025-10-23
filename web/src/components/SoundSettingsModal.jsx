import React, { useEffect, useRef, useState } from 'react';

export default function SoundSettingsModal({
  isOpen,
  onClose,
  currentLevel,      // Current RMS energy (0.0 - 1.0)
  threshold,         // Energy threshold (0.0 - 1.0)
  onThresholdChange, // Callback when threshold changes
  isActive,          // Is VAD currently detecting speech?
  status,            // VAD status text
  onTest             // Callback to start/stop test mode
}) {
  const canvasRef = useRef(null);
  const [localThreshold, setLocalThreshold] = useState(threshold);
  const [isTesting, setIsTesting] = useState(false);

  // Update local threshold when prop changes
  useEffect(() => {
    setLocalThreshold(threshold);
  }, [threshold]);

  // Draw audio level visualization
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.clearRect(0, 0, width, height);

    // Draw background
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);

    // Draw current level bar
    const levelX = currentLevel * width;
    const gradient = ctx.createLinearGradient(0, 0, width, 0);

    if (currentLevel > localThreshold) {
      // Above threshold - green to yellow
      gradient.addColorStop(0, '#10b981');
      gradient.addColorStop(localThreshold, '#10b981');
      gradient.addColorStop(1, '#fbbf24');
    } else {
      // Below threshold - gray
      gradient.addColorStop(0, '#4b5563');
      gradient.addColorStop(1, '#6b7280');
    }

    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, levelX, height);

    // Draw border
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 2;
    ctx.strokeRect(0, 0, width, height);

    // Draw threshold line ON TOP (so it's always visible)
    const thresholdX = localThreshold * width;

    // Draw shadow/glow for better visibility
    ctx.shadowColor = 'rgba(239, 68, 68, 0.8)';
    ctx.shadowBlur = 8;

    // Draw solid thick line (no dashes for better visibility)
    ctx.strokeStyle = '#ef4444';
    ctx.lineWidth = 4;
    ctx.beginPath();
    ctx.moveTo(thresholdX, 0);
    ctx.lineTo(thresholdX, height);
    ctx.stroke();

    // Reset shadow
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;

  }, [currentLevel, localThreshold]);

  const handleThresholdChange = (e) => {
    const newThreshold = parseFloat(e.target.value);
    setLocalThreshold(newThreshold);
    if (onThresholdChange) {
      onThresholdChange(newThreshold);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0,0,0,0.85)",
        zIndex: 1001,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "1rem"
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: "#1a1a1a",
          borderRadius: "12px",
          border: "1px solid #333",
          width: "100%",
          maxWidth: "500px",
          overflow: "hidden",
          boxShadow: "0 4px 12px rgba(0,0,0,0.5)"
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: "1rem 1.25rem",
          borderBottom: "1px solid #333",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between"
        }}>
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: "0.5rem"
          }}>
            <span style={{ fontSize: "1.25rem" }}>🎤</span>
            <h3 style={{
              margin: 0,
              fontSize: "1.1rem",
              fontWeight: "600",
              color: "white"
            }}>
              Sound Settings
            </h3>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "transparent",
              border: "none",
              color: "#999",
              fontSize: "1.5rem",
              cursor: "pointer",
              padding: "0",
              lineHeight: "1"
            }}
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: "1.5rem" }}>
          {/* Status */}
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            marginBottom: "1rem"
          }}>
            <div style={{
              fontSize: "0.9rem",
              fontWeight: "600",
              color: "#999"
            }}>
              Status
            </div>
            <div style={{
              fontSize: "0.9rem",
              fontWeight: "600",
              color: isActive ? '#10b981' : '#6b7280',
              display: "flex",
              alignItems: "center",
              gap: "0.5rem"
            }}>
              <span>{isActive ? '●' : '○'}</span>
              <span>{status}</span>
            </div>
          </div>

          {/* Audio Level Visualization */}
          <div style={{
            marginBottom: "1.5rem"
          }}>
            <div style={{
              fontSize: "0.9rem",
              fontWeight: "600",
              color: "#999",
              marginBottom: "0.75rem"
            }}>
              Audio Input Level
            </div>
            <canvas
              ref={canvasRef}
              width={450}
              height={80}
              style={{
                borderRadius: "8px",
                width: "100%",
                height: "80px"
              }}
            />
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: "0.5rem",
              fontSize: "0.85rem",
              color: "#6b7280"
            }}>
              <span>
                Level: <strong style={{ color: '#fff' }}>
                  {(currentLevel * 100).toFixed(0)}%
                </strong>
              </span>
              <span>
                Threshold: <strong style={{ color: '#ef4444' }}>
                  {(localThreshold * 100).toFixed(0)}%
                </strong>
              </span>
            </div>
          </div>

          {/* Threshold Adjustment Slider */}
          <div>
            <div style={{
              fontSize: "0.9rem",
              fontWeight: "600",
              color: "#999",
              marginBottom: "0.75rem"
            }}>
              Noise Threshold
            </div>
            <input
              type="range"
              min="0.001"
              max="0.1"
              step="0.001"
              value={localThreshold}
              onChange={handleThresholdChange}
              style={{
                width: "100%",
                height: "6px",
                borderRadius: "3px",
                background: `linear-gradient(to right, #ef4444 0%, #ef4444 ${localThreshold * 1000}%, #333 ${localThreshold * 1000}%, #333 100%)`,
                outline: "none",
                appearance: "none",
                cursor: "pointer"
              }}
            />
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: "0.5rem",
              fontSize: "0.75rem",
              color: "#6b7280"
            }}>
              <span>More Sensitive</span>
              <span>Less Sensitive</span>
            </div>
            <div style={{
              marginTop: "0.75rem",
              fontSize: "0.8rem",
              color: "#9ca3af",
              lineHeight: "1.4"
            }}>
              Adjust if the microphone is picking up too much background noise or not detecting your voice properly.
            </div>
          </div>

          {/* Test Microphone Button */}
          <div style={{
            marginTop: "1.5rem",
            paddingTop: "1.5rem",
            borderTop: "1px solid #333"
          }}>
            <button
              onClick={() => {
                if (onTest) {
                  onTest(!isTesting);
                  setIsTesting(!isTesting);
                }
              }}
              style={{
                width: "100%",
                padding: "0.75rem",
                borderRadius: "8px",
                border: "none",
                background: isTesting ? "#ef4444" : "#10b981",
                color: "white",
                fontSize: "0.9rem",
                fontWeight: "600",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "0.5rem",
                transition: "background 0.2s"
              }}
              onMouseOver={(e) => e.currentTarget.style.opacity = "0.9"}
              onMouseOut={(e) => e.currentTarget.style.opacity = "1"}
            >
              {isTesting ? (
                <>
                  <span>⏹</span>
                  <span>Stop Test</span>
                </>
              ) : (
                <>
                  <span>🎤</span>
                  <span>Test Microphone</span>
                </>
              )}
            </button>
            <div style={{
              marginTop: "0.5rem",
              fontSize: "0.75rem",
              color: "#6b7280",
              textAlign: "center"
            }}>
              {isTesting ? "Speak to test your microphone and threshold settings" : "Start test mode to calibrate your microphone"}
            </div>
          </div>
        </div>
      </div>

      <style>{`
        input[type="range"]::-webkit-slider-thumb {
          appearance: none;
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #ef4444;
          cursor: pointer;
          box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
        }
        input[type="range"]::-moz-range-thumb {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          background: #ef4444;
          cursor: pointer;
          border: none;
          box-shadow: 0 0 8px rgba(239, 68, 68, 0.5);
        }
      `}</style>
    </div>
  );
}
