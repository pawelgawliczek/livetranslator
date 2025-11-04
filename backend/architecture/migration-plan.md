# LiveTranslator Folder Structure Migration Plan

**Version:** 1.0
**Created:** 2025-11-03
**Status:** Phase 1 Architecture

---

## Table of Contents
1. [Executive Summary](#executive-summary)
2. [Current Structure](#current-structure)
3. [Proposed Structure](#proposed-structure)
4. [Migration Strategy](#migration-strategy)
5. [Impact Analysis](#impact-analysis)
6. [Rollback Plan](#rollback-plan)
7. [Testing Checklist](#testing-checklist)

---

## Executive Summary

**Goal:** Reorganize flat structure into `backend/`, `web/`, `ios/`, `shared/` for better scalability and iOS app integration.

**Timeline:** Week 1-2 (Phase 1)

**Risk Level:** Medium (requires Docker path updates, CI/CD changes)

**Backward Compatibility:** All services continue working, folder move only

---

## Current Structure

```
/opt/stack/livetranslator/
├── api/                          # Backend API + workers
│   ├── __init__.py
│   ├── main.py
│   ├── routers/                  # REST endpoints
│   │   ├── stt/                  # STT router + backends
│   │   ├── mt/                   # MT router + backends
│   │   └── admin_api.py
│   ├── services/
│   │   ├── persistence_service.py
│   │   └── debug_tracker.py
│   ├── tests/                    # Backend tests
│   ├── models.py
│   ├── schemas.py
│   ├── auth.py
│   ├── jwt_tools.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── web/                          # Frontend (React + Vite)
│   ├── src/
│   │   ├── pages/
│   │   ├── components/
│   │   ├── locales/              # i18n translations
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   ├── Dockerfile
│   └── nginx.conf
│
├── migrations/                   # SQL migrations
│   ├── 001_add_invite_system.sql
│   ├── 002_add_subscription_billing.sql
│   └── ...
│
├── data/                         # Docker volumes
│   ├── pg/                       # PostgreSQL data
│   └── redis/                    # Redis data
│
├── .claude/                      # Documentation
│   ├── DOCUMENTATION.md
│   ├── test-strategy.md
│   └── agents/
│
├── docker-compose.yml            # Docker services
├── Caddyfile                     # Reverse proxy config
├── .env
├── .gitignore
└── README.md
```

**Issues with Current Structure:**
1. `api/` name too generic (not clear it's backend)
2. `migrations/` at root (should be with backend)
3. No place for `ios/` app
4. No `shared/` for API contracts (TypeScript + Swift)
5. Flat structure harder to navigate with 4+ platforms

---

## Proposed Structure

```
/opt/stack/livetranslator/
├── backend/                      # NEW: All backend code
│   ├── api/                      # FastAPI app (moved from root)
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── routers/
│   │   │   ├── stt/
│   │   │   ├── mt/
│   │   │   └── admin_api.py
│   │   ├── services/
│   │   ├── tests/
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── requirements.txt
│   │   └── Dockerfile
│   │
│   ├── migrations/               # SQL migrations (moved from root)
│   │   ├── 001_add_invite_system.sql
│   │   ├── ...
│   │   └── 016_add_tier_system.sql
│   │
│   ├── scripts/                  # NEW: Backend utilities
│   │   ├── reset_monthly_quotas.py
│   │   ├── refresh_admin_views.py
│   │   └── seed_data.py
│   │
│   └── architecture/             # NEW: Architecture docs
│       ├── database-schema.sql
│       ├── api-specs.md
│       ├── system-diagrams.md
│       └── migration-plan.md (this file)
│
├── web/                          # Frontend (unchanged)
│   ├── src/
│   ├── package.json
│   ├── Dockerfile
│   └── nginx.conf
│
├── ios/                          # NEW: iOS native app
│   ├── LiveTranslator/
│   │   ├── App/
│   │   ├── Views/
│   │   ├── ViewModels/
│   │   ├── Services/
│   │   ├── Models/
│   │   └── Resources/
│   ├── LiveTranslatorTests/
│   ├── LiveTranslatorUITests/
│   └── LiveTranslator.xcodeproj
│
├── shared/                       # NEW: Shared types + contracts
│   ├── types/
│   │   ├── api-contracts.ts      # TypeScript types (Web)
│   │   ├── websocket.ts
│   │   └── models.swift          # Swift models (iOS)
│   └── docs/
│       └── openapi.yaml          # OpenAPI spec
│
├── infrastructure/               # NEW: Deployment configs
│   ├── docker-compose.yml        # Moved from root
│   ├── Caddyfile                 # Moved from root
│   └── monitoring/
│       ├── grafana/
│       └── prometheus/
│
├── data/                         # Docker volumes (unchanged)
│   ├── pg/
│   └── redis/
│
├── .claude/                      # Documentation (unchanged)
│   ├── DOCUMENTATION.md
│   ├── test-strategy.md
│   └── agents/
│
├── .env                          # Environment variables (unchanged)
├── .gitignore                    # Updated with new paths
└── README.md                     # Updated with new structure
```

**Benefits:**
1. Clear separation: `backend/`, `web/`, `ios/`, `shared/`
2. Backend self-contained: `api/`, `migrations/`, `scripts/`, `architecture/`
3. iOS app has dedicated space
4. Shared types prevent API drift
5. Infrastructure isolated for DevOps
6. Scalable: Future `android/`, `desktop/` easy to add

---

## Migration Strategy

### Phase 1: Preparation (Day 1)

**Step 1.1: Create new directories**
```bash
cd /opt/stack/livetranslator

# Create new structure
mkdir -p backend/api
mkdir -p backend/migrations
mkdir -p backend/scripts
mkdir -p backend/architecture
mkdir -p ios
mkdir -p shared/types
mkdir -p shared/docs
mkdir -p infrastructure
```

**Step 1.2: Copy files (don't move yet, keep backup)**
```bash
# Copy API code
cp -r api/* backend/api/

# Copy migrations
cp -r migrations/* backend/migrations/

# Copy infrastructure configs
cp docker-compose.yml infrastructure/
cp Caddyfile infrastructure/

# web/ stays as-is (already correct)
```

**Step 1.3: Update Docker Compose paths**
```yaml
# infrastructure/docker-compose.yml

services:
  api:
    build:
      context: ../backend/api        # OLD: ./api
      dockerfile: Dockerfile
    volumes:
      - ../backend/api:/app           # OLD: ./api:/app
    depends_on:
      - postgres
      - redis

  stt_router:
    build:
      context: ../backend/api        # OLD: ./api
      dockerfile: Dockerfile
    volumes:
      - ../backend/api:/app           # OLD: ./api:/app

  mt_router:
    build:
      context: ../backend/api        # OLD: ./api
      dockerfile: Dockerfile
    volumes:
      - ../backend/api:/app           # OLD: ./api:/app

  persistence:
    build:
      context: ../backend/api        # OLD: ./api
      dockerfile: Dockerfile
    volumes:
      - ../backend/api:/app           # OLD: ./api:/app

  cost_tracker:
    build:
      context: ../backend/api        # OLD: ./api
      dockerfile: Dockerfile
    volumes:
      - ../backend/api:/app           # OLD: ./api:/app

  web:
    build:
      context: ../web                 # OLD: ./web
      dockerfile: Dockerfile
    # No change needed (already relative)

  postgres:
    volumes:
      - ../data/pg:/var/lib/postgresql/data  # OLD: ./data/pg
      - ../backend/migrations:/docker-entrypoint-initdb.d  # OLD: ./migrations

  redis:
    volumes:
      - ../data/redis:/data          # OLD: ./data/redis
```

**Step 1.4: Update .gitignore**
```gitignore
# .gitignore (append new paths)

# Backend
backend/api/__pycache__/
backend/api/.pytest_cache/
backend/api/.coverage
backend/api/htmlcov/

# iOS
ios/LiveTranslator.xcodeproj/xcuserdata/
ios/LiveTranslator.xcodeproj/project.xcworkspace/xcuserdata/
ios/build/
ios/DerivedData/

# Shared (if generated)
shared/types/*.d.ts

# Infrastructure
infrastructure/.env.local
```

**Step 1.5: Update README.md**
```markdown
# LiveTranslator

## Folder Structure
- `backend/` - FastAPI backend + workers
- `web/` - React frontend
- `ios/` - iOS native app
- `shared/` - API contracts (TypeScript + Swift)
- `infrastructure/` - Docker Compose, Caddy

## Running Locally
cd infrastructure
docker compose up -d

## Building
cd infrastructure
docker compose build --no-cache web
docker compose build api
```

---

### Phase 2: Testing (Day 2)

**Step 2.1: Test with new structure**
```bash
cd infrastructure

# Start services
docker compose up -d

# Check logs
docker compose logs -f api
docker compose logs -f web

# Verify endpoints
curl http://localhost:9003/healthz
curl http://localhost:9003/api/tiers

# Run tests
docker compose exec api pytest /app/tests/ -v
```

**Step 2.2: Test migrations**
```bash
# Verify migrations are accessible
docker compose exec postgres ls /docker-entrypoint-initdb.d

# Apply a new migration
cat backend/migrations/016_add_tier_system.sql | \
  docker compose exec -T postgres psql -U lt_user -d livetranslator
```

**Step 2.3: Test volumes**
```bash
# Verify data persists
docker compose down
docker compose up -d
docker compose exec postgres psql -U lt_user -d livetranslator -c "SELECT COUNT(*) FROM users;"
```

---

### Phase 3: Update CI/CD (Day 3)

**Step 3.1: Update GitHub Actions / GitLab CI**
```yaml
# .github/workflows/test.yml

jobs:
  test-backend:
    steps:
      - name: Build API
        run: |
          cd infrastructure
          docker compose build api

      - name: Run Tests
        run: |
          cd infrastructure
          docker compose run api pytest /app/tests/ -v

  test-frontend:
    steps:
      - name: Build Web
        run: |
          cd infrastructure
          docker compose build web

      - name: Run Tests
        run: |
          cd web
          npm test
```

**Step 3.2: Update deployment scripts**
```bash
#!/bin/bash
# deploy.sh

cd /opt/stack/livetranslator/infrastructure

# Pull latest changes
git pull origin main

# Rebuild services
docker compose build --no-cache web
docker compose build api

# Restart services
docker compose up -d

# Run migrations
cat ../backend/migrations/016_add_tier_system.sql | \
  docker compose exec -T postgres psql -U lt_user -d livetranslator

# Check health
curl -f http://localhost:9003/healthz || exit 1
```

---

### Phase 4: Update Documentation (Day 4)

**Step 4.1: Update `.claude/DOCUMENTATION.md`**
```markdown
## Folder Structure

- `backend/` - Backend services
  - `api/` - FastAPI application
  - `migrations/` - SQL migrations
  - `scripts/` - Cron jobs, utilities
  - `architecture/` - Architecture docs

- `web/` - React frontend
- `ios/` - iOS native app (SwiftUI + MVVM)
- `shared/` - API contracts (TypeScript + Swift)
- `infrastructure/` - Docker Compose, Caddy

## Development Commands

# Start services
cd infrastructure && docker compose up -d

# View logs
cd infrastructure && docker compose logs -f api

# Rebuild
cd infrastructure && docker compose build --no-cache web

# Run tests
cd infrastructure && docker compose exec api pytest /app/tests/ -v
```

**Step 4.2: Update CLAUDE.md**
```markdown
# Quick Commands

```bash
# Services (run from infrastructure/)
cd infrastructure
docker compose up -d
docker compose logs -f <service>

# Rebuild
docker compose build api
docker compose build --no-cache web

# Tests
docker compose exec api pytest /app/tests/ -v
cd ../web && npm test

# Database
PGPASSWORD=CHANGE_ME_BEFORE_DEPLOY docker compose exec -T postgres psql -U lt_user -d livetranslator
```
```

---

### Phase 5: Production Deployment (Day 5)

**Step 5.1: Production migration script**
```bash
#!/bin/bash
# migrate_production.sh

set -e  # Exit on error

echo "=== LiveTranslator Folder Structure Migration ==="
echo "This will reorganize the folder structure."
echo "Current structure: api/, migrations/, docker-compose.yml at root"
echo "New structure: backend/, web/, ios/, shared/, infrastructure/"
echo ""
read -p "Continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

cd /opt/stack/livetranslator

# Backup
echo "Creating backup..."
tar -czf ../livetranslator_backup_$(date +%Y%m%d_%H%M%S).tar.gz .

# Stop services
echo "Stopping services..."
docker compose down

# Create new structure
echo "Creating new directories..."
mkdir -p backend/api
mkdir -p backend/migrations
mkdir -p backend/scripts
mkdir -p backend/architecture
mkdir -p shared/types
mkdir -p shared/docs
mkdir -p infrastructure

# Move files
echo "Moving files..."
mv api/* backend/api/
mv migrations/* backend/migrations/
mv docker-compose.yml infrastructure/
mv Caddyfile infrastructure/

# Update docker-compose.yml paths
echo "Updating docker-compose.yml..."
cd infrastructure
sed -i 's|context: \./api|context: ../backend/api|g' docker-compose.yml
sed -i 's|\./api:/app|../backend/api:/app|g' docker-compose.yml
sed -i 's|\./web:|../web:|g' docker-compose.yml
sed -i 's|\./data/pg:|../data/pg:|g' docker-compose.yml
sed -i 's|\./data/redis:|../data/redis:|g' docker-compose.yml
sed -i 's|\./migrations:|../backend/migrations:|g' docker-compose.yml

# Start services
echo "Starting services..."
docker compose up -d

# Check health
echo "Checking health..."
sleep 10
curl -f http://localhost:9003/healthz || (echo "Health check failed!" && exit 1)

# Cleanup old directories (only if everything works)
cd ..
if [ -d "backend/api" ] && [ -f "infrastructure/docker-compose.yml" ]; then
  echo "Migration successful! Cleaning up old directories..."
  rm -rf api/
  rm -rf migrations/
  echo "Old directories removed."
else
  echo "ERROR: New structure not found! Rolling back..."
  tar -xzf ../livetranslator_backup_*.tar.gz
  docker compose up -d
  exit 1
fi

echo "=== Migration Complete ==="
echo "Services are running with new structure."
echo "Verify everything works, then delete backup:"
echo "  rm ../livetranslator_backup_*.tar.gz"
```

**Step 5.2: Run migration on production**
```bash
# SSH to production server
ssh user@livetranslator.pawelgawliczek.cloud

# Run migration script
cd /opt/stack/livetranslator
bash migrate_production.sh

# Verify services
cd infrastructure
docker compose ps
docker compose logs -f api | head -n 50

# Test endpoints
curl https://livetranslator.pawelgawliczek.cloud/healthz
curl https://livetranslator.pawelgawliczek.cloud/api/tiers

# If everything works, delete backup
rm ../livetranslator_backup_*.tar.gz
```

---

## Impact Analysis

### Services Affected

| Service | Path Change | Config Update | Restart Required | Risk |
|---------|------------|---------------|------------------|------|
| API | `./api` → `../backend/api` | docker-compose.yml | Yes | Low |
| Web | `./web` → `../web` | docker-compose.yml | Yes | Low |
| STT Router | `./api` → `../backend/api` | docker-compose.yml | Yes | Low |
| MT Router | `./api` → `../backend/api` | docker-compose.yml | Yes | Low |
| Persistence | `./api` → `../backend/api` | docker-compose.yml | Yes | Low |
| Cost Tracker | `./api` → `../backend/api` | docker-compose.yml | Yes | Low |
| PostgreSQL | `./migrations` → `../backend/migrations` | docker-compose.yml | No | Low |
| Redis | `./data/redis` → `../data/redis` | docker-compose.yml | No | Low |
| Caddy | `./Caddyfile` → `../infrastructure/Caddyfile` | System config | Yes | Low |

### External Dependencies

**Docker Compose:**
- All `build.context` paths updated
- All `volumes` paths updated
- No breaking changes (relative paths)

**CI/CD Pipelines:**
- GitHub Actions: Update `working-directory`
- GitLab CI: Update `script` paths
- Deployment scripts: Update `cd` commands

**Developer Machines:**
- Update local `.env` files
- Run `docker compose down && docker compose up -d` from `infrastructure/`
- Update bookmarks (docs, commands)

**Monitoring:**
- Grafana: No change (metrics endpoints same)
- Prometheus: No change (scrape targets same)
- Log aggregation: No change (container names same)

---

## Rollback Plan

### Automated Rollback

If migration fails, restore from backup:

```bash
# Stop services
cd /opt/stack/livetranslator/infrastructure
docker compose down

# Restore backup
cd /opt/stack/livetranslator
tar -xzf ../livetranslator_backup_20251103_100000.tar.gz

# Start services (old structure)
docker compose up -d

# Verify
curl http://localhost:9003/healthz
```

### Manual Rollback

If automated rollback fails:

1. Stop all containers: `docker compose down`
2. Move files back: `mv backend/api/* api/`
3. Restore old docker-compose.yml (from backup)
4. Start services: `docker compose up -d`

### Rollback Testing

Test rollback procedure on staging before production:

```bash
# Staging server
cd /opt/stack/livetranslator
bash migrate_production.sh  # Run migration

# Simulate failure
docker compose down

# Test rollback
tar -xzf ../livetranslator_backup_*.tar.gz
docker compose up -d

# Verify
curl http://localhost:9003/healthz
```

---

## Testing Checklist

### Pre-Migration Tests

- [ ] Backup created: `tar -czf backup.tar.gz .`
- [ ] All services running: `docker compose ps`
- [ ] Health check passes: `curl /healthz`
- [ ] Database accessible: `psql -U lt_user -d livetranslator`
- [ ] Redis accessible: `redis-cli PING`
- [ ] Frontend loads: `curl http://localhost:9003/`
- [ ] WebSocket connects: Test room creation
- [ ] Migrations up-to-date: Check `schema_migrations` table

### Post-Migration Tests

- [ ] New directories exist: `ls backend/ web/ ios/ shared/ infrastructure/`
- [ ] All services running: `cd infrastructure && docker compose ps`
- [ ] Health check passes: `curl /healthz`
- [ ] Database accessible: `psql` (same command)
- [ ] Redis accessible: `redis-cli PING`
- [ ] Frontend loads: `curl http://localhost:9003/`
- [ ] WebSocket connects: Create room, send message
- [ ] Migrations work: Apply new migration
- [ ] Tests pass: `docker compose exec api pytest /app/tests/ -v`
- [ ] Logs clean: `docker compose logs api | grep ERROR` (none)
- [ ] Old directories removed: `ls api/` (not found)

### Smoke Tests (Critical Paths)

1. **Authentication:**
   - [ ] Signup: `POST /auth/signup`
   - [ ] Login: `POST /auth/login`
   - [ ] Google OAuth: `GET /auth/google/login`

2. **Rooms:**
   - [ ] Create room: `POST /api/rooms`
   - [ ] Get room: `GET /api/rooms/{code}`
   - [ ] Join via WebSocket: `ws://localhost:9003/ws/rooms/{code}`

3. **Transcription:**
   - [ ] Send audio: `audio_chunk` WebSocket message
   - [ ] Receive transcript: `stt_final` WebSocket message
   - [ ] Receive translation: `translation_final` WebSocket message

4. **Subscriptions (New):**
   - [ ] Get tiers: `GET /api/tiers`
   - [ ] Get user subscription: `GET /api/users/{id}/subscription`
   - [ ] Get quota: `GET /api/users/{id}/quota`

5. **Admin Dashboard (New):**
   - [ ] Financial summary: `GET /api/admin/financial/summary`
   - [ ] Tier analysis: `GET /api/admin/financial/tier-analysis`

---

## Timeline Summary

| Phase | Duration | Owner | Status |
|-------|----------|-------|--------|
| Preparation | Day 1 | DevOps | ⏳ Pending |
| Testing | Day 2 | QA + DevOps | ⏳ Pending |
| CI/CD Update | Day 3 | DevOps | ⏳ Pending |
| Documentation | Day 4 | Technical Writer | ⏳ Pending |
| Production Deployment | Day 5 | DevOps | ⏳ Pending |

**Total:** 5 days (1 week)

---

## Risk Mitigation

**Risk 1: Docker paths incorrect → Services fail to start**
- **Mitigation:** Test on staging first, keep backup
- **Detection:** Health check fails
- **Resolution:** Rollback from backup (5 minutes)

**Risk 2: CI/CD pipeline breaks → Deployments fail**
- **Mitigation:** Update CI/CD configs in same PR
- **Detection:** Build fails
- **Resolution:** Fix paths in CI/CD config (15 minutes)

**Risk 3: Developer confusion → Lost productivity**
- **Mitigation:** Update docs, send announcement, provide migration guide
- **Detection:** Support tickets
- **Resolution:** Update docs, provide examples (1 hour)

**Risk 4: Data loss (PostgreSQL, Redis)**
- **Mitigation:** Only move code, not data directories
- **Detection:** Empty database
- **Resolution:** Rollback, verify data paths (10 minutes)

---

## Success Criteria

- [ ] All services start successfully from `infrastructure/docker-compose.yml`
- [ ] All tests pass (backend + frontend)
- [ ] No data loss (PostgreSQL + Redis volumes intact)
- [ ] CI/CD pipeline works (GitHub Actions)
- [ ] Documentation updated (README, DOCUMENTATION.md, CLAUDE.md)
- [ ] Developers onboarded (migration guide sent)
- [ ] Production deployment successful (zero downtime)
- [ ] Monitoring dashboards still work (Grafana, Prometheus)

---

**End of Migration Plan**
