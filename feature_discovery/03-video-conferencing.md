# Feature 3: Video Conferencing with SFU Server

## Overview

Add video conferencing capabilities to LiveTranslator rooms, allowing participants to see each other while receiving real-time translations. This feature will enable face-to-face communication across language barriers.

### Key Concept
- **Real-Time Video/Audio**: WebRTC-based video conferencing
- **Translation Integration**: Video conference + live translation in one platform
- **Scalable Architecture**: SFU (Selective Forwarding Unit) for efficient multi-party video
- **Flexible Deployment**: Option for self-hosted or third-party service

### Use Case Example
International business meeting with 5 participants:
- Alice (US - English) sees everyone's video feeds
- Bob (Poland - Polish) sees everyone and receives English→Polish translations
- Carlos (Spain - Spanish) sees everyone and receives translations to Spanish
- All participants can screen share
- Video quality adapts to each participant's bandwidth

---

## Current System Status

### What We Have ✅
- **Room management** - Participant tracking, presence system
- **WebSocket infrastructure** - Real-time communication backbone
- **Audio capture** - Microphone access via getUserMedia
- **Docker deployment** - Containerized services

### What's Missing ❌
- **No media server** - No infrastructure for video routing
- **No WebRTC implementation** - No signaling, ICE negotiation, peer connections
- **No video UI components** - No video grid, camera controls
- **No TURN server** - No NAT traversal for restricted networks

---

## Implementation Approach: Two Paths

### Path A: Third-Party Service (Recommended for MVP)
**Effort:** 3-4 weeks | **Cost:** $9,600-$24,000 dev + ongoing API fees

**Providers:**
- **Daily.co**: $0.0007/min/participant (~$42/month per active user)
- **Twilio Video**: $0.0015/min/participant (~$90/month per active user)
- **Agora.io**: $0.99 per 1,000 minutes
- **100ms**: $0.0015/min/participant

**Pros:**
- Fast implementation (3-4 weeks vs 12-16 weeks)
- Provider handles infrastructure, scaling, reliability
- Built-in features (recording, streaming, TURN servers)
- Less maintenance burden

**Cons:**
- Ongoing per-minute costs
- Vendor lock-in
- Less control over quality/features
- Data privacy concerns (video goes through third party)

### Path B: Self-Hosted SFU (Full Control)
**Effort:** 12-16 weeks | **Cost:** $38,400-$96,000 dev + server costs

**Technologies:**
- **Mediasoup** (Recommended): Node.js, production-ready, excellent docs
- **Janus Gateway**: C-based, highly scalable, complex setup
- **ion-sfu**: Go-based, modern, smaller community

**Pros:**
- Full control over infrastructure
- No per-minute costs (just server resources)
- Data privacy (video stays on your servers)
- Customizable features

**Cons:**
- Significant development effort (3-4 months)
- Requires DevOps expertise
- Ongoing maintenance and monitoring
- Scaling challenges

---

## Path A: Third-Party Integration (RECOMMENDED)

### Phase 1: Provider Selection & Setup (1 week)

#### 1.1 Provider Evaluation (3 days)
Test each provider with LiveTranslator requirements:

**Criteria:**
- **Audio Quality**: Must support 16kHz+ for STT accuracy
- **Audio Access**: Can we tap audio for translation?
- **Participant Limit**: Support 5-10 participants minimum
- **Latency**: <300ms for real-time feeling
- **Cost**: Estimate for 1,000 room-hours/month
- **SDK Quality**: TypeScript support, documentation

**Recommended: Daily.co**
- ✅ Excellent audio quality (48kHz Opus)
- ✅ Audio track access for STT
- ✅ Supports 200 participants per room
- ✅ Average latency: 150-200ms
- ✅ Best cost/performance ratio
- ✅ React SDK with TypeScript
- ✅ Built-in TURN servers (99% connection success)

#### 1.2 Account Setup (1 day)
- Sign up for Daily.co account
- Get API key
- Configure domain settings
- Set up webhooks for events

#### 1.3 Integration Planning (3 days)
Map Daily.co rooms to LiveTranslator rooms:
- One Daily room per LiveTranslator room
- Use Daily room URL as join link
- Sync participants between systems
- Route Daily audio to STT pipeline

### Phase 2: Backend Integration (1-1.5 weeks)

#### 2.1 Daily.co API Integration (3 days)
Create `api/services/daily_service.py`:

