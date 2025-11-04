# LiveTranslator iOS App - Technical Specification

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Architecture - Development Ready

---

## Table of Contents
1. [System Requirements](#system-requirements)
2. [Apple Frameworks](#apple-frameworks)
3. [Architecture](#architecture)
4. [Offline Mode](#offline-mode)
5. [Background Audio](#background-audio)
6. [Apple Review Compliance](#apple-review-compliance)
7. [StoreKit 2 Integration](#storekit-2-integration)
8. [Push Notifications](#push-notifications)
9. [Network & WebSocket](#network--websocket)
10. [Performance Targets](#performance-targets)

---

## System Requirements

### Minimum Requirements
- **iOS Version:** 15.0 (for StoreKit 2, improved Speech Recognition)
- **Target iOS:** 17.0+ (recommended for latest features)
- **Swift:** 5.9+
- **Xcode:** 15.0+
- **Devices:** iPhone 8 and later, iPad (5th gen) and later

### Device Capabilities Required
- **Microphone:** Required for speech capture
- **Network:** WiFi or Cellular (4G/5G recommended)
- **Storage:** 50MB app size, 100MB data (transcripts, cache)
- **Memory:** 128MB minimum available RAM

### Framework Versions
- **Speech Framework:** iOS 15+ (on-device recognition)
- **Translation Framework:** iOS 15+ (offline capable)
- **StoreKit 2:** iOS 15+ (async/await API)
- **AVFoundation:** iOS 14+ (audio capture + TTS)
- **Combine:** iOS 13+ (reactive programming)

---

## Apple Frameworks

### 1. Speech Framework (SFSpeechRecognizer)

**Purpose:** On-device speech-to-text transcription (zero server cost)

**Configuration:**
```swift
import Speech

class SpeechRecognitionService {
    private let recognizer: SFSpeechRecognizer?
    private var recognitionRequest: SFSpeechAudioBufferRecognitionRequest?
    private var recognitionTask: SFSpeechRecognitionTask?

    init(locale: Locale = Locale(identifier: "en-US")) {
        recognizer = SFSpeechRecognizer(locale: locale)
        recognizer?.supportsOnDeviceRecognition = true // iOS 15+
    }

    func requestAuthorization() async -> Bool {
        await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { status in
                continuation.resume(returning: status == .authorized)
            }
        }
    }

    func startRecognition(audioEngine: AVAudioEngine) throws {
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.requiresOnDeviceRecognition = true // Force on-device

        recognitionTask = recognizer?.recognitionTask(with: request) { [weak self] result, error in
            if let result = result {
                let transcript = result.bestTranscription.formattedString
                let isFinal = result.isFinal

                if isFinal {
                    // Send to backend via WebSocket
                    self?.sendTranscriptToBackend(text: transcript, isFinal: true)
                } else {
                    // Display locally (do not send partials)
                    self?.updateLocalUI(text: transcript)
                }
            }
        }

        // Attach audio buffer
        let inputNode = audioEngine.inputNode
        let recordingFormat = inputNode.outputFormat(forBus: 0)
        inputNode.installTap(onBus: 0, bufferSize: 1024, format: recordingFormat) { buffer, _ in
            request.append(buffer)
        }
    }
}
```

**Limits:**
- 1 minute per recognition request (restart for longer sessions)
- 60 minutes per day per device (on-device mode: unlimited iOS 15+)
- Requires microphone permission

**Supported Languages:** 60+ languages (see Apple documentation)

---

### 2. Translation Framework

**Purpose:** On-device translation (offline capable for common language pairs)

**Configuration:**
```swift
import Translation

@available(iOS 15.0, *)
class TranslationService {
    func translateText(_ text: String, from source: String, to target: String) async throws -> String {
        let configuration = TranslationSession.Configuration(
            source: Locale.Language(identifier: source),
            target: Locale.Language(identifier: target)
        )

        let session = TranslationSession(configuration: configuration)

        let response = try await session.translate(text)
        return response.targetText
    }

    func downloadLanguageModel(for language: String) async throws {
        // Pre-download for offline use
        let configuration = TranslationSession.Configuration(
            source: .english,
            target: Locale.Language(identifier: language)
        )
        try await TranslationSession.prepareLanguagePair(for: configuration)
    }
}
```

**Offline Support:**
- English ↔ Spanish, French, German, Italian, Portuguese, Chinese, Japanese, Korean
- Other pairs require online connection

**Fallback:** If offline translation fails, use server-side MT (DeepL/Google)

---

### 3. AVFoundation (Audio Capture + TTS)

**Purpose:** Microphone capture + Text-to-Speech playback

**Audio Session Configuration:**
```swift
import AVFoundation

class AudioSessionManager {
    func configureAudioSession() throws {
        let session = AVAudioSession.sharedInstance()

        // Allow simultaneous recording and playback
        try session.setCategory(.playAndRecord, mode: .voiceChat, options: [
            .defaultToSpeaker,
            .allowBluetooth,
            .allowBluetoothA2DP
        ])

        // Enable background audio
        try session.setActive(true)
    }

    func handleInterruption(notification: Notification) {
        guard let userInfo = notification.userInfo,
              let typeValue = userInfo[AVAudioSessionInterruptionTypeKey] as? UInt,
              let type = AVAudioSession.InterruptionType(rawValue: typeValue) else {
            return
        }

        switch type {
        case .began:
            // Pause audio capture/playback
            pauseAudio()
        case .ended:
            // Resume audio
            if let optionsValue = userInfo[AVAudioSessionInterruptionOptionKey] as? UInt {
                let options = AVAudioSession.InterruptionOptions(rawValue: optionsValue)
                if options.contains(.shouldResume) {
                    resumeAudio()
                }
            }
        @unknown default:
            break
        }
    }
}
```

**TTS (AVSpeechSynthesizer):**
```swift
class TTSService {
    private let synthesizer = AVSpeechSynthesizer()

    func speak(_ text: String, language: String, rate: Float = 0.5) {
        let utterance = AVSpeechUtterance(string: text)
        utterance.voice = AVSpeechSynthesisVoice(language: language)
        utterance.rate = rate // 0.0-1.0 (0.5 = normal speed)
        utterance.pitchMultiplier = 1.0
        utterance.volume = 1.0

        synthesizer.speak(utterance)
    }

    func stop() {
        synthesizer.stopSpeaking(at: .immediate)
    }
}
```

---

### 4. StoreKit 2

**Purpose:** In-App Purchases (subscriptions + consumables)

**Configuration:**
```swift
import StoreKit

@available(iOS 15.0, *)
class StoreService: ObservableObject {
    @Published var products: [Product] = []
    @Published var purchasedProductIDs: Set<String> = []

    private var transactionListener: Task<Void, Error>?

    func loadProducts() async throws {
        let productIDs: Set<String> = [
            "com.livetranslator.plus.monthly",
            "com.livetranslator.pro.monthly",
            "com.livetranslator.credits.4hr"
        ]

        products = try await Product.products(for: productIDs)
    }

    func purchase(_ product: Product) async throws -> Transaction? {
        let result = try await product.purchase()

        switch result {
        case .success(let verification):
            let transaction = try checkVerified(verification)

            // Send receipt to backend
            await verifyWithBackend(transaction)

            // Finish transaction (acknowledge to Apple)
            await transaction.finish()

            return transaction

        case .userCancelled:
            return nil

        case .pending:
            // Parental approval required
            return nil

        @unknown default:
            return nil
        }
    }

    func checkVerified<T>(_ result: VerificationResult<T>) throws -> T {
        switch result {
        case .unverified:
            throw StoreError.failedVerification
        case .verified(let safe):
            return safe
        }
    }

    func verifyWithBackend(_ transaction: Transaction) async {
        // Extract receipt data
        let receiptData = transaction.jsonRepresentation.base64EncodedString()

        // Send to backend
        let request = VerifyAppleReceiptRequest(
            transaction_id: String(transaction.id),
            original_transaction_id: String(transaction.originalID),
            product_id: transaction.productID,
            receipt_data: receiptData
        )

        do {
            let response = try await apiClient.post("/api/payments/apple-verify", body: request)
            print("✅ Receipt verified: \(response)")
        } catch {
            print("❌ Receipt verification failed: \(error)")
        }
    }

    func listenForTransactions() {
        transactionListener = Task.detached {
            for await result in Transaction.updates {
                do {
                    let transaction = try self.checkVerified(result)
                    await self.verifyWithBackend(transaction)
                    await transaction.finish()
                } catch {
                    print("Transaction verification failed: \(error)")
                }
            }
        }
    }
}
```

**Product IDs (configured in App Store Connect):**
- Subscriptions:
  - `com.livetranslator.plus.monthly` - $29/month
  - `com.livetranslator.pro.monthly` - $199/month
- Consumables (Credits):
  - `com.livetranslator.credits.1hr` - $5
  - `com.livetranslator.credits.4hr` - $19
  - `com.livetranslator.credits.8hr` - $35
  - `com.livetranslator.credits.20hr` - $80

---

## Architecture

### MVVM + Combine

**Pattern:** Model-View-ViewModel + Reactive bindings

```
┌─────────────────────────────────────────┐
│            SwiftUI Views                │
│  (RoomView, TranscriptView, SettingsView)│
└────────────┬────────────────────────────┘
             │ @ObservedObject / @Published
             ▼
┌─────────────────────────────────────────┐
│           ViewModels                    │
│  (RoomViewModel, QuotaViewModel, etc.)  │
└────────────┬────────────────────────────┘
             │ Combine Publishers
             ▼
┌─────────────────────────────────────────┐
│            Services                     │
│  (WebSocketService, SpeechService,      │
│   StoreService, AudioService)           │
└────────────┬────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────┐
│       Repositories (Data Layer)         │
│  (APIClient, LocalStorage, CacheManager)│
└─────────────────────────────────────────┘
```

### Core Services

**1. WebSocketService:** Real-time communication with backend
**2. SpeechRecognitionService:** Apple STT integration
**3. TTSService:** Apple TTS playback
**4. StoreService:** StoreKit 2 IAP
**5. QuotaService:** Quota tracking + alerts
**6. AudioSessionManager:** Background audio handling

---

## Offline Mode

### Capabilities

**What Works Offline:**
1. Speech-to-Text (Apple STT, on-device)
2. Translation (Apple Translation, for cached language pairs)
3. TTS (AVSpeechSynthesizer, always offline)
4. Local queue (SQLite for unsent messages)

**What Requires Network:**
1. Room join/create
2. Real-time sync with other participants
3. Server-side translation (DeepL/Google)
4. Quota deduction confirmation

### Implementation

**Local Message Queue:**
```swift
import SQLite

class MessageQueue {
    private let db: Connection

    struct QueuedMessage {
        let id: String
        let roomCode: String
        let text: String
        let sourceLang: String
        let timestamp: Date
        var synced: Bool
    }

    func enqueue(_ message: QueuedMessage) throws {
        let messages = Table("queued_messages")
        let id = Expression<String>("id")
        let roomCode = Expression<String>("room_code")
        let text = Expression<String>("text")
        let timestamp = Expression<Date>("timestamp")
        let synced = Expression<Bool>("synced")

        try db.run(messages.insert(
            id <- message.id,
            roomCode <- message.roomCode,
            text <- message.text,
            timestamp <- message.timestamp,
            synced <- false
        ))
    }

    func syncWhenOnline() async {
        let unsynced = try? db.prepare(messages.filter(synced == false))

        for message in unsynced ?? [] {
            do {
                try await apiClient.post("/api/transcript-direct", body: message)
                try db.run(messages.filter(id == message[id]).update(synced <- true))
            } catch {
                print("Failed to sync message: \(error)")
                break // Stop on first failure, retry later
            }
        }
    }
}
```

**Offline Detection:**
```swift
import Network

class NetworkMonitor: ObservableObject {
    @Published var isConnected = true
    private let monitor = NWPathMonitor()
    private let queue = DispatchQueue.global(qos: .background)

    init() {
        monitor.pathUpdateHandler = { [weak self] path in
            DispatchQueue.main.async {
                self?.isConnected = path.status == .satisfied

                if self?.isConnected == true {
                    Task {
                        await self?.syncOfflineData()
                    }
                }
            }
        }
        monitor.start(queue: queue)
    }

    func syncOfflineData() async {
        // Sync queued messages
        await MessageQueue.shared.syncWhenOnline()

        // Sync quota status
        await QuotaService.shared.refreshQuota()
    }
}
```

---

## Background Audio

### Configuration (Info.plist)

```xml
<key>UIBackgroundModes</key>
<array>
    <string>audio</string>
    <string>voip</string> <!-- Optional: For WebSocket keep-alive -->
</array>

<key>NSMicrophoneUsageDescription</key>
<string>LiveTranslator needs microphone access to transcribe your speech in real-time.</string>

<key>NSSpeechRecognitionUsageDescription</key>
<string>LiveTranslator uses speech recognition to convert your speech to text.</string>
```

### Background Audio Continuity

```swift
class BackgroundAudioManager {
    func handleAppDidEnterBackground() {
        // Keep audio session active
        try? AVAudioSession.sharedInstance().setActive(true)

        // Start background task (up to 30 seconds for cleanup)
        var backgroundTaskID: UIBackgroundTaskIdentifier = .invalid
        backgroundTaskID = UIApplication.shared.beginBackgroundTask {
            UIApplication.shared.endBackgroundTask(backgroundTaskID)
        }

        // WebSocket stays connected for ~30 minutes in background
        // iOS automatically suspends after 30 min unless audio is active
    }

    func configureRemoteTransportControls() {
        let commandCenter = MPRemoteCommandCenter.shared()

        commandCenter.playCommand.addTarget { [weak self] event in
            self?.resumeAudio()
            return .success
        }

        commandCenter.pauseCommand.addTarget { [weak self] event in
            self?.pauseAudio()
            return .success
        }
    }

    func updateNowPlaying(roomName: String, speakerName: String) {
        var nowPlayingInfo = [String: Any]()
        nowPlayingInfo[MPMediaItemPropertyTitle] = "LiveTranslator: \(roomName)"
        nowPlayingInfo[MPMediaItemPropertyArtist] = "Speaking: \(speakerName)"
        nowPlayingInfo[MPNowPlayingInfoPropertyIsLiveStream] = true

        MPNowPlayingInfoCenter.default().nowPlayingInfo = nowPlayingInfo
    }
}
```

---

## Apple Review Compliance

### Critical: In-App Purchase Rules

**Apple Guidelines 3.1.1 - In-App Purchase:**
- All digital goods/services MUST use Apple IAP (subscriptions, credits)
- Cannot link to external payment pages from iOS app
- Cannot mention "cheaper on web" or price comparisons
- Cannot ask users to "sign up on web to save money"

**Compliant UI:**
```swift
// ✅ ALLOWED
Button("Upgrade to Plus - $29/month") {
    showStoreKitSubscriptionSheet()
}

// ❌ NOT ALLOWED
Button("Sign up on web for a better price") {
    openURL("https://livetranslator.com/subscribe")
}

// ✅ ALLOWED (for existing web subscribers)
Text("Manage your subscription in Settings")
// Opens iOS Settings > [App Name] > Subscriptions (built-in Apple UI)
```

**For Existing Web Subscribers:**
- Do NOT show upgrade/purchase buttons in iOS app
- Show "You're subscribed via Web. Manage in Stripe portal." (with external link icon)
- External link is allowed if it's for managing existing subscription, not purchasing

### App Store Metadata

**App Name:** LiveTranslator
**Subtitle:** Real-time Speech Translation
**Category:** Productivity
**Age Rating:** 4+ (no objectionable content)

**Screenshots (required):**
- 6.5" iPhone 14 Pro Max (required)
- 5.5" iPhone 8 Plus (optional)
- 12.9" iPad Pro (required for iPad support)

**Privacy Labels:**
- Data Collected: Email, audio transcripts, usage data
- Data Not Linked to User: Analytics
- Tracking: None (IDFA not used)

---

## StoreKit 2 Integration

### Testing (Sandbox)

**Setup:**
1. Create sandbox Apple ID in App Store Connect
2. Sign in to device: Settings > App Store > Sandbox Account
3. Test purchases use sandbox environment (no real charges)

**StoreKit Configuration File (.storekit):**
```json
{
  "identifier" : "livetranslator",
  "products" : [
    {
      "id" : "com.livetranslator.plus.monthly",
      "type" : "auto-renewable",
      "displayName" : "Plus Monthly",
      "price" : 29.00,
      "subscriptionGroupID" : "group1",
      "renewalPeriod" : "P1M"
    },
    {
      "id" : "com.livetranslator.credits.4hr",
      "type" : "consumable",
      "displayName" : "4 Hours Extra",
      "price" : 19.00
    }
  ]
}
```

### Production Checklist

- [ ] Products configured in App Store Connect
- [ ] Paid Applications Agreement signed
- [ ] Bank details + tax forms complete
- [ ] Receipt verification endpoint live
- [ ] Server-to-server notification URL configured
- [ ] Shared secret generated (for receipt validation)

---

## Push Notifications

### Setup (APNs)

**Capabilities:** Enable Push Notifications in Xcode

**Request Permission:**
```swift
import UserNotifications

func requestPushPermission() async throws {
    let center = UNUserNotificationCenter.current()
    let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])

    if granted {
        await UIApplication.shared.registerForRemoteNotifications()
    }
}

func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
    let token = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
    print("APNs token: \(token)")

    // Send to backend
    Task {
        try await apiClient.post("/api/users/apns-token", body: ["token": token])
    }
}
```

### Notification Types

**1. Quota Alert (80% used):**
```json
{
  "aps": {
    "alert": {
      "title": "Quota Warning",
      "body": "You've used 80% of your quota. 24 minutes remaining."
    },
    "sound": "default",
    "badge": 1
  },
  "type": "quota_alert",
  "remaining_seconds": 1440
}
```

**2. Payment Confirmation:**
```json
{
  "aps": {
    "alert": {
      "title": "Plus Tier Activated",
      "body": "Your subscription is now active. Enjoy 2 hours per month!"
    },
    "sound": "default"
  },
  "type": "subscription_activated",
  "tier": "plus"
}
```

### Handling Notifications

```swift
func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse) async {
    let userInfo = response.notification.request.content.userInfo

    guard let type = userInfo["type"] as? String else { return }

    switch type {
    case "quota_alert":
        // Open quota dashboard
        await navigateTo(.quotaDashboard)

    case "subscription_activated":
        // Refresh user subscription
        await QuotaService.shared.refreshQuota()

    default:
        break
    }
}
```

---

## Network & WebSocket

### WebSocket Connection (Starscream)

**Dependency:** `Starscream` (via Swift Package Manager)

```swift
import Starscream

class WebSocketService: ObservableObject, WebSocketDelegate {
    @Published var isConnected = false
    private var socket: WebSocket?
    private let jwtToken: String

    init(jwtToken: String) {
        self.jwtToken = jwtToken
    }

    func connect(roomCode: String) {
        var request = URLRequest(url: URL(string: "wss://livetranslator.../ws/\(roomCode)")!)
        request.setValue("Bearer \(jwtToken)", forHTTPHeaderField: "Authorization")

        socket = WebSocket(request: request)
        socket?.delegate = self
        socket?.connect()
    }

    func sendTranscript(text: String, isFinal: Bool) {
        let message: [String: Any] = [
            "type": "transcript_direct",
            "text": text,
            "is_final": isFinal,
            "timestamp": ISO8601DateFormatter().string(from: Date())
        ]

        if let data = try? JSONSerialization.data(withJSONObject: message) {
            socket?.write(data: data)
        }
    }

    // MARK: - WebSocketDelegate

    func didReceive(event: WebSocketEvent, client: WebSocket) {
        switch event {
        case .connected:
            isConnected = true

        case .disconnected(let reason, let code):
            isConnected = false
            print("WebSocket disconnected: \(reason) (code: \(code))")

            // Auto-reconnect after 5 seconds
            DispatchQueue.global().asyncAfter(deadline: .now() + 5) {
                self.socket?.connect()
            }

        case .text(let string):
            handleMessage(string)

        case .error(let error):
            print("WebSocket error: \(String(describing: error))")

        default:
            break
        }
    }

    func handleMessage(_ text: String) {
        guard let data = text.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else {
            return
        }

        switch type {
        case "translation_final":
            // Update UI with translation
            break

        case "quota_alert":
            // Show quota warning
            break

        case "quota_exhausted":
            // Show upgrade modal
            break

        default:
            break
        }
    }
}
```

### Connection Stability

**Auto-Reconnect Logic:**
- Exponential backoff: 1s, 2s, 4s, 8s, 16s (max)
- Reset backoff on successful connection
- Ping/pong every 30 seconds (keep-alive)

**Network Change Handling:**
```swift
func handleNetworkChange(isConnected: Bool) {
    if isConnected {
        // Network available: reconnect WebSocket
        socket?.connect()
    } else {
        // Network lost: gracefully disconnect
        socket?.disconnect()

        // Show offline banner in UI
        showOfflineBanner()
    }
}
```

---

## Performance Targets

### Latency (iOS → Backend → iOS)

| Operation | Target (P50) | Target (P95) | Target (P99) |
|-----------|--------------|--------------|--------------|
| Speech Recognition (Apple STT) | <1s | <2s | <3s |
| Translation (Server-side) | <500ms | <1s | <2s |
| WebSocket Message Delivery | <100ms | <200ms | <500ms |
| StoreKit Purchase Flow | <3s | <5s | <10s |
| Quota Check | <100ms | <200ms | <500ms |

### Memory Usage

| Scenario | Target | Maximum |
|----------|--------|---------|
| Idle (in room) | <50MB | <100MB |
| Active speaking | <80MB | <150MB |
| Background audio | <30MB | <50MB |

### Battery Usage

**Target:** <5% battery per hour of active use

**Optimization:**
- Use on-device STT (no network calls for audio)
- Batch WebSocket messages (avoid constant writes)
- Reduce screen brightness during long sessions
- Pause recognition when user not speaking (VAD)

### Data Usage

**Target:** <1MB per 30-minute conversation

**Breakdown:**
- WebSocket messages (JSON): ~500KB
- API requests (quota, profile): ~100KB
- Translation responses: ~400KB

**Note:** Audio never sent to server (0 MB saved per session)

---

## Development Tools

### Debugging

**1. Xcode Console Logging:**
```swift
#if DEBUG
print("[WebSocket] Message sent: \(message)")
#endif
```

**2. Network Link Conditioner:** Simulate slow network (Settings > Developer)

**3. Instruments:** Profile memory, CPU, network usage

### Testing

**Unit Tests (XCTest):**
```swift
import XCTest

class QuotaServiceTests: XCTestCase {
    func testQuotaDeduction() async throws {
        let service = QuotaService(apiClient: MockAPIClient())

        let remaining = try await service.deductQuota(seconds: 30)
        XCTAssertEqual(remaining, 7170) // 7200 - 30
    }
}
```

**UI Tests (XCUITest):**
```swift
func testPurchaseFlow() throws {
    let app = XCUIApplication()
    app.launch()

    app.buttons["Upgrade to Plus"].tap()

    // Wait for StoreKit sheet
    XCTAssertTrue(app.otherElements["StoreKit"].waitForExistence(timeout: 5))

    // Tap "Subscribe" button (sandbox mode)
    app.buttons["Subscribe"].tap()

    // Verify success
    XCTAssertTrue(app.staticTexts["Plus tier activated!"].waitForExistence(timeout: 10))
}
```

---

## Deployment Checklist

### App Store Connect

- [ ] App ID created (com.livetranslator.ios)
- [ ] Provisioning profiles generated
- [ ] App icon (1024x1024) uploaded
- [ ] Screenshots (all required sizes) uploaded
- [ ] Privacy policy URL provided
- [ ] Support URL provided
- [ ] App review notes (test account credentials)

### Code Signing

- [ ] Distribution certificate valid
- [ ] Push notification entitlement enabled
- [ ] Associated domains configured (livetranslator.pawelgawliczek.cloud)
- [ ] App Groups (for shared data) configured

### TestFlight

- [ ] Internal testing complete (team members)
- [ ] External testing (beta users) complete
- [ ] Crash reports reviewed (Firebase Crashlytics)
- [ ] Feedback addressed

### Production Launch

- [ ] All acceptance tests passing (see acceptance-tests.md)
- [ ] Apple Review approved (typically 24-48 hours)
- [ ] Phased release enabled (gradual rollout over 7 days)
- [ ] Backend production ready (see deployment docs)

---

**End of iOS Technical Specification - Version 1.0**
**All iOS architecture gaps addressed per Business Analyst review 2025-11-03**
