"""
Archive Verification Worker

Background worker for verifying archive integrity through:
- Hash verification: Recalculate and verify file hashes
- Orphan detection: Find files in archive not tracked in database
- Missing file detection: Find database records without files on disk
"""

from PySide6.QtCore import QThread, Signal
import os
import sqlite3
import hashlib
import logging

logger = logging.getLogger(__name__)


class ArchiveVerificationWorker(QThread):
    """
    Worker thread for archive verification operations.

    Supports three modes:
    - verify_hashes: Recalculate hashes and compare to database
    - find_orphaned: Find files in archive not in database
    - find_missing: Find database records where files are missing

    Supports graceful cancellation.
    """

    # Signals
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)  # status message
    completed = Signal(dict)  # results dictionary
    error_occurred = Signal(str)  # error message

    def __init__(self, database_path: str, archive_location: str, verification_mode: str):
        """
        Initialize the verification worker.

        Args:
            database_path: Path to the SQLite database
            archive_location: Path to the main archive
            verification_mode: 'verify_hashes', 'find_orphaned', or 'find_missing'
        """
        super().__init__()
        self.database_path = database_path
        self.archive_location = archive_location
        self.verification_mode = verification_mode
        self._should_stop = False

    def stop(self):
        """Request the worker to stop gracefully."""
        self._should_stop = True
        logger.info("Verification stop requested")

    def run(self):
        """Main processing loop."""
        try:
            if self.verification_mode == 'verify_hashes':
                self._verify_hashes()
            elif self.verification_mode == 'find_orphaned':
                self._find_orphaned()
            elif self.verification_mode == 'find_missing':
                self._find_missing()
            else:
                self.error_occurred.emit(f"Unknown verification mode: {self.verification_mode}")

        except Exception as e:
            logger.error(f"Verification failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.database_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _verify_hashes(self):
        """
        Verify file hashes by recalculating and comparing to database.
        """
        self.status_update.emit("Loading files from database...")

        verified = 0
        mismatches = []
        missing = []

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get all files from database
                cursor.execute("""
                    SELECT file_hash, file_name
                    FROM UniquePhotos
                    WHERE file_name IS NOT NULL
                """)
                files = cursor.fetchall()

            total = len(files)
            self.status_update.emit(f"Verifying {total:,} files...")

            for i, (stored_hash, file_path) in enumerate(files):
                if self._should_stop:
                    break

                filename = os.path.basename(file_path) if file_path else stored_hash[:12]
                self.progress_update.emit(i + 1, total, filename)

                if not file_path or not os.path.exists(file_path):
                    missing.append(file_path or f"(hash: {stored_hash[:16]})")
                    continue

                try:
                    # Calculate actual hash
                    actual_hash = self._hash_file(file_path)

                    if actual_hash == stored_hash:
                        verified += 1
                    else:
                        mismatches.append(file_path)
                        logger.warning(f"Hash mismatch: {file_path}")
                        logger.warning(f"  Stored:  {stored_hash}")
                        logger.warning(f"  Actual:  {actual_hash}")

                except Exception as e:
                    logger.error(f"Failed to verify {file_path}: {e}")
                    missing.append(file_path)

            status = 'cancelled' if self._should_stop else 'completed'

            self.completed.emit({
                'mode': 'verify_hashes',
                'status': status,
                'verified': verified,
                'mismatches': mismatches,
                'missing': missing
            })

        except Exception as e:
            logger.error(f"Hash verification failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def _find_orphaned(self):
        """
        Find files in archive that are not tracked in the database.
        """
        self.status_update.emit("Loading known files from database...")

        orphaned = []

        try:
            # Get all known file paths from database
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT file_name
                    FROM UniquePhotos
                    WHERE file_name IS NOT NULL
                """)
                known_paths = {row[0] for row in cursor.fetchall() if row[0]}

            self.status_update.emit(f"Database has {len(known_paths):,} files")

            if not self.archive_location or not os.path.exists(self.archive_location):
                self.error_occurred.emit(f"Archive location not found: {self.archive_location}")
                return

            # Count files first
            self.status_update.emit("Counting files in archive...")
            total_files = sum(len(files) for _, _, files in os.walk(self.archive_location))
            self.status_update.emit(f"Scanning {total_files:,} files in archive...")

            checked = 0
            for root, dirs, files in os.walk(self.archive_location):
                if self._should_stop:
                    break

                for filename in files:
                    if self._should_stop:
                        break

                    file_path = os.path.join(root, filename)
                    checked += 1

                    if checked % 500 == 0:
                        self.progress_update.emit(checked, total_files, filename)

                    if file_path not in known_paths:
                        orphaned.append(file_path)

            status = 'cancelled' if self._should_stop else 'completed'

            self.completed.emit({
                'mode': 'find_orphaned',
                'status': status,
                'files_checked': checked,
                'orphaned': orphaned
            })

        except Exception as e:
            logger.error(f"Orphan detection failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def _find_missing(self):
        """
        Find database records where the file is missing from disk.
        """
        self.status_update.emit("Loading files from database...")

        missing = []

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get all files from database
                cursor.execute("""
                    SELECT file_hash, file_name
                    FROM UniquePhotos
                    WHERE file_name IS NOT NULL
                """)
                files = cursor.fetchall()

            total = len(files)
            self.status_update.emit(f"Checking {total:,} database records...")

            for i, (file_hash, file_path) in enumerate(files):
                if self._should_stop:
                    break

                filename = os.path.basename(file_path) if file_path else file_hash[:12]

                if i % 500 == 0:
                    self.progress_update.emit(i + 1, total, filename)

                if not file_path or not os.path.exists(file_path):
                    missing.append(file_path or f"(hash: {file_hash[:16]})")

            status = 'cancelled' if self._should_stop else 'completed'

            self.completed.emit({
                'mode': 'find_missing',
                'status': status,
                'records_checked': len(files),
                'missing': missing
            })

        except Exception as e:
            logger.error(f"Missing file detection failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def _hash_file(self, file_path: str) -> str:
        """
        Calculate SHA-256 hash of a file.

        Args:
            file_path: Path to the file

        Returns:
            Hexadecimal hash string
        """
        hasher = hashlib.sha256()
        buffer_size = 65536  # 64KB chunks

        with open(file_path, 'rb') as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                hasher.update(data)

        return hasher.hexdigest()
