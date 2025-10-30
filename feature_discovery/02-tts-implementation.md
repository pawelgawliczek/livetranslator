# Feature 2: Text-to-Speech (TTS) Implementation

## Overview

Add text-to-speech capabilities to enable users to hear translations spoken aloud in addition to reading them. This feature will support two TTS providers with different quality/cost profiles.

### Key Concept
- **Multi-Provider TTS**: Google Cloud TTS (primary) and Eleven Labs (premium)
- **Per-User Control**: Each user can enable/disable TTS independently
- **Voice Selection**: Users can choose from available voices for each language
- **Audio Playback**: Browser-based audio synthesis and mixing

### Use Case Example
Bob joins a room where people are speaking English, but he speaks Polish:
- Bob sees English text with Polish translations
- Bob enables TTS for Polish
- System synthesizes Polish translation audio and plays it automatically
- Bob adjusts playback speed to 1.2× for faster comprehension
- Bob can mute/unmute TTS without leaving the room

---

## Current System Status

### What We Have ✅
- **Text translations** - Working STT + MT pipeline
- **Multi-provider architecture** - Existing pattern for STT/MT routers
- **Cost tracking system** - Ready to track TTS costs
- **User settings infrastructure** - UI patterns for preferences

### What's Missing ❌
- **No TTS integration** - No text-to-speech providers configured
- **No audio playback system** - Frontend can't synthesize/play audio
- **No voice preferences** - No way to select or store voice preferences
- **No TTS router service** - Need new microservice for TTS

---

## Technical Implementation

### Phase 1: Backend TTS Infrastructure (2-3 weeks)

#### 1.1 TTS Router Service (1 week)
Create new service: `/opt/stack/livetranslator/api/routers/tts/router.py`

**Architecture:**
- Standalone service (similar to stt_router, mt_router)
- Redis pub/sub: `tts_requests` → `tts_audio`
- Multi-provider routing (language-based)
- Database-driven configuration

**Key Components:**
```python
# routers/tts/router.py
class TTSRouter:
    def __init__(self):
        self.providers = {
            "google": GoogleTTSBackend(),
            "elevenlabs": ElevenLabsBackend()
        }

    async def synthesize(self, text: str, language: str,
                        voice_id: str, user_id: str):
        # Select provider based on user subscription
        provider = self.select_provider(user_id, language)

        # Check cache first
        cache_key = f"tts:{hash(text)}:{voice_id}"
        audio = await redis.get(cache_key)

        if not audio:
            # Generate audio
            audio = await provider.synthesize(text, voice_id)
            # Cache for 1 hour
            await redis.setex(cache_key, 3600, audio)

        # Track costs
        await track_cost(user_id, provider, len(text))

        return audio
```

**Docker Integration:**
Add to `docker-compose.yml`:
```yaml
tts_router:
  build: ./api
  command: python -m api.routers.tts.router
  environment:
    - GOOGLE_TTS_API_KEY=${GOOGLE_TTS_API_KEY}
    - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
  depends_on:
    - redis
```

#### 1.2 Google Cloud TTS Backend (4 days)
Create `routers/tts/google_tts_backend.py`:

**Features:**
- Google Cloud Text-to-Speech API integration
- 40+ languages supported
- 200+ voice options (Standard, WaveNet, Neural2)
- SSML support for prosody control (pitch, rate, volume)
- Multiple audio formats (MP3, OGG, PCM)

**Implementation:**
```python
from google.cloud import texttospeech

class GoogleTTSBackend:
    def __init__(self):
        self.client = texttospeech.TextToSpeechClient()

    async def synthesize(self, text: str, voice_id: str,
                        language: str = "en-US",
                        rate: float = 1.0,
                        pitch: float = 0.0):

        synthesis_input = texttospeech.SynthesisInput(text=text)

        voice = texttospeech.VoiceSelectionParams(
            language_code=language,
            name=voice_id,  # e.g., "en-US-Neural2-A"
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL
        )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=rate,
            pitch=pitch
        )

        response = self.client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        return response.audio_content
```

**Voice Selection:**
- Standard voices: $4 per 1M characters
- WaveNet voices: $16 per 1M characters
- Neural2 voices: $16 per 1M characters

**Recommended Default:**
- Free tier: Standard voices
- Plus tier: WaveNet/Neural2 voices

#### 1.3 Eleven Labs Backend (4 days)
Create `routers/tts/elevenlabs_backend.py`:

**Features:**
- Premium quality voice synthesis
- Voice cloning support
- Streaming API for low latency
- 29 languages supported
- Emotional voice control

