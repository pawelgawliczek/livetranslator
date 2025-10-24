#!/bin/bash
# Stop and cleanup test environment

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}🛑 Stopping test services...${NC}"

# Stop containers
docker-compose -f docker-compose.test.yml down

# Optional: Remove volumes for fresh start
if [ "$1" == "--clean" ] || [ "$1" == "-c" ]; then
    echo -e "${YELLOW}🧹 Cleaning up test volumes...${NC}"
    docker-compose -f docker-compose.test.yml down -v
    docker volume rm livetranslator_test_pg_data 2>/dev/null || true
    docker volume rm livetranslator_test_redis_data 2>/dev/null || true
    echo -e "${GREEN}✅ Test volumes removed${NC}"
fi

echo -e "${GREEN}✅ Test services stopped${NC}"
