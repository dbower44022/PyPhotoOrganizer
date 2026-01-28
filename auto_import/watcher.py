"""
Directory Watcher for Auto-Import Service.

Monitors directories for new files using polling.
"""

import fnmatch
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set

from auto_import.config import ServiceConfig, WatchConfig

logger = logging.getLogger(__name__)


@dataclass
class NewFile:
    """Represents a new file detected for import."""
    path: str
    size: int
    mtime: float
    watch_config: WatchConfig
    first_seen: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'path': self.path,
            'size': self.size,
            'mtime': self.mtime,
            'watch_directory': self.watch_config.path,
            'album_id': self.watch_config.album_id,
            'first_seen': self.first_seen.isoformat(),
        }


class DirectoryWatcher:
    """
    Watches directories for new files using polling.

    Maintains state in SQLite database to track processed files
    and avoid re-processing on service restart.
    """

    def __init__(self, config: ServiceConfig):
        """
        Initialize DirectoryWatcher.

        Args:
            config: Service configuration
        """
        self.config = config
        self._state_db_path = self._get_state_db_path()
        self._ensure_state_table()

    def _get_state_db_path(self) -> str:
        """Get path to state database."""
        if self.config.state_file:
            return self.config.state_file

        # Use same directory as main database
        db_dir = os.path.dirname(self.config.database_path)
        return os.path.join(db_dir, '.autoimport_state.db')

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self._state_db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_state_table(self):
        """Ensure state tracking table exists."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ProcessedFiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL UNIQUE,
                    file_size INTEGER,
                    file_mtime REAL,
                    first_seen TEXT,
                    processed_at TEXT,
                    status TEXT,
                    result_hash TEXT,
                    error_message TEXT,
                    watch_directory TEXT
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_processed_path
                ON ProcessedFiles(file_path)
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS ImportRuns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT UNIQUE,
                    start_time TEXT,
                    end_time TEXT,
                    files_scanned INTEGER,
                    files_imported INTEGER,
                    files_duplicate INTEGER,
                    files_filtered INTEGER,
                    files_failed INTEGER,
                    report_sent INTEGER DEFAULT 0
                )
            """)

            conn.commit()

    def scan_for_new_files(self) -> List[NewFile]:
        """
        Scan all watched directories for new files.

        Returns:
            List of new files ready for processing
        """
        new_files = []
        now = time.time()

        for watch_config in self.config.get_enabled_watch_directories():
            if not watch_config.is_available():
                logger.warning(f"Watch directory not available: {watch_config.path}")
                continue

            try:
                files = self._scan_directory(watch_config, now)
                new_files.extend(files)
            except Exception as e:
                logger.error(f"Error scanning {watch_config.path}: {e}")

        logger.debug(f"Total new files found: {len(new_files)}")
        return new_files

    def _scan_directory(self, watch_config: WatchConfig, now: float) -> List[NewFile]:
        """
        Scan a single directory for new files.

        Args:
            watch_config: Watch configuration
            now: Current timestamp

        Returns:
            List of new files
        """
        new_files = []
        min_age = watch_config.min_file_age_seconds

        logger.debug(f"Scanning: {watch_config.path}")

        # Get already processed files for this directory
        processed = self._get_processed_files(watch_config.path)

        # Walk directory
        if watch_config.recursive:
            walker = os.walk(watch_config.path)
        else:
            # Non-recursive: only top level
            try:
                entries = os.listdir(watch_config.path)
                walker = [(watch_config.path, [], entries)]
            except OSError as e:
                logger.error(f"Cannot list directory {watch_config.path}: {e}")
                return []

        for root, dirs, files in walker:
            for filename in files:
                file_path = os.path.join(root, filename)

                try:
                    # Check if file matches patterns
                    if not self._matches_patterns(filename, watch_config.file_patterns):
                        continue

                    # Get file info
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    file_mtime = stat.st_mtime

                    # Check if already processed
                    if file_path in processed:
                        continue

                    # Check file age (wait for copy to complete)
                    file_age = now - file_mtime
                    if file_age < min_age:
                        logger.debug(f"File too new ({file_age:.0f}s < {min_age}s): {filename}")
                        continue

                    # Check if file is still being written (size changed)
                    time.sleep(0.1)
                    stat2 = os.stat(file_path)
                    if stat2.st_size != file_size:
                        logger.debug(f"File still being written: {filename}")
                        continue

                    # Add to new files list
                    new_files.append(NewFile(
                        path=file_path,
                        size=file_size,
                        mtime=file_mtime,
                        watch_config=watch_config,
                        first_seen=datetime.now()
                    ))

                except OSError as e:
                    logger.debug(f"Cannot access file {file_path}: {e}")
                    continue

        logger.debug(f"Found {len(new_files)} new files in {watch_config.path}")
        return new_files

    def _matches_patterns(self, filename: str, patterns: List[str]) -> bool:
        """Check if filename matches any of the patterns."""
        filename_lower = filename.lower()
        for pattern in patterns:
            if fnmatch.fnmatch(filename_lower, pattern.lower()):
                return True
        return False

    def _get_processed_files(self, watch_directory: str) -> Set[str]:
        """Get set of already processed file paths for a directory."""
        processed = set()

        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                    SELECT file_path FROM ProcessedFiles
                    WHERE watch_directory = ?
                    AND status IN ('imported', 'duplicate', 'filtered')
                """, (watch_directory,))

                for row in cursor:
                    processed.add(row[0])

        except Exception as e:
            logger.error(f"Error getting processed files: {e}")

        return processed

    def mark_as_processed(self, file_path: str, status: str = 'imported',
                         result_hash: str = None, error: str = None):
        """
        Mark a file as processed.

        Args:
            file_path: Path to the file
            status: Processing status ('imported', 'duplicate', 'filtered', 'failed')
            result_hash: Hash of imported file (if applicable)
            error: Error message (if failed)
        """
        try:
            with self._get_connection() as conn:
                # Get watch directory for this file
                watch_dir = None
                for wc in self.config.watch_directories:
                    if file_path.startswith(wc.path):
                        watch_dir = wc.path
                        break

                # Get file info
                try:
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    file_mtime = stat.st_mtime
                except OSError:
                    file_size = 0
                    file_mtime = 0

                conn.execute("""
                    INSERT OR REPLACE INTO ProcessedFiles
                    (file_path, file_size, file_mtime, first_seen, processed_at,
                     status, result_hash, error_message, watch_directory)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    file_path,
                    file_size,
                    file_mtime,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    status,
                    result_hash,
                    error,
                    watch_dir
                ))
                conn.commit()

        except Exception as e:
            logger.error(f"Error marking file as processed: {e}")

    def get_watch_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get status of all watched directories.

        Returns:
            Dict mapping directory path to status info
        """
        status = {}

        for wc in self.config.watch_directories:
            available = wc.is_available()

            # Count files in state database
            processed_count = 0
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute("""
                        SELECT COUNT(*) FROM ProcessedFiles
                        WHERE watch_directory = ?
                    """, (wc.path,))
                    processed_count = cursor.fetchone()[0]
            except Exception:
                pass

            status[wc.path] = {
                'name': wc.name,
                'enabled': wc.enabled,
                'available': available,
                'recursive': wc.recursive,
                'patterns': wc.file_patterns,
                'min_age_seconds': wc.min_file_age_seconds,
                'album_id': wc.album_id,
                'processed_count': processed_count,
            }

        return status

    def clear_processed_files(self, watch_directory: str = None,
                             older_than_days: int = None):
        """
        Clear processed files from state database.

        Args:
            watch_directory: Specific directory, or None for all
            older_than_days: Only clear entries older than this many days
        """
        try:
            with self._get_connection() as conn:
                if watch_directory and older_than_days:
                    from datetime import timedelta
                    cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
                    conn.execute("""
                        DELETE FROM ProcessedFiles
                        WHERE watch_directory = ? AND processed_at < ?
                    """, (watch_directory, cutoff))

                elif watch_directory:
                    conn.execute("""
                        DELETE FROM ProcessedFiles
                        WHERE watch_directory = ?
                    """, (watch_directory,))

                elif older_than_days:
                    from datetime import timedelta
                    cutoff = (datetime.now() - timedelta(days=older_than_days)).isoformat()
                    conn.execute("""
                        DELETE FROM ProcessedFiles
                        WHERE processed_at < ?
                    """, (cutoff,))

                else:
                    conn.execute("DELETE FROM ProcessedFiles")

                deleted = conn.total_changes
                conn.commit()
                logger.info(f"Cleared {deleted} processed file entries")

        except Exception as e:
            logger.error(f"Error clearing processed files: {e}")
