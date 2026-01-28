"""
Import Processor for Auto-Import Service.

Processes detected files by integrating with the existing PyPhotoOrganizer import logic.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from auto_import.config import ServiceConfig

logger = logging.getLogger(__name__)


@dataclass
class ImportedFile:
    """Information about an imported file."""
    source_path: str
    dest_path: str
    file_hash: str
    file_size: int
    date_taken: Optional[datetime] = None
    album_id: Optional[int] = None


@dataclass
class ImportResult:
    """Result of an import run."""
    start_time: datetime
    end_time: datetime
    files_scanned: int
    files_imported: int
    files_duplicate: int
    files_filtered: int
    files_failed: int
    bytes_processed: int
    errors: List[str] = field(default_factory=list)
    imported_files: List[ImportedFile] = field(default_factory=list)
    watch_directories_scanned: int = 0

    @property
    def duration_seconds(self) -> float:
        """Get duration of import run in seconds."""
        return (self.end_time - self.start_time).total_seconds()

    @property
    def success_rate(self) -> float:
        """Get success rate as percentage."""
        total = self.files_imported + self.files_failed
        if total == 0:
            return 100.0
        return (self.files_imported / total) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for reporting."""
        return {
            'start_time': self.start_time.isoformat(),
            'end_time': self.end_time.isoformat(),
            'duration_seconds': self.duration_seconds,
            'files_scanned': self.files_scanned,
            'files_imported': self.files_imported,
            'files_duplicate': self.files_duplicate,
            'files_filtered': self.files_filtered,
            'files_failed': self.files_failed,
            'bytes_processed': self.bytes_processed,
            'success_rate': self.success_rate,
            'errors': self.errors,
            'imported_files': [
                {
                    'source': f.source_path,
                    'dest': f.dest_path,
                    'size': f.file_size,
                }
                for f in self.imported_files
            ],
        }


