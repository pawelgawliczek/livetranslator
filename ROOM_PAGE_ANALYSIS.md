# RoomPage Component Analysis

## Overview
The RoomPage is the main real-time translation interface - a massive 2566-line component handling WebSocket connections, audio streaming, VAD (Voice Activity Detection), and real-time message display.

## Component Structure

### State Management (96 React hooks)
The component uses extensive state management through useState, useEffect, and useRef:

#### Core Room State
- `roomId` - Current room identifier
- `isGuest` - Guest vs authenticated user flag
- `isAdmin` - Room administrator flag
- `isPublic` - Room visibility setting
- `persistenceEnabled` - Message history persistence
- `userEmail` - Current user email

#### Audio/Speech State
- `status` - Audio streaming status (idle/streaming)
- `vadStatus` - VAD state (idle/speech detected)
- `vadReady` - VAD model loaded flag
- `pushToTalk` - PTT mode enabled
- `isPressing` - PTT button press state
- `audioLevel` - Current audio RMS level
- `audioThreshold` - VAD energy threshold

#### Message/Translation State
- `lines` - Array of chat messages with translations
- `myLanguage` - User's selected language
- `participants` - Active room participants
- `languageCounts` - Count of users per language

#### Network/Performance State
- `networkQuality` - Connection quality (high/medium/low)
- `networkRTT` - Round-trip time in ms
- `sendInterval` - Adaptive send rate

#### UI State
- `showLangPicker` - Language picker modal
- `showCosts` - Cost breakdown modal
- `showSettings` - Settings menu
- `showInvite` - Invite modal
- `showSoundSettings` - Audio settings modal

### Major Sections (89 inline style blocks)

#### 1. Header (lines ~1600-1710)
- Back button
- Centered room name
- Language participant counts (flags + numbers)
- VAD status indicator
- Menu button (⋮)

#### 2. Language Picker Modal (lines ~1712-1790)
- Full-screen modal overlay
- Language grid with flags
- Selection handler

#### 3. Costs Modal (lines ~1791-1863)
- Service breakdown (STT/MT)
- Cost per operation
- Total costs
- Close button

#### 4. Chat Messages (lines ~1864-2124)
- Scrollable message container
- Message rendering with:
  - Original text + translations
  - Speaker identification
  - Timestamp
  - Debug icon (development)
  - System messages (join/leave)
- Auto-scroll to latest

#### 5. Bottom Controls (lines ~2125-2236)
- Push-to-talk toggle
- Network status indicator
- Large microphone button:
  - Start/Stop states
  - PTT hold interaction
  - Visual feedback

#### 6. Modals & Overlays (lines ~2238-2565)
- SettingsMenu component
- InviteModal component
- SoundSettingsModal component
- AdminLeaveModal (room admin departure warning)
- RoomExpirationModal (inactive room warning)
- NotificationToast system
- ParticipantsPanel
- WelcomeBanner
- MessageDebugModal

### WebSocket Logic (Complex)

#### Main WebSocket (lines ~400-780)
- Handles incoming messages
- Translation events
- Participant updates
- Admin presence tracking
- Placeholder management
- Segment finalization

#### Presence WebSocket (lines ~850-1050)
- Join/leave notifications
- Participant list sync
- Language count updates
- Admin status tracking

### Audio Processing (Critical)

#### Audio Stream Setup (lines ~1100-1350)
- MediaStream acquisition
- AudioWorkletNode creation
- VAD integration (@ricky0123/vad-web)
- Adaptive send rate based on network
- Audio level monitoring
- Push-to-talk gate logic

#### VAD (Voice Activity Detection) (lines ~170-180)
```javascript
const SILENCE_THRESHOLD = 20;  // frames
const SPEECH_THRESHOLD = 5;    // frames
const ENERGY_THRESHOLD = 0.02; // RMS level
const RING_BUFFER_MS = 500;    // pre-speech buffer
```

### Key Functions

#### start() - Start Audio Streaming
1. Request microphone permission
2. Initialize VAD model
3. Create audio worklet
4. Connect to WebSocket
5. Begin sending audio chunks

#### stop() - Stop Audio Streaming
1. Close WebSocket
2. Stop media stream
3. Cleanup audio context
4. Reset VAD state

