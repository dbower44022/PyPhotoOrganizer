"""
Archive Change Scanner Worker

Background worker for detecting external modifications to archive files by comparing
current content hashes against stored content hashes in the database.

When modifications are detected, the system:
1. Locates the original version from backup or source
2. Copies the original to Prior Revision Archive
3. Creates a revision record linking new hash to old hash
4. Logs to audit trail
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
from typing import Optional, Dict, List
from datetime import datetime

from DuplicateFileDetection import PhotoDatabase, hash_file, hash_image_content
from ui.rotate_worker import generate_prior_revision_path

logger = logging.getLogger(__name__)


class ArchiveChangeScannerWorker(QThread):
    """
    Worker thread for scanning archive files and detecting external modifications.

    Compares current content hashes against stored values to detect when files
    have been modified outside the application (e.g., edited in external software).
    """

    # Signals
    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)  # status message
    file_modified = Signal(dict)  # per-file modification notification
    completed = Signal(dict)  # final results
    error_occurred = Signal(str)  # error message

    def __init__(
        self,
        database_path: str,
        archive_location: str,
        backup_location: Optional[str],
        prior_revision_archive: str,
        scan_folder: Optional[str] = None,
        batch_size: int = 100
    ):
        """
        Initialize the change scanner worker.

        Args:
            database_path: Path to the SQLite database
            archive_location: Base path for the main archive
            backup_location: Path to backup location (for finding originals)
            prior_revision_archive: Path to prior revision archive
            scan_folder: Specific folder to scan (None for full archive)
            batch_size: Number of files to process before committing
        """
        super().__init__()
        self.database_path = database_path
        self.archive_location = archive_location
        self.backup_location = backup_location
        self.prior_revision_archive = prior_revision_archive
        self.scan_folder = scan_folder or archive_location
        self.batch_size = batch_size
        self._should_stop = False

    def stop(self):
        """Request the worker to stop gracefully."""
        self._should_stop = True
        logger.info("Archive change scanner stop requested")

    def run(self):
        """Main processing loop."""
        from audit_manager import AuditManager

        try:
            self.status_update.emit("Initializing archive change scanner...")
            logger.info("=" * 80)
            logger.info("STARTING ARCHIVE CHANGE SCAN")
            logger.info(f"Archive location: {self.archive_location}")
            logger.info(f"Scan folder: {self.scan_folder}")
            logger.info(f"Backup location: {self.backup_location or 'Not configured'}")
            logger.info(f"Prior Revision Archive: {self.prior_revision_archive}")
            logger.info("=" * 80)

            # Count total files to scan
            with PhotoDatabase(self.database_path) as db:
                total_files = db.count_archive_files_for_change_scan(self.scan_folder)

            if total_files == 0:
                self.status_update.emit("No files with content hashes found to scan")
                self.completed.emit({
                    'status': 'completed',
                    'total_scanned': 0,
                    'unchanged': 0,
                    'modifications_detected': 0,
                    'revisions_created': 0,
                    'originals_from_backup': 0,
                    'originals_from_source': 0,
                    'originals_not_found': 0,
                    'errors': 0,
                    'skipped_videos': 0,
                    'skipped_missing': 0,
                    'skipped_no_content_hash': 0,
                    'was_cancelled': False
                })
                return

            self.status_update.emit(f"Found {total_files} files to scan")
            logger.info(f"Total files to scan: {total_files}")

            # Initialize audit manager
            try:
                audit_manager = AuditManager(self.database_path)
                session_id = audit_manager.start_session(
                    operation_mode='archive_change_scan',
                    source_directories=[self.scan_folder],
                    destination_directory=self.archive_location
                )
                logger.info(f"Audit session started: {session_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize audit manager: {e}")
                audit_manager = None
                session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Results tracking
            results = {
                'total_scanned': 0,
                'unchanged': 0,
                'modifications_detected': 0,
                'revisions_created': 0,
                'originals_from_backup': 0,
                'originals_from_source': 0,
                'originals_not_found': 0,
                'errors': 0,
                'skipped_videos': 0,
                'skipped_missing': 0,
                'skipped_no_content_hash': 0,
                'was_cancelled': False,
                'error_details': []
            }

            offset = 0
            files_processed = 0

            while not self._should_stop:
                # Get next batch of files
                with PhotoDatabase(self.database_path) as db:
                    files = db.get_archive_files_for_change_scan(
                        self.scan_folder,
                        limit=self.batch_size,
                        offset=offset
                    )

                if not files:
                    break

                for file_record in files:
                    if self._should_stop:
                        results['was_cancelled'] = True
                        self.status_update.emit("Scan cancelled by user")
                        break

                    files_processed += 1
                    results['total_scanned'] += 1
                    filename = os.path.basename(file_record['file_name']) if file_record['file_name'] else file_record['file_hash'][:12]
                    self.progress_update.emit(files_processed, total_files, filename)

                    try:
                        result = self._process_file(file_record, audit_manager, session_id)

                        if result == 'unchanged':
                            results['unchanged'] += 1
                        elif result == 'modified':
                            results['modifications_detected'] += 1
                        elif result == 'revision_created_backup':
                            results['modifications_detected'] += 1
                            results['revisions_created'] += 1
                            results['originals_from_backup'] += 1
                        elif result == 'revision_created_source':
                            results['modifications_detected'] += 1
                            results['revisions_created'] += 1
                            results['originals_from_source'] += 1
                        elif result == 'revision_created_no_original':
                            results['modifications_detected'] += 1
                            results['revisions_created'] += 1
                            results['originals_not_found'] += 1
                        elif result == 'skipped_video':
                            results['skipped_videos'] += 1
                        elif result == 'skipped_missing':
                            results['skipped_missing'] += 1
                        elif result == 'skipped_no_hash':
                            results['skipped_no_content_hash'] += 1
                        elif result.startswith('error:'):
                            results['errors'] += 1
                            results['error_details'].append(result[6:])

                    except Exception as e:
                        results['errors'] += 1
                        error_msg = f"{filename}: {str(e)}"
                        results['error_details'].append(error_msg)
                        logger.error(f"Error processing {filename}: {e}", exc_info=True)

                if results['was_cancelled']:
                    break

                offset += len(files)

            # End audit session
            if audit_manager:
                try:
                    status = 'cancelled' if results['was_cancelled'] else 'completed'
                    if results['errors'] > 0:
                        status = 'completed_with_errors'
                    audit_manager.end_session(
                        session_id=session_id,
                        status=status,
                        stats={
                            'total_files_processed': results['total_scanned'],
                            'modifications_detected': results['modifications_detected'],
                            'revisions_created': results['revisions_created'],
                            'total_errors': results['errors']
                        }
                    )
                    logger.info(f"Audit session ended: {session_id}")
                except Exception as e:
                    logger.warning(f"Failed to end audit session: {e}")

            # Final status
            status_text = 'cancelled' if results['was_cancelled'] else 'completed'
            self.status_update.emit(
                f"Scan {status_text}: {results['modifications_detected']} modifications detected, "
                f"{results['revisions_created']} revisions created"
            )

            logger.info("=" * 80)
            logger.info("ARCHIVE CHANGE SCAN COMPLETE")
            logger.info(f"Total scanned: {results['total_scanned']}")
            logger.info(f"Unchanged: {results['unchanged']}")
            logger.info(f"Modifications detected: {results['modifications_detected']}")
            logger.info(f"Revisions created: {results['revisions_created']}")
            logger.info(f"  - From backup: {results['originals_from_backup']}")
            logger.info(f"  - From source: {results['originals_from_source']}")
            logger.info(f"  - Original not found: {results['originals_not_found']}")
            logger.info(f"Errors: {results['errors']}")
            logger.info(f"Skipped (videos): {results['skipped_videos']}")
            logger.info(f"Skipped (missing): {results['skipped_missing']}")
            logger.info(f"Skipped (no content hash): {results['skipped_no_content_hash']}")
            logger.info("=" * 80)

            results['status'] = status_text
            self.completed.emit(results)

        except Exception as e:
            logger.error(f"Archive change scan failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
            self.completed.emit({
                'status': 'failed',
                'total_scanned': 0,
                'unchanged': 0,
                'modifications_detected': 0,
                'revisions_created': 0,
                'originals_from_backup': 0,
                'originals_from_source': 0,
                'originals_not_found': 0,
                'errors': 1,
                'skipped_videos': 0,
                'skipped_missing': 0,
                'skipped_no_content_hash': 0,
                'was_cancelled': False,
                'error': str(e)
            })

    def _process_file(self, file_record: Dict, audit_manager, session_id: str) -> str:
        """
        Process a single file for change detection.

        Args:
            file_record: Database record for the file
            audit_manager: AuditManager instance (may be None)
            session_id: Current audit session ID

        Returns:
            Result string: 'unchanged', 'modified', 'revision_created_backup',
                          'revision_created_source', 'revision_created_no_original',
                          'skipped_video', 'skipped_missing', 'skipped_no_hash',
                          or 'error:message'
        """
        file_hash = file_record['file_hash']
        file_path = file_record['file_name']
        stored_content_hash = file_record.get('content_hash')
        source_path = file_record.get('source_path')
        create_datetime = file_record.get('create_datetime')
        create_year = file_record.get('create_year')
        create_month = file_record.get('create_month')
        create_day = file_record.get('create_day')

        filename = os.path.basename(file_path) if file_path else file_hash[:12]

        # Skip if no content hash stored
        if not stored_content_hash:
            logger.debug(f"Skipping {filename}: no content hash in database")
            return 'skipped_no_hash'

        # Skip if file doesn't exist
        if not file_path or not os.path.exists(file_path):
            logger.debug(f"Skipping {filename}: file not found at {file_path}")
            return 'skipped_missing'

        # Calculate current content hash
        current_content_hash = hash_image_content(file_path)

        # Skip videos (hash_image_content returns None for videos)
        if current_content_hash is None:
            logger.debug(f"Skipping {filename}: video or unreadable image")
            return 'skipped_video'

        # Compare hashes
        if current_content_hash == stored_content_hash:
            logger.debug(f"File unchanged: {filename}")
            return 'unchanged'

        # MISMATCH DETECTED - External modification
        logger.info(f"External modification detected: {filename}")
        logger.info(f"  Stored content hash: {stored_content_hash[:16]}...")
        logger.info(f"  Current content hash: {current_content_hash[:16]}...")

        # Emit modification signal
        self.file_modified.emit({
            'file_path': file_path,
            'file_hash': file_hash,
            'stored_content_hash': stored_content_hash,
            'current_content_hash': current_content_hash
        })

        # Try to find original file
        original_source = None
        original_path = None

        # First, check backup location
        if self.backup_location and os.path.exists(self.backup_location):
            # Try to find file in backup using relative path from archive
            try:
                rel_path = os.path.relpath(file_path, self.archive_location)
                backup_path = os.path.join(self.backup_location, rel_path)
                if os.path.exists(backup_path):
                    original_path = backup_path
                    original_source = 'backup'
                    logger.info(f"  Original found in backup: {backup_path}")
            except ValueError:
                # relpath can fail if paths are on different drives
                pass

        # Second, check source path
        if not original_path and source_path and os.path.exists(source_path):
            original_path = source_path
            original_source = 'source'
            logger.info(f"  Original found at source: {source_path}")

        # Calculate new file hash for the modified file
        new_file_hash = hash_file(file_path)
        new_file_size = os.path.getsize(file_path)

        # If we found the original, preserve it
        if original_path:
            try:
                # Generate path in prior revision archive
                prior_revision_path = generate_prior_revision_path(
                    file_path,
                    file_hash,  # Use original hash for the path
                    self.prior_revision_archive
                )

                # Create directory structure
                prior_dir = os.path.dirname(prior_revision_path)
                os.makedirs(prior_dir, exist_ok=True)

                # Copy original to prior revision archive
                try:
                    shutil.copy2(original_path, prior_revision_path)
                except (PermissionError, OSError) as copy_err:
                    if isinstance(copy_err, OSError) and copy_err.errno != 95:
                        raise
                    shutil.copyfile(original_path, prior_revision_path)

                logger.info(f"  Original preserved to: {prior_revision_path}")

                # Update database - change the original record's file_name to prior revision path
                with PhotoDatabase(self.database_path) as db:
                    cursor = db.get_cursor()
                    cursor.execute("""
                        UPDATE UniquePhotos
                        SET file_name = ?
                        WHERE file_hash = ?
                    """, (prior_revision_path, file_hash))
                    db.commit()

            except Exception as e:
                logger.error(f"  Failed to preserve original: {e}")
                # Continue anyway - we'll create the revision without the original

        # Create revision record for the modified file
        try:
            with PhotoDatabase(self.database_path) as db:
                from DuplicateFileDetection import hash_file_partial

                # Calculate partial hash if needed
                partial_hash = None
                partial_hash_bytes = None
                if new_file_size >= 1048576:  # 1MB threshold
                    partial_hash_bytes = 16384
                    partial_hash = hash_file_partial(file_path, partial_hash_bytes)

                # Create revision record linking new hash to original hash
                success = db.create_revision(
                    new_file_hash=new_file_hash,
                    parent_hash=file_hash,
                    revision_reason='external_modification',
                    file_path=file_path,
                    file_size=new_file_size,
                    create_datetime=create_datetime,
                    create_year=create_year,
                    create_month=create_month,
                    create_day=create_day,
                    partial_hash=partial_hash,
                    partial_hash_bytes=partial_hash_bytes
                )

                if not success:
                    logger.warning(f"  Failed to create revision record (may already exist)")

                # Update content hash for the new revision
                db.update_content_hash(new_file_hash, current_content_hash)
                db.commit()

                logger.info(f"  Created revision: {new_file_hash[:16]}... (parent: {file_hash[:16]}...)")

        except Exception as e:
            logger.error(f"  Failed to create revision record: {e}")
            return f'error:{filename}: {str(e)}'

        # Log to audit trail
        if audit_manager:
            try:
                audit_manager.log_file_operation(
                    session_id=session_id,
                    source_path=file_path,
                    destination_path=file_path,
                    file_hash=new_file_hash,
                    operation='external_modification_detected',
                    status='revision_created' if original_path else 'original_not_found',
                    file_size=new_file_size,
                    creation_date=create_datetime,
                    duplicate_of_hash=file_hash  # Store original hash for reference
                )
            except Exception as e:
                logger.warning(f"  Failed to log to audit trail: {e}")

        # Return appropriate result
        if original_source == 'backup':
            return 'revision_created_backup'
        elif original_source == 'source':
            return 'revision_created_source'
        else:
            return 'revision_created_no_original'
