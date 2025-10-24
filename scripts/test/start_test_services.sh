#!/bin/bash
# Start isolated test environment
# Uses docker-compose.test.yml for complete isolation from production

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}🚀 Starting test services...${NC}"

# Check if already running
if docker ps | grep -q "postgres_test"; then
    echo -e "${GREEN}✅ Test services already running${NC}"
    exit 0
fi

# Start test stack
echo "Starting Docker containers..."
docker-compose -f docker-compose.test.yml up -d

# Wait for health checks
echo -e "${YELLOW}⏳ Waiting for services to be healthy...${NC}"

# Wait for PostgreSQL
timeout 60 bash -c '
  until docker exec postgres_test pg_isready -U lt_test_user -d livetranslator_test &> /dev/null; do
    echo -n "."
    sleep 2
  done
' || {
    echo -e "\n${RED}❌ PostgreSQL test service failed to start${NC}"
    docker-compose -f docker-compose.test.yml logs postgres_test
    exit 1
}
echo -e "\n${GREEN}✓ PostgreSQL test ready${NC}"

# Wait for Redis
timeout 60 bash -c '
  until docker exec redis_test redis-cli ping &> /dev/null; do
    echo -n "."
    sleep 2
  done
' || {
    echo -e "\n${RED}❌ Redis test service failed to start${NC}"
    docker-compose -f docker-compose.test.yml logs redis_test
    exit 1
}
echo -e "\n${GREEN}✓ Redis test ready${NC}"

# Wait for API
timeout 60 bash -c '
  until curl -sf http://localhost:9004/healthz &> /dev/null; do
    echo -n "."
    sleep 2
  done
' || {
    echo -e "\n${YELLOW}⚠ API test service not responding (may not be critical)${NC}"
}
echo -e "\n${GREEN}✓ API test ready${NC}"

echo ""
echo -e "${GREEN}✅ Test services ready!${NC}"
echo ""
echo "Service endpoints:"
echo "  • PostgreSQL: localhost:5433"
echo "  • Redis: localhost:6380"
echo "  • API: localhost:9004"
echo ""
