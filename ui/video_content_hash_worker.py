"""
Video Content Hash Backfill Worker

Background worker for calculating video content hashes on existing archive videos
that don't have video content hashes yet.
"""

from PySide6.QtCore import QThread, Signal
import logging
import os

from DuplicateFileDetection import PhotoDatabase
from hashing import hash_video_content

logger = logging.getLogger(__name__)


class VideoContentHashBackfillWorker(QThread):
    """
    Worker thread for backfilling video content hashes on existing archive videos.

    Processes videos in batches, calculating and storing video content hashes for
    videos that don't have them yet. Supports graceful cancellation.
    """

    # Signals
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)  # status message
    completed = Signal(dict)  # results dictionary
    error_occurred = Signal(str)  # error message

    def __init__(self, database_path: str, batch_size: int = 50):
        """
        Initialize the backfill worker.

        Args:
            database_path: Path to the SQLite database
            batch_size: Number of videos to process before committing (default 50,
                       lower than images due to higher processing cost)
        """
        super().__init__()
        self.database_path = database_path
        self.batch_size = batch_size
        self._should_stop = False

    def stop(self):
        """Request the worker to stop gracefully."""
        self._should_stop = True
        logger.info("Video content hash backfill stop requested")

    def run(self):
        """Main processing loop."""
        try:
            self.status_update.emit("Initializing video content hash backfill...")

            # Get count of videos needing processing
            with PhotoDatabase(self.database_path) as db:
                total_videos = db.count_videos_without_content_hash()

            if total_videos == 0:
                self.status_update.emit("All videos already have content hashes")
                self.completed.emit({
                    'status': 'completed',
                    'files_processed': 0,
                    'files_updated': 0,
                    'files_skipped': 0,
                    'files_failed': 0,
                    'was_cancelled': False
                })
                return

            self.status_update.emit(f"Found {total_videos} videos without content hashes")

            files_processed = 0
            files_updated = 0
            files_skipped = 0
            files_failed = 0
            discovered_duplicates = []  # List of duplicate info dicts
            was_cancelled = False

            while not self._should_stop:
                # Get next batch of videos
                with PhotoDatabase(self.database_path) as db:
                    videos = db.get_videos_without_content_hash(limit=self.batch_size)

                if not videos:
                    # No more videos to process
                    break

                for video_record in videos:
                    if self._should_stop:
                        was_cancelled = True
                        self.status_update.emit("Backfill cancelled by user")
                        break

                    file_hash = video_record['file_hash']
                    file_path = video_record['file_name']  # This is the archive path

                    # Update progress
                    files_processed += 1
                    filename = os.path.basename(file_path) if file_path else file_hash[:12]
                    self.progress_update.emit(files_processed, total_videos, filename)

                    # Check if file exists
                    if not file_path or not os.path.exists(file_path):
                        logger.debug(f"Video not found, skipping: {file_path}")
                        files_skipped += 1
                        continue

                    try:
                        # Calculate video content hash
                        video_content_hash = hash_video_content(file_path)

                        if video_content_hash:
                            with PhotoDatabase(self.database_path) as db:
                                # Check if this video content hash already exists in another file
                                if db.has_video_content_hash(video_content_hash):
                                    existing_videos = db.get_files_by_video_content_hash(video_content_hash)
                                    if existing_videos:
                                        # Found a video content duplicate!
                                        duplicate_of = existing_videos[0]['file_name']
                                        discovered_duplicates.append({
                                            'file_path': file_path,
                                            'file_hash': file_hash,
                                            'video_content_hash': video_content_hash,
                                            'duplicate_of_path': duplicate_of,
                                            'duplicate_of_hash': existing_videos[0]['file_hash']
                                        })
                                        logger.info(f"Discovered video content duplicate: {filename} matches {os.path.basename(duplicate_of)}")

                                # Update database with video content hash
                                db.update_video_content_hash(file_hash, video_content_hash)
                                db.commit()
                            files_updated += 1
                            logger.debug(f"Updated video content hash for {filename}")
                        else:
                            # Failed to extract frames or hash
                            files_skipped += 1
                            logger.debug(f"No video content hash (extraction failed): {filename}")

                    except Exception as e:
                        files_failed += 1
                        logger.warning(f"Failed to process video {file_path}: {e}")

                if was_cancelled:
                    break

            # Compile results
            status = 'cancelled' if was_cancelled else 'completed'
            dup_count = len(discovered_duplicates)
            self.status_update.emit(f"Backfill {status}: {files_updated} videos updated, {dup_count} duplicates discovered")

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
            logger.error(f"Video content hash backfill failed: {e}", exc_info=True)
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
