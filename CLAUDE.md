# CLAUDE.md

Guidance for Claude Code when working with this repository.

## 💬 Communication Style

**CRITICAL: Be concise to save tokens!**

- ✅ Direct, brief responses (skip pleasantries)
- ✅ Use bullets, tables, code blocks
- ✅ One sentence when one is enough
- ✅ Skip verbose explanations
- ❌ No "Let me help you with that..."
- ❌ No repetition or restating questions
- ❌ No excessive context recap

**Example**:
```
Bad:  "I'll help you fix this issue. Let me analyze the code and identify
       the problem. After careful review, I found that..."
Good: "Bug in api/main.py:42 - missing await. Fixed."
```

## Default Agent

Use **Project Manager** (`.claude/agents/project-manager.md`) for all requests. PM delegates to specialists.

**Optimization**: PM uses **Explore agent** for context gathering (medium+ tasks) before creating TEMP_context.md. Token savings: ~60%.

## 📄 Documentation Policy

**CRITICAL: Minimal documentation only!**

**Allowed**: `.claude/DOCUMENTATION.md` + `.claude/test-strategy.md`
**Prohibited**: ❌ PHASE_*.md ❌ *_SUMMARY.md ❌ *_REPORT.md ❌ Tracking files

**Guidelines**: Update core docs at completion only + Delete temp files + Focus on "what changed?" not "how we built it?"

## Quick Commands

```bash
# Services
docker compose up -d
docker compose logs -f <service>

# Rebuild (ALWAYS --no-cache for web!)
docker compose build api
docker compose build --no-cache web
docker compose restart api web

# Tests
docker compose exec api pytest api/tests/ -v
cd web && npm test

# Git hooks
TEST_LEVEL=fast git commit  # Unit (~10s)
git commit                   # Unit + Integration (~30s, default)
TEST_LEVEL=full git commit   # All tests (~2-3min)

# Database
PGPASSWORD=${POSTGRES_PASSWORD} docker compose exec -T postgres psql -U lt_user -d livetranslator

# Redis debug
docker compose exec redis redis-cli -n 5 SUBSCRIBE stt_events
```

## Test Requirements

- Run tests BEFORE code changes
- TDD: Write tests first (see test-strategy.md)
- Targets: Critical 100%, Unit 95%+, Integration 90%+
- Status: 689 tests, 98.5% passing, ~32s

## Architecture

**Docs**: `.claude/DOCUMENTATION.md` (2200+ lines)

**Flow**: Browser → Caddy → API → Redis Pub/Sub → Workers → PostgreSQL

**Services**: API (FastAPI + WebSocket) + STT Router (5 providers) + MT Router (4 providers) + Persistence + Cost Tracker

**Redis Channels** (db 5): `stt_input`, `stt_events`, `mt_events`, `cost_events`, `presence_events`

## Critical Patterns

1. **Multi-Provider Routing**: Language-based STT, language-pair MT (see DOCUMENTATION.md)
2. **Segment Tracking**: Redis atomic counters prevent ID collisions
3. **Multi-Speaker**: N×(N-1) translation routing (`feature_discovery/01-multi-speaker-diarization.md`)
4. **Translation Caching**: `translations.room_id` = room CODE (not ID!)

## Common Issues

**Docker build hangs**: Verify files exist (`ls -la api/requirements.txt`) before `docker compose build`
**History empty**: Use room CODE not ID in queries
**Redis errors**: All services use `redis://redis:6379/5` (database 5)
**Web cache**: Always `docker compose build --no-cache web`

## Development

**Add API**: Route in `api/main.py` or `api/routers/` + Pydantic models + Tests + Rebuild api
**Add Page**: Component in `web/src/pages/` + Route in `main.jsx` + i18n keys + Tests + Rebuild web (--no-cache)
**DB Migration**: Create `migrations/###_name.sql` + Apply via psql + Update `api/models.py` + Restart services

## Environment

**Required (.env)**:
```
POSTGRES_USER=lt_user
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
POSTGRES_DB=livetranslator
REDIS_URL=redis://redis:6379/5
OPENAI_API_KEY=sk-...
```

**Secrets** (`/opt/stack/secrets/`): `jwt_secret`, `google_oauth_client_id.txt`, `google_oauth_client_secret.txt`

## Performance

**Latency**: STT 1.5-3s, MT 100-1500ms, end-to-end 2-4s
**Multi-speaker**: N×(N-1) translations (2 speakers = 2, 5 speakers = 20)

## Deployment

**Domain**: livetranslator.pawelgawliczek.cloud
**Proxy**: Caddy (auto HTTPS)
**Health**: `/healthz`, `/readyz`, `/metrics`

---

**Full docs**: `.claude/DOCUMENTATION.md` | **Tests**: `.claude/test-strategy.md`
- 3 1 per billing
#7 B
#1 80% everytime this level is crossed. if user had 60% and then he crossed 80% then trigger. if then package is bought and user will again cross 80% then trigger it again