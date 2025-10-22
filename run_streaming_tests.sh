#!/bin/bash
# Test runner for STT Streaming components

set -e

echo "================================"
echo "STT Streaming Tests"
echo "================================"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo -e "${RED}Error: pytest is not installed${NC}"
    echo "Install with: pip install pytest pytest-asyncio pytest-cov"
    exit 1
fi

# Change to project directory
cd "$(dirname "$0")"

echo -e "${YELLOW}Running Unit Tests...${NC}"
echo ""

# Test 1: Streaming Manager
echo "1. Testing Streaming Manager..."
python3 -m pytest api/tests/test_streaming_manager.py -v --tb=short || {
    echo -e "${RED}✗ Streaming Manager tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Streaming Manager tests passed${NC}"
echo ""

# Test 2: Speechmatics Integration
echo "2. Testing Speechmatics Integration..."
python3 -m pytest api/tests/test_speechmatics_integration.py -v --tb=short || {
    echo -e "${RED}✗ Speechmatics integration tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Speechmatics integration tests passed${NC}"
echo ""

# Test 3: STT Router Streaming
echo "3. Testing STT Router with Streaming..."
python3 -m pytest api/tests/test_stt_router_streaming.py -v --tb=short || {
    echo -e "${RED}✗ STT Router streaming tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ STT Router streaming tests passed${NC}"
echo ""

# Test 4: Existing STT Router Tests
echo "4. Testing Existing STT Router..."
python3 -m pytest api/tests/test_stt_router.py -v --tb=short || {
    echo -e "${RED}✗ Existing STT Router tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ Existing STT Router tests passed${NC}"
echo ""

# Test 5: STT Router Integration
echo "5. Testing STT Router Integration..."
python3 -m pytest api/tests/test_stt_router_integration.py -v --tb=short || {
    echo -e "${RED}✗ STT Router integration tests failed${NC}"
    exit 1
}
echo -e "${GREEN}✓ STT Router integration tests passed${NC}"
echo ""

echo "================================"
echo -e "${GREEN}All Tests Passed! ✓${NC}"
echo "================================"
echo ""

# Optional: Run with coverage
if [ "$1" == "--coverage" ]; then
    echo -e "${YELLOW}Running with coverage...${NC}"
    python3 -m pytest \
        api/tests/test_streaming_manager.py \
        api/tests/test_speechmatics_integration.py \
        api/tests/test_stt_router_streaming.py \
        --cov=api.routers.stt \
        --cov-report=html \
        --cov-report=term

    echo ""
    echo "Coverage report generated in htmlcov/index.html"
fi

echo ""
echo "Test Summary:"
echo "  • Streaming Manager: Connection pool and lifecycle"
echo "  • Speechmatics: WebSocket protocol and integration"
echo "  • STT Router: Streaming vs batch, routing, callbacks"
echo "  • Integration: Database settings and API endpoints"
echo ""
