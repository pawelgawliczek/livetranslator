# Audio Settings Testing Guide

## Overview
This document outlines the comprehensive testing strategy for the audio settings feature, which allows users to configure microphone selection and voice activation threshold.

---

## 1. Automated Backend Tests ✅

**Location:** `api/tests/test_profile_api.py::TestAudioSettings`

### Test Coverage (7 tests - All Passing)

```bash
# Run all audio settings tests
docker compose exec api pytest api/tests/test_profile_api.py::TestAudioSettings -v
```

#### Tests Included:

1. **test_get_profile_includes_audio_settings**
   - Verifies profile response includes audio settings fields
   - Checks default values (threshold=0.02, device_id=null)

2. **test_update_audio_threshold**
   - Tests updating threshold value
   - Verifies persistence across requests

3. **test_update_preferred_mic_device**
   - Tests setting a specific microphone device ID
   - Verifies persistence

4. **test_update_both_audio_settings**
   - Tests updating threshold and device simultaneously
   - Ensures both values persist correctly

5. **test_clear_preferred_mic_device**
   - Tests explicitly clearing device selection (set to null)
   - Verifies user can return to browser default

6. **test_audio_threshold_edge_values**
   - Tests minimum value (0.001)
   - Tests maximum value (0.1)
   - Ensures edge cases work correctly

7. **test_update_audio_settings_with_other_fields**
   - Tests updating audio settings alongside other profile fields
   - Ensures no conflicts between different field updates

---

## 2. Manual Testing Checklist

### A. Backend API Testing

```bash
# Get your auth token first
TOKEN="your_jwt_token_here"

# Test 1: Get profile with audio settings
curl -X GET "http://localhost:9003/api/profile" \
  -H "Authorization: Bearer $TOKEN"

# Expected: Response includes audio_threshold and preferred_mic_device_id

# Test 2: Update threshold
curl -X PATCH "http://localhost:9003/api/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"audio_threshold": 0.05}'

# Expected: Response shows threshold=0.05

# Test 3: Update microphone device
curl -X PATCH "http://localhost:9003/api/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"preferred_mic_device_id": "test_device_123"}'

# Expected: Response shows preferred_mic_device_id="test_device_123"

# Test 4: Clear device (set to null)
curl -X PATCH "http://localhost:9003/api/profile" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"preferred_mic_device_id": null}'

# Expected: Response shows preferred_mic_device_id=null
```

### B. Frontend UI Testing

#### Profile Page Testing

**Location:** Profile → Settings Tab → Audio Settings Section

1. **Visual Elements**
   - [ ] "Audio Settings" heading visible
   - [ ] Microphone dropdown shows all available devices
   - [ ] Threshold slider shows current value as percentage
   - [ ] Slider range labels ("More Sensitive" / "Less Sensitive")
   - [ ] "Save Audio Settings" button present

2. **Microphone Selection**
   - [ ] Dropdown shows "Default Microphone" as first option
   - [ ] Lists all detected microphones with labels
   - [ ] Selected value persists after page reload
   - [ ] Can switch between different devices
   - [ ] Can return to default by selecting "Default Microphone"

3. **Threshold Adjustment**
   - [ ] Slider moves smoothly from 0.1% to 10%
   - [ ] Percentage display updates in real-time
   - [ ] Value persists after page reload
   - [ ] Can set to minimum (0.1%)
   - [ ] Can set to maximum (10%)

4. **Persistence Testing**
   - [ ] Save settings, refresh page → settings retained
   - [ ] Save settings, logout/login → settings retained
   - [ ] Settings apply across all browser tabs
   - [ ] Settings apply in different rooms

#### Room Sound Settings Modal Testing

**Location:** Room → Sound Settings Icon (🎤)

1. **Visual Elements**
   - [ ] Microphone dropdown at top of modal
   - [ ] Current mic selection highlighted
   - [ ] Threshold slider with visual meter
   - [ ] Real-time audio level display
   - [ ] Test microphone button

2. **Device Selection in Modal**
   - [ ] Can change microphone from dropdown
   - [ ] Change auto-saves to profile
   - [ ] Audio stream restarts with new device
   - [ ] Visual meter shows audio from selected device

