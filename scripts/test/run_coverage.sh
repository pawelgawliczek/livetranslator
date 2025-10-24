#!/bin/bash
# Run tests with coverage report

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}📊 Running Tests with Coverage...${NC}"
echo ""

cd "$(dirname "$0")/../.."

# Load test environment
export $(cat .env.test | grep -v '^#' | xargs)

# Ensure test services are running
./scripts/test/start_test_services.sh

# Run tests with coverage
pytest tests/unit tests/integration \
  --cov=api \
  --cov=workers \
  --cov-report=html \
  --cov-report=term-missing \
  --cov-report=json

echo ""
echo -e "${GREEN}✅ Coverage report generated!${NC}"
echo ""
echo "📊 View coverage report:"
echo "  • HTML: open tests/htmlcov/index.html"
echo "  • JSON: tests/coverage.json"
echo ""
