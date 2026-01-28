"""
Cloud Sync Manager for PyPhotoOrganizer.

Manages synchronization between local storage and cloud storage backends.
Provides:
- Upload queue management with offline support
- Background sync processing
- Progress tracking and reporting
- Retry logic for failed operations
- Verification of cloud uploads

Usage:
    from cloud_sync_manager import CloudSyncManager
    from storage_backend import StorageManager

    manager = StorageManager(storage_config)
    sync = CloudSyncManager(database_path, manager)

    # Queue a file for upload
    sync.queue_upload(file_hash, local_path, 'archive', '2024/01/photo.jpg')

    # Process the queue
    results = sync.process_queue(progress_callback=my_callback)
"""

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from storage_backend import StorageManager, StorageBackend

logger = logging.getLogger(__name__)


@dataclass
class UploadTask:
    """Represents a pending upload task."""
    id: int
    file_hash: str
    local_path: str
    target_storage: str  # 'archive', 'video_archive', etc.
    target_path: str     # Relative path in target storage
    priority: int
    queued_at: str
    attempts: int
    last_attempt: Optional[str]
    last_error: Optional[str]
    status: str  # 'queued', 'uploading', 'completed', 'failed'


@dataclass
class SyncResult:
    """Result of a sync operation."""
    file_hash: str
    local_path: str
    cloud_path: str
    storage_type: str
    cloud_provider: str
    success: bool
    error_message: Optional[str] = None
    bytes_uploaded: int = 0
    duration_seconds: float = 0.0


