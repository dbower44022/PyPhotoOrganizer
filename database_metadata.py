"""
Database Metadata Management

Manages database metadata including archive location, creation date, and statistics.
Each database is tied to a specific archive location.
"""

import sqlite3
import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


logger = logging.getLogger(__name__)


class DatabaseMetadata:
    """Manages database metadata and archive location binding."""

    METADATA_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS DatabaseMetadata (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            database_name TEXT NOT NULL,
            description TEXT,
            archive_location TEXT NOT NULL,
            video_archive_location TEXT,
            separate_video_archive INTEGER DEFAULT 0,
            created_date TEXT NOT NULL,
            last_used_date TEXT,
            schema_version INTEGER DEFAULT 1,
            total_photos INTEGER DEFAULT 0,
            organization_template TEXT DEFAULT '{YYYY}/{MM}/{DD}',
            file_type_organization TEXT DEFAULT 'combined',
            user_specified_unreliable_paths TEXT DEFAULT '[]',
            filename_template TEXT DEFAULT '{original_name}',
            enable_file_rename INTEGER DEFAULT 0,
            ignored_directories TEXT DEFAULT '[]',
            thumbnail_size INTEGER DEFAULT 200,
            thumbnail_cache_dir TEXT,
            preview_window_geometry TEXT,
            preview_window_visible INTEGER DEFAULT 1
        );
    """

    SOURCE_DIRECTORIES_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS SourceDirectories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            order_index INTEGER NOT NULL,
            added_date TEXT NOT NULL,
            last_scanned TEXT,
            enabled INTEGER DEFAULT 1
        );
    """

    UNRELIABLE_DATES_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS UnreliableDates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT NOT NULL,
            source_path TEXT NOT NULL,
            archive_path TEXT,
            original_archive_path TEXT,
            original_date TEXT,
            date_source TEXT,
            flag_reason TEXT,
            corrected_date TEXT,
            correction_timestamp TEXT,
            needs_reorganization INTEGER DEFAULT 0,
            FOREIGN KEY (file_hash) REFERENCES UniquePhotos(hash)
        );
    """

    FILE_RENAME_HISTORY_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS FileRenameHistory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            renamed_filename TEXT NOT NULL,
            rename_timestamp TEXT NOT NULL,
            FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
        );
    """

    THUMBNAIL_CACHE_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS ThumbnailCache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_hash TEXT NOT NULL,
            thumbnail_path TEXT NOT NULL,
            thumbnail_size INTEGER NOT NULL,
            created_timestamp TEXT NOT NULL,
            last_accessed_timestamp TEXT NOT NULL,
            file_size_bytes INTEGER,
            UNIQUE(file_hash, thumbnail_size)
        );
    """

    def __init__(self, database_path: str):
        """
        Initialize database metadata manager.

        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path
        self._ensure_metadata_table()
        self._ensure_source_directories_table()
        self._ensure_unreliable_dates_table()
        self._ensure_file_rename_history_table()
        self._ensure_thumbnail_cache_table()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection with proper settings for concurrency.

        Returns:
            sqlite3.Connection with timeout and WAL mode enabled
        """
        conn = sqlite3.connect(self.database_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _ensure_metadata_table(self):
        """Ensure the metadata table exists in the database with all columns."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.METADATA_TABLE_SCHEMA)

                # Check if new columns exist (for upgrading old databases)
                cursor.execute("PRAGMA table_info(DatabaseMetadata)")
                columns = [row[1] for row in cursor.fetchall()]

                # Add video_archive_location column if missing
                if 'video_archive_location' not in columns:
                    logger.info("Upgrading database: adding video_archive_location column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN video_archive_location TEXT")

                # Add separate_video_archive column if missing
                if 'separate_video_archive' not in columns:
                    logger.info("Upgrading database: adding separate_video_archive column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN separate_video_archive INTEGER DEFAULT 0")

                # Add organization_template column if missing
                if 'organization_template' not in columns:
                    logger.info("Upgrading database: adding organization_template column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN organization_template TEXT DEFAULT '{YYYY}/{MM}/{DD}'")

                # Add file_type_organization column if missing
                if 'file_type_organization' not in columns:
                    logger.info("Upgrading database: adding file_type_organization column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN file_type_organization TEXT DEFAULT 'combined'")

                # Add user_specified_unreliable_paths column if missing
                if 'user_specified_unreliable_paths' not in columns:
                    logger.info("Upgrading database: adding user_specified_unreliable_paths column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN user_specified_unreliable_paths TEXT DEFAULT '[]'")

                # Add filename_template column if missing
                if 'filename_template' not in columns:
                    logger.info("Upgrading database: adding filename_template column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN filename_template TEXT DEFAULT '{original_name}'")
                    # Set default value for existing rows
                    cursor.execute("UPDATE DatabaseMetadata SET filename_template = '{original_name}' WHERE filename_template IS NULL")

                # Add enable_file_rename column if missing
                if 'enable_file_rename' not in columns:
                    logger.info("Upgrading database: adding enable_file_rename column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN enable_file_rename INTEGER DEFAULT 0")
                    # Set default value for existing rows
                    cursor.execute("UPDATE DatabaseMetadata SET enable_file_rename = 0 WHERE enable_file_rename IS NULL")

                # Add ignored_directories column if missing
                if 'ignored_directories' not in columns:
                    logger.info("Upgrading database: adding ignored_directories column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN ignored_directories TEXT DEFAULT '[]'")
                    # Set default value for existing rows
                    cursor.execute("UPDATE DatabaseMetadata SET ignored_directories = '[]' WHERE ignored_directories IS NULL")

                # Add thumbnail_size column if missing
                if 'thumbnail_size' not in columns:
                    logger.info("Upgrading database: adding thumbnail_size column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN thumbnail_size INTEGER DEFAULT 200")

                # Add thumbnail_cache_dir column if missing
                if 'thumbnail_cache_dir' not in columns:
                    logger.info("Upgrading database: adding thumbnail_cache_dir column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN thumbnail_cache_dir TEXT")

                # Add preview_window_geometry column if missing
                if 'preview_window_geometry' not in columns:
                    logger.info("Upgrading database: adding preview_window_geometry column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN preview_window_geometry TEXT")

                # Add preview_window_visible column if missing
                if 'preview_window_visible' not in columns:
                    logger.info("Upgrading database: adding preview_window_visible column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN preview_window_visible INTEGER DEFAULT 1")

                conn.commit()
                logger.debug(f"Metadata table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create/upgrade metadata table: {e}")
            raise

    def _ensure_source_directories_table(self):
        """Ensure the SourceDirectories table exists in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.SOURCE_DIRECTORIES_TABLE_SCHEMA)

                conn.commit()
                logger.debug(f"SourceDirectories table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create SourceDirectories table: {e}")
            raise

    def _ensure_unreliable_dates_table(self):
        """Ensure the UnreliableDates table exists in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.UNRELIABLE_DATES_TABLE_SCHEMA)

                # Check if new columns exist (for upgrading old databases)
                cursor.execute("PRAGMA table_info(UnreliableDates)")
                columns = [row[1] for row in cursor.fetchall()]

                # Add original_archive_path column if missing
                if 'original_archive_path' not in columns:
                    logger.info("Upgrading database: adding original_archive_path column to UnreliableDates")
                    cursor.execute("ALTER TABLE UnreliableDates ADD COLUMN original_archive_path TEXT")

                conn.commit()
                logger.debug(f"UnreliableDates table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create UnreliableDates table: {e}")
            raise

    def _ensure_file_rename_history_table(self):
        """Ensure the FileRenameHistory table exists in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.FILE_RENAME_HISTORY_TABLE_SCHEMA)

                conn.commit()
                logger.debug(f"FileRenameHistory table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create FileRenameHistory table: {e}")
            raise

    def _ensure_thumbnail_cache_table(self):
        """Ensure the ThumbnailCache table exists in the database with correct schema."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if table exists and has old schema
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ThumbnailCache'")
                table_exists = cursor.fetchone()

                if table_exists:
                    # Check if old schema (has 'size' column instead of 'thumbnail_size')
                    cursor.execute("PRAGMA table_info(ThumbnailCache)")
                    columns = {row[1] for row in cursor.fetchall()}

                    # Old schema has 'size', new schema has 'thumbnail_size'
                    if 'size' in columns and 'thumbnail_size' not in columns:
                        logger.info("Migrating ThumbnailCache table to new schema")
                        # Drop old table (it's just a cache, safe to recreate)
                        cursor.execute("DROP TABLE ThumbnailCache")
                        cursor.execute("DROP INDEX IF EXISTS idx_thumbnail_cache_hash")
                        cursor.execute("DROP INDEX IF EXISTS idx_thumbnail_cache_accessed")

                # Create table with new schema (if not exists or after migration)
                cursor.execute(self.THUMBNAIL_CACHE_TABLE_SCHEMA)

                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thumbnail_cache_hash ON ThumbnailCache(file_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_thumbnail_cache_accessed ON ThumbnailCache(last_accessed_timestamp)")

                conn.commit()
                logger.debug(f"ThumbnailCache table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create ThumbnailCache table: {e}")
            raise

    def ensure_all_tables(self):
        """
        Ensure all required tables exist in the database.
        This includes both DatabaseMetadata and UniquePhotos tables.
        Useful for upgrading old databases.
        """
        try:
            # Ensure metadata table exists
            self._ensure_metadata_table()

            # Ensure UniquePhotos table exists
            import DuplicateFileDetection
            with DuplicateFileDetection.PhotoDatabase(self.database_path) as db:
                db.initialize_database()

            logger.info(f"All required tables ensured in {self.database_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to ensure all tables: {e}")
            return False

    def initialize_metadata(self, database_name: str, archive_location: str,
                          description: str = "") -> bool:
        """
        Initialize metadata for a new database.

        Args:
            database_name: User-friendly name for the database
            archive_location: Absolute path to the archive (destination) folder
            description: Optional description

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate archive location
            if not os.path.isabs(archive_location):
                raise ValueError("Archive location must be an absolute path")

            created_date = datetime.now().isoformat()

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if metadata already exists
                cursor.execute("SELECT COUNT(*) FROM DatabaseMetadata")
                count = cursor.fetchone()[0]

                if count > 0:
                    logger.warning(f"Metadata already exists for {self.database_path}")
                    return False

                # Insert metadata
                cursor.execute("""
                    INSERT INTO DatabaseMetadata
                    (id, database_name, description, archive_location, created_date, last_used_date, total_photos)
                    VALUES (1, ?, ?, ?, ?, ?, 0)
                """, (database_name, description, archive_location, created_date, created_date))

                conn.commit()
                logger.info(f"Initialized metadata for database: {database_name}")
                return True

        except Exception as e:
            logger.error(f"Failed to initialize metadata: {e}")
            raise

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """
        Get database metadata.

        Returns:
            Dictionary with metadata or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT database_name, description, archive_location, video_archive_location,
                           separate_video_archive, created_date, last_used_date, schema_version, total_photos,
                           organization_template, file_type_organization, enable_file_rename, filename_template,
                           thumbnail_size, thumbnail_cache_dir, preview_window_geometry, preview_window_visible
                    FROM DatabaseMetadata WHERE id = 1
                """)

                row = cursor.fetchone()
                if row:
                    return {
                        'database_name': row[0],
                        'description': row[1],
                        'archive_location': row[2],
                        'video_archive_location': row[3],
                        'separate_video_archive': bool(row[4]),
                        'created_date': row[5],
                        'last_used_date': row[6],
                        'schema_version': row[7],
                        'total_photos': row[8],
                        'organization_template': row[9] if len(row) > 9 else '{YYYY}/{MM}/{DD}',
                        'file_type_organization': row[10] if len(row) > 10 else 'combined',
                        'enable_file_rename': row[11] if len(row) > 11 else 0,
                        'filename_template': row[12] if len(row) > 12 else '{original_name}',
                        'thumbnail_size': row[13] if len(row) > 13 else 200,
                        'thumbnail_cache_dir': row[14] if len(row) > 14 else None,
                        'preview_window_geometry': row[15] if len(row) > 15 else None,
                        'preview_window_visible': row[16] if len(row) > 16 else 1
                    }
                return None

        except sqlite3.OperationalError:
            # Metadata table doesn't exist (old database)
            logger.warning(f"No metadata table in {self.database_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to get metadata: {e}")
            return None

    def get_archive_location(self) -> Optional[str]:
        """
        Get the archive location for this database.

        Returns:
            Archive location path or None if not found
        """
        metadata = self.get_metadata()
        return metadata['archive_location'] if metadata else None

    def get_video_archive_location(self) -> Optional[str]:
        """
        Get the video archive location for this database.

        Returns:
            Video archive location path or None if not set
        """
        metadata = self.get_metadata()
        return metadata.get('video_archive_location') if metadata else None

    def is_separate_video_archive_enabled(self) -> bool:
        """
        Check if separate video archive is enabled.

        Returns:
            True if separate video archive is enabled, False otherwise
        """
        metadata = self.get_metadata()
        return metadata.get('separate_video_archive', False) if metadata else False

    def set_video_archive(self, video_archive_location: str, enabled: bool = True) -> bool:
        """
        Set or update the video archive location.

        Args:
            video_archive_location: Path to video archive folder
            enabled: Whether to enable separate video archive

        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate path if enabling
            if enabled and video_archive_location:
                if not os.path.isabs(video_archive_location):
                    raise ValueError("Video archive location must be an absolute path")

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET video_archive_location = ?,
                        separate_video_archive = ?
                    WHERE id = 1
                """, (video_archive_location if enabled else None, 1 if enabled else 0))
                conn.commit()

                logger.info(f"Video archive {'enabled' if enabled else 'disabled'}: {video_archive_location if enabled else 'N/A'}")
                return True

        except Exception as e:
            logger.error(f"Failed to set video archive: {e}")
            return False

    def update_last_used(self):
        """Update the last used timestamp."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET last_used_date = ?
                    WHERE id = 1
                """, (datetime.now().isoformat(),))
                conn.commit()
                logger.debug("Updated last_used_date")
        except Exception as e:
            logger.error(f"Failed to update last_used_date: {e}")

    def update_total_photos(self, count: int):
        """
        Update the total photos count.

        Args:
            count: New total photos count
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET total_photos = ?
                    WHERE id = 1
                """, (count,))
                conn.commit()
                logger.debug(f"Updated total_photos to {count}")
        except Exception as e:
            logger.error(f"Failed to update total_photos: {e}")

    def refresh_total_photos(self):
        """
        Refresh the total photos count by querying the UniquePhotos table.
        This should be called after processing files to update the count.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Count rows in UniquePhotos table
                cursor.execute("SELECT COUNT(*) FROM UniquePhotos")
                count = cursor.fetchone()[0]

                # Update the metadata
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET total_photos = ?
                    WHERE id = 1
                """, (count,))
                conn.commit()

                logger.info(f"Refreshed total_photos to {count} from UniquePhotos table")
                return count
        except Exception as e:
            logger.error(f"Failed to refresh total_photos: {e}")
            return 0

    def update_archive_location(self, new_location: str) -> bool:
        """
        Update the archive location (for future migration feature).

        Args:
            new_location: New archive location path

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.isabs(new_location):
                raise ValueError("Archive location must be an absolute path")

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET archive_location = ?
                    WHERE id = 1
                """, (new_location,))
                conn.commit()
                logger.info(f"Updated archive location to: {new_location}")
                return True

        except Exception as e:
            logger.error(f"Failed to update archive location: {e}")
            return False

    def get_organization_template(self) -> str:
        """
        Get the organization template for this database.

        Returns:
            Organization template string (default: '{YYYY}/{MM}/{DD}')
        """
        metadata = self.get_metadata()
        return metadata.get('organization_template', '{YYYY}/{MM}/{DD}') if metadata else '{YYYY}/{MM}/{DD}'

    def set_organization_template(self, template: str) -> bool:
        """
        Set the organization template.

        Args:
            template: Organization template string

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET organization_template = ?
                    WHERE id = 1
                """, (template,))
                conn.commit()
                logger.info(f"Updated organization template to: {template}")
                return True

        except Exception as e:
            logger.error(f"Failed to update organization template: {e}")
            return False

    def get_file_type_organization(self) -> str:
        """
        Get the file type organization mode.

        Returns:
            File type organization mode ('combined', 'subfolder', 'separate_archive')
        """
        metadata = self.get_metadata()
        return metadata.get('file_type_organization', 'combined') if metadata else 'combined'

    def set_file_type_organization(self, mode: str) -> bool:
        """
        Set the file type organization mode.

        Args:
            mode: Organization mode ('combined', 'subfolder', 'separate_archive')

        Returns:
            True if successful, False otherwise
        """
        try:
            valid_modes = ['combined', 'subfolder', 'separate_archive']
            if mode not in valid_modes:
                raise ValueError(f"Invalid mode: {mode}. Must be one of {valid_modes}")

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET file_type_organization = ?
                    WHERE id = 1
                """, (mode,))
                conn.commit()
                logger.info(f"Updated file type organization to: {mode}")
                return True

        except Exception as e:
            logger.error(f"Failed to update file type organization: {e}")
            return False

    # ========== Source Directories Management ==========

    def add_source_directory(self, path: str, enabled: bool = True) -> bool:
        """
        Add a source directory to the database.

        Args:
            path: Absolute path to the source directory
            enabled: Whether the source is enabled for scanning (default: True)

        Returns:
            True if successful, False otherwise
        """
        try:
            if not os.path.isabs(path):
                raise ValueError("Source directory path must be absolute")

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get current max order_index
                cursor.execute("SELECT COALESCE(MAX(order_index), -1) FROM SourceDirectories")
                max_order = cursor.fetchone()[0]
                next_order = max_order + 1

                # Insert new source directory
                cursor.execute("""
                    INSERT INTO SourceDirectories (path, order_index, added_date, enabled)
                    VALUES (?, ?, ?, ?)
                """, (path, next_order, datetime.now().isoformat(), 1 if enabled else 0))

                conn.commit()
                logger.info(f"Added source directory: {path}")
                return True

        except sqlite3.IntegrityError:
            logger.warning(f"Source directory already exists: {path}")
            return False
        except Exception as e:
            logger.error(f"Failed to add source directory: {e}")
            return False

    def remove_source_directory(self, path: str) -> bool:
        """
        Remove a source directory from the database.

        Args:
            path: Path to the source directory to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Delete the source directory
                cursor.execute("DELETE FROM SourceDirectories WHERE path = ?", (path,))

                if cursor.rowcount == 0:
                    logger.warning(f"Source directory not found: {path}")
                    return False

                # Reorder remaining entries
                cursor.execute("""
                    SELECT id FROM SourceDirectories ORDER BY order_index
                """)
                rows = cursor.fetchall()

                for new_index, (row_id,) in enumerate(rows):
                    cursor.execute("""
                        UPDATE SourceDirectories SET order_index = ? WHERE id = ?
                    """, (new_index, row_id))

                conn.commit()
                logger.info(f"Removed source directory: {path}")
                return True

        except Exception as e:
            logger.error(f"Failed to remove source directory: {e}")
            return False

    def get_all_source_directories(self) -> List[Dict[str, Any]]:
        """
        Get all source directories with their metadata.

        Returns:
            List of dictionaries with source directory information
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, path, order_index, added_date, last_scanned, enabled
                    FROM SourceDirectories
                    ORDER BY order_index
                """)

                rows = cursor.fetchall()
                sources = []

                for row in rows:
                    sources.append({
                        'id': row[0],
                        'path': row[1],
                        'order_index': row[2],
                        'added_date': row[3],
                        'last_scanned': row[4],
                        'enabled': bool(row[5])
                    })

                return sources

        except Exception as e:
            logger.error(f"Failed to get source directories: {e}")
            return []

    def update_source_last_scanned(self, path: str, timestamp: Optional[str] = None) -> bool:
        """
        Update the last_scanned timestamp for a source directory.

        Args:
            path: Path to the source directory
            timestamp: ISO format timestamp (default: current time)

        Returns:
            True if successful, False otherwise
        """
        try:
            if timestamp is None:
                timestamp = datetime.now().isoformat()

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE SourceDirectories
                    SET last_scanned = ?
                    WHERE path = ?
                """, (timestamp, path))

                if cursor.rowcount == 0:
                    logger.warning(f"Source directory not found: {path}")
                    return False

                conn.commit()
                logger.debug(f"Updated last_scanned for {path}")
                return True

        except Exception as e:
            logger.error(f"Failed to update last_scanned: {e}")
            return False

    def update_source_enabled(self, path: str, enabled: bool) -> bool:
        """
        Update the enabled status for a source directory.

        Args:
            path: Path to the source directory
            enabled: Whether the source is enabled

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE SourceDirectories
                    SET enabled = ?
                    WHERE path = ?
                """, (1 if enabled else 0, path))

                if cursor.rowcount == 0:
                    logger.warning(f"Source directory not found: {path}")
                    return False

                conn.commit()
                logger.debug(f"Updated enabled status for {path}")
                return True

        except Exception as e:
            logger.error(f"Failed to update enabled status: {e}")
            return False

    def clear_all_source_directories(self) -> bool:
        """
        Remove all source directories from the database.

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM SourceDirectories")
                conn.commit()
                logger.info("Cleared all source directories")
                return True

        except Exception as e:
            logger.error(f"Failed to clear source directories: {e}")
            return False

    def reorder_source_directories(self, paths_in_order: List[str]) -> bool:
        """
        Reorder source directories by updating their order_index.

        Args:
            paths_in_order: List of paths in desired order

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                for new_index, path in enumerate(paths_in_order):
                    cursor.execute("""
                        UPDATE SourceDirectories
                        SET order_index = ?
                        WHERE path = ?
                    """, (new_index, path))

                conn.commit()
                logger.info("Reordered source directories")
                return True

        except Exception as e:
            logger.error(f"Failed to reorder source directories: {e}")
            return False

    # ========== Unreliable Dates Management ==========

    def insert_unreliable_date(self, file_hash: str, source_path: str,
                               archive_path: Optional[str], original_date: str,
                               date_source: str, flag_reason: str) -> bool:
        """
        Insert a record for a file with unreliable date information.

        Args:
            file_hash: SHA-256 hash of the file
            source_path: Original source path of the file
            archive_path: Archive path where file was stored
            original_date: Original detected date (YYYY-MM-DD format)
            date_source: Source of date ('exif', 'os_metadata', 'fallback')
            flag_reason: Reason for flagging ('no_exif', 'year_1000', 'suspicious', 'user_specified')

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if record already exists for this file
                cursor.execute("SELECT COUNT(*) FROM UnreliableDates WHERE file_hash = ?", (file_hash,))
                if cursor.fetchone()[0] > 0:
                    logger.debug(f"Unreliable date record already exists for {file_hash}")
                    return True

                # Insert new record
                cursor.execute("""
                    INSERT INTO UnreliableDates
                    (file_hash, source_path, archive_path, original_date, date_source, flag_reason)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (file_hash, source_path, archive_path, original_date, date_source, flag_reason))

                conn.commit()
                logger.debug(f"Inserted unreliable date record for {source_path}")
                return True

        except Exception as e:
            logger.error(f"Failed to insert unreliable date record: {e}")
            return False

    def get_unreliable_dates(self, filter_reason: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all files flagged with unreliable dates.

        Args:
            filter_reason: Optional filter ('no_exif', 'year_1000', 'suspicious', 'user_specified')

        Returns:
            List of dict records with unreliable date information
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if filter_reason:
                    cursor.execute("""
                        SELECT id, file_hash, source_path, archive_path, original_archive_path,
                               original_date, date_source, flag_reason, corrected_date,
                               correction_timestamp, needs_reorganization
                        FROM UnreliableDates
                        WHERE flag_reason = ?
                        ORDER BY source_path
                    """, (filter_reason,))
                else:
                    cursor.execute("""
                        SELECT id, file_hash, source_path, archive_path, original_archive_path,
                               original_date, date_source, flag_reason, corrected_date,
                               correction_timestamp, needs_reorganization
                        FROM UnreliableDates
                        ORDER BY source_path
                    """)

                rows = cursor.fetchall()
                records = []

                for row in rows:
                    records.append({
                        'id': row[0],
                        'file_hash': row[1],
                        'source_path': row[2],
                        'archive_path': row[3],
                        'original_archive_path': row[4],
                        'original_date': row[5],
                        'date_source': row[6],
                        'flag_reason': row[7],
                        'corrected_date': row[8],
                        'correction_timestamp': row[9],
                        'needs_reorganization': bool(row[10])
                    })

                return records

        except Exception as e:
            logger.error(f"Failed to get unreliable dates: {e}")
            return []

    def update_corrected_date(self, file_hash: str, new_date: str,
                             mark_for_reorganization: bool = True) -> bool:
        """
        Update corrected date for a file.

        Args:
            file_hash: SHA-256 hash of file
            new_date: New date as "YYYY-MM-DD"
            mark_for_reorganization: Whether to set needs_reorganization flag

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE UnreliableDates
                    SET corrected_date = ?,
                        correction_timestamp = ?,
                        needs_reorganization = ?
                    WHERE file_hash = ?
                """, (new_date, datetime.now().isoformat(),
                     1 if mark_for_reorganization else 0, file_hash))

                if cursor.rowcount == 0:
                    logger.warning(f"No unreliable date record found for hash: {file_hash}")
                    return False

                conn.commit()
                logger.info(f"Updated corrected date to {new_date} for {file_hash}")
                return True

        except Exception as e:
            logger.error(f"Failed to update corrected date: {e}")
            return False

    def get_files_needing_reorganization(self) -> List[Dict[str, Any]]:
        """
        Get all files with needs_reorganization=1.

        Returns:
            List of dict records that need reorganization
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, file_hash, source_path, archive_path, original_archive_path,
                           original_date, corrected_date, correction_timestamp
                    FROM UnreliableDates
                    WHERE needs_reorganization = 1
                    ORDER BY corrected_date
                """)

                rows = cursor.fetchall()
                records = []

                for row in rows:
                    records.append({
                        'id': row[0],
                        'file_hash': row[1],
                        'source_path': row[2],
                        'archive_path': row[3],
                        'original_archive_path': row[4],
                        'original_date': row[5],
                        'corrected_date': row[6],
                        'correction_timestamp': row[7]
                    })

                return records

        except Exception as e:
            logger.error(f"Failed to get files needing reorganization: {e}")
            return []

    def sync_archive_paths_from_unique_photos(self) -> int:
        """
        Sync archive_path from UniquePhotos to UnreliableDates, and repair archive paths
        that are currently pointing to source paths.

        This fixes records that were created before archive_path tracking was added.

        Returns:
            Number of records updated
        """
        try:
            from datetime import datetime
            from organization_template import OrganizationTemplate
            import os

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get organization settings
                template_str = self.get_organization_template()
                archive_base = self.get_archive_location()

                if not archive_base:
                    logger.warning("No archive location configured, skipping archive path sync")
                    return 0

                # First, update NULL archive_paths from UniquePhotos
                cursor.execute("""
                    UPDATE UnreliableDates
                    SET archive_path = (
                        SELECT file_name
                        FROM UniquePhotos
                        WHERE UniquePhotos.file_hash = UnreliableDates.file_hash
                    )
                    WHERE archive_path IS NULL
                    AND EXISTS (
                        SELECT 1
                        FROM UniquePhotos
                        WHERE UniquePhotos.file_hash = UnreliableDates.file_hash
                    )
                """)
                updated_null = cursor.rowcount

                # Now repair archive_paths that look like source paths (don't start with archive_base)
                cursor.execute("""
                    SELECT u.file_hash, u.archive_path, p.create_year, p.create_month, p.create_day, p.file_name
                    FROM UnreliableDates u
                    JOIN UniquePhotos p ON u.file_hash = p.file_hash
                    WHERE u.archive_path IS NOT NULL
                """)

                records_to_fix = []
                for row in cursor.fetchall():
                    file_hash, current_archive_path, year, month, day, unique_photos_path = row

                    # Check if archive_path looks like a source path (not in archive)
                    if not current_archive_path.startswith(archive_base):
                        # Reconstruct the correct archive path
                        try:
                            file_date = datetime(int(year), int(month), int(day))
                            folder_path = OrganizationTemplate.parse(template_str, file_date)
                            filename = os.path.basename(current_archive_path)
                            correct_archive_path = os.path.join(archive_base, folder_path, filename)

                            # Verify the file exists at this location
                            if os.path.exists(correct_archive_path):
                                records_to_fix.append((correct_archive_path, file_hash))
                                logger.debug(f"Will repair path: {current_archive_path} -> {correct_archive_path}")
                        except Exception as e:
                            logger.debug(f"Could not reconstruct path for {file_hash[:16]}...: {e}")

                # Update the repaired paths
                repaired_count = 0
                for correct_path, file_hash in records_to_fix:
                    # Update UnreliableDates
                    cursor.execute("""
                        UPDATE UnreliableDates
                        SET archive_path = ?
                        WHERE file_hash = ?
                    """, (correct_path, file_hash))

                    # Also update UniquePhotos
                    cursor.execute("""
                        UPDATE UniquePhotos
                        SET file_name = ?
                        WHERE file_hash = ?
                    """, (correct_path, file_hash))

                    repaired_count += 1

                conn.commit()

                total_updated = updated_null + repaired_count
                if total_updated > 0:
                    logger.info(f"Synced archive paths: {updated_null} NULL paths, {repaired_count} source paths repaired")

                return total_updated

        except Exception as e:
            logger.error(f"Failed to sync archive paths: {e}", exc_info=True)
            return 0

    def mark_reorganized(self, file_hash: str) -> bool:
        """
        Set needs_reorganization=0 for file after successful reorganization.

        Args:
            file_hash: SHA-256 hash of file

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE UnreliableDates
                    SET needs_reorganization = 0
                    WHERE file_hash = ?
                """, (file_hash,))

                if cursor.rowcount == 0:
                    logger.warning(f"No unreliable date record found for hash: {file_hash}")
                    return False

                conn.commit()
                logger.debug(f"Marked file as reorganized: {file_hash}")
                return True

        except Exception as e:
            logger.error(f"Failed to mark file as reorganized: {e}")
            return False

    def update_photo_path(self, file_hash: str, new_path: str) -> bool:
        """
        Update the file path in UniquePhotos table (for reorganization).

        Args:
            file_hash: SHA-256 hash of file
            new_path: New file path after reorganization

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Update UniquePhotos table
                cursor.execute("""
                    UPDATE UniquePhotos
                    SET file_name = ?
                    WHERE file_hash = ?
                """, (new_path, file_hash))

                if cursor.rowcount == 0:
                    logger.warning(f"No photo found in UniquePhotos for hash: {file_hash}")
                    return False

                # Also update archive_path in UnreliableDates table
                cursor.execute("""
                    UPDATE UnreliableDates
                    SET archive_path = ?
                    WHERE file_hash = ?
                """, (new_path, file_hash))

                conn.commit()
                logger.info(f"Updated photo path to: {new_path}")
                return True

        except Exception as e:
            logger.error(f"Failed to update photo path: {e}")
            return False

    def get_user_specified_paths(self) -> List[str]:
        """
        Get list of user-specified unreliable paths.

        Returns:
            List of folder path strings
        """
        try:
            import json

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT user_specified_unreliable_paths FROM DatabaseMetadata WHERE id = 1")
                row = cursor.fetchone()

                if row and row[0]:
                    return json.loads(row[0])
                return []

        except Exception as e:
            logger.error(f"Failed to get user-specified paths: {e}")
            return []

    def set_user_specified_paths(self, paths: List[str]) -> bool:
        """
        Save list of user-specified unreliable paths.

        Args:
            paths: List of folder path strings

        Returns:
            True if successful, False otherwise
        """
        try:
            import json

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET user_specified_unreliable_paths = ?
                    WHERE id = 1
                """, (json.dumps(paths),))

                conn.commit()
                logger.info(f"Updated user-specified unreliable paths: {len(paths)} paths")
                return True

        except Exception as e:
            logger.error(f"Failed to set user-specified paths: {e}")
            return False

    # ========== Filename Template Methods ==========

    def get_filename_template(self) -> str:
        """
        Get the filename template for this database.

        Returns:
            Filename template string (default: '{original_name}')
        """
        try:
            logger.info(f"→ DATABASE_METADATA.get_filename_template() called for database: {self.database_path}")
            metadata = self.get_metadata()

            if metadata is None:
                logger.warning("⚠ get_metadata() returned None - using default template")
                return '{original_name}'

            template = metadata.get('filename_template', '{original_name}')
            logger.info(f"✓ Retrieved filename template: '{template}'")
            return template

        except Exception as e:
            logger.error(f"✗ Error getting filename template: {e}", exc_info=True)
            return '{original_name}'

    def set_filename_template(self, template: str) -> bool:
        """
        Set the filename template.

        Args:
            template: Filename template string

        Returns:
            True if successful, False otherwise

        Raises:
            ValueError: If template validation fails
        """
        try:
            logger.info(f"→ set_filename_template('{template}') called for database: {self.database_path}")

            # Validate template first
            from filename_template import FilenameTemplate
            logger.debug(f"  Validating template...")
            is_valid, error_msg = FilenameTemplate.validate(template)
            if not is_valid:
                logger.error(f"✗ Template validation FAILED: {error_msg}")
                raise ValueError(f"Invalid filename template: {error_msg}")

            logger.debug(f"  ✓ Template validation passed")

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if row exists
                cursor.execute("SELECT COUNT(*) FROM DatabaseMetadata WHERE id = 1")
                count = cursor.fetchone()[0]
                if count == 0:
                    logger.error("✗ Cannot set template: DatabaseMetadata row (id=1) does not exist!")
                    logger.error("  Database must be initialized first")
                    return False

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET filename_template = ?
                    WHERE id = 1
                """, (template,))

                rows_affected = cursor.rowcount
                conn.commit()

                if rows_affected > 0:
                    logger.info(f"✓ Filename template updated successfully: '{template}' (rows: {rows_affected})")

                    # Verify the change
                    cursor.execute("SELECT filename_template FROM DatabaseMetadata WHERE id = 1")
                    result = cursor.fetchone()
                    if result:
                        actual_value = result[0]
                        logger.debug(f"  Verification: filename_template = '{actual_value}'")
                        if actual_value != template:
                            logger.error(f"✗ Verification FAILED: Expected '{template}', got '{actual_value}'")
                            return False
                    return True
                else:
                    logger.warning(f"⚠ UPDATE returned 0 rows affected - row may not exist")
                    return False

        except ValueError as e:
            logger.error(f"✗ Template validation failed: {e}")
            raise
        except Exception as e:
            logger.error(f"✗ Failed to update filename template: {e}", exc_info=True)
            return False

    def is_file_rename_enabled(self) -> bool:
        """
        Check if file renaming is enabled for this database.

        Returns:
            True if file renaming is enabled, False otherwise
        """
        try:
            logger.info(f"→ DATABASE_METADATA.is_file_rename_enabled() called for database: {self.database_path}")
            metadata = self.get_metadata()

            if metadata is None:
                logger.warning("⚠ get_metadata() returned None - database may not be initialized!")
                logger.warning("  File renaming will be DISABLED")
                return False

            enable_value = metadata.get('enable_file_rename', 0)
            result = bool(enable_value)
            logger.info(f"✓ File rename is {'ENABLED' if result else 'DISABLED'} (database value: {enable_value})")
            return result

        except Exception as e:
            logger.error(f"✗ Error checking file rename enabled status: {e}", exc_info=True)
            return False

    def set_file_rename_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable file renaming.

        Args:
            enabled: True to enable, False to disable

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"→ set_file_rename_enabled({enabled}) called for database: {self.database_path}")

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if row exists
                cursor.execute("SELECT COUNT(*) FROM DatabaseMetadata WHERE id = 1")
                count = cursor.fetchone()[0]
                if count == 0:
                    logger.error("✗ Cannot set file rename: DatabaseMetadata row (id=1) does not exist!")
                    logger.error("  Database must be initialized first")
                    return False

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET enable_file_rename = ?
                    WHERE id = 1
                """, (1 if enabled else 0,))

                rows_affected = cursor.rowcount
                conn.commit()

                if rows_affected > 0:
                    logger.info(f"✓ File rename {'ENABLED' if enabled else 'DISABLED'} successfully (rows updated: {rows_affected})")

                    # Verify the change
                    cursor.execute("SELECT enable_file_rename FROM DatabaseMetadata WHERE id = 1")
                    result = cursor.fetchone()
                    if result:
                        actual_value = result[0]
                        logger.debug(f"  Verification: enable_file_rename = {actual_value}")
                        if actual_value != (1 if enabled else 0):
                            logger.error(f"✗ Verification FAILED: Expected {1 if enabled else 0}, got {actual_value}")
                            return False
                    return True
                else:
                    logger.warning(f"⚠ UPDATE returned 0 rows affected - row may not exist")
                    return False

        except Exception as e:
            logger.error(f"✗ Failed to set file rename enabled state: {e}", exc_info=True)
            return False

    def insert_rename_history(self, file_hash: str, original_filename: str,
                             renamed_filename: str) -> bool:
        """
        Record a file rename operation for undo capability and audit trail.

        Args:
            file_hash: SHA-256 hash of the file
            original_filename: Original basename
            renamed_filename: New basename

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO FileRenameHistory
                    (file_hash, original_filename, renamed_filename, rename_timestamp)
                    VALUES (?, ?, ?, datetime('now'))
                """, (file_hash, original_filename, renamed_filename))
                conn.commit()
                logger.debug(f"Recorded rename: {original_filename} → {renamed_filename}")
                return True

        except Exception as e:
            logger.error(f"Failed to insert rename history: {e}")
            return False

    def get_rename_history(self, file_hash: str) -> List[Dict[str, Any]]:
        """
        Get rename history for a specific file.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            List of dict records with rename history, sorted by timestamp (newest first)
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT original_filename, renamed_filename, rename_timestamp
                    FROM FileRenameHistory
                    WHERE file_hash = ?
                    ORDER BY rename_timestamp DESC
                """, (file_hash,))

                columns = [desc[0] for desc in cursor.description]
                return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get rename history: {e}")
            return []

    # ========== Thumbnail Settings ==========

    def get_thumbnail_size(self) -> int:
        """
        Get the thumbnail size setting for the grid view.

        Returns:
            Thumbnail size in pixels (default: 200)
        """
        try:
            metadata = self.get_metadata()
            if metadata is None:
                logger.warning("get_metadata() returned None - using default thumbnail size")
                return 200

            size = metadata.get('thumbnail_size', 200)
            return int(size) if size else 200

        except Exception as e:
            logger.error(f"Failed to get thumbnail size: {e}")
            return 200

    def set_thumbnail_size(self, size: int) -> bool:
        """
        Set the thumbnail size setting for the grid view.

        Args:
            size: Thumbnail size in pixels (typically 150, 200, or 300)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET thumbnail_size = ?
                    WHERE id = 1
                """, (size,))

                conn.commit()
                logger.info(f"Updated thumbnail size to {size}px")
                return True

        except Exception as e:
            logger.error(f"Failed to set thumbnail size: {e}")
            return False

    # ========== Preview Window Settings ==========

    def get_preview_window_geometry(self) -> Optional[str]:
        """
        Get the saved preview window geometry (JSON string).

        Returns:
            JSON string with window geometry or None
        """
        try:
            metadata = self.get_metadata()
            if metadata is None:
                return None

            return metadata.get('preview_window_geometry')

        except Exception as e:
            logger.error(f"Failed to get preview window geometry: {e}")
            return None

    def set_preview_window_geometry(self, geometry: str) -> bool:
        """
        Save the preview window geometry (JSON string).

        Args:
            geometry: JSON string with window geometry (x, y, width, height)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET preview_window_geometry = ?
                    WHERE id = 1
                """, (geometry,))

                conn.commit()
                logger.debug(f"Updated preview window geometry")
                return True

        except Exception as e:
            logger.error(f"Failed to set preview window geometry: {e}")
            return False

    def get_preview_window_visible(self) -> bool:
        """
        Check if preview window should be visible on startup.

        Returns:
            True if preview window should be shown, False otherwise
        """
        try:
            metadata = self.get_metadata()
            if metadata is None:
                return True  # Default: show preview

            visible = metadata.get('preview_window_visible', 1)
            return bool(visible)

        except Exception as e:
            logger.error(f"Failed to get preview window visible state: {e}")
            return True

    def set_preview_window_visible(self, visible: bool) -> bool:
        """
        Set whether preview window should be visible on startup.

        Args:
            visible: True to show preview window, False to hide

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET preview_window_visible = ?
                    WHERE id = 1
                """, (1 if visible else 0,))

                conn.commit()
                logger.info(f"Preview window visibility set to {visible}")
                return True

        except Exception as e:
            logger.error(f"Failed to set preview window visible state: {e}")
            return False

    # ========== Ignored Directories Management ==========

    def get_ignored_directories(self) -> List[str]:
        """
        Get list of ignored directory patterns.

        Returns:
            List of directory pattern strings (can contain wildcards *, ?)
        """
        try:
            import json

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT ignored_directories FROM DatabaseMetadata WHERE id = 1")
                row = cursor.fetchone()

                if row and row[0]:
                    return json.loads(row[0])
                return []

        except Exception as e:
            logger.error(f"Failed to get ignored directories: {e}")
            return []

    def set_ignored_directories(self, patterns: List[str]) -> bool:
        """
        Save list of ignored directory patterns.

        Args:
            patterns: List of directory pattern strings (can contain wildcards *, ?)

        Returns:
            True if successful, False otherwise
        """
        try:
            import json

            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET ignored_directories = ?
                    WHERE id = 1
                """, (json.dumps(patterns),))

                conn.commit()
                logger.info(f"Updated ignored directories: {len(patterns)} patterns")
                return True

        except Exception as e:
            logger.error(f"Failed to set ignored directories: {e}")
            return False

    def add_ignored_directory(self, pattern: str) -> bool:
        """
        Add a directory pattern to the ignored list.

        Args:
            pattern: Directory pattern string (can contain wildcards *, ?)

        Returns:
            True if successful, False otherwise
        """
        try:
            patterns = self.get_ignored_directories()

            # Check if pattern already exists (case-insensitive)
            if any(p.lower() == pattern.lower() for p in patterns):
                logger.debug(f"Pattern already exists: {pattern}")
                return True

            patterns.append(pattern)
            return self.set_ignored_directories(patterns)

        except Exception as e:
            logger.error(f"Failed to add ignored directory: {e}")
            return False

    def remove_ignored_directory(self, pattern: str) -> bool:
        """
        Remove a directory pattern from the ignored list.

        Args:
            pattern: Directory pattern string to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            patterns = self.get_ignored_directories()

            # Remove pattern (case-insensitive match)
            patterns = [p for p in patterns if p.lower() != pattern.lower()]

            return self.set_ignored_directories(patterns)

        except Exception as e:
            logger.error(f"Failed to remove ignored directory: {e}")
            return False

    # ========== Static Methods ==========

    @staticmethod
    def find_databases(search_path: str = ".") -> List[Dict[str, Any]]:
        """
        Find all PyPhotoOrganizer databases in a directory.

        Args:
            search_path: Directory to search for databases

        Returns:
            List of dictionaries with database info
        """
        databases = []

        try:
            search_dir = Path(search_path)
            for db_file in search_dir.glob("*.db"):
                try:
                    db_meta = DatabaseMetadata(str(db_file))
                    metadata = db_meta.get_metadata()

                    if metadata:
                        databases.append({
                            'path': str(db_file.absolute()),
                            'filename': db_file.name,
                            **metadata
                        })
                except Exception as e:
                    logger.debug(f"Skipping {db_file}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Failed to search for databases: {e}")

        return databases

    @staticmethod
    def create_database(database_path: str, database_name: str,
                       archive_location: str, description: str = "") -> bool:
        """
        Create a new database with metadata and UniquePhotos table.

        Args:
            database_path: Path for the new database file
            database_name: User-friendly name
            archive_location: Archive (destination) location
            description: Optional description

        Returns:
            True if successful, False otherwise
        """
        try:
            # Create database file if it doesn't exist
            if os.path.exists(database_path):
                raise FileExistsError(f"Database already exists: {database_path}")

            # Create parent directory if needed
            parent_dir = os.path.dirname(database_path)
            if parent_dir:  # Only create if there's a parent directory
                os.makedirs(parent_dir, exist_ok=True)

            # Create database with metadata
            db_meta = DatabaseMetadata(database_path)
            success = db_meta.initialize_metadata(database_name, archive_location, description)

            if not success:
                return False

            # Initialize UniquePhotos table
            # Import here to avoid circular dependency
            import DuplicateFileDetection
            with DuplicateFileDetection.PhotoDatabase(database_path) as db:
                db.initialize_database()

            logger.info(f"Created new database with all tables: {database_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to create database: {e}")
            raise
