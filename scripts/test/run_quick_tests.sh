#!/bin/bash
# Quick tests for pre-commit hook
# Only runs fast unit tests (<30 seconds)

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}⚡ Running Quick Tests (Unit Only)...${NC}"
echo ""

# Change to project root
cd "$(dirname "$0")/../.."

# Load test environment
export $(cat .env.test | grep -v '^#' | xargs)

# Run unit tests only (fast, no I/O)
pytest tests/unit/ \
  -v \
  --tb=short \
  --quiet \
  --maxfail=3 \
  --durations=5 \
  -m "not slow"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Quick tests passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Quick tests failed!${NC}"
    exit 1
fi