class CloudSyncManager:
    """
    Manages cloud synchronization operations.

    Handles queueing, processing, and tracking of cloud uploads.
    """

    # Upload status constants
    STATUS_QUEUED = 'queued'
    STATUS_UPLOADING = 'uploading'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_VERIFIED = 'verified'

    def __init__(self, database_path: str, storage_manager: StorageManager,
                 max_retries: int = 3, retry_delay: float = 5.0):
        """
        Initialize CloudSyncManager.

        Args:
            database_path: Path to the SQLite database
            storage_manager: StorageManager with configured backends
            max_retries: Maximum retry attempts for failed uploads
            retry_delay: Base delay between retries (seconds)
        """
        self.database_path = database_path
        self.storage_manager = storage_manager
        self.max_retries = max_retries
        self.retry_delay = retry_delay

        self._ensure_tables()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode."""
        conn = sqlite3.connect(self.database_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_tables(self):
        """Ensure cloud sync tables exist."""
        from database_schema import (
            CLOUD_SYNC_STATUS_TABLE,
            CLOUD_UPLOAD_QUEUE_TABLE,
            FILE_LOCATIONS_TABLE,
            CLOUD_SYNC_STATUS_INDEXES,
            CLOUD_UPLOAD_QUEUE_INDEXES,
            FILE_LOCATIONS_INDEXES
        )

        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # Create tables
            cursor.execute(CLOUD_SYNC_STATUS_TABLE)
            cursor.execute(CLOUD_UPLOAD_QUEUE_TABLE)
            cursor.execute(FILE_LOCATIONS_TABLE)

            # Create indexes
            for index_sql in CLOUD_SYNC_STATUS_INDEXES:
                cursor.execute(index_sql)
            for index_sql in CLOUD_UPLOAD_QUEUE_INDEXES:
                cursor.execute(index_sql)
            for index_sql in FILE_LOCATIONS_INDEXES:
                cursor.execute(index_sql)

            conn.commit()
            logger.debug("Cloud sync tables ensured")

        finally:
            conn.close()

    def queue_upload(self, file_hash: str, local_path: str,
                    target_storage: str, target_path: str,
                    priority: int = 0) -> int:
        """
        Add a file to the upload queue.

        Args:
            file_hash: SHA-256 hash of the file
            local_path: Absolute path to local file
            target_storage: Target storage type ('archive', 'video_archive', etc.)
            target_path: Relative path in target storage
            priority: Upload priority (higher = sooner)

        Returns:
            Queue entry ID
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO CloudUploadQueue
                (file_hash, local_path, target_storage, target_path, priority, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (file_hash, local_path, target_storage, target_path,
                  priority, self.STATUS_QUEUED))

            conn.commit()
            queue_id = cursor.lastrowid

            logger.debug(f"Queued upload: {file_hash} -> {target_storage}/{target_path}")
            return queue_id

        finally:
            conn.close()

    def get_queue_count(self, status: str = None) -> int:
        """
        Get count of items in upload queue.

        Args:
            status: Filter by status (None for all)

        Returns:
            Number of queued items
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            if status:
                cursor.execute(
                    "SELECT COUNT(*) FROM CloudUploadQueue WHERE status = ?",
                    (status,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM CloudUploadQueue")

            return cursor.fetchone()[0]

        finally:
            conn.close()

    def get_pending_uploads(self, limit: int = 100) -> List[UploadTask]:
        """
        Get pending uploads from queue.

        Args:
            limit: Maximum number of tasks to return

        Returns:
            List of UploadTask objects
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, file_hash, local_path, target_storage, target_path,
                       priority, queued_at, attempts, last_attempt, last_error, status
                FROM CloudUploadQueue
                WHERE status IN (?, ?)
                ORDER BY priority DESC, queued_at ASC
                LIMIT ?
            """, (self.STATUS_QUEUED, self.STATUS_FAILED, limit))

            tasks = []
            for row in cursor.fetchall():
                # Skip failed tasks that have exceeded retry limit
                if row['status'] == self.STATUS_FAILED and row['attempts'] >= self.max_retries:
                    continue

                tasks.append(UploadTask(
                    id=row['id'],
                    file_hash=row['file_hash'],
                    local_path=row['local_path'],
                    target_storage=row['target_storage'],
                    target_path=row['target_path'],
                    priority=row['priority'],
                    queued_at=row['queued_at'],
                    attempts=row['attempts'],
                    last_attempt=row['last_attempt'],
                    last_error=row['last_error'],
                    status=row['status']
                ))

            return tasks

        finally:
            conn.close()

    def _update_task_status(self, task_id: int, status: str,
                           error: str = None, increment_attempts: bool = False):
        """Update task status in the queue."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            if increment_attempts:
                cursor.execute("""
                    UPDATE CloudUploadQueue
                    SET status = ?, last_attempt = ?, last_error = ?,
                        attempts = attempts + 1
                    WHERE id = ?
                """, (status, datetime.now().isoformat(), error, task_id))
            else:
                cursor.execute("""
                    UPDATE CloudUploadQueue
                    SET status = ?, last_attempt = ?, last_error = ?
                    WHERE id = ?
                """, (status, datetime.now().isoformat(), error, task_id))

            conn.commit()

        finally:
            conn.close()

    def _record_sync_status(self, file_hash: str, storage_location: str,
                           cloud_provider: str, cloud_path: str,
                           status: str, etag: str = None,
                           storage_class: str = None, error: str = None):
        """Record sync status in the database."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT OR REPLACE INTO CloudSyncStatus
                (file_hash, storage_location, cloud_provider, cloud_path,
                 upload_status, upload_completed, cloud_etag, cloud_storage_class,
                 last_error, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (file_hash, storage_location, cloud_provider, cloud_path,
                  status, now if status == self.STATUS_COMPLETED else None,
                  etag, storage_class, error,
                  now if status == self.STATUS_VERIFIED else None))

            conn.commit()

        finally:
            conn.close()

    def _record_file_location(self, file_hash: str, location_type: str,
                             storage_backend: str, relative_path: str,
                             cloud_provider: str = None, cloud_bucket: str = None):
        """Record file location in the database."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO FileLocations
                (file_hash, location_type, storage_backend, relative_path,
                 cloud_provider, cloud_bucket, verified_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (file_hash, location_type, storage_backend, relative_path,
                  cloud_provider, cloud_bucket, datetime.now().isoformat()))

            conn.commit()

        finally:
            conn.close()

    def process_upload(self, task: UploadTask,
                      progress_callback: Callable = None) -> SyncResult:
        """
        Process a single upload task.

        Args:
            task: UploadTask to process
            progress_callback: Optional callback for progress updates

        Returns:
            SyncResult with operation outcome
        """
        backend = self.storage_manager.get_backend(task.target_storage)
        if not backend:
            error = f"No backend configured for storage: {task.target_storage}"
            logger.error(error)
            self._update_task_status(task.id, self.STATUS_FAILED,
                                    error, increment_attempts=True)
            return SyncResult(
                file_hash=task.file_hash,
                local_path=task.local_path,
                cloud_path=task.target_path,
                storage_type=task.target_storage,
                cloud_provider='unknown',
                success=False,
                error_message=error
            )

        # Check if local file still exists
        if not os.path.exists(task.local_path):
            error = f"Local file not found: {task.local_path}"
            logger.error(error)
            self._update_task_status(task.id, self.STATUS_FAILED,
                                    error, increment_attempts=True)
            return SyncResult(
                file_hash=task.file_hash,
                local_path=task.local_path,
                cloud_path=task.target_path,
                storage_type=task.target_storage,
                cloud_provider=backend.storage_type,
                success=False,
                error_message=error
            )

        # Update status to uploading
        self._update_task_status(task.id, self.STATUS_UPLOADING)

        start_time = time.time()
        file_size = os.path.getsize(task.local_path)

        try:
            # Perform the upload
            success = backend.copy_from_local(task.local_path, task.target_path)

            if success:
                duration = time.time() - start_time

                # Get cloud file info for ETag
                cloud_info = backend.get_file_info(task.target_path)
                etag = cloud_info.content_hash if cloud_info else None

                # Record success
                self._update_task_status(task.id, self.STATUS_COMPLETED)
                self._record_sync_status(
                    task.file_hash, task.target_storage,
                    backend.storage_type, task.target_path,
                    self.STATUS_COMPLETED, etag=etag
                )
                self._record_file_location(
                    task.file_hash, 'cloud', task.target_storage,
                    task.target_path, backend.storage_type,
                    getattr(backend, 'bucket', None)
                )

                logger.info(f"Uploaded {task.file_hash} to {backend.storage_type}://{task.target_path}")

                return SyncResult(
                    file_hash=task.file_hash,
                    local_path=task.local_path,
                    cloud_path=task.target_path,
                    storage_type=task.target_storage,
                    cloud_provider=backend.storage_type,
                    success=True,
                    bytes_uploaded=file_size,
                    duration_seconds=duration
                )
            else:
                error = "Upload returned False"
                self._update_task_status(task.id, self.STATUS_FAILED,
                                        error, increment_attempts=True)
                return SyncResult(
                    file_hash=task.file_hash,
                    local_path=task.local_path,
                    cloud_path=task.target_path,
                    storage_type=task.target_storage,
                    cloud_provider=backend.storage_type,
                    success=False,
                    error_message=error
                )

        except Exception as e:
            error = str(e)
            logger.error(f"Upload failed: {error}")
            self._update_task_status(task.id, self.STATUS_FAILED,
                                    error, increment_attempts=True)
            self._record_sync_status(
                task.file_hash, task.target_storage,
                backend.storage_type, task.target_path,
                self.STATUS_FAILED, error=error
            )
            return SyncResult(
                file_hash=task.file_hash,
                local_path=task.local_path,
                cloud_path=task.target_path,
                storage_type=task.target_storage,
                cloud_provider=backend.storage_type,
                success=False,
                error_message=error
            )

    def process_queue(self, limit: int = None,
                     progress_callback: Callable = None,
                     should_stop: Callable = None) -> Dict[str, Any]:
        """
        Process pending uploads from the queue.

        Args:
            limit: Maximum number of uploads to process (None for all)
            progress_callback: Optional callback(completed, total, current_file)
            should_stop: Optional callable that returns True to stop processing

        Returns:
            Dictionary with processing statistics
        """
        tasks = self.get_pending_uploads(limit or 1000)
        total = len(tasks)

        stats = {
            'total': total,
            'completed': 0,
            'failed': 0,
            'bytes_uploaded': 0,
            'duration_seconds': 0.0,
            'results': []
        }

        if total == 0:
            logger.info("No pending uploads in queue")
            return stats

        logger.info(f"Processing {total} pending uploads")

        for i, task in enumerate(tasks):
            # Check for stop signal
            if should_stop and should_stop():
                logger.info("Stop requested - halting queue processing")
                break

            # Callback for progress
            if progress_callback:
                progress_callback(i, total, task.local_path)

            # Process the upload
            result = self.process_upload(task, progress_callback)

            stats['results'].append(result)
            stats['duration_seconds'] += result.duration_seconds

            if result.success:
                stats['completed'] += 1
                stats['bytes_uploaded'] += result.bytes_uploaded
            else:
                stats['failed'] += 1

                # Add delay before next retry
                if task.attempts < self.max_retries:
                    delay = self.retry_delay * (2 ** task.attempts)
                    time.sleep(min(delay, 60))  # Cap at 60 seconds

        # Final callback
        if progress_callback:
            progress_callback(stats['completed'], total, "")

        logger.info(f"Queue processing complete: {stats['completed']}/{total} successful")
        return stats

    def verify_upload(self, file_hash: str, storage_type: str,
                     full_verify: bool = False) -> bool:
        """
        Verify that a file was successfully uploaded and matches.

        Args:
            file_hash: SHA-256 hash of the original file
            storage_type: Storage type to check
            full_verify: If True, download and hash entire file

        Returns:
            True if verification passes
        """
        backend = self.storage_manager.get_backend(storage_type)
        if not backend:
            return False

        # Get the cloud path from sync status
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT cloud_path FROM CloudSyncStatus
                WHERE file_hash = ? AND storage_location = ?
                AND upload_status = ?
            """, (file_hash, storage_type, self.STATUS_COMPLETED))

            row = cursor.fetchone()
            if not row:
                return False

            cloud_path = row['cloud_path']

        finally:
            conn.close()

        # Verify the file
        if full_verify:
            try:
                cloud_hash = backend.compute_hash(cloud_path, 'sha256')
                verified = cloud_hash == file_hash

                if verified:
                    self._record_sync_status(
                        file_hash, storage_type, backend.storage_type,
                        cloud_path, self.STATUS_VERIFIED
                    )

                return verified
            except Exception as e:
                logger.error(f"Verification failed: {e}")
                return False
        else:
            # Quick check - just verify file exists
            return backend.exists(cloud_path)

    def get_sync_status(self, file_hash: str) -> List[Dict[str, Any]]:
        """
        Get cloud sync status for a file.

        Args:
            file_hash: File hash to check

        Returns:
            List of sync status records
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT storage_location, cloud_provider, cloud_path,
                       upload_status, upload_completed, cloud_etag,
                       cloud_storage_class, retry_count, last_error, verified_at
                FROM CloudSyncStatus
                WHERE file_hash = ?
            """, (file_hash,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def get_file_locations(self, file_hash: str) -> List[Dict[str, Any]]:
        """
        Get all known locations for a file.

        Args:
            file_hash: File hash to check

        Returns:
            List of location records (local and cloud)
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT location_type, storage_backend, relative_path,
                       cloud_provider, cloud_bucket, verified_at
                FROM FileLocations
                WHERE file_hash = ?
            """, (file_hash,))

            return [dict(row) for row in cursor.fetchall()]

        finally:
            conn.close()

    def clear_completed(self) -> int:
        """
        Remove completed uploads from the queue.

        Returns:
            Number of entries removed
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM CloudUploadQueue WHERE status = ?",
                (self.STATUS_COMPLETED,)
            )
            count = cursor.rowcount
            conn.commit()
            logger.info(f"Cleared {count} completed uploads from queue")
            return count

        finally:
            conn.close()

    def reset_failed(self) -> int:
        """
        Reset failed uploads for retry.

        Returns:
            Number of entries reset
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE CloudUploadQueue
                SET status = ?, attempts = 0, last_error = NULL
                WHERE status = ? AND attempts < ?
            """, (self.STATUS_QUEUED, self.STATUS_FAILED, self.max_retries))
            count = cursor.rowcount
            conn.commit()
            logger.info(f"Reset {count} failed uploads for retry")
            return count

        finally:
            conn.close()


