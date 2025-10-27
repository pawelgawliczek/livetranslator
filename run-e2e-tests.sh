#!/bin/bash
# E2E Test Runner - Spins up Playwright container, runs tests, then tears it down
# Usage: ./run-e2e-tests.sh [test-file]

set -e

echo "🎭 Starting E2E tests with Playwright..."
echo ""

# Create directories if they don't exist
mkdir -p tests/e2e/test-results
mkdir -p tests/e2e/playwright-report

# Install dependencies if needed (only on first run or after package.json changes)
if [ ! -d "tests/e2e/node_modules" ]; then
    echo "📦 Installing dependencies..."
    docker compose run --rm playwright npm install
    echo ""
fi

# Run tests (container will auto-remove after completion)
if [ -z "$1" ]; then
    echo "📝 Running all E2E tests..."
    docker compose run --rm playwright npx playwright test
else
    echo "📝 Running test: $1"
    docker compose run --rm playwright npx playwright test "$1"
fi

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All tests passed!"
else
    echo "❌ Tests failed (exit code: $EXIT_CODE)"
    echo ""
    echo "📊 To view the HTML report:"
    echo "   cd tests/e2e && npx playwright show-report"
    echo ""
    echo "📸 Screenshots saved to: tests/e2e/test-results/"
fi

exit $EXIT_CODE
