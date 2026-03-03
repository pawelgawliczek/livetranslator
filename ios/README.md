# LiveTranslator iOS App

**Feature ID 10: iOS Core Setup (Week 1-2)**  
**Status:** Complete - Ready for build on macOS  
**Platform:** iOS 16.0+  
**Framework:** SwiftUI  

---

## Overview

This is the iOS client for LiveTranslator, a real-time multi-language translation platform. Week 1-2 delivers the core authentication and navigation infrastructure.

## Features Implemented (Week 1-2)

- Email/password authentication (signup/login)
- Google OAuth integration
- JWT token management (secure Keychain storage)
- Profile management (view profile, logout)
- TabView navigation (Home, Profile, Settings)
- Network connectivity monitoring
- Comprehensive unit tests

## Project Structure

```
LiveTranslator/
├── App/
│   ├── LiveTranslatorApp.swift      # App entry point
│   └── ContentView.swift            # Main TabView
├── Views/
│   ├── Auth/
│   │   ├── LoginView.swift
│   │   ├── SignupView.swift
│   │   └── GoogleAuthView.swift
│   ├── Profile/
│   │   ├── ProfileView.swift
│   │   └── ProfileEditView.swift
│   └── Settings/
│       └── SettingsView.swift
├── ViewModels/
│   ├── AuthViewModel.swift
│   └── ProfileViewModel.swift
├── Models/
│   ├── User.swift
│   ├── AuthResponse.swift
│   └── APIError.swift
├── Services/
│   ├── APIClient.swift              # HTTP client
│   ├── AuthService.swift            # Auth business logic
│   ├── KeychainService.swift        # Secure token storage
│   └── NetworkMonitor.swift         # Connectivity monitoring
└── Resources/
    └── Info.plist                   # App configuration
```

## Building the Project

### Prerequisites

- macOS 13.0+ (Ventura or later)
- Xcode 15.0+
- iOS 16.0+ device or simulator

### Steps

1. **Open Xcode:**
   ```bash
   cd /opt/stack/livetranslator/ios/LiveTranslator
   open LiveTranslator.xcodeproj
   ```

2. **Configure Bundle ID:**
   - Select LiveTranslator target
   - General tab → Bundle Identifier: `com.livetranslator.ios`
   - Signing & Capabilities → Select your Team

3. **Build & Run:**
   - Select iPhone simulator or connected device
   - Press `Cmd+R` to build and run
   - Or Product → Run

4. **Run Tests:**
   - Press `Cmd+U` to run unit tests
   - Or Product → Test

### Google OAuth Setup

To enable Google OAuth:

1. **Backend Configuration:**
   - Ensure backend has Google OAuth configured
   - Redirect URI: `https://livetranslator.pawelgawliczek.cloud/auth/google/callback`

2. **iOS URL Scheme:**
   - Already configured in Info.plist
   - URL Scheme: `livetranslator://auth/google/callback`

3. **Test Flow:**
   - Tap "Continue with Google" in LoginView
   - Complete Google authentication in browser
   - App receives JWT token via callback URL

## API Backend

- **Base URL:** `https://livetranslator.pawelgawliczek.cloud`
- **Authentication:** JWT Bearer token
- **Endpoints:**
  - `POST /auth/signup` - Create account
  - `POST /auth/login` - Email/password login
  - `GET /auth/google/login` - Initiate Google OAuth
  - `POST /auth/logout` - Logout (optional)

## Testing

### Unit Tests Included

- **KeychainServiceTests:** Token save/retrieve/delete
- **AuthServiceTests:** Authentication flows
- **APIClientTests:** HTTP request/response handling

### Running Tests

```bash
# Via Xcode
Cmd+U

# Via xcodebuild (command line)
xcodebuild test -scheme LiveTranslator -destination 'platform=iOS Simulator,name=iPhone 15'
```

### Test Coverage

- Target: 80%+ coverage
- Focus areas: Services layer, authentication logic

## Architecture

**Pattern:** MVVM (Model-View-ViewModel)

- **Views:** SwiftUI declarative UI
- **ViewModels:** UI state management (`@ObservableObject`)
- **Services:** Business logic and API communication
- **Models:** Data transfer objects (Codable)

**Key Technologies:**

- SwiftUI for UI
- async/await for concurrency
- Keychain for secure storage
- URLSession for networking
- ASWebAuthenticationSession for OAuth

## Security

- JWT tokens stored in iOS Keychain
- HTTPS enforced (App Transport Security)
- No plaintext credentials storage
- Automatic token injection in API requests
- Token expiry detection and re-authentication

## Coming in Week 3-4

- Essential Mode (Apple Speech & Translation frameworks)
- Room creation & joining
- QR code generation & scanning
- Guest sessions
- Real-time transcription UI

## Troubleshooting

### Build Errors

**"No such module 'LiveTranslator'"**
- Clean build folder: Product → Clean Build Folder (Shift+Cmd+K)
- Rebuild project

**Signing errors**
- Ensure Apple Developer account configured in Xcode
- Select appropriate Team in Signing & Capabilities

### Runtime Errors

**"App crashes on launch"**
- Check Console for error messages
- Verify backend API is accessible
- Check network connectivity

**"Google OAuth fails"**
- Verify redirect URI matches backend configuration
- Check Info.plist has correct URL scheme
- Ensure Google OAuth client ID/secret configured on backend

### Testing Errors

**"Keychain tests fail"**
- Tests should clean up after themselves
- If persistent failures, manually clear Keychain:
  - iOS Simulator → Device → Erase All Content and Settings

## Documentation

- **Requirements:** `/opt/stack/livetranslator/TEMP_requirements.md`
- **Architecture Design:** `/opt/stack/livetranslator/TEMP_design.md`
- **Backend API Docs:** `.claude/DOCUMENTATION.md`

## Contact

**Project:** LiveTranslator  
**Phase:** iOS Core Setup (Week 1-2)  
**Feature ID:** 10  
**Status:** Ready for macOS build  

---

**Next Steps:**

1. Build project on macOS with Xcode
2. Test authentication flows
3. Verify unit tests pass
4. Proceed to Week 3-4: Essential Mode Integration
