"""
Cloud Sync Orchestration for PyPhotoOrganizer.

High-level synchronization operations between local and cloud storage.
Provides:
- Full vault sync (local to cloud)
- Selective file sync
- Cloud to local downloads
- Conflict detection and resolution
- Sync status reporting

This module orchestrates the CloudSyncManager for batch operations.

Usage:
    from cloud_sync import CloudSync
    from storage_backend import StorageManager
    from cloud_sync_manager import CloudSyncManager

    storage_manager = StorageManager(config)
    sync_manager = CloudSyncManager(db_path, storage_manager)
    cloud_sync = CloudSync(db_path, sync_manager)

    # Sync entire archive to cloud
    results = cloud_sync.sync_vault_to_cloud('archive', progress_callback=my_callback)

    # Download a file from cloud
    cloud_sync.download_from_cloud(file_hash, 'archive', local_path)
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, Iterator, List, Optional, Set, Tuple

from cloud_sync_manager import CloudSyncManager, SyncResult, UploadTask
from storage_backend import StorageManager, StorageBackend

logger = logging.getLogger(__name__)


class ConflictResolution(Enum):
    """How to resolve conflicts between local and cloud versions."""
    KEEP_LOCAL = 'keep_local'       # Upload local version to cloud
    KEEP_CLOUD = 'keep_cloud'       # Download cloud version to local
    KEEP_BOTH = 'keep_both'         # Keep both versions (rename one)
    SKIP = 'skip'                   # Skip this file
    ASK = 'ask'                     # Ask user (via callback)


@dataclass
class SyncStats:
    """Statistics for a sync operation."""
    total_files: int = 0
    files_uploaded: int = 0
    files_downloaded: int = 0
    files_skipped: int = 0
    files_failed: int = 0
    bytes_transferred: int = 0
    conflicts_found: int = 0
    conflicts_resolved: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"SyncStats: {self.files_uploaded} uploaded, {self.files_downloaded} downloaded, "
            f"{self.files_skipped} skipped, {self.files_failed} failed, "
            f"{self.bytes_transferred / (1024*1024):.1f} MB transferred"
        )


@dataclass
class FileConflict:
    """Represents a conflict between local and cloud versions."""
    file_hash: str
    relative_path: str
    local_size: int
    cloud_size: int
    local_modified: Optional[datetime]
    cloud_modified: Optional[datetime]
    local_exists: bool
    cloud_exists: bool
    conflict_type: str  # 'size_mismatch', 'missing_local', 'missing_cloud', 'both_modified'


class CloudSync:
    """
    High-level cloud synchronization orchestrator.

    Coordinates sync operations across vaults using CloudSyncManager.
    """

    def __init__(self, database_path: str, sync_manager: CloudSyncManager):
        """
        Initialize CloudSync.

        Args:
            database_path: Path to the SQLite database
            sync_manager: CloudSyncManager instance for queue operations
        """
        self.database_path = database_path
        self.sync_manager = sync_manager
        self.storage_manager = sync_manager.storage_manager

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with WAL mode."""
        conn = sqlite3.connect(self.database_path)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    # ========== Finding Files to Sync ==========

    def find_files_needing_upload(self, vault_type: str = 'archive',
                                  limit: int = None) -> Iterator[Dict[str, Any]]:
        """
        Find files in database that haven't been uploaded to cloud.

        Checks UniquePhotos against CloudSyncStatus to find files
        that exist locally but not in cloud storage.

        Args:
            vault_type: Type of vault ('archive', 'video_archive', etc.)
            limit: Maximum number of files to return

        Yields:
            Dict with file_hash, relative_path, file_size for each file
        """
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get the backend for this vault
            backend = self.storage_manager.get_backend(vault_type)
            if not backend:
                logger.warning(f"No backend configured for vault: {vault_type}")
                return

            # Check if this vault uses cloud storage
            if backend.storage_type == 'local':
                logger.info(f"Vault '{vault_type}' uses local storage, no cloud sync needed")
                return

            # Find files that exist in UniquePhotos but not in CloudSyncStatus
            # for this specific vault and provider
            query = """
                SELECT up.file_hash, up.relative_path, up.file_size, up.file_name
                FROM UniquePhotos up
                WHERE up.storage_type = ?
                AND up.relative_path IS NOT NULL
                AND NOT EXISTS (
                    SELECT 1 FROM CloudSyncStatus css
                    WHERE css.file_hash = up.file_hash
                    AND css.storage_location = ?
                    AND css.upload_status IN ('completed', 'verified')
                )
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, (vault_type, vault_type))

            for row in cursor:
                yield {
                    'file_hash': row['file_hash'],
                    'relative_path': row['relative_path'],
                    'file_size': row['file_size'],
                    'file_name': row['file_name']
                }

            conn.close()

        except Exception as e:
            logger.error(f"Error finding files needing upload: {e}")

    def find_files_needing_download(self, vault_type: str = 'archive',
                                    limit: int = None) -> Iterator[Dict[str, Any]]:
        """
        Find files that exist in cloud but not locally.

        Useful for restoring files or populating a local cache.

        Args:
            vault_type: Type of vault
            limit: Maximum number of files to return

        Yields:
            Dict with file_hash, cloud_path, file_size for each file
        """
        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Find files in CloudSyncStatus that exist in cloud but may need local copy
            query = """
                SELECT css.file_hash, css.cloud_path, up.file_size, up.relative_path
                FROM CloudSyncStatus css
                JOIN UniquePhotos up ON css.file_hash = up.file_hash
                WHERE css.storage_location = ?
                AND css.upload_status IN ('completed', 'verified')
                AND NOT EXISTS (
                    SELECT 1 FROM FileLocations fl
                    WHERE fl.file_hash = css.file_hash
                    AND fl.location_type = 'local'
                )
            """

            if limit:
                query += f" LIMIT {limit}"

            cursor.execute(query, (vault_type,))

            for row in cursor:
                yield {
                    'file_hash': row['file_hash'],
                    'cloud_path': row['cloud_path'],
                    'relative_path': row['relative_path'],
                    'file_size': row['file_size']
                }

            conn.close()

        except Exception as e:
            logger.error(f"Error finding files needing download: {e}")

    def get_sync_status_summary(self, vault_type: str = 'archive') -> Dict[str, Any]:
        """
        Get summary of sync status for a vault.

        Returns:
            Dict with counts of synced, pending, failed files
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Count total files in vault
            cursor.execute("""
                SELECT COUNT(*) FROM UniquePhotos
                WHERE storage_type = ? AND relative_path IS NOT NULL
            """, (vault_type,))
            total_files = cursor.fetchone()[0]

            # Count synced files
            cursor.execute("""
                SELECT COUNT(DISTINCT css.file_hash)
                FROM CloudSyncStatus css
                WHERE css.storage_location = ?
                AND css.upload_status IN ('completed', 'verified')
            """, (vault_type,))
            synced_files = cursor.fetchone()[0]

            # Count pending uploads
            cursor.execute("""
                SELECT COUNT(*) FROM CloudUploadQueue
                WHERE target_storage = ?
                AND status IN ('queued', 'uploading')
            """, (vault_type,))
            pending_uploads = cursor.fetchone()[0]

            # Count failed uploads
            cursor.execute("""
                SELECT COUNT(*) FROM CloudUploadQueue
                WHERE target_storage = ?
                AND status = 'failed'
            """, (vault_type,))
            failed_uploads = cursor.fetchone()[0]

            conn.close()

            return {
                'vault_type': vault_type,
                'total_files': total_files,
                'synced_files': synced_files,
                'pending_uploads': pending_uploads,
                'failed_uploads': failed_uploads,
                'sync_percentage': (synced_files / total_files * 100) if total_files > 0 else 0,
                'needs_sync': total_files - synced_files - pending_uploads
            }

        except Exception as e:
            logger.error(f"Error getting sync status summary: {e}")
            return {
                'vault_type': vault_type,
                'total_files': 0,
                'synced_files': 0,
                'pending_uploads': 0,
                'failed_uploads': 0,
                'sync_percentage': 0,
                'needs_sync': 0,
                'error': str(e)
            }

    # ========== Sync Operations ==========

    def sync_vault_to_cloud(self, vault_type: str = 'archive',
                           batch_size: int = 100,
                           progress_callback: Callable[[int, int, str], bool] = None,
                           should_stop: Callable[[], bool] = None) -> SyncStats:
        """
        Sync all files from a vault to cloud storage.

        This method:
        1. Finds all files not yet uploaded to cloud
        2. Queues them for upload
        3. Processes the upload queue

        Args:
            vault_type: Type of vault to sync
            batch_size: Number of files to process per batch
            progress_callback: Called with (current, total, message), returns True to stop
            should_stop: Callable that returns True if sync should stop

        Returns:
            SyncStats with sync results
        """
        import time
        start_time = time.time()
        stats = SyncStats()

        logger.info(f"Starting vault sync to cloud: {vault_type}")

        # Get backend and verify it's cloud storage
        backend = self.storage_manager.get_backend(vault_type)
        if not backend:
            stats.errors.append(f"No backend configured for vault: {vault_type}")
            return stats

        if backend.storage_type == 'local':
            logger.info(f"Vault '{vault_type}' uses local storage, skipping cloud sync")
            return stats

        # Get local backend to read files from
        local_backend = self._get_local_backend_for_vault(vault_type)
        if not local_backend:
            stats.errors.append(f"No local backend available for vault: {vault_type}")
            return stats

        try:
            # Find all files needing upload
            files_to_sync = list(self.find_files_needing_upload(vault_type))
            stats.total_files = len(files_to_sync)

            if stats.total_files == 0:
                logger.info(f"No files need syncing for vault: {vault_type}")
                return stats

            logger.info(f"Found {stats.total_files} files needing sync")

            # Queue files for upload in batches
            for i, file_info in enumerate(files_to_sync):
                # Check for stop signal
                if should_stop and should_stop():
                    logger.info("Sync stopped by user request")
                    break

                # Progress callback
                if progress_callback:
                    message = f"Queuing: {file_info['file_name']}"
                    if progress_callback(i, stats.total_files, message):
                        logger.info("Sync stopped by callback")
                        break

                # Get local path for the file
                local_path = local_backend.resolve_path(file_info['relative_path'])
                if not local_path or not os.path.exists(local_path):
                    logger.warning(f"Local file not found: {file_info['relative_path']}")
                    stats.files_skipped += 1
                    continue

                # Queue for upload
                try:
                    self.sync_manager.queue_upload(
                        file_hash=file_info['file_hash'],
                        local_path=local_path,
                        target_storage=vault_type,
                        target_path=file_info['relative_path']
                    )
                except Exception as e:
                    logger.error(f"Failed to queue file: {e}")
                    stats.files_failed += 1
                    stats.errors.append(f"Queue failed for {file_info['file_hash']}: {e}")

            # Process the upload queue
            if progress_callback:
                progress_callback(0, stats.total_files, "Processing upload queue...")

            def upload_progress(current, total, message):
                stats.files_uploaded = current
                if progress_callback:
                    return progress_callback(current, total, message)
                return False

            queue_results = self.sync_manager.process_queue(
                progress_callback=upload_progress,
                should_stop=should_stop
            )

            stats.files_uploaded = queue_results.get('processed', 0)
            stats.files_failed += queue_results.get('failed', 0)
            stats.bytes_transferred = queue_results.get('bytes_uploaded', 0)

        except Exception as e:
            logger.error(f"Error during vault sync: {e}", exc_info=True)
            stats.errors.append(str(e))

        stats.duration_seconds = time.time() - start_time
        logger.info(f"Vault sync completed: {stats}")

        return stats

    def download_from_cloud(self, file_hash: str, vault_type: str,
                           local_path: str, verify: bool = True) -> bool:
        """
        Download a file from cloud storage to local filesystem.

        Args:
            file_hash: Hash of the file to download
            vault_type: Type of vault
            local_path: Destination local path
            verify: Whether to verify hash after download

        Returns:
            True if download succeeded, False otherwise
        """
        logger.info(f"Downloading {file_hash} from {vault_type} to {local_path}")

        try:
            # Get cloud backend
            backend = self.storage_manager.get_backend(vault_type)
            if not backend:
                logger.error(f"No backend for vault: {vault_type}")
                return False

            # Get the cloud path for this file
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT cloud_path FROM CloudSyncStatus
                WHERE file_hash = ? AND storage_location = ?
                AND upload_status IN ('completed', 'verified')
            """, (file_hash, vault_type))

            result = cursor.fetchone()
            conn.close()

            if not result:
                logger.error(f"File {file_hash} not found in cloud sync status")
                return False

            cloud_path = result[0]

            # Create local directory if needed
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download the file
            success = backend.copy_to_local(cloud_path, local_path)
            if not success:
                logger.error(f"Download failed for {cloud_path}")
                return False

            # Verify hash if requested
            if verify:
                import hashlib
                sha256 = hashlib.sha256()
                with open(local_path, 'rb') as f:
                    for chunk in iter(lambda: f.read(8192), b''):
                        sha256.update(chunk)
                local_hash = sha256.hexdigest()

                if local_hash != file_hash:
                    logger.error(f"Hash mismatch after download: expected {file_hash}, got {local_hash}")
                    os.remove(local_path)
                    return False

            # Record local location
            self._record_local_location(file_hash, vault_type, local_path)

            logger.info(f"Successfully downloaded {file_hash} to {local_path}")
            return True

        except Exception as e:
            logger.error(f"Error downloading file: {e}", exc_info=True)
            return False

    def _get_local_backend_for_vault(self, vault_type: str) -> Optional[StorageBackend]:
        """
        Get local storage backend for reading source files.

        For cloud vaults, we need to find where the local copies are stored.
        """
        # First check if we have a local backend configured
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get archive location from metadata
            cursor.execute("""
                SELECT archive_location, video_archive_location,
                       prior_revision_archive_location, delete_vault_location
                FROM DatabaseMetadata WHERE id = 1
            """)
            result = cursor.fetchone()
            conn.close()

            if result:
                location_map = {
                    'archive': result[0],
                    'video_archive': result[1],
                    'prior_revision': result[2],
                    'delete_vault': result[3]
                }

                local_path = location_map.get(vault_type)
                if local_path and os.path.exists(local_path):
                    from storage_backend import LocalStorageBackend
                    return LocalStorageBackend(local_path)

        except Exception as e:
            logger.error(f"Error getting local backend: {e}")

        return None

    def _record_local_location(self, file_hash: str, vault_type: str, local_path: str):
        """Record that a file exists at a local location."""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO FileLocations
                (file_hash, location_type, storage_backend, relative_path, verified_at)
                VALUES (?, 'local', ?, ?, ?)
            """, (file_hash, vault_type, local_path, datetime.now().isoformat()))

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error recording local location: {e}")

    # ========== Conflict Detection and Resolution ==========

    def find_conflicts(self, vault_type: str = 'archive') -> List[FileConflict]:
        """
        Find files with conflicts between local and cloud versions.

        Checks for:
        - Size mismatches
        - Files missing from local
        - Files missing from cloud

        Args:
            vault_type: Type of vault to check

        Returns:
            List of FileConflict objects
        """
        conflicts = []

        try:
            backend = self.storage_manager.get_backend(vault_type)
            local_backend = self._get_local_backend_for_vault(vault_type)

            if not backend or not local_backend:
                logger.warning(f"Cannot check conflicts without both backends")
                return conflicts

            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get files that should be in both locations
            cursor.execute("""
                SELECT up.file_hash, up.relative_path, up.file_size,
                       css.cloud_path, css.upload_status
                FROM UniquePhotos up
                LEFT JOIN CloudSyncStatus css ON up.file_hash = css.file_hash
                    AND css.storage_location = ?
                WHERE up.storage_type = ?
            """, (vault_type, vault_type))

            for row in cursor:
                file_hash = row['file_hash']
                relative_path = row['relative_path']
                expected_size = row['file_size']
                cloud_path = row['cloud_path']
                cloud_status = row['upload_status']

                # Check local existence and size
                local_path = local_backend.resolve_path(relative_path) if relative_path else None
                local_exists = local_path and os.path.exists(local_path)
                local_size = os.path.getsize(local_path) if local_exists else 0

                # Check cloud existence
                cloud_exists = cloud_status in ('completed', 'verified')
                cloud_size = 0
                if cloud_exists and cloud_path:
                    try:
                        cloud_size = backend.get_size(cloud_path)
                    except:
                        pass

                # Detect conflicts
                conflict_type = None

                if local_exists and cloud_exists:
                    if local_size != cloud_size:
                        conflict_type = 'size_mismatch'
                elif local_exists and not cloud_exists:
                    conflict_type = 'missing_cloud'
                elif not local_exists and cloud_exists:
                    conflict_type = 'missing_local'

                if conflict_type:
                    conflicts.append(FileConflict(
                        file_hash=file_hash,
                        relative_path=relative_path,
                        local_size=local_size,
                        cloud_size=cloud_size,
                        local_modified=datetime.fromtimestamp(os.path.getmtime(local_path)) if local_exists else None,
                        cloud_modified=None,  # Would need to get from cloud
                        local_exists=local_exists,
                        cloud_exists=cloud_exists,
                        conflict_type=conflict_type
                    ))

            conn.close()

        except Exception as e:
            logger.error(f"Error finding conflicts: {e}", exc_info=True)

        return conflicts

    def resolve_conflict(self, conflict: FileConflict,
                        resolution: ConflictResolution,
                        vault_type: str = 'archive') -> bool:
        """
        Resolve a file conflict.

        Args:
            conflict: The conflict to resolve
            resolution: How to resolve the conflict
            vault_type: Type of vault

        Returns:
            True if resolution succeeded, False otherwise
        """
        logger.info(f"Resolving conflict for {conflict.file_hash}: {resolution.value}")

        try:
            if resolution == ConflictResolution.SKIP:
                return True

            backend = self.storage_manager.get_backend(vault_type)
            local_backend = self._get_local_backend_for_vault(vault_type)

            if resolution == ConflictResolution.KEEP_LOCAL:
                # Upload local version to cloud
                if conflict.local_exists:
                    local_path = local_backend.resolve_path(conflict.relative_path)
                    self.sync_manager.queue_upload(
                        file_hash=conflict.file_hash,
                        local_path=local_path,
                        target_storage=vault_type,
                        target_path=conflict.relative_path,
                        priority=10  # High priority for conflict resolution
                    )
                    return True
                else:
                    logger.error("Cannot keep local: file doesn't exist locally")
                    return False

            elif resolution == ConflictResolution.KEEP_CLOUD:
                # Download cloud version to local
                if conflict.cloud_exists:
                    local_path = local_backend.resolve_path(conflict.relative_path)
                    return self.download_from_cloud(
                        conflict.file_hash, vault_type, local_path
                    )
                else:
                    logger.error("Cannot keep cloud: file doesn't exist in cloud")
                    return False

            elif resolution == ConflictResolution.KEEP_BOTH:
                # Keep both versions - rename the cloud version
                if conflict.local_exists and conflict.cloud_exists:
                    # Download cloud version with different name
                    base, ext = os.path.splitext(conflict.relative_path)
                    cloud_local_path = local_backend.resolve_path(f"{base}_cloud{ext}")
                    return self.download_from_cloud(
                        conflict.file_hash, vault_type, cloud_local_path, verify=False
                    )
                return True

            return False

        except Exception as e:
            logger.error(f"Error resolving conflict: {e}", exc_info=True)
            return False

    # ========== Batch Operations ==========

    def queue_all_for_sync(self, vault_type: str = 'archive',
                          priority: int = 0) -> int:
        """
        Queue all un-synced files for upload without processing.

        Useful for preparing a batch sync to run later.

        Args:
            vault_type: Type of vault
            priority: Upload priority (higher = sooner)

        Returns:
            Number of files queued
        """
        local_backend = self._get_local_backend_for_vault(vault_type)
        if not local_backend:
            logger.error(f"No local backend for vault: {vault_type}")
            return 0

        count = 0
        for file_info in self.find_files_needing_upload(vault_type):
            local_path = local_backend.resolve_path(file_info['relative_path'])
            if local_path and os.path.exists(local_path):
                try:
                    self.sync_manager.queue_upload(
                        file_hash=file_info['file_hash'],
                        local_path=local_path,
                        target_storage=vault_type,
                        target_path=file_info['relative_path'],
                        priority=priority
                    )
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to queue {file_info['file_hash']}: {e}")

        logger.info(f"Queued {count} files for sync to {vault_type}")
        return count

    def clear_failed_uploads(self, vault_type: str = None,
                            retry: bool = False) -> int:
        """
        Clear or retry failed uploads.

        Args:
            vault_type: Specific vault, or None for all
            retry: If True, reset to 'queued' status instead of deleting

        Returns:
            Number of entries affected
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if retry:
                query = "UPDATE CloudUploadQueue SET status = 'queued', attempts = 0, last_error = NULL"
            else:
                query = "DELETE FROM CloudUploadQueue"

            query += " WHERE status = 'failed'"

            if vault_type:
                query += f" AND target_storage = ?"
                cursor.execute(query, (vault_type,))
            else:
                cursor.execute(query)

            affected = cursor.rowcount
            conn.commit()
            conn.close()

            action = "reset for retry" if retry else "cleared"
            logger.info(f"{affected} failed uploads {action}")
            return affected

        except Exception as e:
            logger.error(f"Error clearing failed uploads: {e}")
            return 0
