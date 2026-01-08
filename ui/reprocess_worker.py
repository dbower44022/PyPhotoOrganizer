"""
Reprocess Worker for PyPhotoOrganizer GUI

Background worker thread for reprocessing files from import history.
Allows users to retry failed or skipped files with current settings.
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
import time
from datetime import datetime as dt_datetime
from typing import List, Dict, Any, Optional

import DuplicateFileDetection
from database_metadata import DatabaseMetadata
from organization_template import OrganizationTemplate
from filename_template import FilenameTemplate
from audit_manager import AuditManager
import utils

logger = logging.getLogger(__name__)


class ReprocessWorker(QThread):
    """Worker thread for reprocessing files from import history."""

    # Progress signals
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)  # status message
    completed = Signal(dict)  # results dictionary
    error_occurred = Signal(str)  # error message

    def __init__(self, database_path: str, file_records: List[Dict[str, Any]],
                 archive_location: str, organization_template: str,
                 copy_mode: bool = True, audit_manager: Optional[AuditManager] = None):
        """
        Initialize reprocess worker.

        Args:
            database_path: Path to SQLite database
            file_records: List of file log records to reprocess
            archive_location: Archive base directory
            organization_template: Organization template string
            copy_mode: True for copy, False for move
            audit_manager: Optional AuditManager for logging operations
        """
        super().__init__()
        self.database_path = database_path
        self.file_records = file_records
        self.archive_location = archive_location
        self.organization_template = organization_template
        self.copy_mode = copy_mode
        self.audit_manager = audit_manager
        self._should_stop = False

        # Session tracking
        self.session_id = None

        # Results tracking
        self.successful = []
        self.failed = []
        self.skipped = []

    def run(self):
        """Main processing loop (runs in background thread)."""
        final_status = 'completed'
        error_summary = None

        try:
            total = len(self.file_records)
            self.status_update.emit(f"Reprocessing {total} file(s)...")

            # Start audit session if audit manager available
            if self.audit_manager:
                try:
                    # Extract unique source paths for session metadata
                    source_paths = list(set([r.get('source_path', '') for r in self.file_records if r.get('source_path')]))
                    source_dirs = list(set([os.path.dirname(p) for p in source_paths]))

                    operation_mode = 'reprocess_copy' if self.copy_mode else 'reprocess_move'

                    self.session_id = self.audit_manager.start_session(
                        source_directories=source_dirs,
                        destination_directory=self.archive_location,
                        organization_template=self.organization_template,
                        operation_mode=operation_mode
                    )
                    logger.info(f"Started reprocess audit session: {self.session_id}")
                except Exception as e:
                    logger.error(f"Failed to start audit session: {e}", exc_info=True)
                    self.session_id = None

            # Load existing database hashes
            with DuplicateFileDetection.PhotoDatabase(self.database_path) as db:
                existing_hashes = db.get_all_hashes()
                historical_hashes = db.get_all_historical_hashes()

            # Get database metadata for settings
            db_metadata = DatabaseMetadata(self.database_path)
            rename_enabled = db_metadata.is_file_rename_enabled()
            filename_template = db_metadata.get_filename_template() if rename_enabled else None

            file_counter = 0

            for idx, record in enumerate(self.file_records, 1):
                if self._should_stop:
                    final_status = 'cancelled'
                    self.status_update.emit("Processing cancelled by user")
                    break

                source_path = record.get('source_path', '')
                filename = os.path.basename(source_path)

                self.progress_update.emit(idx, total, filename)
                self.status_update.emit(f"Processing {filename}...")

                # Track timing for this file
                file_start_time = time.time()

                # Verify source file exists
                if not source_path or not os.path.exists(source_path):
                    error_msg = f"Source file not found: {source_path}"
                    logger.warning(error_msg)

                    # Log to audit
                    if self.audit_manager and self.session_id:
                        self.audit_manager.log_file_operation(
                            session_id=self.session_id,
                            source_path=source_path,
                            operation='reprocess',
                            status='failed',
                            error_code='FileNotFoundError',
                            error_message=error_msg,
                            duration_ms=int((time.time() - file_start_time) * 1000)
                        )

                    self.failed.append({
                        'filename': filename,
                        'source_path': source_path,
                        'reason': 'Source file not found'
                    })
                    continue

                try:
                    # Hash the file
                    logger.info(f"Hashing file: {source_path}")
                    file_hash = DuplicateFileDetection.hash_file(source_path)

                    # Check if it's a duplicate (check both current and historical hashes)
                    is_duplicate = (file_hash in existing_hashes or
                                   file_hash in historical_hashes)

                    if is_duplicate:
                        logger.info(f"File is a duplicate (hash: {file_hash[:12]}...), skipping")

                        # Log to audit
                        if self.audit_manager and self.session_id:
                            self.audit_manager.log_file_operation(
                                session_id=self.session_id,
                                source_path=source_path,
                                operation='duplicate detected',
                                status='skipped',
                                file_hash=file_hash,
                                file_size=os.path.getsize(source_path) if os.path.exists(source_path) else None,
                                duplicate_of_hash=file_hash,
                                duration_ms=int((time.time() - file_start_time) * 1000)
                            )

                        self.skipped.append({
                            'filename': filename,
                            'source_path': source_path,
                            'reason': 'Duplicate of existing file'
                        })
                        continue

                    # Get file creation date
                    year, month, day, date_source, is_reliable = DuplicateFileDetection.get_creation_date(source_path)

                    # Convert to datetime for template parsing
                    try:
                        file_date = dt_datetime(int(year), int(month), int(day))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Invalid date {year}/{month}/{day}, using current date: {e}")
                        file_date = dt_datetime.now()
                        year, month, day = str(file_date.year), f"{file_date.month:02d}", f"{file_date.day:02d}"

                    # Determine destination using organization template
                    folder_path = OrganizationTemplate.parse(self.organization_template, file_date)
                    destination_folder = os.path.join(self.archive_location, folder_path)

                    # Ensure destination folder exists
                    utils.ensure_directory_exists(destination_folder)

                    # Increment counter for filename template
                    file_counter += 1

                    # Apply filename template if enabled
                    if rename_enabled and filename_template:
                        try:
                            new_filename = FilenameTemplate.parse(
                                filename_template,
                                file_date,
                                source_path,
                                counter=file_counter
                            )
                            logger.info(f"Filename template applied: {filename} → {new_filename}")
                        except Exception as e:
                            logger.error(f"Failed to parse filename template, using original: {e}")
                            new_filename = filename
                    else:
                        new_filename = filename

                    # Build target path
                    target_path = os.path.join(destination_folder, new_filename)

                    # Handle filename collision
                    if os.path.exists(target_path):
                        target_path = utils.get_unique_filename(target_path)
                        logger.info(f"File exists, using unique name: {os.path.basename(target_path)}")

                    # Copy or move file
                    operation = "copy" if self.copy_mode else "move"
                    logger.info(f"{operation.title()}ing file to: {target_path}")

                    if self.copy_mode:
                        shutil.copy2(source_path, target_path)
                    else:
                        shutil.move(source_path, target_path)

                    # Verify file was copied/moved successfully
                    if not os.path.exists(target_path):
                        raise Exception(f"File {operation} failed - destination file not found")

                    # Add to database
                    with DuplicateFileDetection.PhotoDatabase(self.database_path) as db:
                        # Calculate partial hash if needed
                        partial_hash = None
                        partial_hash_bytes = None
                        file_size = os.path.getsize(target_path)
                        if file_size >= 1048576:  # 1MB threshold
                            partial_hash_bytes = 16384
                            partial_hash = DuplicateFileDetection.hash_file_partial(target_path, partial_hash_bytes)

                        # Create datetime string in YYYY-MM-DD format
                        create_datetime = f"{year}-{month}-{day}"

                        db.insert_unique_photo(
                            file_hash=file_hash,
                            file_path=target_path,
                            create_datetime=create_datetime,
                            create_year=year,
                            create_month=month,
                            create_day=day,
                            partial_hash=partial_hash,
                            partial_hash_bytes=partial_hash_bytes,
                            file_size=file_size
                        )

                        # Note: Hash history is automatically created by insert_unique_photo()

                    # Log to audit
                    if self.audit_manager and self.session_id:
                        self.audit_manager.log_file_operation(
                            session_id=self.session_id,
                            source_path=source_path,
                            destination_path=target_path,
                            operation='reprocess',
                            status='success',
                            file_hash=file_hash,
                            partial_hash=partial_hash,
                            file_size=file_size,
                            creation_date=create_datetime,
                            date_source=date_source,
                            date_reliable=is_reliable,
                            duration_ms=int((time.time() - file_start_time) * 1000)
                        )

                    logger.info(f"✓ Successfully reprocessed: {filename}")
                    self.successful.append({
                        'filename': filename,
                        'source_path': source_path,
                        'destination_path': target_path,
                        'operation': operation
                    })

                except Exception as e:
                    error_msg = f"Failed to reprocess {filename}: {str(e)}"
                    logger.error(error_msg, exc_info=True)

                    # Log to audit
                    if self.audit_manager and self.session_id:
                        import traceback
                        self.audit_manager.log_file_operation(
                            session_id=self.session_id,
                            source_path=source_path,
                            operation='reprocess',
                            status='failed',
                            error_code=type(e).__name__,
                            error_message=str(e),
                            error_traceback=traceback.format_exc(),
                            duration_ms=int((time.time() - file_start_time) * 1000)
                        )

                    self.failed.append({
                        'filename': filename,
                        'source_path': source_path,
                        'reason': str(e)
                    })

            # Compile results
            results = {
                'total': total,
                'successful': len(self.successful),
                'failed': len(self.failed),
                'skipped': len(self.skipped),
                'successful_files': self.successful,
                'failed_files': self.failed,
                'skipped_files': self.skipped,
                'session_id': self.session_id
            }

            # End audit session if started
            if self.audit_manager and self.session_id:
                try:
                    self.audit_manager.end_session(
                        session_id=self.session_id,
                        status=final_status,
                        stats={
                            'total_files_processed': len(self.successful) + len(self.failed) + len(self.skipped),
                            'total_unique_files': len(self.successful),
                            'total_duplicates': len(self.skipped),
                            'total_errors': len(self.failed)
                        }
                    )
                    logger.info(f"Ended reprocess audit session: {self.session_id}")
                except Exception as e:
                    logger.error(f"Failed to end audit session: {e}", exc_info=True)

            self.status_update.emit("Reprocessing complete")
            self.completed.emit(results)

        except Exception as e:
            final_status = 'failed'
            error_msg = f"Reprocessing failed: {str(e)}"
            logger.error(error_msg, exc_info=True)

            # End audit session with error status
            if self.audit_manager and self.session_id:
                try:
                    import traceback
                    error_summary = {'exception': str(e), 'traceback': traceback.format_exc()}
                    self.audit_manager.end_session(
                        session_id=self.session_id,
                        status='failed',
                        stats={},
                        error_summary=error_summary
                    )
                except Exception as cleanup_error:
                    logger.error(f"Failed to end audit session during cleanup: {cleanup_error}", exc_info=True)

            self.error_occurred.emit(error_msg)

    def stop(self):
        """Request worker to stop gracefully."""
        self._should_stop = True
        logger.info("Stop requested for reprocess worker")
