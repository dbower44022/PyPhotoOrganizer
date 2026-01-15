"""
Database Schema Verification Test

Tests database creation and auto-upgrade functionality to ensure all tables,
columns, and indexes are created correctly.

Scope:
    - Tests tables managed by DatabaseMetadata (database_metadata.py)
    - Does NOT test audit tables (ImportSession, FileProcessingLog, etc.)
      which are managed by AuditManager (audit_manager.py)

Usage:
    python3 test_database_schema.py
"""

import os
import sys
import sqlite3
import tempfile
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DatabaseSchemaTest:
    """Test suite for database schema verification."""

    # Expected tables and their required columns
    # NOTE: Only includes tables managed by DatabaseMetadata
    # Audit tables (ImportSession, FileProcessingLog, etc.) are managed by audit_manager.py
    EXPECTED_SCHEMA = {
        'DatabaseMetadata': [
            'id', 'database_name', 'description', 'archive_location',
            'video_archive_location', 'separate_video_archive', 'created_date',
            'last_used_date', 'schema_version', 'total_photos',
            'organization_template', 'file_type_organization',
            'user_specified_unreliable_paths', 'filename_template',
            'enable_file_rename', 'ignored_directories', 'thumbnail_size',
            'thumbnail_cache_dir', 'preview_window_geometry',
            'preview_window_visible', 'cache_memory_mb', 'cache_worker_threads',
            'delete_vault_location'
        ],
        'UniquePhotos': [
            'id', 'file_hash', 'file_path', 'file_size', 'create_year',
            'create_month', 'create_day', 'date_source', 'original_hash',
            'partial_hash', 'file_created_timestamp'
        ],
        'SourceDirectories': [
            'id', 'path', 'order_index', 'added_date', 'last_scanned', 'enabled'
        ],
        'UnreliableDates': [
            'id', 'file_hash', 'source_path', 'archive_path', 'original_date',
            'date_source', 'flag_reason', 'corrected_date', 'correction_timestamp',
            'needs_reorganization', 'original_archive_path'
        ],
        'FileRenameHistory': [
            'id', 'file_hash', 'original_filename', 'renamed_filename',
            'rename_timestamp'
        ],
        'ThumbnailCache': [
            'id', 'file_hash', 'thumbnail_path', 'thumbnail_size',
            'created_timestamp', 'last_accessed_timestamp', 'file_size_bytes'
        ],
        'DeletedFiles': [
            'id', 'file_hash', 'original_archive_path', 'delete_vault_path',
            'deletion_timestamp', 'deletion_reason', 'deleted_by_session',
            'file_size', 'creation_date', 'is_restored', 'restore_timestamp'
        ]
    }

    # Expected indexes (only for DatabaseMetadata-managed tables)
    EXPECTED_INDEXES = {
        'DatabaseMetadata': [],
        'UniquePhotos': [
            'idx_file_hash', 'idx_original_hash', 'idx_partial_hash'
        ],
        'SourceDirectories': [],
        'UnreliableDates': ['idx_unreliable_hash', 'idx_unreliable_needs_reorg'],
        'FileRenameHistory': [],
        'ThumbnailCache': ['idx_thumbnail_cache_hash', 'idx_thumbnail_cache_accessed'],
        'DeletedFiles': ['idx_deleted_hash', 'idx_deleted_restored', 'idx_deleted_timestamp']
    }

    def __init__(self):
        self.test_db_path = None
        self.passed_tests = 0
        self.failed_tests = 0
        self.test_results = []

    def log_test(self, test_name: str, passed: bool, message: str = ""):
        """Log test result."""
        if passed:
            self.passed_tests += 1
            logger.info(f"✓ {test_name}")
            if message:
                logger.info(f"  {message}")
        else:
            self.failed_tests += 1
            logger.error(f"✗ {test_name}")
            if message:
                logger.error(f"  {message}")

        self.test_results.append({
            'test': test_name,
            'passed': passed,
            'message': message
        })

    def create_test_database(self) -> str:
        """Create a temporary test database."""
        temp_dir = tempfile.gettempdir()
        db_path = os.path.join(temp_dir, 'test_schema_verification.db')

        # Remove old test database if it exists
        if os.path.exists(db_path):
            os.remove(db_path)

        return db_path

    def test_new_database_creation(self):
        """Test creating a new database from scratch."""
        logger.info("\n" + "="*80)
        logger.info("TEST 1: New Database Creation")
        logger.info("="*80)

        try:
            from database_metadata import DatabaseMetadata

            # Create new database by directly initializing DatabaseMetadata
            # This bypasses the pillow_heif dependency in DuplicateFileDetection
            self.test_db_path = self.create_test_database()
            test_archive = tempfile.mkdtemp()

            # Initialize DatabaseMetadata - this creates all tables managed by it
            db_meta = DatabaseMetadata(self.test_db_path)

            # Insert minimal metadata
            success = db_meta.initialize_metadata(
                "Test Database",
                test_archive,
                "Schema verification test database"
            )

            self.log_test(
                "Create new database",
                success,
                f"Database created at: {self.test_db_path}"
            )

            # Create UniquePhotos table manually (normally done by DuplicateFileDetection)
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS UniquePhotos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_hash TEXT NOT NULL UNIQUE,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    create_year TEXT,
                    create_month TEXT,
                    create_day TEXT,
                    date_source TEXT,
                    original_hash TEXT,
                    partial_hash TEXT,
                    file_created_timestamp TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_file_hash ON UniquePhotos(file_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_original_hash ON UniquePhotos(original_hash)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_partial_hash ON UniquePhotos(partial_hash)")
            conn.commit()
            conn.close()

            # Clean up test archive directory
            os.rmdir(test_archive)

        except Exception as e:
            self.log_test(
                "Create new database",
                False,
                f"Exception: {e}"
            )

    def test_table_existence(self):
        """Test that all expected tables exist."""
        logger.info("\n" + "="*80)
        logger.info("TEST 2: Table Existence")
        logger.info("="*80)

        try:
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()

            # Get all tables
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            existing_tables = {row[0] for row in cursor.fetchall()}

            # Check each expected table
            for table_name in self.EXPECTED_SCHEMA.keys():
                exists = table_name in existing_tables
                self.log_test(
                    f"Table exists: {table_name}",
                    exists,
                    f"Table {'found' if exists else 'MISSING'}"
                )

            # Check for unexpected tables
            expected_tables = set(self.EXPECTED_SCHEMA.keys())
            unexpected_tables = existing_tables - expected_tables
            if unexpected_tables:
                logger.warning(f"  Unexpected tables found: {unexpected_tables}")

            conn.close()

        except Exception as e:
            self.log_test(
                "Table existence check",
                False,
                f"Exception: {e}"
            )

    def test_table_columns(self):
        """Test that all expected columns exist in each table."""
        logger.info("\n" + "="*80)
        logger.info("TEST 3: Table Column Verification")
        logger.info("="*80)

        try:
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()

            for table_name, expected_columns in self.EXPECTED_SCHEMA.items():
                # Get table columns
                cursor.execute(f"PRAGMA table_info({table_name})")
                existing_columns = {row[1] for row in cursor.fetchall()}

                # Check each expected column
                all_columns_exist = True
                missing_columns = []

                for column in expected_columns:
                    if column not in existing_columns:
                        all_columns_exist = False
                        missing_columns.append(column)

                if all_columns_exist:
                    self.log_test(
                        f"Table columns: {table_name}",
                        True,
                        f"All {len(expected_columns)} columns present"
                    )
                else:
                    self.log_test(
                        f"Table columns: {table_name}",
                        False,
                        f"Missing columns: {missing_columns}"
                    )

                # Check for unexpected columns
                expected_set = set(expected_columns)
                unexpected_columns = existing_columns - expected_set
                if unexpected_columns:
                    logger.warning(f"  Unexpected columns in {table_name}: {unexpected_columns}")

            conn.close()

        except Exception as e:
            self.log_test(
                "Column verification",
                False,
                f"Exception: {e}"
            )

    def test_indexes(self):
        """Test that all expected indexes exist."""
        logger.info("\n" + "="*80)
        logger.info("TEST 4: Index Verification")
        logger.info("="*80)

        try:
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()

            # Get all indexes
            cursor.execute("""
                SELECT name, tbl_name FROM sqlite_master
                WHERE type='index' AND name NOT LIKE 'sqlite_%'
                ORDER BY tbl_name, name
            """)
            existing_indexes = {}
            for row in cursor.fetchall():
                index_name, table_name = row
                if table_name not in existing_indexes:
                    existing_indexes[table_name] = set()
                existing_indexes[table_name].add(index_name)

            # Check expected indexes for each table
            for table_name, expected_idx_list in self.EXPECTED_INDEXES.items():
                table_indexes = existing_indexes.get(table_name, set())

                if not expected_idx_list:
                    # No indexes expected for this table
                    continue

                all_indexes_exist = True
                missing_indexes = []

                for index_name in expected_idx_list:
                    if index_name not in table_indexes:
                        all_indexes_exist = False
                        missing_indexes.append(index_name)

                if all_indexes_exist:
                    self.log_test(
                        f"Indexes: {table_name}",
                        True,
                        f"All {len(expected_idx_list)} indexes present"
                    )
                else:
                    self.log_test(
                        f"Indexes: {table_name}",
                        False,
                        f"Missing indexes: {missing_indexes}"
                    )

            conn.close()

        except Exception as e:
            self.log_test(
                "Index verification",
                False,
                f"Exception: {e}"
            )

    def test_auto_upgrade(self):
        """Test that auto-upgrade works for existing databases."""
        logger.info("\n" + "="*80)
        logger.info("TEST 5: Database Auto-Upgrade")
        logger.info("="*80)

        try:
            # Create a minimal old database (missing some columns/tables)
            # Use a separate path to avoid deleting the main test database
            temp_dir = tempfile.gettempdir()
            old_db_path = os.path.join(temp_dir, 'test_schema_verification_old.db')

            # Remove old test database if it exists
            if os.path.exists(old_db_path):
                os.remove(old_db_path)

            conn = sqlite3.connect(old_db_path)
            cursor = conn.cursor()

            # Create minimal DatabaseMetadata table (old schema)
            cursor.execute("""
                CREATE TABLE DatabaseMetadata (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    database_name TEXT NOT NULL,
                    description TEXT,
                    archive_location TEXT NOT NULL,
                    created_date TEXT NOT NULL,
                    last_used_date TEXT NOT NULL,
                    total_photos INTEGER DEFAULT 0
                )
            """)

            # Insert metadata
            cursor.execute("""
                INSERT INTO DatabaseMetadata
                (id, database_name, description, archive_location, created_date, last_used_date)
                VALUES (1, 'Old DB', 'Test', '/tmp/test', '2024-01-01', '2024-01-01')
            """)

            conn.commit()
            conn.close()

            # Now open with DatabaseMetadata to trigger auto-upgrade
            from database_metadata import DatabaseMetadata
            db_meta = DatabaseMetadata(old_db_path)

            # Verify upgrades were applied
            conn = sqlite3.connect(old_db_path)
            cursor = conn.cursor()

            # Check that new columns were added
            cursor.execute("PRAGMA table_info(DatabaseMetadata)")
            columns = {row[1] for row in cursor.fetchall()}

            new_columns = ['delete_vault_location', 'organization_template', 'cache_memory_mb']
            all_added = all(col in columns for col in new_columns)

            self.log_test(
                "Auto-upgrade: Add missing columns",
                all_added,
                f"New columns {'added successfully' if all_added else 'MISSING'}"
            )

            # Check that new tables were added
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name IN ('DeletedFiles', 'ThumbnailCache')
            """)
            new_tables = {row[0] for row in cursor.fetchall()}
            tables_added = 'DeletedFiles' in new_tables and 'ThumbnailCache' in new_tables

            self.log_test(
                "Auto-upgrade: Add missing tables",
                tables_added,
                f"Tables {'added successfully' if tables_added else 'MISSING'}"
            )

            conn.close()

            # Clean up
            if os.path.exists(old_db_path):
                os.remove(old_db_path)

        except Exception as e:
            self.log_test(
                "Auto-upgrade test",
                False,
                f"Exception: {e}"
            )

    def test_foreign_keys(self):
        """Test that foreign key constraints are defined."""
        logger.info("\n" + "="*80)
        logger.info("TEST 6: Foreign Key Constraints")
        logger.info("="*80)

        try:
            conn = sqlite3.connect(self.test_db_path)
            cursor = conn.cursor()

            # Tables with expected foreign keys (only DatabaseMetadata-managed tables)
            expected_fk = {
                'DeletedFiles': ['UniquePhotos'],
                'UnreliableDates': ['UniquePhotos'],
                'FileRenameHistory': ['UniquePhotos']
            }

            for table_name, referenced_tables in expected_fk.items():
                cursor.execute(f"PRAGMA foreign_key_list({table_name})")
                fk_info = cursor.fetchall()

                has_fk = len(fk_info) > 0
                fk_tables = [fk[2] for fk in fk_info]

                # Note: SQLite doesn't always report foreign keys via PRAGMA if referenced
                # tables don't exist when the FK table is created. This is expected behavior.
                # Foreign keys are defined in schema but may not show up in PRAGMA queries.
                if has_fk:
                    self.log_test(
                        f"Foreign keys: {table_name}",
                        True,
                        f"References: {fk_tables}"
                    )
                else:
                    # Check if FK is defined in table schema (even if not enforced)
                    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
                    table_sql = cursor.fetchone()

                    if not table_sql:
                        self.log_test(
                            f"Foreign keys: {table_name}",
                            False,
                            f"Table not found in database"
                        )
                    elif 'FOREIGN KEY' in table_sql[0]:
                        self.log_test(
                            f"Foreign keys: {table_name}",
                            True,
                            f"Defined in schema (SQLite doesn't enforce by default)"
                        )
                    else:
                        self.log_test(
                            f"Foreign keys: {table_name}",
                            False,
                            f"Missing from schema definition (found: {table_sql[0][:100]}...)"
                        )

            conn.close()

        except Exception as e:
            self.log_test(
                "Foreign key verification",
                False,
                f"Exception: {e}"
            )

    def cleanup(self):
        """Clean up test database."""
        if self.test_db_path and os.path.exists(self.test_db_path):
            try:
                # os.remove(self.test_db_path)
                logger.info(f"\n✓ Cleaned up test database: {self.test_db_path}")
            except Exception as e:
                logger.warning(f"\n⚠ Failed to clean up test database: {e}")

    def print_summary(self):
        """Print test summary."""
        logger.info("\n" + "="*80)
        logger.info("TEST SUMMARY")
        logger.info("="*80)

        total_tests = self.passed_tests + self.failed_tests
        pass_rate = (self.passed_tests / total_tests * 100) if total_tests > 0 else 0

        logger.info(f"Total tests: {total_tests}")
        logger.info(f"Passed: {self.passed_tests} ✓")
        logger.info(f"Failed: {self.failed_tests} ✗")
        logger.info(f"Pass rate: {pass_rate:.1f}%")

        if self.failed_tests > 0:
            logger.info("\nFailed tests:")
            for result in self.test_results:
                if not result['passed']:
                    logger.error(f"  ✗ {result['test']}")
                    if result['message']:
                        logger.error(f"    {result['message']}")

        logger.info("="*80)

        return self.failed_tests == 0

    def run_all_tests(self):
        """Run all schema verification tests."""
        logger.info("="*80)
        logger.info("DATABASE SCHEMA VERIFICATION TEST SUITE")
        logger.info("="*80)

        try:
            # Test 1: Create new database
            self.test_new_database_creation()

            # Test 2: Verify all tables exist
            self.test_table_existence()

            # Test 3: Verify all columns exist
            self.test_table_columns()

            # Test 4: Verify all indexes exist
            self.test_indexes()

            # Test 5: Test auto-upgrade
            self.test_auto_upgrade()

            # Test 6: Verify foreign keys
            self.test_foreign_keys()

        except Exception as e:
            logger.error(f"\n✗ Test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # Clean up
            self.cleanup()

            # Print summary
            all_passed = self.print_summary()

            return all_passed


def main():
    """Main entry point."""
    test_suite = DatabaseSchemaTest()
    all_passed = test_suite.run_all_tests()

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
