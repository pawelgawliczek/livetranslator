.PHONY: test test-unit test-integration test-e2e test-quick test-coverage test-setup test-clean test-hooks help
.PHONY: db-migrate db-migrate-test db-status db-status-test db-reset-test

# Default target
help:
	@echo "LiveTranslator Test Commands"
	@echo "============================="
	@echo ""
	@echo "Setup:"
	@echo "  make test-setup         Install test dependencies"
	@echo "  make test-hooks         Install Git hooks"
	@echo ""
	@echo "Running Tests:"
	@echo "  make test               Run all tests (unit + integration + E2E)"
	@echo "  make test-unit          Run unit tests only (fast, <30s)"
	@echo "  make test-integration   Run integration tests"
	@echo "  make test-e2e           Run E2E tests"
	@echo "  make test-quick         Run quick tests (for pre-commit)"
	@echo "  make test-coverage      Run tests with coverage report"
	@echo ""
	@echo "Database Migrations:"
	@echo "  make db-migrate         Apply pending migrations to production DB"
	@echo "  make db-migrate-test    Apply pending migrations to test DB"
	@echo "  make db-status          Check migration status (production DB)"
	@echo "  make db-status-test     Check migration status (test DB)"
	@echo "  make db-reset-test      Reset test DB (DANGER: drops all tables)"
	@echo ""
	@echo "Services:"
	@echo "  make test-start         Start test services"
	@echo "  make test-stop          Stop test services"
	@echo "  make test-clean         Stop and remove test volumes"
	@echo "  make test-logs          Show test service logs"
	@echo ""
	@echo "CI/CD:"
	@echo "  make ci-test            Run tests in CI mode"
	@echo ""

# Setup and Installation
test-setup:
	@echo "🔧 Setting up test environment..."
	./scripts/test/setup_test_env.sh

test-hooks:
	@echo "📌 Installing Git hooks..."
	./scripts/test/setup_git_hooks.sh

# Run Tests
test:
	@echo "🧪 Running all tests..."
	./scripts/test/run_all_tests.sh

test-unit:
	@echo "⚡ Running unit tests..."
	./scripts/test/run_unit_tests.sh

test-integration:
	@echo "🔗 Running integration tests..."
	./scripts/test/start_test_services.sh
	./scripts/test/run_integration_tests.sh

test-e2e:
	@echo "🌐 Running E2E tests..."
	./scripts/test/start_test_services.sh
	./scripts/test/run_e2e_tests.sh

test-quick:
	@echo "⚡ Running quick tests..."
	./scripts/test/run_quick_tests.sh

test-coverage:
	@echo "📊 Running tests with coverage..."
	./scripts/test/run_coverage.sh

# Test Services Management
test-start:
	@echo "🚀 Starting test services..."
	./scripts/test/start_test_services.sh

test-stop:
	@echo "🛑 Stopping test services..."
	./scripts/test/stop_test_services.sh

test-clean:
	@echo "🧹 Cleaning test environment..."
	./scripts/test/stop_test_services.sh --clean

test-logs:
	@echo "📋 Showing test service logs..."
	docker-compose -f docker-compose.test.yml logs -f

# CI/CD
ci-test:
	@echo "🤖 Running tests in CI mode..."
	./scripts/test/start_test_services.sh
	./scripts/test/run_unit_tests.sh
	./scripts/test/run_integration_tests.sh
	./scripts/test/run_coverage.sh
	./scripts/test/stop_test_services.sh --clean

# Individual test markers
test-websocket:
	@echo "🔌 Running WebSocket tests..."
	pytest -v -m websocket

test-database:
	@echo "🗄️  Running database tests..."
	pytest -v -m database

test-api:
	@echo "🔗 Running API tests..."
	pytest -v -m api

test-auth:
	@echo "🔐 Running authentication tests..."
	pytest -v -m auth

# Frontend tests
test-frontend:
	@echo "⚛️  Running frontend tests..."
	cd web && npm run test

# Watch mode (for development)
test-watch:
	@echo "👀 Running tests in watch mode..."
	pytest -v -f tests/unit

# Linting and formatting (bonus)
lint:
	@echo "🔍 Running linters..."
	cd api && python -m black --check .
	cd api && python -m flake8 .
	cd web && npm run lint

format:
	@echo "✨ Formatting code..."
	cd api && python -m black .
	cd web && npm run format

# Database Migration Commands
db-migrate:
	@echo "🗄️  Applying migrations to production database..."
	docker compose exec api python /app/scripts/db/migrate.py \
		--database livetranslator \
		--user lt_user \
		--password ${POSTGRES_PASSWORD} \
		--host postgres

db-migrate-test:
	@echo "🗄️  Applying migrations to test database..."
	docker compose exec api python /app/scripts/db/migrate.py \
		--database livetranslator_test \
		--user lt_user \
		--password ${POSTGRES_PASSWORD} \
		--host postgres

db-status:
	@echo "📊 Checking migration status (production database)..."
	docker compose exec api python /app/scripts/db/migrate.py \
		--database livetranslator \
		--user lt_user \
		--password ${POSTGRES_PASSWORD} \
		--host postgres \
		--status

db-status-test:
	@echo "📊 Checking migration status (test database)..."
	docker compose exec api python /app/scripts/db/migrate.py \
		--database livetranslator_test \
		--user lt_user \
		--password ${POSTGRES_PASSWORD} \
		--host postgres \
		--status

db-reset-test:
	@echo "⚠️  WARNING: This will DROP ALL TABLES in the test database!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read confirm
	@echo "🗄️  Resetting test database..."
	docker compose exec api python /app/scripts/db/migrate.py \
		--database livetranslator_test \
		--user lt_user \
		--password ${POSTGRES_PASSWORD} \
		--host postgres \
		--reset
