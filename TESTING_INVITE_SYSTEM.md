# Invite System - Live Testing Guide

## Overview
The invite system is now fully functional with JWT-based time-limited invite codes (30-minute expiration), QR code generation, and stateless verification.

## Test Results
All 16 unit tests passed successfully:
- JWT token generation and structure
- Token validation and expiration
- Room code extraction
- Invalid/expired token handling
- Signature verification
- Multiple room support

## Live API Endpoints

### Base URL
```
https://livetranslator.pawelgawliczek.cloud/api/invites
```

### 1. Generate Invite Code
**Endpoint:** `POST /api/invites/generate/{room_code}`

**Example:**
```bash
# Generate invite for "test" room
curl -X POST "https://livetranslator.pawelgawliczek.cloud/api/invites/generate/test"
```

**Response:**
```json
{
  "invite_code": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "invite_url": "https://livetranslator.pawelgawliczek.cloud/join/eyJhbGci...",
  "qr_code": "data:image/png;base64,iVBORw0KGgo...",
  "expires_in_minutes": 30,
  "room_code": "test"
}
```

**Try it now:**
- [Generate invite for "test" room](https://livetranslator.pawelgawliczek.cloud/api/invites/generate/test)
- [Generate invite for "nowy-test" room](https://livetranslator.pawelgawliczek.cloud/api/invites/generate/nowy-test)
- [Generate invite for "testroom" room](https://livetranslator.pawelgawliczek.cloud/api/invites/generate/testroom)

### 2. Validate Invite Code
**Endpoint:** `GET /api/invites/validate/{invite_code}`

**Example:**
```bash
# First generate an invite
INVITE_CODE=$(curl -s -X POST "https://livetranslator.pawelgawliczek.cloud/api/invites/generate/test" | jq -r .invite_code)

# Then validate it
curl "https://livetranslator.pawelgawliczek.cloud/api/invites/validate/$INVITE_CODE"
```

**Response (valid invite):**
```json
{
  "valid": true,
  "room_code": "test",
  "room_id": 4,
  "is_public": false,
  "requires_login": false,
  "max_participants": 10
}
```

**Response (expired/invalid invite):**
```json
{
  "valid": false,
  "room_code": null,
  "room_id": null,
  "is_public": null,
  "requires_login": null,
  "max_participants": null
}
```

### 3. Extract Room Code
**Endpoint:** `GET /api/invites/room/{invite_code}/code`

**Example:**
```bash
curl "https://livetranslator.pawelgawliczek.cloud/api/invites/room/eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.../code"
```

**Response:**
```json
{
  "room_code": "test"
}
```

## Testing Workflow

### Step 1: Generate an Invite
Open this URL in your browser (replace `test` with any existing room code):
```
https://livetranslator.pawelgawliczek.cloud/api/invites/generate/test
```

You'll receive:
- `invite_code`: JWT token (copy this)
- `invite_url`: Full URL for joining (not implemented in frontend yet)
- `qr_code`: Base64-encoded PNG QR code

### Step 2: Validate the Invite
Take the `invite_code` from Step 1 and validate it:
```
https://livetranslator.pawelgawliczek.cloud/api/invites/validate/{PASTE_INVITE_CODE_HERE}
```

### Step 3: View QR Code
Copy the `qr_code` value (starts with `data:image/png;base64,...`) and paste it into an HTML img tag:
```html
<img src="data:image/png;base64,iVBORw0KGgo..." alt="QR Code" />
```

Or save it to a file and open in browser.

## Available Rooms for Testing
These rooms currently exist in the database:
- `test` (room_id: 4)
- `testroom` (room_id: 5)
- `nowy-pokoj` (room_id: 6)
- `nowy-test` (room_id: 7)
- `rt1` (room_id: 3)

## Testing Expiration

### Generate and Wait
```bash
# Generate invite
echo "Generated at: $(date)"
curl -X POST "https://livetranslator.pawelgawliczek.cloud/api/invites/generate/test" | jq .

# Wait 31 minutes
sleep 1860

# Try to validate (should fail)
echo "Validating at: $(date)"
curl "https://livetranslator.pawelgawliczek.cloud/api/invites/validate/{invite_code}"
```

## Next Steps (Frontend Integration)

### Phase 1.2: Display Invite UI
Create a component in the frontend to:
1. Request invite code from API
2. Display QR code image
3. Show shareable invite URL
4. Display countdown timer (30 minutes)

### Phase 1.3: Join via Invite
Create `/join/:inviteCode` route that:
1. Validates invite code
2. Prompts for display name and language
3. Joins room as participant
4. Starts translation session

## Security Notes

- Invite codes are **NOT** stored in the database (stateless JWT)
- Each code is valid for exactly **30 minutes**
- Codes are signed with `JWT_SECRET` to prevent tampering
- Expired codes cannot be validated
- Invalid signatures are rejected

## Technical Details

### JWT Payload Structure
```json
{
  "room_code": "test",
  "iat": 1761028413,    // Issued at timestamp
  "exp": 1761030213,    // Expires at timestamp (iat + 1800 seconds)
  "type": "invite"      // Token type (must be "invite")
}
```

### Time Handling
- Uses `time.time()` for timestamp generation (UTC-aware)
- PyJWT uses `time.time()` for validation (consistent)
- Expiration is checked automatically by PyJWT during decode

### QR Code Format
- PNG format, Base64-encoded
- Data URI scheme: `data:image/png;base64,...`
- Contains full invite URL
- Can be directly embedded in HTML `<img>` tags
- Size: 300x300 pixels (configurable)

## Troubleshooting

### "Room not found" Error
Make sure the room exists in the database. List available rooms:
```bash
docker compose exec postgres psql -U lt_user -d livetranslator -c "SELECT code FROM rooms;"
```

### "Invalid or expired" Error
- Check that invite was generated within last 30 minutes
- Verify invite code wasn't modified
- Ensure JWT_SECRET matches between generation and validation

### QR Code Not Displaying
- Verify the `qr_code` value starts with `data:image/png;base64,`
- Check that the entire base64 string was copied
- Try opening in a dedicated base64 decoder tool