```python
import httpx
from typing import Optional

class DailyService:
    BASE_URL = "https://api.daily.co/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.client = httpx.AsyncClient(headers={
            "Authorization": f"Bearer {api_key}"
        })

    async def create_room(self, room_code: str,
                         max_participants: int = 10) -> dict:
        """Create a Daily.co room for LiveTranslator room"""

        payload = {
            "name": f"lt-{room_code}",  # Prefix to avoid conflicts
            "privacy": "private",
            "properties": {
                "max_participants": max_participants,
                "enable_chat": False,  # We handle chat
                "enable_screenshare": True,
                "enable_recording": "cloud",  # Optional
                "start_video_off": False,
                "start_audio_off": False
            }
        }

        response = await self.client.post(f"{self.BASE_URL}/rooms", json=payload)
        return response.json()

    async def get_meeting_token(self, room_name: str,
                                user_id: str,
                                is_owner: bool = False) -> str:
        """Generate meeting token for participant"""

        payload = {
            "properties": {
                "room_name": room_name,
                "user_id": user_id,
                "is_owner": is_owner,
                "enable_recording": "cloud" if is_owner else "local"
            }
        }

        response = await self.client.post(f"{self.BASE_URL}/meeting-tokens", json=payload)
        return response.json()["token"]

    async def delete_room(self, room_name: str):
        """Delete Daily.co room when LiveTranslator room closes"""
        await self.client.delete(f"{self.BASE_URL}/rooms/{room_name}")
```

#### 2.2 Room API Modifications (2 days)
Modify [api/rooms_api.py](api/rooms_api.py):

```python
@router.post("/api/rooms")
async def create_room(user: User = Depends(get_current_user)):
    # Create LiveTranslator room
    room = Room(owner_id=user.id, code=generate_code())
    db.add(room)
    db.commit()

    # Create corresponding Daily.co room
    daily_room = await daily_service.create_room(
        room_code=room.code,
        max_participants=room.max_participants
    )

    # Store Daily room URL
    room.video_room_url = daily_room["url"]
    db.commit()

    return room

@router.get("/api/rooms/{room_id}/video-token")
async def get_video_token(room_id: int, user: User = Depends(get_current_user)):
    room = db.query(Room).get(room_id)

    # Generate Daily.co meeting token
    token = await daily_service.get_meeting_token(
        room_name=f"lt-{room.code}",
        user_id=str(user.id),
        is_owner=(user.id == room.owner_id)
    )

    return {"token": token, "room_url": room.video_room_url}
```

#### 2.3 Audio Pipeline Integration (4 days)
Extract audio from Daily.co for STT:

**Challenge:** Daily.co audio → STT pipeline

**Solution:**
```javascript
// Frontend: Capture audio tracks
dailyCall.on('track-started', (event) => {
  if (event.track.kind === 'audio') {
    // Get MediaStreamTrack
    const audioTrack = event.track;

    // Create MediaStream
    const stream = new MediaStream([audioTrack]);

    // Connect to existing audio pipeline
    connectToSTTPipeline(stream, event.participant.user_id);
  }
});
```

**Backend:** No changes needed - audio still flows through WebSocket

### Phase 3: Frontend Video UI (2-3 weeks)

#### 3.1 Daily.co React SDK Integration (1 week)
Install and configure:

```bash
npm install @daily-co/daily-react @daily-co/daily-js
```

Create `web/src/hooks/useVideoConference.jsx`:

```javascript
import { useDaily, useParticipantIds, useScreenShare } from '@daily-co/daily-react';

export const useVideoConference = (roomUrl, token) => {
  const daily = useDaily();
  const participantIds = useParticipantIds();
  const { isSharingScreen, startScreenShare, stopScreenShare } = useScreenShare();

  const joinCall = async () => {
    await daily.join({ url: roomUrl, token });
  };

  const leaveCall = async () => {
    await daily.leave();
  };

  const toggleCamera = () => {
    daily.setLocalVideo(!daily.localVideo());
  };

  const toggleMic = () => {
    daily.setLocalAudio(!daily.localAudio());
  };

  return {
    joinCall,
    leaveCall,
    toggleCamera,
    toggleMic,
    participants: participantIds,
    isSharingScreen,
    startScreenShare,
    stopScreenShare
  };
};
```

#### 3.2 Video Grid Component (1 week)
Create `web/src/components/VideoGrid.jsx`:

**Features:**
- Responsive grid layout (1-16 participants)
- Auto-layout: 1-2 participants (full), 3-4 (grid-2×2), 5-9 (grid-3×3), etc.
- Active speaker highlight
- Participant name overlay
- Language indicator badge
- Network quality indicator

