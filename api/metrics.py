from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

MET_WS_CONNS = Gauge("ws_connections", "Active WS connections")
MET_STT_EVENTS = Counter("stt_events_total", "STT events seen", ["kind"])
MET_MT_REQ = Counter("mt_requests_total", "MT requests")
MET_MT_ERR = Counter("mt_errors_total", "MT errors")
MET_MT_LAT = Histogram("mt_latency_seconds", "MT roundtrip seconds")
# Re-export helpers for the endpoint
__all__ = [
    "MET_WS_CONNS", "MET_STT_EVENTS", "MET_MT_REQ", "MET_MT_ERR", "MET_MT_LAT",
    "generate_latest", "CONTENT_TYPE_LATEST",
]
