#!/bin/bash
# Run end-to-end tests with Playwright

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}🧪 Running E2E Tests...${NC}"
echo ""

cd "$(dirname "$0")/../.."

# Load test environment
export $(cat .env.test | grep -v '^#' | xargs)

# Ensure test services are running
./scripts/test/start_test_services.sh

# Check if Playwright is installed
if ! command -v npx playwright &> /dev/null; then
    echo -e "${RED}❌ Playwright not installed${NC}"
    echo "Install with: npx playwright install"
    exit 1
fi

# Run E2E tests
cd tests/e2e
npx playwright test \
  --config playwright.config.js \
  ${1:-}  # Pass any additional arguments

RESULT=$?

cd ../..

if [ $RESULT -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ E2E tests passed!${NC}"
else
    echo ""
    echo -e "${RED}❌ E2E tests failed!${NC}"
fi

exit $RESULT
