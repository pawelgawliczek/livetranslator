#!/bin/bash
# Setup test environment and install dependencies

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🔧 Setting up test environment...${NC}"
echo ""

cd "$(dirname "$0")/../.."

# Check Python version
echo "Checking Python version..."
python3 --version

# Install Python test dependencies
echo ""
echo "Installing Python test dependencies..."
pip install --upgrade pip
pip install pytest pytest-asyncio pytest-cov pytest-timeout pytest-xdist
pip install websockets httpx

# Install Playwright for E2E tests
echo ""
echo "Installing Playwright..."
pip install playwright
npx playwright install chromium

# Install frontend test dependencies
echo ""
echo "Installing frontend test dependencies..."
if [ -f "web/package.json" ]; then
    cd web
    npm install --save-dev vitest @testing-library/react @testing-library/jest-dom jsdom
    cd ..
fi

# Create .env.test if it doesn't exist
if [ ! -f ".env.test" ]; then
    echo ""
    echo "Creating .env.test..."
    cp .env.test.example .env.test 2>/dev/null || {
        echo "⚠  .env.test.example not found, .env.test already exists"
    }
fi

echo ""
echo -e "${GREEN}✅ Test environment setup complete!${NC}"
echo ""
echo "Next steps:"
echo "  1. Review .env.test configuration"
echo "  2. Run: ./scripts/test/start_test_services.sh"
echo "  3. Run: make test"
echo ""
