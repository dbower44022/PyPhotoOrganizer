"""
Bulk Delete Worker

Background worker for scanning reference folder and deleting matching archive files.
Supports two phases: scan (preview) and delete (execution).
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class BulkDeleteWorker(QThread):
    """
    Background worker for bulk delete operations.

    Two-phase operation:
    - Scan phase (execute_delete=False): Hash reference files, match against archive
    - Delete phase (execute_delete=True): Perform soft-delete on confirmed matches
    """

    progress_update = Signal(int, int, str)  # current, total, filename
    status_update = Signal(str)  # status message
    scan_completed = Signal(dict)  # scan results for preview
    delete_completed = Signal(dict)  # final deletion results
    error_occurred = Signal(str)  # error message

    def __init__(self, database_path, reference_folder, delete_vault_path,
                 archive_location, execute_delete=False, files_to_delete=None):
        """
        Initialize bulk delete worker.

        Args:
            database_path: Path to database
            reference_folder: Folder containing reference files to match
            delete_vault_path: Path to Delete Vault directory
            archive_location: Base archive location
            execute_delete: If False, scan only. If True, execute deletion.
            files_to_delete: List of file records to delete (required if execute_delete=True)
        """
        super().__init__()
        self.database_path = database_path
        self.reference_folder = reference_folder
        self.delete_vault_path = delete_vault_path
        self.archive_location = archive_location
        self.execute_delete = execute_delete
        self.files_to_delete = files_to_delete or []
        self._cancelled = False

    def cancel(self):
        """Request cancellation of the operation."""
        self._cancelled = True
        logger.info("Bulk delete operation cancelled by user")

    def run(self):
        """Execute the operation in background thread."""
        try:
            if self.execute_delete:
                self._run_delete_phase()
            else:
                self._run_scan_phase()
        except Exception as e:
            logger.exception(f"Bulk delete worker failed: {e}")
            self.error_occurred.emit(str(e))

    def _run_scan_phase(self):
        """Scan reference folder and find matches in archive."""
        from DuplicateFileDetection import PhotoDatabase, hash_file, hash_file_partial
        import constants

        self.status_update.emit("Scanning reference folder...")

        # Get list of files in reference folder
        reference_files = []
        for root, dirs, files in os.walk(self.reference_folder):
            for filename in files:
                file_path = os.path.join(root, filename)
                reference_files.append(file_path)

        if not reference_files:
            self.scan_completed.emit({
                'status': 'completed',
                'matched_files': [],
                'not_found_files': [],
                'total_reference': 0,
                'total_matched': 0,
                'total_not_found': 0,
                'total_matched_size': 0
            })
            return

        total = len(reference_files)
        matched_files = []
        not_found_files = []
        total_matched_size = 0

        self.status_update.emit(f"Hashing {total} files...")

        with PhotoDatabase(self.database_path) as db:
            for idx, ref_path in enumerate(reference_files):
                if self._cancelled:
                    self.status_update.emit("Scan cancelled")
                    self.scan_completed.emit({
                        'status': 'cancelled',
                        'matched_files': matched_files,
                        'not_found_files': not_found_files,
                        'total_reference': total,
                        'total_matched': len(matched_files),
                        'total_not_found': len(not_found_files),
                        'total_matched_size': total_matched_size
                    })
                    return

                filename = os.path.basename(ref_path)
                self.progress_update.emit(idx + 1, total, filename)

                try:
                    if not os.path.exists(ref_path):
                        not_found_files.append({
                            'reference_path': ref_path,
                            'reason': 'File not accessible'
                        })
                        continue

                    file_size = os.path.getsize(ref_path)

                    # Use partial hash optimization for files >= 1MB
                    if file_size >= constants.PARTIAL_HASH_MIN_FILE_SIZE:
                        partial_hash = hash_file_partial(ref_path)
                        matching_full_hashes = db.has_partial_hash(partial_hash)

                        if not matching_full_hashes:
                            # No partial match, file not in archive
                            not_found_files.append({
                                'reference_path': ref_path,
                                'file_size': file_size,
                                'reason': 'Not in archive'
                            })
                            continue

                        # Partial match found, compute full hash to verify
                        full_hash = hash_file(ref_path)
                    else:
                        # Small file, compute full hash directly
                        full_hash = hash_file(ref_path)

                    # Check if hash exists in archive
                    if db.has_hash(full_hash):
                        archive_path = db.get_file_path_for_hash(full_hash)
                        matched_files.append({
                            'reference_path': ref_path,
                            'archive_path': archive_path,
                            'file_hash': full_hash,
                            'file_size': file_size
                        })
                        total_matched_size += file_size
                    else:
                        not_found_files.append({
                            'reference_path': ref_path,
                            'file_size': file_size,
                            'reason': 'Not in archive'
                        })

                except Exception as e:
                    logger.warning(f"Error processing {ref_path}: {e}")
                    not_found_files.append({
                        'reference_path': ref_path,
                        'reason': f'Error: {str(e)}'
                    })

        self.status_update.emit("Scan complete")
        self.scan_completed.emit({
            'status': 'completed',
            'matched_files': matched_files,
            'not_found_files': not_found_files,
            'total_reference': total,
            'total_matched': len(matched_files),
            'total_not_found': len(not_found_files),
            'total_matched_size': total_matched_size
        })

    def _run_delete_phase(self):
        """Execute deletion of matched files."""
        from database_metadata import DatabaseMetadata
        from DuplicateFileDetection import PhotoDatabase, hash_file
        from audit_manager import AuditManager
        from album_manager import AlbumManager

        if not self.files_to_delete:
            self.delete_completed.emit({
                'status': 'completed',
                'success_count': 0,
                'error_count': 0,
                'errors': [],
                'deleted_hashes': []
            })
            return

        self.status_update.emit("Initializing delete operation...")

        # Initialize database metadata
        try:
            db_metadata = DatabaseMetadata(self.database_path)
            prior_revision_archive = db_metadata.get_prior_revision_archive_location()
        except Exception as e:
            self.error_occurred.emit(f"Failed to initialize database: {e}")
            return

        # Initialize audit manager and create session
        try:
            audit_manager = AuditManager(self.database_path)
            session_id = audit_manager.start_session(
                operation_mode='bulk_delete',
                source_directories=[self.reference_folder],
                destination_directory=self.delete_vault_path
            )
            logger.info(f"Audit session started: {session_id}")
        except Exception as e:
            logger.warning(f"Failed to initialize audit manager: {e}")
            audit_manager = None
            session_id = None

        # Initialize album manager
        try:
            album_manager = AlbumManager(self.database_path)
        except Exception as e:
            logger.warning(f"Failed to initialize album manager: {e}")
            album_manager = None

        total = len(self.files_to_delete)
        success_count = 0
        error_count = 0
        errors = []
        deleted_hashes = []

        for idx, file_record in enumerate(self.files_to_delete):
            if self._cancelled:
                self.status_update.emit("Delete cancelled")
                break

            archive_path = file_record.get('archive_path')
            file_hash = file_record.get('file_hash')
            reference_path = file_record.get('reference_path')
            file_size = file_record.get('file_size', 0)

            if not archive_path:
                errors.append(f"No archive path for file")
                error_count += 1
                continue

            filename = os.path.basename(archive_path)
            self.progress_update.emit(idx + 1, total, filename)

            try:
                # Validate archive file exists
                if not os.path.exists(archive_path):
                    # Log as not found but not an error (file may have been deleted)
                    if audit_manager:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=reference_path,
                            destination_path=archive_path,
                            file_hash=file_hash,
                            operation='bulk_delete_matched',
                            status='failed',
                            error_message='Archive file not found',
                            file_size=file_size
                        )
                    errors.append(f"{filename}: Archive file not found")
                    error_count += 1
                    continue

                # CRITICAL: Verify we're deleting from archive, not source
                archive_path_normalized = os.path.realpath(archive_path)
                archive_base_normalized = os.path.realpath(self.archive_location)

                in_main_archive = archive_path_normalized.startswith(archive_base_normalized)

                in_prior_archive = False
                if prior_revision_archive:
                    prior_archive_normalized = os.path.realpath(prior_revision_archive)
                    in_prior_archive = archive_path_normalized.startswith(prior_archive_normalized)

                if not in_main_archive and not in_prior_archive:
                    raise ValueError(
                        f"CRITICAL: Attempted to delete non-archive file!\n"
                        f"File path: {archive_path}\n"
                        f"Archive base: {self.archive_location}"
                    )

                # Calculate Delete Vault path (preserve structure relative to archive)
                if in_prior_archive:
                    relative_path = os.path.relpath(archive_path, prior_revision_archive)
                    vault_path = os.path.join(self.delete_vault_path, "prior_revisions", relative_path)
                else:
                    relative_path = os.path.relpath(archive_path, self.archive_location)
                    vault_path = os.path.join(self.delete_vault_path, relative_path)

                vault_dir = os.path.dirname(vault_path)

                # Create destination directory
                if not os.path.exists(vault_dir):
                    os.makedirs(vault_dir, exist_ok=True)

                # Check for collision in vault
                if os.path.exists(vault_path):
                    base, ext = os.path.splitext(vault_path)
                    counter = 1
                    while os.path.exists(f"{base}_{counter}{ext}"):
                        counter += 1
                    vault_path = f"{base}_{counter}{ext}"

                # Copy file to Delete Vault
                old_size = os.path.getsize(archive_path)
                try:
                    shutil.copy2(archive_path, vault_path)
                except OSError as e:
                    # Handle SMB/network shares that don't support chmod (errno 95)
                    if e.errno == 95:
                        shutil.copyfile(archive_path, vault_path)
                    else:
                        raise

                # Verify copy
                if not os.path.exists(vault_path):
                    raise Exception("File not found in vault after copy")

                new_size = os.path.getsize(vault_path)
                if new_size != old_size:
                    raise Exception(f"Size mismatch: {old_size} != {new_size}")

                # Delete from archive
                os.remove(archive_path)

                # Clean up empty directories
                self._cleanup_empty_dirs(archive_path, self.archive_location)

                # Mark in database
                success = db_metadata.mark_file_as_deleted(
                    file_hash=file_hash,
                    original_path=archive_path,
                    vault_path=vault_path,
                    reason='bulk_delete'
                )

                # Remove from UnreliableDates table
                try:
                    with PhotoDatabase(self.database_path) as db:
                        cursor = db.get_cursor()
                        cursor.execute("""
                            DELETE FROM UnreliableDates
                            WHERE file_hash = ?
                        """, (file_hash,))
                except Exception as e:
                    logger.warning(f"Failed to remove from UnreliableDates: {e}")

                # Sync deletion to albums
                if album_manager:
                    try:
                        album_manager.sync_deletion_to_albums(file_hash)
                    except Exception as e:
                        logger.warning(f"Failed to sync album deletion: {e}")

                # Log to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=reference_path,
                            destination_path=vault_path,
                            file_hash=file_hash,
                            operation='bulk_delete_matched',
                            status='success',
                            file_size=old_size
                        )
                    except Exception as audit_error:
                        logger.warning(f"Failed to log audit: {audit_error}")

                success_count += 1
                deleted_hashes.append(file_hash)

            except Exception as e:
                logger.error(f"Failed to delete {filename}: {e}", exc_info=True)
                errors.append(f"{filename}: {str(e)}")
                error_count += 1

                # Log failure to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=reference_path,
                            destination_path=archive_path,
                            file_hash=file_hash,
                            operation='bulk_delete_matched',
                            status='failed',
                            error_message=str(e),
                            file_size=file_size
                        )
                    except Exception as audit_error:
                        logger.warning(f"Failed to log audit failure: {audit_error}")

        # Log not found files to audit trail
        if audit_manager and hasattr(self, '_not_found_files'):
            for nf in self._not_found_files:
                try:
                    audit_manager.log_file_operation(
                        session_id=session_id,
                        source_path=nf.get('reference_path', ''),
                        destination_path='',
                        file_hash='',
                        operation='bulk_delete_not_found',
                        status='skipped',
                        error_message=nf.get('reason', 'Not in archive')
                    )
                except Exception as audit_error:
                    logger.warning(f"Failed to log not found file: {audit_error}")

        # End audit session
        if audit_manager:
            try:
                status = 'completed' if error_count == 0 else 'completed_with_errors'
                if self._cancelled:
                    status = 'cancelled'
                audit_manager.end_session(
                    session_id=session_id,
                    status=status,
                    stats={
                        'total_files_processed': total,
                        'total_unique_files': success_count,
                        'total_errors': error_count
                    }
                )
            except Exception as e:
                logger.warning(f"Failed to end audit session: {e}")

        self.status_update.emit("Delete operation complete")
        self.delete_completed.emit({
            'status': 'cancelled' if self._cancelled else 'completed',
            'success_count': success_count,
            'error_count': error_count,
            'errors': errors,
            'deleted_hashes': deleted_hashes
        })

    def _cleanup_empty_dirs(self, file_path, archive_base):
        """
        Clean up empty directories after file deletion.

        Args:
            file_path: Path to the deleted file
            archive_base: Base archive directory (stop cleanup here)
        """
        try:
            current_dir = os.path.dirname(file_path)

            while current_dir and current_dir != archive_base:
                try:
                    if os.path.exists(current_dir) and os.path.isdir(current_dir):
                        if not os.listdir(current_dir):
                            os.rmdir(current_dir)
                            logger.debug(f"Removed empty directory: {current_dir}")
                        else:
                            break
                except OSError:
                    break

                parent = os.path.dirname(current_dir)
                if parent == current_dir:
                    break
                current_dir = parent

        except Exception as e:
            logger.warning(f"Failed to clean up directories: {e}")
