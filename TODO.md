# LiveTranslator TODO

## High Priority

### 1. Voice Activity Detection (VAD)
- **Goal**: Auto-detect silence and create segments without manual "Stop mic"
- **Implementation**: 
  - Add browser-side VAD to detect speech pauses
  - Auto-send `audio_end` after 1-2 seconds of silence
  - Continue recording for next segment
  - Each sentence becomes a separate segment
- **Benefit**: Natural conversation flow, better UX

### 2. Partial Transcripts & Translations
- **Goal**: Show real-time text while speaking (not just finals)
- **Current**: Only shows final result after stopping
- **Options**:
  - Option A: Send audio chunks every 2-3 seconds to OpenAI (expensive)
  - Option B: Use OpenAI Realtime API (WebSocket, lower latency)
  - Option C: Use local Whisper for partials, OpenAI for finals
- **Benefit**: Live feedback, more engaging experience

### 3. Persistent Segment Counter
- **Issue**: segment_id resets when stt_router restarts
- **Solution**: Store counter in Redis or read max segment_id from DB on startup
- **Benefit**: Reliable segment numbering across restarts

## Medium Priority

### 4. User Attribution
- **Goal**: Track who said what (multi-speaker support)
- **Current**: All segments attributed to "system"
- **Implementation**:
  - Pass user_id/device_id through audio chunks
  - Store speaker_id in segments table
  - Show speaker names in UI
- **Benefit**: Clear conversation history with multiple participants

### 5. Room Management UI
- **Features needed**:
  - Create/join room interface
  - Room settings (language pairs, STT/MT modes)
  - Cost dashboard per room
  - Export conversation history
- **Benefit**: Better user control

### 6. Cost Optimization
- **Current**: Every message costs money (OpenAI)
- **Ideas**:
  - Cache common translations
  - Use local models for supported language pairs
  - Batch small segments
  - User quotas/limits

## Low Priority

### 7. OpenAI Realtime API Integration
- **Phase 5** from architecture plan
- Ultra-low latency STT via WebSocket
- Session-based pricing
- Complex but valuable for live conversations

### 8. Advanced Features
- Language auto-detection improvements
- Custom vocabulary/terminology
- Speaker diarization (who's speaking)
- Audio playback with timestamps
- Search through history

## Bugs to Fix

- [ ] Fix: segment_id all showing as "1" in old data
- [ ] Fix: Watchtower trying to pull local images
- [ ] Fix: Frontend doesn't show partials during speaking

## Infrastructure

- [ ] Add health checks to all services
- [ ] Prometheus metrics for cost tracking
- [ ] Grafana dashboard for monitoring
- [ ] Backup strategy for PostgreSQL
- [ ] Rate limiting on API endpoints

## Done ✅

- [x] OpenAI STT integration (Whisper API)
- [x] OpenAI MT integration (GPT-4o-mini)
- [x] Cost tracking per room
- [x] Persistence of segments and translations
- [x] Chat history API endpoint
- [x] WebSocket real-time delivery
- [x] Router architecture for multi-backend support
- [x] Database schema for rooms, segments, translations