**Implementation:**
```javascript
const VideoGrid = () => {
  const participantIds = useParticipantIds();

  const gridLayout = useMemo(() => {
    const count = participantIds.length;
    if (count <= 2) return 'grid-cols-1';
    if (count <= 4) return 'grid-cols-2';
    if (count <= 9) return 'grid-cols-3';
    return 'grid-cols-4';
  }, [participantIds.length]);

  return (
    <div className={`grid ${gridLayout} gap-2 p-4`}>
      {participantIds.map(id => (
        <VideoTile key={id} participantId={id} />
      ))}
    </div>
  );
};
```

#### 3.3 Video Controls (3 days)
Create `web/src/components/VideoControls.jsx`:

**Controls:**
- Camera on/off toggle
- Microphone mute/unmute
- Screen share start/stop
- Leave call button
- Settings (camera/mic selection)

**UI Location:** Bottom bar (persistent during video call)

#### 3.4 Room Page Integration (2 days)
Modify [web/src/pages/RoomPage.jsx](web/src/pages/RoomPage.jsx):

**Layout:**
```
┌─────────────────────────────────────┐
│  Video Grid (Participants)          │
│  ┌────┐ ┌────┐ ┌────┐              │
│  │ 👤 │ │ 👤 │ │ 👤 │              │
│  └────┘ └────┘ └────┘              │
├─────────────────────────────────────┤
│  Translation Chat (Scrollable)      │
│  Alice: Hello everyone              │
│  └─ Cześć wszystkim (Polish)        │
│  Bob: Jak się masz?                 │
│  └─ How are you? (English)          │
├─────────────────────────────────────┤
│  Controls: [🎥][🎤][💬][📤][⚙️]    │
└─────────────────────────────────────┘
```

**Responsive:**
- Desktop: Video (60%) + Chat (40%) side-by-side
- Mobile: Tabs (Video / Chat) or minimized video + chat overlay

### Phase 4: Testing & Optimization (1 week)

#### 4.1 Multi-User Testing (3 days)
- 2-10 participant scenarios
- Different browsers (Chrome, Firefox, Safari)
- Different networks (WiFi, 4G, 5G)
- Screen sharing tests
- Mobile app testing

#### 4.2 Performance Optimization (2 days)
- Video quality settings (360p, 720p, 1080p)
- Automatic quality adjustment based on bandwidth
- CPU usage profiling
- Memory leak detection

#### 4.3 Edge Cases (2 days)
- Participant disconnect/reconnect
- Network interruption handling
- Simultaneous screen shares
- Camera/mic permission denied

---

## Path B: Self-Hosted SFU (ADVANCED)

> **Note:** This path is for teams requiring full control or avoiding third-party dependencies. Requires significant WebRTC expertise.

### Phase 1: SFU Selection & Deployment (3-4 weeks)

#### 1.1 SFU Selection: Mediasoup (1 week)

**Why Mediasoup?**
- Production-ready (used by Whereby, LiveKit)
- Excellent documentation
- Node.js (same stack as API)
- SFU architecture (scales better than MCU)
- Built-in simulcast support
- Active community

**Alternatives:**
- **Janus Gateway**: C-based, complex, ultra-scalable
- **ion-sfu**: Go-based, modern, smaller community
- **Kurento**: Java-based, includes recording

#### 1.2 Mediasoup Docker Setup (2 weeks)

Create `mediasoup/Dockerfile`:

```dockerfile
FROM node:18-alpine

RUN apk add --no-cache \
    python3 \
    make \
    g++ \
    gcc \
    linux-headers

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 3000 10000-10100/udp

CMD ["node", "server.js"]
```

Create `mediasoup/server.js`:

```javascript
const mediasoup = require('mediasoup');
const express = require('express');
const http = require('http');
const socketio = require('socket.io');

// Configuration
const config = {
  listenIp: '0.0.0.0',
  listenPort: 3000,
  mediasoup: {
    numWorkers: 4,  // Number of CPU cores
    worker: {
      rtcMinPort: 10000,
      rtcMaxPort: 10100,
      logLevel: 'warn',
      logTags: ['info', 'ice', 'dtls', 'rtp', 'srtp', 'rtcp']
    },
    router: {
      mediaCodecs: [
        {
          kind: 'audio',
          mimeType: 'audio/opus',
          clockRate: 48000,
          channels: 2
        },
        {
          kind: 'video',
          mimeType: 'video/VP8',
          clockRate: 90000,
          parameters: {
            'x-google-start-bitrate': 1000
          }
        }
      ]
    },
    webRtcTransport: {
      listenIps: [
        { ip: '0.0.0.0', announcedIp: process.env.MEDIASOUP_ANNOUNCED_IP }
      ],
      enableUdp: true,
      enableTcp: true,
      preferUdp: true
    }
  }
};

// Initialize workers and routers
const workers = [];
let nextWorkerIndex = 0;

async function createWorker() {
  const worker = await mediasoup.createWorker(config.mediasoup.worker);
  worker.on('died', () => {
    console.error('mediasoup worker died, exiting in 2s');
    setTimeout(() => process.exit(1), 2000);
  });
  return worker;
}

async function getRouter() {
  const worker = workers[nextWorkerIndex];
  nextWorkerIndex = (nextWorkerIndex + 1) % workers.length;

  return await worker.createRouter({
    mediaCodecs: config.mediasoup.router.mediaCodecs
  });
}

// Initialize
(async () => {
  for (let i = 0; i < config.mediasoup.numWorkers; i++) {
    const worker = await createWorker();
    workers.push(worker);
  }

  // Express + Socket.io
  const app = express();
  const server = http.createServer(app);
  const io = socketio(server);

  // Store routers per room
  const routers = new Map();

  io.on('connection', (socket) => {
    console.log('Client connected:', socket.id);

    socket.on('join', async ({ roomId }, callback) => {
      // Get or create router for room
      if (!routers.has(roomId)) {
        routers.set(roomId, await getRouter());
      }

      const router = routers.get(roomId);
      callback({ rtpCapabilities: router.rtpCapabilities });
    });

    // ... more WebRTC signaling handlers
  });

  server.listen(config.listenPort, () => {
    console.log(`Mediasoup server running on port ${config.listenPort}`);
  });
})();
```

Add to `docker-compose.yml`:

```yaml
mediasoup:
  build: ./mediasoup
  network_mode: host  # Required for RTC
  environment:
    - MEDIASOUP_ANNOUNCED_IP=${PUBLIC_IP}
  volumes:
    - ./mediasoup:/app
```

#### 1.3 TURN Server (Coturn) Setup (1 week)

**Why TURN?**
- 10-20% of users behind restrictive NAT
- TURN relays media when direct P2P fails
- Essential for corporate networks

Create `coturn/docker-compose.yml`:

```yaml
coturn:
  image: coturn/coturn:latest
  network_mode: host
  volumes:
    - ./turnserver.conf:/etc/coturn/turnserver.conf
  command: ["-c", "/etc/coturn/turnserver.conf"]
```

Create `coturn/turnserver.conf`:

```
listening-port=3478
listening-ip=0.0.0.0
relay-ip=0.0.0.0
external-ip=${PUBLIC_IP}
realm=livetranslator.com
server-name=livetranslator.com
lt-cred-mech
user=livetr:${TURN_PASSWORD}
total-quota=100
max-bps=1000000
stale-nonce=600
cert=/etc/letsencrypt/live/turn.livetranslator.com/cert.pem
pkey=/etc/letsencrypt/live/turn.livetranslator.com/privkey.pem
cipher-list="ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512"
no-tlsv1
no-tlsv1_1
dh2066
```

### Phase 2: WebRTC Signaling Backend (3-4 weeks)

#### 2.1 Signaling API (2 weeks)
Create WebRTC signaling endpoints:

**Endpoints:**
- `POST /api/webrtc/rooms/{room_id}/join` - Get router RTP capabilities
- `POST /api/webrtc/transport/create` - Create send/receive transport
- `POST /api/webrtc/transport/connect` - Connect transport (ICE)
- `POST /api/webrtc/produce` - Start producing video/audio
- `POST /api/webrtc/consume` - Start consuming peer's media
- `POST /api/webrtc/leave` - Cleanup transports

**Too complex to show full implementation here** - Requires 50+ handlers.

#### 2.2 Room-Based Media Routing (1 week)
- One Mediasoup router per room
- Track producers/consumers per participant
- Handle participant join/leave
- Forward media only to room participants

#### 2.3 Audio Extraction for STT (1 week)
- Tap audio producers before routing
- Convert RTP → PCM
- Send to STT pipeline via Redis

### Phase 3: Frontend WebRTC Client (4-5 weeks)

#### 3.1 Mediasoup Client Implementation (3 weeks)
Create `web/src/hooks/useMediasoup.jsx`:

**Features:**
- Device loading (get RTP capabilities)
- Transport creation and connection
- Producer creation (camera, mic, screen)
- Consumer creation (receive peer media)
- Simulcast support (multi-quality video)

**Implementation:** 500+ lines of WebRTC logic

#### 3.2 Video UI Components (1.5 weeks)
Same as Path A (VideoGrid, VideoTile, VideoControls)

#### 3.3 Error Handling (3 days)
- ICE connection failures
- Producer/consumer errors
- Transport disconnections
- Bandwidth estimation

### Phase 4: Bandwidth & Quality Management (2-3 weeks)

#### 4.1 Simulcast Implementation (1 week)
- Producer sends 3 layers: 1080p, 540p, 270p
- Consumer selects appropriate layer
- Automatic layer switching based on bandwidth

#### 4.2 Adaptive Bitrate (1 week)
- Monitor available bandwidth
- Adjust video quality dynamically
- Prioritize audio (never drop audio)

### Phase 5: Integration with Translation (2-3 weeks)

#### 5.1 Audio Extraction (1 week)
- Extract audio from Mediasoup producers
- Convert to 16kHz PCM for STT
- Maintain existing translation flow

#### 5.2 Video Recording (1 week, optional)
- Server-side recording of mixed video
- Store to S3 or local storage
- Playback UI

### Phase 6: Testing & Production (2-3 weeks)

#### 6.1 Load Testing (1 week)
- Simulate 50+ concurrent rooms
- Monitor CPU, memory, bandwidth
- Identify bottlenecks
- Scale testing

#### 6.2 Network Condition Testing (1 week)
- Packet loss simulation (1%, 5%, 10%)
- Latency simulation (50ms, 200ms, 500ms)
- Bandwidth throttling (1 Mbps, 5 Mbps)

---

## Effort Estimate Comparison

| Path | Duration | Dev Cost | Ongoing Cost (per 1K room-hours) |
|------|----------|----------|----------------------------------|
| **Path A: Third-Party (Daily.co)** | 3-4 weeks | $9,600-$24,000 | $700/month |
| **Path B: Self-Hosted (Mediasoup)** | 12-16 weeks | $38,400-$96,000 | $150/month (server) |

**Break-Even Point:**
- Additional dev cost for self-hosted: ~$28,000 - $72,000
- Monthly savings with self-hosted: ~$550
- **Break-even: 51-131 months (4-11 years)**

**Recommendation:** Use third-party for MVP, migrate to self-hosted only if:
1. Video costs exceed $5,000/month
2. Data privacy is critical (healthcare, government)
3. Custom features not available in third-party services

---

## Cost Analysis

### Path A: Third-Party (Daily.co)

**Pricing:** $0.0007 per participant-minute

**Example Costs:**
| Usage Scenario | Monthly Cost |
|---------------|--------------|
| 100 users × 10 hours/month | $420 |
| 500 users × 10 hours/month | $2,100 |
| 1,000 users × 20 hours/month | $8,400 |

**Cost Optimization:**
- Only start video when user clicks "Join Video"
- End video session after 30s of inactivity
- Show warning at 50 minutes (near limit)

### Path B: Self-Hosted

**Infrastructure Costs:**
| Component | Monthly Cost |
|-----------|--------------|
| Media server (8 CPU, 16GB RAM) | $80-120 |
| TURN server (4 CPU, 8GB RAM) | $40-60 |
| Bandwidth (1TB @ $0.08/GB) | $80 |
| **Total** | **$200-260** |

**Scaling Costs:**
- Each media server handles ~100 concurrent participants
- Add $120/month per additional 100 users

---

## Risks & Considerations

### Technical Risks

1. **NAT Traversal Failures** (Medium Risk)
   - 10-20% of users may need TURN relay
   - TURN bandwidth expensive
   - Mitigation: Use third-party with built-in TURN

2. **Video Quality on Poor Networks** (High Risk)
   - Video degrades badly on poor connections
   - Mitigation: Adaptive bitrate, simulcast

3. **Mobile Performance** (High Risk)
   - Video encoding/decoding is CPU-intensive
   - Battery drain, overheating
   - Mitigation: Lower quality on mobile, warn users

4. **Browser Compatibility** (Medium Risk)
   - Safari has limited WebRTC support
   - iOS Safari restrictions
   - Mitigation: Test extensively, provide fallbacks

### Product Risks