#### handleLanguageChange() - Update Language
1. Update local state
2. Persist to localStorage (guests) or API (users)
3. Sync with profile via language sync utility
4. Update UI

#### updatePlaceholder() - Manage Pending Messages
- Show "..." for in-progress transcriptions
- Replace with final text when ready
- Handle segment merging

### Dependencies

#### External Components (Already Updated)
- InviteModal ✅
- SettingsMenu ✅
- SoundSettingsModal ✅
- MessageDebugModal ✅
- ParticipantsPanel (needs update)
- NotificationToast (needs update)
- AdminLeftToast (needs update)

#### UI Components Available
- Card ✅
- Button ✅
- Modal ✅
- TagPill ✅
- Section ✅

#### External Libraries
- @ricky0123/vad-web - Voice activity detection
- react-i18next - Internationalization
- react-router-dom - Routing

### Complexity Metrics

| Metric | Value |
|--------|-------|
| Total Lines | 2566 |
| React Hooks | 96 |
| Inline Styles | 89 |
| useEffect Hooks | ~25 |
| WebSocket Connections | 2 |
| Event Listeners | ~15 |
| Refs | ~20 |

## Refactoring Strategy

### Phase 1: Extract Presentational Components (Low Risk)
1. **RoomHeader** - Header bar (50 lines)
2. **NetworkStatusIndicator** - Network badge (30 lines)
3. **ChatMessage** - Single message (100 lines)
4. **ChatMessageList** - Message container (150 lines)
5. **WelcomeBanner** - Welcome message (50 lines)

### Phase 2: Extract Modal Components (Medium Risk)
6. **LanguagePickerModal** - Language selection (80 lines)
7. **CostsModal** - Cost breakdown (70 lines)
8. **AdminLeaveModal** - Admin warning (80 lines)
9. **RoomExpirationModal** - Expiry warning (80 lines)

### Phase 3: Extract Interactive Components (Medium-High Risk)
10. **MicrophoneButton** - Mic control (100 lines)
11. **RoomControls** - Bottom panel (120 lines)

### Phase 4: Extract Custom Hooks (High Risk)
12. **useRoomWebSocket** - Main WS logic (400 lines)
13. **usePresenceWebSocket** - Presence WS (200 lines)
14. **useAudioStream** - Audio & VAD (500 lines)
15. **useRoomState** - Shared state management (150 lines)

### Phase 5: Reassemble (High Risk)
16. **Refactor RoomPage** - Orchestrate all components (300-400 lines)
17. **Apply Tailwind** - Replace all inline styles
18. **Integration Testing** - Full E2E tests

## Risks & Mitigation

### High-Risk Areas
1. **WebSocket State** - Message ordering, reconnection logic
   - Mitigation: Extract carefully, preserve closure patterns
2. **Audio Worklet** - Browser-specific, timing-critical
   - Mitigation: Extensive manual testing on multiple browsers
3. **VAD Integration** - ML model loading, performance
   - Mitigation: Keep VAD logic isolated, test thoroughly
4. **Placeholder Management** - Complex segment tracking
   - Mitigation: Unit tests for message update logic

### Testing Requirements
- ✅ Unit tests for each component
- ✅ Integration tests for hooks
- ⚠️ Manual testing for:
  - Audio streaming
  - VAD detection
  - WebSocket reconnection
  - Multi-user scenarios
  - Network quality adaptation

## Expected Outcomes

### Code Reduction
- Current: 2566 lines
- Target: ~1200 lines total (distributed across files)
- Reduction: ~53% (1366 lines)

### Component Distribution
- RoomPage.jsx: 300-400 lines (orchestration)
- 11 Components: ~600 lines total
- 4 Custom Hooks: ~400 lines total
- Test Files: ~500 lines total

### Benefits
- ✅ Improved maintainability
- ✅ Reusable components
- ✅ Easier testing
- ✅ Consistent design system
- ✅ Better code organization
- ✅ Theme support (light/dark)

## Next Steps
1. ✅ Setup Vitest + React Testing Library
2. 🔄 Extract RoomHeader component
3. Write RoomHeader tests
4. Continue with remaining components following test-first approach