class ImportProcessor:
    """
    Processes files for import using PyPhotoOrganizer's existing logic.

    Integrates with the main application's database and import functions.
    """

    def __init__(self, config: ServiceConfig):
        """
        Initialize ImportProcessor.

        Args:
            config: Service configuration
        """
        self.config = config
        self._database = None
        self._stop_requested = False

    def _get_database(self):
        """Get or create database connection."""
        if self._database is None:
            from DuplicateFileDetection import PhotoDatabase
            self._database = PhotoDatabase(self.config.database_path)
        return self._database

    def process_files(self, files: List[Any]) -> ImportResult:
        """
        Process a list of files for import.

        Args:
            files: List of NewFile objects from watcher

        Returns:
            ImportResult with processing statistics
        """
        from DuplicateFileDetection import (
            PhotoDatabase,
            find_duplicates,
            calculate_file_hash,
        )
        from main import organize_files
        from database_metadata import DatabaseMetadata

        start_time = datetime.now()
        self._stop_requested = False

        result = ImportResult(
            start_time=start_time,
            end_time=start_time,
            files_scanned=len(files),
            files_imported=0,
            files_duplicate=0,
            files_filtered=0,
            files_failed=0,
            bytes_processed=0,
            errors=[],
            imported_files=[],
        )

        if not files:
            result.end_time = datetime.now()
            return result

        try:
            # Get database and metadata
            db = self._get_database()
            metadata = DatabaseMetadata(self.config.database_path)
            archive_path = metadata.get_archive_path()

            if not archive_path:
                result.errors.append("Archive path not configured in database")
                result.end_time = datetime.now()
                return result

            # Get organization settings
            org_template = metadata.get_organization_template() or "{year}/{month}/{day}"

            # Check limits
            max_files = self.config.processing.max_files_per_run
            max_bytes = self.config.processing.max_bytes_per_run

            bytes_processed = 0
            files_processed = 0

            for new_file in files:
                if self._stop_requested:
                    logger.info("Stop requested, aborting processing")
                    break

                # Check limits
                if max_files > 0 and files_processed >= max_files:
                    logger.info(f"Reached max files limit ({max_files})")
                    break

                if max_bytes > 0 and bytes_processed >= max_bytes:
                    logger.info(f"Reached max bytes limit ({max_bytes})")
                    break

                try:
                    file_result = self._process_single_file(
                        new_file,
                        db,
                        archive_path,
                        org_template,
                    )

                    if file_result['status'] == 'imported':
                        result.files_imported += 1
                        result.imported_files.append(ImportedFile(
                            source_path=new_file.path,
                            dest_path=file_result.get('dest_path', ''),
                            file_hash=file_result.get('hash', ''),
                            file_size=new_file.size,
                            album_id=new_file.watch_config.album_id,
                        ))
                    elif file_result['status'] == 'duplicate':
                        result.files_duplicate += 1
                    elif file_result['status'] == 'filtered':
                        result.files_filtered += 1
                    else:
                        result.files_failed += 1
                        if file_result.get('error'):
                            result.errors.append(
                                f"{os.path.basename(new_file.path)}: {file_result['error']}"
                            )

                    bytes_processed += new_file.size
                    files_processed += 1

                except Exception as e:
                    logger.error(f"Error processing {new_file.path}: {e}")
                    result.files_failed += 1
                    result.errors.append(f"{os.path.basename(new_file.path)}: {str(e)}")

            result.bytes_processed = bytes_processed

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            result.errors.append(f"Processing error: {str(e)}")

        result.end_time = datetime.now()
        return result

    def _process_single_file(
        self,
        new_file: Any,
        db: Any,
        archive_path: str,
        org_template: str,
    ) -> Dict[str, Any]:
        """
        Process a single file.

        Args:
            new_file: NewFile object
            db: PhotoDatabase instance
            archive_path: Destination archive path
            org_template: Organization template

        Returns:
            Dict with status and details
        """
        from DuplicateFileDetection import (
            calculate_file_hash,
            get_creation_date,
        )
        from photo_filter import PhotoFilter

        file_path = new_file.path

        # Check if file still exists
        if not os.path.exists(file_path):
            return {'status': 'failed', 'error': 'File no longer exists'}

        # Apply photo filter (skip for videos)
        ext = os.path.splitext(file_path)[1].lower()
        video_extensions = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.wmv', '.3gp'}

        if ext not in video_extensions:
            photo_filter = PhotoFilter()
            if not photo_filter.should_process_file(file_path):
                return {'status': 'filtered', 'reason': 'Did not pass photo filter'}

        # Calculate hash
        file_hash = calculate_file_hash(file_path)
        if not file_hash:
            return {'status': 'failed', 'error': 'Could not calculate hash'}

        # Check for duplicate
        existing = db.get_photo_by_hash(file_hash)
        if existing:
            return {'status': 'duplicate', 'existing_path': existing.get('dest_file_path')}

        # Get creation date
        date_info = get_creation_date(file_path)
        creation_date = date_info.get('date') if date_info else None

        if not creation_date:
            # Fall back to file modification time
            creation_date = datetime.fromtimestamp(os.path.getmtime(file_path))

        # Build destination path
        dest_folder = self._build_dest_folder(archive_path, org_template, creation_date)
        os.makedirs(dest_folder, exist_ok=True)

        dest_filename = os.path.basename(file_path)
        dest_path = os.path.join(dest_folder, dest_filename)

        # Handle name collision
        dest_path = self._get_unique_path(dest_path)

        # Copy or move file
        try:
            if self.config.processing.copy_mode:
                import shutil
                shutil.copy2(file_path, dest_path)
            else:
                import shutil
                shutil.move(file_path, dest_path)

        except Exception as e:
            return {'status': 'failed', 'error': f'Copy/move failed: {e}'}

        # Add to database
        try:
            db.insert_unique_photo(
                file_hash=file_hash,
                source_file_path=file_path,
                dest_file_path=dest_path,
                date_info=date_info,
            )

            # Add to album if configured
            album_id = new_file.watch_config.album_id
            if album_id:
                self._add_to_album(db, file_hash, album_id)

        except Exception as e:
            logger.error(f"Database insert failed: {e}")
            # File was copied, but DB failed - log but don't delete
            return {
                'status': 'imported',
                'dest_path': dest_path,
                'hash': file_hash,
                'warning': f'Database insert failed: {e}',
            }

        return {
            'status': 'imported',
            'dest_path': dest_path,
            'hash': file_hash,
        }

    def _build_dest_folder(
        self,
        archive_path: str,
        template: str,
        date: datetime,
    ) -> str:
        """Build destination folder from template and date."""
        month_names = [
            'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
            'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
        ]
        month_full_names = [
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ]
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        day_full_names = [
            'Monday', 'Tuesday', 'Wednesday', 'Thursday',
            'Friday', 'Saturday', 'Sunday'
        ]

        folder = template.format(
            year=date.strftime('%Y'),
            month=date.strftime('%m'),
            day=date.strftime('%d'),
            month_name=month_full_names[date.month - 1],
            month_sname=month_names[date.month - 1],
            day_name=day_full_names[date.weekday()],
            day_sname=day_names[date.weekday()],
        )

        return os.path.join(archive_path, folder)

    def _get_unique_path(self, path: str) -> str:
        """Get unique path by adding counter if file exists."""
        if not os.path.exists(path):
            return path

        base, ext = os.path.splitext(path)
        counter = 1

        while os.path.exists(f"{base}_{counter}{ext}"):
            counter += 1

        return f"{base}_{counter}{ext}"

    def _add_to_album(self, db: Any, file_hash: str, album_id: int):
        """Add file to album if not already present."""
        try:
            from album_manager import AlbumManager
            album_manager = AlbumManager(db)
            album_manager.add_photo_to_album(album_id, file_hash)
            logger.debug(f"Added {file_hash[:8]} to album {album_id}")
        except Exception as e:
            logger.warning(f"Failed to add to album: {e}")

    def request_stop(self):
        """Request processing to stop."""
        self._stop_requested = True

    def close(self):
        """Close database connection."""
        if self._database:
            self._database.close()
            self._database = None
