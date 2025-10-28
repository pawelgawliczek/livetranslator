import React, { useState, useEffect } from 'react';

export default function MessageDebugModal({ isOpen, onClose, segmentId, token }) {
  const [debugData, setDebugData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [source, setSource] = useState(null);

  useEffect(() => {
    if (!isOpen || !segmentId) {
      return;
    }

    // Fetch debug info from API
    const fetchDebugInfo = async () => {
      setLoading(true);
      setError(null);

      try {
        const response = await fetch(`/api/admin/message-debug/${segmentId}`, {
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        });

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error('Debug information not found for this message');
          } else if (response.status === 403) {
            throw new Error('Access denied. Admin privileges required.');
          } else {
            throw new Error(`Failed to fetch debug info (${response.status})`);
          }
        }

        const result = await response.json();
        setDebugData(result.data);
        setSource(result.source);
      } catch (err) {
        console.error('Failed to fetch debug info:', err);
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };

    fetchDebugInfo();
  }, [isOpen, segmentId, token]);

  // Close modal on Escape key
  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const formatCost = (cost) => {
    if (cost === undefined || cost === null) return 'N/A';
    return `$${Number(cost).toFixed(6)}`;
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    try {
      return new Date(timestamp).toLocaleString();
    } catch (e) {
      return timestamp;
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'rgba(0, 0, 0, 0.85)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 9999,
        padding: '1rem'
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#1a1a1a',
          border: '1px solid #333',
          borderRadius: '12px',
          maxWidth: '800px',
          width: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          boxShadow: '0 4px 20px rgba(0, 0, 0, 0.5)'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div style={{
          padding: '1rem 1.25rem',
          borderBottom: '1px solid #333',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          background: '#1a1a1a',
          zIndex: 1
        }}>
          <h2 style={{
            margin: 0,
            fontSize: '1.1rem',
            fontWeight: '600',
            color: '#fff'
          }}>
            🔍 Debug Information - Segment #{segmentId}
          </h2>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#999',
              fontSize: '1.5rem',
              cursor: 'pointer',
              padding: '0.25rem',
              lineHeight: 1,
              transition: 'color 0.2s'
            }}
            onMouseEnter={(e) => e.target.style.color = '#fff'}
            onMouseLeave={(e) => e.target.style.color = '#999'}
          >
            ×
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '1.25rem' }}>
          {loading && (
            <div style={{
              textAlign: 'center',
              padding: '3rem',
              color: '#999'
            }}>
              <div style={{
                fontSize: '2rem',
                marginBottom: '1rem'
              }}>⏳</div>
              Loading debug information...
            </div>
          )}

          {error && (
            <div style={{
              background: '#2a1515',
              border: '1px solid #553',
              borderRadius: '8px',
              padding: '1rem',
              color: '#ff9999'
            }}>
              <strong>Error:</strong> {error}
            </div>
          )}

          {!loading && !error && debugData && (
            <>
              {/* Source Badge */}
              {source && (
                <div style={{
                  marginBottom: '1rem',
                  display: 'inline-block',
                  background: source === 'redis' ? '#1a2a1a' : '#2a2a1a',
                  border: `1px solid ${source === 'redis' ? '#4a6' : '#66a'}`,
                  borderRadius: '6px',
                  padding: '0.35rem 0.75rem',
                  fontSize: '0.75rem',
                  color: source === 'redis' ? '#9f9' : '#99f'
                }}>
                  {source === 'redis' ? '⚡ Live Data (Redis)' : '📦 Historical Data (Database)'}
                </div>
              )}

              {/* Metadata */}
              <div style={{
                background: '#0f0f0f',
                border: '1px solid #2a2a2a',
                borderRadius: '8px',
                padding: '0.75rem 1rem',
                marginBottom: '1rem',
                fontSize: '0.85rem'
              }}>
                <div style={{ color: '#999', marginBottom: '0.25rem' }}>
                  <strong>Room:</strong> <span style={{ color: '#fff' }}>{debugData.room_code || 'N/A'}</span>
                </div>
                <div style={{ color: '#999' }}>
                  <strong>Timestamp:</strong> <span style={{ color: '#fff' }}>{formatTimestamp(debugData.timestamp)}</span>
                </div>
              </div>

              {/* STT Section */}
              {debugData.stt && (
                <div style={{
                  background: '#0f0f0f',
                  border: '1px solid #2a2a2a',
                  borderRadius: '8px',
                  padding: '1rem',
                  marginBottom: '1rem'
                }}>
                  <h3 style={{
                    margin: '0 0 0.75rem 0',
                    fontSize: '0.95rem',
                    fontWeight: '600',
                    color: '#3b82f6'
                  }}>
                    🎤 Speech-to-Text (STT)
                  </h3>

                  <div style={{ fontSize: '0.85rem' }}>
                    <div style={{ marginBottom: '0.5rem' }}>
                      <span style={{ color: '#999' }}>Provider:</span>{' '}
                      <span style={{
                        background: '#2a2a3a',
                        padding: '0.2rem 0.5rem',
                        borderRadius: '4px',
                        color: '#fff',
                        fontFamily: 'monospace'
                      }}>
                        {debugData.stt.provider}
                      </span>
                    </div>

                    <div style={{ marginBottom: '0.5rem', color: '#999' }}>
                      <strong>Language:</strong> <span style={{ color: '#fff' }}>{debugData.stt.language}</span>
                    </div>

                    <div style={{ marginBottom: '0.5rem', color: '#999' }}>
                      <strong>Mode:</strong> <span style={{ color: '#fff' }}>{debugData.stt.mode}</span>
                    </div>

                    {debugData.stt.latency_ms !== null && debugData.stt.latency_ms !== undefined && (
                      <div style={{ marginBottom: '0.5rem', color: '#999' }}>
                        <strong>Latency:</strong> <span style={{ color: '#fff' }}>{debugData.stt.latency_ms}ms</span>
                      </div>
                    )}

                    <div style={{ marginBottom: '0.5rem', color: '#999' }}>
                      <strong>Audio Duration:</strong> <span style={{ color: '#fff' }}>{debugData.stt.audio_duration_sec?.toFixed(2)}s</span>
                    </div>

                    <div style={{
                      marginTop: '0.75rem',
                      padding: '0.5rem',
                      background: '#1a1a1a',
                      borderRadius: '4px'
                    }}>
                      <div style={{ color: '#999', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
                        Transcribed Text:
                      </div>
                      <div style={{ color: '#fff', fontStyle: 'italic' }}>
                        "{debugData.stt.text}"
                      </div>
                    </div>

                    {/* Routing Info */}
                    {debugData.stt.routing_reason && (
                      <div style={{
                        marginTop: '0.75rem',
                        padding: '0.5rem',
                        background: '#1a1a2a',
                        borderRadius: '4px',
                        fontSize: '0.8rem'
                      }}>
                        <div style={{ color: '#99f', marginBottom: '0.25rem' }}>
                          <strong>Routing:</strong>
                        </div>
                        <div style={{ color: '#ccc' }}>{debugData.stt.routing_reason}</div>
                        {debugData.stt.fallback_triggered && (
                          <div style={{ color: '#fa3', marginTop: '0.25rem' }}>
                            ⚠️ Fallback triggered
                          </div>
                        )}
                      </div>
                    )}

                    {/* Cost Breakdown */}
                    <div style={{
                      marginTop: '0.75rem',
                      padding: '0.75rem',
                      background: '#1a2a1a',
                      border: '1px solid #2a4a2a',
                      borderRadius: '6px'
                    }}>
                      <div style={{
                        color: '#9f9',
                        fontSize: '0.85rem',
                        fontWeight: '600',
                        marginBottom: '0.5rem'
                      }}>
                        Cost: {formatCost(debugData.stt.cost_usd)}
                      </div>
                      {debugData.stt.cost_breakdown && (
                        <div style={{ fontSize: '0.75rem', color: '#9c9' }}>
                          {debugData.stt.cost_breakdown.units?.toFixed(2)} {debugData.stt.cost_breakdown.unit_type} × {formatCost(debugData.stt.cost_breakdown.rate_per_unit)}/{debugData.stt.cost_breakdown.unit_type}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* MT Section */}
              {debugData.mt && debugData.mt.length > 0 && (
                <div style={{
                  background: '#0f0f0f',
                  border: '1px solid #2a2a2a',
                  borderRadius: '8px',
                  padding: '1rem',
                  marginBottom: '1rem'
                }}>
                  <h3 style={{
                    margin: '0 0 0.75rem 0',
                    fontSize: '0.95rem',
                    fontWeight: '600',
                    color: '#a855f7'
                  }}>
                    🌍 Machine Translation (MT)
                  </h3>

                  {debugData.mt.map((translation, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: '#1a1a1a',
                        border: '1px solid #2a2a2a',
                        borderRadius: '6px',
                        padding: '0.75rem',
                        marginBottom: idx < debugData.mt.length - 1 ? '0.75rem' : 0,
                        fontSize: '0.85rem'
                      }}
                    >
                      <div style={{ marginBottom: '0.5rem' }}>
                        <span style={{ color: '#999' }}>Provider:</span>{' '}
                        <span style={{
                          background: '#3a2a3a',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          color: '#fff',
                          fontFamily: 'monospace'
                        }}>
                          {translation.provider}
                        </span>
                      </div>

                      <div style={{ marginBottom: '0.5rem', color: '#999' }}>
                        <strong>Languages:</strong>{' '}
                        <span style={{ color: '#fff' }}>{translation.src_lang} → {translation.tgt_lang}</span>
                      </div>

                      {translation.latency_ms !== null && translation.latency_ms !== undefined && (
                        <div style={{ marginBottom: '0.5rem', color: '#999' }}>
                          <strong>Latency:</strong> <span style={{ color: '#fff' }}>{translation.latency_ms}ms</span>
                        </div>
                      )}

                      <div style={{
                        marginTop: '0.5rem',
                        padding: '0.5rem',
                        background: '#0f0f0f',
                        borderRadius: '4px'
                      }}>
                        <div style={{ color: '#999', fontSize: '0.75rem', marginBottom: '0.25rem' }}>
                          Translation:
                        </div>
                        <div style={{ color: '#fff', fontStyle: 'italic' }}>
                          "{translation.text}"
                        </div>
                      </div>

                      {/* Routing Info */}
                      {translation.routing_reason && (
                        <div style={{
                          marginTop: '0.5rem',
                          padding: '0.5rem',
                          background: '#1a1a2a',
                          borderRadius: '4px',
                          fontSize: '0.75rem'
                        }}>
                          <div style={{ color: '#99f', marginBottom: '0.25rem' }}>
                            <strong>Routing:</strong>
                          </div>
                          <div style={{ color: '#ccc' }}>{translation.routing_reason}</div>
                          {translation.fallback_triggered && (
                            <div style={{ color: '#fa3', marginTop: '0.25rem' }}>
                              ⚠️ Fallback triggered
                            </div>
                          )}
                          {translation.throttled && (
                            <div style={{ color: '#fa3', marginTop: '0.25rem' }}>
                              🕒 Throttled ({translation.throttle_delay_ms}ms delay)
                              {translation.throttle_reason && (
                                <div style={{ fontSize: '0.7rem', marginTop: '0.1rem' }}>
                                  {translation.throttle_reason}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Cost */}
                      <div style={{
                        marginTop: '0.5rem',
                        padding: '0.5rem',
                        background: '#1a2a1a',
                        border: '1px solid #2a4a2a',
                        borderRadius: '4px',
                        fontSize: '0.8rem',
                        color: '#9f9'
                      }}>
                        <strong>Cost:</strong> {formatCost(translation.cost_usd)}
                        {translation.cost_breakdown && (
                          <div style={{ fontSize: '0.7rem', color: '#9c9', marginTop: '0.2rem' }}>
                            {translation.cost_breakdown.units?.toFixed(0)} {translation.cost_breakdown.unit_type} × {formatCost(translation.cost_breakdown.rate_per_unit)}/{translation.cost_breakdown.unit_type}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* MT Skip Reasons Section */}
              {debugData.mt_skip_reasons && debugData.mt_skip_reasons.length > 0 && (
                <div style={{
                  background: '#0f0f0f',
                  border: '1px solid #2a2a2a',
                  borderRadius: '8px',
                  padding: '1rem',
                  marginBottom: '1rem'
                }}>
                  <h3 style={{
                    margin: '0 0 0.75rem 0',
                    fontSize: '0.95rem',
                    fontWeight: '600',
                    color: '#fb923c'
                  }}>
                    ℹ️ Translation Info
                  </h3>

                  {debugData.mt_skip_reasons.map((skip, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: '#1a1a1a',
                        border: '1px solid #2a2a2a',
                        borderRadius: '6px',
                        padding: '0.75rem',
                        marginBottom: idx < debugData.mt_skip_reasons.length - 1 ? '0.5rem' : 0,
                        fontSize: '0.85rem'
                      }}
                    >
                      <div style={{ marginBottom: '0.5rem' }}>
                        <span style={{ color: '#999' }}>Target Language:</span>{' '}
                        <span style={{
                          background: '#2a2a1a',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          color: '#fb923c',
                          fontFamily: 'monospace'
                        }}>
                          {skip.src_lang} → {skip.tgt_lang}
                        </span>
                      </div>

                      <div style={{
                        padding: '0.5rem',
                        background: '#1a1a0f',
                        borderRadius: '4px',
                        color: '#fb923c',
                        fontSize: '0.8rem'
                      }}>
                        <strong>Reason:</strong> {skip.reason}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Totals Section */}
              {debugData.totals && (
                <div style={{
                  background: '#1a2a1a',
                  border: '1px solid #2a4a2a',
                  borderRadius: '8px',
                  padding: '1rem'
                }}>
                  <h3 style={{
                    margin: '0 0 0.75rem 0',
                    fontSize: '0.95rem',
                    fontWeight: '600',
                    color: '#10b981'
                  }}>
                    💰 Cost Summary
                  </h3>

                  <div style={{ fontSize: '0.85rem' }}>
                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginBottom: '0.4rem',
                      color: '#ccc'
                    }}>
                      <span>STT Cost:</span>
                      <span style={{ fontFamily: 'monospace' }}>{formatCost(debugData.totals.stt_cost_usd)}</span>
                    </div>

                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      marginBottom: '0.4rem',
                      color: '#ccc'
                    }}>
                      <span>MT Cost ({debugData.totals.mt_translations} translations):</span>
                      <span style={{ fontFamily: 'monospace' }}>{formatCost(debugData.totals.mt_cost_usd)}</span>
                    </div>

                    <div style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      paddingTop: '0.5rem',
                      marginTop: '0.5rem',
                      borderTop: '1px solid #2a4a2a',
                      color: '#9f9',
                      fontWeight: '600',
                      fontSize: '0.95rem'
                    }}>
                      <span>Total Cost:</span>
                      <span style={{ fontFamily: 'monospace' }}>{formatCost(debugData.totals.total_cost_usd)}</span>
                    </div>
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
