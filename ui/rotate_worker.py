"""
Rotate Worker

Background worker for rotating images with Prior Revision Archive support.
When files are rotated, originals are moved to Prior Revision Archive,
keeping the main archive clean with only current revisions.
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_prior_revision_path(original_archive_path, file_hash, prior_archive_base):
    """
    Generate path in Prior Revision Archive that mirrors original date structure.

    Args:
        original_archive_path: Original path in main archive
            Example: /archive/2024/01/15/photo.jpg
        file_hash: SHA-256 hash of the file
        prior_archive_base: Base path for prior revision archive
            Example: /prior_revisions/

    Returns:
        Path in prior revision archive with hash suffix
            Example: /prior_revisions/2024/01/15/photo_abcd1234.jpg

    This mirrors the date structure and uses hash suffix (first 8 chars) to prevent collisions.
    """
    # Get just the directory structure and filename
    directory_parts = os.path.dirname(original_archive_path).split(os.sep)
    filename = os.path.basename(original_archive_path)

    # Find where date structure starts (look for year pattern YYYY)
    date_start_idx = None
    for i, part in enumerate(directory_parts):
        if part.isdigit() and len(part) == 4:
            year_val = int(part)
            if 1990 <= year_val <= 2100:  # Reasonable year range
                date_start_idx = i
                break

    if date_start_idx is None:
        # Fallback: use last 3 parts (likely year/month/day)
        date_structure = os.sep.join(directory_parts[-3:]) if len(directory_parts) >= 3 else ""
    else:
        # Use from year onwards
        date_structure = os.sep.join(directory_parts[date_start_idx:])

    # Add hash suffix to filename (first 8 characters of hash)
    name, ext = os.path.splitext(filename)
    hash_suffix = file_hash[:8]
    new_filename = f"{name}_{hash_suffix}{ext}"

    # Construct full path
    prior_path = os.path.join(prior_archive_base, date_structure, new_filename)

    return prior_path


class RotateWorker(QThread):
    """Background worker for rotating images."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)  # {'success': int, 'errors': list}

    def __init__(self, records, angle, db_path, archive_base, worker_logger):
        """
        Initialize rotation worker.

        Args:
            records: List of file record dictionaries
            angle: Rotation angle in degrees
            db_path: Path to database
            archive_base: Base path for archive
            worker_logger: Logger instance
        """
        super().__init__()
        self.records = records
        self.angle = angle
        self.db_path = db_path
        self.archive_base = archive_base
        self.worker_logger = worker_logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Rotation operation cancelled by user")

    def run(self):
        """Execute rotation operation in background thread (v5 + Prior Revision Archive)."""
        from image_modifier import ImageModifier
        from DuplicateFileDetection import PhotoDatabase, hash_file
        from database_metadata import DatabaseMetadata
        from audit_manager import AuditManager
        import time

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING IMAGE ROTATION PROCESS (v5 + Prior Revision Archive)")
        self.worker_logger.info(f"Files to rotate: {len(self.records)}")
        self.worker_logger.info(f"Rotation angle: {self.angle}°")
        self.worker_logger.info("=" * 80)

        # Get Prior Revision Archive location
        db_metadata = DatabaseMetadata(self.db_path)
        prior_archive_base = db_metadata.get_prior_revision_archive_location()

        if not prior_archive_base:
            error_msg = ("Prior Revision Archive not configured. "
                        "Please set location in Archive Settings tab.")
            self.worker_logger.error(error_msg)
            self.finished.emit({'success': 0, 'errors': [error_msg]})
            return

        if not os.path.exists(prior_archive_base):
            error_msg = f"Prior Revision Archive path does not exist: {prior_archive_base}"
            self.worker_logger.error(error_msg)
            self.finished.emit({'success': 0, 'errors': [error_msg]})
            return

        self.worker_logger.info(f"Prior Revision Archive: {prior_archive_base}")

        success_count = 0
        errors = []

        # Initialize audit manager and create session
        try:
            audit_manager = AuditManager(self.db_path)
            session_id = audit_manager.start_session(
                operation_mode='rotate_image',
                source_directories=[],
                destination_directory=self.archive_base
            )
            self.worker_logger.info(f"✓ Audit session started: {session_id}")
        except Exception as e:
            self.worker_logger.warning(f"Failed to initialize audit manager: {e}")
            # Continue without audit logging
            audit_manager = None
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        for idx, record in enumerate(self.records):
            if self.cancelled:
                self.worker_logger.info("Rotation cancelled by user")
                break

            archive_path = record.get('archive_path')
            if not archive_path:
                error_msg = f"File {idx+1}: No archive path"
                self.worker_logger.error(error_msg)
                errors.append(error_msg)
                continue

            filename = os.path.basename(archive_path)
            self.progress.emit(idx + 1, len(self.records), filename)

            self.worker_logger.info("-" * 60)
            self.worker_logger.info(f"Processing file {idx+1}/{len(self.records)}: {filename}")

            # Initialize original_hash for exception handler
            original_hash = None

            try:
                # Validate file exists
                if not os.path.exists(archive_path):
                    raise FileNotFoundError(f"Archive file not found: {archive_path}")

                # CRITICAL: Ensure we're NOT modifying a source file
                # Source files must NEVER be modified - this is a fundamental architecture rule
                # Files can be in the main archive OR the prior revision archive
                archive_path_normalized = os.path.realpath(archive_path)
                archive_base_normalized = os.path.realpath(self.archive_base)

                # Check if file is in main archive
                in_main_archive = archive_path_normalized.startswith(archive_base_normalized)

                # Check if file is in prior revision archive
                in_prior_archive = False
                if prior_archive_base:
                    prior_archive_normalized = os.path.realpath(prior_archive_base)
                    in_prior_archive = archive_path_normalized.startswith(prior_archive_normalized)

                if not in_main_archive and not in_prior_archive:
                    raise ValueError(
                        f"CRITICAL: Attempted to rotate source file!\n"
                        f"File path: {archive_path}\n"
                        f"Archive base: {self.archive_base}\n"
                        f"Prior archive: {prior_archive_base}\n"
                        f"Source files must NEVER be modified. "
                        f"This file appears to be in a source directory, not the archive."
                    )

                # Calculate original hash
                original_hash = hash_file(archive_path)
                self.worker_logger.info(f"  Original hash: {original_hash[:16]}...")

                # Get original file metadata from database
                with PhotoDatabase(self.db_path) as db:
                    cursor = db.get_cursor()
                    cursor.execute("""
                        SELECT create_datetime, create_year, create_month, create_day, file_size
                        FROM UniquePhotos
                        WHERE file_hash = ?
                    """, (original_hash,))

                    result = cursor.fetchone()
                    if not result:
                        raise Exception(f"Original file not found in database: {original_hash[:16]}...")

                    create_datetime, create_year, create_month, create_day, original_file_size = result
                    self.worker_logger.info(f"  Original metadata: {create_datetime}, size: {original_file_size}")

                # Rotate the image
                self.worker_logger.info(f"  Rotating by {self.angle}°...")
                success, rotated_path, error = ImageModifier.rotate_image(
                    archive_path,
                    self.angle,
                    expand=True
                )

                if not success:
                    raise Exception(f"Rotation failed: {error}")

                self.worker_logger.info(f"  ✓ Rotated image created: {os.path.basename(rotated_path)}")

                # Calculate new hash
                new_hash = hash_file(rotated_path)
                new_file_size = os.path.getsize(rotated_path)
                self.worker_logger.info(f"  New hash: {new_hash[:16]}..., size: {new_file_size}")

                # ========================================
                # CRITICAL: Move original to Prior Revision Archive
                # ========================================
                self.worker_logger.info("  Moving original to Prior Revision Archive...")

                # Generate path in prior revision archive
                prior_revision_path = generate_prior_revision_path(
                    archive_path,
                    original_hash,
                    prior_archive_base
                )

                self.worker_logger.info(f"  Prior revision path: {prior_revision_path}")

                # Create directory structure in prior archive
                prior_dir = os.path.dirname(prior_revision_path)
                os.makedirs(prior_dir, exist_ok=True)

                # Move original file to prior revision archive
                try:
                    shutil.move(archive_path, prior_revision_path)
                    self.worker_logger.info(f"  ✓ Original moved to: {os.path.basename(prior_revision_path)}")
                except Exception as e:
                    # Fallback: copy then delete
                    self.worker_logger.warning(f"  ⚠ Move failed, using copy+delete: {e}")
                    try:
                        shutil.copy2(archive_path, prior_revision_path)
                    except PermissionError:
                        shutil.copy(archive_path, prior_revision_path)
                        self.worker_logger.info("  ℹ Using copy() instead of copy2()")
                    os.remove(archive_path)
                    self.worker_logger.info(f"  ✓ Original copied to: {os.path.basename(prior_revision_path)}")

                # Verify original is gone from main archive
                if os.path.exists(archive_path):
                    raise Exception("Original file still exists in main archive after move!")

                # Update database record for original (now in prior archive)
                with PhotoDatabase(self.db_path) as db:
                    cursor = db.get_cursor()
                    cursor.execute("""
                        UPDATE UniquePhotos
                        SET file_name = ?
                        WHERE file_hash = ?
                    """, (prior_revision_path, original_hash))

                    if cursor.rowcount == 0:
                        raise Exception("Failed to update original file location in database")

                    self.worker_logger.info("  ✓ Database updated with prior revision location")

                # ========================================
                # Place rotated version in main archive (takes over current slot)
                # ========================================
                self.worker_logger.info("  Placing rotated version in main archive...")

                try:
                    shutil.copy2(rotated_path, archive_path)
                except PermissionError:
                    shutil.copy(rotated_path, archive_path)
                    self.worker_logger.info("  ℹ Using copy() instead of copy2()")

                # Verify placement
                if not os.path.exists(archive_path):
                    raise Exception("Rotated file not placed in main archive!")

                placed_size = os.path.getsize(archive_path)
                if placed_size != new_file_size:
                    raise Exception(f"Size mismatch: {placed_size} != {new_file_size}")

                self.worker_logger.info(f"  ✓ Rotated version placed as: {filename}")
                self.worker_logger.info(f"  ✓ Main archive now contains CURRENT revision only")

                # Clean up temporary rotated file
                if os.path.exists(rotated_path):
                    os.remove(rotated_path)

                # Create revision record in UniquePhotos (v5 schema)
                self.worker_logger.info("  Creating revision record in database...")
                with PhotoDatabase(self.db_path) as db:
                    from DuplicateFileDetection import hash_file_partial

                    # Calculate partial hash if needed
                    partial_hash = None
                    partial_hash_bytes = None
                    if new_file_size >= 1048576:  # 1MB threshold
                        partial_hash_bytes = 16384
                        partial_hash = hash_file_partial(archive_path, partial_hash_bytes)

                    # Create new revision record
                    success = db.create_revision(
                        new_file_hash=new_hash,
                        parent_hash=original_hash,
                        revision_reason='rotation',
                        file_path=archive_path,  # Same path (in-place replacement)
                        file_size=new_file_size,
                        create_datetime=create_datetime,
                        create_year=create_year,
                        create_month=create_month,
                        create_day=create_day,
                        partial_hash=partial_hash,
                        partial_hash_bytes=partial_hash_bytes
                    )

                    if not success:
                        raise Exception("Failed to create revision record")

                    self.worker_logger.info(f"  ✓ Created revision record: {new_hash[:16]}... (parent: {original_hash[:16]}...)")

                    # CRITICAL: Update UnreliableDates table with new hash
                    # Without this, grid displays old thumbnails because it looks up by old hash
                    cursor = db.get_cursor()
                    cursor.execute("""
                        UPDATE UnreliableDates
                        SET file_hash = ?
                        WHERE file_hash = ?
                    """, (new_hash, original_hash))

                    if cursor.rowcount > 0:
                        self.worker_logger.info("  ✓ Updated UnreliableDates with new hash")

                    self.worker_logger.info("  ✓ Duplicate detection enabled via UniquePhotos primary key")

                # Log to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=archive_path,
                            destination_path=archive_path,
                            file_hash=new_hash,
                            operation='rotate_image',
                            status='success',
                            file_size=os.path.getsize(archive_path) if os.path.exists(archive_path) else None
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
                            destination_path=archive_path,
                            file_hash=original_hash,
                            operation='rotate_image',
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
        self.worker_logger.info("ROTATION PROCESS COMPLETE")
        self.worker_logger.info(f"Successfully rotated: {success_count}/{len(self.records)}")
        self.worker_logger.info(f"Failed: {len(errors)}")
        self.worker_logger.info(f"Main archive contains: CURRENT revisions only")
        self.worker_logger.info(f"Prior revisions stored in: {prior_archive_base}")
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


