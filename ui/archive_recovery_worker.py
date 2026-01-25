"""
Archive Recovery Worker

Scans the archive directory to find files that exist in the archive but not in
the database. This is used after restoring from a backup to recover information
about files that were imported after the backup was created.
"""

from PySide6.QtCore import QThread, Signal
import os
import sqlite3
import hashlib
import logging
from datetime import datetime
from typing import Optional, Set, Dict, Any, Callable

logger = logging.getLogger(__name__)

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.heic', '.heif', '.webp', '.raw', '.cr2', '.nef', '.arw',
    '.mov', '.mp4', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', '.mpg', '.mpeg'
}


class ArchiveRecoveryWorker(QThread):
    """
    Worker thread that scans the archive to find and recover orphaned files.

    Orphaned files are files that exist in the archive directory but are not
    tracked in the database. This typically happens when a database is restored
    from a backup that was created before some files were imported.

    Signals:
        progress_update: (current, total, filename) - Progress during scan
        status_update: (message) - Status message updates
        file_recovered: (file_info) - Emitted for each recovered file
        completed: (results_dict) - Final results when complete
        error_occurred: (error_message) - Error notification
    """

    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)
    file_recovered = Signal(dict)  # Per-file recovery notification
    completed = Signal(dict)  # Final results
    error_occurred = Signal(str)

    def __init__(self, database_path: str, archive_location: str,
                 video_archive_location: Optional[str] = None,
                 parent=None):
        """
        Initialize the archive recovery worker.

        Args:
            database_path: Path to the database file
            archive_location: Path to the main photo archive
            video_archive_location: Optional separate video archive path
            parent: Parent QObject
        """
        super().__init__(parent)
        self.database_path = database_path
        self.archive_location = archive_location
        self.video_archive_location = video_archive_location
        self._should_stop = False
        self._recovery_session_id = None

    def stop(self):
        """Request the worker to stop."""
        self._should_stop = True

    def _should_stop_check(self) -> bool:
        """Check if stop has been requested."""
        return self._should_stop

    def run(self):
        """Main worker execution."""
        try:
            self.status_update.emit("Initializing archive recovery scan...")

            # Get all known file hashes from database
            known_hashes = self._get_known_hashes()
            self.status_update.emit(f"Database contains {len(known_hashes):,} known files")

            # Scan archive for all media files
            self.status_update.emit("Scanning archive for media files...")
            archive_files = self._scan_archive()

            if self._should_stop:
                self.completed.emit({'cancelled': True})
                return

            total_files = len(archive_files)
            self.status_update.emit(f"Found {total_files:,} files in archive")

            # Find orphaned files (not in database)
            orphaned_files = []
            self.status_update.emit("Checking for orphaned files...")

            for i, file_path in enumerate(archive_files):
                if self._should_stop:
                    self.completed.emit({'cancelled': True})
                    return

                filename = os.path.basename(file_path)
                self.progress_update.emit(i + 1, total_files, filename)

                # Hash the file
                file_hash = self._hash_file(file_path)
                if file_hash and file_hash not in known_hashes:
                    orphaned_files.append({
                        'path': file_path,
                        'hash': file_hash,
                        'size': os.path.getsize(file_path)
                    })

            if not orphaned_files:
                self.status_update.emit("No orphaned files found - database is up to date")
                self.completed.emit({
                    'cancelled': False,
                    'total_scanned': total_files,
                    'orphaned_found': 0,
                    'recovered': 0,
                    'failed': 0
                })
                return

            self.status_update.emit(f"Found {len(orphaned_files):,} orphaned files - recovering...")

            # Start recovery session
            self._start_recovery_session()

            # Add orphaned files to database
            recovered = 0
            failed = 0

            for i, file_info in enumerate(orphaned_files):
                if self._should_stop:
                    self._end_recovery_session(recovered, failed, cancelled=True)
                    self.completed.emit({
                        'cancelled': True,
                        'total_scanned': total_files,
                        'orphaned_found': len(orphaned_files),
                        'recovered': recovered,
                        'failed': failed
                    })
                    return

                filename = os.path.basename(file_info['path'])
                self.progress_update.emit(i + 1, len(orphaned_files), f"Recovering: {filename}")

                success, result = self._recover_file(file_info)
                if success:
                    recovered += 1
                    self.file_recovered.emit(result)
                else:
                    failed += 1
                    logger.warning(f"Failed to recover {file_info['path']}: {result}")

            # End recovery session
            self._end_recovery_session(recovered, failed)

            self.status_update.emit(f"Recovery complete: {recovered:,} files recovered")
            self.completed.emit({
                'cancelled': False,
                'total_scanned': total_files,
                'orphaned_found': len(orphaned_files),
                'recovered': recovered,
                'failed': failed
            })

        except Exception as e:
            logger.error(f"Archive recovery failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def _get_known_hashes(self) -> Set[str]:
        """Get all known file hashes from the database."""
        hashes = set()
        try:
            conn = sqlite3.connect(self.database_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("SELECT file_hash FROM UniquePhotos WHERE file_hash IS NOT NULL")
            for row in cursor.fetchall():
                hashes.add(row[0])

            conn.close()
        except Exception as e:
            logger.error(f"Failed to get known hashes: {e}")

        return hashes

    def _scan_archive(self) -> list:
        """Scan archive directories for media files."""
        files = []

        # Scan main archive
        if self.archive_location and os.path.isdir(self.archive_location):
            files.extend(self._scan_directory(self.archive_location))

        # Scan video archive if separate
        if self.video_archive_location and os.path.isdir(self.video_archive_location):
            if self.video_archive_location != self.archive_location:
                files.extend(self._scan_directory(self.video_archive_location))

        return files

    def _scan_directory(self, directory: str) -> list:
        """Recursively scan a directory for media files."""
        files = []

        try:
            for root, dirs, filenames in os.walk(directory):
                if self._should_stop:
                    break

                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in SUPPORTED_EXTENSIONS:
                        files.append(os.path.join(root, filename))
        except Exception as e:
            logger.error(f"Error scanning directory {directory}: {e}")

        return files

    def _hash_file(self, file_path: str) -> Optional[str]:
        """Calculate SHA-256 hash of a file."""
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(65536), b''):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.debug(f"Failed to hash {file_path}: {e}")
            return None

    def _start_recovery_session(self):
        """Start a recovery audit session."""
        try:
            conn = sqlite3.connect(self.database_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO ImportSession
                (start_timestamp, operation_mode, status)
                VALUES (?, 'archive_recovery', 'in_progress')
            """, (datetime.now().isoformat(),))

            self._recovery_session_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Started archive recovery session: {self._recovery_session_id}")
        except Exception as e:
            logger.error(f"Failed to start recovery session: {e}")

    def _end_recovery_session(self, recovered: int, failed: int, cancelled: bool = False):
        """End the recovery audit session."""
        if not self._recovery_session_id:
            return

        try:
            conn = sqlite3.connect(self.database_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            status = 'cancelled' if cancelled else 'completed'

            cursor.execute("""
                UPDATE ImportSession
                SET end_timestamp = ?,
                    status = ?,
                    total_files = ?,
                    successful_imports = ?,
                    failed_imports = ?
                WHERE id = ?
            """, (
                datetime.now().isoformat(),
                status,
                recovered + failed,
                recovered,
                failed,
                self._recovery_session_id
            ))

            conn.commit()
            conn.close()

            logger.info(f"Ended archive recovery session: {recovered} recovered, {failed} failed")
        except Exception as e:
            logger.error(f"Failed to end recovery session: {e}")

    def _recover_file(self, file_info: dict) -> tuple:
        """
        Add an orphaned file back to the database.

        Args:
            file_info: Dict with 'path', 'hash', 'size' keys

        Returns:
            Tuple of (success: bool, result: dict or error message)
        """
        try:
            file_path = file_info['path']
            file_hash = file_info['hash']
            file_size = file_info['size']

            # Extract creation date from file
            creation_date = self._get_creation_date(file_path)

            # Determine storage type and relative path
            storage_type, relative_path = self._get_storage_info(file_path)

            # Calculate content hash for images
            content_hash = self._get_content_hash(file_path)

            conn = sqlite3.connect(self.database_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            # Insert into UniquePhotos
            # Note: source_path is set to indicate this was recovered
            cursor.execute("""
                INSERT INTO UniquePhotos (
                    file_hash, file_size, file_name, source_path,
                    create_datetime, create_year, create_month, create_day,
                    content_hash, relative_path, storage_type,
                    revision_reason, revision_timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                file_hash,
                file_size,
                file_path,
                f"RECOVERED:{file_path}",  # Mark as recovered with original path
                creation_date.isoformat() if creation_date else None,
                str(creation_date.year) if creation_date else None,
                str(creation_date.month).zfill(2) if creation_date else None,
                str(creation_date.day).zfill(2) if creation_date else None,
                content_hash,
                relative_path,
                storage_type,
                'recovered_from_archive',  # Mark recovery in revision_reason
                datetime.now().isoformat()
            ))

            # Log to audit trail
            if self._recovery_session_id:
                cursor.execute("""
                    INSERT INTO FileProcessingLog (
                        session_id, file_path, file_hash, operation, status,
                        timestamp, details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    self._recovery_session_id,
                    file_path,
                    file_hash,
                    'archive_recovery',
                    'success',
                    datetime.now().isoformat(),
                    f"Recovered orphaned file from archive scan. Size: {file_size} bytes"
                ))

            conn.commit()
            conn.close()

            result = {
                'path': file_path,
                'hash': file_hash,
                'size': file_size,
                'creation_date': creation_date.isoformat() if creation_date else None
            }

            return (True, result)

        except sqlite3.IntegrityError as e:
            # File hash already exists (shouldn't happen but handle it)
            return (False, f"Hash already exists: {e}")
        except Exception as e:
            return (False, str(e))

    def _get_creation_date(self, file_path: str) -> Optional[datetime]:
        """Extract creation date from file metadata or filesystem."""
        try:
            # Try to import and use the main date extraction function
            from DuplicateFileDetection import get_creation_date
            date_result = get_creation_date(file_path)
            if date_result and date_result.year > 1990:
                return date_result
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Could not extract EXIF date from {file_path}: {e}")

        # Fall back to file modification time
        try:
            mtime = os.path.getmtime(file_path)
            return datetime.fromtimestamp(mtime)
        except Exception:
            return None

    def _get_storage_info(self, file_path: str) -> tuple:
        """
        Determine storage type and relative path for a file.

        Returns:
            Tuple of (storage_type, relative_path)
        """
        abs_path = os.path.abspath(file_path)

        # Check video archive first (may be subdirectory of main archive)
        if self.video_archive_location:
            video_base = os.path.abspath(self.video_archive_location)
            if abs_path.startswith(video_base + os.sep):
                relative = os.path.relpath(abs_path, video_base)
                return ('video_archive', relative)

        # Check main archive
        if self.archive_location:
            archive_base = os.path.abspath(self.archive_location)
            if abs_path.startswith(archive_base + os.sep):
                relative = os.path.relpath(abs_path, archive_base)
                return ('archive', relative)

        # Unknown storage type
        return ('archive', os.path.basename(file_path))

    def _get_content_hash(self, file_path: str) -> Optional[str]:
        """Calculate content hash for image files."""
        ext = os.path.splitext(file_path)[1].lower()

        # Only calculate for images, not videos
        video_extensions = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.3gp', '.wmv', '.mpg', '.mpeg'}
        if ext in video_extensions:
            return None

        try:
            from DuplicateFileDetection import hash_image_content
            return hash_image_content(file_path)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Could not calculate content hash for {file_path}: {e}")

        return None
