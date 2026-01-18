"""
Album Worker Module

Background workers for album operations that involve file I/O.
Follows the pattern established by DeleteWorker and RotateWorker.
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AddToAlbumWorker(QThread):
    """Background worker for adding photos to an album."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)  # {'added': int, 'skipped': int, 'errors': list}

    def __init__(self, album_id: int, records: list, db_path: str,
                 album_storage_path: str, worker_logger=None):
        """
        Initialize add to album worker.

        Args:
            album_id: Target album ID
            records: List of file record dicts (from grid selection)
            db_path: Database path
            album_storage_path: Album storage folder path
            worker_logger: Logger instance (optional)
        """
        super().__init__()
        self.album_id = album_id
        self.records = records
        self.db_path = db_path
        self.album_storage_path = album_storage_path
        self.worker_logger = worker_logger or logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Add to album operation cancelled by user")

    def run(self):
        """Execute add to album operation."""
        from album_manager import AlbumManager

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING ADD TO ALBUM PROCESS")
        self.worker_logger.info(f"Album ID: {self.album_id}")
        self.worker_logger.info(f"Files to add: {len(self.records)}")
        self.worker_logger.info(f"Storage: {self.album_storage_path}")
        self.worker_logger.info("=" * 80)

        added_count = 0
        skipped_count = 0
        errors = []

        # Initialize album manager
        try:
            album_manager = AlbumManager(self.db_path)
            album = album_manager.get_album(self.album_id)
            if not album:
                error_msg = f"Album {self.album_id} not found"
                self.worker_logger.error(error_msg)
                self.finished.emit({'added': 0, 'skipped': 0, 'errors': [error_msg]})
                return
        except Exception as e:
            error_msg = f"Failed to initialize: {e}"
            self.worker_logger.error(error_msg, exc_info=True)
            self.finished.emit({'added': 0, 'skipped': 0, 'errors': [error_msg]})
            return

        # Ensure storage directory exists
        if not os.path.exists(self.album_storage_path):
            try:
                os.makedirs(self.album_storage_path, exist_ok=True)
                self.worker_logger.info(f"Created storage directory: {self.album_storage_path}")
            except OSError as e:
                error_msg = f"Cannot create storage: {e}"
                self.worker_logger.error(error_msg)
                self.finished.emit({'added': 0, 'skipped': 0, 'errors': [error_msg]})
                return

        for idx, record in enumerate(self.records):
            if self.cancelled:
                self.worker_logger.info("Operation cancelled by user")
                break

            file_hash = record.get('file_hash')
            archive_path = record.get('archive_path')

            if not archive_path:
                error_msg = f"File {idx+1}: No archive path"
                self.worker_logger.error(f"  {error_msg}")
                errors.append(error_msg)
                continue

            filename = os.path.basename(archive_path)
            self.progress.emit(idx + 1, len(self.records), filename)

            self.worker_logger.info("-" * 60)
            self.worker_logger.info(f"Processing file {idx+1}/{len(self.records)}: {filename}")
            self.worker_logger.info(f"  Hash: {file_hash[:16]}...")
            self.worker_logger.info(f"  Source: {archive_path}")

            # Check if already in album
            if album_manager.is_photo_in_album(self.album_id, file_hash):
                self.worker_logger.info(f"  Skipped: Already in album")
                skipped_count += 1
                continue

            # Verify source file exists
            if not os.path.exists(archive_path):
                error_msg = f"{filename}: Source file not found"
                self.worker_logger.error(f"  {error_msg}")
                errors.append(error_msg)
                continue

            # Add to album (copies file)
            try:
                album_path = album_manager.add_photo_to_album(
                    self.album_id, file_hash, archive_path
                )
                if album_path:
                    self.worker_logger.info(f"  Added: {os.path.basename(album_path)}")
                    added_count += 1
                else:
                    self.worker_logger.warning(f"  Skipped: Could not add (may already exist)")
                    skipped_count += 1

            except Exception as e:
                error_msg = f"{filename}: {str(e)}"
                self.worker_logger.error(f"  Failed: {e}")
                errors.append(error_msg)

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("ADD TO ALBUM COMPLETE")
        self.worker_logger.info(f"  Added: {added_count}")
        self.worker_logger.info(f"  Skipped: {skipped_count}")
        self.worker_logger.info(f"  Errors: {len(errors)}")
        self.worker_logger.info("=" * 80)

        self.finished.emit({
            'added': added_count,
            'skipped': skipped_count,
            'errors': errors
        })


