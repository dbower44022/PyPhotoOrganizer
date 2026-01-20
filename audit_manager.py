"""
Import Audit Manager

Manages session tracking, file operation logging, duplicate mapping,
and audit report generation for PyPhotoOrganizer.

This module provides complete traceability for all file operations during import,
including session-level tracking, per-file operation logs, duplicate relationship
tracking, and configurable retention policies.
"""

import sqlite3
import uuid
import json
import logging
import csv
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from pathlib import Path

# Import profiling utilities
from utils import profile_block

logger = logging.getLogger(__name__)

# SQLite connection timeout (seconds) - wait for locks
SQLITE_TIMEOUT = 30

# Retry settings for transient lock errors during concurrent access
# Total retry time with exponential backoff: 0.5 + 1.0 + 1.5 + 2.0 + 2.5 = 7.5 seconds
MAX_RETRIES = 5
RETRY_DELAY = 0.5  # seconds base delay (multiplied by attempt number)


def generate_session_id() -> str:
    """
    Generate a unique session ID.

    Format: YYYYMMDD_HHMMSS_XXXXXX
    Where XXXXXX is 6 random hex characters.

    Returns:
        Unique session identifier string
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"{timestamp}_{random_part}"


class AuditManager:
    """
    Manages import audit tracking and reporting.

    Provides functionality for:
    - Session lifecycle management (start, end, query)
    - Per-file operation logging with verification
    - Duplicate relationship tracking
    - Configurable retention policies
    - Report generation and export (JSON, CSV)
    """

    # SQL Schema for audit tables
    IMPORT_SESSION_SCHEMA = """
        CREATE TABLE IF NOT EXISTS ImportSession (
            session_id TEXT PRIMARY KEY,
            start_timestamp TEXT NOT NULL,
            end_timestamp TEXT,
            status TEXT NOT NULL DEFAULT 'running',
            source_directories TEXT,
            destination_directory TEXT,
            organization_template TEXT,
            operation_mode TEXT,
            total_files_scanned INTEGER DEFAULT 0,
            total_files_processed INTEGER DEFAULT 0,
            total_unique_files INTEGER DEFAULT 0,
            total_duplicates INTEGER DEFAULT 0,
            total_filtered INTEGER DEFAULT 0,
            total_errors INTEGER DEFAULT 0,
            total_unreliable_dates INTEGER DEFAULT 0,
            total_bytes_processed INTEGER DEFAULT 0,
            scan_duration_seconds REAL DEFAULT 0,
            process_duration_seconds REAL DEFAULT 0,
            organize_duration_seconds REAL DEFAULT 0,
            error_summary TEXT,
            notes TEXT
        )
    """

    FILE_PROCESSING_LOG_SCHEMA = """
        CREATE TABLE IF NOT EXISTS FileProcessingLog (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            source_path TEXT NOT NULL,
            destination_path TEXT,
            file_hash TEXT,
            partial_hash TEXT,
            operation TEXT NOT NULL,
            status TEXT NOT NULL,
            file_size INTEGER,
            creation_date TEXT,
            date_source TEXT,
            date_reliable INTEGER,
            source_hash_verified INTEGER DEFAULT 0,
            destination_hash_verified INTEGER DEFAULT 0,
            hash_verification_status TEXT,
            process_timestamp TEXT NOT NULL,
            duration_ms INTEGER,
            error_code TEXT,
            error_message TEXT,
            error_traceback TEXT,
            duplicate_of_hash TEXT,
            filter_reason TEXT,
            filter_details TEXT,
            album_name TEXT,
            album_path TEXT,
            sub_album_name TEXT,
            FOREIGN KEY (session_id) REFERENCES ImportSession(session_id) ON DELETE CASCADE
        )
    """

    DUPLICATE_MAPPING_SCHEMA = """
        CREATE TABLE IF NOT EXISTS DuplicateMapping (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_hash TEXT NOT NULL,
            original_path TEXT NOT NULL,
            duplicate_source_path TEXT NOT NULL,
            first_seen_session TEXT NOT NULL,
            first_seen_timestamp TEXT NOT NULL,
            times_seen INTEGER DEFAULT 1,
            last_seen_session TEXT,
            last_seen_timestamp TEXT,
            UNIQUE(original_hash, duplicate_source_path),
            FOREIGN KEY (first_seen_session) REFERENCES ImportSession(session_id)
        )
    """

    RETENTION_SETTINGS_SCHEMA = """
        CREATE TABLE IF NOT EXISTS AuditRetentionSettings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            retention_mode TEXT DEFAULT 'none',
            retain_session_count INTEGER DEFAULT 50,
            retain_days INTEGER DEFAULT 365,
            auto_cleanup_enabled INTEGER DEFAULT 0,
            last_cleanup_timestamp TEXT,
            preserve_error_logs INTEGER DEFAULT 1,
            preserve_days_for_errors INTEGER DEFAULT 730
        )
    """

    def __init__(self, database_path: str):
        """
        Initialize the audit manager.

        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path
        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection with proper settings.

        Returns:
            sqlite3.Connection with timeout and WAL mode enabled
        """
        conn = sqlite3.connect(self.database_path, timeout=SQLITE_TIMEOUT)
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")  # 30 second busy timeout
        return conn

    def _ensure_tables(self) -> None:
        """Create audit tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Create all audit tables
                cursor.execute(self.IMPORT_SESSION_SCHEMA)
                cursor.execute(self.FILE_PROCESSING_LOG_SCHEMA)
                cursor.execute(self.DUPLICATE_MAPPING_SCHEMA)
                cursor.execute(self.RETENTION_SETTINGS_SCHEMA)

                # Create indexes for performance
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_start
                    ON ImportSession(start_timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_session_status
                    ON ImportSession(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_filelog_session
                    ON FileProcessingLog(session_id)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_filelog_hash
                    ON FileProcessingLog(file_hash)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_filelog_status
                    ON FileProcessingLog(status)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_filelog_operation
                    ON FileProcessingLog(operation)
                """)
                # Index on process_timestamp for ORDER BY optimization
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_filelog_timestamp
                    ON FileProcessingLog(process_timestamp)
                """)
                # Composite index for session queries with ORDER BY timestamp
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_filelog_session_timestamp
                    ON FileProcessingLog(session_id, process_timestamp)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_dupmap_original
                    ON DuplicateMapping(original_hash)
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_dupmap_duplicate_path
                    ON DuplicateMapping(duplicate_source_path)
                """)

                # Initialize retention settings if not exist
                cursor.execute("""
                    INSERT OR IGNORE INTO AuditRetentionSettings (id)
                    VALUES (1)
                """)

                # Auto-upgrade: Add album columns to FileProcessingLog if they don't exist
                cursor.execute("PRAGMA table_info(FileProcessingLog)")
                existing_columns = {row[1] for row in cursor.fetchall()}

                album_columns = [
                    ("album_name", "TEXT"),
                    ("album_path", "TEXT"),
                    ("sub_album_name", "TEXT"),
                ]

                for col_name, col_type in album_columns:
                    if col_name not in existing_columns:
                        cursor.execute(f"ALTER TABLE FileProcessingLog ADD COLUMN {col_name} {col_type}")
                        logger.info(f"Added column {col_name} to FileProcessingLog table")

                conn.commit()
                logger.debug("Audit tables ensured successfully")

        except Exception as e:
            logger.error(f"Failed to create audit tables: {e}", exc_info=True)
            raise

    # ==================== Session Management ====================

    def start_session(
        self,
        source_directories: List[str],
        destination_directory: str,
        organization_template: str = "",
        operation_mode: str = "copy"
    ) -> str:
        """
        Start a new import session.

        Args:
            source_directories: List of source folder paths
            destination_directory: Archive destination path
            organization_template: Folder organization template
            operation_mode: 'copy' or 'move'

        Returns:
            session_id: Unique identifier for this session
        """
        session_id = generate_session_id()
        start_timestamp = datetime.now().isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ImportSession
                    (session_id, start_timestamp, status, source_directories,
                     destination_directory, organization_template, operation_mode)
                    VALUES (?, ?, 'running', ?, ?, ?, ?)
                """, (
                    session_id,
                    start_timestamp,
                    json.dumps(source_directories),
                    destination_directory,
                    organization_template,
                    operation_mode
                ))
                conn.commit()

            logger.info(f"Started import session: {session_id}")
            return session_id

        except Exception as e:
            logger.error(f"Failed to start session: {e}", exc_info=True)
            raise

    def end_session(
        self,
        session_id: str,
        status: str,
        stats: Dict[str, Any],
        error_summary: Optional[Dict[str, int]] = None
    ) -> bool:
        """
        Mark a session as complete.

        Args:
            session_id: Session to close
            status: Final status ('completed', 'failed', 'cancelled')
            stats: Dictionary of final statistics (only provided fields are updated,
                   existing values are preserved for fields not in stats)
            error_summary: Error counts by type

        Returns:
            True if successful
        """
        end_timestamp = datetime.now().isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # First fetch existing session values to preserve fields not in stats
                cursor.execute("""
                    SELECT total_files_scanned, total_files_processed, total_unique_files,
                           total_duplicates, total_filtered, total_errors,
                           total_unreliable_dates, total_bytes_processed
                    FROM ImportSession WHERE session_id = ?
                """, (session_id,))
                existing = cursor.fetchone()

                if existing:
                    # Use existing values as defaults, override with stats if provided
                    total_files_scanned = stats.get('total_files_scanned', existing[0] or 0)
                    total_files_processed = stats.get('total_files_processed', existing[1] or 0)
                    total_unique_files = stats.get('total_unique_files',
                                                   stats.get('total_new_original_files', existing[2] or 0))
                    total_duplicates = stats.get('total_duplicates', existing[3] or 0)
                    total_filtered = stats.get('total_filtered', existing[4] or 0)
                    total_errors = stats.get('total_errors', existing[5] or 0)
                    total_unreliable_dates = stats.get('total_unreliable_dates', existing[6] or 0)
                    total_bytes_processed = stats.get('total_bytes_processed', existing[7] or 0)
                else:
                    # No existing session, use stats with 0 defaults
                    total_files_scanned = stats.get('total_files_scanned', 0)
                    total_files_processed = stats.get('total_files_processed', 0)
                    total_unique_files = stats.get('total_unique_files',
                                                   stats.get('total_new_original_files', 0))
                    total_duplicates = stats.get('total_duplicates', 0)
                    total_filtered = stats.get('total_filtered', 0)
                    total_errors = stats.get('total_errors', 0)
                    total_unreliable_dates = stats.get('total_unreliable_dates', 0)
                    total_bytes_processed = stats.get('total_bytes_processed', 0)

                cursor.execute("""
                    UPDATE ImportSession
                    SET end_timestamp = ?,
                        status = ?,
                        total_files_scanned = ?,
                        total_files_processed = ?,
                        total_unique_files = ?,
                        total_duplicates = ?,
                        total_filtered = ?,
                        total_errors = ?,
                        total_unreliable_dates = ?,
                        total_bytes_processed = ?,
                        error_summary = ?
                    WHERE session_id = ?
                """, (
                    end_timestamp,
                    status,
                    total_files_scanned,
                    total_files_processed,
                    total_unique_files,
                    total_duplicates,
                    total_filtered,
                    total_errors,
                    total_unreliable_dates,
                    total_bytes_processed,
                    json.dumps(error_summary) if error_summary else None,
                    session_id
                ))
                conn.commit()

            logger.info(f"Ended session {session_id} with status: {status}")
            return True

        except Exception as e:
            logger.error(f"Failed to end session {session_id}: {e}", exc_info=True)
            return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session details by ID."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM ImportSession WHERE session_id = ?
                """, (session_id,))
                row = cursor.fetchone()
                if row:
                    result = dict(row)
                    # Parse JSON fields
                    if result.get('source_directories'):
                        result['source_directories'] = json.loads(result['source_directories'])
                    if result.get('error_summary'):
                        result['error_summary'] = json.loads(result['error_summary'])
                    return result
                return None

        except Exception as e:
            logger.error(f"Failed to get session {session_id}: {e}", exc_info=True)
            return None

    def get_recent_sessions(
        self,
        limit: int = 50,
        status_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent import sessions.

        Args:
            limit: Maximum number of sessions to return
            status_filter: Optional filter by status

        Returns:
            List of session dictionaries, newest first
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if status_filter:
                    cursor.execute("""
                        SELECT * FROM ImportSession
                        WHERE status = ?
                        ORDER BY start_timestamp DESC
                        LIMIT ?
                    """, (status_filter, limit))
                else:
                    cursor.execute("""
                        SELECT * FROM ImportSession
                        ORDER BY start_timestamp DESC
                        LIMIT ?
                    """, (limit,))

                sessions = []
                for row in cursor.fetchall():
                    session = dict(row)
                    if session.get('source_directories'):
                        session['source_directories'] = json.loads(session['source_directories'])
                    if session.get('error_summary'):
                        session['error_summary'] = json.loads(session['error_summary'])
                    sessions.append(session)

                return sessions

        except Exception as e:
            logger.error(f"Failed to get recent sessions: {e}", exc_info=True)
            return []

    def update_session_stats(self, session_id: str, **stats) -> bool:
        """Update session statistics incrementally (for progress tracking)."""
        try:
            # Build SET clause dynamically from provided stats
            valid_fields = [
                'total_files_scanned', 'total_files_processed', 'total_unique_files',
                'total_duplicates', 'total_filtered', 'total_errors',
                'total_unreliable_dates', 'total_bytes_processed',
                'scan_duration_seconds', 'process_duration_seconds', 'organize_duration_seconds'
            ]

            updates = []
            values = []
            for key, value in stats.items():
                if key in valid_fields:
                    updates.append(f"{key} = ?")
                    values.append(value)

            if not updates:
                return True

            values.append(session_id)

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE ImportSession
                    SET {', '.join(updates)}
                    WHERE session_id = ?
                """, values)
                conn.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to update session stats: {e}", exc_info=True)
            return False

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its related data."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                # FileProcessingLog will be deleted via CASCADE
                cursor.execute("DELETE FROM ImportSession WHERE session_id = ?", (session_id,))
                conn.commit()
                logger.info(f"Deleted session: {session_id}")
                return True
        except Exception as e:
            logger.error(f"Failed to delete session {session_id}: {e}", exc_info=True)
            return False

    # ==================== File Operation Logging ====================

    def log_file_operation(
        self,
        session_id: str,
        source_path: str,
        operation: str,
        status: str,
        file_hash: Optional[str] = None,
        partial_hash: Optional[str] = None,
        destination_path: Optional[str] = None,
        file_size: Optional[int] = None,
        creation_date: Optional[str] = None,
        date_source: Optional[str] = None,
        date_reliable: bool = True,
        duration_ms: Optional[int] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
        error_traceback: Optional[str] = None,
        duplicate_of_hash: Optional[str] = None,
        filter_reason: Optional[str] = None,
        filter_details: Optional[Dict] = None,
        album_name: Optional[str] = None,
        album_path: Optional[str] = None,
        sub_album_name: Optional[str] = None
    ) -> int:
        """
        Log a file operation.

        Args:
            session_id: Current session ID
            source_path: Source file path
            operation: 'copy', 'move', 'duplicate detected', 'skip_filtered', 'error'
            status: 'success', 'failed', 'skipped', 'duplicate'
            file_hash: Full SHA-256 hash
            partial_hash: Partial hash (first 16KB)
            destination_path: Destination path (if applicable)
            file_size: File size in bytes
            creation_date: Extracted creation date
            date_source: 'exif', 'os_metadata', 'fallback'
            date_reliable: Whether date is reliable
            duration_ms: Processing time in milliseconds
            error_code: Error type name
            error_message: Error message
            error_traceback: Full traceback for debugging
            duplicate_of_hash: Hash of original file (if duplicate)
            filter_reason: Why file was filtered
            filter_details: Detailed filter results
            album_name: Name of album file was added to (None if no album)
            album_path: Path to file in album storage (None if no album)
            sub_album_name: Sub-album name if applicable (None if parent album or no album)

        Returns:
            Log entry ID
        """
        process_timestamp = datetime.now().isoformat()

        # Retry logic for transient database locks
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO FileProcessingLog
                        (session_id, source_path, destination_path, file_hash, partial_hash,
                         operation, status, file_size, creation_date, date_source, date_reliable,
                         process_timestamp, duration_ms, error_code, error_message, error_traceback,
                         duplicate_of_hash, filter_reason, filter_details,
                         album_name, album_path, sub_album_name)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session_id, source_path, destination_path, file_hash, partial_hash,
                        operation, status, file_size, creation_date, date_source,
                        1 if date_reliable else 0, process_timestamp, duration_ms,
                        error_code, error_message, error_traceback, duplicate_of_hash,
                        filter_reason, json.dumps(filter_details) if filter_details else None,
                        album_name, album_path, sub_album_name
                    ))
                    conn.commit()
                    return cursor.lastrowid

            except sqlite3.OperationalError as e:
                last_error = e
                if "locked" in str(e).lower() and attempt < MAX_RETRIES - 1:
                    logger.warning(f"Database locked, retrying ({attempt + 1}/{MAX_RETRIES})...")
                    time.sleep(RETRY_DELAY * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"Failed to log file operation after {attempt + 1} attempts: {e}", exc_info=True)
                    return -1
            except Exception as e:
                logger.error(f"Failed to log file operation: {e}", exc_info=True)
                return -1

        logger.error(f"Failed to log file operation after all retries: {last_error}", exc_info=True)
        return -1

    def update_verification_status(
        self,
        log_id: int,
        source_verified: bool,
        destination_verified: bool,
        verification_status: str
    ) -> bool:
        """Update hash verification status for a file operation."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE FileProcessingLog
                    SET source_hash_verified = ?,
                        destination_hash_verified = ?,
                        hash_verification_status = ?
                    WHERE id = ?
                """, (
                    1 if source_verified else 0,
                    1 if destination_verified else 0,
                    verification_status,
                    log_id
                ))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to update verification status: {e}", exc_info=True)
            return False

    def get_aggregate_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate statistics across all sessions.

        Returns:
            Dictionary with aggregate counts and totals
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get totals from ImportSession table
                cursor.execute("""
                    SELECT
                        COUNT(*) as total_sessions,
                        SUM(total_files_scanned) as total_scanned,
                        SUM(total_files_processed) as total_processed,
                        SUM(total_unique_files) as total_unique,
                        SUM(total_duplicates) as total_duplicates,
                        SUM(total_filtered) as total_filtered,
                        SUM(total_errors) as total_errors,
                        MIN(start_timestamp) as first_session,
                        MAX(end_timestamp) as last_session
                    FROM ImportSession
                """)

                row = cursor.fetchone()
                if row:
                    return {
                        'total_sessions': row[0] or 0,
                        'total_files_scanned': row[1] or 0,
                        'total_files_processed': row[2] or 0,
                        'total_unique_files': row[3] or 0,
                        'total_duplicates': row[4] or 0,
                        'total_filtered': row[5] or 0,
                        'total_errors': row[6] or 0,
                        'first_session_date': row[7],
                        'last_session_date': row[8]
                    }
                else:
                    return {
                        'total_sessions': 0,
                        'total_files_scanned': 0,
                        'total_files_processed': 0,
                        'total_unique_files': 0,
                        'total_duplicates': 0,
                        'total_filtered': 0,
                        'total_errors': 0,
                        'first_session_date': None,
                        'last_session_date': None
                    }

        except Exception as e:
            logger.error(f"Failed to get aggregate statistics: {e}", exc_info=True)
            return {}

    def get_all_file_logs(
        self,
        operation_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 10000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get file operation logs from all sessions.

        Args:
            operation_filter: Filter by operation type
            status_filter: Filter by status
            limit: Maximum number of records to return
            offset: Number of records to skip

        Returns:
            List of file log dictionaries
        """
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                conditions = []
                params = []

                if operation_filter:
                    conditions.append("operation = ?")
                    params.append(operation_filter)

                if status_filter:
                    conditions.append("status = ?")
                    params.append(status_filter)

                where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
                params.extend([limit, offset])

                with profile_block(f"SQL - SELECT FileProcessingLog (limit={limit})", logger):
                    cursor.execute(f"""
                        SELECT * FROM FileProcessingLog
                        {where_clause}
                        ORDER BY process_timestamp DESC
                        LIMIT ? OFFSET ?
                    """, params)

                    results = [dict(row) for row in cursor.fetchall()]

                logger.info(f"📊 Query returned {len(results)} records")
                return results

        except Exception as e:
            logger.error(f"Failed to get all file logs: {e}", exc_info=True)
            return []

    def get_file_logs_for_session(
        self,
        session_id: str,
        operation_filter: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get file operation logs for a session."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                conditions = ["session_id = ?"]
                params = [session_id]

                if operation_filter:
                    conditions.append("operation = ?")
                    params.append(operation_filter)

                if status_filter:
                    conditions.append("status = ?")
                    params.append(status_filter)

                params.extend([limit, offset])

                with profile_block(f"SQL - SELECT FileProcessingLog for session (limit={limit})", logger):
                    cursor.execute(f"""
                        SELECT * FROM FileProcessingLog
                        WHERE {' AND '.join(conditions)}
                        ORDER BY process_timestamp
                        LIMIT ? OFFSET ?
                    """, params)

                    results = [dict(row) for row in cursor.fetchall()]

                logger.info(f"📊 Query returned {len(results)} records for session {session_id}")
                return results

        except Exception as e:
            logger.error(f"Failed to get file logs for session {session_id}: {e}", exc_info=True)
            return []

    def get_file_history(self, file_hash: str) -> List[Dict[str, Any]]:
        """Get all operations involving a specific file hash."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM FileProcessingLog
                    WHERE file_hash = ? OR duplicate_of_hash = ?
                    ORDER BY process_timestamp DESC
                """, (file_hash, file_hash))
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get file history for {file_hash}: {e}", exc_info=True)
            return []

    def get_errors_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all error entries for a session."""
        return self.get_file_logs_for_session(session_id, status_filter='failed')

    def get_session_file_counts(self, session_id: str) -> Dict[str, int]:
        """Get file operation counts grouped by operation type."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT operation, COUNT(*) as count
                    FROM FileProcessingLog
                    WHERE session_id = ?
                    GROUP BY operation
                """, (session_id,))
                return {row[0]: row[1] for row in cursor.fetchall()}

        except Exception as e:
            logger.error(f"Failed to get file counts: {e}", exc_info=True)
            return {}

    # ==================== Duplicate Mapping ====================

    def record_duplicate(
        self,
        session_id: str,
        original_hash: str,
        original_path: str,
        duplicate_source_path: str
    ) -> bool:
        """
        Record a duplicate file relationship.

        If the same duplicate has been seen before, increments times_seen.

        Args:
            session_id: Current session ID
            original_hash: Hash of the original file (in archive)
            original_path: Archive path of the original
            duplicate_source_path: Path where duplicate was found

        Returns:
            True if successful
        """
        timestamp = datetime.now().isoformat()

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Try to update existing record
                cursor.execute("""
                    UPDATE DuplicateMapping
                    SET times_seen = times_seen + 1,
                        last_seen_session = ?,
                        last_seen_timestamp = ?
                    WHERE original_hash = ? AND duplicate_source_path = ?
                """, (session_id, timestamp, original_hash, duplicate_source_path))

                if cursor.rowcount == 0:
                    # Insert new record
                    cursor.execute("""
                        INSERT INTO DuplicateMapping
                        (original_hash, original_path, duplicate_source_path,
                         first_seen_session, first_seen_timestamp, times_seen)
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (original_hash, original_path, duplicate_source_path,
                          session_id, timestamp))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to record duplicate: {e}", exc_info=True)
            return False

    def get_duplicates_of(self, original_hash: str) -> List[Dict[str, Any]]:
        """Get all known duplicates of an original file."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM DuplicateMapping
                    WHERE original_hash = ?
                    ORDER BY times_seen DESC
                """, (original_hash,))
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get duplicates of {original_hash}: {e}", exc_info=True)
            return []

    def get_duplicate_statistics(self) -> Dict[str, Any]:
        """
        Get aggregate duplicate statistics.

        Returns:
            Dictionary with:
            - total_duplicates: Total duplicate mappings
            - unique_originals: Number of originals with duplicates
            - top_duplicated: List of most-duplicated files
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Total duplicate mappings
                cursor.execute("SELECT COUNT(*) FROM DuplicateMapping")
                total_duplicates = cursor.fetchone()[0]

                # Unique originals with duplicates
                cursor.execute("SELECT COUNT(DISTINCT original_hash) FROM DuplicateMapping")
                unique_originals = cursor.fetchone()[0]

                # Top duplicated files
                cursor.execute("""
                    SELECT original_hash, original_path, SUM(times_seen) as total_times
                    FROM DuplicateMapping
                    GROUP BY original_hash
                    ORDER BY total_times DESC
                    LIMIT 10
                """)
                top_duplicated = [
                    {'hash': row[0], 'path': row[1], 'times_seen': row[2]}
                    for row in cursor.fetchall()
                ]

                return {
                    'total_duplicates': total_duplicates,
                    'unique_originals': unique_originals,
                    'top_duplicated': top_duplicated
                }

        except Exception as e:
            logger.error(f"Failed to get duplicate statistics: {e}", exc_info=True)
            return {}

    def get_duplicates_for_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get duplicates found during a specific session."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM DuplicateMapping
                    WHERE first_seen_session = ? OR last_seen_session = ?
                    ORDER BY first_seen_timestamp
                """, (session_id, session_id))
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get duplicates for session: {e}", exc_info=True)
            return []

    # ==================== Retention Management ====================

    def get_retention_settings(self) -> Dict[str, Any]:
        """Get current retention settings."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM AuditRetentionSettings WHERE id = 1")
                row = cursor.fetchone()
                return dict(row) if row else {}

        except Exception as e:
            logger.error(f"Failed to get retention settings: {e}", exc_info=True)
            return {}

    def set_retention_settings(
        self,
        mode: str,
        session_count: Optional[int] = None,
        days: Optional[int] = None,
        auto_cleanup: bool = False,
        preserve_errors: bool = True,
        error_retention_days: int = 730
    ) -> bool:
        """Update retention settings."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE AuditRetentionSettings
                    SET retention_mode = ?,
                        retain_session_count = ?,
                        retain_days = ?,
                        auto_cleanup_enabled = ?,
                        preserve_error_logs = ?,
                        preserve_days_for_errors = ?
                    WHERE id = 1
                """, (
                    mode,
                    session_count or 50,
                    days or 365,
                    1 if auto_cleanup else 0,
                    1 if preserve_errors else 0,
                    error_retention_days
                ))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Failed to set retention settings: {e}", exc_info=True)
            return False

    def apply_retention_policy(self) -> Tuple[int, int]:
        """
        Apply retention policy and clean up old data.

        Returns:
            Tuple of (sessions_deleted, log_entries_deleted)
        """
        settings = self.get_retention_settings()
        mode = settings.get('retention_mode', 'none')

        if mode == 'none':
            return 0, 0

        sessions_deleted = 0
        logs_deleted = 0

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if mode == 'sessions':
                    # Keep last N sessions
                    retain_count = settings.get('retain_session_count', 50)
                    cursor.execute("""
                        SELECT session_id FROM ImportSession
                        ORDER BY start_timestamp DESC
                        LIMIT -1 OFFSET ?
                    """, (retain_count,))
                    old_sessions = [row[0] for row in cursor.fetchall()]

                elif mode == 'days':
                    # Keep sessions from last X days
                    retain_days = settings.get('retain_days', 365)
                    cutoff_date = (datetime.now() - timedelta(days=retain_days)).isoformat()
                    cursor.execute("""
                        SELECT session_id FROM ImportSession
                        WHERE start_timestamp < ?
                    """, (cutoff_date,))
                    old_sessions = [row[0] for row in cursor.fetchall()]

                else:
                    old_sessions = []

                # Delete old sessions (CASCADE will delete file logs)
                for session_id in old_sessions:
                    cursor.execute("""
                        SELECT COUNT(*) FROM FileProcessingLog
                        WHERE session_id = ?
                    """, (session_id,))
                    logs_deleted += cursor.fetchone()[0]

                    cursor.execute("""
                        DELETE FROM ImportSession WHERE session_id = ?
                    """, (session_id,))
                    sessions_deleted += 1

                # Update last cleanup timestamp
                cursor.execute("""
                    UPDATE AuditRetentionSettings
                    SET last_cleanup_timestamp = ?
                    WHERE id = 1
                """, (datetime.now().isoformat(),))

                conn.commit()

            logger.info(f"Retention cleanup: {sessions_deleted} sessions, {logs_deleted} log entries deleted")
            return sessions_deleted, logs_deleted

        except Exception as e:
            logger.error(f"Failed to apply retention policy: {e}", exc_info=True)
            return 0, 0

    def get_data_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about audit data storage.

        Returns:
            Dictionary with counts and oldest session info
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT COUNT(*) FROM ImportSession")
                total_sessions = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM FileProcessingLog")
                total_file_logs = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM DuplicateMapping")
                total_duplicate_mappings = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT MIN(start_timestamp) FROM ImportSession
                """)
                oldest = cursor.fetchone()[0]

                return {
                    'total_sessions': total_sessions,
                    'total_file_logs': total_file_logs,
                    'total_duplicate_mappings': total_duplicate_mappings,
                    'oldest_session_date': oldest
                }

        except Exception as e:
            logger.error(f"Failed to get data statistics: {e}", exc_info=True)
            return {}

    # ==================== Report Generation ====================

    def generate_session_report(
        self,
        session_id: str,
        include_file_details: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive report for a session.

        Returns:
            Dictionary containing session info, statistics, and optional file details
        """
        session = self.get_session(session_id)
        if not session:
            return {}

        file_counts = self.get_session_file_counts(session_id)

        report = {
            'report_type': 'session_summary',
            'generated_at': datetime.now().isoformat(),
            'session_info': session,
            'file_breakdown': file_counts
        }

        if include_file_details:
            report['file_details'] = self.get_file_logs_for_session(session_id, limit=10000)
            report['duplicates'] = self.get_duplicates_for_session(session_id)
            report['errors'] = self.get_errors_for_session(session_id)

        return report

    def generate_duplicate_report(
        self,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate duplicate analysis report."""
        stats = self.get_duplicate_statistics()

        report = {
            'report_type': 'duplicate_analysis',
            'generated_at': datetime.now().isoformat(),
            'statistics': stats
        }

        if session_id:
            report['session_duplicates'] = self.get_duplicates_for_session(session_id)

        return report

    def generate_error_report(
        self,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate error analysis report."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if session_id:
                    cursor.execute("""
                        SELECT error_code, COUNT(*) as count
                        FROM FileProcessingLog
                        WHERE session_id = ? AND status = 'failed'
                        GROUP BY error_code
                    """, (session_id,))
                else:
                    cursor.execute("""
                        SELECT error_code, COUNT(*) as count
                        FROM FileProcessingLog
                        WHERE status = 'failed'
                        GROUP BY error_code
                    """)

                error_breakdown = {row[0] or 'Unknown': row[1] for row in cursor.fetchall()}

                report = {
                    'report_type': 'error_analysis',
                    'generated_at': datetime.now().isoformat(),
                    'error_breakdown': error_breakdown,
                    'total_errors': sum(error_breakdown.values())
                }

                if session_id:
                    report['session_id'] = session_id
                    report['errors'] = self.get_errors_for_session(session_id)

                return report

        except Exception as e:
            logger.error(f"Failed to generate error report: {e}", exc_info=True)
            return {}

    # ==================== Export Functions ====================

    def export_session_to_json(
        self,
        session_id: str,
        output_path: str,
        include_file_details: bool = True
    ) -> bool:
        """Export session report to JSON file."""
        try:
            report = self.generate_session_report(session_id, include_file_details)
            if not report:
                return False

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported session {session_id} to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export session to JSON: {e}", exc_info=True)
            return False

    def export_session_to_csv(
        self,
        session_id: str,
        output_path: str
    ) -> bool:
        """
        Export session file logs to CSV.

        Columns: source_path, destination_path, operation, status,
                 file_hash, file_size, creation_date, error_message
        """
        try:
            files = self.get_file_logs_for_session(session_id, limit=100000)
            if not files:
                return False

            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'source_path', 'destination_path', 'operation', 'status',
                    'file_hash', 'file_size', 'creation_date', 'date_source',
                    'duration_ms', 'error_code', 'error_message',
                    'duplicate_of_hash', 'filter_reason',
                    'album_name', 'album_path', 'sub_album_name'
                ])

                for file_log in files:
                    writer.writerow([
                        file_log.get('source_path', ''),
                        file_log.get('destination_path', ''),
                        file_log.get('operation', ''),
                        file_log.get('status', ''),
                        file_log.get('file_hash', ''),
                        file_log.get('file_size', ''),
                        file_log.get('creation_date', ''),
                        file_log.get('date_source', ''),
                        file_log.get('duration_ms', ''),
                        file_log.get('error_code', ''),
                        file_log.get('error_message', ''),
                        file_log.get('duplicate_of_hash', ''),
                        file_log.get('filter_reason', ''),
                        file_log.get('album_name', ''),
                        file_log.get('album_path', ''),
                        file_log.get('sub_album_name', '')
                    ])

            logger.info(f"Exported session {session_id} to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export session to CSV: {e}", exc_info=True)
            return False

    def export_duplicates_to_csv(
        self,
        output_path: str,
        session_id: Optional[str] = None
    ) -> bool:
        """Export duplicate mappings to CSV."""
        try:
            with self._get_connection() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if session_id:
                    cursor.execute("""
                        SELECT * FROM DuplicateMapping
                        WHERE first_seen_session = ?
                        ORDER BY original_hash
                    """, (session_id,))
                else:
                    cursor.execute("""
                        SELECT * FROM DuplicateMapping
                        ORDER BY original_hash
                    """)

                rows = cursor.fetchall()

            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'original_hash', 'original_path', 'duplicate_source_path',
                    'times_seen', 'first_seen_session', 'first_seen_timestamp'
                ])

                for row in rows:
                    writer.writerow([
                        row['original_hash'],
                        row['original_path'],
                        row['duplicate_source_path'],
                        row['times_seen'],
                        row['first_seen_session'],
                        row['first_seen_timestamp']
                    ])

            logger.info(f"Exported duplicates to {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to export duplicates to CSV: {e}", exc_info=True)
            return False
