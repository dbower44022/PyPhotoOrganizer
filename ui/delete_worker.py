"""
Delete Worker

Background worker for deleting files to Delete Vault.
Preserves folder structure and tracks deletions in database.
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DeleteWorker(QThread):
    """Background worker for deleting files to Delete Vault."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)  # {'success': int, 'errors': list}

    def __init__(self, records, delete_vault_path, db_path, worker_logger):
        """
        Initialize deletion worker.

        Args:
            records: List of file record dictionaries
            delete_vault_path: Path to Delete Vault directory
            db_path: Path to database
            worker_logger: Logger instance
        """
        super().__init__()
        self.records = records
        self.delete_vault_path = delete_vault_path
        self.db_path = db_path
        self.worker_logger = worker_logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Deletion operation cancelled by user")

    def run(self):
        """Execute deletion operation in background thread."""
        from database_metadata import DatabaseMetadata
        from DuplicateFileDetection import hash_file
        from audit_manager import AuditManager

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING FILE DELETION PROCESS")
        self.worker_logger.info(f"Files to delete: {len(self.records)}")
        self.worker_logger.info(f"Delete Vault: {self.delete_vault_path}")
        self.worker_logger.info("=" * 80)

        success_count = 0
        errors = []

        # Initialize database metadata
        try:
            db_metadata = DatabaseMetadata(self.db_path)
            archive_base = db_metadata.get_archive_location()
        except Exception as e:
            self.worker_logger.error(f"Failed to initialize database: {e}", exc_info=True)
            self.finished.emit({'success': 0, 'errors': [f"Failed to initialize: {e}"]})
            return

        # Initialize audit manager and create session
        try:
            audit_manager = AuditManager(self.db_path)
            session_id = audit_manager.start_session(
                operation_mode='delete_to_vault',
                source_directories=[],
                destination_directory=self.delete_vault_path
            )
            self.worker_logger.info(f"✓ Audit session started: {session_id}")
        except Exception as e:
            self.worker_logger.warning(f"Failed to initialize audit manager: {e}")
            audit_manager = None
            session_id = None

        for idx, record in enumerate(self.records):
            if self.cancelled:
                self.worker_logger.info("Deletion cancelled by user")
                break

            archive_path = record.get('archive_path')
            file_hash = record.get('file_hash')

            if not archive_path:
                error_msg = f"File {idx+1}: No archive path"
                self.worker_logger.error(error_msg)
                errors.append(error_msg)
                continue

            filename = os.path.basename(archive_path)
            self.progress.emit(idx + 1, len(self.records), filename)

            self.worker_logger.info("-" * 60)
            self.worker_logger.info(f"Processing file {idx+1}/{len(self.records)}: {filename}")

            try:
                # Validate file exists
                if not os.path.exists(archive_path):
                    raise FileNotFoundError(f"Archive file not found: {archive_path}")

                # CRITICAL: Ensure we're NOT deleting a source file
                # Source files must NEVER be modified - this is a fundamental architecture rule
                archive_path_normalized = os.path.realpath(archive_path)
                archive_base_normalized = os.path.realpath(archive_base)

                if not archive_path_normalized.startswith(archive_base_normalized):
                    raise ValueError(
                        f"CRITICAL: Attempted to delete source file!\n"
                        f"File path: {archive_path}\n"
                        f"Archive base: {archive_base}\n"
                        f"Source files must NEVER be modified. "
                        f"This file appears to be in a source directory, not the archive."
                    )

                # Calculate hash if not provided
                if not file_hash:
                    file_hash = hash_file(archive_path)
                    self.worker_logger.info(f"  Calculated hash: {file_hash[:16]}...")

                # Calculate Delete Vault path (preserve structure relative to archive)
                relative_path = os.path.relpath(archive_path, archive_base)
                vault_path = os.path.join(self.delete_vault_path, relative_path)
                vault_dir = os.path.dirname(vault_path)

                self.worker_logger.info(f"  Archive: {archive_path}")
                self.worker_logger.info(f"  Vault: {vault_path}")

                # Create destination directory
                if not os.path.exists(vault_dir):
                    os.makedirs(vault_dir, exist_ok=True)
                    self.worker_logger.info(f"  ✓ Created vault directory: {vault_dir}")

                # Check for collision in vault
                if os.path.exists(vault_path):
                    # Generate unique filename
                    base, ext = os.path.splitext(vault_path)
                    counter = 1
                    while os.path.exists(f"{base}_{counter}{ext}"):
                        counter += 1
                    vault_path = f"{base}_{counter}{ext}"
                    self.worker_logger.info(f"  ⚠ Collision detected, using: {os.path.basename(vault_path)}")

                # Copy file to Delete Vault
                old_size = os.path.getsize(archive_path)
                self.worker_logger.info(f"  Copying to vault (size: {old_size} bytes)...")

                shutil.copy2(archive_path, vault_path)

                # Verify copy
                if not os.path.exists(vault_path):
                    raise Exception("File not found in vault after copy")

                new_size = os.path.getsize(vault_path)
                if new_size != old_size:
                    raise Exception(f"Size mismatch: {old_size} != {new_size}")

                self.worker_logger.info(f"  ✓ Copied to vault successfully")

                # Delete from archive
                self.worker_logger.info("  Deleting from archive...")
                os.remove(archive_path)
                self.worker_logger.info("  ✓ Deleted from archive")

                # Clean up empty directories
                self._cleanup_empty_dirs(archive_path, archive_base)

                # Mark in database
                self.worker_logger.info("  Updating database...")
                success = db_metadata.mark_file_as_deleted(
                    file_hash=file_hash,
                    original_path=archive_path,
                    vault_path=vault_path,
                    reason='user_deleted'
                )

                if success:
                    self.worker_logger.info("  ✓ Database updated (DeletedFiles)")
                else:
                    self.worker_logger.warning("  ⚠ Database update failed (file still deleted)")

                # CRITICAL: Remove from UnreliableDates table (file no longer in archive)
                # This prevents deleted files from appearing in Date Corrections grid
                try:
                    from DuplicateFileDetection import PhotoDatabase
                    with PhotoDatabase(self.db_path) as db:
                        cursor = db.get_cursor()
                        cursor.execute("""
                            DELETE FROM UnreliableDates
                            WHERE file_hash = ?
                        """, (file_hash,))

                        if cursor.rowcount > 0:
                            self.worker_logger.info("  ✓ Removed from UnreliableDates table")
                except Exception as e:
                    self.worker_logger.warning(f"  ⚠ Failed to remove from UnreliableDates: {e}")

                # Log to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=archive_path,
                            destination_path=vault_path,
                            file_hash=file_hash,
                            operation='delete_to_vault',
                            status='success',
                            file_size=old_size
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
                            source_path=archive_path,
                            destination_path=vault_path,
                            file_hash=file_hash,
                            operation='delete_to_vault',
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
                        'total_files_processed': len(self.records),
                        'total_unique_files': success_count,
                        'total_errors': len(errors)
                    }
                )
                self.worker_logger.info(f"✓ Audit session ended: {session_id}")
            except Exception as e:
                self.worker_logger.warning(f"Failed to end audit session: {e}")

        # Final summary
        self.worker_logger.info("=" * 80)
        self.worker_logger.info("DELETION PROCESS COMPLETE")
        self.worker_logger.info(f"Successfully deleted: {success_count}/{len(self.records)}")
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
                # Try to remove directory (only works if empty)
                try:
                    if os.path.exists(current_dir) and os.path.isdir(current_dir):
                        # Check if directory is empty
                        if not os.listdir(current_dir):
                            os.rmdir(current_dir)
                            self.worker_logger.info(f"  ✓ Removed empty directory: {current_dir}")
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
            self.worker_logger.warning(f"  ⚠ Failed to clean up directories: {e}")
