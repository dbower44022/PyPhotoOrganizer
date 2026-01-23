
import datetime
import hashlib
import json
import logging
import os
import pillow_heif  # https://github.com/bigcat88/pillow_heif
import shutil
import sqlite3
import subprocess
import sys
import tempfile

from PIL import Image, ImageOps, UnidentifiedImageError
from PIL.ExifTags import TAGS
from PIL import IptcImagePlugin
from tqdm import tqdm

import utils
from photo_filter import PhotoFilter
import constants

# from pillow_heif import register_heif_opener

# Configure logging using shared utility
logger = utils.setup_logger(__name__, "DuplicateFileDetection_app_error.log")


class PhotoDatabase:
    """
    Context manager for handling SQLite database connections for photo hash storage.

    Usage:
        with PhotoDatabase('PhotoDB.db') as db:
            cursor = db.cursor()
            cursor.execute("SELECT * FROM UniquePhotos")
            results = cursor.fetchall()
    """

    def __init__(self, database_path=constants.DEFAULT_DATABASE_NAME):
        """
        Initialize the PhotoDatabase connection manager.

        Parameters:
            database_path (str): Path to the SQLite database file
        """
        self.database_path = database_path
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """
        Open database connection when entering context.

        Returns:
            PhotoDatabase: Self, allowing access to connection and cursor
        """
        try:
            # Use 30 second timeout to wait for locks
            self.conn = sqlite3.connect(self.database_path, timeout=30)
            # Enable WAL mode for better concurrency with audit logging
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA busy_timeout=30000")
            self.cursor = self.conn.cursor()
            logger.debug(f"Database connection opened to {self.database_path}")
            return self
        except Exception as e:
            logger.exception(f"Failed to connect to database {self.database_path}: {e}")
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Close database connection when exiting context.
        Commits changes if no exception occurred, rolls back otherwise.

        Parameters:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Exception traceback if an exception was raised
        """
        try:
            if exc_type is None:
                # No exception, commit changes
                if self.conn:
                    self.conn.commit()
                    logger.debug("Database changes committed")
            else:
                # Exception occurred, rollback
                if self.conn:
                    self.conn.rollback()
                    logger.warning(f"Database changes rolled back due to exception: {exc_val}")
        finally:
            # Always close the connection
            if self.conn:
                self.conn.close()
                logger.debug("Database connection closed")

        # Return False to propagate exceptions
        return False

    def connection(self):
        """Get the database connection object."""
        return self.conn

    def get_cursor(self):
        """Get a cursor for executing queries."""
        return self.cursor

    def initialize_database(self):
        """
        Create the UniquePhotos table if it doesn't exist (Schema v5).
        This should be called after entering the context.

        Schema v5 - UniquePhotos (Unified Design):
        - file_hash: SHA-256 hash of THIS file (PRIMARY KEY)
        - partial_hash: Hash of first N bytes (for quick comparison)
        - partial_hash_bytes: Number of bytes used for partial hash
        - file_size: File size in bytes
        - file_name: Current location (archive or version storage)
        - source_path: Original import source (NULL for revisions)
        - revised_photo: Parent file hash (NULL if original import)
        - revision_reason: Why revision was created ('rotation', 'crop', 'exif_edit', etc.)
        - revision_timestamp: When revision was created
        - create_datetime, create_year, create_month, create_day: File metadata

        Duplicate Detection (v5):
        - Simple primary key lookup: SELECT file_hash FROM UniquePhotos WHERE file_hash = ?
        - O(1) performance via indexed hash
        - No separate FileHashHistory table needed
        """
        try:
            # Create UniquePhotos table with revision tracking (v5 schema)
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS UniquePhotos (
                    file_hash TEXT PRIMARY KEY,
                    partial_hash TEXT,
                    partial_hash_bytes INTEGER,
                    file_size INTEGER NOT NULL,
                    file_name TEXT NOT NULL,
                    source_path TEXT,
                    revised_photo TEXT,
                    revision_reason TEXT,
                    revision_timestamp TEXT,
                    create_datetime TEXT,
                    create_year TEXT,
                    create_month TEXT,
                    create_day TEXT,
                    FOREIGN KEY (revised_photo) REFERENCES UniquePhotos(file_hash),
                    CHECK (revised_photo IS NULL OR revision_reason IS NOT NULL)
                )
            ''')

            # Create indexes for UniquePhotos
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_unique_partial_hash
                ON UniquePhotos(partial_hash)
            ''')

            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_unique_revised
                ON UniquePhotos(revised_photo)
            ''')

            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_unique_source
                ON UniquePhotos(source_path)
            ''')

            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_unique_year
                ON UniquePhotos(create_year)
            ''')

            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_unique_date
                ON UniquePhotos(create_year, create_month, create_day)
            ''')

            # Add content_hash column if it doesn't exist (auto-migration)
            self.cursor.execute("PRAGMA table_info(UniquePhotos)")
            columns = [row[1] for row in self.cursor.fetchall()]
            if 'content_hash' not in columns:
                logger.info("Upgrading database: adding content_hash column")
                self.cursor.execute("ALTER TABLE UniquePhotos ADD COLUMN content_hash TEXT")

            # Create index for content hash lookups
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_unique_content_hash
                ON UniquePhotos(content_hash)
            ''')

            self.conn.commit()
            logger.info("Database tables and indexes initialized successfully (Schema v5)")
        except Exception as e:
            logger.exception(f"Failed to initialize database tables: {e}")
            raise

    def get_all_hashes(self):
        """
        Retrieve all file hashes from the UniquePhotos table.

        Returns:
            list: List of file hash strings
        """
        try:
            self.cursor.execute("SELECT file_hash FROM UniquePhotos")
            results = self.cursor.fetchall()
            # Extract just the hash values from the tuple results
            return [row[0] for row in results]
        except Exception as e:
            logger.exception(f"Failed to retrieve hashes from database: {e}")
            raise

    def get_all_historical_hashes(self):
        """
        Retrieve all historical file hashes.

        In Schema v5, there is no separate FileHashHistory table.
        All hashes (including revision hashes) are stored directly in UniquePhotos.
        Since get_all_hashes() already returns all hashes from UniquePhotos,
        this method returns an empty set to maintain API compatibility.

        Returns:
            set: Empty set (all hashes are already in get_all_hashes())
        """
        return set()

    def insert_unique_photo(self, file_hash, file_path, create_datetime, create_year, create_month, create_day,
                           partial_hash=None, partial_hash_bytes=None, file_size=None, source_path=None,
                           content_hash=None):
        """
        Insert a new unique photo record into the database (Schema v5).

        Parameters:
            file_hash (str): SHA-256 hash of the full file
            file_path (str): Full path to the file (archive location)
            create_datetime (str): Creation date in YYYY-MM-DD format
            create_year (str): Year as string
            create_month (str): Month as zero-padded string
            create_day (str): Day as zero-padded string
            partial_hash (str, optional): SHA-256 hash of first N bytes
            partial_hash_bytes (int, optional): Number of bytes used for partial hash
            file_size (int, optional): File size in bytes
            source_path (str, optional): Original import source location
            content_hash (str, optional): SHA-256 hash of normalized pixel content
        """
        try:
            # Insert into UniquePhotos (v5 schema)
            # revised_photo=NULL, revision_reason=NULL (this is an original import, not a revision)
            self.cursor.execute(
                """INSERT INTO UniquePhotos
                   (file_hash, partial_hash, partial_hash_bytes, file_size, file_name, source_path,
                    revised_photo, revision_reason, revision_timestamp,
                    create_datetime, create_year, create_month, create_day, content_hash)
                   VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, ?, ?, ?)""",
                (file_hash, partial_hash, partial_hash_bytes, file_size, file_path, source_path,
                 create_datetime, create_year, create_month, create_day, content_hash)
            )

            logger.debug(f"Inserted unique photo: {file_path} (partial_hash: {partial_hash is not None}, source: {source_path}, content_hash: {content_hash is not None})")
        except sqlite3.IntegrityError:
            # Hash already exists (PRIMARY KEY constraint)
            logger.warning(f"Attempted to insert duplicate hash: {file_hash}")
            raise
        except Exception as e:
            logger.exception(f"Failed to insert photo record: {e}")
            raise

    def has_hash(self, file_hash):
        """
        Check if a file hash already exists in the database.
        This is useful for resume capability.

        Parameters:
            file_hash (str): SHA-256 hash to check

        Returns:
            bool: True if hash exists, False otherwise
        """
        try:
            self.cursor.execute("SELECT 1 FROM UniquePhotos WHERE file_hash = ? LIMIT 1", (file_hash,))
            result = self.cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.exception(f"Failed to check if hash exists: {e}")
            raise

    def get_file_path_for_hash(self, file_hash):
        """
        Get the file path for a given hash.

        Parameters:
            file_hash (str): SHA-256 hash to look up

        Returns:
            str or None: File path if found, None otherwise
        """
        try:
            self.cursor.execute("SELECT file_name FROM UniquePhotos WHERE file_hash = ? LIMIT 1", (file_hash,))
            result = self.cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.debug(f"Failed to get file path for hash: {e}")
            return None

    def has_partial_hash(self, partial_hash):
        """
        Check if a partial hash exists in the database.
        Returns list of full hashes that match this partial hash.

        Parameters:
            partial_hash (str): Partial SHA-256 hash to check

        Returns:
            list: List of full hashes that have matching partial hash
        """
        try:
            self.cursor.execute(
                "SELECT file_hash FROM UniquePhotos WHERE partial_hash = ?",
                (partial_hash,)
            )
            results = self.cursor.fetchall()
            return [row[0] for row in results]
        except Exception as e:
            logger.exception(f"Failed to check partial hash: {e}")
            raise

    def has_content_hash(self, content_hash):
        """
        Check if a content hash already exists in the database.

        Parameters:
            content_hash (str): SHA-256 content hash to check

        Returns:
            bool: True if content hash exists, False otherwise
        """
        if content_hash is None:
            return False
        try:
            self.cursor.execute(
                "SELECT 1 FROM UniquePhotos WHERE content_hash = ? LIMIT 1",
                (content_hash,)
            )
            result = self.cursor.fetchone()
            return result is not None
        except Exception as e:
            logger.exception(f"Failed to check if content hash exists: {e}")
            raise

    def get_files_by_content_hash(self, content_hash):
        """
        Get all files that have the specified content hash.

        Parameters:
            content_hash (str): SHA-256 content hash to look up

        Returns:
            list: List of dicts with file_hash, file_name, source_path for matching files
        """
        if content_hash is None:
            return []
        try:
            self.cursor.execute(
                """SELECT file_hash, file_name, source_path
                   FROM UniquePhotos
                   WHERE content_hash = ?""",
                (content_hash,)
            )
            results = self.cursor.fetchall()
            return [
                {"file_hash": row[0], "file_name": row[1], "source_path": row[2]}
                for row in results
            ]
        except Exception as e:
            logger.exception(f"Failed to get files by content hash: {e}")
            raise

    def update_content_hash(self, file_hash, content_hash):
        """
        Update the content hash for an existing record.
        Used for backfilling content hashes on existing files.

        Parameters:
            file_hash (str): Primary key of the record to update
            content_hash (str): The content hash to set

        Returns:
            bool: True if record was updated, False if not found
        """
        try:
            self.cursor.execute(
                "UPDATE UniquePhotos SET content_hash = ? WHERE file_hash = ?",
                (content_hash, file_hash)
            )
            return self.cursor.rowcount > 0
        except Exception as e:
            logger.exception(f"Failed to update content hash: {e}")
            raise

    def get_files_without_content_hash(self, limit=100):
        """
        Get files that don't have a content hash calculated yet.
        Used for backfilling content hashes.

        Parameters:
            limit (int): Maximum number of records to return

        Returns:
            list: List of dicts with file_hash and file_name (archive path)
        """
        try:
            self.cursor.execute(
                """SELECT file_hash, file_name
                   FROM UniquePhotos
                   WHERE content_hash IS NULL
                   LIMIT ?""",
                (limit,)
            )
            results = self.cursor.fetchall()
            return [
                {"file_hash": row[0], "file_name": row[1]}
                for row in results
            ]
        except Exception as e:
            logger.exception(f"Failed to get files without content hash: {e}")
            raise

    def count_files_without_content_hash(self):
        """
        Count how many files don't have a content hash yet.
        Used for progress display during backfill.

        Returns:
            int: Count of files without content_hash
        """
        try:
            self.cursor.execute(
                "SELECT COUNT(*) FROM UniquePhotos WHERE content_hash IS NULL"
            )
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.exception(f"Failed to count files without content hash: {e}")
            raise

    def get_archive_files_for_change_scan(self, scan_path: str, limit: int = 100, offset: int = 0):
        """
        Get files for change scanning that have content hashes.

        Used by the Archive Change Scanner to detect external modifications.
        Only returns files within the specified path that have content hashes.

        Parameters:
            scan_path (str): Path to scan (archive root or specific subfolder)
            limit (int): Maximum number of records to return (batch size)
            offset (int): Starting position for pagination

        Returns:
            list: List of dicts with file info including:
                  file_hash, file_name, content_hash, source_path,
                  create_datetime, create_year, create_month, create_day
        """
        try:
            # Ensure scan_path ends with separator for proper LIKE matching
            if not scan_path.endswith(os.sep):
                scan_path = scan_path + os.sep

            self.cursor.execute(
                """SELECT file_hash, file_name, content_hash, source_path,
                          create_datetime, create_year, create_month, create_day,
                          file_size
                   FROM UniquePhotos
                   WHERE file_name LIKE ? || '%'
                     AND content_hash IS NOT NULL
                   ORDER BY file_name
                   LIMIT ? OFFSET ?""",
                (scan_path, limit, offset)
            )
            results = self.cursor.fetchall()
            return [
                {
                    "file_hash": row[0],
                    "file_name": row[1],
                    "content_hash": row[2],
                    "source_path": row[3],
                    "create_datetime": row[4],
                    "create_year": row[5],
                    "create_month": row[6],
                    "create_day": row[7],
                    "file_size": row[8]
                }
                for row in results
            ]
        except Exception as e:
            logger.exception(f"Failed to get archive files for change scan: {e}")
            raise

    def count_archive_files_for_change_scan(self, scan_path: str) -> int:
        """
        Count files in the scan path that have content hashes.

        Used for progress display during archive change scanning.

        Parameters:
            scan_path (str): Path to scan (archive root or specific subfolder)

        Returns:
            int: Count of files with content_hash in the specified path
        """
        try:
            # Ensure scan_path ends with separator for proper LIKE matching
            if not scan_path.endswith(os.sep):
                scan_path = scan_path + os.sep

            self.cursor.execute(
                """SELECT COUNT(*)
                   FROM UniquePhotos
                   WHERE file_name LIKE ? || '%'
                     AND content_hash IS NOT NULL""",
                (scan_path,)
            )
            result = self.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.exception(f"Failed to count archive files for change scan: {e}")
            raise

    def create_revision(self, new_file_hash, parent_hash, revision_reason, file_path, file_size,
                       create_datetime, create_year, create_month, create_day,
                       partial_hash=None, partial_hash_bytes=None):
        """
        Insert a new revision record into UniquePhotos (Schema v5).

        Used when creating rotated, cropped, or EXIF-edited versions of photos.
        The new file gets its own UniquePhotos record linked to parent via revised_photo.

        Parameters:
            new_file_hash (str): SHA-256 hash of the new revision file
            parent_hash (str): Hash of the parent file this is derived from
            revision_reason (str): Why created ('rotation', 'crop', 'exif_edit', etc.)
            file_path (str): Full path to the revision file
            file_size (int): File size in bytes
            create_datetime (str): Creation date in YYYY-MM-DD format
            create_year (str): Year as string
            create_month (str): Month as zero-padded string
            create_day (str): Day as zero-padded string
            partial_hash (str, optional): SHA-256 hash of first N bytes
            partial_hash_bytes (int, optional): Number of bytes used for partial hash

        Returns:
            bool: True if successful, False otherwise
        """
        try:
            revision_timestamp = datetime.datetime.now().isoformat()

            self.cursor.execute(
                """INSERT INTO UniquePhotos
                   (file_hash, partial_hash, partial_hash_bytes, file_size, file_name, source_path,
                    revised_photo, revision_reason, revision_timestamp,
                    create_datetime, create_year, create_month, create_day)
                   VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?)""",
                (new_file_hash, partial_hash, partial_hash_bytes, file_size, file_path,
                 parent_hash, revision_reason, revision_timestamp,
                 create_datetime, create_year, create_month, create_day)
            )

            logger.info(f"Created revision: {new_file_hash[:16]}... (parent: {parent_hash[:16]}..., reason: {revision_reason})")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Attempted to create revision with duplicate hash: {new_file_hash}")
            return False
        except Exception as e:
            logger.exception(f"Failed to create revision record: {e}")
            return False

    def get_revision_chain(self, file_hash, max_depth=50):
        """
        Walk the revision chain from a file back to its original import.

        Parameters:
            file_hash (str): Hash of any file in the chain
            max_depth (int): Maximum chain depth to prevent infinite loops

        Returns:
            list: List of dicts with file info, ordered from original to current
                  [original, revision1, revision2, ..., current]
        """
        try:
            chain = []
            current_hash = file_hash
            depth = 0

            while current_hash and depth < max_depth:
                self.cursor.execute("""
                    SELECT file_hash, file_name, source_path, revised_photo,
                           revision_reason, revision_timestamp,
                           create_datetime, create_year, create_month, create_day
                    FROM UniquePhotos
                    WHERE file_hash = ?
                """, (current_hash,))

                result = self.cursor.fetchone()
                if not result:
                    break

                file_info = {
                    'file_hash': result[0],
                    'file_name': result[1],
                    'source_path': result[2],
                    'revised_photo': result[3],
                    'revision_reason': result[4],
                    'revision_timestamp': result[5],
                    'create_datetime': result[6],
                    'create_year': result[7],
                    'create_month': result[8],
                    'create_day': result[9]
                }

                # Prepend to chain (we're walking backwards)
                chain.insert(0, file_info)

                # Move to parent
                current_hash = result[3]  # revised_photo
                depth += 1

            return chain
        except Exception as e:
            logger.exception(f"Failed to get revision chain: {e}")
            return []

    def get_all_revisions_of(self, parent_hash):
        """
        Find all direct revisions (children) of a given file.

        Parameters:
            parent_hash (str): Hash of the parent file

        Returns:
            list: List of dicts with revision info
        """
        try:
            self.cursor.execute("""
                SELECT file_hash, file_name, revision_reason, revision_timestamp,
                       create_datetime, create_year, create_month, create_day
                FROM UniquePhotos
                WHERE revised_photo = ?
                ORDER BY revision_timestamp
            """, (parent_hash,))

            results = self.cursor.fetchall()
            revisions = []
            for row in results:
                revisions.append({
                    'file_hash': row[0],
                    'file_name': row[1],
                    'revision_reason': row[2],
                    'revision_timestamp': row[3],
                    'create_datetime': row[4],
                    'create_year': row[5],
                    'create_month': row[6],
                    'create_day': row[7]
                })

            return revisions
        except Exception as e:
            logger.exception(f"Failed to get revisions: {e}")
            return []

    def commit(self):
        """
        Manually commit pending changes to the database.
        Useful for periodic commits during long-running operations.
        """
        try:
            if self.conn:
                self.conn.commit()
                logger.debug("Manual commit executed")
        except Exception as e:
            logger.exception(f"Failed to commit changes: {e}")
            raise

    def mark_photo_as_deleted(self, file_hash):
        """
        Mark a photo as deleted in UniquePhotos table.
        Note: Actual deletion tracking happens in DeletedFiles table via DatabaseMetadata.

        Args:
            file_hash: SHA-256 hash of the file

        Returns:
            bool: True if successful
        """
        try:
            # For now, we don't modify UniquePhotos - the file record stays
            # Deletion tracking is handled by DeletedFiles table
            # This method is a placeholder for future functionality
            logger.debug(f"Photo marked as deleted: {file_hash[:16]}...")
            return True
        except Exception as e:
            logger.exception(f"Failed to mark photo as deleted: {e}")
            return False

    def restore_photo(self, file_hash, new_archive_path):
        """
        Update UniquePhotos with restored archive path after file is restored from Delete Vault.

        Args:
            file_hash: SHA-256 hash of the file
            new_archive_path: New path in archive after restoration

        Returns:
            bool: True if successful
        """
        try:
            self.cursor.execute("""
                UPDATE UniquePhotos
                SET file_name = ?
                WHERE file_hash = ?
            """, (new_archive_path, file_hash))

            if self.cursor.rowcount > 0:
                logger.info(f"✓ Updated photo path for restored file: {os.path.basename(new_archive_path)}")
                return True
            else:
                logger.warning(f"No photo record found for hash: {file_hash[:16]}...")
                return False

        except Exception as e:
            logger.exception(f"Failed to restore photo path: {e}")
            return False


def should_ignore_directory(dir_path, dir_name, ignored_patterns):
    """
    Check if a directory should be ignored based on patterns.

    Supports two types of patterns:
    1. Absolute paths: Full directory paths (e.g., /mnt/backup/old_photos)
    2. Name patterns: Wildcard patterns to match directory names (e.g., @eaDir, *.tmp, thumb*)

    Wildcards:
    - * = match any number of characters
    - ? = match exactly one character

    Pattern matching is case-insensitive.

    Parameters:
        dir_path (str): Full path to the directory
        dir_name (str): Name of the directory (basename)
        ignored_patterns (list): List of patterns to check

    Returns:
        bool: True if directory should be ignored, False otherwise
    """
    import fnmatch

    if not ignored_patterns:
        return False

    # Normalize paths for comparison
    dir_path_normalized = os.path.normpath(dir_path)

    for pattern in ignored_patterns:
        # Case-insensitive matching
        pattern_lower = pattern.lower()
        dir_path_lower = dir_path_normalized.lower()
        dir_name_lower = dir_name.lower()

        # Check if pattern is an absolute path
        if os.path.isabs(pattern):
            # Match against full directory path
            pattern_normalized = os.path.normpath(pattern).lower()
            if dir_path_lower == pattern_normalized or dir_path_lower.startswith(pattern_normalized + os.sep):
                logger.debug(f"Ignoring directory (absolute path match): {dir_path} matches {pattern}")
                return True
        else:
            # Match against directory name using wildcards
            if fnmatch.fnmatch(dir_name_lower, pattern_lower):
                logger.debug(f"Ignoring directory (name pattern match): {dir_name} matches {pattern}")
                return True

    return False


def get_file_list(sources, recursive=False, file_endings=None, progress_callback=None, ignored_directories=None):
    """
    Create a list all files in the source directory, and subdirectories if the recursive parameter is true.

    Parameters:
    source (list of strings that contain valid directory path): The source directory path.
    recursive (bool): If True, list files recursively. Default is False.
    file_endings (list): List of file endings/extensions to include. Default is None.
    progress_callback (callable): Optional callback function(dirs_scanned, total_dirs, current_dir) for progress updates.
    ignored_directories (list): List of directory patterns to ignore. Default is None.

    Returns:
    file_list: A list of file paths contained in the source folder provided.

    """
    try:
        logger.info("Initializing get_file_list")
        file_list = []
        logger.info(f"The list of directories passed = {sources}")
        if not sources:
            logger.info(f"There were no sources passed!")
            return None

        # Progress bar for scanning directories
        with tqdm(total=len(sources), desc="Scanning directories", unit="dir") as pbar:
            for idx, source in enumerate(sources):
                pbar.set_postfix_str(os.path.basename(source)[:constants.MAX_FILENAME_DISPLAY_LENGTH_SCAN])

                # Progress callback for GUI
                if progress_callback:
                    progress_callback(idx + 1, len(sources), source)

                try:
                    logger.info(f"Processing the source = {source}")
                    if recursive:
                        logger.info(f"Recursively processing {source}")
                        skipped_dirs_count = 0
                        for root, dirs, files in os.walk(source):
                            # Filter out ignored directories (modifies dirs in-place to prevent descending)
                            if ignored_directories:
                                original_dir_count = len(dirs)
                                dirs[:] = [d for d in dirs if not should_ignore_directory(
                                    os.path.join(root, d), d, ignored_directories
                                )]
                                skipped_count = original_dir_count - len(dirs)
                                if skipped_count > 0:
                                    skipped_dirs_count += skipped_count
                                    logger.debug(f"Filtered {skipped_count} directories from {root}")

                            logger.info(f"Processing root = {root}, and Subdirectories = {dirs}.")
                            files_processed_count = 0
                            files_added_count = 0
                            for file in files:
                                logger.info(f"Processing file {file} in {root}/{dirs}")
                                files_processed_count = files_processed_count + 1
                                verified_filename = VerifyFileType(os.path.join(root, file))
                                if verified_filename:
                                    logger.info(f"Processing file {verified_filename}")
                                    if not file_endings or verified_filename.lower().endswith(tuple(file_endings)):
                                        file_list.append(os.path.join(root, verified_filename))
                                        files_added_count = files_added_count + 1
                                        logger.info(f"appended - {verified_filename} to file_list")
                                    else:
                                        logger.info("hmmmm")
                                else:
                                    logger.info(f"The verifyfiletype routine determined that the file is not a valid type!")

                            logger.debug(f"Processed {files_processed_count } and Added {files_added_count} files from {root}/{dirs} to the list to process.")

                        if skipped_dirs_count > 0:
                            logger.info(f"Skipped {skipped_dirs_count} ignored directories in {source}")
                    else:
                        logger.info(f"EXCLUSIVELY processing {source}")
                        with os.scandir(source) as entries:
                            for entry in entries:
                                if entry.is_file() and (
                                    not file_endings or entry.name.lower().endswith(tuple(file_endings))
                                ):
                                    file_list.append(entry.path)
                    logger.debug(f"Added {len(file_list)} files from {source} to the list to process.")
                    pbar.update(1)

                except Exception as e:
                    logger.exception(f"\n Processing the source = {source} Failed : {sys.exc_info()} - {e}")
                    pbar.update(1)

        logger.info("Completed processing all sources passed!")
        return file_list
    except Exception as e:
        logger.exception(f"\n list_files process Failed : { sys.exc_info()} - {e}")


def _check_date_reliability(year, month, day, has_exif):
    """
    Check if a date is considered reliable.

    Args:
        year (str): Year as string
        month (str): Month as zero-padded string
        day (str): Day as zero-padded string
        has_exif (bool): Whether EXIF data was found

    Returns:
        bool: True if date is reliable, False otherwise
    """
    try:
        # Check for fallback year (1000)
        if year == constants.INVALID_DATE_YEAR:
            return False

        # Check if no EXIF data
        if not has_exif:
            return False

        # Convert to integer for comparison
        year_int = int(year)

        # Get current year
        from datetime import datetime as dt
        current_year = dt.now().year

        # Check for suspicious dates
        if year_int < 1990:  # Before consumer digital cameras
            return False

        if year_int > current_year + 1:  # Future date
            return False

        # Check for Unix epoch date (1970-01-01)
        if year == "1970" and month == "01" and day == "01":
            return False

        # Date passed all checks
        return True

    except Exception as e:
        logger.error(f"Error checking date reliability: {e}")
        return False  # Assume unreliable on error


def _is_video_file(file_path):
    """Check if file is a video based on extension."""
    file_ext = os.path.splitext(file_path)[1].lower()
    return file_ext in [ext.lower() for ext in constants.VIDEO_EXTENSIONS]


def _try_video_date(file_path, logger):
    """
    Try to extract recording date from video file metadata.

    Uses ffprobe (from FFmpeg) as primary method, with mutagen as fallback.

    Parameters:
        file_path (str): Path to the video file
        logger: Logger instance

    Returns:
        tuple: (datetime_obj, date_source) if successful, (None, None) if failed
               date_source will be 'video_metadata' or 'video_quicktime'
    """
    creation_date = None
    date_source = None

    # Method 1: Try ffprobe (most reliable, works with most video formats)
    try:
        # Run ffprobe to get creation_time from format tags
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode == 0:
            import json as json_module
            probe_data = json_module.loads(result.stdout)

            # Check format tags first (most common location)
            format_tags = probe_data.get('format', {}).get('tags', {})

            # Try various date tag names (different formats use different names)
            date_tags = [
                'creation_time',      # MP4, MOV (ISO format: 2024-01-15T10:30:00.000000Z)
                'date',               # Some formats
                'date_recorded',      # Some formats
                'com.apple.quicktime.creationdate',  # Apple QuickTime
            ]

            for tag_name in date_tags:
                # Check case-insensitively
                for key, value in format_tags.items():
                    if key.lower() == tag_name.lower() and value:
                        creation_date = _parse_video_date(value, logger)
                        if creation_date:
                            date_source = 'video_metadata'
                            logger.info(f"Found video date via ffprobe format tag '{key}': {creation_date}")
                            return creation_date, date_source

            # Also check stream tags (some videos store date in stream metadata)
            for stream in probe_data.get('streams', []):
                stream_tags = stream.get('tags', {})
                for tag_name in date_tags:
                    for key, value in stream_tags.items():
                        if key.lower() == tag_name.lower() and value:
                            creation_date = _parse_video_date(value, logger)
                            if creation_date:
                                date_source = 'video_metadata'
                                logger.info(f"Found video date via ffprobe stream tag '{key}': {creation_date}")
                                return creation_date, date_source

            logger.info("ffprobe found no creation date tags in video")

    except FileNotFoundError:
        logger.info("ffprobe not found - FFmpeg may not be installed")
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timed out for {file_path}")
    except Exception as e:
        logger.warning(f"ffprobe failed for {file_path}: {e}")

    # Method 2: Try mutagen library (fallback for MP4/M4V files)
    try:
        from mutagen.mp4 import MP4

        file_ext = os.path.splitext(file_path)[1].lower()
        if file_ext in ['.mp4', '.m4v', '.m4a', '.mov']:
            mp4_file = MP4(file_path)

            # Check for creation date in MP4 tags
            # The '©day' tag contains the date
            if '©day' in mp4_file.tags:
                date_value = mp4_file.tags['©day'][0]
                creation_date = _parse_video_date(date_value, logger)
                if creation_date:
                    date_source = 'video_quicktime'
                    logger.info(f"Found video date via mutagen ©day tag: {creation_date}")
                    return creation_date, date_source

            logger.info("mutagen found no creation date in MP4 file")

    except ImportError:
        logger.debug("mutagen library not installed - skipping MP4 tag check")
    except Exception as e:
        logger.debug(f"mutagen failed for {file_path}: {e}")

    # Method 3: Try reading QuickTime/MP4 atoms directly (last resort)
    try:
        creation_date = _try_quicktime_atom_date(file_path, logger)
        if creation_date:
            date_source = 'video_quicktime'
            return creation_date, date_source
    except Exception as e:
        logger.debug(f"QuickTime atom parsing failed: {e}")

    return None, None


def _parse_video_date(date_string, logger):
    """
    Parse various video date formats into a datetime object.

    Parameters:
        date_string (str): Date string from video metadata
        logger: Logger instance

    Returns:
        datetime or None: Parsed datetime object, or None if parsing failed
    """
    if not date_string:
        return None

    date_string = str(date_string).strip()

    # Common video date formats
    formats = [
        '%Y-%m-%dT%H:%M:%S.%fZ',      # ISO with microseconds and Z: 2024-01-15T10:30:00.000000Z
        '%Y-%m-%dT%H:%M:%SZ',          # ISO with Z: 2024-01-15T10:30:00Z
        '%Y-%m-%dT%H:%M:%S.%f%z',      # ISO with microseconds and timezone
        '%Y-%m-%dT%H:%M:%S%z',         # ISO with timezone: 2024-01-15T10:30:00+00:00
        '%Y-%m-%dT%H:%M:%S',           # ISO basic: 2024-01-15T10:30:00
        '%Y-%m-%d %H:%M:%S',           # Standard: 2024-01-15 10:30:00
        '%Y:%m:%d %H:%M:%S',           # EXIF-style: 2024:01:15 10:30:00
        '%Y-%m-%d',                     # Date only: 2024-01-15
        '%Y%m%d',                       # Compact: 20240115
        '%Y',                           # Year only: 2024
    ]

    for fmt in formats:
        try:
            # Handle timezone offset formats like +00:00 (Python < 3.11 needs colon removed)
            test_string = date_string
            if '+' in date_string or (date_string.count('-') > 2):
                # Try to normalize timezone format
                test_string = date_string.replace('Z', '+00:00')

            parsed = datetime.datetime.strptime(test_string, fmt)
            logger.debug(f"Parsed video date '{date_string}' with format '{fmt}'")
            return parsed
        except ValueError:
            continue

    # Try a more flexible approach for unusual formats
    try:
        # Extract just the date portion if present
        import re
        date_match = re.search(r'(\d{4})[:\-/](\d{1,2})[:\-/](\d{1,2})', date_string)
        if date_match:
            year, month, day = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
            if 1900 <= year <= 2100 and 1 <= month <= 12 and 1 <= day <= 31:
                return datetime.datetime(year, month, day)
    except Exception:
        pass

    logger.debug(f"Could not parse video date: {date_string}")
    return None


def _try_quicktime_atom_date(file_path, logger):
    """
    Try to read creation date from QuickTime/MP4 mvhd atom directly.

    This is a fallback method that reads the raw file structure.

    Parameters:
        file_path (str): Path to video file
        logger: Logger instance

    Returns:
        datetime or None: Creation date if found
    """
    import struct

    try:
        with open(file_path, 'rb') as f:
            # QuickTime files have atoms (boxes) with size and type
            # We're looking for moov -> mvhd which contains creation_time

            def read_atom_header():
                data = f.read(8)
                if len(data) < 8:
                    return None, None, 0
                size, atom_type = struct.unpack('>I4s', data)
                atom_type = atom_type.decode('latin-1', errors='ignore')
                if size == 1:  # Extended size
                    size = struct.unpack('>Q', f.read(8))[0]
                    return size - 16, atom_type, 16
                return size - 8, atom_type, 8

            # Search for moov atom (may be at beginning or end of file)
            f.seek(0, 2)  # End of file
            file_size = f.tell()
            f.seek(0)

            while f.tell() < file_size:
                data_size, atom_type, header_size = read_atom_header()
                if atom_type is None:
                    break

                if atom_type == 'moov':
                    # Found moov, now search for mvhd inside it
                    moov_end = f.tell() + data_size
                    while f.tell() < moov_end:
                        inner_size, inner_type, inner_header = read_atom_header()
                        if inner_type is None:
                            break

                        if inner_type == 'mvhd':
                            # Read mvhd atom
                            version = struct.unpack('>B', f.read(1))[0]
                            f.read(3)  # flags

                            if version == 0:
                                creation_time = struct.unpack('>I', f.read(4))[0]
                            else:
                                creation_time = struct.unpack('>Q', f.read(8))[0]

                            # QuickTime epoch is 1904-01-01
                            if creation_time > 0:
                                qt_epoch = datetime.datetime(1904, 1, 1)
                                creation_date = qt_epoch + datetime.timedelta(seconds=creation_time)
                                # Sanity check
                                if 1990 <= creation_date.year <= datetime.datetime.now().year + 1:
                                    logger.info(f"Found date in QuickTime mvhd atom: {creation_date}")
                                    return creation_date
                            return None

                        # Skip to next atom
                        f.seek(f.tell() + inner_size - (inner_header - 8) if inner_size > 0 else 0, 0)
                        if inner_size <= 0:
                            break
                    break

                # Skip to next atom
                if data_size > 0:
                    f.seek(f.tell() + data_size, 0)
                else:
                    break

    except Exception as e:
        logger.debug(f"QuickTime atom parsing error: {e}")

    return None


def _try_iptc_date(im, current_creation_date, current_date_source, current_has_exif, logger):
    """
    Try to extract date from IPTC metadata as fallback when EXIF is unavailable.

    Parameters:
        im: PIL Image object (must be open)
        current_creation_date: Current datetime value to use if IPTC fails
        current_date_source: Current date source string
        current_has_exif: Current has_exif boolean
        logger: Logger instance

    Returns:
        tuple: (creation_date, date_source, has_exif) - updated values if IPTC found
    """
    import datetime

    try:
        iptc_data = IptcImagePlugin.getiptcinfo(im)
        if iptc_data:
            # IPTC Date Created is tag (2, 55), format: YYYYMMDD
            # IPTC Time Created is tag (2, 60), format: HHMMSS or HHMMSS±HHMM
            iptc_date = iptc_data.get((2, 55))
            iptc_time = iptc_data.get((2, 60))

            if iptc_date:
                # Decode if bytes
                if isinstance(iptc_date, bytes):
                    iptc_date = iptc_date.decode('utf-8', errors='ignore')

                logger.info(f"Found IPTC Date Created: {iptc_date}")

                # Parse IPTC date (YYYYMMDD format)
                if len(iptc_date) >= 8 and iptc_date[:8].isdigit():
                    iptc_year = iptc_date[0:4]
                    iptc_month = iptc_date[4:6]
                    iptc_day = iptc_date[6:8]

                    # Build time component if available
                    hour, minute, second = 0, 0, 0
                    if iptc_time:
                        if isinstance(iptc_time, bytes):
                            iptc_time = iptc_time.decode('utf-8', errors='ignore')
                        if len(iptc_time) >= 6:
                            try:
                                hour = int(iptc_time[0:2])
                                minute = int(iptc_time[2:4])
                                second = int(iptc_time[4:6])
                            except ValueError:
                                pass

                    try:
                        creation_date = datetime.datetime(
                            int(iptc_year), int(iptc_month), int(iptc_day),
                            hour, minute, second
                        )
                        logger.info(f"Using IPTC date: {creation_date}")
                        return creation_date, 'iptc', True  # IPTC found, treat as reliable
                    except ValueError as ve:
                        logger.warning(f"Invalid IPTC date values: {iptc_date} - {ve}")
                else:
                    logger.info(f"IPTC date format not recognized: {iptc_date}")
            else:
                logger.info("No IPTC Date Created field found")
        else:
            logger.info("No IPTC data present in image")
    except Exception as iptc_err:
        logger.warning(f"Error reading IPTC data: {iptc_err}")

    # Return original values if IPTC extraction failed
    return current_creation_date, current_date_source, current_has_exif


def get_creation_date(file_path, database_path=None):
    """
    Get the creation date of a file and extract year, month, and day.
    Also tracks the date source and reliability.

    Date extraction priority for IMAGES:
    1. EXIF DateTimeOriginal (most accurate for camera photos)
    2. IPTC Date Created (fallback for images without EXIF)
    3. OS file metadata (creation time or modification time)
    4. Fallback to year 1000 on complete failure

    Date extraction priority for VIDEOS:
    1. Video metadata via ffprobe (creation_time tag)
    2. mutagen library for MP4/MOV files
    3. QuickTime atom parsing (mvhd creation_time)
    4. OS file metadata
    5. Fallback to year 1000 on complete failure

    Parameters:
    file_path (str): The full file name with path.
    database_path (str, optional): Path to database for user-specified unreliable paths check.

    Returns:
    tuple: A tuple containing (year, month, day, date_source, is_reliable).
           - year, month, day: Date components as zero-padded strings
           - date_source: 'exif', 'iptc', 'video_metadata', 'video_quicktime', 'os_metadata', or 'fallback'
           - is_reliable: Boolean indicating if date is considered reliable
    """
    try:
        logger.info("Initializing get_creation_date")
        # init required variables
        im = None
        date_source = 'os_metadata'  # Default to OS metadata
        has_exif = False  # Track if EXIF data exists
        exts = Image.registered_extensions()
        supported_extensions = {ex for ex, f in exts.items() if f in Image.OPEN}
        # logger.info(f"The supported extensions = {supported_extensions}.")

        # Get file extension (needed for EXIF check on all platforms)
        extension = os.path.splitext(file_path)[1]

        # STEP 1: Get OS-specific fallback timestamp
        if os.name == "nt":  # Windows
            # get the creation date/time from Windows
            try:
                creation_time = os.path.getctime(file_path)
            except Exception as e:
                logger.exception(f"The getctime function failure {e} occurred for file {file_path}")
                creation_time = os.path.getmtime(file_path)

            mod_time = os.path.getmtime(file_path)
            # Use creation_time as initial value (will be overridden by EXIF if available)
            creation_date = datetime.datetime.fromtimestamp(creation_time)
            logger.info(f"-- create_time = {creation_time}, creation_date = {creation_date}, extension = {extension}")

        else:  # macOS or Linux
            stat = os.stat(file_path)
            try:
                creation_time = stat.st_birthtime
                creation_date = datetime.datetime.fromtimestamp(creation_time)
            except AttributeError:
                # Fallback to the last metadata change time (best approximation)
                creation_time = stat.st_mtime
                creation_date = datetime.datetime.fromtimestamp(creation_time)
            logger.info(f"-- create_time = {creation_time}, creation_date = {creation_date}, extension = {extension}")

        # STEP 1b: Handle VIDEO files separately (they don't have EXIF/IPTC)
        if _is_video_file(file_path):
            logger.info(f"Processing VIDEO file: {file_path}")
            video_date, video_source = _try_video_date(file_path, logger)
            if video_date:
                creation_date = video_date
                date_source = video_source
                has_exif = True  # Treat video metadata as equivalent to EXIF for reliability
                logger.info(f"Using video metadata date: {creation_date} (source: {date_source})")
            else:
                logger.info(f"No video metadata date found, using OS date: {creation_date}")

            # Convert and return for video files
            year = f"{creation_date:%Y}"
            month = f"{creation_date:%m}"
            day = f"{creation_date:%d}"
            is_reliable = _check_date_reliability(year, month, day, has_exif)
            logger.debug(f"Video file {file_path} creation date: {year}-{month}-{day}, source: {date_source}, reliable: {is_reliable}")
            return year, month, day, date_source, is_reliable

        # STEP 2: Try to get EXIF data (PLATFORM-INDEPENDENT - runs on all OS)
        # Now try to get a more accurate date from EXIF data.
        try:
            processed_photos = 0
            not_photos = 0

            # TAGS is defined in PIL as a list of items returned
            _TAGS_r = dict(((v, k) for k, v in TAGS.items()))

            # logger.info(f"TAGS.items() = {TAGS.items()}")
            #logger.info(f"The extension for file is {extension}, and the supported_extensions = {supported_extensions}")
            if extension.lower() in supported_extensions:
                # verifying extension is valid saves time necessary for pillow to attempt open and fail, which can be considerable.
                logger.info(f"We have a pillow supported file type - {extension}. So attempt to get exif data.")

                with Image.open(file_path) as im:
                    try:
                        exif_data_PIL = im.getexif()
                        #logger.info(f"exif_data_PIL = {exif_data_PIL}")
                        '''
                        EXIF contains at least four dates:
                        DateTime -
                        DateTimeDigitized -
                        PreviewDateTime -
                        DateTimeOriginal -

                        GPS Date time can be retrieved from the  GPSTAGS object if necessary.
                        GPSDateTime -
                        '''
                        logger.info(f"____________________   List of Date Tags ____________________________________ ")
                        logger.info(f"_TAGS_r  for DateTimeOriginal = ")
                        logger.info(_TAGS_r["DateTimeOriginal"])
                        logger.info(_TAGS_r["Model"])
                        # logger.info(_TAGS_r["CreateDate"])
                        # logger.info(_TAGS_r["GPSDateTime"])
                        # logger.info(_TAGS_r["DateTimeCreated"])
                        logger.info(f"________________________________________________________ ")
                        if exif_data_PIL is not None:
                            # Safely check if DateTimeOriginal exists in EXIF
                            datetime_original_tag = _TAGS_r.get("DateTimeOriginal")
                            if datetime_original_tag and datetime_original_tag in exif_data_PIL:
                                # if a value for DateTimeOriginal is included in EXIF data, then use that as the fileDate.
                                fileDate = exif_data_PIL[datetime_original_tag]
                                logger.info(f"fileDate = {fileDate}")
                                # Validate EXIF date is not empty, not just whitespace, not "0000:00:00 00:00:00", and can be parsed
                                if (fileDate != '' and len(fileDate) > 10 and
                                    fileDate != "0000:00:00 00:00:00" and
                                    fileDate.strip() != '' and
                                    fileDate.strip().replace(':', '').replace(' ', '').strip() != ''):
                                    # we located a proper file date in the exif data, so use that instead of date from OS.
                                    # Try to parse the EXIF date - if it fails, fall back to OS date
                                    try:
                                        has_exif = True  # Mark that we found EXIF data
                                        date_source = 'exif'  # Date came from EXIF
                                        logger.info("------------------  File Dates --------------------------")
                                        logger.info(f"Date from os {datetime.datetime.fromtimestamp(creation_time)}, date from EXIF {fileDate}")
                                        exif_datetime = datetime.datetime.strptime(fileDate, '%Y:%m:%d %H:%M:%S')
                                        logger.info(f"Converted EXIF fileDate = {exif_datetime}")
                                        logger.info("--------------------------------------------")

                                        if creation_date != exif_datetime:
                                            logger.info("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                                            logger.info("The OS and EXIF dates do NOT match, so using the EXIF date!")
                                            logger.info("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
                                            creation_date = exif_datetime
                                        else:
                                            logger.info("The OS and EXIF dates matched, so using them both :)")
                                    except ValueError as e:
                                        logger.warning(f"EXIF date '{fileDate}' could not be parsed, falling back to OS date: {e}")
                                        has_exif = False
                                        date_source = 'os_metadata'

                                    im.close()
                                    processed_photos += 1
                                    logger.info(f"\r{processed_photos} photos processed, {not_photos} not processed")
                                else:
                                    logger.info("fileDate does not exist in EXIF data. Trying IPTC...")
                                    # Try IPTC as fallback
                                    creation_date, date_source, has_exif = _try_iptc_date(im, creation_date, date_source, has_exif, logger)
                            else:
                                logger.info(f"exif_data_PIL[_TAGS_r[DateTimeOriginal]] does not exist. Trying IPTC...")
                                # Try IPTC as fallback
                                creation_date, date_source, has_exif = _try_iptc_date(im, creation_date, date_source, has_exif, logger)
                        else:
                            not_photos += 1
                            logger.info(f"No EXIF data was present. Checking for IPTC data...")
                            # Try IPTC as fallback
                            creation_date, date_source, has_exif = _try_iptc_date(im, creation_date, date_source, has_exif, logger)
                            logger.info(f"\r{processed_photos} photos processed, {not_photos} not processed")
                    except Exception as e:
                        logger.exception(f"The failure {e} occurred for file {file_path}")
                im.close()
            else:
                logger.info(f"The file {file_path}, with an extension of {extension} cannot be opened by pillow to determine date information, so return the OS date created. Supported Extensions = {supported_extensions}")

        except IOError as io_err:
            not_photos += 1
            logger.error(f"IOError when processing file {file_path}- {io_err}.")
            logger.info(f"\r{processed_photos} photos processed, {not_photos} not processed")
            pass
        except OSError as os_err:
            not_photos += 1
            logger.error(f"OSError when processing file {file_path}- {os_err}.")
            logger.info(f"\r{processed_photos} photos processed, {not_photos} not processed")
            pass
        except KeyError as key_err:
            logger.error(f"KeyError when processing file {file_path} - {key_err}.")
            not_photos += 1
            pass
        except Exception as e:
            logger.exception(f"When processing file {file_path} this error occurred:  {e}")

        logger.info(f"Completed locating date for {file_path}, now convert it.... {creation_date}")

        # make sure to return month and day as two digit strings and year as a string!
        year = f"{creation_date:%Y}"
        month = f"{creation_date:%m}"
        day = f"{creation_date:%d}"

        # Check reliability
        is_reliable = _check_date_reliability(year, month, day, has_exif)

        logger.debug(f"File {file_path} creation date: {year}-{month}-{day}, source: {date_source}, reliable: {is_reliable}")
        return year, month, day, date_source, is_reliable

    except Exception as e:
        logger.exception(f"\n When processing file {file_path},  get_creation_date process Failed : {sys.exc_info()} == {e}")
        if im:
            im.close()
        year = constants.INVALID_DATE_YEAR
        month = constants.INVALID_DATE_MONTH
        day = constants.INVALID_DATE_DAY
        date_source = 'fallback'
        is_reliable = False  # Fallback is always unreliable
        return year, month, day, date_source, is_reliable

def hash_file(filename):
    """
    Calculates the SHA-256 hash of an entire file.

    Parameters:
        filename (str): Path to the file to hash

    Returns:
        str: Hexadecimal SHA-256 hash of the file
    """
    try:
        logger.info(f"Initiating full hash for {filename}")
        hasher = hashlib.sha256()
        with open(filename, 'rb') as file:
            while True:
                chunk = file.read(constants.FILE_READ_CHUNK_SIZE)  # Read file in chunks
                if not chunk:
                    break
                hasher.update(chunk)
        hash_result = hasher.hexdigest()
        logger.info(f"Full hash for {filename}: {hash_result}")
        return hash_result

    except Exception as duplicate_e:
        logger.exception(f"The hash_file routine failed - {duplicate_e}")
        raise


def hash_file_partial(filename, num_bytes=constants.PARTIAL_HASH_BYTES):
    """
    Calculates the SHA-256 hash of the first N bytes of a file.

    This is used as a quick preliminary check before hashing the entire file.
    If partial hashes don't match, files cannot be duplicates.
    If partial hashes match, must verify with full hash.

    Parameters:
        filename (str): Path to the file to hash
        num_bytes (int): Number of bytes from start of file to hash (default: 16KB)

    Returns:
        str: Hexadecimal SHA-256 hash of first num_bytes of the file
    """
    try:
        logger.debug(f"Calculating partial hash ({num_bytes} bytes) for {filename}")
        hasher = hashlib.sha256()
        with open(filename, 'rb') as file:
            # Read only the first num_bytes
            chunk = file.read(num_bytes)
            hasher.update(chunk)

        hash_result = hasher.hexdigest()
        logger.debug(f"Partial hash for {filename}: {hash_result}")
        return hash_result

    except Exception as e:
        logger.exception(f"The hash_file_partial routine failed - {e}")
        raise


def hash_image_content(file_path):
    """
    Calculate SHA-256 hash of the normalized pixel content of an image.

    This hash is based purely on the visual content (RGB pixel data), ignoring
    all metadata including EXIF. Two images that look identical will produce
    the same content hash even if their metadata differs.

    The image is normalized by:
    1. Applying EXIF rotation via ImageOps.exif_transpose()
    2. Converting to RGB mode (strips alpha channel, handles grayscale)
    3. Hashing the raw pixel bytes

    Parameters:
        file_path (str): Path to the image file

    Returns:
        str or None: SHA-256 hex digest of pixel content, or None for:
            - Video files (cannot be processed by PIL)
            - Files that fail to load
            - Any other processing errors
    """
    # Check if file is a video (cannot process with PIL)
    video_extensions = {'.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg', '.3gp'}
    file_ext = os.path.splitext(file_path)[1].lower()
    if file_ext in video_extensions:
        logger.debug(f"Skipping content hash for video file: {file_path}")
        return None

    try:
        # Register HEIF opener if needed
        pillow_heif.register_heif_opener()

        # Open and load the image
        with Image.open(file_path) as img:
            # Apply EXIF rotation to normalize orientation
            img = ImageOps.exif_transpose(img)

            # Convert to RGB mode for consistent hashing
            # This handles RGBA (strips alpha), L (grayscale), P (palette), etc.
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Get raw pixel data as bytes
            pixel_data = img.tobytes()

            # Calculate SHA-256 hash of pixel data
            hasher = hashlib.sha256()
            hasher.update(pixel_data)
            content_hash = hasher.hexdigest()

            logger.debug(f"Content hash for {file_path}: {content_hash}")
            return content_hash

    except UnidentifiedImageError:
        logger.debug(f"Cannot identify image format for content hash: {file_path}")
        return None
    except Exception as e:
        logger.warning(f"Failed to calculate content hash for {file_path}: {e}")
        return None


def find_duplicates(files, hashes, database_path=constants.DEFAULT_DATABASE_NAME, batch_size=constants.DEFAULT_BATCH_SIZE,
                   partial_hash_enabled=True, partial_hash_bytes=constants.PARTIAL_HASH_BYTES,
                   partial_hash_min_file_size=constants.PARTIAL_HASH_MIN_FILE_SIZE,
                   config=None, progress_callback=None, audit_manager=None, session_id=None, should_stop=None,
                   content_hash_enabled=True):
    """ Looks through a list of files and returns a list of duplicate and original files using two-stage hashing.

        Two-Stage Hashing Strategy:
        1. For files >= partial_hash_min_file_size:
           - Calculate quick partial hash (first N bytes)
           - If partial hash not in DB: file is unique
           - If partial hash in DB: calculate full hash to confirm
        2. For files < partial_hash_min_file_size:
           - Skip partial hash, calculate full hash directly

        Photo Filtering:
        - Before hashing, files are checked to determine if they are real photographs
        - Filters out icons, web graphics, thumbnails based on size, dimensions, filename
        - Filtered files are tracked separately and not added to the database

        Parameters:
        files - a list of files to be processed including the directory path to access the file
        hashes - a list of all previously located file hashes.
        database_path - path to the SQLite database file (default: constants.DEFAULT_DATABASE_NAME)
        batch_size - number of files to process before committing to database (default: constants.DEFAULT_BATCH_SIZE)
                     Set to 0 to only commit at the end (not recommended for large batches)
        partial_hash_enabled - whether to use partial hashing optimization (default: True)
        partial_hash_bytes - number of bytes to hash for partial check (default: constants.PARTIAL_HASH_BYTES = 16KB)
        partial_hash_min_file_size - minimum file size to use partial hashing (default: constants.PARTIAL_HASH_MIN_FILE_SIZE = 1MB)
        config - Config object with photo filter settings (optional, if None filtering is disabled)
        should_stop - callable that returns True if processing should be cancelled (optional)
            Used for graceful shutdown - when True is returned, commits partial progress and exits cleanly.
        content_hash_enabled - whether to calculate content (pixel) hashes for duplicate detection (default: True)
            Content hashing detects visually identical images with different metadata/EXIF.

        Returns:
            results - a dictionary containing:
                duplicate_files - list of files that already exist in the database
                original_files - list of new unique files that were added to database
                filtered_files - list of files that were filtered out (not real photos)
                content_duplicate_files - list of files with same pixel content as existing files
                status - "completed" if successful, "cancelled" if stopped early
                files_processed - total number of files processed
                files_skipped - number of files skipped (already in DB from previous run)
                filter_statistics - statistics about filtering (if enabled)

        Resume Capability:
            If processing is interrupted, you can re-run with the same file list.
            Files already in the database will be detected and skipped automatically.

        Periodic Commits:
            Database is committed every 'batch_size' files to preserve progress.
            If a crash occurs, all files up to the last commit are saved.

        TODO: Modify data base to contain a 512 byte filed containing the hash for the first 512 bytes in a file.  This will allow us to quickly locate new files by checking the first
              512 bytes.  If it is unique, we know the entire file is unique.  if it matches, we need to hash the entire file to determine if it is truly a duplicate.
              We may want to use a larger value for the number of bytes to process initially, but when we do that, we need to reset all of the values in the database.
              The primary objective of this function is to eliminate the time to process very large files when they are clearly not a duplicate.  This will decrease the time necessary to process new files dramatically.
    """
    try:
        # check existence of parameters
        if hashes:
            # logger.info(f"hashes was provided! - {hashes}")
            logger.info(f"hashes was successfully loaded with {len(hashes)} existing unique photos")
        else:
            logger.info("hashes was not provided")

        # Load historical hashes for duplicate detection after EXIF modifications
        historical_hashes = set()
        try:
            with PhotoDatabase(database_path) as temp_db:
                historical_hashes = temp_db.get_all_historical_hashes()
                logger.info(f"Loaded {len(historical_hashes)} historical hashes for duplicate detection")
        except Exception as e:
            logger.warning(f"Could not load historical hashes (table may not exist yet): {e}")
            hashes = []

        duplicate_files = []
        original_files = []
        filtered_files = []
        content_duplicate_files = []  # Files with same pixel content as existing files
        files_processed = 0
        files_skipped = 0
        files_since_last_commit = 0
        unreliable_dates_count = 0  # Count files with suspicious/unreliable dates
        unreliable_dates_to_insert = []  # Batch unreliable date records to avoid DB lock

        # NEW: Additional counters for enhanced progress reporting
        photos_processed = 0  # Count of image files processed
        videos_processed = 0  # Count of video files processed
        bytes_processed = 0  # Total bytes processed for throughput calculation
        current_file_size = 0  # Size of currently processing file

        # Date source breakdown counters
        date_from_exif = 0  # Files with EXIF date (includes IPTC)
        date_from_os = 0  # Files using OS metadata date
        date_from_video = 0  # Files using video metadata date

        # Initialize photo filter if config provided
        photo_filter = None
        if config:
            try:
                photo_filter = PhotoFilter(config)
                if photo_filter.enabled:
                    logger.info("Photo filtering ENABLED - non-photos will be filtered out")
                else:
                    logger.info("Photo filtering DISABLED in config")
            except Exception as e:
                logger.warning(f"Failed to initialize PhotoFilter: {e}. Continuing without filtering.")
                photo_filter = None

        logger.info(f"Starting to process {len(files)} files with batch_size={batch_size}")

        # Initialize cancellation flag (must be outside context for visibility in return)
        was_cancelled = False

        # Use the PhotoDatabase context manager
        with PhotoDatabase(database_path) as db:
            # Create progress bar for file processing
            with tqdm(total=len(files), desc="Processing files", unit="file",
                     bar_format='{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]') as pbar:
                for file_index, filename in enumerate(files, 1):
                    # Check for cancellation at the start of each file
                    if should_stop and should_stop():
                        logger.info(f"Processing cancelled by user after {files_processed} files")
                        was_cancelled = True
                        # Commit any uncommitted work before exiting
                        if files_since_last_commit > 0:
                            db.commit()
                            logger.info(f"*** CANCELLATION COMMIT: Saved {files_since_last_commit} files before stopping ***")
                        break

                    try:
                        # Update progress bar description with current file
                        pbar.set_postfix_str(os.path.basename(filename)[:constants.MAX_FILENAME_DISPLAY_LENGTH])

                        # Get current file size for progress display
                        try:
                            current_file_size = os.path.getsize(filename) if os.path.isfile(filename) else 0
                        except Exception:
                            current_file_size = 0

                        # Progress callback for GUI - also checks for stop signal
                        if progress_callback:
                            stats = {
                                # Existing stats
                                'unique': len(original_files),
                                'duplicates': len(duplicate_files),
                                'filtered': len(filtered_files),
                                # NEW: Content duplicates count
                                'content_duplicates': len(content_duplicate_files),
                                # NEW: Unreliable dates count
                                'unreliable_dates': unreliable_dates_count,
                                # NEW: File type breakdown
                                'photos_processed': photos_processed,
                                'videos_processed': videos_processed,
                                # NEW: Date source breakdown
                                'date_from_exif': date_from_exif,
                                'date_from_os': date_from_os,
                                'date_from_video': date_from_video,
                                # NEW: Throughput data
                                'bytes_processed': bytes_processed,
                                'current_file_size': current_file_size,
                            }
                            callback_result = progress_callback(file_index, len(files), filename, stats)
                            # If callback returns True, it means stop was requested
                            if callback_result:
                                logger.info(f"Processing cancelled via callback after {files_processed} files")
                                was_cancelled = True
                                # Commit any uncommitted work before exiting
                                if files_since_last_commit > 0:
                                    db.commit()
                                    logger.info(f"*** CANCELLATION COMMIT: Saved {files_since_last_commit} files before stopping ***")
                                break

                        if not os.path.isfile(filename):
                            logger.warning(f"Skipping non-file entry: {filename}")
                            pbar.update(1)
                            continue

                        logger.info(f"Processing file {file_index}/{len(files)}: {filename}")

                        # PHOTO FILTERING: Check if file is a real photograph
                        if photo_filter and photo_filter.enabled:
                            if not photo_filter.is_photo(filename):
                                filter_reason = photo_filter.get_filter_reason(filename)
                                logger.info(f"FILTERED OUT (non-photo): {filename} - Reason: {filter_reason}")

                                # Gather comprehensive file information for UI display
                                filtered_file = {
                                    "file_path": filename,
                                    "filter_reason": filter_reason
                                }

                                # Get file size
                                try:
                                    filtered_file["file_size"] = os.path.getsize(filename)
                                except Exception as e:
                                    logger.warning(f"Failed to get file size for {filename}: {e}")
                                    filtered_file["file_size"] = 0

                                # Get image properties
                                try:
                                    from PIL import Image
                                    with Image.open(filename) as img:
                                        filtered_file["width"] = img.size[0]
                                        filtered_file["height"] = img.size[1]
                                        filtered_file["format"] = img.format or "Unknown"
                                        filtered_file["mode"] = img.mode

                                        # Check for EXIF data
                                        try:
                                            exif_data = img.getexif()
                                            filtered_file["has_exif"] = exif_data is not None and len(exif_data) > 0
                                        except Exception as exif_e:
                                            logger.debug(f"Failed to read EXIF from {filename}: {exif_e}")
                                            filtered_file["has_exif"] = False
                                except Exception as e:
                                    # If we can't open the image, set defaults
                                    filtered_file["width"] = 0
                                    filtered_file["height"] = 0
                                    filtered_file["format"] = "Unknown"
                                    filtered_file["mode"] = "Unknown"
                                    filtered_file["has_exif"] = False

                                # Individual filter check results (for detailed review)
                                filtered_file["passes_size"] = photo_filter._check_file_size(filename)
                                try:
                                    with Image.open(filename) as img:
                                        filtered_file["passes_dimensions"] = photo_filter._check_dimensions(img, filename)
                                        filtered_file["passes_square_check"] = photo_filter._check_square_icon(img, filename)
                                except Exception as img_e:
                                    logger.debug(f"Failed to check dimensions for {filename}: {img_e}")
                                    filtered_file["passes_dimensions"] = False
                                    filtered_file["passes_square_check"] = False

                                filtered_file["passes_filename"] = photo_filter._check_filename(filename)

                                filtered_files.append(filtered_file)

                                # Log filtered file to audit
                                if audit_manager and session_id:
                                    try:
                                        # Commit to release any pending locks before audit write
                                        db.commit()
                                        audit_manager.log_file_operation(
                                            session_id=session_id,
                                            source_path=filename,
                                            operation='skip_filtered',
                                            status='skipped',
                                            file_size=filtered_file.get("file_size", 0),
                                            filter_reason=filter_reason,
                                            filter_details=f"W:{filtered_file.get('width', 0)}xH:{filtered_file.get('height', 0)}"
                                        )
                                    except Exception as audit_err:
                                        logger.debug(f"Failed to log audit for filtered file: {audit_err}")

                                pbar.update(1)
                                continue

                        # Get file size to decide on hashing strategy
                        try:
                            file_size = os.path.getsize(filename)
                        except Exception as e:
                            logger.exception(f"Failed to get file size for {filename}: {e}")
                            pbar.update(1)
                            continue

                        # Track file type (photo vs video) for progress display
                        is_video = _is_video_file(filename)
                        if is_video:
                            videos_processed += 1
                        else:
                            photos_processed += 1

                        # Update bytes processed for throughput calculation
                        bytes_processed += file_size

                        # TWO-STAGE HASHING OPTIMIZATION
                        file_hash = None
                        partial_hash = None
                        use_partial_hash = (partial_hash_enabled and
                                           file_size >= partial_hash_min_file_size)

                        if use_partial_hash:
                            # STAGE 1: Quick partial hash check
                            try:
                                partial_hash = hash_file_partial(filename, partial_hash_bytes)
                                logger.info(f"Partial hash calculated for {filename} ({utils.format_file_size(file_size)})")
                            except Exception as e:
                                logger.exception(f"Partial hash failed for {filename}: {e}")
                                pbar.update(1)
                                continue

                            # Check if partial hash exists in database
                            matching_full_hashes = db.has_partial_hash(partial_hash)

                            if matching_full_hashes:
                                # Potential duplicate - STAGE 2: Verify with full hash
                                logger.info(f"Partial hash match found! Calculating full hash to confirm for {filename}")
                                try:
                                    file_hash = hash_file(filename)
                                except Exception as e:
                                    logger.exception(f"Full hash failed for {filename}: {e}")
                                    pbar.update(1)
                                    continue

                                # Check if full hash matches any of the candidates or historical hashes
                                if file_hash in matching_full_hashes or file_hash in historical_hashes:
                                    logger.info(f"DUPLICATE CONFIRMED: Full hash matches (current or historical) for {filename}")
                                    # This is a true duplicate
                                    files_skipped += 1
                                    duplicate_file = {
                                        "file_hash": file_hash,
                                        "file_path": filename,
                                        "file_create_datetime": "N/A"
                                    }
                                    duplicate_files.append(duplicate_file)
                                    files_processed += 1

                                    # Log duplicate to audit and record relationship
                                    if audit_manager and session_id:
                                        try:
                                            # Get original file path for this hash
                                            original_path = db.get_file_path_for_hash(file_hash)
                                            # Commit to release any pending locks before audit write
                                            db.commit()
                                            audit_manager.log_file_operation(
                                                session_id=session_id,
                                                source_path=filename,
                                                operation='duplicate detected',
                                                status='duplicate',
                                                file_hash=file_hash,
                                                file_size=file_size,
                                                duplicate_of_hash=file_hash
                                            )
                                            audit_manager.record_duplicate(
                                                session_id=session_id,
                                                original_hash=file_hash,
                                                original_path=original_path or 'unknown',
                                                duplicate_path=filename
                                            )
                                        except Exception as audit_err:
                                            logger.debug(f"Failed to log audit for duplicate: {audit_err}")

                                    pbar.update(1)
                                    continue
                                else:
                                    # Partial hash collision - different files with same first N bytes
                                    logger.info(f"Partial hash collision (rare!) - files differ: {filename}")
                                    # Continue to save as unique file
                            else:
                                # No partial hash match - file is definitely unique
                                # Calculate full hash for storage
                                logger.info(f"No partial hash match - file is unique: {filename}")
                                try:
                                    file_hash = hash_file(filename)
                                except Exception as e:
                                    logger.exception(f"Full hash failed for {filename}: {e}")
                                    pbar.update(1)
                                    continue

                        else:
                            # Small file - skip partial hash, go straight to full hash
                            logger.debug(f"Small file ({utils.format_file_size(file_size)}) - using full hash only: {filename}")
                            try:
                                file_hash = hash_file(filename)
                            except Exception as e:
                                logger.exception(f"Hash failed for {filename}: {e}")
                                pbar.update(1)
                                continue

                            # Check if hash already exists in database (current or historical)
                            if db.has_hash(file_hash) or file_hash in historical_hashes:
                                logger.info(f"File hash already in database (current or historical): {filename}")
                                files_skipped += 1
                                duplicate_file = {
                                    "file_hash": file_hash,
                                    "file_path": filename,
                                    "file_create_datetime": "N/A"
                                }
                                duplicate_files.append(duplicate_file)
                                files_processed += 1

                                # Log duplicate to audit and record relationship
                                if audit_manager and session_id:
                                    try:
                                        original_path = db.get_file_path_for_hash(file_hash)
                                        # Commit to release any pending locks before audit write
                                        db.commit()
                                        audit_manager.log_file_operation(
                                            session_id=session_id,
                                            source_path=filename,
                                            operation='duplicate detected',
                                            status='duplicate',
                                            file_hash=file_hash,
                                            file_size=file_size,
                                            duplicate_of_hash=file_hash
                                        )
                                        audit_manager.record_duplicate(
                                            session_id=session_id,
                                            original_hash=file_hash,
                                            original_path=original_path or 'unknown',
                                            duplicate_path=filename
                                        )
                                    except Exception as audit_err:
                                        logger.debug(f"Failed to log audit for duplicate: {audit_err}")

                                pbar.update(1)
                                continue

                        # Check against in-memory hash list (current batch) and historical hashes
                        if file_hash in hashes or file_hash in historical_hashes:
                            logger.info(f"Duplicate found (in batch or historical): {filename}")
                            duplicate_file = {
                                "file_hash": file_hash,
                                "file_path": filename,
                                "file_create_datetime": "N/A"
                            }
                            duplicate_files.append(duplicate_file)
                            files_processed += 1

                            # Log duplicate to audit and record relationship
                            if audit_manager and session_id:
                                try:
                                    original_path = db.get_file_path_for_hash(file_hash)
                                    # Commit to release any pending locks before audit write
                                    db.commit()
                                    audit_manager.log_file_operation(
                                        session_id=session_id,
                                        source_path=filename,
                                        operation='duplicate detected',
                                        status='duplicate',
                                        file_hash=file_hash,
                                        file_size=file_size,
                                        duplicate_of_hash=file_hash
                                    )
                                    audit_manager.record_duplicate(
                                        session_id=session_id,
                                        original_hash=file_hash,
                                        original_path=original_path or 'unknown',
                                        duplicate_path=filename
                                    )
                                except Exception as audit_err:
                                    logger.debug(f"Failed to log audit for duplicate: {audit_err}")

                            pbar.update(1)
                        else:
                            # NEW UNIQUE FILE - Save to database
                            logger.info(f"Unique file - saving to database: {filename}")
                            hashes.append(file_hash)

                            # Get the create date with reliability info
                            file_year, file_month, file_day, date_source, is_reliable = get_creation_date(filename, database_path)
                            file_create_date = f"{file_year}-{file_month}-{file_day}"

                            # Track date source breakdown for progress display
                            if date_source in ('exif', 'iptc'):
                                date_from_exif += 1
                            elif date_source in ('video_metadata', 'video_quicktime'):
                                date_from_video += 1
                            else:  # 'os_metadata', 'fallback', or other
                                date_from_os += 1

                            # Check if date is unreliable and determine flag reason
                            if not is_reliable:
                                # Import database metadata for unreliable dates tracking
                                from database_metadata import DatabaseMetadata

                                # Determine flag reason
                                flag_reason = None
                                if file_year == constants.INVALID_DATE_YEAR:
                                    flag_reason = 'year_1000'
                                elif date_source != 'exif':
                                    flag_reason = 'no_exif'
                                else:
                                    # Check for suspicious dates
                                    from datetime import datetime as dt
                                    year_int = int(file_year)
                                    current_year = dt.now().year
                                    if year_int < 1990 or year_int > current_year + 1 or (file_year == "1970" and file_month == "01" and file_day == "01"):
                                        flag_reason = 'suspicious'

                                # Also check for user-specified unreliable paths
                                if database_path:
                                    try:
                                        db_meta = DatabaseMetadata(database_path)
                                        user_paths = db_meta.get_user_specified_paths()
                                        for user_path in user_paths:
                                            if filename.startswith(user_path):
                                                flag_reason = 'user_specified'
                                                break
                                    except Exception as e:
                                        logger.warning(f"Could not check user-specified paths: {e}")

                                # Collect unreliable date record for batch insertion
                                if flag_reason and database_path:
                                    unreliable_dates_to_insert.append({
                                        'file_hash': file_hash,
                                        'source_path': filename,
                                        'archive_path': None,  # Will be updated when file is organized
                                        'original_date': file_create_date,
                                        'date_source': date_source,
                                        'flag_reason': flag_reason
                                    })
                                    unreliable_dates_count += 1  # Increment counter
                                    logger.info(f"Flagged file with unreliable date: {filename} (reason: {flag_reason})")

                            # Calculate content hash for content-based duplicate detection
                            content_hash = None
                            is_content_duplicate = False
                            content_duplicate_of = None
                            if content_hash_enabled:
                                content_hash = hash_image_content(filename)
                                if content_hash:
                                    # Check if this content hash already exists
                                    if db.has_content_hash(content_hash):
                                        is_content_duplicate = True
                                        matching_files = db.get_files_by_content_hash(content_hash)
                                        if matching_files:
                                            content_duplicate_of = matching_files[0]  # First match
                                            logger.info(f"Content duplicate detected: {filename} matches content of {content_duplicate_of['file_name']}")

                            original_file = {
                                "file_hash": file_hash,
                                "file_path": filename,
                                "file_create_datetime": file_create_date,
                                "file_create_year": file_year,
                                "file_create_month": file_month,
                                "file_create_day": file_day,
                                "content_hash": content_hash,
                                "is_content_duplicate": is_content_duplicate
                            }
                            original_files.append(original_file)

                            # Track content duplicates separately
                            if is_content_duplicate and content_duplicate_of:
                                content_duplicate_entry = {
                                    "file_hash": file_hash,
                                    "file_path": filename,
                                    "file_create_datetime": file_create_date,
                                    "content_hash": content_hash,
                                    "duplicate_of_hash": content_duplicate_of["file_hash"],
                                    "duplicate_of_path": content_duplicate_of["file_name"]
                                }
                                content_duplicate_files.append(content_duplicate_entry)

                            # Add to database with partial hash info and source path (v5 schema)
                            db.insert_unique_photo(
                                file_hash,
                                filename,  # This will be archive path after organize_files()
                                file_create_date,
                                file_year,
                                file_month,
                                file_day,
                                partial_hash=partial_hash,  # Will be None for small files
                                partial_hash_bytes=partial_hash_bytes if partial_hash else None,
                                file_size=file_size,
                                source_path=filename,  # Original source location (v5 schema)
                                content_hash=content_hash
                            )

                            files_processed += 1
                            files_since_last_commit += 1

                            # Periodic commit to preserve progress
                            if batch_size > 0 and files_since_last_commit >= batch_size:
                                db.commit()
                                logger.info(f"*** CHECKPOINT: Committed {files_since_last_commit} files to database. Progress: {files_processed}/{len(files)} ***")
                                files_since_last_commit = 0

                            # Update progress bar after successful processing
                            pbar.update(1)

                    except Exception as e:
                        logger.exception(f"Error processing file {filename}: {e}")
                        logger.warning(f"Continuing with next file despite error in {filename}")
                        pbar.update(1)
                        # Continue processing other files even if one fails

            # Final commit for any remaining uncommitted changes
            if files_since_last_commit > 0:
                db.commit()
                logger.info(f"*** FINAL COMMIT: Committed final {files_since_last_commit} files to database ***")

            logger.info(f"=== PROCESSING COMPLETE ===")
            logger.info(f"Total files processed: {files_processed}/{len(files)}")
            logger.info(f"Unique files added: {len(original_files)}")
            logger.info(f"Duplicates found: {len(duplicate_files)}")
            logger.info(f"Content duplicates found: {len(content_duplicate_files)}")
            logger.info(f"Files skipped (already in DB): {files_skipped}")
            if photo_filter and photo_filter.enabled:
                logger.info(f"Files filtered (non-photos): {len(filtered_files)}")
                photo_filter.print_statistics()

        # Batch insert unreliable date records (after PhotoDatabase context closed to avoid lock)
        if unreliable_dates_to_insert and database_path:
            try:
                logger.info(f"Batch inserting {len(unreliable_dates_to_insert)} unreliable date records...")
                db_meta = DatabaseMetadata(database_path)
                for record in unreliable_dates_to_insert:
                    try:
                        db_meta.insert_unreliable_date(
                            file_hash=record['file_hash'],
                            source_path=record['source_path'],
                            archive_path=record['archive_path'],
                            original_date=record['original_date'],
                            date_source=record['date_source'],
                            flag_reason=record['flag_reason']
                        )
                    except Exception as e:
                        logger.error(f"Failed to insert unreliable date for {record['source_path']}: {e}")
                logger.info(f"Successfully inserted {len(unreliable_dates_to_insert)} unreliable date records")
            except Exception as e:
                logger.error(f"Failed to batch insert unreliable dates: {e}")

        # Return results
        results = {}
        results["duplicate_files"] = duplicate_files
        results["original_files"] = original_files
        results["filtered_files"] = filtered_files
        results["content_duplicate_files"] = content_duplicate_files
        results["status"] = "cancelled" if was_cancelled else "completed"
        results["files_processed"] = files_processed
        results["files_skipped"] = files_skipped
        results["unreliable_dates_count"] = unreliable_dates_count

        if was_cancelled:
            logger.info(f"=== PROCESSING CANCELLED ===")
            logger.info(f"Partial progress saved: {files_processed} files processed, {len(original_files)} unique files added")

        # Add filter statistics if filtering was enabled
        if photo_filter and photo_filter.enabled:
            results["filter_statistics"] = photo_filter.get_statistics()
        else:
            results["filter_statistics"] = None

        return results

    except Exception as duplicate_e:
        logger.exception(f"The find_duplicates routine failed - {duplicate_e}")


def load_photo_hashes(database_path='PhotoDB.db'):
    '''
    This routine will return a list of all unique photo hashes that can be used to locate existing photos.

    Parameters:
        database_path - path to the SQLite database file (default: 'PhotoDB.db')

    Returns:
        List of file hashes from the UniquePhotos table
    '''
    try:
        logger.info(f"Loading photo hashes from {database_path}")

        # Use the PhotoDatabase context manager
        with PhotoDatabase(database_path) as db:
            results = db.get_all_hashes()
            logger.info(f"Loaded {len(results)} unique photo hashes from database")
            return results

    except Exception as e:
        logger.exception(f"The error {e} occurred in load_photo_hashes")
        return []


def VerifyFileType(filename):
    """ This routine takes a filename, and then verifies that the file extension matches the file type.
    This is specifically used to assign a file extension to files that do not have an extension!

    This routine will return the passed 'filename' if it is a valid photo/video, or the 'newfilename' if the file had to be processed.

    Note: Video files are passed through without verification since PIL cannot open them.
    Video format verification would require ffprobe or similar tools.
    """
    try:
        logger.info(f"About to process file '{filename}'!")

        # VIDEO FILES: Pass through without PIL verification
        # PIL cannot open video files, so we trust the extension
        if _is_video_file(filename):
            logger.info(f"Video file detected, passing through without PIL verification: {filename}")
            return filename

        valid_extensions = constants.VALID_IMAGE_EXTENSIONS
        EXTENSIONS_MAP = {
            'JPEG': ['.jpg', '.jpeg'],
            'PNG': ['.png', '.png'],
            'GIF': ['.gif'],
            'TIFF': ['.tiff', '.tif'],
            'BMP': ['.bmp'],
            'WEBP': ['.webp'],
            'ICO': ['.ico'],
            'PPM': ['.ppm'],
            'EPS': ['.eps'],
            'PDF': ['.pdf'],
            'MPO': ['.mpo', '.jpg'],  # Multi-Picture Object (used by some cameras, especially 3D)
        }

        # Get the base filename, and extension (if one exists)
        base_filename, existing_file_extension = os.path.splitext(filename)
        logger.info(f"The existing_file_extension = '{existing_file_extension}'")

        # Try to open the file, and if it fails, try to verify if the extension is invalid.
        try:
            with Image.open(filename) as img:
                analyzed_file_format = img.format
                logger.info(f"The file - {filename} was successfully opened and the filetype returned by pillow is {analyzed_file_format}")

                # Now determine if the returned filetype contains a file extension that matches the file extension of the file being processed.  The format returned by pillow (correct_file_format) is a coded value, and likely does not match the extension. ex:  JPEG instead of .jpg
                matching_file_extension = None
                # for ext, extensions in EXTENSIONS_MAP.items():
                for file_type in EXTENSIONS_MAP:
                    if file_type.upper() == analyzed_file_format.upper():
                        logger.info(f"We found the matching file_type = {file_type}")
                        matching_file_type = file_type
                        for ext in EXTENSIONS_MAP[file_type]:
                            logger.info(f"Checking for match between the calculated file type extensions and the existing extension - existing_file_extension.upper() = '{existing_file_extension.upper()}',  ext.upper() = '{ext.upper()}'")
                            if existing_file_extension.upper() == ext.upper():
                                # If there is a matching file extension found, convert it to the STANDARD extension.
                                matching_file_extension = ext
                                logger.info(f"We located a valid file type -{analyzed_file_format}, and the existing file extension matched one of the valid extensions for that format - '{matching_file_extension}'")
                                # We found a file extension in the calculated type that matches the existing extension.  So the file is valid to process.
                                return filename
                            else:
                                logger.info(f"existing_file_extension.upper() - '{existing_file_extension.upper()}' does NOT MATCH ext.upper() = '{ext.upper()}', so checking other possible extensions for the file type = {file_type}.")
                    else:
                        logger.info(f"file_type.upper() = {file_type.upper()} does not match the calculated file format = {analyzed_file_format.upper()}, so checking next file type. ")

                logger.info("##################################################################################")
                logger.info(f"The file format returned by pillow '{analyzed_file_format}'is a valid pillow format, but the existing file extension '{existing_file_extension}' does not match any of the valid file extensions for the calculated file type.  So we need to continue processing to determine if it is a valid file!")
                logger.info("##################################################################################")

                # Check if the analyzed file format is in our supported EXTENSIONS_MAP
                if analyzed_file_format.upper() not in [ft.upper() for ft in EXTENSIONS_MAP.keys()]:
                    logger.warning(f"File format '{analyzed_file_format}' is not in EXTENSIONS_MAP. Accepting file with existing extension '{existing_file_extension}'")
                    # File format not in our map (like MPO), but Pillow can open it, so accept it as-is
                    return filename

                # If the actual filetype does not match the extension of the file to be processed, write a valid file to the disk drive and return it to be processed instead of the incorrect file.
                if not existing_file_extension or not matching_file_extension or existing_file_extension.lower() != matching_file_extension.lower():
                    # The valid file extensions from the analyzed_filetype does not match the existing file extension.  So create a new file with the first correct extensions from the analyzed_filetype
                    extension_list = EXTENSIONS_MAP[matching_file_type]
                    logger.info(f"The extension list = {extension_list}")
                    new_file_extension =  extension_list[0]  # Return the first extension in the list of valid extensions
                    logger.info(f"The new file extension = {new_file_extension}")
                    new_filepath = f"{os.path.splitext(filename)[0]}{new_file_extension}"
                    try:
                        safe_rename_or_copy(filename, new_filepath)
                    except Exception as e:
                        logger.error(f"The file {filename} could not be renamed - {e}")
                        return  None

                    logger.info(f"File extension corrected: {filename} -> {new_filepath}")
                    return new_filepath

                else:
                    logger.info("File extension is None, or matches!  How is this possible?????")
                    return

        except (FileNotFoundError, UnidentifiedImageError):
            logger.info(f"Pillow cannot open the file: {filename}. It might not be a valid image.")
            pass
        except Exception as e:
            logger.exception(f"The error {e} occurred in VerifyFileType")


        #TODO: Not sure if this use case can occur for a invalid file extension - IE pillow will open a file with an mis-matched extension or no extension at all... VERIFY!!!!
        logger.info("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        logger.info(f"Pillow could not open the file.  This could because of a file lock, or incorrect extension...THIS LOGIC IS NOT COMPLETE!!!!!")
        logger.info("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        # Verify that the file has a valid extension type
        logger.info(f"The existing_file_extension = {existing_file_extension}")
        if not os.path.exists(filename) :
            logger.info(f"The file to be processed - {filename}, does not exist. ")
            return None
        else:
            logger.info("The file exists, and will be checked for other format types!")

        if existing_file_extension:
            logger.info(f"The file extension = {existing_file_extension}")
        else:
            logger.info(f"The file does not contain an extension.  So we need to try adding an extension and seeing if the file can be opened in Pillow")
            # Read the original file content
            try:
                with open(filename, 'rb') as f:
                    content = f.read()
            except Exception:
                return None

            # Create a temporary directory to test file variants
            valid_extension_found = None
            with tempfile.TemporaryDirectory() as temp_dir:
                for ext in valid_extensions:
                    temp_path = os.path.join(temp_dir, 'temp' + ext)
                    logger.info(f"Processing {temp_path}")
                    try:
                        with open(temp_path, 'wb') as f:
                            f.write(content)
                        with Image.open(temp_path) as img:
                            img.verify()  # This confirms the image is valid
                            valid_extension_found = ext
                            logger.info(f"We found a valid format!!! - {img.format} with extension {ext}")
                            break
                    except (UnidentifiedImageError, OSError):
                        continue

            # Now outside the temp directory context, handle the file appropriately
            if valid_extension_found:
                # Create a new filepath with the correct extension
                new_filepath = f"{filename}{valid_extension_found}"
                try:
                    safe_rename_or_copy(filename, new_filepath)
                    logger.info(f"File extension added: {filename} -> {new_filepath}")
                    return new_filepath
                except Exception as e:
                    logger.error(f"Failed to rename file with new extension: {e}")
                    return None
            else:
                logger.info(f"We did not find a valid file format for {filename}")
                return filename

    except Exception as e:
        logger.exception(f"The error {e} occurred in VerifyFileType")


def safe_rename_or_copy(old_path, new_path):
    """Try to rename, or fall back to copying if the file is locked."""
    try:
        os.rename(old_path, new_path)
        logger.info(f"File renamed to: {new_path}")
    except (PermissionError, OSError) as e:
        logger.error(f"Rename failed: {e}")
        try:
            if os.path.exists(new_path):
                logger.info(f"Cannot copy. Target file already exists: {new_path}")
                return
            try:
                shutil.copy2(old_path, new_path)
            except OSError as copy2_err:
                # Handle SMB/network shares that don't support chmod (errno 95)
                if copy2_err.errno == 95:
                    logger.warning(f"copy2 failed (metadata not supported), falling back to copy: {copy2_err}")
                    shutil.copyfile(old_path, new_path)
                else:
                    raise
            logger.info(f"File copied to: {new_path}")
        except Exception as copy_err:
            logger.error(f"Copy also failed: {copy_err}")

if __name__ == '__main__':
    try:
        '''
        This routine reads files in a directory and calculates the hash for each file.
        It then checks the database to determine if the file is a duplicate of a previous file.
        If the file is NOT a duplicate, it then adds the hash and filename/path  to the UniquePhotos database, and copies the file to the UniquePhotos Directory.
        If the file is a duplicate, it adds the hash and filename/path to the DuplicatePhotos database. 
        
        '''
        #logger.info("About to run sql_light")
        #sql_light()
        #logger.info("just finished!")

        directory_to_check = 'd:\\Test Files\\'
        #directory_to_check = "W:\\All Photographs\\2023 Photos\\To Be Filed"
        recursive = False
        file_endings =  [".jpg", ".png", ".heic"]

        try:
            logger.info("Initializing ensure_directory_exists")
            file_list = []
            if recursive:
                for root, dirs, files in os.walk(directory_to_check):
                    for file in files:
                        if not file_endings or file.lower().endswith(tuple(file_endings)):
                            file_list.append(os.path.join(root, file))
            else:
                with os.scandir(directory_to_check) as entries:
                    for entry in entries:
                        if entry.is_file() and (
                                not file_endings or entry.name.lower().endswith(tuple(file_endings))
                        ):
                            file_list.append(entry.path)
            logger.debug(f"Listed {len(file_list)} files from {directory_to_check}")

        except Exception as e:
            logger.exception(f"\n list_files process Failed : {sys.exc_info()} - {e}")

        try:
            database_path = constants.DEFAULT_DATABASE_NAME  # Can be loaded from settings if needed
            batch_size = constants.DEFAULT_BATCH_SIZE  # Commit every N files
            logger.info(f"About to run load_photo_hashes.")
            existing_hashes = load_photo_hashes(database_path)
        except Exception as e:
            logger.exception(f"The load_photo_hashes failed - {e}")

        results = find_duplicates(file_list, existing_hashes, database_path, batch_size)
        if results:
            logger.info("Files completed processing:")
            logger.info("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^")
            if results["original_files"]:
                original_files = results["original_files"]
                logger.info(f"The original files found = {original_files}")
            else:
                logger.info("No new files located")

            if results["duplicate_files"]:
                duplicate_files = results["duplicate_files"]
                logger.info(f"The duplicate files found = {duplicate_files}")
            else:
                logger.info("No duplicate files located")

        else:
            print("No duplicate files found.")
    except Exception as duplicate_e:
        logger.exception(f"The __main__ routine failed - {duplicate_e}")