1. **Cognitive Overload** (High Risk)
   - Video + text + audio translations = overwhelming
   - Mitigation: Clean UI, hide non-essential elements

2. **Privacy Concerns** (Medium Risk)
   - Users may not want video
   - Third-party services = data leaves your servers
   - Mitigation: Make video optional, self-host if needed

3. **Cost Management** (High Risk - Third-Party)
   - Video costs can explode with usage
   - Mitigation: Usage limits, show cost estimates, auto-end sessions

### UX Considerations

1. **Video vs Translation Focus** - Need clear visual hierarchy
2. **Screen Real Estate** - Video takes space from translation chat
3. **Mobile Experience** - Difficult to see video + chat on small screens
4. **Bandwidth Warnings** - Warn users with poor connections

---

## Success Metrics

1. **Video Adoption Rate** - % of rooms using video - Target: >40%
2. **Connection Success Rate** - % of successful video connects - Target: >95%
3. **Video Quality Score** - Average user rating - Target: >4/5
4. **Cost Per Video Hour** - Actual costs vs estimates
5. **Dropout Rate** - % of users who disable video mid-session
6. **TURN Relay Usage** - % of users requiring TURN - Target: <20%

---

## Future Enhancements

1. **Virtual Backgrounds** - Blur or replace background
2. **Beauty Filters** - Smooth skin, adjust lighting
3. **AI Avatars** - Generate avatar from audio (if no camera)
4. **Gesture Recognition** - Detect hand raises, thumbs up
5. **Meeting Recording** - Record video + translations
6. **Breakout Rooms** - Split into smaller groups
7. **Whiteboard** - Collaborative drawing

---

## Recommended Approach

### MVP (3-4 weeks) - Path A: Daily.co
1. Integrate Daily.co React SDK
2. Basic video grid (2-6 participants)
3. Essential controls (camera, mic, screen share)
4. Audio extraction for STT
5. Test with real users

**Launch & Validate:**
- Deploy to 10% of users
- Monitor adoption, costs, quality
- Gather user feedback

### Evaluate After 3 Months:
- If video costs > $2,000/month → Consider self-hosting
- If data privacy becomes concern → Migrate to self-hosted
- If third-party features sufficient → Stay on Daily.co

### Path B: Self-Hosted (Only if necessary)
- Start implementation only after validation
- Allocate 3-4 months for development
- Hire WebRTC specialist contractor

---

## Dependencies

### Path A:
- Daily.co API account
- React 18+
- WebRTC browser support

### Path B:
- Mediasoup, Coturn
- Public IP with open ports (UDP 10000-10100)
- SSL certificates for TURN
- WebRTC expertise on team
- DevOps for deployment

## Blockers

### Path A:
- API key provisioning (1 day)
- Billing setup

### Path B:
- Public server provisioning
- Network configuration (firewall, ports)
- SSL certificate setup
- WebRTC developer hiring

## Timeline

### Path A (Recommended):
- **Week 1:** Provider selection, setup, backend integration
- **Week 2:** Frontend Daily.co SDK integration
- **Week 3:** Video UI components
- **Week 4:** Testing, optimization, deployment

**Target Launch:** 3-4 weeks from start

### Path B (Advanced):
- **Weeks 1-4:** Mediasoup + Coturn deployment
- **Weeks 5-8:** WebRTC signaling backend
- **Weeks 9-12:** Frontend WebRTC client
- **Weeks 13-16:** Testing, optimization, deployment

**Target Launch:** 14-18 weeks from start

---

## Decision Matrix

**Choose Path A (Third-Party) if:**
- ✅ Fast time to market required (< 1 month)
- ✅ Limited WebRTC expertise on team
- ✅ Expected usage < 5,000 video hours/month
- ✅ Comfortable with data going through third party
- ✅ Want built-in features (recording, streaming, TURN)

**Choose Path B (Self-Hosted) if:**
- ✅ Data privacy is critical (healthcare, government, enterprise)
- ✅ Expected usage > 10,000 video hours/month (cost savings)
- ✅ Need custom features not available in third-party
- ✅ Have WebRTC expertise on team
- ✅ Can wait 3-4 months for launch
- ✅ Have DevOps resources for maintenance

**Our Recommendation: Path A → Path B migration if needed**

Start with Daily.co for fast validation, migrate to self-hosted only if:
1. Monthly video costs exceed $5,000
2. Privacy requirements mandate self-hosting
3. Custom features become essential

This de-risks the investment and ensures product-market fit before spending 3-4 months on infrastructure.
