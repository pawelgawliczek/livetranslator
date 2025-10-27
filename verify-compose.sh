#!/bin/bash
# Verify and fix docker-compose.yml configuration
# Run from livetranslator directory: bash verify-compose.sh

set -e

echo "================================================"
echo "Docker Compose Configuration Checker"
echo "================================================"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${BLUE}ℹ${NC} $1"; }
success() { echo -e "${GREEN}✓${NC} $1"; }
warning() { echo -e "${YELLOW}⚠${NC} $1"; }
error() { echo -e "${RED}✗${NC} $1"; }

# Check if docker-compose.yml exists
if [ ! -f docker-compose.yml ]; then
    error "docker-compose.yml not found!"
    exit 1
fi

success "Found docker-compose.yml"

# Parse and check required services
echo ""
info "Checking required services..."

REQUIRED_SERVICES=("api" "stt_worker" "mt_worker" "redis" "postgres")
MISSING_SERVICES=()

for service in "${REQUIRED_SERVICES[@]}"; do
    if grep -q "^  $service:" docker-compose.yml; then
        success "$service service defined"
    else
        error "$service service missing"
        MISSING_SERVICES+=("$service")
    fi
done

# Check healthchecks
echo ""
info "Checking healthchecks..."

for service in api stt_worker mt_worker; do
    if grep -A 5 "^  $service:" docker-compose.yml | grep -q "healthcheck:"; then
        success "$service has healthcheck"
    else
        warning "$service missing healthcheck"
    fi
done

# Check Redis database
echo ""
info "Checking Redis configuration..."

if grep -q "redis://redis:6379/5" docker-compose.yml || grep -q "REDIS.*:6379/5" .env 2>/dev/null; then
    success "Redis DB 5 configured"
else
    warning "Redis DB might not be set to 5"
fi

# Check network configuration
echo ""
info "Checking networks..."

if grep -q "networks:" docker-compose.yml; then
    success "Networks defined"
    NETWORKS=$(grep -A 20 "^networks:" docker-compose.yml | grep "^  [a-z]" | sed 's/://g' | xargs)
    info "Found networks: $NETWORKS"
else
    warning "No explicit networks defined (using default)"
fi

# Check