**Implementation:**
```python
import httpx

class ElevenLabsBackend:
    BASE_URL = "https://api.elevenlabs.io/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient()

    async def synthesize(self, text: str, voice_id: str,
                        model_id: str = "eleven_multilingual_v2"):

        url = f"{self.BASE_URL}/text-to-speech/{voice_id}"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        payload = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }

        response = await self.client.post(url, json=payload, headers=headers)
        return response.content

    async def clone_voice(self, voice_name: str, audio_files: list):
        """Clone a voice from audio samples"""
        url = f"{self.BASE_URL}/voices/add"
        # ... implementation
```

**Voice Cloning Flow:**
1. User uploads 1-5 minutes of audio samples
2. API processes and creates voice profile
3. Voice ID stored in user preferences
4. Use cloned voice for TTS synthesis

**Cost:**
- Basic: $0.30 per 1,000 characters (~10× Google)
- Premium features (cloning): Requires paid subscription

#### 1.4 Audio Caching System (2 days)
Optimize costs with aggressive caching:

**Cache Strategy:**
```python
# Cache key: hash(text + voice_id + language + rate + pitch)
cache_key = f"tts:{hashlib.md5(key_components.encode()).hexdigest()}"

# TTL: 1 hour (balance between cost savings and memory)
await redis.setex(cache_key, 3600, audio_blob)
```

**Cache Optimization:**
- Pre-generate common phrases ("Hello", "Thank you", etc.)
- LRU eviction when cache size > 500MB
- Separate cache per provider (Google vs Eleven Labs)

---

### Phase 2: Database & Cost Tracking (1 week)

#### 2.1 Database Schema (2 days)
Modify [api/models.py](api/models.py):

```python
class User(Base):
    # ... existing fields ...
    tts_enabled = Column(Boolean, default=False)
    tts_provider = Column(String(20), default="google")  # "google" or "elevenlabs"
    tts_rate = Column(Float, default=1.0)  # Playback speed multiplier

class UserVoicePreference(Base):
    __tablename__ = "user_voice_preferences"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    language = Column(String(10))  # "en", "pl", "es"
    voice_id = Column(String(100))  # Provider-specific voice ID
    provider = Column(String(20))  # "google" or "elevenlabs"

    user = relationship("User", back_populates="voice_preferences")

class RoomCost(Base):
    # ... existing fields ...
    tts_cost = Column(Float, default=0.0)
    tts_characters = Column(Integer, default=0)
```

#### 2.2 TTS Settings API (2 days)
Add endpoints to [api/profile_api.py](api/profile_api.py):

- `PATCH /api/profile/tts-settings`
  - Enable/disable TTS
  - Set default provider
  - Set playback rate
  - Body: `{tts_enabled: true, tts_provider: "google", tts_rate: 1.2}`

- `GET /api/profile/voice-preferences`
  - List user's voice preferences per language
  - Response: `[{language: "en", voice_id: "en-US-Neural2-A", provider: "google"}]`

- `PUT /api/profile/voice-preferences/{language}`
  - Set voice for specific language
  - Body: `{voice_id: "en-US-Neural2-C", provider: "google"}`

- `GET /api/tts/voices`
  - List available voices per provider
  - Query params: `?provider=google&language=en`
  - Response: Voice catalog with samples

#### 2.3 Cost Tracking Integration (2 days)
Modify [api/services/cost_tracker.py](api/services/cost_tracker.py):

**Cost Calculation:**
```python
# Google Cloud TTS
standard_cost = characters / 1_000_000 * 4.0  # $4 per 1M chars
wavenet_cost = characters / 1_000_000 * 16.0  # $16 per 1M chars

# Eleven Labs
elevenlabs_cost = characters / 1_000 * 0.30  # $0.30 per 1K chars
```

**Usage Limits (per month):**
- Free tier: 10,000 characters
- Plus tier: 500,000 characters (Google), 50,000 (Eleven Labs)
- Pro tier: Unlimited

---

### Phase 3: Frontend Audio Playback (2-3 weeks)

#### 3.1 Audio Playback Hook (1 week)
Create `web/src/hooks/useAudioPlayback.jsx`:

**Features:**
- Audio queue management (sequential playback)
- Volume control per speaker
- Playback status tracking
- Audio ducking (fade current audio when new arrives)

