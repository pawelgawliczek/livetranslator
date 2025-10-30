#!/bin/bash
# Script to run frontend tests using Docker build container

set -e

echo "========================================="
echo "Running Frontend Tests (Phase 2.4)"
echo "========================================="

# Create a temporary Docker container with Node to run tests
docker run --rm \
  -v "$(pwd)":/app \
  -w /app \
  node:20-alpine \
  sh -c "npm ci && npm test -- --run --reporter=verbose"

echo ""
echo "========================================="
echo "Tests completed!"
echo "========================================="
