#!/usr/bin/env python3
"""
Database migration runner with tracking.

Usage:
    python scripts/db/migrate.py --database livetranslator          # Production
    python scripts/db/migrate.py --database livetranslator_test     # Test
    python scripts/db/migrate.py --database livetranslator_test --reset  # Reset test DB
    python scripts/db/migrate.py --database livetranslator --status      # Check status
"""
import os
import sys
import hashlib
import time
import psycopg2
from pathlib import Path
from typing import List, Tuple, Set

# Get migrations directory (relative to this script)
MIGRATIONS_DIR = Path(__file__).parent.parent.parent / "migrations"


class MigrationRunner:
    def __init__(self, db_name: str, db_user: str, db_password: str, db_host: str = "localhost", db_port: int = 5432):
        self.db_name = db_name
        self.conn_params = {
            "dbname": db_name,
            "user": db_user,
            "password": db_password,
            "host": db_host,
            "port": db_port
        }

    def connect(self):
        """Create database connection."""
        return psycopg2.connect(**self.conn_params)

    def get_applied_migrations(self) -> Set[str]:
        """Get set of already applied migration versions."""
        conn = self.connect()
        try:
            cur = conn.cursor()
            # Check if schema_migrations table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = 'schema_migrations'
                );
            """)
            table_exists = cur.fetchone()[0]

            if not table_exists:
                print("⚠️  schema_migrations table doesn't exist. Will create it with first migration.")
                return set()

            cur.execute("SELECT version FROM schema_migrations ORDER BY version;")
            return {row[0] for row in cur.fetchall()}
        finally:
            conn.close()

    def get_migration_files(self) -> List[Tuple[str, Path]]:
        """Get sorted list of migration files with their versions."""
        migrations = []
        for file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            # Extract version number from filename (e.g., "001_add_invite_system.sql" -> "001")
            version = file.name.split("_")[0]
            migrations.append((version, file))
        return migrations

    def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of migration file."""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            sha256.update(f.read())
        return sha256.hexdigest()

    def apply_migration(self, version: str, file_path: Path) -> bool:
        """Apply a single migration and record it."""
        print(f"📦 Applying migration {version}: {file_path.name}")

        conn = self.connect()
        conn.autocommit = False  # Use transactions

        try:
            cur = conn.cursor()

            # Read and execute migration
            with open(file_path, 'r') as f:
                migration_sql = f.read()

            start_time = time.time()
            cur.execute(migration_sql)
            execution_time_ms = int((time.time() - start_time) * 1000)

            # Record migration (if schema_migrations exists)
            # Note: Migration 009 creates the table, so it won't record itself
            checksum = self.calculate_checksum(file_path)
            name = file_path.stem  # Filename without .sql extension

            # Try to record the migration, but don't fail if table doesn't exist yet
            try:
                cur.execute("""
                    INSERT INTO schema_migrations (version, name, checksum, execution_time_ms)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (version) DO NOTHING;
                """, (version, name, checksum, execution_time_ms))
            except psycopg2.errors.UndefinedTable:
                # schema_migrations doesn't exist yet (this is migration 009)
                pass

            conn.commit()
            print(f"✅ Migration {version} applied successfully ({execution_time_ms}ms)")
            return True

        except Exception as e:
            conn.rollback()
            print(f"❌ Migration {version} failed: {e}")
            return False
        finally:
            conn.close()

    def migrate(self) -> bool:
        """Run all pending migrations."""
        print(f"🔍 Checking migrations for database: {self.db_name}")

        applied = self.get_applied_migrations()
        migrations = self.get_migration_files()

        print(f"📊 Found {len(migrations)} total migrations")
        print(f"✅ Already applied: {len(applied)}")

        pending = [(v, p) for v, p in migrations if v not in applied]

        if not pending:
            print("✨ Database is up to date!")
            return True

        print(f"⏳ Pending migrations: {len(pending)}")
        for version, path in pending:
            print(f"   • {version}: {path.name}")

        print()
        success = True
        for version, path in pending:
            if not self.apply_migration(version, path):
                success = False
                break

        return success

    def reset_database(self):
        """Drop all tables and reapply all migrations (TEST DATABASE ONLY)."""
        if "test" not in self.db_name.lower():
            raise ValueError("❌ SAFETY: reset_database() can only be used on test databases!")

        print(f"⚠️  RESETTING DATABASE: {self.db_name}")
        print("   This will DROP ALL TABLES and reapply migrations.")

        conn = self.connect()
        try:
            cur = conn.cursor()

            # Drop all tables in public schema
            cur.execute("""
                DROP SCHEMA public CASCADE;
                CREATE SCHEMA public;
                GRANT ALL ON SCHEMA public TO public;
            """)
            conn.commit()
            print("✅ Database reset complete")

        finally:
            conn.close()

        # Reapply all migrations
        print()
        return self.migrate()

    def status(self):
        """Show migration status."""
        applied = self.get_applied_migrations()
        migrations = self.get_migration_files()

        print(f"\n📊 Migration Status for {self.db_name}")
        print("=" * 70)

        for version, path in migrations:
            status = "✅ Applied" if version in applied else "⏳ Pending"
            print(f"{version:>3} {status:>12}  {path.name}")

        print("=" * 70)
        print(f"Total: {len(migrations)} | Applied: {len(applied)} | Pending: {len(migrations) - len(applied)}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Database migration runner")
    parser.add_argument("--database", required=True, help="Database name (livetranslator or livetranslator_test)")
    parser.add_argument("--user", default=os.getenv("POSTGRES_USER", "lt_user"), help="Database user")
    parser.add_argument("--password", default=os.getenv("POSTGRES_PASSWORD"), help="Database password")
    parser.add_argument("--host", default="localhost", help="Database host")
    parser.add_argument("--port", type=int, default=5432, help="Database port")
    parser.add_argument("--reset", action="store_true", help="Reset database (test only!)")
    parser.add_argument("--status", action="store_true", help="Show migration status")

    args = parser.parse_args()

    if not args.password:
        print("❌ Database password required (use --password or POSTGRES_PASSWORD env var)")
        sys.exit(1)

    runner = MigrationRunner(
        db_name=args.database,
        db_user=args.user,
        db_password=args.password,
        db_host=args.host,
        db_port=args.port
    )

    try:
        if args.status:
            runner.status()
        elif args.reset:
            if not runner.reset_database():
                sys.exit(1)
        else:
            if not runner.migrate():
                sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