**Implementation:**
```javascript
export const useAudioPlayback = () => {
  const audioContextRef = useRef(null);
  const playbackQueueRef = useRef([]);
  const [isPlaying, setIsPlaying] = useState(false);

  const initAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    }
  };

  const playAudio = async (audioBlob, speakerId) => {
    initAudioContext();

    // Decode audio
    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioContextRef.current.decodeAudioData(arrayBuffer);

    // Create source node
    const source = audioContextRef.current.createBufferSource();
    source.buffer = audioBuffer;

    // Create gain node for volume control
    const gainNode = audioContextRef.current.createGain();
    gainNode.gain.value = getVolumeForSpeaker(speakerId);

    // Connect: source -> gain -> destination
    source.connect(gainNode);
    gainNode.connect(audioContextRef.current.destination);

    // Play
    source.start(0);
    setIsPlaying(true);

    // Cleanup when finished
    source.onended = () => {
      setIsPlaying(false);
      playNext(); // Play next in queue
    };
  };

  const queueAudio = (audioBlob, speakerId) => {
    playbackQueueRef.current.push({audioBlob, speakerId});

    if (!isPlaying) {
      playNext();
    }
  };

  return {playAudio, queueAudio, isPlaying};
};
```

#### 3.2 Multi-Speaker Audio Mixing (4 days)
Handle simultaneous TTS from multiple speakers:

**Approach 1: Sequential (Recommended for MVP)**
- Queue all TTS requests
- Play one at a time
- Simple, no confusion

**Approach 2: Simultaneous (Advanced)**
- Play multiple TTS concurrently
- Apply stereo panning (different speakers → different ears)
- Requires more CPU, potentially confusing

**Implementation (Sequential):**
```javascript
const handleTranslation = (translation) => {
  if (!user.tts_enabled) return;

  // Request TTS audio from backend
  fetch(`/api/tts/synthesize`, {
    method: 'POST',
    body: JSON.stringify({
      text: translation.text,
      language: user.preferred_language,
      voice_id: user.voice_preferences[translation.language]
    })
  })
  .then(res => res.blob())
  .then(audioBlob => {
    // Queue for playback
    queueAudio(audioBlob, translation.speaker_id);
  });
};
```

#### 3.3 Playback Controls UI (3 days)
Create `web/src/components/TTSControls.jsx`:

**Features:**
- Enable/disable TTS toggle
- Volume slider (0-100%)
- Playback speed selector (0.5×, 0.75×, 1×, 1.25×, 1.5×, 2×)
- Skip current TTS button
- Visual playback indicator (sound waves animation)

**UI Location:**
- Persistent controls in room header
- Speaker-specific mute buttons in participant list
- Settings integration

---

### Phase 4: Voice Selection UI (1 week)

#### 4.1 Voice Picker Modal (3 days)
Create `web/src/components/VoicePickerModal.jsx`:

**Features:**
- Browse voices by language
- Filter by:
  - Gender (male, female, neutral)
  - Accent (US, UK, Australian, etc.)
  - Voice type (Standard, WaveNet, Neural)
- Preview button (play sample phrase)
- Favorites system (star voices)
- Current selection indicator

**Sample Audio:**
```javascript
const previewVoice = (voiceId, language) => {
  const samplePhrases = {
    'en': 'Hello, this is a sample of my voice.',
    'pl': 'Witaj, to jest próbka mojego głosu.',
    'es': 'Hola, esta es una muestra de mi voz.'
  };

  // Generate TTS for sample phrase
  synthesizeSample(samplePhrases[language], voiceId);
};
```

#### 4.2 Settings Integration (2 days)
Modify [web/src/components/SettingsMenu.jsx](web/src/components/SettingsMenu.jsx):

**Add TTS Section:**
- Enable TTS toggle (main switch)
- Provider selector (Google / Eleven Labs) [Pro only]
- Playback speed slider
- "Configure Voices" button → opens VoicePickerModal
- Current voices per language (quick view)

**Settings Persistence:**
- Save to backend: `/api/profile/tts-settings`
- Sync to localStorage for offline access
- Apply immediately (no page reload)

---

### Phase 5: Eleven Labs Premium Features (1-2 weeks, Optional)

#### 5.1 Voice Cloning UI (1 week)
Create `web/src/components/VoiceCloningModal.jsx`:

**Flow:**
1. User uploads audio samples (1-5 files, 1-5 minutes total)
2. Progress indicator during upload
3. Backend sends to Eleven Labs API for processing
4. Voice profile created (takes 2-5 minutes)
5. User can preview cloned voice
6. Add to voice library with custom name

