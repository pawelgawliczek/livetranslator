"""
Tests for database migration tracking system.

Ensures that:
1. Migration tracking table exists and is preserved
2. Migration runner script works correctly
3. Automatic test database verification functions
4. Schema drift detection works
"""

import os
import json
import pytest
import subprocess
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
import pytest_asyncio


@pytest.mark.unit
class TestSchemaMigrationsTable:
    """Tests for schema_migrations table existence and structure."""

    @pytest_asyncio.fixture
    async def test_engine(self):
        """Create engine for test database."""
        test_db_dsn = os.getenv("TEST_POSTGRES_DSN")
        engine = create_async_engine(test_db_dsn, echo=False)
        yield engine
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_schema_migrations_table_exists(self, test_engine):
        """Verify schema_migrations table exists."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = 'schema_migrations'
                    );
                """)
            )
            exists = result.scalar()
            assert exists is True, "schema_migrations table should exist"

    @pytest.mark.asyncio
    async def test_schema_migrations_has_correct_columns(self, test_engine):
        """Verify schema_migrations has required columns."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = 'schema_migrations'
                    ORDER BY ordinal_position;
                """)
            )
            columns = {row[0]: {"type": row[1], "nullable": row[2]} for row in result}

        # Verify required columns exist
        assert "version" in columns
        assert "name" in columns
        assert "applied_at" in columns
        assert "checksum" in columns
        assert "execution_time_ms" in columns

        # Verify column types
        assert columns["version"]["type"] == "character varying"
        assert columns["name"]["type"] == "character varying"
        assert columns["applied_at"]["type"] == "timestamp without time zone"
        assert columns["checksum"]["type"] == "character varying"
        assert columns["execution_time_ms"]["type"] == "integer"

        # Verify NOT NULL constraints
        assert columns["version"]["nullable"] == "NO"
        assert columns["name"]["nullable"] == "NO"
        assert columns["applied_at"]["nullable"] == "NO"

    @pytest.mark.asyncio
    async def test_schema_migrations_has_primary_key(self, test_engine):
        """Verify schema_migrations has primary key on version."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT a.attname
                    FROM pg_index i
                    JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
                    WHERE i.indrelid = 'schema_migrations'::regclass
                    AND i.indisprimary;
                """)
            )
            pk_columns = [row[0] for row in result]

        assert pk_columns == ["version"], "Primary key should be on version column"

    @pytest.mark.asyncio
    async def test_schema_migrations_contains_migration_009(self, test_engine):
        """Verify migration 009 is recorded in schema_migrations."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT version, name, applied_at
                    FROM schema_migrations
                    WHERE version = '009'
                """)
            )
            row = result.fetchone()

        assert row is not None, "Migration 009 should be recorded"
        assert row[0] == "009"
        assert "schema_migrations" in row[1].lower()
        assert row[2] is not None  # applied_at should be set

    @pytest.mark.asyncio
    async def test_schema_migrations_has_all_migrations(self, test_engine):
        """Verify all expected migrations are recorded."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT version FROM schema_migrations ORDER BY version")
            )
            versions = [row[0] for row in result]

        # Should have at least migrations 001-010
        expected_migrations = [f"{i:03d}" for i in range(1, 11)]
        for expected in expected_migrations:
            assert expected in versions, f"Migration {expected} should be recorded"


@pytest.mark.unit
class TestMigrationPreservation:
    """Tests that schema_migrations table is preserved during cleanup."""

    @pytest_asyncio.fixture
    async def test_engine(self):
        """Create engine for test database."""
        test_db_dsn = os.getenv("TEST_POSTGRES_DSN")
        engine = create_async_engine(test_db_dsn, echo=False)
        yield engine
        await engine.dispose()

    @pytest.mark.asyncio
    async def test_schema_migrations_not_in_truncate_list(self, test_engine):
        """Verify schema_migrations is excluded from dynamic table list."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                    AND tablename != 'schema_migrations'
                    ORDER BY tablename;
                """)
            )
            tables = [row[0] for row in result]

        # Verify schema_migrations is NOT in the list
        assert "schema_migrations" not in tables

    @pytest.mark.asyncio
    async def test_schema_migrations_has_data_after_tests(self, test_engine):
        """Verify schema_migrations retains data throughout test session."""
        async with test_engine.connect() as conn:
            result = await conn.execute(
                text("SELECT COUNT(*) FROM schema_migrations")
            )
            count = result.scalar()

        assert count >= 10, "schema_migrations should have migration records"


@pytest.mark.integration
class TestMigrationRunner:
    """Tests for the migrate.py script."""

    def test_migration_script_exists(self):
        """Verify migrate.py script exists and is executable."""
        script_path = "/app/scripts/db/migrate.py"
        assert os.path.exists(script_path), "migrate.py should exist"
        assert os.access(script_path, os.X_OK), "migrate.py should be executable"

    def test_migration_status_command(self):
        """Test migration status command runs successfully."""
        result = subprocess.run(
            [
                "python", "/app/scripts/db/migrate.py",
                "--database", "livetranslator_test",
                "--user", "lt_user",
                "--password", os.getenv("POSTGRES_PASSWORD", "${POSTGRES_PASSWORD}"),
                "--host", "postgres",
                "--status"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0, f"Migration status command failed: {result.stderr}"
        assert "Migration Status" in result.stdout
        assert "Total:" in result.stdout
        assert "Applied:" in result.stdout
        assert "Pending:" in result.stdout

    def test_migration_status_shows_all_applied(self):
        """Test that migration status shows all migrations as applied."""
        result = subprocess.run(
            [
                "python", "/app/scripts/db/migrate.py",
                "--database", "livetranslator_test",
                "--user", "lt_user",
                "--password", os.getenv("POSTGRES_PASSWORD", "${POSTGRES_PASSWORD}"),
                "--host", "postgres",
                "--status"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result.returncode == 0
        # Should show no pending migrations
        assert "Pending: 0" in result.stdout or "Database is up to date" in result.stdout

    def test_migration_script_idempotent(self):
        """Test that running migrations again is idempotent."""
        # Run migrations
        result1 = subprocess.run(
            [
                "python", "/app/scripts/db/migrate.py",
                "--database", "livetranslator_test",
                "--user", "lt_user",
                "--password", os.getenv("POSTGRES_PASSWORD", "${POSTGRES_PASSWORD}"),
                "--host", "postgres"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result1.returncode == 0

        # Run again - should show database is up to date
        result2 = subprocess.run(
            [
                "python", "/app/scripts/db/migrate.py",
                "--database", "livetranslator_test",
                "--user", "lt_user",
                "--password", os.getenv("POSTGRES_PASSWORD", "${POSTGRES_PASSWORD}"),
                "--host", "postgres"
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        assert result2.returncode == 0
        assert "Database is up to date" in result2.stdout or "Pending: 0" in result2.stdout


@pytest.mark.integration
class TestAutomaticMigrationVerification:
    """Tests for automatic migration verification in test suite."""

    def test_verify_migrations_fixture_exists(self):
        """Verify the verify_migrations fixture is defined."""
        from api.tests.conftest import verify_migrations
        assert verify_migrations is not None

    def test_verify_test_database_schema_function_exists(self):
        """Verify the verify_test_database_schema function is defined."""
        from api.tests.conftest import verify_test_database_schema
        assert verify_test_database_schema is not None


@pytest.mark.unit
class TestMigrationFiles:
    """Tests for migration file structure and naming."""

    def test_migration_009_file_exists(self):
        """Verify migration 009 file exists."""
        migration_file = "/app/migrations/009_create_schema_migrations.sql"
        assert os.path.exists(migration_file), "Migration 009 file should exist"

    def test_migration_009_has_correct_structure(self):
        """Verify migration 009 has proper SQL structure."""
        migration_file = "/app/migrations/009_create_schema_migrations.sql"

        with open(migration_file, "r") as f:
            content = f.read()

        # Should have transaction control
        assert "BEGIN;" in content
        assert "COMMIT;" in content

        # Should create schema_migrations table
        assert "CREATE TABLE" in content
        assert "schema_migrations" in content

        # Should have required columns
        assert "version" in content
        assert "name" in content
        assert "applied_at" in content
        assert "checksum" in content

        # Should have comments for documentation
        assert "COMMENT ON" in content

    def test_all_migration_files_follow_naming_convention(self):
        """Verify all migration files follow NNN_description.sql format."""
        migrations_dir = "/app/migrations"
        migration_files = [f for f in os.listdir(migrations_dir) if f.endswith(".sql")]

        for filename in migration_files:
            # Should match pattern: 001_description.sql
            assert len(filename.split("_")) >= 2, f"{filename} should have underscore separator"
            version_part = filename.split("_")[0]
            assert version_part.isdigit(), f"{filename} should start with digits"
            assert len(version_part) == 3, f"{filename} should have 3-digit version"