class UndoRotationWorker(QThread):
    """Background worker for undoing image rotations by restoring prior revisions."""

    progress = Signal(int, int, str)  # current, total, description
    finished = Signal(dict)  # {'success': int, 'errors': list}

    def __init__(self, revision_hashes, db_path, worker_logger):
        """
        Initialize undo rotation worker.

        Args:
            revision_hashes: List of file_hash values for revisions to undo
            db_path: Path to database
            worker_logger: Logger instance
        """
        super().__init__()
        self.revision_hashes = revision_hashes
        self.db_path = db_path
        self.worker_logger = worker_logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Undo operation cancelled by user")

    def run(self):
        """Execute undo operation in background thread."""
        from DuplicateFileDetection import PhotoDatabase
        from database_metadata import DatabaseMetadata
        from audit_manager import AuditManager

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING UNDO ROTATION PROCESS")
        self.worker_logger.info(f"Revisions to undo: {len(self.revision_hashes)}")
        self.worker_logger.info("=" * 80)

        success_count = 0
        errors = []

        # Get Prior Revision Archive location
        db_metadata = DatabaseMetadata(self.db_path)
        prior_archive_base = db_metadata.get_prior_revision_archive_location()

        if not prior_archive_base:
            error_msg = "Prior Revision Archive not configured"
            self.worker_logger.error(error_msg)
            self.finished.emit({'success': 0, 'errors': [error_msg]})
            return

        # Initialize audit manager and create session
        try:
            audit_manager = AuditManager(self.db_path)
            session_id = audit_manager.start_session(
                operation_mode='undo_rotation',
                source_directories=[],
                destination_directory=""
            )
            self.worker_logger.info(f"✓ Audit session started: {session_id}")
        except Exception as e:
            self.worker_logger.warning(f"Failed to initialize audit manager: {e}")
            audit_manager = None
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        for idx, revision_hash in enumerate(self.revision_hashes):
            if self.cancelled:
                self.worker_logger.info("Undo cancelled by user")
                break

            self.progress.emit(idx + 1, len(self.revision_hashes), f"Undoing {revision_hash[:16]}...")

            self.worker_logger.info("-" * 60)
            self.worker_logger.info(f"Processing revision {idx+1}/{len(self.revision_hashes)}: {revision_hash[:16]}...")

            try:
                with PhotoDatabase(self.db_path) as db:
                    cursor = db.get_cursor()

                    # Get current revision record (in main archive)
                    cursor.execute("""
                        SELECT file_name, revised_photo, revision_reason
                        FROM UniquePhotos
                        WHERE file_hash = ?
                    """, (revision_hash,))

                    result = cursor.fetchone()
                    if not result:
                        raise Exception(f"Revision not found in database: {revision_hash[:16]}...")

                    current_path, parent_hash, revision_reason = result

                    if not parent_hash:
                        raise Exception("Cannot undo original import (no parent revision)")

                    self.worker_logger.info(f"  Current file: {current_path}")
                    self.worker_logger.info(f"  Parent hash: {parent_hash[:16]}...")
                    self.worker_logger.info(f"  Reason: {revision_reason}")

                    # Get parent revision record (in prior archive)
                    cursor.execute("""
                        SELECT file_name
                        FROM UniquePhotos
                        WHERE file_hash = ?
                    """, (parent_hash,))

                    parent_result = cursor.fetchone()
                    if not parent_result:
                        raise Exception("Parent revision not found in database")

                    parent_path = parent_result[0]
                    self.worker_logger.info(f"  Parent file: {parent_path}")

                    # Verify parent file exists in prior archive
                    if not os.path.exists(parent_path):
                        raise Exception(f"Parent file not found: {parent_path}")

                    # Generate path in prior archive for current revision
                    current_to_prior_path = generate_prior_revision_path(
                        current_path,
                        revision_hash,
                        prior_archive_base
                    )

                    # 1. Move current → Prior Archive
                    self.worker_logger.info("  Moving current revision to Prior Archive...")
                    prior_dir = os.path.dirname(current_to_prior_path)
                    os.makedirs(prior_dir, exist_ok=True)

                    try:
                        shutil.move(current_path, current_to_prior_path)
                    except Exception as e:
                        # Fallback: copy then delete
                        self.worker_logger.warning(f"  ⚠ Move failed, using copy+delete: {e}")
                        shutil.copy2(current_path, current_to_prior_path)
                        os.remove(current_path)

                    self.worker_logger.info(f"  ✓ Current moved to: {os.path.basename(current_to_prior_path)}")

                    # 2. Move parent → Main Archive (restores position)
                    self.worker_logger.info("  Restoring parent to Main Archive...")
                    try:
                        shutil.move(parent_path, current_path)
                    except Exception as e:
                        # Fallback: copy then delete
                        self.worker_logger.warning(f"  ⚠ Move failed, using copy+delete: {e}")
                        shutil.copy2(parent_path, current_path)
                        os.remove(parent_path)

                    self.worker_logger.info(f"  ✓ Parent restored to: {os.path.basename(current_path)}")

                    # 3. Update database
                    # Update current revision (now in prior archive)
                    cursor.execute("""
                        UPDATE UniquePhotos
                        SET file_name = ?
                        WHERE file_hash = ?
                    """, (current_to_prior_path, revision_hash))

                    # Update parent (now in main archive)
                    cursor.execute("""
                        UPDATE UniquePhotos
                        SET file_name = ?
                        WHERE file_hash = ?
                    """, (current_path, parent_hash))

                    # Update UnreliableDates if needed
                    cursor.execute("""
                        UPDATE UnreliableDates
                        SET file_hash = ?
                        WHERE file_hash = ?
                    """, (parent_hash, revision_hash))

                    if cursor.rowcount > 0:
                        self.worker_logger.info("  ✓ Updated UnreliableDates to parent hash")

                    self.worker_logger.info(f"  ✓ Parent revision ({parent_hash[:16]}...) is now current")

                # Log to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=current_to_prior_path,
                            destination_path=current_path,
                            file_hash=parent_hash,
                            operation='undo_rotation',
                            status='success'
                        )
                    except Exception as audit_error:
                        self.worker_logger.warning(f"  ⚠ Failed to log audit: {audit_error}")

                success_count += 1
                self.worker_logger.info(f"✓ Revision {idx+1} undone successfully")

            except Exception as e:
                error_msg = f"{revision_hash[:16]}...: {str(e)}"
                self.worker_logger.error(f"✗ Revision {idx+1} failed: {e}", exc_info=True)
                errors.append(error_msg)

                # Log failure to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path="",
                            destination_path="",
                            file_hash=revision_hash,
                            operation='undo_rotation',
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
                        'total_files_processed': len(self.revision_hashes),
                        'total_unique_files': success_count,
                        'total_errors': len(errors)
                    }
                )
                self.worker_logger.info(f"✓ Audit session ended: {session_id}")
            except Exception as e:
                self.worker_logger.warning(f"Failed to end audit session: {e}")

        # Final summary
        self.worker_logger.info("=" * 80)
        self.worker_logger.info("UNDO ROTATION COMPLETE")
        self.worker_logger.info(f"Successfully undone: {success_count}/{len(self.revision_hashes)}")
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
