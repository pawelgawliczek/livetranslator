# iOS app technical spec

## Requirements

- iOS 16+, Swift 5.9+, Xcode 15+
- iPhone 8+ / iPad 5th gen+
- Microphone access required

## Apple frameworks

### Speech Framework (SFSpeechRecognizer)

On-device speech-to-text. No server cost for STT when using this.

```swift
let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
recognizer?.supportsOnDeviceRecognition = true

let request = SFSpeechAudioBufferRecognitionRequest()
request.shouldReportPartialResults = true
request.requiresOnDeviceRecognition = true
```

Limits: 1 minute per request (restart for longer), unlimited in on-device mode (iOS 15+), 60+ languages.

### Translation Framework

On-device translation for common pairs (English to/from Spanish, French, German, Italian, Portuguese, Chinese, Japanese, Korean). Other pairs need network.

```swift
let configuration = TranslationSession.Configuration(
    source: Locale.Language(identifier: source),
    target: Locale.Language(identifier: target)
)
let session = TranslationSession(configuration: configuration)
let response = try await session.translate(text)
```

### AVFoundation

Audio capture (microphone) and TTS playback (AVSpeechSynthesizer). Configured for `.playAndRecord` mode with Bluetooth support.

## Architecture

MVVM + Combine. SwiftUI views bind to ViewModels via `@ObservedObject` / `@Published`. ViewModels call into services (WebSocket, Speech, Audio). Services talk to the API via `APIClient`.

```
SwiftUI Views
    ↓ @ObservedObject
ViewModels
    ↓ Combine Publishers
Services (WebSocket, Speech, Audio)
    ↓
APIClient / LocalStorage
```

## Offline mode

What works offline:
- Speech-to-text (Apple STT, on-device)
- Translation (Apple Translation, cached language pairs)
- TTS (AVSpeechSynthesizer, always offline)
- Local message queue (SQLite, syncs when back online)

What needs network:
- Room join/create
- Real-time sync with other participants
- Server-side translation (DeepL/Google/OpenAI)

## Background audio

Configured via `UIBackgroundModes: audio`. Audio session stays active when app is backgrounded. WebSocket stays connected for ~30 minutes in background.

Info.plist permissions:
- `NSMicrophoneUsageDescription`
- `NSSpeechRecognitionUsageDescription`

## WebSocket

Uses Starscream (SPM). Connects to `wss://<domain>/ws/<roomCode>` with JWT in Authorization header. Auto-reconnect with exponential backoff (1s, 2s, 4s, 8s, 16s max). Ping/pong every 30 seconds.

## Performance targets

| Operation | P50 | P95 |
|-----------|-----|-----|
| Apple STT | <1s | <2s |
| Server-side MT | <500ms | <1s |
| WebSocket delivery | <100ms | <200ms |

Memory: <50MB idle, <80MB active speaking, <30MB background.
Battery: <5% per hour of active use.
Data: <1MB per 30-minute conversation (audio stays on-device).

## Current implementation status

Implemented:
- Email/password auth
- Google OAuth
- JWT token management (Keychain)
- Profile management
- Network connectivity monitoring

Not yet implemented:
- Room creation and joining
- Real-time transcription UI
- Voice activity detection
- QR code scanning
- On-device STT/MT integration
