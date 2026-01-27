"""
Progress Persistence Module

Provides enhanced progress tracking and crash recovery capabilities.
This module extends the basic PendingOperations system with:

1. Scan Progress Tracking
   - Track which directories have been scanned
   - Resume scanning from last position on crash

2. Import Session State
   - Track current position in file list
   - Store batch progress
   - Enable graceful resume

3. Hash Cache
   - Cache partial hashes for large files
   - Avoid recomputing on resume

4. Checkpoint System
   - Periodic checkpoints during long operations
   - Transaction-like commit points

Usage:
    from progress_persistence import ProgressTracker

    tracker = ProgressTracker(database_path)

    # Start a new session
    session_id = tracker.start_session(source_dirs, dest_dir)

    # Track scan progress
    tracker.mark_directory_scanned(session_id, "/path/to/dir")

    # Track file processing
    tracker.mark_file_processed(session_id, file_path, file_hash)

    # Create checkpoints
    tracker.create_checkpoint(session_id, current_index, total_files)

    # On restart, check for incomplete sessions
    incomplete = tracker.get_incomplete_sessions()
    if incomplete:
        # Resume from checkpoint
        checkpoint = tracker.get_latest_checkpoint(session_id)
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import uuid

import constants
import utils

logger = utils.setup_logger(__name__, "progress_persistence.log")


class ProgressTracker:
    """
    Enhanced progress tracking for crash recovery.

    Maintains state across:
    - Directory scanning progress
    - File processing progress
    - Hash computation cache
    - Batch checkpoints
    """

    def __init__(self, database_path: str):
        """
        Initialize the progress tracker.

        Args:
            database_path: Path to the SQLite database
        """
        self.database_path = database_path
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with appropriate settings."""
        conn = sqlite3.connect(
            self.database_path,
            timeout=constants.DATABASE_TIMEOUT_SECONDS
        )
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={constants.DATABASE_BUSY_TIMEOUT_MS}")
        return conn

    def _ensure_tables(self) -> None:
        """Create required tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Import sessions table (extends existing ImportSession)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ProgressSessions (
                        session_id TEXT PRIMARY KEY,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        status TEXT DEFAULT 'running',
                        operation_type TEXT DEFAULT 'import',
                        source_directories TEXT,
                        destination_directory TEXT,
                        total_files_found INTEGER DEFAULT 0,
                        total_files_processed INTEGER DEFAULT 0,
                        current_file_index INTEGER DEFAULT 0,
                        last_checkpoint_time TEXT,
                        can_resume INTEGER DEFAULT 1,
                        resume_data TEXT
                    )
                """)

                # Scanned directories table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ScannedDirectories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        directory_path TEXT NOT NULL,
                        scan_time TEXT DEFAULT CURRENT_TIMESTAMP,
                        files_found INTEGER DEFAULT 0,
                        is_complete INTEGER DEFAULT 1,
                        FOREIGN KEY (session_id) REFERENCES ProgressSessions(session_id),
                        UNIQUE (session_id, directory_path)
                    )
                """)

                # Checkpoints table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ProcessingCheckpoints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        checkpoint_time TEXT DEFAULT CURRENT_TIMESTAMP,
                        current_index INTEGER NOT NULL,
                        total_files INTEGER NOT NULL,
                        files_processed INTEGER DEFAULT 0,
                        files_skipped INTEGER DEFAULT 0,
                        files_failed INTEGER DEFAULT 0,
                        bytes_processed INTEGER DEFAULT 0,
                        current_file_path TEXT,
                        checkpoint_data TEXT,
                        FOREIGN KEY (session_id) REFERENCES ProgressSessions(session_id)
                    )
                """)

                # Hash cache table (for partial hashes of large files)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS HashCache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        file_path TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        file_mtime REAL NOT NULL,
                        partial_hash TEXT,
                        full_hash TEXT,
                        content_hash TEXT,
                        computed_time TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (file_path, file_size, file_mtime)
                    )
                """)

                # Processed files log (for resume)
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS ProcessedFiles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        file_path TEXT NOT NULL,
                        file_hash TEXT,
                        status TEXT DEFAULT 'processed',
                        processed_time TEXT DEFAULT CURRENT_TIMESTAMP,
                        result_path TEXT,
                        error_message TEXT,
                        FOREIGN KEY (session_id) REFERENCES ProgressSessions(session_id),
                        UNIQUE (session_id, file_path)
                    )
                """)

                # Create indexes
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_progress_session_status
                    ON ProgressSessions(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_scanned_session
                    ON ScannedDirectories(session_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_checkpoint_session
                    ON ProcessingCheckpoints(session_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_hash_cache_path
                    ON HashCache(file_path)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_processed_session
                    ON ProcessedFiles(session_id)
                """)

                conn.commit()
                logger.debug("Progress tracking tables ensured")

        except Exception as e:
            logger.error(f"Failed to create progress tables: {e}")

    # ========================================================================
    # Session Management
    # ========================================================================

    def start_session(
        self,
        source_directories: List[str],
        destination_directory: str,
        operation_type: str = 'import'
    ) -> str:
        """
        Start a new progress tracking session.

        Args:
            source_directories: List of source directory paths
            destination_directory: Destination archive path
            operation_type: Type of operation ('import', 'reorganize', etc.)

        Returns:
            Session ID string
        """
        session_id = f"progress_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ProgressSessions
                    (session_id, start_time, operation_type, source_directories,
                     destination_directory, status)
                    VALUES (?, ?, ?, ?, ?, 'running')
                """, (
                    session_id,
                    datetime.now().isoformat(),
                    operation_type,
                    json.dumps(source_directories),
                    destination_directory
                ))
                conn.commit()

            logger.info(f"Started progress session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to start session: {e}")
            return session_id  # Return ID anyway for tracking

    def end_session(
        self,
        session_id: str,
        status: str = 'completed',
        can_resume: bool = False
    ) -> bool:
        """
        End a progress tracking session.

        Args:
            session_id: Session ID to end
            status: Final status ('completed', 'cancelled', 'failed')
            can_resume: Whether session can be resumed later

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE ProgressSessions
                    SET end_time = ?, status = ?, can_resume = ?
                    WHERE session_id = ?
                """, (datetime.now().isoformat(), status, 1 if can_resume else 0, session_id))
                conn.commit()

            logger.info(f"Ended session {session_id} with status: {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to end session: {e}")
            return False

    def get_incomplete_sessions(self) -> List[Dict[str, Any]]:
        """
        Get all sessions that can be resumed.

        Returns:
            List of session dictionaries
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT session_id, start_time, operation_type, source_directories,
                           destination_directory, total_files_found, total_files_processed,
                           current_file_index, can_resume, resume_data
                    FROM ProgressSessions
                    WHERE status IN ('running', 'paused') AND can_resume = 1
                    ORDER BY start_time DESC
                """)

                sessions = []
                for row in cursor.fetchall():
                    sessions.append({
                        'session_id': row[0],
                        'start_time': row[1],
                        'operation_type': row[2],
                        'source_directories': json.loads(row[3]) if row[3] else [],
                        'destination_directory': row[4],
                        'total_files_found': row[5],
                        'total_files_processed': row[6],
                        'current_file_index': row[7],
                        'can_resume': bool(row[8]),
                        'resume_data': json.loads(row[9]) if row[9] else {}
                    })

                return sessions

        except Exception as e:
            logger.error(f"Failed to get incomplete sessions: {e}")
            return []

    # ========================================================================
    # Directory Scanning Progress
    # ========================================================================

    def mark_directory_scanned(
        self,
        session_id: str,
        directory_path: str,
        files_found: int = 0,
        is_complete: bool = True
    ) -> bool:
        """
        Mark a directory as scanned.

        Args:
            session_id: Current session ID
            directory_path: Path that was scanned
            files_found: Number of files found
            is_complete: Whether scan is complete

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO ScannedDirectories
                    (session_id, directory_path, files_found, is_complete, scan_time)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, directory_path, files_found,
                      1 if is_complete else 0, datetime.now().isoformat()))
                conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to mark directory scanned: {e}")
            return False

    def get_scanned_directories(self, session_id: str) -> List[str]:
        """
        Get list of directories already scanned in a session.

        Args:
            session_id: Session ID to check

        Returns:
            List of scanned directory paths
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT directory_path FROM ScannedDirectories
                    WHERE session_id = ? AND is_complete = 1
                """, (session_id,))
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get scanned directories: {e}")
            return []

    def get_unscanned_directories(
        self,
        session_id: str,
        all_directories: List[str]
    ) -> List[str]:
        """
        Get directories that haven't been scanned yet.

        Args:
            session_id: Session ID
            all_directories: Full list of directories to scan

        Returns:
            List of directories not yet scanned
        """
        scanned = set(self.get_scanned_directories(session_id))
        return [d for d in all_directories if d not in scanned]

    # ========================================================================
    # File Processing Progress
    # ========================================================================

    def mark_file_processed(
        self,
        session_id: str,
        file_path: str,
        file_hash: Optional[str] = None,
        status: str = 'processed',
        result_path: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Mark a file as processed.

        Args:
            session_id: Current session ID
            file_path: Path of processed file
            file_hash: Hash of the file
            status: Processing status ('processed', 'skipped', 'failed', 'duplicate')
            result_path: Destination path if copied
            error_message: Error message if failed

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO ProcessedFiles
                    (session_id, file_path, file_hash, status, result_path,
                     error_message, processed_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (session_id, file_path, file_hash, status, result_path,
                      error_message, datetime.now().isoformat()))
                conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to mark file processed: {e}")
            return False

    def get_processed_files(self, session_id: str) -> set:
        """
        Get set of file paths already processed in a session.

        Args:
            session_id: Session ID

        Returns:
            Set of processed file paths
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT file_path FROM ProcessedFiles
                    WHERE session_id = ?
                """, (session_id,))
                return {row[0] for row in cursor.fetchall()}

        except Exception as e:
            logger.error(f"Failed to get processed files: {e}")
            return set()

    def get_unprocessed_files(
        self,
        session_id: str,
        all_files: List[str]
    ) -> List[str]:
        """
        Get files that haven't been processed yet.

        Args:
            session_id: Session ID
            all_files: Full list of files to process

        Returns:
            List of files not yet processed
        """
        processed = self.get_processed_files(session_id)
        return [f for f in all_files if f not in processed]

    # ========================================================================
    # Checkpoints
    # ========================================================================

    def create_checkpoint(
        self,
        session_id: str,
        current_index: int,
        total_files: int,
        files_processed: int = 0,
        files_skipped: int = 0,
        files_failed: int = 0,
        bytes_processed: int = 0,
        current_file_path: Optional[str] = None,
        extra_data: Optional[Dict] = None
    ) -> bool:
        """
        Create a progress checkpoint.

        Args:
            session_id: Session ID
            current_index: Current position in file list
            total_files: Total files to process
            files_processed: Count of processed files
            files_skipped: Count of skipped files
            files_failed: Count of failed files
            bytes_processed: Total bytes processed
            current_file_path: Path of current file
            extra_data: Additional checkpoint data

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Insert checkpoint
                cursor.execute("""
                    INSERT INTO ProcessingCheckpoints
                    (session_id, current_index, total_files, files_processed,
                     files_skipped, files_failed, bytes_processed,
                     current_file_path, checkpoint_data, checkpoint_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id, current_index, total_files, files_processed,
                    files_skipped, files_failed, bytes_processed,
                    current_file_path,
                    json.dumps(extra_data) if extra_data else None,
                    datetime.now().isoformat()
                ))

                # Update session with checkpoint info
                cursor.execute("""
                    UPDATE ProgressSessions
                    SET current_file_index = ?, total_files_found = ?,
                        total_files_processed = ?, last_checkpoint_time = ?
                    WHERE session_id = ?
                """, (current_index, total_files, files_processed,
                      datetime.now().isoformat(), session_id))

                conn.commit()
                logger.debug(f"Checkpoint created: {current_index}/{total_files}")
                return True

        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return False

    def get_latest_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent checkpoint for a session.

        Args:
            session_id: Session ID

        Returns:
            Checkpoint dictionary or None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT current_index, total_files, files_processed,
                           files_skipped, files_failed, bytes_processed,
                           current_file_path, checkpoint_data, checkpoint_time
                    FROM ProcessingCheckpoints
                    WHERE session_id = ?
                    ORDER BY checkpoint_time DESC
                    LIMIT 1
                """, (session_id,))

                row = cursor.fetchone()
                if row:
                    return {
                        'current_index': row[0],
                        'total_files': row[1],
                        'files_processed': row[2],
                        'files_skipped': row[3],
                        'files_failed': row[4],
                        'bytes_processed': row[5],
                        'current_file_path': row[6],
                        'checkpoint_data': json.loads(row[7]) if row[7] else {},
                        'checkpoint_time': row[8]
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get checkpoint: {e}")
            return None

    # ========================================================================
    # Hash Cache
    # ========================================================================

    def cache_hash(
        self,
        file_path: str,
        file_size: int,
        file_mtime: float,
        partial_hash: Optional[str] = None,
        full_hash: Optional[str] = None,
        content_hash: Optional[str] = None
    ) -> bool:
        """
        Cache computed hashes for a file.

        Args:
            file_path: Path to the file
            file_size: File size in bytes
            file_mtime: File modification time
            partial_hash: Partial hash (first N bytes)
            full_hash: Full file hash
            content_hash: Image content hash

        Returns:
            True if successful
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO HashCache
                    (file_path, file_size, file_mtime, partial_hash,
                     full_hash, content_hash, computed_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (file_path, file_size, file_mtime, partial_hash,
                      full_hash, content_hash, datetime.now().isoformat()))
                conn.commit()
            return True

        except Exception as e:
            logger.error(f"Failed to cache hash: {e}")
            return False

    def get_cached_hash(
        self,
        file_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached hash for a file if still valid.

        Checks that file size and mtime match.

        Args:
            file_path: Path to the file

        Returns:
            Cached hash info or None if not valid
        """
        try:
            # Get current file stats
            if not os.path.exists(file_path):
                return None

            stat = os.stat(file_path)
            current_size = stat.st_size
            current_mtime = stat.st_mtime

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT partial_hash, full_hash, content_hash
                    FROM HashCache
                    WHERE file_path = ? AND file_size = ? AND file_mtime = ?
                """, (file_path, current_size, current_mtime))

                row = cursor.fetchone()
                if row:
                    return {
                        'partial_hash': row[0],
                        'full_hash': row[1],
                        'content_hash': row[2]
                    }
                return None

        except Exception as e:
            logger.error(f"Failed to get cached hash: {e}")
            return None

    # ========================================================================
    # Cleanup
    # ========================================================================

    def cleanup_old_data(self, days_old: int = 7) -> int:
        """
        Clean up old progress tracking data.

        Args:
            days_old: Delete data older than this many days

        Returns:
            Number of records deleted
        """
        try:
            cutoff = (datetime.now() - timedelta(days=days_old)).isoformat()
            total_deleted = 0

            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Delete old completed/cancelled sessions and related data
                cursor.execute("""
                    DELETE FROM ProcessedFiles
                    WHERE session_id IN (
                        SELECT session_id FROM ProgressSessions
                        WHERE end_time < ? AND status IN ('completed', 'cancelled')
                    )
                """, (cutoff,))
                total_deleted += cursor.rowcount

                cursor.execute("""
                    DELETE FROM ProcessingCheckpoints
                    WHERE session_id IN (
                        SELECT session_id FROM ProgressSessions
                        WHERE end_time < ? AND status IN ('completed', 'cancelled')
                    )
                """, (cutoff,))
                total_deleted += cursor.rowcount

                cursor.execute("""
                    DELETE FROM ScannedDirectories
                    WHERE session_id IN (
                        SELECT session_id FROM ProgressSessions
                        WHERE end_time < ? AND status IN ('completed', 'cancelled')
                    )
                """, (cutoff,))
                total_deleted += cursor.rowcount

                cursor.execute("""
                    DELETE FROM ProgressSessions
                    WHERE end_time < ? AND status IN ('completed', 'cancelled')
                """, (cutoff,))
                total_deleted += cursor.rowcount

                # Clean old hash cache
                cursor.execute("""
                    DELETE FROM HashCache
                    WHERE computed_time < ?
                """, (cutoff,))
                total_deleted += cursor.rowcount

                conn.commit()

            if total_deleted > 0:
                logger.info(f"Cleaned up {total_deleted} old progress records")

            return total_deleted

        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")
            return 0

    def get_session_statistics(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics for a session.

        Args:
            session_id: Session ID

        Returns:
            Dictionary with session statistics
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get session info
                cursor.execute("""
                    SELECT start_time, end_time, status, total_files_found,
                           total_files_processed, operation_type
                    FROM ProgressSessions
                    WHERE session_id = ?
                """, (session_id,))
                session = cursor.fetchone()

                if not session:
                    return {}

                # Get file status counts
                cursor.execute("""
                    SELECT status, COUNT(*) FROM ProcessedFiles
                    WHERE session_id = ?
                    GROUP BY status
                """, (session_id,))
                status_counts = dict(cursor.fetchall())

                # Get directory count
                cursor.execute("""
                    SELECT COUNT(*) FROM ScannedDirectories
                    WHERE session_id = ?
                """, (session_id,))
                dir_count = cursor.fetchone()[0]

                return {
                    'session_id': session_id,
                    'start_time': session[0],
                    'end_time': session[1],
                    'status': session[2],
                    'total_files_found': session[3],
                    'total_files_processed': session[4],
                    'operation_type': session[5],
                    'directories_scanned': dir_count,
                    'files_by_status': status_counts
                }

        except Exception as e:
            logger.error(f"Failed to get session statistics: {e}")
            return {}