3. **Threshold Adjustment in Modal**
   - [ ] Slider adjustment auto-saves
   - [ ] Red threshold line updates on visual meter
   - [ ] Changes immediately affect VAD detection
   - [ ] Status indicator reflects new threshold sensitivity

4. **Integration Testing**
   - [ ] Settings changed in modal appear in Profile page
   - [ ] Settings changed in Profile page appear in modal
   - [ ] Both UIs always show same values

### C. Audio Functionality Testing

#### Voice Activation Detection (VAD)

1. **Low Threshold Testing (More Sensitive)**
   - Set threshold to 0.1-1%
   - [ ] Detects quiet speech
   - [ ] Detects whispers
   - [ ] May pick up background noise
   - [ ] Status shows "recording" more frequently

2. **High Threshold Testing (Less Sensitive)**
   - Set threshold to 5-10%
   - [ ] Requires louder speech to activate
   - [ ] Ignores quiet background sounds
   - [ ] Doesn't detect whispers
   - [ ] Status shows "recording" only for clear speech

3. **Multiple Microphones**
   - [ ] Switch between built-in mic and USB mic
   - [ ] Audio levels differ appropriately
   - [ ] Recording quality reflects device capabilities
   - [ ] Can test each device separately

#### Real-World Scenarios

1. **Headset Microphone**
   - [ ] Select headset from dropdown
   - [ ] Adjust threshold for close-mic audio
   - [ ] Verify recordings sound clear
   - [ ] Test with noise cancellation on/off

2. **Built-in Laptop Mic**
   - [ ] Select built-in mic
   - [ ] May need higher threshold
   - [ ] Test from various distances
   - [ ] Verify background noise handling

3. **External USB Microphone**
   - [ ] Detects when plugged in
   - [ ] Appears in device list
   - [ ] Can select and use immediately
   - [ ] Settings persist even when unplugged

### D. Edge Cases & Error Handling

1. **Device Enumeration**
   - [ ] Browser requests microphone permission
   - [ ] Error message if permission denied
   - [ ] Re-prompts if permission changed
   - [ ] Handles no devices available

2. **Device Changes**
   - [ ] Unplug selected device → graceful fallback
   - [ ] Plug in new device → appears in dropdown
   - [ ] Device list updates dynamically
   - [ ] Selected device persists across sessions

3. **Guest Users**
   - [ ] Can change settings in session
   - [ ] Settings don't persist after logout
   - [ ] No errors when saving (localStorage)
   - [ ] Clean state on new session

4. **Network Issues**
   - [ ] Settings save failure shows error
   - [ ] Retries on network recovery
   - [ ] UI remains functional
   - [ ] No data loss on save failure

### E. Cross-Browser Testing

Test on multiple browsers to ensure compatibility:

- [ ] **Chrome/Edge** (Chromium-based)
  - `navigator.mediaDevices.enumerateDevices()` support
  - Device labels with permission
  - Audio constraints work correctly

- [ ] **Firefox**
  - Device enumeration works
  - DeviceId constraints supported
  - Audio levels display correctly

- [ ] **Safari**
  - getUserMedia permission flow
  - Device selection functionality
  - Audio processing performance

### F. Performance Testing

1. **Audio Stream Initialization**
   - [ ] Device selection doesn't cause lag
   - [ ] Stream switches smoothly
   - [ ] No audio glitches during switch

2. **Settings Save Performance**
   - [ ] Save completes quickly (<500ms)
   - [ ] UI doesn't block during save
   - [ ] Multiple rapid changes handled gracefully

3. **Memory & Resource Usage**
   - [ ] No memory leaks with device switching
   - [ ] Audio contexts properly cleaned up
   - [ ] Browser performance remains stable

---

## 3. Integration Testing

### Full User Flow Test

```
1. Login as new user
2. Navigate to Profile → Settings
3. Open Audio Settings section
4. Select a specific microphone
5. Adjust threshold to 3%
6. Click "Save Audio Settings"
7. Navigate to a room
8. Open Sound Settings modal
9. Verify microphone matches selection
10. Verify threshold shows 3%
11. Speak at different volumes
12. Verify VAD triggers at ~3% audio level
13. Refresh the page
14. Verify settings persist
15. Logout and login
16. Verify settings still persist
```

### Multi-Device Flow

