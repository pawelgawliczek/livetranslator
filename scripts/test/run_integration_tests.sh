#!/bin/bash
# Run integration tests (requires test services)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🧪 Running Integration Tests...${NC}"
echo ""

cd "$(dirname "$0")/../.."

# Load test environment
export $(cat .env.test | grep -v '^#' | xargs)

# Ensure test services are running
./scripts/test/start_test_services.sh

# Run integration tests
pytest tests/integration/ \
  -v \
  --tb=short \
  -m integration

RESULT=$?

if [ $RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ Integration tests passed!${NC}"
else
    echo ""
    echo -e "${RED}❌ Integration tests failed!${NC}"
fi

exit $RESULT