class RemoveFromAlbumWorker(QThread):
    """Background worker for removing photos from an album."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)  # {'removed': int, 'errors': list}

    def __init__(self, album_id: int, file_hashes: list, db_path: str,
                 delete_files: bool = True, worker_logger=None):
        """
        Initialize remove from album worker.

        Args:
            album_id: Album ID
            file_hashes: List of file hashes to remove
            db_path: Database path
            delete_files: Whether to delete physical files
            worker_logger: Logger instance (optional)
        """
        super().__init__()
        self.album_id = album_id
        self.file_hashes = file_hashes
        self.db_path = db_path
        self.delete_files = delete_files
        self.worker_logger = worker_logger or logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Remove from album operation cancelled by user")

    def run(self):
        """Execute removal operation."""
        from album_manager import AlbumManager

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING REMOVE FROM ALBUM PROCESS")
        self.worker_logger.info(f"Album ID: {self.album_id}")
        self.worker_logger.info(f"Files to remove: {len(self.file_hashes)}")
        self.worker_logger.info(f"Delete files: {self.delete_files}")
        self.worker_logger.info("=" * 80)

        removed_count = 0
        errors = []

        # Initialize album manager
        try:
            album_manager = AlbumManager(self.db_path)
        except Exception as e:
            error_msg = f"Failed to initialize: {e}"
            self.worker_logger.error(error_msg, exc_info=True)
            self.finished.emit({'removed': 0, 'errors': [error_msg]})
            return

        for idx, file_hash in enumerate(self.file_hashes):
            if self.cancelled:
                self.worker_logger.info("Operation cancelled by user")
                break

            self.progress.emit(idx + 1, len(self.file_hashes), file_hash[:16] + "...")

            self.worker_logger.info(f"Removing file {idx+1}/{len(self.file_hashes)}: {file_hash[:16]}...")

            try:
                if album_manager.remove_photo_from_album(
                    self.album_id, file_hash, delete_file=self.delete_files
                ):
                    removed_count += 1
                    self.worker_logger.info(f"  Removed successfully")
                else:
                    self.worker_logger.warning(f"  Not found in album")

            except Exception as e:
                error_msg = f"{file_hash[:16]}...: {str(e)}"
                self.worker_logger.error(f"  Failed: {e}")
                errors.append(error_msg)

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("REMOVE FROM ALBUM COMPLETE")
        self.worker_logger.info(f"  Removed: {removed_count}")
        self.worker_logger.info(f"  Errors: {len(errors)}")
        self.worker_logger.info("=" * 80)

        self.finished.emit({
            'removed': removed_count,
            'errors': errors
        })


class SyncAlbumDeletionWorker(QThread):
    """Background worker for syncing archive deletion to albums."""

    progress = Signal(int, int, str)  # current, total, album_name
    finished = Signal(dict)  # {'albums_synced': list, 'files_removed': int}

    def __init__(self, file_hashes: list, db_path: str, worker_logger=None):
        """
        Initialize sync worker.

        Args:
            file_hashes: List of file hashes that were deleted from archive
            db_path: Database path
            worker_logger: Logger instance (optional)
        """
        super().__init__()
        self.file_hashes = file_hashes
        self.db_path = db_path
        self.worker_logger = worker_logger or logger

    def run(self):
        """
        Sync deletion to all albums with sync_deletions=1.

        Called automatically after DeleteWorker completes.
        """
        from album_manager import AlbumManager

        self.worker_logger.info("-" * 60)
        self.worker_logger.info("SYNCING DELETIONS TO ALBUMS")
        self.worker_logger.info(f"Files to sync: {len(self.file_hashes)}")

        total_albums_synced = []
        total_files_removed = 0

        try:
            album_manager = AlbumManager(self.db_path)

            for idx, file_hash in enumerate(self.file_hashes):
                self.progress.emit(idx + 1, len(self.file_hashes), file_hash[:16] + "...")

                result = album_manager.sync_deletion_to_albums(file_hash)

                if result.get('albums_updated'):
                    total_albums_synced.extend(result['albums_updated'])
                    total_files_removed += result.get('files_removed', 0)

        except Exception as e:
            self.worker_logger.error(f"Failed to sync deletions: {e}")

        # Remove duplicates from album list
        unique_albums = list(set(total_albums_synced))

        if unique_albums:
            self.worker_logger.info(f"  Albums updated: {', '.join(unique_albums)}")
            self.worker_logger.info(f"  Files removed: {total_files_removed}")
        else:
            self.worker_logger.info("  No album photos affected")

        self.worker_logger.info("-" * 60)

        self.finished.emit({
            'albums_synced': unique_albums,
            'files_removed': total_files_removed
        })
