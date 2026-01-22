"""
Restore Worker

Background worker for restoring files from Delete Vault to archive.
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class RestoreWorker(QThread):
    """Background worker for restoring files from Delete Vault."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)  # {'success': int, 'errors': list}

    def __init__(self, deleted_records, db_metadata, worker_logger):
        """
        Initialize restore worker.

        Args:
            deleted_records: List of deleted file record dictionaries
            db_metadata: DatabaseMetadata instance
            worker_logger: Logger instance
        """
        super().__init__()
        self.deleted_records = deleted_records
        self.db_metadata = db_metadata
        self.worker_logger = worker_logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Restore operation cancelled by user")

    def run(self):
        """Execute restore operation in background thread."""
        from DuplicateFileDetection import PhotoDatabase
        from audit_manager import AuditManager

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING FILE RESTORE PROCESS")
        self.worker_logger.info(f"Files to restore: {len(self.deleted_records)}")
        self.worker_logger.info("=" * 80)

        success_count = 0
        errors = []

        # Initialize audit manager and create session
        try:
            audit_manager = AuditManager(self.db_metadata.database_path)
            archive_base = self.db_metadata.get_archive_location()
            session_id = audit_manager.start_session(
                operation_mode='restore_from_vault',
                source_directories=[self.db_metadata.get_delete_vault_location()],
                destination_directory=archive_base
            )
            self.worker_logger.info(f"✓ Audit session started: {session_id}")
        except Exception as e:
            self.worker_logger.warning(f"Failed to initialize audit manager: {e}")
            audit_manager = None
            session_id = None

        for idx, record in enumerate(self.deleted_records):
            if self.cancelled:
                self.worker_logger.info("Restore cancelled by user")
                break

            vault_path = record.get('delete_vault_path')
            original_path = record.get('original_archive_path')
            file_hash = record.get('file_hash')

            if not vault_path or not original_path:
                error_msg = f"File {idx+1}: Missing vault or original path"
                self.worker_logger.error(error_msg)
                errors.append(error_msg)
                continue

            filename = os.path.basename(original_path)
            self.progress.emit(idx + 1, len(self.deleted_records), filename)

            self.worker_logger.info("-" * 60)
            self.worker_logger.info(f"Processing file {idx+1}/{len(self.deleted_records)}: {filename}")

            try:
                # Validate file exists in vault
                if not os.path.exists(vault_path):
                    raise FileNotFoundError(f"File not found in vault: {vault_path}")

                self.worker_logger.info(f"  Vault: {vault_path}")
                self.worker_logger.info(f"  Restore to: {original_path}")

                # Create destination directory
                original_dir = os.path.dirname(original_path)
                if not os.path.exists(original_dir):
                    os.makedirs(original_dir, exist_ok=True)
                    self.worker_logger.info(f"  ✓ Created archive directory: {original_dir}")

                # Check for collision in archive
                restore_path = original_path
                if os.path.exists(restore_path):
                    # Generate unique filename
                    base, ext = os.path.splitext(restore_path)
                    counter = 1
                    while os.path.exists(f"{base}_restored_{counter}{ext}"):
                        counter += 1
                    restore_path = f"{base}_restored_{counter}{ext}"
                    self.worker_logger.info(f"  ⚠ Collision detected, using: {os.path.basename(restore_path)}")

                # Copy file from vault to archive
                vault_size = os.path.getsize(vault_path)
                self.worker_logger.info(f"  Copying from vault (size: {vault_size} bytes)...")

                try:
                    shutil.copy2(vault_path, restore_path)
                except OSError as e:
                    # Handle SMB/network shares that don't support chmod (errno 95)
                    if e.errno == 95:
                        self.worker_logger.warning(f"copy2 failed (metadata not supported), using copyfile: {e}")
                        shutil.copyfile(vault_path, restore_path)
                    else:
                        raise

                # Verify copy
                if not os.path.exists(restore_path):
                    raise Exception("File not found in archive after copy")

                restored_size = os.path.getsize(restore_path)
                if restored_size != vault_size:
                    raise Exception(f"Size mismatch: {vault_size} != {restored_size}")

                self.worker_logger.info(f"  ✓ Copied to archive successfully")

                # Delete from vault
                self.worker_logger.info("  Deleting from vault...")
                os.remove(vault_path)
                self.worker_logger.info("  ✓ Deleted from vault")

                # Clean up empty directories in vault
                self._cleanup_empty_dirs(vault_path)

                # Update database - mark as restored
                self.worker_logger.info("  Updating database...")
                success = self.db_metadata.mark_file_as_restored(file_hash)

                if success:
                    self.worker_logger.info("  ✓ Marked as restored in DeletedFiles")
                else:
                    self.worker_logger.warning("  ⚠ Database update failed (file still restored)")

                # Update UniquePhotos with restored path
                with PhotoDatabase(self.db_metadata.database_path) as db:
                    db.restore_photo(file_hash, restore_path)
                    self.worker_logger.info("  ✓ Updated UniquePhotos with restored path")

                # NOTE: Restored files do NOT automatically reappear in UnreliableDates view
                # The UnreliableDates record was deleted during deletion to vault
                # If user wants to correct dates on restored files, they should re-import them

                # Log to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=vault_path,
                            destination_path=restore_path,
                            file_hash=file_hash,
                            operation='restore_from_vault',
                            status='success',
                            file_size=restored_size
                        )
                    except Exception as audit_error:
                        self.worker_logger.warning(f"  ⚠ Failed to log audit: {audit_error}")

                success_count += 1
                self.worker_logger.info(f"✓ File {idx+1} completed successfully")

            except Exception as e:
                error_msg = f"{filename}: {str(e)}"
                self.worker_logger.error(f"✗ File {idx+1} failed: {e}", exc_info=True)
                errors.append(error_msg)

                # Log failure to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=vault_path,
                            destination_path=original_path,
                            file_hash=file_hash,
                            operation='restore_from_vault',
                            status='failed',
                            error_message=str(e)
                        )
                    except Exception as audit_error:
                        self.worker_logger.warning(f"  ⚠ Failed to log audit failure: {audit_error}")

        # End audit session
        if audit_manager:
            try:
                audit_manager.end_session(
                    session_id=session_id,
                    status='completed' if not errors else 'completed_with_errors',
                    stats={
                        'total_files_processed': len(self.deleted_records),
                        'total_unique_files': success_count,
                        'total_errors': len(errors)
                    }
                )
                self.worker_logger.info(f"✓ Audit session ended: {session_id}")
            except Exception as e:
                self.worker_logger.warning(f"Failed to end audit session: {e}")

        # Final summary
        self.worker_logger.info("=" * 80)
        self.worker_logger.info("RESTORE PROCESS COMPLETE")
        self.worker_logger.info(f"Successfully restored: {success_count}/{len(self.deleted_records)}")
        self.worker_logger.info(f"Failed: {len(errors)}")
        if errors:
            self.worker_logger.info("Errors:")
            for error in errors:
                self.worker_logger.info(f"  - {error}")
        self.worker_logger.info("=" * 80)

        # Emit results
        self.finished.emit({
            'success': success_count,
            'errors': errors
        })

    def _cleanup_empty_dirs(self, file_path):
        """
        Clean up empty directories after file removal from vault.

        Args:
            file_path: Path to the removed file
        """
        try:
            current_dir = os.path.dirname(file_path)
            vault_base = self.db_metadata.get_delete_vault_location()

            while current_dir and current_dir != vault_base:
                # Try to remove directory (only works if empty)
                try:
                    if os.path.exists(current_dir) and os.path.isdir(current_dir):
                        # Check if directory is empty
                        if not os.listdir(current_dir):
                            os.rmdir(current_dir)
                            self.worker_logger.info(f"  ✓ Removed empty vault directory: {current_dir}")
                        else:
                            # Directory not empty, stop cleanup
                            break
                except OSError:
                    # Directory not empty or permission error
                    break

                # Move to parent directory
                parent = os.path.dirname(current_dir)
                if parent == current_dir:  # Reached root
                    break
                current_dir = parent

        except Exception as e:
            self.worker_logger.warning(f"  ⚠ Failed to clean up vault directories: {e}")
