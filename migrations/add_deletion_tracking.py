"""
Database Migration: Add File Deletion and Restore Support

Adds tables for:
- DeletedFiles: Tracks files moved to Delete Vault with restore capability

Enhances:
- DatabaseMetadata: Adds delete_vault_location column for Delete Vault configuration

Schema Version: 3 → 4
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def migrate_database(database_path):
    """
    Migrate database to support file deletion tracking and restore.

    Args:
        database_path: Path to the SQLite database file

    Returns:
        bool: True if migration succeeded, False otherwise
    """
    logger.info("=" * 80)
    logger.info("STARTING DATABASE MIGRATION: Add Deletion Tracking Support")
    logger.info(f"Database: {database_path}")
    logger.info("=" * 80)

    try:
        conn = sqlite3.connect(database_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        cursor = conn.cursor()

        # Check current schema version
        cursor.execute("PRAGMA table_info(DatabaseMetadata)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'schema_version' in columns:
            cursor.execute("SELECT schema_version FROM DatabaseMetadata WHERE id = 1")
            result = cursor.fetchone()
            current_version = result[0] if result else 1
            logger.info(f"Current schema version: {current_version}")

            if current_version >= 4:
                logger.info("Database already migrated to schema version 4 or higher")
                logger.info("Migration skipped")
                conn.close()
                return True
        else:
            current_version = 1
            logger.info("No schema_version column found, assuming version 1")

        # Verify we're at schema version 3 (modifications support must be present)
        if current_version < 3:
            logger.warning("Schema version is less than 3 - modifications support missing")
            logger.warning("Please run add_modifications_support.py migration first")
            conn.close()
            return False

        # Begin migration transaction
        logger.info("-" * 60)
        logger.info("Creating DeletedFiles table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS DeletedFiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_hash TEXT NOT NULL,
                original_archive_path TEXT NOT NULL,
                delete_vault_path TEXT NOT NULL,
                deletion_timestamp TEXT NOT NULL,
                deletion_reason TEXT,
                deleted_by_session TEXT,
                file_size INTEGER,
                creation_date TEXT,
                is_restored INTEGER DEFAULT 0,
                restore_timestamp TEXT,
                FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
            )
        """)
        logger.info("✓ DeletedFiles table created")

        # Create indexes for DeletedFiles
        logger.info("Creating DeletedFiles indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deleted_hash ON DeletedFiles(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deleted_restored ON DeletedFiles(is_restored)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deleted_timestamp ON DeletedFiles(deletion_timestamp)")
        logger.info("✓ DeletedFiles indexes created (3 indexes)")

        # Enhance DatabaseMetadata table
        logger.info("-" * 60)
        logger.info("Enhancing DatabaseMetadata table...")

        # Check if delete_vault_location column already exists
        cursor.execute("PRAGMA table_info(DatabaseMetadata)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'delete_vault_location' not in columns:
            cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN delete_vault_location TEXT")
            logger.info("✓ Added delete_vault_location column to DatabaseMetadata")
        else:
            logger.info("✓ delete_vault_location column already exists in DatabaseMetadata")

        # Update schema version
        logger.info("-" * 60)
        logger.info("Updating schema version to 4...")

        cursor.execute("""
            UPDATE DatabaseMetadata
            SET schema_version = 4
            WHERE id = 1
        """)
        logger.info("✓ Schema version updated to 4")

        # Commit transaction
        conn.commit()
        conn.close()

        logger.info("=" * 80)
        logger.info("✓✓✓ DATABASE MIGRATION COMPLETED SUCCESSFULLY ✓✓✓")
        logger.info("=" * 80)
        logger.info("Migration summary:")
        logger.info("  • Created DeletedFiles table with 3 indexes")
        logger.info("  • Enhanced DatabaseMetadata with delete_vault_location column")
        logger.info("  • Updated schema version: 3 → 4")
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
        print("Usage: python add_deletion_tracking.py <database_path>")
        sys.exit(1)

    database_path = sys.argv[1]
    success = migrate_database(database_path)

    if success:
        print("\n✓ Migration completed successfully")
        sys.exit(0)
    else:
        print("\n✗ Migration failed - check logs for details")
        sys.exit(1)
