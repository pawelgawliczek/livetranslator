# API Structure Analysis & Recommendations

## 📊 Current State Analysis

### Router Prefix Inconsistencies

The API currently has **inconsistent URL patterns** across different routers:

| Router File | Prefix | Example Endpoints | Issue |
|------------|--------|-------------------|-------|
| `rooms_api.py` | **NONE** | `/rooms`<br>`/rooms/{room_code}`<br>**BUT ALSO:**<br>`/api/rooms/{room_code}/participants`<br>`/api/rooms/{room_code}/recording`<br>`/api/rooms/{room_code}/public`<br>`/api/rooms/{room_code}/status` | **MIXED** - Some with `/api/` prefix, some without |
| `history_api.py` | `/history` | `/history/rooms`<br>`/history/room/{room_code}` | No `/api/` prefix |
| `costs_api.py` | `/costs` | `/costs/room/{room_code}` | No `/api/` prefix |
| `billing_api.py` | `/api/billing` | `/api/billing/...` | Has `/api/` prefix ✓ |
| `profile_api.py` | `/api/profile` | `/api/profile/...` | Has `/api/` prefix ✓ |
| `subscription_api.py` | `/api/subscription` | `/api/subscription/...` | Has `/api/` prefix ✓ |
| `guest_api.py` | `/api/guest` | `/api/guest/...` | Has `/api/` prefix ✓ |
| `invites_api.py` | `/api/invites` | `/api/invites/...` | Has `/api/` prefix ✓ |
| `user_history_api.py` | `/api/user/history` | `/api/user/history/...` | Has `/api/` prefix ✓ |

### The Major Issue: `rooms_api.py`

The `rooms_api.py` file has **BOTH** patterns:

```python
# NO prefix in router definition
router = APIRouter(tags=["rooms"])

# Some endpoints WITHOUT /api/ prefix
@router.post("/rooms", ...)          # → /rooms
@router.get("/rooms/{room_code}", ...)  # → /rooms/{room_code}

# Other endpoints WITH /api/ prefix (hardcoded in decorator)
@router.get("/api/rooms/{room_code}/participants", ...)  # → /api/rooms/{room_code}/participants
@router.patch("/api/rooms/{room_code}/recording", ...)   # → /api/rooms/{room_code}/recording
@router.patch("/api/rooms/{room_code}/public", ...)      # → /api/rooms/{room_code}/public
@router.get("/api/rooms/{room_code}/status", ...)        # → /api/rooms/{room_code}/status
```

This creates confusion:
- Frontend developers don't know which pattern to use
- API documentation becomes unclear
- Harder to maintain and debug

---

## 🎯 Recommended Solutions

### Option 1: **Standardize ALL endpoints with `/api/` prefix** (RECOMMENDED)

Move all routers to use `/api/` prefix for consistency.

**Pros:**
- Clear separation between API endpoints and other routes (auth, websocket, health)
- Industry standard pattern
- Easier to apply middleware/rate limiting to all API routes
- Better for API versioning in the future

**Changes needed:**

1. **Update router definitions:**

```python
# rooms_api.py
router = APIRouter(prefix="/api/rooms", tags=["rooms"])

# history_api.py
router = APIRouter(prefix="/api/history", tags=["history"])

# costs_api.py
router = APIRouter(prefix="/api/costs", tags=["costs"])
```

2. **Remove hardcoded `/api/` from endpoint decorators in rooms_api.py:**

```python
# Before
@router.get("/api/rooms/{room_code}/participants", ...)

# After
@router.get("/{room_code}/participants", ...)
```

3. **Update frontend to use new paths:**

```javascript
// Before
fetch(`/rooms/${roomId}`)              // Inconsistent
fetch(`/history/rooms`)                 // Inconsistent
fetch(`/api/rooms/${roomId}/status`)   // Inconsistent

// After (all consistent)
fetch(`/api/rooms/${roomId}`)
fetch(`/api/history/rooms`)
fetch(`/api/rooms/${roomId}/status`)
```

---

### Option 2: **Keep legacy patterns** (NOT recommended)

Keep `/history`, `/costs`, `/rooms` without prefix for backward compatibility.

**Pros:**
- No breaking changes

**Cons:**
- Continues the inconsistency
- Harder for new developers to understand
- Difficult to version or apply middleware selectively

---

