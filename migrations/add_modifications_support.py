"""
Database Migration: Add File Modification and Version Control Support

Adds tables for:
- FileVersions: Complete version history for all file modifications
- ModificationSession: Session tracking for modification operations
- ModificationLog: Per-file operation logging

Enhances:
- FileHashHistory: Adds version_id column for version tracking

Schema Version: 1 → 3
"""

import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def migrate_database(database_path):
    """
    Migrate database to support file modifications and version control.

    Args:
        database_path: Path to the SQLite database file

    Returns:
        bool: True if migration succeeded, False otherwise
    """
    logger.info("=" * 80)
    logger.info("STARTING DATABASE MIGRATION: Add Modifications Support")
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

            if current_version >= 3:
                logger.info("Database already migrated to schema version 3 or higher")
                logger.info("Migration skipped")
                conn.close()
                return True
        else:
            current_version = 1
            logger.info("No schema_version column found, assuming version 1")

        # Begin migration transaction
        logger.info("-" * 60)
        logger.info("Creating FileVersions table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FileVersions (
                version_id TEXT PRIMARY KEY,
                file_hash TEXT NOT NULL,
                parent_version_id TEXT,
                original_hash TEXT NOT NULL,
                version_number INTEGER NOT NULL,

                storage_path TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,

                modification_session_id TEXT,
                modification_type TEXT,
                modification_params TEXT,

                file_size INTEGER,
                image_width INTEGER,
                image_height INTEGER,
                image_format TEXT,

                created_timestamp TEXT NOT NULL,

                FOREIGN KEY (parent_version_id) REFERENCES FileVersions(version_id),
                FOREIGN KEY (original_hash) REFERENCES UniquePhotos(original_hash),
                FOREIGN KEY (modification_session_id) REFERENCES ModificationSession(session_id)
            )
        """)
        logger.info("✓ FileVersions table created")

        # Create indexes for FileVersions
        logger.info("Creating FileVersions indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fileversions_hash ON FileVersions(file_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fileversions_original ON FileVersions(original_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fileversions_parent ON FileVersions(parent_version_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fileversions_active ON FileVersions(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fileversions_session ON FileVersions(modification_session_id)")
        logger.info("✓ FileVersions indexes created (5 indexes)")

        # Create ModificationSession table
        logger.info("-" * 60)
        logger.info("Creating ModificationSession table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ModificationSession (
                session_id TEXT PRIMARY KEY,
                start_timestamp TEXT NOT NULL,
                end_timestamp TEXT,
                status TEXT DEFAULT 'running',

                operation_type TEXT NOT NULL,
                total_files_selected INTEGER DEFAULT 0,
                total_files_processed INTEGER DEFAULT 0,
                total_successful INTEGER DEFAULT 0,
                total_failed INTEGER DEFAULT 0,

                process_duration_seconds REAL DEFAULT 0,
                error_summary TEXT,
                notes TEXT,

                can_undo INTEGER DEFAULT 1,
                undo_session_id TEXT,
                is_undo_of TEXT
            )
        """)
        logger.info("✓ ModificationSession table created")

        # Create indexes for ModificationSession
        logger.info("Creating ModificationSession indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modsession_start ON ModificationSession(start_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modsession_status ON ModificationSession(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modsession_type ON ModificationSession(operation_type)")
        logger.info("✓ ModificationSession indexes created (3 indexes)")

        # Create ModificationLog table
        logger.info("-" * 60)
        logger.info("Creating ModificationLog table...")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ModificationLog (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,

                original_hash TEXT NOT NULL,
                input_version_id TEXT NOT NULL,
                output_version_id TEXT,
                input_hash TEXT NOT NULL,
                output_hash TEXT,

                operation_type TEXT NOT NULL,
                operation_params TEXT NOT NULL,

                input_path TEXT NOT NULL,
                output_path TEXT,

                status TEXT NOT NULL,
                process_timestamp TEXT NOT NULL,
                duration_ms INTEGER,

                error_code TEXT,
                error_message TEXT,
                error_traceback TEXT,

                FOREIGN KEY (session_id) REFERENCES ModificationSession(session_id) ON DELETE CASCADE,
                FOREIGN KEY (original_hash) REFERENCES UniquePhotos(original_hash),
                FOREIGN KEY (input_version_id) REFERENCES FileVersions(version_id),
                FOREIGN KEY (output_version_id) REFERENCES FileVersions(version_id)
            )
        """)
        logger.info("✓ ModificationLog table created")

        # Create indexes for ModificationLog
        logger.info("Creating ModificationLog indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modlog_session ON ModificationLog(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modlog_original ON ModificationLog(original_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modlog_input_version ON ModificationLog(input_version_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modlog_output_version ON ModificationLog(output_version_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_modlog_status ON ModificationLog(status)")
        logger.info("✓ ModificationLog indexes created (5 indexes)")

        # Enhance FileHashHistory table
        logger.info("-" * 60)
        logger.info("Enhancing FileHashHistory table...")

        # Check if version_id column already exists
        cursor.execute("PRAGMA table_info(FileHashHistory)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'version_id' not in columns:
            cursor.execute("ALTER TABLE FileHashHistory ADD COLUMN version_id TEXT")
            logger.info("✓ Added version_id column to FileHashHistory")

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_hashhist_version ON FileHashHistory(version_id)")
            logger.info("✓ Created index on version_id column")
        else:
            logger.info("✓ version_id column already exists in FileHashHistory")

        # Update schema version
        logger.info("-" * 60)
        logger.info("Updating schema version to 3...")

        cursor.execute("""
            UPDATE DatabaseMetadata
            SET schema_version = 3
            WHERE id = 1
        """)
        logger.info("✓ Schema version updated to 3")

        # Commit transaction
        conn.commit()
        conn.close()

        logger.info("=" * 80)
        logger.info("✓✓✓ DATABASE MIGRATION COMPLETED SUCCESSFULLY ✓✓✓")
        logger.info("=" * 80)
        logger.info("Migration summary:")
        logger.info("  • Created FileVersions table with 5 indexes")
        logger.info("  • Created ModificationSession table with 3 indexes")
        logger.info("  • Created ModificationLog table with 5 indexes")
        logger.info("  • Enhanced FileHashHistory with version_id column + index")
        logger.info("  • Updated schema version: 1 → 3")
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
        print("Usage: python add_modifications_support.py <database_path>")
        sys.exit(1)

    database_path = sys.argv[1]
    success = migrate_database(database_path)

    if success:
        print("\n✓ Migration completed successfully")
        sys.exit(0)
    else:
        print("\n✗ Migration failed - check logs for details")
        sys.exit(1)
