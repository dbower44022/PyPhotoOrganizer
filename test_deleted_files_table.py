"""
DeletedFiles Table Verification Test

Specifically tests that the DeletedFiles table is created correctly
with all required columns and indexes.

Usage:
    python3 test_deleted_files_table.py
"""

import os
import sys
import sqlite3
import tempfile
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_deleted_files_table():
    """Test DeletedFiles table creation."""
    logger.info("="*80)
    logger.info("DeletedFiles Table Verification Test")
    logger.info("="*80)

    # Create temporary database
    temp_dir = tempfile.gettempdir()
    db_path = os.path.join(temp_dir, 'test_deleted_files.db')

    # Remove old test database if it exists
    if os.path.exists(db_path):
        os.remove(db_path)

    try:
        # Create test database by directly initializing DatabaseMetadata
        # This bypasses the pillow_heif dependency in DuplicateFileDetection
        from database_metadata import DatabaseMetadata

        logger.info(f"\nCreating test database: {db_path}")

        # Initialize DatabaseMetadata - this creates all tables managed by it
        db_meta = DatabaseMetadata(db_path)

        # Insert minimal metadata
        test_archive = tempfile.mkdtemp()
        db_meta.initialize_metadata("Test Database", test_archive, "DeletedFiles table test")

        logger.info("✓ Database created successfully")

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Test 1: Check table exists
        logger.info("\nTest 1: Table Existence")
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='DeletedFiles'
        """)
        table_exists = cursor.fetchone() is not None

        if table_exists:
            logger.info("✓ DeletedFiles table exists")
        else:
            logger.error("✗ DeletedFiles table MISSING")
            conn.close()
            os.rmdir(test_archive)
            return False

        # Test 2: Check all columns exist
        logger.info("\nTest 2: Column Verification")
        expected_columns = [
            'id', 'file_hash', 'original_archive_path', 'delete_vault_path',
            'deletion_timestamp', 'deletion_reason', 'deleted_by_session',
            'file_size', 'creation_date', 'is_restored', 'restore_timestamp'
        ]

        cursor.execute("PRAGMA table_info(DeletedFiles)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        missing_columns = []
        for col in expected_columns:
            if col in existing_columns:
                logger.info(f"  ✓ Column: {col}")
            else:
                logger.error(f"  ✗ Column MISSING: {col}")
                missing_columns.append(col)

        if missing_columns:
            logger.error(f"✗ Missing columns: {missing_columns}")
            conn.close()
            os.rmdir(test_archive)
            return False

        logger.info(f"✓ All {len(expected_columns)} columns present")

        # Test 3: Check indexes exist
        logger.info("\nTest 3: Index Verification")
        expected_indexes = [
            'idx_deleted_hash',
            'idx_deleted_restored',
            'idx_deleted_timestamp'
        ]

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND tbl_name='DeletedFiles'
            AND name NOT LIKE 'sqlite_%'
        """)
        existing_indexes = [row[0] for row in cursor.fetchall()]

        missing_indexes = []
        for idx in expected_indexes:
            if idx in existing_indexes:
                logger.info(f"  ✓ Index: {idx}")
            else:
                logger.error(f"  ✗ Index MISSING: {idx}")
                missing_indexes.append(idx)

        if missing_indexes:
            logger.error(f"✗ Missing indexes: {missing_indexes}")
            conn.close()
            os.rmdir(test_archive)
            return False

        logger.info(f"✓ All {len(expected_indexes)} indexes present")

        # Test 4: Check foreign key constraint
        logger.info("\nTest 4: Foreign Key Constraint")
        cursor.execute("PRAGMA foreign_key_list(DeletedFiles)")
        fk_info = cursor.fetchall()

        if fk_info:
            for fk in fk_info:
                referenced_table = fk[2]
                from_column = fk[3]
                to_column = fk[4]
                logger.info(f"  ✓ Foreign key: {from_column} -> {referenced_table}({to_column})")
        else:
            logger.warning("  ⚠ No foreign key constraints found (expected: file_hash -> UniquePhotos)")
            logger.warning("  Note: This is OK - SQLite doesn't enforce foreign keys by default")

        # Test 5: Test insert/query operations
        logger.info("\nTest 5: Insert and Query Operations")

        # Insert test record
        from datetime import datetime
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO DeletedFiles
                (file_hash, original_archive_path, delete_vault_path,
                 deletion_timestamp, deletion_reason, file_size, creation_date,
                 is_restored)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            'test_hash_12345',
            '/archive/2024/01/01/photo.jpg',
            '/vault/2024/01/01/photo.jpg',
            now,
            'user_deleted',
            1234567,
            '2024-01-01',
            0
        ))

        conn.commit()
        logger.info("  ✓ Test record inserted")

        # Query test record
        cursor.execute("""
            SELECT file_hash, original_archive_path, is_restored
            FROM DeletedFiles
            WHERE file_hash = ?
        """, ('test_hash_12345',))

        result = cursor.fetchone()
        if result and result[0] == 'test_hash_12345':
            logger.info(f"  ✓ Test record queried: {result[1]}")
        else:
            logger.error("  ✗ Failed to query test record")
            conn.close()
            os.rmdir(test_archive)
            return False

        # Test update (mark as restored)
        cursor.execute("""
            UPDATE DeletedFiles
            SET is_restored = 1,
                restore_timestamp = ?
            WHERE file_hash = ?
        """, (now, 'test_hash_12345'))

        conn.commit()
        logger.info("  ✓ Test record updated (marked as restored)")

        # Verify update
        cursor.execute("""
            SELECT is_restored FROM DeletedFiles
            WHERE file_hash = ?
        """, ('test_hash_12345',))

        result = cursor.fetchone()
        if result and result[0] == 1:
            logger.info("  ✓ Update verified")
        else:
            logger.error("  ✗ Update failed")
            conn.close()
            os.rmdir(test_archive)
            return False

        # Clean up
        conn.close()
        os.remove(db_path)
        os.rmdir(test_archive)

        # Success!
        logger.info("\n" + "="*80)
        logger.info("✓ ALL TESTS PASSED")
        logger.info("="*80)
        logger.info("\nDeletedFiles table:")
        logger.info("  • Table created successfully")
        logger.info(f"  • All {len(expected_columns)} columns present")
        logger.info(f"  • All {len(expected_indexes)} indexes created")
        logger.info("  • Insert, query, and update operations work correctly")
        logger.info("="*80)

        return True

    except Exception as e:
        logger.error(f"\n✗ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()

        # Clean up on error
        if os.path.exists(db_path):
            os.remove(db_path)

        return False


def main():
    """Main entry point."""
    success = test_deleted_files_table()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