```
1. Login on computer with multiple microphones
2. Select USB headset in Profile
3. Join a room
4. Verify headset is active
5. In Sound Settings, switch to built-in mic
6. Verify audio stream switches
7. Verify setting auto-saved to profile
8. Close and reopen browser
9. Join same/different room
10. Verify built-in mic still selected
```

---

## 4. Database Testing

```sql
-- Verify schema
\d users

-- Should show:
-- audio_threshold | double precision | default 0.02
-- preferred_mic_device_id | character varying(255) | nullable

-- Verify data
SELECT id, email, audio_threshold, preferred_mic_device_id
FROM users
LIMIT 10;

-- Test default values for new users
INSERT INTO users (email, password_hash, display_name, preferred_lang)
VALUES ('testuser@example.com', 'hash', 'Test', 'en');

SELECT audio_threshold, preferred_mic_device_id
FROM users
WHERE email='testuser@example.com';

-- Should return: audio_threshold=0.02, preferred_mic_device_id=NULL
```

---

## 5. Regression Testing

Ensure audio settings don't break existing functionality:

- [ ] Users without audio settings can still login
- [ ] OAuth users can set audio settings
- [ ] Profile updates for other fields still work
- [ ] Room functionality unaffected
- [ ] Guest mode still works
- [ ] Push-to-talk mode works with custom threshold
- [ ] Network quality adjustments work
- [ ] Test mode in Sound Settings works

---

## 6. Accessibility Testing

- [ ] Keyboard navigation works for dropdowns
- [ ] Slider accessible via keyboard (arrow keys)
- [ ] Screen readers announce device names
- [ ] Labels properly associated with inputs
- [ ] Focus indicators visible
- [ ] Error messages screen-reader friendly

---

## 7. Security Testing

- [ ] Only authenticated users can set audio settings
- [ ] Cannot set audio settings for other users
- [ ] Invalid device IDs don't cause errors
- [ ] Extreme threshold values handled safely
- [ ] SQL injection attempts fail safely
- [ ] XSS attempts in device names handled

---

## Test Results Summary

### Automated Tests
✅ **7/7 Backend API Tests Passing**

### Manual Test Status
- Backend API: ✅ Ready for testing
- Frontend UI: ✅ Deployed and ready
- Integration: ✅ Ready for testing
- Database: ✅ Schema verified

---

## Quick Test Commands

```bash
# Run all audio settings tests
docker compose exec api pytest api/tests/test_profile_api.py::TestAudioSettings -v

# Run all profile tests
docker compose exec api pytest api/tests/test_profile_api.py -v

# Verify database schema
docker compose exec postgres psql -U lt_user -d livetranslator -c "\d users"

# Check current user settings
docker compose exec postgres psql -U lt_user -d livetranslator \
  -c "SELECT email, audio_threshold, preferred_mic_device_id FROM users;"
```

---

## Reporting Bugs

When reporting audio settings issues, include:

1. **Browser & Version:** Chrome 120, Firefox 121, Safari 17, etc.
2. **Device Info:** Microphone model, connection type (USB, built-in)
3. **Steps to Reproduce:** Detailed steps from login to error
4. **Expected Behavior:** What should happen
5. **Actual Behavior:** What actually happened
6. **Console Errors:** Any JavaScript errors in browser console
7. **Network Tab:** Any failed API requests
8. **Settings Values:** Current threshold and device ID

Example:
```
Browser: Chrome 120 on macOS
Device: Blue Yeti USB Microphone
Steps:
1. Selected Blue Yeti in Profile
2. Set threshold to 0.05
3. Joined room
4. Sound Settings shows "Default" instead of "Blue Yeti"
Expected: Should show "Blue Yeti"
Actual: Shows "Default Microphone"
Console: No errors
Network: PATCH /api/profile returns 200 with correct device_id
```

---

## Conclusion

This comprehensive testing strategy ensures the audio settings feature is:
- **Functional:** All features work as designed
- **Reliable:** Settings persist correctly
- **User-Friendly:** Intuitive UI and error handling
- **Performant:** No lag or resource issues
- **Secure:** Protected against common vulnerabilities
- **Accessible:** Usable by all users

For questions or issues, refer to the main project documentation or open an issue on GitHub.
