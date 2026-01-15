"""
Triage Database Management

Provides database operations for triage-specific tables:
- TriageActions: Track marking/unmarking of files
- ThumbnailCache: Track disk-cached thumbnails
- FavoritesArchive: Configuration for favorites

Reuses PhotoDatabase context manager from DuplicateFileDetection.py
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import sys
import os

# Add parent directory to path to import existing modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from DuplicateFileDetection import PhotoDatabase

logger = logging.getLogger(__name__)


class TriageDatabase:
    """
    Helper class for triage-specific database operations.

    Uses PhotoDatabase context manager for connection management.
    All methods assume tables have been created via migrate_database.sql
    """

    def __init__(self, db_path: str):
        """
        Initialize triage database helper.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path

    def ensure_triage_tables(self):
        """
        Ensure all triage tables exist and are up-to-date.
        Runs migration script and upgrades schema if needed.
        """
        logger.info(f"{'='*80}")
        logger.info(f"ENSURING TRIAGE TABLES")
        logger.info(f"  Database: {self.db_path}")
        logger.info(f"{'-'*60}")

        migration_script = Path(__file__).parent / "migrate_database.sql"

        if not migration_script.exists():
            logger.error(f"✗ Migration script not found: {migration_script}")
            raise FileNotFoundError(f"Migration script not found: {migration_script}")

        with open(migration_script, 'r') as f:
            sql_script = f.read()

        with PhotoDatabase(self.db_path) as db:
            # Run migration script (creates tables if they don't exist)
            db.conn.executescript(sql_script)

            # Check and upgrade ThumbnailCache schema if needed
            cursor = db.conn.cursor()
            cursor.execute("PRAGMA table_info(ThumbnailCache)")
            columns = [row[1] for row in cursor.fetchall()]

            # Add file_modified_timestamp column if missing
            if 'file_modified_timestamp' not in columns:
                logger.info("  Upgrading ThumbnailCache: adding file_modified_timestamp column")
                cursor.execute("""
                    ALTER TABLE ThumbnailCache
                    ADD COLUMN file_modified_timestamp TEXT NOT NULL DEFAULT ''
                """)
                logger.info("  ✓ Added file_modified_timestamp column")

            # Remove obsolete file_size_bytes column if it exists (can't drop in SQLite, just ignore it)
            if 'file_size_bytes' in columns and 'file_modified_timestamp' in columns:
                logger.debug("  Note: Obsolete file_size_bytes column exists but is unused")

            db.commit()

        logger.info(f"✓ Triage tables ensured and upgraded")
        logger.info(f"{'='*80}")

    # ========================================================================
    # TriageActions - Mark/Unmark Operations
    # ========================================================================

    def mark_file(self, file_hash: str, action_type: str, notes: str = None) -> int:
        """
        Mark file for action (delete/favorite/date_correction).

        Args:
            file_hash: SHA-256 hash from UniquePhotos
            action_type: 'delete', 'favorite', or 'date_correction'
            notes: Optional notes about the action

        Returns:
            Row ID of inserted record
        """
        if action_type not in ('delete', 'favorite', 'date_correction'):
            raise ValueError(f"Invalid action_type: {action_type}")

        timestamp = datetime.now().isoformat()

        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("""
                INSERT INTO TriageActions
                (file_hash, action_type, marked_timestamp, notes)
                VALUES (?, ?, ?, ?)
            """, (file_hash, action_type, timestamp, notes))

            row_id = db.cursor.lastrowid
            db.commit()

        logger.debug(f"Marked {file_hash[:8]}... for {action_type}")
        return row_id

    def unmark_file(self, file_hash: str, action_type: str) -> int:
        """
        Unmark file (undo action).

        Sets unmarked_timestamp for all active marks of this type.

        Args:
            file_hash: SHA-256 hash
            action_type: 'delete', 'favorite', or 'date_correction'

        Returns:
            Number of records updated
        """
        timestamp = datetime.now().isoformat()

        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("""
                UPDATE TriageActions
                SET unmarked_timestamp = ?
                WHERE file_hash = ?
                  AND action_type = ?
                  AND unmarked_timestamp IS NULL
            """, (timestamp, file_hash, action_type))

            count = db.cursor.rowcount
            db.commit()

        logger.debug(f"Unmarked {count} {action_type} marks for {file_hash[:8]}...")
        return count

    def get_marked_files(self, action_type: str = None,
                        active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get all marked files.

        Args:
            action_type: Filter by action type, or None for all types
            active_only: If True, only return files not yet unmarked

        Returns:
            List of dicts with keys: file_hash, action_type, marked_timestamp,
                                    unmarked_timestamp, notes
        """
        query = "SELECT * FROM TriageActions WHERE 1=1"
        params = []

        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)

        if active_only:
            query += " AND unmarked_timestamp IS NULL"

        query += " ORDER BY marked_timestamp DESC"

        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute(query, params)
            rows = db.cursor.fetchall()

        results = []
        for row in rows:
            results.append({
                'id': row[0],
                'file_hash': row[1],
                'action_type': row[2],
                'marked_timestamp': row[3],
                'unmarked_timestamp': row[4],
                'notes': row[5]
            })

        return results

    def get_marked_hashes(self, action_type: str = None) -> Set[str]:
        """
        Get set of file hashes that are actively marked.

        Args:
            action_type: Filter by type, or None for all types

        Returns:
            Set of file hashes
        """
        marked_files = self.get_marked_files(action_type, active_only=True)
        return {f['file_hash'] for f in marked_files}

    def is_file_marked(self, file_hash: str, action_type: str) -> bool:
        """
        Check if file is actively marked for action.

        Args:
            file_hash: SHA-256 hash
            action_type: 'delete', 'favorite', or 'date_correction'

        Returns:
            True if file has active mark of this type
        """
        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("""
                SELECT COUNT(*) FROM TriageActions
                WHERE file_hash = ?
                  AND action_type = ?
                  AND unmarked_timestamp IS NULL
            """, (file_hash, action_type))

            count = db.cursor.fetchone()[0]

        return count > 0

    # ========================================================================
    # ThumbnailCache - Disk Cache Management
    # ========================================================================

    def add_thumbnail(self, file_hash: str, thumbnail_path: str,
                     thumbnail_size: int, file_modified_time: float):
        """
        Record thumbnail in cache.

        Args:
            file_hash: SHA-256 hash
            thumbnail_path: Path to cached thumbnail file
            thumbnail_size: Size in pixels (256, 512, 1024)
            file_modified_time: Modification time of original file (timestamp)
        """
        timestamp = datetime.now().isoformat()
        file_modified = datetime.fromtimestamp(file_modified_time).isoformat()

        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("""
                INSERT OR REPLACE INTO ThumbnailCache
                (file_hash, thumbnail_path, thumbnail_size,
                 created_timestamp, last_accessed_timestamp, file_modified_timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (file_hash, thumbnail_path, thumbnail_size,
                  timestamp, timestamp, file_modified))

            db.commit()

        logger.debug(f"Added thumbnail to cache: {file_hash[:8]}... size={thumbnail_size}")

    def get_thumbnail(self, file_hash: str, thumbnail_size: int) -> Optional[Dict[str, Any]]:
        """
        Get thumbnail cache entry.

        Updates last_accessed_timestamp on hit.

        Args:
            file_hash: SHA-256 hash
            thumbnail_size: Size in pixels

        Returns:
            Dict with cache entry or None if not found
        """
        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("""
                SELECT * FROM ThumbnailCache
                WHERE file_hash = ? AND thumbnail_size = ?
            """, (file_hash, thumbnail_size))

            row = db.cursor.fetchone()

            if row:
                # Update last accessed
                timestamp = datetime.now().isoformat()
                db.cursor.execute("""
                    UPDATE ThumbnailCache
                    SET last_accessed_timestamp = ?
                    WHERE file_hash = ? AND thumbnail_size = ?
                """, (timestamp, file_hash, thumbnail_size))
                db.commit()

                return {
                    'id': row[0],
                    'file_hash': row[1],
                    'thumbnail_path': row[2],
                    'thumbnail_size': row[3],
                    'created_timestamp': row[4],
                    'last_accessed_timestamp': row[5],
                    'file_modified_timestamp': row[6]
                }

        return None

    def cleanup_lru_thumbnails(self, max_size_bytes: int) -> int:
        """
        Clean up least recently used thumbnails to stay under size limit.

        Args:
            max_size_bytes: Maximum total cache size in bytes

        Returns:
            Number of thumbnails deleted
        """
        # Calculate current cache size
        total_size = 0
        thumbnails = []

        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("""
                SELECT file_hash, thumbnail_path, last_accessed_timestamp
                FROM ThumbnailCache
                ORDER BY last_accessed_timestamp ASC
            """)

            for row in db.cursor.fetchall():
                file_hash, thumb_path, last_accessed = row

                if os.path.exists(thumb_path):
                    file_size = os.path.getsize(thumb_path)
                    total_size += file_size
                    thumbnails.append((file_hash, thumb_path, file_size, last_accessed))

        # If under limit, nothing to do
        if total_size <= max_size_bytes:
            logger.debug(f"Cache size OK: {total_size / 1024 / 1024:.1f} MB")
            return 0

        # Delete oldest thumbnails until under limit
        deleted_count = 0
        target_size = int(max_size_bytes * 0.9)  # Leave 10% headroom

        with PhotoDatabase(self.db_path) as db:
            for file_hash, thumb_path, file_size, _ in thumbnails:
                if total_size <= target_size:
                    break

                # Delete file
                if os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                        total_size -= file_size
                        deleted_count += 1
                    except OSError as e:
                        logger.warning(f"Failed to delete {thumb_path}: {e}")

                # Delete from database
                db.cursor.execute("""
                    DELETE FROM ThumbnailCache
                    WHERE file_hash = ?
                """, (file_hash,))

            db.commit()

        logger.info(f"Cleaned up {deleted_count} thumbnails, "
                   f"new size: {total_size / 1024 / 1024:.1f} MB")
        return deleted_count

    def delete_thumbnails_for_hash(self, file_hash: str) -> int:
        """
        Delete all cached thumbnails for a specific file hash.

        Used when file is modified (rotated, edited) and hash changes.
        Removes thumbnails from both database and disk.

        Args:
            file_hash: SHA-256 hash to delete thumbnails for

        Returns:
            Number of thumbnails deleted
        """
        deleted_count = 0

        with PhotoDatabase(self.db_path) as db:
            # Get all thumbnail paths for this hash
            db.cursor.execute("""
                SELECT thumbnail_path
                FROM ThumbnailCache
                WHERE file_hash = ?
            """, (file_hash,))

            thumbnail_paths = [row[0] for row in db.cursor.fetchall()]

            # Delete files from disk
            for thumb_path in thumbnail_paths:
                if os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                        deleted_count += 1
                        logger.debug(f"Deleted thumbnail file: {thumb_path}")
                    except OSError as e:
                        logger.warning(f"Failed to delete {thumb_path}: {e}")

            # Delete from database
            db.cursor.execute("""
                DELETE FROM ThumbnailCache
                WHERE file_hash = ?
            """, (file_hash,))

            db.commit()

        if deleted_count > 0:
            logger.debug(f"Deleted {deleted_count} thumbnails for hash {file_hash[:8]}...")

        return deleted_count

    # ========================================================================
    # FavoritesArchive - Configuration
    # ========================================================================

    def get_favorites_config(self) -> Optional[Dict[str, Any]]:
        """
        Get favorites archive configuration.

        Returns:
            Dict with archive_location and auto_copy_enabled, or None
        """
        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("SELECT * FROM FavoritesArchive WHERE id = 1")
            row = db.cursor.fetchone()

        if row:
            return {
                'id': row[0],
                'archive_location': row[1],
                'auto_copy_enabled': bool(row[2])
            }

        return None

    def set_favorites_config(self, archive_location: str, auto_copy_enabled: bool = False):
        """
        Set favorites archive configuration.

        Args:
            archive_location: Path to favorites archive
            auto_copy_enabled: If True, auto-copy marked favorites
        """
        with PhotoDatabase(self.db_path) as db:
            db.cursor.execute("""
                INSERT OR REPLACE INTO FavoritesArchive
                (id, archive_location, auto_copy_enabled)
                VALUES (1, ?, ?)
            """, (archive_location, int(auto_copy_enabled)))

            db.commit()

        logger.info(f"Set favorites archive: {archive_location}")


if __name__ == '__main__':
    # Test database operations
    import tempfile

    logging.basicConfig(level=logging.DEBUG)

    # Create test database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    try:
        # Initialize
        triage_db = TriageDatabase(test_db_path)
        triage_db.ensure_triage_tables()
        print("✓ Tables created")

        # Test marking
        test_hash = "abc123def456"
        triage_db.mark_file(test_hash, 'delete', notes='Test delete')
        print("✓ File marked for deletion")

        # Check if marked
        assert triage_db.is_file_marked(test_hash, 'delete')
        print("✓ File is marked")

        # Get marked files
        marked = triage_db.get_marked_files('delete')
        assert len(marked) == 1
        print(f"✓ Retrieved {len(marked)} marked file(s)")

        # Unmark
        count = triage_db.unmark_file(test_hash, 'delete')
        assert count == 1
        assert not triage_db.is_file_marked(test_hash, 'delete')
        print("✓ File unmarked")

        # Test favorites config
        triage_db.set_favorites_config('/tmp/favorites', auto_copy_enabled=True)
        config = triage_db.get_favorites_config()
        assert config['archive_location'] == '/tmp/favorites'
        assert config['auto_copy_enabled'] == True
        print("✓ Favorites config saved and retrieved")

        print("\nAll tests passed!")

    finally:
        # Clean up
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
            print(f"Cleaned up test database")
