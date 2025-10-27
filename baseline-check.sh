#!/bin/bash
# LiveTranslator Baseline Health Check
# Run from project root: bash baseline-check.sh

set -e

echo "================================================"
echo "LiveTranslator Baseline Health Check"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Check Docker Compose status
echo "1. Checking Docker Compose services..."
if docker compose ps | grep -q "api.*running"; then
    check_pass "API container running"
else
    check_fail "API container not running"
fi

if docker compose ps | grep -q "stt_worker.*running"; then
    check_pass "STT worker running"
else
    check_fail "STT worker not running"
fi

if docker compose ps | grep -q "mt_worker.*running"; then
    check_pass "MT worker running"
else
    check_fail "MT worker not running"
fi

if docker compose ps | grep -q "redis.*running"; then
    check_pass "Redis running"
else
    check_fail "Redis not running"
fi

echo ""

# 2. Check environment variables
echo "2. Checking environment configuration..."
if [ -f .env ]; then
    check_pass ".env file exists"
    
    if grep -q "LT_REDIS_URL" .env; then
        check_pass "LT_REDIS_URL defined"
    else
        check_fail "LT_REDIS_URL missing from .env"
    fi
    
    if grep -q "OPENAI" .env; then
        check_warn "OPENAI variables found (should be removed for baseline)"
    else
        check_pass "No OPENAI variables (baseline clean)"
    fi
else
    check_fail ".env file not found"
fi

echo ""

# 3. Check API health
echo "3. Checking API endpoints..."
if curl -sf http://localhost:9003/healthz > /dev/null 2>&1; then
    check_pass "API /healthz responding"
else
    check_fail "API /healthz not responding"
fi

if curl -sf http://localhost:9003/metrics > /dev/null 2>&1; then
    check_pass "API /metrics responding"
else
    check_fail "API /metrics not responding"
fi

echo ""

# 4. Check Redis connectivity
echo "4. Checking Redis..."
if docker compose exec -T redis redis-cli -n 5 PING 2>/dev/null | grep -q "PONG"; then
    check_pass "Redis DB 5 responding"
else
    check_fail "Redis DB 5 not responding"
fi

# Check subscribers
NUMSUB=$(docker compose exec -T redis redis-cli -n 5 PUBSUB NUMSUB stt_input stt_events mt_events 2>/dev/null || echo "")
if [ -n "$NUMSUB" ]; then
    check_pass "Redis channels queryable"
    echo "   Subscribers: $NUMSUB"
else
    check_warn "Could not query Redis channels"
fi

echo ""

# 5. Check recent errors
echo "5. Checking for recent errors..."
API_ERRORS=$(docker compose logs --tail=50 api 2>/dev/null | grep -i "error" | wc -l)
STT_ERRORS=$(docker compose logs --tail=50 stt_worker 2>/dev/null | grep -i "error" | wc -l)
MT_ERRORS=$(docker compose logs --tail=50 mt_worker 2>/dev/null | grep -i "error" | wc -l)
PG_ERRORS=$(docker compose logs --tail=50 postgres 2>/dev/null | grep -i "error" | wc -l)

if [ "$API_ERRORS" -eq 0 ]; then
    check_pass "No recent API errors"
else
    check_warn "API has $API_ERRORS recent errors"
fi

if [ "$STT_ERRORS" -eq 0 ]; then
    check_pass "No recent STT errors"
else
    check_warn "STT has $STT_ERRORS recent errors"
fi

if [ "$MT_ERRORS" -eq 0 ]; then
    check_pass "No recent MT errors"
else
    check_warn "MT has $MT_ERRORS recent errors"
fi

if [ "$PG_ERRORS" -gt 0 ]; then
    check_warn "Postgres has $PG_ERRORS recent errors (schema issues detected)"
fi

echo ""

# 6. Summary
echo "================================================"
echo "Summary"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Fix PostgreSQL schema if errors present"
echo "2. Test JWT auth: curl -X POST http://localhost:9003/auth/login"
echo "3. Test WebSocket: websocat ws://localhost:9003/ws/rooms/demo?token=TOKEN"
echo "4. Inject test events via Redis"
echo ""
echo "Quick commands:"
echo "  docker compose logs -f api"
echo "  docker compose exec -T redis redis-cli -n 5 PSUBSCRIBE 'stt_*' 'mt_*'"
echo ""
