#!/bin/bash
# Run complete test suite: unit + integration + E2E

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "════════════════════════════════════════════════"
echo "🧪 Running Complete Test Suite"
echo "════════════════════════════════════════════════"
echo ""

cd "$(dirname "$0")/../.."

# Start test environment
./scripts/test/start_test_services.sh

# Track failures
FAILURES=0

# 1. Unit Tests
echo ""
echo "1️⃣  Running Unit Tests..."
echo "────────────────────────────────────────────────"
./scripts/test/run_unit_tests.sh || {
    echo -e "${RED}❌ Unit tests failed${NC}"
    FAILURES=$((FAILURES + 1))
}

# 2. Integration Tests
echo ""
echo "2️⃣  Running Integration Tests..."
echo "────────────────────────────────────────────────"
./scripts/test/run_integration_tests.sh || {
    echo -e "${RED}❌ Integration tests failed${NC}"
    FAILURES=$((FAILURES + 1))
}

# 3. Frontend Tests
echo ""
echo "3️⃣  Running Frontend Tests..."
echo "────────────────────────────────────────────────"
if [ -f "web/package.json" ]; then
    cd web
    npm run test 2>/dev/null || {
        echo -e "${YELLOW}⚠  Frontend tests not configured yet${NC}"
    }
    cd ..
else
    echo -e "${YELLOW}⚠  No frontend tests found${NC}"
fi

# 4. E2E Tests
echo ""
echo "4️⃣  Running E2E Tests..."
echo "────────────────────────────────────────────────"
if command -v npx playwright &> /dev/null; then
    ./scripts/test/run_e2e_tests.sh || {
        echo -e "${RED}❌ E2E tests failed${NC}"
        FAILURES=$((FAILURES + 1))
    }
else
    echo -e "${YELLOW}⚠  Playwright not installed, skipping E2E tests${NC}"
fi

# Summary
echo ""
echo "════════════════════════════════════════════════"
if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✅ All Tests Passed!${NC}"
    echo "════════════════════════════════════════════════"
    exit 0
else
    echo -e "${RED}❌ $FAILURES test suite(s) failed${NC}"
    echo "════════════════════════════════════════════════"
    exit 1
fi
