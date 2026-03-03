# iOS App Quick Start Guide

## 1. Open Project in Xcode

```bash
cd /opt/stack/livetranslator/ios/LiveTranslator
open LiveTranslator.xcodeproj
```

**Note:** You'll need to create the `.xcodeproj` file on macOS. Follow steps below.

---

## 2. Create Xcode Project (First Time Only)

Since we're on Linux, you'll need to create the Xcode project on macOS:

### Option A: Manual Setup (Recommended)

1. **Open Xcode on macOS**
2. **Create New Project:**
   - File → New → Project
   - iOS → App
   - Click Next
3. **Configure Project:**
   - Product Name: `LiveTranslator`
   - Team: Select your Apple Developer team
   - Organization Identifier: `com.livetranslator`
   - Bundle Identifier: `com.livetranslator.ios`
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Storage: None
   - Click Next
4. **Save Location:**
   - Select `/opt/stack/livetranslator/ios/LiveTranslator/`
   - Uncheck "Create Git repository" (already exists)
5. **Add Existing Files:**
   - Right-click `LiveTranslator` folder in Project Navigator
   - Add Files to "LiveTranslator"...
   - Select all folders (App, Views, ViewModels, Models, Services, Resources)
   - Check "Copy items if needed"
   - Check "Create groups"
   - Add to target: LiveTranslator
6. **Add Test Files:**
   - Select `LiveTranslatorTests` target
   - Add Files: Select all files in `LiveTranslatorTests/` folder
7. **Configure Info.plist:**
   - Select `LiveTranslator` target
   - Info tab → Custom iOS Target Properties
   - Remove default Info.plist if present
   - Add existing: `Resources/Info.plist`

### Option B: Use Provided Files

All Swift files are already created at:
```
/opt/stack/livetranslator/ios/LiveTranslator/LiveTranslator/
```

Just create the Xcode project and drag files in.

---

## 3. Configure Signing

1. Select `LiveTranslator` target
2. Signing & Capabilities tab
3. Team: Select your Apple Developer account
4. Bundle Identifier: `com.livetranslator.ios` (should auto-populate)

---

## 4. Build & Run

1. Select iPhone simulator (e.g., iPhone 15)
2. Press `Cmd+R` or click ▶️ Play button
3. App should build and launch in simulator

---

## 5. Test Authentication

### Email/Password Signup
1. Launch app → Should show Login screen
2. Tap "Don't have an account? Sign Up"
3. Enter:
   - Email: your-email@example.com
   - Password: password123
   - Display Name: Your Name
4. Tap "Sign Up"
5. Should navigate to Home tab (welcome screen)

### Email/Password Login
1. Force quit app (swipe up in simulator)
2. Relaunch app → Should auto-login (JWT token persists)
3. Or logout and login again

### Google OAuth
1. Tap "Continue with Google"
2. Browser opens with Google consent screen
3. Approve permissions
4. App receives JWT token
5. Navigates to Home tab

**Important:** Backend must have Google OAuth configured for this to work.

---

## 6. Run Unit Tests

1. Press `Cmd+U` or Product → Test
2. Tests should run:
   - KeychainServiceTests (5 tests)
   - AuthServiceTests (4 tests)
   - APIClientTests (4 tests)
3. All tests should pass ✅

---

## 7. Verify Features

**Authentication:**
- [x] Signup with email/password
- [x] Login with email/password
- [x] Google OAuth login
- [x] JWT token persists across launches
- [x] Logout clears token

**Navigation:**
- [x] TabView with 3 tabs (Home, Profile, Settings)
- [x] Profile displays user info
- [x] Settings shows placeholder

**Error Handling:**
- [x] Invalid email format → Error message
- [x] Password too short → Error message
- [x] Network error → Error message
- [x] No internet → Banner displayed

---

## 8. Common Issues

### "No such module 'LiveTranslator'"
- Clean build folder: Shift+Cmd+K
- Rebuild: Cmd+B

### "Keychain tests fail"
- Simulator → Device → Erase All Content and Settings
- Re-run tests

### "Google OAuth fails"
- Check backend Google OAuth configuration
- Verify redirect URI matches
- Check Info.plist URL scheme: `livetranslator`

### "API calls fail"
- Verify backend is running at https://livetranslator.pawelgawliczek.cloud
- Check network connectivity
- Check API logs for errors

---

## 9. Next Steps

After verifying Week 1-2 features work:

1. **Test on real device** (iPhone)
2. **Proceed to Week 3-4:**
   - Essential Mode (Apple Speech & Translation)
   - Room creation & joining
   - QR code scanning
3. **Track issues** in project tracker
4. **Provide feedback** on UX/bugs

---

## 10. Project Structure

```
LiveTranslator/
├── App/                  # Entry point
├── Views/               # SwiftUI views
│   ├── Auth/           # Login, Signup, Google OAuth
│   ├── Profile/        # Profile display/edit
│   └── Settings/       # Settings placeholder
├── ViewModels/          # State management
├── Models/              # Data models
├── Services/            # Business logic
│   ├── APIClient.swift
│   ├── AuthService.swift
│   ├── KeychainService.swift
│   └── NetworkMonitor.swift
└── Resources/
    └── Info.plist      # App configuration
```

---

## Need Help?

- **Architecture:** See `TEMP_design.md`
- **Requirements:** See `TEMP_requirements.md`
- **API Docs:** See `.claude/DOCUMENTATION.md`
- **Full README:** See `README.md`

---

**Status:** Ready to build on macOS! 🚀