## 📁 Recommended File Organization

Current structure is relatively good, but could be improved:

### Current Structure:
```
api/
├── auth.py              # Auth endpoints
├── rooms_api.py         # Room management
├── history_api.py       # Room history
├── costs_api.py         # Cost tracking
├── billing_api.py       # Billing management
├── profile_api.py       # User profile
├── subscription_api.py  # User subscriptions
├── guest_api.py         # Guest access
├── invites_api.py       # Room invites
├── user_history_api.py  # User history (different from room history?)
├── routers/
│   ├── mt/router.py     # Machine translation
│   └── stt/router.py    # Speech-to-text
├── services/
│   ├── cost_tracker_service.py
│   ├── persistence_service.py
│   └── room_cleanup_service.py
└── utils/
    ├── invite_code.py
    └── qr_code.py
```

### Questions to Consider:

1. **Why is `user_history_api.py` separate from `history_api.py`?**
   - Consider merging or clarifying the distinction
   - `history_api` = room conversation history
   - `user_history_api` = user's usage/activity history?

2. **Why are MT/STT routers in `routers/` subfolder but others in root?**
   - Consider moving ALL routers to `routers/` for consistency
   - OR keep all in root and move MT/STT to root too

### Recommended Structure:

```
api/
├── main.py
├── models.py
├── db.py
├── settings.py
├── routers/              # All API route handlers
│   ├── auth.py
│   ├── rooms.py          # Rename from rooms_api.py
│   ├── history.py        # Rename from history_api.py
│   ├── costs.py          # Rename from costs_api.py
│   ├── billing.py        # Rename from billing_api.py
│   ├── profile.py        # Rename from profile_api.py
│   ├── subscriptions.py  # Rename from subscription_api.py
│   ├── guests.py         # Rename from guest_api.py
│   ├── invites.py        # Rename from invites_api.py
│   ├── mt.py             # Move from routers/mt/router.py
│   └── stt.py            # Move from routers/stt/router.py
├── services/             # Business logic
│   ├── cost_tracker.py
│   ├── persistence.py
│   └── room_cleanup.py
├── utils/                # Helper utilities
│   ├── invite_code.py
│   ├── qr_code.py
│   └── jwt_tools.py      # Move from root
└── tests/
```

---

## 🔧 Implementation Plan

### Phase 1: Fix Immediate Inconsistencies (PRIORITY)

1. **Standardize `rooms_api.py`:**
   - Add `prefix="/api/rooms"` to router
   - Remove `/api/` from endpoint decorators
   - Update frontend calls

2. **Add prefixes to other routers:**
   - `history_api.py` → `prefix="/api/history"`
   - `costs_api.py` → `prefix="/api/costs"`

3. **Update documentation**

**Estimated time:** 2-4 hours
**Risk:** Low (if properly tested)

### Phase 2: Reorganize File Structure (OPTIONAL)

1. Create `routers/` directory
2. Move and rename all `*_api.py` files
3. Update imports in `main.py`
4. Update test files

**Estimated time:** 4-6 hours
**Risk:** Medium (requires careful refactoring)

---

## 📋 Action Items

- [ ] **Decision:** Choose Option 1 or Option 2 for URL patterns
- [ ] **Fix rooms_api.py** - Remove mixed `/api/` usage
- [ ] **Standardize all routers** - Add `/api/` prefix consistently
- [ ] **Update frontend** - Change all API calls to match new structure
- [ ] **Update DOCUMENTATION.md** - Reflect new API structure
- [ ] **Optional:** Reorganize file structure under `routers/`
- [ ] **Test:** Ensure all endpoints work after changes
- [ ] **Deploy:** Update production with backward compatibility if needed

---

## 💡 Additional Recommendations

1. **API Versioning:** Consider adding `/api/v1/` prefix for future versioning
2. **OpenAPI/Swagger:** FastAPI auto-generates this - ensure it's accessible at `/docs`
3. **Rate Limiting:** Easier to apply with consistent `/api/*` prefix
4. **Monitoring:** Consistent paths make logging and metrics clearer
5. **CORS:** Simplified with consistent API paths

---

## 📝 Notes

- Current inconsistency likely evolved organically as features were added
- No breaking changes to database or core logic required
- Frontend changes are straightforward (find/replace in fetch calls)
- Can be done incrementally without downtime if using blue-green deployment
