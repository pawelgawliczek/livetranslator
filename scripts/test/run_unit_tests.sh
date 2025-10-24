#!/bin/bash
# Run unit tests only (fast, no services required)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🧪 Running Unit Tests...${NC}"
echo ""

cd "$(dirname "$0")/../.."

# Load test environment
export $(cat .env.test | grep -v '^#' | xargs)

# Run unit tests
pytest tests/unit/ \
  -v \
  --tb=short \
  -m unit

RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Unit tests passed!${NC}"
else
    echo ""
    echo -e "${RED}❌ Unit tests failed!${NC}"
fi

exit $RESULT