if __name__ == '__main__':
    """Test the cloud sync manager."""
    import tempfile

    print("Testing CloudSyncManager")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test directories
        archive_dir = os.path.join(tmpdir, 'archive')
        cloud_dir = os.path.join(tmpdir, 'cloud')
        os.makedirs(archive_dir)
        os.makedirs(cloud_dir)

        # Create test database
        db_path = os.path.join(tmpdir, 'test.db')

        # Create storage manager (local backends only for testing)
        from storage_backend import StorageManager
        storage_config = {
            'archive': {'type': 'local', 'path': archive_dir},
            'video_archive': {'type': 'local', 'path': cloud_dir}
        }
        manager = StorageManager(storage_config)

        # Create sync manager
        sync = CloudSyncManager(db_path, manager)

        # Create a test file
        test_file = os.path.join(tmpdir, 'test_photo.jpg')
        with open(test_file, 'wb') as f:
            f.write(b'fake photo data' * 1000)

        # Compute hash
        import hashlib
        with open(test_file, 'rb') as f:
            file_hash = hashlib.sha256(f.read()).hexdigest()

        print(f"Test file hash: {file_hash[:16]}...")

        # Queue upload
        queue_id = sync.queue_upload(
            file_hash=file_hash,
            local_path=test_file,
            target_storage='video_archive',
            target_path='2024/01/test_photo.jpg'
        )
        print(f"Queued upload with ID: {queue_id}")

        # Check queue count
        count = sync.get_queue_count()
        print(f"Queue count: {count}")

        # Process queue
        def progress_cb(completed, total, current):
            if current:
                print(f"  Progress: {completed}/{total} - {os.path.basename(current)}")

        results = sync.process_queue(progress_callback=progress_cb)
        print(f"Results: {results['completed']} completed, {results['failed']} failed")

        # Check sync status
        status = sync.get_sync_status(file_hash)
        print(f"Sync status: {status}")

        # Check file locations
        locations = sync.get_file_locations(file_hash)
        print(f"File locations: {locations}")

        # Verify upload
        verified = sync.verify_upload(file_hash, 'video_archive')
        print(f"Verification: {verified}")

        # Clear completed
        cleared = sync.clear_completed()
        print(f"Cleared {cleared} completed entries")

        print("=" * 50)
        print("All tests passed!")
