"""
Database Migration: Schema v5 - Unified UniquePhotos Table

BREAKING CHANGE - Fresh import required:
- Removes FileHashHistory table (duplicate detection now via UniquePhotos primary key)
- Removes FileVersions, ModificationSession, ModificationLog tables (merged into UniquePhotos)
- Recreates UniquePhotos with revision tracking fields:
  - revised_photo: Parent file hash (chain topology)
  - revision_reason: Why revision was created ('rotation', 'crop', 'exif_edit', etc.)
  - source_path: Original import source location
  - revision_timestamp: When revision was created

Design Rationale:
- ALL files (originals + versions) get UniquePhotos records
- Duplicate detection: Simple primary key lookup (O(1))
- Parent-child relationships: Foreign key chain via revised_photo
- Single source of truth: No redundant tables

Preserves:
- DatabaseMetadata, SourceDirectories, UnreliableDates, DeletedFiles
- All audit tables (ImportSession, FileProcessingLog, DuplicateMapping, AuditRetentionSettings)

Schema Version: 4 → 5
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def migrate_database(database_path):
    """
    Migrate database to schema v5 with unified UniquePhotos table.

    WARNING: This is a breaking change requiring fresh imports.
    All existing UniquePhotos data will be lost.

    Args:
        database_path: Path to the SQLite database file

    Returns:
        bool: True if migration succeeded, False otherwise
    """
    logger.info("=" * 80)
    logger.info("STARTING DATABASE MIGRATION: Schema v5 - Unified UniquePhotos")
    logger.info(f"Database: {database_path}")
    logger.info("⚠️  WARNING: This is a BREAKING CHANGE - fresh imports required")
    logger.info("=" * 80)

    try:
        conn = sqlite3.connect(database_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=OFF")  # Disable for table drops
        cursor = conn.cursor()

        # Check current schema version
        cursor.execute("PRAGMA table_info(DatabaseMetadata)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'schema_version' in columns:
            cursor.execute("SELECT schema_version FROM DatabaseMetadata WHERE id = 1")
            result = cursor.fetchone()
            current_version = result[0] if result else 1
            logger.info(f"Current schema version: {current_version}")

            if current_version >= 5:
                logger.info("Database already migrated to schema version 5 or higher")
                logger.info("Migration skipped")
                conn.close()
                return True
        else:
            current_version = 1
            logger.info("No schema_version column found, assuming version 1")

        # Verify we're at schema version 4
        if current_version < 4:
            logger.warning("Schema version is less than 4")
            logger.warning("Please run previous migrations first:")
            logger.warning("  1. add_modifications_support.py (v1 → v3)")
            logger.warning("  2. add_deletion_tracking.py (v3 → v4)")
            conn.close()
            return False

        # Begin migration transaction
        logger.info("-" * 60)
        logger.info("Phase 1: Dropping obsolete tables...")

        # Drop obsolete tables (no longer needed with unified schema)
        obsolete_tables = [
            'FileHashHistory',       # Replaced by UniquePhotos primary key lookup
            'FileVersions',          # Merged into UniquePhotos
            'ModificationSession',   # No longer used
            'ModificationLog'        # No longer used
        ]

        for table in obsolete_tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
            logger.info(f"  ✓ Dropped table: {table}")

        logger.info("✓ Obsolete tables removed")

        # Drop and recreate UniquePhotos with new schema
        logger.info("-" * 60)
        logger.info("Phase 2: Recreating UniquePhotos table with v5 schema...")

        # Backup note
        logger.warning("⚠️  All existing UniquePhotos data will be lost")
        logger.warning("⚠️  Fresh import of photos required after migration")

        cursor.execute("DROP TABLE IF EXISTS UniquePhotos")
        logger.info("  ✓ Dropped old UniquePhotos table")

        # Create new UniquePhotos table with revision tracking
        cursor.execute("""
            CREATE TABLE UniquePhotos (
                -- Identity
                file_hash TEXT PRIMARY KEY,              -- SHA-256 hash of THIS file
                partial_hash TEXT,                       -- First N bytes hash for quick comparison
                partial_hash_bytes INTEGER,              -- Bytes used for partial hash (typically 16384)

                -- File Information
                file_size INTEGER NOT NULL,              -- Size in bytes
                file_name TEXT NOT NULL,                 -- Current location (archive or version storage)
                source_path TEXT,                        -- Original import source (NULL for versions)

                -- Revision Tracking (NEW in v5)
                revised_photo TEXT,                      -- Parent file hash (NULL if original import)
                revision_reason TEXT,                    -- 'rotation', 'crop', 'color_adjust', 'exif_edit', etc.
                revision_timestamp TEXT,                 -- When revision was created (ISO 8601)

                -- Date Information
                create_datetime TEXT,                    -- ISO 8601 timestamp
                create_year TEXT,                        -- YYYY
                create_month TEXT,                       -- MM (zero-padded)
                create_day TEXT,                         -- DD (zero-padded)

                -- Constraints
                FOREIGN KEY (revised_photo) REFERENCES UniquePhotos(file_hash),
                CHECK (revised_photo IS NULL OR revision_reason IS NOT NULL)
            )
        """)
        logger.info("  ✓ Created new UniquePhotos table with revision tracking")

        # Create indexes for UniquePhotos
        logger.info("Creating UniquePhotos indexes...")

        indexes = [
            ("idx_unique_partial_hash", "partial_hash"),
            ("idx_unique_revised", "revised_photo"),
            ("idx_unique_source", "source_path"),
            ("idx_unique_year", "create_year"),
            ("idx_unique_date", "create_year, create_month, create_day")
        ]

        for idx_name, idx_columns in indexes:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON UniquePhotos({idx_columns})")
            logger.info(f"  ✓ Created index: {idx_name}")

        logger.info(f"✓ UniquePhotos indexes created ({len(indexes)} indexes)")

        # Clear UnreliableDates table (references old file hashes)
        logger.info("-" * 60)
        logger.info("Phase 3: Clearing UnreliableDates table...")

        cursor.execute("DELETE FROM UnreliableDates")
        deleted_count = cursor.rowcount
        logger.info(f"  ✓ Cleared {deleted_count} records from UnreliableDates")
        logger.info("  ℹ  Records will be repopulated during fresh import")

        # Clear DeletedFiles table (references old file hashes)
        logger.info("Clearing DeletedFiles table...")

        cursor.execute("DELETE FROM DeletedFiles")
        deleted_count = cursor.rowcount
        logger.info(f"  ✓ Cleared {deleted_count} records from DeletedFiles")

        # Reset total_photos counter in DatabaseMetadata
        logger.info("Resetting photo counter in DatabaseMetadata...")

        cursor.execute("""
            UPDATE DatabaseMetadata
            SET total_photos = 0
            WHERE id = 1
        """)
        logger.info("  ✓ Reset total_photos to 0")

        # Update schema version
        logger.info("-" * 60)
        logger.info("Phase 4: Updating schema version to 5...")

        cursor.execute("""
            UPDATE DatabaseMetadata
            SET schema_version = 5
            WHERE id = 1
        """)
        logger.info("✓ Schema version updated to 5")

        # Re-enable foreign keys
        cursor.execute("PRAGMA foreign_keys=ON")

        # Commit transaction
        conn.commit()
        conn.close()

        logger.info("=" * 80)
        logger.info("✓✓✓ DATABASE MIGRATION COMPLETED SUCCESSFULLY ✓✓✓")
        logger.info("=" * 80)
        logger.info("Migration summary:")
        logger.info("  • Dropped obsolete tables:")
        logger.info("    - FileHashHistory (replaced by UniquePhotos PK lookup)")
        logger.info("    - FileVersions (merged into UniquePhotos)")
        logger.info("    - ModificationSession (no longer used)")
        logger.info("    - ModificationLog (no longer used)")
        logger.info("  • Recreated UniquePhotos with v5 schema:")
        logger.info("    - Added: revised_photo, revision_reason, source_path, revision_timestamp")
        logger.info("    - Created 5 indexes for performance")
        logger.info("  • Cleared UnreliableDates and DeletedFiles tables")
        logger.info("  • Reset total_photos counter to 0")
        logger.info("  • Updated schema version: 4 → 5")
        logger.info("=" * 80)
        logger.info("")
        logger.info("⚠️  IMPORTANT: Fresh import of photos required")
        logger.info("⚠️  All previous file records have been cleared")
        logger.info("⚠️  Preserved: Database config, source directories, audit history")
        logger.info("=" * 80)

        return True

    except Exception as e:
        logger.error("=" * 80)
        logger.error("✗✗✗ DATABASE MIGRATION FAILED ✗✗✗")
        logger.error(f"Error: {e}", exc_info=True)
        logger.error("=" * 80)

        try:
            conn.rollback()
            conn.close()
        except:
            pass

        return False


if __name__ == "__main__":
    # For testing migration script standalone
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    if len(sys.argv) < 2:
        print("Usage: python schema_v5.py <database_path>")
        sys.exit(1)

    database_path = sys.argv[1]

    print("\n" + "=" * 80)
    print("⚠️  WARNING: BREAKING CHANGE - FRESH IMPORT REQUIRED")
    print("=" * 80)
    print("This migration will:")
    print("  1. Drop FileHashHistory, FileVersions, ModificationSession, ModificationLog tables")
    print("  2. Recreate UniquePhotos table with new schema")
    print("  3. Clear all existing photo records")
    print("")
    print("Preserved:")
    print("  • Database configuration and settings")
    print("  • Source directory configurations")
    print("  • Import audit history")
    print("")

    response = input("Continue with migration? (yes/no): ").strip().lower()

    if response != 'yes':
        print("\n✗ Migration cancelled by user")
        sys.exit(0)

    print("\nStarting migration...\n")
    success = migrate_database(database_path)

    if success:
        print("\n✓ Migration completed successfully")
        print("\n⚠️  Next step: Re-import photos using the Setup tab")
        sys.exit(0)
    else:
        print("\n✗ Migration failed - check logs for details")
        sys.exit(1)
