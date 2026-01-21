"""
Content Hash Backfill Worker

Background worker for calculating content hashes on existing archive files
that don't have content hashes yet.
"""

from PySide6.QtCore import QThread, Signal
import logging
import os

import DuplicateFileDetection
from DuplicateFileDetection import hash_image_content, PhotoDatabase

logger = logging.getLogger(__name__)


class ContentHashBackfillWorker(QThread):
    """
    Worker thread for backfilling content hashes on existing archive files.

    Processes files in batches, calculating and storing content hashes for
    files that don't have them yet. Supports graceful cancellation.
    """

    # Signals
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)  # status message
    completed = Signal(dict)  # results dictionary
    error_occurred = Signal(str)  # error message

    def __init__(self, database_path: str, batch_size: int = 100):
        """
        Initialize the backfill worker.

        Args:
            database_path: Path to the SQLite database
            batch_size: Number of files to process before committing
        """
        super().__init__()
        self.database_path = database_path
        self.batch_size = batch_size
        self._should_stop = False

    def stop(self):
        """Request the worker to stop gracefully."""
        self._should_stop = True
        logger.info("Content hash backfill stop requested")

    def run(self):
        """Main processing loop."""
        try:
            self.status_update.emit("Initializing content hash backfill...")

            # Get count of files needing processing
            with PhotoDatabase(self.database_path) as db:
                total_files = db.count_files_without_content_hash()

            if total_files == 0:
                self.status_update.emit("All files already have content hashes")
                self.completed.emit({
                    'status': 'completed',
                    'files_processed': 0,
                    'files_updated': 0,
                    'files_skipped': 0,
                    'files_failed': 0,
                    'was_cancelled': False
                })
                return

            self.status_update.emit(f"Found {total_files} files without content hashes")

            files_processed = 0
            files_updated = 0
            files_skipped = 0
            files_failed = 0
            discovered_duplicates = []  # List of (file_path, duplicate_of_path) tuples
            was_cancelled = False

            while not self._should_stop:
                # Get next batch of files
                with PhotoDatabase(self.database_path) as db:
                    files = db.get_files_without_content_hash(limit=self.batch_size)

                if not files:
                    # No more files to process
                    break

                for file_record in files:
                    if self._should_stop:
                        was_cancelled = True
                        self.status_update.emit("Backfill cancelled by user")
                        break

                    file_hash = file_record['file_hash']
                    file_path = file_record['file_name']  # This is the archive path

                    # Update progress
                    files_processed += 1
                    filename = os.path.basename(file_path) if file_path else file_hash[:12]
                    self.progress_update.emit(files_processed, total_files, filename)

                    # Check if file exists
                    if not file_path or not os.path.exists(file_path):
                        logger.debug(f"File not found, skipping: {file_path}")
                        files_skipped += 1
                        continue

                    try:
                        # Calculate content hash
                        content_hash = hash_image_content(file_path)

                        if content_hash:
                            with PhotoDatabase(self.database_path) as db:
                                # Check if this content hash already exists in another file
                                if db.has_content_hash(content_hash):
                                    existing_files = db.get_files_by_content_hash(content_hash)
                                    if existing_files:
                                        # Found a content duplicate!
                                        duplicate_of = existing_files[0]['file_name']
                                        discovered_duplicates.append({
                                            'file_path': file_path,
                                            'file_hash': file_hash,
                                            'content_hash': content_hash,
                                            'duplicate_of_path': duplicate_of,
                                            'duplicate_of_hash': existing_files[0]['file_hash']
                                        })
                                        logger.info(f"Discovered content duplicate: {filename} matches {os.path.basename(duplicate_of)}")

                                # Update database with content hash
                                db.update_content_hash(file_hash, content_hash)
                                db.commit()
                            files_updated += 1
                            logger.debug(f"Updated content hash for {filename}")
                        else:
                            # Video or unreadable file
                            files_skipped += 1
                            logger.debug(f"No content hash (video or unreadable): {filename}")

                    except Exception as e:
                        files_failed += 1
                        logger.warning(f"Failed to process {file_path}: {e}")

                if was_cancelled:
                    break

            # Compile results
            status = 'cancelled' if was_cancelled else 'completed'
            dup_count = len(discovered_duplicates)
            self.status_update.emit(f"Backfill {status}: {files_updated} files updated, {dup_count} duplicates discovered")

            self.completed.emit({
                'status': status,
                'files_processed': files_processed,
                'files_updated': files_updated,
                'files_skipped': files_skipped,
                'files_failed': files_failed,
                'discovered_duplicates': discovered_duplicates,
                'discovered_duplicates_count': dup_count,
                'was_cancelled': was_cancelled
            })

        except Exception as e:
            logger.error(f"Content hash backfill failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
            self.completed.emit({
                'status': 'failed',
                'files_processed': 0,
                'files_updated': 0,
                'files_skipped': 0,
                'files_failed': 0,
                'was_cancelled': False,
                'error': str(e)
            })
