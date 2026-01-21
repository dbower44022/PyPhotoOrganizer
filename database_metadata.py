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
            prior_revision_archive_location TEXT,
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
            enabled INTEGER DEFAULT 1,
            album_id INTEGER,
            enable_sub_albums INTEGER DEFAULT 0,
            FOREIGN KEY (album_id) REFERENCES Albums(id) ON DELETE SET NULL
        );
    """

    SOURCE_DIRECTORY_SUB_ALBUMS_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS SourceDirectorySubAlbums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_directory_id INTEGER NOT NULL,
            parent_album_id INTEGER NOT NULL,
            sub_album_id INTEGER NOT NULL,
            relative_subdir_path TEXT NOT NULL,
            created_timestamp TEXT NOT NULL,
            FOREIGN KEY (source_directory_id) REFERENCES SourceDirectories(id) ON DELETE CASCADE,
            FOREIGN KEY (parent_album_id) REFERENCES Albums(id) ON DELETE CASCADE,
            FOREIGN KEY (sub_album_id) REFERENCES Albums(id) ON DELETE CASCADE,
            UNIQUE(source_directory_id, relative_subdir_path)
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
            FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
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

    DELETED_FILES_TABLE_SCHEMA = """
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
        );
    """

    SAVED_QUERIES_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS SavedQueries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            query_json TEXT NOT NULL,
            is_favorite INTEGER DEFAULT 0,
            is_system INTEGER DEFAULT 0,
            created_date TEXT NOT NULL,
            last_used_date TEXT,
            use_count INTEGER DEFAULT 0
        );
    """

    ALBUMS_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS Albums (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_name TEXT NOT NULL UNIQUE,
            album_description TEXT,
            storage_location TEXT NOT NULL,
            created_timestamp TEXT NOT NULL,
            updated_timestamp TEXT,
            photo_count INTEGER DEFAULT 0,
            total_size_bytes INTEGER DEFAULT 0,
            sync_deletions INTEGER DEFAULT 1,
            is_active INTEGER DEFAULT 1,
            sort_order INTEGER DEFAULT 0
        );
    """

    ALBUM_PHOTOS_TABLE_SCHEMA = """
        CREATE TABLE IF NOT EXISTS AlbumPhotos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            album_id INTEGER NOT NULL,
            file_hash TEXT NOT NULL,
            album_file_path TEXT NOT NULL,
            added_timestamp TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            FOREIGN KEY (album_id) REFERENCES Albums(id) ON DELETE CASCADE,
            FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash),
            UNIQUE(album_id, file_hash)
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
        self._ensure_deleted_files_table()
        self._ensure_saved_queries_table()
        self._ensure_albums_table()
        self._ensure_source_directory_sub_albums_table()

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

                # Add prior_revision_archive_location column if missing
                if 'prior_revision_archive_location' not in columns:
                    logger.info("Upgrading database: adding prior_revision_archive_location column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN prior_revision_archive_location TEXT")

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

                # Add cache_memory_mb column if missing
                if 'cache_memory_mb' not in columns:
                    logger.info("Upgrading database: adding cache_memory_mb column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN cache_memory_mb INTEGER DEFAULT 500")

                # Add cache_worker_threads column if missing
                if 'cache_worker_threads' not in columns:
                    logger.info("Upgrading database: adding cache_worker_threads column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN cache_worker_threads INTEGER DEFAULT 8")

                # Add delete_vault_location column if missing
                if 'delete_vault_location' not in columns:
                    logger.info("Upgrading database: adding delete_vault_location column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN delete_vault_location TEXT")

                # Add photo_review_state column if missing (for Photo Review app)
                if 'photo_review_state' not in columns:
                    logger.info("Upgrading database: adding photo_review_state column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN photo_review_state TEXT DEFAULT '{}'")

                # Add content_hash_enabled column if missing (for content-based duplicate detection)
                if 'content_hash_enabled' not in columns:
                    logger.info("Upgrading database: adding content_hash_enabled column")
                    cursor.execute("ALTER TABLE DatabaseMetadata ADD COLUMN content_hash_enabled INTEGER DEFAULT 1")
                    # Set default value for existing rows
                    cursor.execute("UPDATE DatabaseMetadata SET content_hash_enabled = 1 WHERE content_hash_enabled IS NULL")

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

                # Check if new columns exist (for upgrading old databases)
                cursor.execute("PRAGMA table_info(SourceDirectories)")
                columns = [row[1] for row in cursor.fetchall()]

                # Add album_id column if missing (for album association)
                if 'album_id' not in columns:
                    logger.info("Upgrading database: adding album_id column to SourceDirectories")
                    cursor.execute("ALTER TABLE SourceDirectories ADD COLUMN album_id INTEGER")

                # Add enable_sub_albums column if missing
                if 'enable_sub_albums' not in columns:
                    logger.info("Upgrading database: adding enable_sub_albums column to SourceDirectories")
                    cursor.execute("ALTER TABLE SourceDirectories ADD COLUMN enable_sub_albums INTEGER DEFAULT 0")

                conn.commit()
                logger.debug(f"SourceDirectories table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create SourceDirectories table: {e}")
            raise

    def _ensure_source_directory_sub_albums_table(self):
        """Ensure the SourceDirectorySubAlbums table exists in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.SOURCE_DIRECTORY_SUB_ALBUMS_TABLE_SCHEMA)

                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_subalbums_source_dir
                    ON SourceDirectorySubAlbums(source_directory_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_subalbums_parent_album
                    ON SourceDirectorySubAlbums(parent_album_id)
                """)

                conn.commit()
                logger.debug(f"SourceDirectorySubAlbums table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create SourceDirectorySubAlbums table: {e}")
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

                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_unreliable_hash ON UnreliableDates(file_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_unreliable_needs_reorg ON UnreliableDates(needs_reorganization)")

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

    def _ensure_deleted_files_table(self):
        """Ensure the DeletedFiles table exists in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.DELETED_FILES_TABLE_SCHEMA)

                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_deleted_hash ON DeletedFiles(file_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_deleted_restored ON DeletedFiles(is_restored)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_deleted_timestamp ON DeletedFiles(deletion_timestamp)")

                conn.commit()
                logger.debug(f"DeletedFiles table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create DeletedFiles table: {e}")
            raise

    def _ensure_saved_queries_table(self):
        """Ensure the SavedQueries table exists in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create table if it doesn't exist
                cursor.execute(self.SAVED_QUERIES_TABLE_SCHEMA)

                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_queries_name ON SavedQueries(name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_queries_favorite ON SavedQueries(is_favorite)")

                conn.commit()
                logger.debug(f"SavedQueries table ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create SavedQueries table: {e}")
            raise

    def _ensure_albums_table(self):
        """Ensure the Albums and AlbumPhotos tables exist in the database."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create Albums table if it doesn't exist
                cursor.execute(self.ALBUMS_TABLE_SCHEMA)

                # Create AlbumPhotos table if it doesn't exist
                cursor.execute(self.ALBUM_PHOTOS_TABLE_SCHEMA)

                # Create indexes for performance
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_albums_name ON Albums(album_name)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_albums_active ON Albums(is_active)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_albumphoto_album ON AlbumPhotos(album_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_albumphoto_hash ON AlbumPhotos(file_hash)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_albumphoto_album_order ON AlbumPhotos(album_id, display_order)")

                conn.commit()
                logger.debug(f"Albums and AlbumPhotos tables ensured in {self.database_path}")

        except Exception as e:
            logger.error(f"Failed to create Albums tables: {e}")
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
                           thumbnail_size, thumbnail_cache_dir, preview_window_geometry, preview_window_visible,
                           cache_memory_mb, cache_worker_threads, prior_revision_archive_location
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
                        'preview_window_visible': row[16] if len(row) > 16 else 1,
                        'cache_memory_mb': row[17] if len(row) > 17 else 500,
                        'cache_worker_threads': row[18] if len(row) > 18 else 8,
                        'prior_revision_archive_location': row[19] if len(row) > 19 else None
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

    def get_prior_revision_archive_location(self) -> Optional[str]:
        """
        Get the Prior Revision Archive location.

        The Prior Revision Archive stores files that have been superseded by revisions
        (e.g., original photos before rotation). This keeps the main archive clean
        with only current revisions while preserving full history.

        Returns:
            str: Path to prior revision archive, or None if not configured
        """
        try:
            metadata = self.get_metadata()
            if metadata and 'prior_revision_archive_location' in metadata:
                location = metadata['prior_revision_archive_location']
                return location if location else None
            return None
        except Exception as e:
            logger.error(f"Failed to get prior revision archive location: {e}")
            return None

    def set_prior_revision_archive_location(self, path: str) -> bool:
        """
        Set the Prior Revision Archive location.

        Args:
            path: Path to prior revision archive directory

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Validate path exists and is writable
            if not path:
                # Allow clearing the location
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE DatabaseMetadata
                        SET prior_revision_archive_location = NULL
                        WHERE id = 1
                    """)
                    conn.commit()
                logger.info("Prior revision archive location cleared")
                return True

            if not os.path.exists(path):
                raise ValueError(f"Path does not exist: {path}")
            if not os.path.isdir(path):
                raise ValueError(f"Path is not a directory: {path}")
            if not os.access(path, os.W_OK):
                raise ValueError(f"Path is not writable: {path}")

            # Check it's not the same as main archive
            archive_base = self.get_archive_location()
            if archive_base and os.path.realpath(path) == os.path.realpath(archive_base):
                raise ValueError("Prior Revision Archive cannot be the same as main archive")

            # Check it's not inside main archive
            if archive_base and os.path.realpath(path).startswith(os.path.realpath(archive_base) + os.sep):
                raise ValueError("Prior Revision Archive cannot be inside main archive")

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET prior_revision_archive_location = ?
                    WHERE id = 1
                """, (path,))
                conn.commit()

            logger.info(f"Prior revision archive location set: {path}")
            return True

        except Exception as e:
            logger.error(f"Failed to set prior revision archive location: {e}")
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
                    SELECT id, path, order_index, added_date, last_scanned, enabled,
                           album_id, enable_sub_albums
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
                        'enabled': bool(row[5]),
                        'album_id': row[6],
                        'enable_sub_albums': bool(row[7]) if row[7] is not None else False
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

    def update_source_album(self, path: str, album_id: Optional[int]) -> bool:
        """
        Update the album association for a source directory.

        Args:
            path: Path to the source directory
            album_id: Album ID to associate (None to remove association)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE SourceDirectories
                    SET album_id = ?
                    WHERE path = ?
                """, (album_id, path))

                if cursor.rowcount == 0:
                    logger.warning(f"Source directory not found: {path}")
                    return False

                conn.commit()
                logger.debug(f"Updated album association for {path}: album_id={album_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to update album association: {e}")
            return False

    def update_source_sub_albums_enabled(self, path: str, enabled: bool) -> bool:
        """
        Update the sub-albums enabled setting for a source directory.

        Args:
            path: Path to the source directory
            enabled: Whether sub-albums are enabled

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE SourceDirectories
                    SET enable_sub_albums = ?
                    WHERE path = ?
                """, (1 if enabled else 0, path))

                if cursor.rowcount == 0:
                    logger.warning(f"Source directory not found: {path}")
                    return False

                conn.commit()
                logger.debug(f"Updated sub-albums enabled for {path}: {enabled}")
                return True

        except Exception as e:
            logger.error(f"Failed to update sub-albums setting: {e}")
            return False

    def get_source_directory_by_path(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get a source directory record by its path.

        Args:
            path: Path to the source directory

        Returns:
            Dictionary with source directory information, or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, path, order_index, added_date, last_scanned, enabled,
                           album_id, enable_sub_albums
                    FROM SourceDirectories
                    WHERE path = ?
                """, (path,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'path': row[1],
                        'order_index': row[2],
                        'added_date': row[3],
                        'last_scanned': row[4],
                        'enabled': bool(row[5]),
                        'album_id': row[6],
                        'enable_sub_albums': bool(row[7]) if row[7] is not None else False
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get source directory: {e}")
            return None

    def get_source_directory_by_id(self, source_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a source directory record by its ID.

        Args:
            source_id: ID of the source directory

        Returns:
            Dictionary with source directory information, or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, path, order_index, added_date, last_scanned, enabled,
                           album_id, enable_sub_albums
                    FROM SourceDirectories
                    WHERE id = ?
                """, (source_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'path': row[1],
                        'order_index': row[2],
                        'added_date': row[3],
                        'last_scanned': row[4],
                        'enabled': bool(row[5]),
                        'album_id': row[6],
                        'enable_sub_albums': bool(row[7]) if row[7] is not None else False
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get source directory by ID: {e}")
            return None

    # ========== Source Directory Sub-Albums Management ==========

    def get_or_create_sub_album(self, source_directory_id: int, parent_album_id: int,
                                sub_album_id: int, relative_subdir_path: str) -> Optional[int]:
        """
        Get or create a sub-album mapping for a source directory.

        Args:
            source_directory_id: ID of the source directory
            parent_album_id: ID of the parent album
            sub_album_id: ID of the sub-album
            relative_subdir_path: Relative path of the subdirectory from source

        Returns:
            ID of the mapping record, or None if failed
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if mapping exists
                cursor.execute("""
                    SELECT id, sub_album_id FROM SourceDirectorySubAlbums
                    WHERE source_directory_id = ? AND relative_subdir_path = ?
                """, (source_directory_id, relative_subdir_path))

                row = cursor.fetchone()
                if row:
                    return row[0]  # Return existing mapping ID

                # Create new mapping
                cursor.execute("""
                    INSERT INTO SourceDirectorySubAlbums (
                        source_directory_id, parent_album_id, sub_album_id,
                        relative_subdir_path, created_timestamp
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    source_directory_id, parent_album_id, sub_album_id,
                    relative_subdir_path, datetime.now().isoformat()
                ))

                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Failed to get/create sub-album mapping: {e}")
            return None

    def get_sub_album_for_path(self, source_directory_id: int,
                               relative_subdir_path: str) -> Optional[int]:
        """
        Get the sub-album ID for a given source directory and relative path.

        Args:
            source_directory_id: ID of the source directory
            relative_subdir_path: Relative path of the subdirectory

        Returns:
            Sub-album ID, or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT sub_album_id FROM SourceDirectorySubAlbums
                    WHERE source_directory_id = ? AND relative_subdir_path = ?
                """, (source_directory_id, relative_subdir_path))

                row = cursor.fetchone()
                return row[0] if row else None

        except Exception as e:
            logger.error(f"Failed to get sub-album for path: {e}")
            return None

    def get_all_sub_albums_for_source(self, source_directory_id: int) -> List[Dict[str, Any]]:
        """
        Get all sub-album mappings for a source directory.

        Args:
            source_directory_id: ID of the source directory

        Returns:
            List of sub-album mapping dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, source_directory_id, parent_album_id, sub_album_id,
                           relative_subdir_path, created_timestamp
                    FROM SourceDirectorySubAlbums
                    WHERE source_directory_id = ?
                    ORDER BY relative_subdir_path
                """, (source_directory_id,))

                return [
                    {
                        'id': row[0],
                        'source_directory_id': row[1],
                        'parent_album_id': row[2],
                        'sub_album_id': row[3],
                        'relative_subdir_path': row[4],
                        'created_timestamp': row[5]
                    }
                    for row in cursor.fetchall()
                ]

        except Exception as e:
            logger.error(f"Failed to get sub-albums for source: {e}")
            return []

    def delete_sub_album_mapping(self, mapping_id: int) -> bool:
        """
        Delete a sub-album mapping.

        Args:
            mapping_id: ID of the mapping to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM SourceDirectorySubAlbums WHERE id = ?", (mapping_id,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to delete sub-album mapping: {e}")
            return False

    def clear_sub_albums_for_source(self, source_directory_id: int) -> bool:
        """
        Clear all sub-album mappings for a source directory.

        Args:
            source_directory_id: ID of the source directory

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM SourceDirectorySubAlbums
                    WHERE source_directory_id = ?
                """, (source_directory_id,))
                conn.commit()
                logger.info(f"Cleared sub-album mappings for source {source_directory_id}")
                return True

        except Exception as e:
            logger.error(f"Failed to clear sub-album mappings: {e}")
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

    # ========== Thumbnail Cache Settings ==========

    def get_cache_memory_mb(self) -> int:
        """
        Get the thumbnail cache memory size in MB.

        Returns:
            Cache memory size in MB (default: 500MB)
        """
        try:
            metadata = self.get_metadata()
            if metadata is None:
                logger.warning("get_metadata() returned None - using default cache memory size")
                return 500

            size_mb = metadata.get('cache_memory_mb', 500)
            return int(size_mb) if size_mb else 500

        except Exception as e:
            logger.error(f"Failed to get cache memory size: {e}")
            return 500

    def set_cache_memory_mb(self, size_mb: int) -> bool:
        """
        Set the thumbnail cache memory size in MB.

        Args:
            size_mb: Cache memory size in MB (e.g., 100, 500, 1000)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET cache_memory_mb = ?
                    WHERE id = 1
                """, (size_mb,))

                conn.commit()
                logger.info(f"Updated cache memory size to {size_mb}MB")
                return True

        except Exception as e:
            logger.error(f"Failed to set cache memory size: {e}")
            return False

    def get_cache_worker_threads(self) -> int:
        """
        Get the number of worker threads for thumbnail generation.

        Returns:
            Number of worker threads (default: 8)
        """
        try:
            metadata = self.get_metadata()
            if metadata is None:
                logger.warning("get_metadata() returned None - using default worker threads")
                return 8

            threads = metadata.get('cache_worker_threads', 8)
            return int(threads) if threads else 8

        except Exception as e:
            logger.error(f"Failed to get cache worker threads: {e}")
            return 8

    def set_cache_worker_threads(self, threads: int) -> bool:
        """
        Set the number of worker threads for thumbnail generation.

        Args:
            threads: Number of worker threads (1-16, typically matches CPU cores)

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET cache_worker_threads = ?
                    WHERE id = 1
                """, (threads,))

                conn.commit()
                logger.info(f"Updated cache worker threads to {threads}")
                return True

        except Exception as e:
            logger.error(f"Failed to set cache worker threads: {e}")
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

    def sync_versions_to_hash_history(self):
        """
        One-time sync: Add all existing FileVersions hashes to FileHashHistory.
        Called automatically on first access after migration.
        Safe to run multiple times (uses INSERT OR IGNORE).

        Returns:
            int: Number of version hashes synced
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if sync needed (if FileVersions has records but some aren't in history)
            cursor.execute("""
                SELECT COUNT(*) FROM FileVersions v
                WHERE NOT EXISTS (
                    SELECT 1 FROM FileHashHistory h
                    WHERE h.historical_hash = v.file_hash
                )
            """)

            missing_count = cursor.fetchone()[0]

            if missing_count == 0:
                logger.info("All version hashes already in FileHashHistory")
                conn.close()
                return 0

            logger.info(f"Syncing {missing_count} version hashes to FileHashHistory...")

            # Insert missing version hashes
            cursor.execute("""
                INSERT OR IGNORE INTO FileHashHistory
                    (current_file_hash, historical_hash, created_date, reason)
                SELECT
                    v.original_hash,
                    v.file_hash,
                    v.created_timestamp,
                    'sync_' || COALESCE(v.modification_type, 'version')
                FROM FileVersions v
                WHERE NOT EXISTS (
                    SELECT 1 FROM FileHashHistory h
                    WHERE h.historical_hash = v.file_hash
                )
            """)

            synced = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"✓ Synced {synced} version hashes to FileHashHistory")
            return synced

        except Exception as e:
            logger.error(f"Failed to sync versions to hash history: {e}")
            return 0

    # ========== Deletion Tracking Methods ==========

    def get_delete_vault_location(self) -> str:
        """
        Get the configured Delete Vault location.

        Returns:
            str: Path to Delete Vault, or None if not configured
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT delete_vault_location
                FROM DatabaseMetadata
                WHERE id = 1
            """)

            result = cursor.fetchone()
            conn.close()

            vault_path = result[0] if result and result[0] else None
            if vault_path:
                logger.debug(f"ℹ Delete Vault location retrieved: {vault_path}")
            else:
                logger.debug("ℹ Delete Vault location not configured")

            return vault_path

        except Exception as e:
            logger.error(f"✗ Failed to get Delete Vault location from database: {e}", exc_info=True)
            logger.error(f"  Database path: {self.database_path}")
            return None

    def set_delete_vault_location(self, path: str) -> bool:
        """
        Save the Delete Vault location to database.
        Validates that the directory exists.

        Args:
            path: Path to Delete Vault directory

        Returns:
            bool: True if saved successfully, False otherwise
        """
        logger.info(f"{'='*80}")
        logger.info(f"SETTING DELETE VAULT LOCATION")
        logger.info(f"  Path: {path}")
        logger.info(f"  Database: {self.database_path}")
        logger.info(f"{'-'*60}")

        try:
            # Validate path exists
            if not os.path.exists(path):
                logger.error(f"✗ Delete Vault path does not exist: {path}")
                logger.error(f"  Validation failed: Directory not found")
                return False

            if not os.path.isdir(path):
                logger.error(f"✗ Delete Vault path is not a directory: {path}")
                logger.error(f"  Validation failed: Path is not a directory")
                return False

            # Check if writable
            if not os.access(path, os.W_OK):
                logger.error(f"✗ Delete Vault path is not writable: {path}")
                logger.error(f"  Validation failed: Permission denied")
                return False

            logger.info(f"  ✓ Path validation passed")

            conn = self._get_connection()
            cursor = conn.cursor()

            logger.info(f"  Updating DatabaseMetadata table...")

            cursor.execute("""
                UPDATE DatabaseMetadata
                SET delete_vault_location = ?
                WHERE id = 1
            """, (path,))

            rows_affected = cursor.rowcount
            logger.info(f"  Rows updated: {rows_affected}")

            conn.commit()
            conn.close()

            logger.info(f"✓ Delete Vault location saved successfully")
            logger.info(f"  Location: {path}")
            logger.info(f"{'='*80}")
            return True

        except Exception as e:
            logger.error(f"{'='*80}")
            logger.error(f"✗ FAILED TO SET DELETE VAULT LOCATION")
            logger.error(f"  Path: {path}")
            logger.error(f"  Database: {self.database_path}")
            logger.error(f"  Error: {e}", exc_info=True)
            logger.error(f"{'='*80}")
            return False

    def get_deleted_files(self, include_restored=False) -> List[Dict]:
        """
        Query all deleted files from DeletedFiles table.

        Args:
            include_restored: If True, include restored files. If False, only show non-restored.

        Returns:
            List of dictionaries with deleted file records
        """
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if include_restored:
                cursor.execute("""
                    SELECT * FROM DeletedFiles
                    ORDER BY deletion_timestamp DESC
                """)
            else:
                cursor.execute("""
                    SELECT * FROM DeletedFiles
                    WHERE is_restored = 0
                    ORDER BY deletion_timestamp DESC
                """)

            results = [dict(row) for row in cursor.fetchall()]
            conn.close()

            return results

        except Exception as e:
            logger.error(f"Failed to get deleted files: {e}")
            return []

    def mark_file_as_deleted(self, file_hash: str, original_path: str,
                           vault_path: str, reason: str) -> bool:
        """
        Insert a record into DeletedFiles table.

        Args:
            file_hash: SHA-256 hash of the file
            original_path: Original archive path before deletion
            vault_path: Path in Delete Vault
            reason: Deletion reason ('user_deleted', 'batch_deleted', etc.)

        Returns:
            bool: True if inserted successfully, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get file info from UniquePhotos if available
            cursor.execute("""
                SELECT file_size, create_year, create_month, create_day
                FROM UniquePhotos
                WHERE file_hash = ?
            """, (file_hash,))

            photo_info = cursor.fetchone()
            file_size = photo_info[0] if photo_info else None
            creation_date = None
            if photo_info and photo_info[1] and photo_info[2] and photo_info[3]:
                # Convert month/day to int for formatting (they're stored as TEXT in database)
                creation_date = f"{photo_info[1]}-{int(photo_info[2]):02d}-{int(photo_info[3]):02d}"

            # Insert deletion record
            now = datetime.now().isoformat()
            cursor.execute("""
                INSERT INTO DeletedFiles
                    (file_hash, original_archive_path, delete_vault_path,
                     deletion_timestamp, deletion_reason, file_size, creation_date,
                     is_restored)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (file_hash, original_path, vault_path, now, reason, file_size, creation_date))

            conn.commit()
            conn.close()

            logger.info(f"✓ Marked file as deleted: {os.path.basename(original_path)}")
            return True

        except Exception as e:
            logger.error(f"Failed to mark file as deleted: {e}", exc_info=True)
            return False

    def mark_file_as_restored(self, file_hash: str) -> bool:
        """
        Mark a deleted file as restored.
        Sets is_restored=1 and updates restore_timestamp.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            bool: True if updated successfully, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            now = datetime.now().isoformat()
            cursor.execute("""
                UPDATE DeletedFiles
                SET is_restored = 1,
                    restore_timestamp = ?
                WHERE file_hash = ?
                  AND is_restored = 0
            """, (now, file_hash))

            updated_count = cursor.rowcount
            conn.commit()
            conn.close()

            if updated_count > 0:
                logger.info(f"✓ Marked file as restored: {file_hash[:16]}...")
                return True
            else:
                logger.warning(f"No non-restored deletion record found for hash: {file_hash[:16]}...")
                return False

        except Exception as e:
            logger.error(f"Failed to mark file as restored: {e}")
            return False

    def delete_deleted_file_record(self, file_hash: str) -> bool:
        """
        Permanently delete a record from DeletedFiles table.
        Used when permanently deleting files from Delete Vault.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM DeletedFiles
                WHERE file_hash = ?
            """, (file_hash,))

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted_count > 0:
                logger.info(f"✓ Deleted record from DeletedFiles: {file_hash[:16]}...")
                return True
            else:
                logger.warning(f"No deletion record found for hash: {file_hash[:16]}...")
                return False

        except Exception as e:
            logger.error(f"Failed to delete DeletedFiles record: {e}")
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

    # -------------------------------------------------------------------------
    # Photo Review State Methods
    # -------------------------------------------------------------------------

    def get_photo_review_state(self) -> Optional[Dict[str, Any]]:
        """
        Get the Photo Review application state.

        Returns:
            Dictionary with state data or empty dict if not found
        """
        import json
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT photo_review_state FROM DatabaseMetadata WHERE id = 1
                """)
                row = cursor.fetchone()
                if row and row[0]:
                    return json.loads(row[0])
                return {}

        except Exception as e:
            logger.error(f"Failed to get photo review state: {e}")
            return {}

    def set_photo_review_state(self, state: Dict[str, Any]) -> bool:
        """
        Set the Photo Review application state.

        Args:
            state: Dictionary with state data (will be JSON-encoded)

        Returns:
            True if successful, False otherwise
        """
        import json
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                state_json = json.dumps(state)
                cursor.execute("""
                    UPDATE DatabaseMetadata SET photo_review_state = ? WHERE id = 1
                """, (state_json,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to set photo review state: {e}")
            return False

    def get_thumbnail_cache_dir(self) -> Optional[str]:
        """
        Get the thumbnail cache directory.

        Returns:
            Thumbnail cache directory path or None if not set
        """
        metadata = self.get_metadata()
        return metadata.get('thumbnail_cache_dir') if metadata else None

    def set_thumbnail_cache_dir(self, cache_dir: str) -> bool:
        """
        Set the thumbnail cache directory.

        Args:
            cache_dir: Path to thumbnail cache directory

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE DatabaseMetadata SET thumbnail_cache_dir = ? WHERE id = 1
                """, (cache_dir,))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to set thumbnail cache dir: {e}")
            return False

    # -------------------------------------------------------------------------
    # Content Hash Settings Methods
    # -------------------------------------------------------------------------

    def is_content_hash_enabled(self) -> bool:
        """
        Check if content-based (pixel) hashing is enabled for duplicate detection.

        Returns:
            True if enabled (default), False otherwise
        """
        try:
            self._ensure_metadata_table()

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT content_hash_enabled FROM DatabaseMetadata WHERE id = 1
                """)
                result = cursor.fetchone()

                if result is None or result[0] is None:
                    return True  # Default to enabled
                return bool(result[0])

        except Exception as e:
            logger.error(f"Error checking content hash enabled status: {e}", exc_info=True)
            return True  # Default to enabled on error

    def set_content_hash_enabled(self, enabled: bool) -> bool:
        """
        Enable or disable content-based (pixel) hashing for duplicate detection.

        Content hashing detects visually identical images even when their metadata
        or file bytes differ. This is useful for finding duplicates where one copy
        has been re-encoded or had EXIF data modified.

        Args:
            enabled: True to enable content hashing, False to disable

        Returns:
            True if successful, False otherwise
        """
        try:
            logger.info(f"→ set_content_hash_enabled({enabled}) called for database: {self.database_path}")
            self._ensure_metadata_table()

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if row exists
                cursor.execute("SELECT COUNT(*) FROM DatabaseMetadata WHERE id = 1")
                count = cursor.fetchone()[0]
                if count == 0:
                    logger.error("Cannot set content hash enabled: DatabaseMetadata row (id=1) does not exist!")
                    return False

                cursor.execute("""
                    UPDATE DatabaseMetadata
                    SET content_hash_enabled = ?
                    WHERE id = 1
                """, (1 if enabled else 0,))

                rows_affected = cursor.rowcount
                conn.commit()

                if rows_affected > 0:
                    logger.info(f"Content hashing {'ENABLED' if enabled else 'DISABLED'} successfully")
                    return True
                else:
                    logger.warning("UPDATE returned 0 rows affected - row may not exist")
                    return False

        except Exception as e:
            logger.error(f"Failed to set content hash enabled state: {e}", exc_info=True)
            return False

    # -------------------------------------------------------------------------
    # Saved Queries Methods
    # -------------------------------------------------------------------------

    def save_query(self, name: str, query_filters: Dict[str, Any],
                   description: str = None, is_favorite: bool = False) -> bool:
        """
        Save a named query to the database.

        Args:
            name: Unique name for the query
            query_filters: Dictionary of query filters
            description: Optional description
            is_favorite: Whether to mark as favorite

        Returns:
            True if successful, False otherwise
        """
        import json
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query_json = json.dumps(query_filters)
                created_date = datetime.now().isoformat()

                cursor.execute("""
                    INSERT OR REPLACE INTO SavedQueries
                    (name, description, query_json, is_favorite, is_system, created_date)
                    VALUES (?, ?, ?, ?, 0, ?)
                """, (name, description, query_json, 1 if is_favorite else 0, created_date))

                conn.commit()
                logger.info(f"Saved query: {name}")
                return True

        except Exception as e:
            logger.error(f"Failed to save query: {e}")
            return False

    def get_saved_queries(self, favorites_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get all saved queries.

        Args:
            favorites_only: If True, only return favorite queries

        Returns:
            List of query dictionaries
        """
        import json
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if favorites_only:
                    cursor.execute("""
                        SELECT id, name, description, query_json, is_favorite, is_system,
                               created_date, last_used_date, use_count
                        FROM SavedQueries
                        WHERE is_favorite = 1
                        ORDER BY use_count DESC, name ASC
                    """)
                else:
                    cursor.execute("""
                        SELECT id, name, description, query_json, is_favorite, is_system,
                               created_date, last_used_date, use_count
                        FROM SavedQueries
                        ORDER BY is_favorite DESC, use_count DESC, name ASC
                    """)

                results = []
                for row in cursor.fetchall():
                    results.append({
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'filters': json.loads(row[3]) if row[3] else {},
                        'is_favorite': bool(row[4]),
                        'is_system': bool(row[5]),
                        'created_date': row[6],
                        'last_used_date': row[7],
                        'use_count': row[8] or 0
                    })

                return results

        except Exception as e:
            logger.error(f"Failed to get saved queries: {e}")
            return []

    def get_query_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific saved query by name.

        Args:
            name: Query name

        Returns:
            Query dictionary or None if not found
        """
        import json
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, description, query_json, is_favorite, is_system,
                           created_date, last_used_date, use_count
                    FROM SavedQueries
                    WHERE name = ?
                """, (name,))

                row = cursor.fetchone()
                if row:
                    return {
                        'id': row[0],
                        'name': row[1],
                        'description': row[2],
                        'filters': json.loads(row[3]) if row[3] else {},
                        'is_favorite': bool(row[4]),
                        'is_system': bool(row[5]),
                        'created_date': row[6],
                        'last_used_date': row[7],
                        'use_count': row[8] or 0
                    }

                return None

        except Exception as e:
            logger.error(f"Failed to get query by name: {e}")
            return None

    def delete_saved_query(self, name: str) -> bool:
        """
        Delete a saved query by name.

        Args:
            name: Query name to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM SavedQueries WHERE name = ? AND is_system = 0
                """, (name,))
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Deleted query: {name}")
                    return True
                return False

        except Exception as e:
            logger.error(f"Failed to delete query: {e}")
            return False

    def update_query_usage(self, name: str) -> None:
        """
        Update last_used_date and increment use_count for a query.

        Args:
            name: Query name
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE SavedQueries
                    SET last_used_date = ?, use_count = use_count + 1
                    WHERE name = ?
                """, (datetime.now().isoformat(), name))
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to update query usage: {e}")

    def initialize_system_queries(self) -> None:
        """
        Initialize predefined system queries if they don't exist.
        """
        import json
        from datetime import timedelta

        system_queries = [
            {
                'name': 'Recent Imports (Last 7 Days)',
                'description': 'Photos imported in the last week',
                'filters': {
                    'import_date_from': (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'),
                    'import_date_to': datetime.now().strftime('%Y-%m-%d')
                }
            },
            {
                'name': 'Unreliable Dates - Pending',
                'description': 'Files with unreliable dates that need correction',
                'filters': {
                    'has_unreliable_date': True,
                    'has_corrected_date': False
                }
            },
            {
                'name': 'Needs Reorganization',
                'description': 'Files with corrected dates waiting for reorganization',
                'filters': {
                    'needs_reorganization': True
                }
            },
            {
                'name': 'Photos This Year',
                'description': 'All photos from current year',
                'filters': {
                    'creation_date_from': f'{datetime.now().year}-01-01',
                    'creation_date_to': f'{datetime.now().year}-12-31'
                }
            },
            {
                'name': 'All Photos',
                'description': 'Browse entire archive',
                'filters': {}
            }
        ]

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                for query in system_queries:
                    # Check if already exists
                    cursor.execute("""
                        SELECT id FROM SavedQueries WHERE name = ?
                    """, (query['name'],))

                    if cursor.fetchone() is None:
                        # Insert system query
                        cursor.execute("""
                            INSERT INTO SavedQueries
                            (name, description, query_json, is_favorite, is_system, created_date)
                            VALUES (?, ?, ?, 0, 1, ?)
                        """, (
                            query['name'],
                            query['description'],
                            json.dumps(query['filters']),
                            datetime.now().isoformat()
                        ))
                        logger.info(f"Initialized system query: {query['name']}")

                conn.commit()

        except Exception as e:
            logger.error(f"Failed to initialize system queries: {e}")