**Backend Endpoint:**
```python
@router.post("/api/tts/clone-voice")
async def clone_voice(
    files: List[UploadFile],
    voice_name: str,
    user: User = Depends(get_current_user)
):
    # Verify user has Pro subscription
    if user.subscription_tier != "pro":
        raise HTTPException(403, "Voice cloning requires Pro subscription")

    # Upload to Eleven Labs
    voice_id = await elevenlabs_backend.clone_voice(voice_name, files)

    # Save to user preferences
    preference = UserVoicePreference(
        user_id=user.id,
        language=user.preferred_language,
        voice_id=voice_id,
        provider="elevenlabs"
    )
    db.add(preference)
    db.commit()

    return {"voice_id": voice_id, "message": "Voice cloned successfully"}
```

#### 5.2 Cost Gating (2 days)
Restrict premium features to paid users:

- **Free Tier:**
  - Google Standard voices only
  - 10,000 characters/month
  - No voice cloning

- **Plus Tier ($9/month):**
  - Google WaveNet/Neural2 voices
  - 500,000 characters/month
  - No voice cloning

- **Pro Tier ($29/month):**
  - All Google voices
  - Eleven Labs access (50,000 chars/month)
  - Voice cloning (3 custom voices)
  - Unlimited characters

**UI Implementation:**
```javascript
const VoicePickerModal = ({user}) => {
  const availableVoices = useMemo(() => {
    if (user.tier === 'free') {
      return voices.filter(v => v.type === 'standard');
    } else if (user.tier === 'plus') {
      return voices.filter(v => v.provider === 'google');
    } else {
      return voices; // All voices for Pro
    }
  }, [user.tier, voices]);

  const showUpgradePrompt = (voice) => {
    if (voice.provider === 'elevenlabs' && user.tier !== 'pro') {
      return <UpgradePrompt tier="pro" feature="Premium AI Voices" />;
    }
  };
};
```

---

### Phase 6: Testing & Optimization (1 week)

#### 6.1 Playback Quality Testing (3 days)
- **Audio Format Comparison:**
  - MP3 (compressed, smaller): ~50KB per 10 seconds
  - OGG (compressed, better quality): ~60KB per 10 seconds
  - PCM (uncompressed, best): ~320KB per 10 seconds
  - **Recommendation:** MP3 for mobile, OGG for desktop

- **Latency Optimization:**
  - Target: <300ms from text → audio start
  - Pre-fetch TTS for predicted translations
  - Streaming TTS (Eleven Labs supports this)

- **Browser Compatibility:**
  - Chrome/Edge: Full support ✅
  - Firefox: Full support ✅
  - Safari: Requires user gesture to start AudioContext ⚠️
  - Mobile browsers: Battery/performance considerations

#### 6.2 Cost Optimization (2 days)
- **Cache Hit Rate Analysis:**
  - Monitor cache hits vs misses
  - Identify frequently translated phrases
  - Pre-generate common translations

- **Partial Translation Strategy:**
  - Don't synthesize TTS for partial transcriptions (too noisy)
  - Only generate TTS for final transcriptions

- **Batch Optimization:**
  - Combine short segments (< 5 words) before TTS
  - Reduces API calls, improves prosody

#### 6.3 Multi-User Testing (2 days)
- Test with 2-5 concurrent TTS streams
- Network condition simulation (slow 3G, 4G, WiFi)
- Mobile device testing (iOS, Android)
- Battery impact measurement

---

## Effort Estimate

| Phase | Duration | Complexity |
|-------|----------|------------|
| Backend TTS infrastructure | 2-3 weeks | Medium |
| Database & cost tracking | 1 week | Low-Medium |
| Frontend audio playback | 2-3 weeks | Medium-High |
| Voice selection UI | 1 week | Medium |
| Eleven Labs premium (optional) | 1-2 weeks | Medium |
| Testing & optimization | 1 week | Medium |
| **Total (MVP)** | **5-7 weeks** | **Medium** |
| **Total (Full)** | **7-10 weeks** | **Medium** |

**Team Size:** 1 full-stack developer

**Cost Estimate:**
- MVP: $16,000 - $42,000 (at $80-150/hr)
- Full: $22,400 - $60,000

---

## Cost Impact Analysis

### API Costs Per Room-Hour

**Google Cloud TTS:**
| Voice Type | Cost per 1M chars | Typical Room-Hour Cost |
|-----------|------------------|----------------------|
| Standard | $4 | $0.40 - $0.80 |
| WaveNet | $16 | $1.60 - $3.20 |
| Neural2 | $16 | $1.60 - $3.20 |

