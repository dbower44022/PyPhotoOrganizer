"""
Cloud Sync Worker for PyPhotoOrganizer.

Background worker thread for cloud synchronization operations.
Provides:
- Non-blocking sync operations
- Progress reporting via Qt signals
- Pause/resume/cancel support
- Error handling and reporting

Usage:
    from ui.cloud_sync_worker import CloudSyncWorker

    worker = CloudSyncWorker(database_path, storage_manager)
    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    worker.start()

    # To stop
    worker.request_stop()
    worker.wait()
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

logger = logging.getLogger(__name__)


@dataclass
class SyncProgress:
    """Progress update for sync operations."""
    current_file: int
    total_files: int
    current_bytes: int
    total_bytes: int
    current_filename: str
    status: str  # 'queuing', 'uploading', 'downloading', 'verifying', 'complete', 'error'
    message: str
    vault_type: str
    error: Optional[str] = None


class CloudSyncWorker(QThread):
    """
    Background worker for cloud sync operations.

    Signals:
        progress: Emitted with SyncProgress during sync
        file_completed: Emitted when a single file completes (file_hash, success, error)
        sync_completed: Emitted when entire sync completes (stats dict)
        error: Emitted on critical error (error message)
        paused: Emitted when sync is paused
        resumed: Emitted when sync resumes
    """

    # Signals
    progress = Signal(object)  # SyncProgress
    file_completed = Signal(str, bool, str)  # file_hash, success, error
    sync_completed = Signal(dict)  # SyncStats as dict
    error = Signal(str)
    paused = Signal()
    resumed = Signal()

    def __init__(self, database_path: str, storage_manager, parent=None):
        """
        Initialize CloudSyncWorker.

        Args:
            database_path: Path to the SQLite database
            storage_manager: StorageManager with configured backends
            parent: Parent QObject
        """
        super().__init__(parent)
        self.database_path = database_path
        self.storage_manager = storage_manager

        # Control flags
        self._stop_requested = False
        self._pause_requested = False
        self._paused = False

        # Synchronization
        self._mutex = QMutex()
        self._pause_condition = QWaitCondition()

        # Sync configuration
        self.vault_type = 'archive'
        self.operation = 'sync_to_cloud'  # 'sync_to_cloud', 'download', 'verify'
        self.batch_size = 100
        self.verify_uploads = True

        # Statistics
        self._current_file = 0
        self._total_files = 0
        self._bytes_transferred = 0

    def configure(self, vault_type: str = 'archive',
                 operation: str = 'sync_to_cloud',
                 batch_size: int = 100,
                 verify_uploads: bool = True):
        """
        Configure sync operation before starting.

        Args:
            vault_type: Type of vault to sync
            operation: Operation type ('sync_to_cloud', 'download', 'verify')
            batch_size: Number of files per batch
            verify_uploads: Whether to verify uploads
        """
        self.vault_type = vault_type
        self.operation = operation
        self.batch_size = batch_size
        self.verify_uploads = verify_uploads

    def request_stop(self):
        """Request the worker to stop gracefully."""
        self._mutex.lock()
        self._stop_requested = True
        if self._paused:
            self._pause_requested = False
            self._paused = False
            self._pause_condition.wakeAll()
        self._mutex.unlock()
        logger.info("Cloud sync stop requested")

    def request_pause(self):
        """Request the worker to pause."""
        self._mutex.lock()
        self._pause_requested = True
        self._mutex.unlock()
        logger.info("Cloud sync pause requested")

    def request_resume(self):
        """Request the worker to resume from pause."""
        self._mutex.lock()
        self._pause_requested = False
        self._paused = False
        self._pause_condition.wakeAll()
        self._mutex.unlock()
        logger.info("Cloud sync resume requested")

    def is_paused(self) -> bool:
        """Check if worker is currently paused."""
        self._mutex.lock()
        paused = self._paused
        self._mutex.unlock()
        return paused

    def _check_pause(self):
        """Check for pause request and wait if paused."""
        self._mutex.lock()
        if self._pause_requested and not self._stop_requested:
            self._paused = True
            self._mutex.unlock()
            self.paused.emit()

            self._mutex.lock()
            while self._paused and not self._stop_requested:
                self._pause_condition.wait(self._mutex)
            self._mutex.unlock()

            if not self._stop_requested:
                self.resumed.emit()
        else:
            self._mutex.unlock()

    def _should_stop(self) -> bool:
        """Check if stop was requested."""
        self._mutex.lock()
        stop = self._stop_requested
        self._mutex.unlock()
        return stop

    def run(self):
        """Main worker thread execution."""
        logger.info(f"Starting cloud sync worker: {self.operation} for {self.vault_type}")

        try:
            # Import here to avoid circular imports
            from cloud_sync_manager import CloudSyncManager
            from cloud_sync import CloudSync

            # Create managers
            sync_manager = CloudSyncManager(
                self.database_path,
                self.storage_manager
            )
            cloud_sync = CloudSync(self.database_path, sync_manager)

            # Execute the appropriate operation
            if self.operation == 'sync_to_cloud':
                self._run_sync_to_cloud(cloud_sync)
            elif self.operation == 'download':
                self._run_download(cloud_sync)
            elif self.operation == 'verify':
                self._run_verify(sync_manager)
            elif self.operation == 'process_queue':
                self._run_process_queue(sync_manager)
            else:
                self.error.emit(f"Unknown operation: {self.operation}")

        except Exception as e:
            logger.error(f"Cloud sync worker error: {e}", exc_info=True)
            self.error.emit(str(e))

        logger.info("Cloud sync worker finished")

    def _run_sync_to_cloud(self, cloud_sync):
        """Run sync-to-cloud operation."""
        from cloud_sync import SyncStats

        def progress_callback(current: int, total: int, message: str) -> bool:
            self._check_pause()
            if self._should_stop():
                return True

            self._current_file = current
            self._total_files = total

            progress = SyncProgress(
                current_file=current,
                total_files=total,
                current_bytes=self._bytes_transferred,
                total_bytes=0,  # Unknown initially
                current_filename=message,
                status='uploading',
                message=message,
                vault_type=self.vault_type
            )
            self.progress.emit(progress)
            return False

        stats = cloud_sync.sync_vault_to_cloud(
            vault_type=self.vault_type,
            batch_size=self.batch_size,
            progress_callback=progress_callback,
            should_stop=self._should_stop
        )

        # Emit completion
        self.sync_completed.emit({
            'total_files': stats.total_files,
            'files_uploaded': stats.files_uploaded,
            'files_skipped': stats.files_skipped,
            'files_failed': stats.files_failed,
            'bytes_transferred': stats.bytes_transferred,
            'duration_seconds': stats.duration_seconds,
            'errors': stats.errors
        })

    def _run_process_queue(self, sync_manager):
        """Process the existing upload queue."""

        def progress_callback(current: int, total: int, message: str) -> bool:
            self._check_pause()
            if self._should_stop():
                return True

            progress = SyncProgress(
                current_file=current,
                total_files=total,
                current_bytes=0,
                total_bytes=0,
                current_filename=message,
                status='uploading',
                message=message,
                vault_type=self.vault_type
            )
            self.progress.emit(progress)
            return False

        results = sync_manager.process_queue(
            progress_callback=progress_callback,
            should_stop=self._should_stop
        )

        self.sync_completed.emit(results)

    def _run_download(self, cloud_sync):
        """Run download operation."""
        # Find files needing download
        files = list(cloud_sync.find_files_needing_download(self.vault_type))
        total = len(files)

        if total == 0:
            self.sync_completed.emit({
                'total_files': 0,
                'files_downloaded': 0,
                'message': 'No files need downloading'
            })
            return

        downloaded = 0
        failed = 0

        for i, file_info in enumerate(files):
            self._check_pause()
            if self._should_stop():
                break

            progress = SyncProgress(
                current_file=i,
                total_files=total,
                current_bytes=0,
                total_bytes=0,
                current_filename=file_info.get('relative_path', ''),
                status='downloading',
                message=f"Downloading {file_info.get('relative_path', '')}",
                vault_type=self.vault_type
            )
            self.progress.emit(progress)

            # Determine local path
            local_path = self._get_local_path_for_download(file_info)
            if not local_path:
                failed += 1
                continue

            success = cloud_sync.download_from_cloud(
                file_info['file_hash'],
                self.vault_type,
                local_path
            )

            if success:
                downloaded += 1
                self.file_completed.emit(file_info['file_hash'], True, '')
            else:
                failed += 1
                self.file_completed.emit(file_info['file_hash'], False, 'Download failed')

        self.sync_completed.emit({
            'total_files': total,
            'files_downloaded': downloaded,
            'files_failed': failed
        })

    def _run_verify(self, sync_manager):
        """Run verification operation."""
        import sqlite3

        try:
            conn = sqlite3.connect(self.database_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get files to verify
            cursor.execute("""
                SELECT file_hash, cloud_path FROM CloudSyncStatus
                WHERE storage_location = ?
                AND upload_status IN ('completed', 'verified')
            """, (self.vault_type,))

            files = cursor.fetchall()
            conn.close()

            total = len(files)
            verified = 0
            failed = 0

            for i, row in enumerate(files):
                self._check_pause()
                if self._should_stop():
                    break

                file_hash = row['file_hash']

                progress = SyncProgress(
                    current_file=i,
                    total_files=total,
                    current_bytes=0,
                    total_bytes=0,
                    current_filename=file_hash[:16] + '...',
                    status='verifying',
                    message=f"Verifying {file_hash[:16]}...",
                    vault_type=self.vault_type
                )
                self.progress.emit(progress)

                if sync_manager.verify_upload(file_hash, self.vault_type):
                    verified += 1
                else:
                    failed += 1
                    self.file_completed.emit(file_hash, False, 'Verification failed')

            self.sync_completed.emit({
                'total_files': total,
                'files_verified': verified,
                'files_failed': failed
            })

        except Exception as e:
            logger.error(f"Verification error: {e}")
            self.error.emit(str(e))

    def _get_local_path_for_download(self, file_info: Dict) -> Optional[str]:
        """Determine local path for downloaded file."""
        import sqlite3

        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()

            # Get archive location
            cursor.execute("""
                SELECT archive_location FROM DatabaseMetadata WHERE id = 1
            """)
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                import os
                relative_path = file_info.get('relative_path', '')
                if relative_path:
                    return os.path.join(result[0], relative_path)

        except Exception as e:
            logger.error(f"Error getting local path: {e}")

        return None


class SyncStatusPoller(QThread):
    """
    Background poller for sync status updates.

    Periodically checks sync status and emits updates.
    Useful for showing real-time sync status in the UI.
    """

    status_updated = Signal(dict)  # sync status summary

    def __init__(self, database_path: str, storage_manager,
                 poll_interval: float = 5.0, parent=None):
        """
        Initialize SyncStatusPoller.

        Args:
            database_path: Path to the SQLite database
            storage_manager: StorageManager instance
            poll_interval: Seconds between polls
            parent: Parent QObject
        """
        super().__init__(parent)
        self.database_path = database_path
        self.storage_manager = storage_manager
        self.poll_interval = poll_interval
        self._stop_requested = False
        self.vault_types = ['archive', 'video_archive', 'prior_revision', 'delete_vault']

    def request_stop(self):
        """Request the poller to stop."""
        self._stop_requested = True

    def run(self):
        """Poll sync status periodically."""
        from cloud_sync_manager import CloudSyncManager
        from cloud_sync import CloudSync

        sync_manager = CloudSyncManager(self.database_path, self.storage_manager)
        cloud_sync = CloudSync(self.database_path, sync_manager)

        while not self._stop_requested:
            try:
                status = {}
                for vault_type in self.vault_types:
                    backend = self.storage_manager.get_backend(vault_type)
                    if backend and backend.storage_type != 'local':
                        status[vault_type] = cloud_sync.get_sync_status_summary(vault_type)

                if status:
                    self.status_updated.emit(status)

            except Exception as e:
                logger.debug(f"Status poll error: {e}")

            # Sleep in small increments to allow quick stopping
            for _ in range(int(self.poll_interval * 10)):
                if self._stop_requested:
                    break
                time.sleep(0.1)

        logger.debug("Sync status poller stopped")