**Eleven Labs:**
| Usage | Cost per 1K chars | Typical Room-Hour Cost |
|-------|------------------|----------------------|
| Basic | $0.30 | $30 - $60 |

**Assumptions:**
- Average room: 100 words/minute per speaker
- Average word: 5 characters
- Average room-hour: 100,000 characters

**Multi-Speaker Impact:**
- 2 speakers: 2× TTS requests (each speaker's target language)
- 3 speakers: 3× TTS requests
- TTS cost scales linearly with speaker count (unlike MT which is quadratic)

---

## Risks & Considerations

### Technical Risks

1. **Audio Timing/Sync** (Medium Risk)
   - TTS playback may lag behind text display
   - Mitigation: Pre-fetch TTS, use streaming API

2. **Mobile Performance** (High Risk)
   - Audio decoding is CPU-intensive
   - Battery drain concerns
   - Mitigation: Lower quality on mobile, warn users

3. **Browser Audio Policies** (Medium Risk)
   - Safari requires user gesture to play audio
   - Mitigation: Auto-play after first user interaction

4. **Network Latency** (Low Risk)
   - Slow connections delay TTS playback
   - Mitigation: Show loading indicator, queue management

### Product Risks

1. **Cognitive Overload** (High Risk)
   - Multiple TTS voices + visual text = overwhelming
   - Mitigation: Default to TTS-only mode, hide text option

2. **Voice Quality Expectations** (Medium Risk)
   - Users may expect human-like voices
   - Google Standard voices sound robotic
   - Mitigation: Offer WaveNet/Eleven Labs for premium

3. **Cost Management** (High Risk)
   - Eleven Labs is 10× more expensive than Google
   - Mitigation: Restrict to Pro tier, show cost estimates

### UX Considerations

1. **Playback Control** - Users need easy pause/skip/volume controls
2. **Voice Preferences** - Allow per-language voice selection
3. **Queue Management** - Visual indicator of pending TTS (e.g., "2 messages queued")
4. **Accessibility** - TTS is critical for visually impaired users

---

## Success Metrics

1. **TTS Adoption Rate** - % of users enabling TTS - Target: >30%
2. **TTS Retention** - % of users keeping TTS enabled - Target: >70%
3. **Voice Preview Usage** - % of users trying voice samples - Target: >50%
4. **Provider Distribution** - Google vs Eleven Labs usage
5. **Cost Per User** - Actual TTS costs vs estimates
6. **Playback Quality** - Error rate, latency metrics

---

## Future Enhancements

1. **Offline TTS** - Browser-native Web Speech API for offline mode
2. **Emotional Prosody** - Adjust voice tone based on sentiment
3. **Voice Mixing** - Blend multiple voices for multi-speaker effect
4. **Custom Voice Training** - Train on user's past translations
5. **Lip Sync** (if video feature added) - Sync TTS with video avatar
6. **Podcast Export** - Export room conversation as podcast with TTS

---

## Recommended Approach

### MVP Scope (5-6 weeks)
- Google Cloud TTS only (Standard + WaveNet voices)
- Sequential playback (no mixing)
- Basic voice selection (5-10 voices per language)
- Essential controls (enable/disable, volume, skip)

### Full Version (7-10 weeks)
- Eleven Labs integration
- Voice cloning for Pro users
- Advanced playback (simultaneous, panning)
- Extensive voice library (50+ voices)
- Cost optimization (aggressive caching)

### Start With:
1. Backend TTS router + Google integration (weeks 1-2)
2. Frontend audio playback system (weeks 3-4)
3. Voice selection UI (week 5)
4. Test with users, gather feedback (week 6)
5. Add Eleven Labs if demanded (weeks 7-8)

---

## Dependencies

- Google Cloud TTS API account ($$$)
- Eleven Labs API account (optional, $$$$)
- Browser support for Web Audio API (Chrome, Firefox, Safari)
- Sufficient bandwidth for audio streaming (10-50KB per message)

## Blockers

- API keys/accounts need to be provisioned
- Subscription tier system must be implemented (if not already exists)
- Billing system for tracking usage limits

## Timeline

- **Weeks 1-2:** Backend TTS infrastructure (router, Google backend)
- **Weeks 3-4:** Frontend audio playback system
- **Week 5:** Voice selection UI
- **Week 6:** Testing & optimization
- **Weeks 7-8:** (Optional) Eleven Labs + voice cloning
- **Week 9-10:** (Optional) Advanced features + polish

**Target Launch (MVP):** 5-6 weeks from start
**Target Launch (Full):** 8-10 weeks from start
