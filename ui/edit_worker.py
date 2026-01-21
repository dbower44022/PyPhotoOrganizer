"""
Edit Worker

Background worker for applying photo edits with Prior Revision Archive support.
When files are edited, originals are moved to Prior Revision Archive,
keeping the main archive clean with only current revisions.

Follows the same pattern as rotate_worker.py for consistency.
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class EditState:
    """
    Tracks pending edits for an image.

    All adjustment values are -100 to +100 (0 = no change).
    """
    brightness: int = 0
    contrast: int = 0
    saturation: int = 0
    crop_box: Optional[Tuple[int, int, int, int]] = None  # (left, upper, right, lower)

    def has_changes(self) -> bool:
        """Check if any edits have been made."""
        return (
            self.brightness != 0 or
            self.contrast != 0 or
            self.saturation != 0 or
            self.crop_box is not None
        )

    def has_color_changes(self) -> bool:
        """Check if color adjustments have been made."""
        return self.brightness != 0 or self.contrast != 0 or self.saturation != 0

    def has_crop(self) -> bool:
        """Check if crop has been applied."""
        return self.crop_box is not None

    def get_revision_reason(self) -> str:
        """Get the appropriate revision reason based on changes."""
        if self.has_crop() and self.has_color_changes():
            return 'photo_edit'
        elif self.has_crop():
            return 'crop'
        elif self.has_color_changes():
            return 'color_adjustment'
        return 'photo_edit'

    def reset(self):
        """Reset all values to defaults."""
        self.brightness = 0
        self.contrast = 0
        self.saturation = 0
        self.crop_box = None

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/serialization."""
        return {
            'brightness': self.brightness,
            'contrast': self.contrast,
            'saturation': self.saturation,
            'crop_box': self.crop_box
        }


def generate_prior_revision_path(original_archive_path: str, file_hash: str,
                                  prior_archive_base: str) -> str:
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
    """
    # Get just the directory structure and filename
    directory_parts = os.path.dirname(original_archive_path).split(os.sep)
    filename = os.path.basename(original_archive_path)

    # Find where date structure starts (look for year pattern YYYY)
    date_start_idx = None
    for i, part in enumerate(directory_parts):
        if part.isdigit() and len(part) == 4:
            year_val = int(part)
            if 1990 <= year_val <= 2100:
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


class EditWorker(QThread):
    """Background worker for applying photo edits."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)  # {'success': int, 'errors': list, 'edited_hashes': list}

    def __init__(self, records: List[dict], edit_states: Dict[str, EditState],
                 db_path: str, archive_base: str, worker_logger):
        """
        Initialize edit worker.

        Args:
            records: List of file record dictionaries
            edit_states: Dictionary mapping file_hash to EditState
            db_path: Path to database
            archive_base: Base path for archive
            worker_logger: Logger instance
        """
        super().__init__()
        self.records = records
        self.edit_states = edit_states
        self.db_path = db_path
        self.archive_base = archive_base
        self.worker_logger = worker_logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Edit operation cancelled by user")

    def run(self):
        """Execute edit operation in background thread (v5 + Prior Revision Archive)."""
        from image_modifier import ImageModifier
        from DuplicateFileDetection import PhotoDatabase, hash_file, hash_file_partial
        from database_metadata import DatabaseMetadata
        from audit_manager import AuditManager

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING IMAGE EDIT PROCESS (v5 + Prior Revision Archive)")
        self.worker_logger.info(f"Files to edit: {len(self.records)}")
        self.worker_logger.info("=" * 80)

        # Get Prior Revision Archive location
        db_metadata = DatabaseMetadata(self.db_path)
        prior_archive_base = db_metadata.get_prior_revision_archive_location()

        if not prior_archive_base:
            error_msg = ("Prior Revision Archive not configured. "
                        "Please set location in Archive Settings tab.")
            self.worker_logger.error(error_msg)
            self.finished.emit({'success': 0, 'errors': [error_msg], 'edited_hashes': []})
            return

        if not os.path.exists(prior_archive_base):
            error_msg = f"Prior Revision Archive path does not exist: {prior_archive_base}"
            self.worker_logger.error(error_msg)
            self.finished.emit({'success': 0, 'errors': [error_msg], 'edited_hashes': []})
            return

        self.worker_logger.info(f"Prior Revision Archive: {prior_archive_base}")

        success_count = 0
        errors = []
        edited_hashes = []

        # Initialize audit manager and create session
        try:
            audit_manager = AuditManager(self.db_path)
            session_id = audit_manager.start_session(
                operation_mode='edit_image',
                source_directories=[],
                destination_directory=self.archive_base
            )
            self.worker_logger.info(f"Audit session started: {session_id}")
        except Exception as e:
            self.worker_logger.warning(f"Failed to initialize audit manager: {e}")
            audit_manager = None
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        for idx, record in enumerate(self.records):
            if self.cancelled:
                self.worker_logger.info("Edit cancelled by user")
                break

            archive_path = record.get('archive_path') or record.get('file_name')
            if not archive_path:
                error_msg = f"File {idx+1}: No archive path"
                self.worker_logger.error(error_msg)
                errors.append(error_msg)
                continue

            file_hash = record.get('file_hash')
            if not file_hash:
                error_msg = f"File {idx+1}: No file hash"
                self.worker_logger.error(error_msg)
                errors.append(error_msg)
                continue

            # Get edit state for this file
            edit_state = self.edit_states.get(file_hash)
            if not edit_state or not edit_state.has_changes():
                self.worker_logger.info(f"Skipping {file_hash[:16]}... - no changes")
                continue

            filename = os.path.basename(archive_path)
            self.progress.emit(idx + 1, len(self.records), filename)

            self.worker_logger.info("-" * 60)
            self.worker_logger.info(f"Processing file {idx+1}/{len(self.records)}: {filename}")
            self.worker_logger.info(f"  Edit state: {edit_state.to_dict()}")

            original_hash = None

            try:
                # Validate file exists
                if not os.path.exists(archive_path):
                    raise FileNotFoundError(f"Archive file not found: {archive_path}")

                # CRITICAL: Ensure we're NOT modifying a source file
                archive_path_normalized = os.path.realpath(archive_path)
                archive_base_normalized = os.path.realpath(self.archive_base)

                in_main_archive = archive_path_normalized.startswith(archive_base_normalized)

                in_prior_archive = False
                if prior_archive_base:
                    prior_archive_normalized = os.path.realpath(prior_archive_base)
                    in_prior_archive = archive_path_normalized.startswith(prior_archive_normalized)

                if not in_main_archive and not in_prior_archive:
                    raise ValueError(
                        f"CRITICAL: Attempted to edit source file!\n"
                        f"File path: {archive_path}\n"
                        f"Source files must NEVER be modified."
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

                # Apply the edits
                self.worker_logger.info(f"  Applying edits...")
                success, edited_path, error = ImageModifier.apply_edits(
                    archive_path,
                    brightness=edit_state.brightness,
                    contrast=edit_state.contrast,
                    saturation=edit_state.saturation,
                    crop_box=edit_state.crop_box
                )

                if not success:
                    raise Exception(f"Edit failed: {error}")

                self.worker_logger.info(f"  Edited image created: {os.path.basename(edited_path)}")

                # Calculate new hash
                new_hash = hash_file(edited_path)
                new_file_size = os.path.getsize(edited_path)
                self.worker_logger.info(f"  New hash: {new_hash[:16]}..., size: {new_file_size}")

                # Move original to Prior Revision Archive
                self.worker_logger.info("  Moving original to Prior Revision Archive...")

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
                    self.worker_logger.info(f"  Original moved to: {os.path.basename(prior_revision_path)}")
                except Exception as e:
                    self.worker_logger.warning(f"  Move failed, using copy+delete: {e}")
                    try:
                        shutil.copy2(archive_path, prior_revision_path)
                    except PermissionError:
                        shutil.copy(archive_path, prior_revision_path)
                    os.remove(archive_path)
                    self.worker_logger.info(f"  Original copied to: {os.path.basename(prior_revision_path)}")

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

                    self.worker_logger.info("  Database updated with prior revision location")

                # Place edited version in main archive
                self.worker_logger.info("  Placing edited version in main archive...")

                try:
                    shutil.copy2(edited_path, archive_path)
                except PermissionError:
                    shutil.copy(edited_path, archive_path)

                # Verify placement
                if not os.path.exists(archive_path):
                    raise Exception("Edited file not placed in main archive!")

                placed_size = os.path.getsize(archive_path)
                if placed_size != new_file_size:
                    raise Exception(f"Size mismatch: {placed_size} != {new_file_size}")

                self.worker_logger.info(f"  Edited version placed as: {filename}")

                # Clean up temporary edited file
                if os.path.exists(edited_path):
                    os.remove(edited_path)

                # Create revision record in UniquePhotos (v5 schema)
                self.worker_logger.info("  Creating revision record in database...")
                with PhotoDatabase(self.db_path) as db:
                    # Calculate partial hash if needed
                    partial_hash = None
                    partial_hash_bytes = None
                    if new_file_size >= 1048576:  # 1MB threshold
                        partial_hash_bytes = 16384
                        partial_hash = hash_file_partial(archive_path, partial_hash_bytes)

                    # Create new revision record
                    revision_reason = edit_state.get_revision_reason()
                    success = db.create_revision(
                        new_file_hash=new_hash,
                        parent_hash=original_hash,
                        revision_reason=revision_reason,
                        file_path=archive_path,
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

                    self.worker_logger.info(f"  Created revision record: {new_hash[:16]}... (parent: {original_hash[:16]}...)")
                    self.worker_logger.info(f"  Revision reason: {revision_reason}")

                    # Update UnreliableDates table with new hash
                    cursor = db.get_cursor()
                    cursor.execute("""
                        UPDATE UnreliableDates
                        SET file_hash = ?
                        WHERE file_hash = ?
                    """, (new_hash, original_hash))

                    if cursor.rowcount > 0:
                        self.worker_logger.info("  Updated UnreliableDates with new hash")

                # Log to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=archive_path,
                            destination_path=archive_path,
                            file_hash=new_hash,
                            operation='edit_image',
                            status='success',
                            file_size=os.path.getsize(archive_path) if os.path.exists(archive_path) else None
                        )
                    except Exception as audit_error:
                        self.worker_logger.warning(f"  Failed to log audit: {audit_error}")

                success_count += 1
                edited_hashes.append(new_hash)
                self.worker_logger.info(f"File {idx+1} completed successfully")

            except Exception as e:
                error_msg = f"{filename}: {str(e)}"
                self.worker_logger.error(f"File {idx+1} failed: {e}", exc_info=True)
                errors.append(error_msg)

                # Log failure to audit trail
                if audit_manager:
                    try:
                        audit_manager.log_file_operation(
                            session_id=session_id,
                            source_path=archive_path,
                            destination_path=archive_path,
                            file_hash=original_hash,
                            operation='edit_image',
                            status='failed',
                            error_message=str(e)
                        )
                    except Exception as audit_error:
                        self.worker_logger.warning(f"  Failed to log audit failure: {audit_error}")

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
                self.worker_logger.info(f"Audit session ended: {session_id}")
            except Exception as e:
                self.worker_logger.warning(f"Failed to end audit session: {e}")

        # Final summary
        self.worker_logger.info("=" * 80)
        self.worker_logger.info("EDIT PROCESS COMPLETE")
        self.worker_logger.info(f"Successfully edited: {success_count}/{len(self.records)}")
        self.worker_logger.info(f"Failed: {len(errors)}")
        if errors:
            self.worker_logger.info("Errors:")
            for error in errors:
                self.worker_logger.info(f"  - {error}")
        self.worker_logger.info("=" * 80)

        # Emit results
        self.finished.emit({
            'success': success_count,
            'errors': errors,
            'edited_hashes': edited_hashes
        })


class BatchEditWorker(QThread):
    """Background worker for applying the same edits to multiple photos."""

    progress = Signal(int, int, str)  # current, total, filename
    finished = Signal(dict)  # {'success': int, 'errors': list, 'edited_hashes': list}

    def __init__(self, records: List[dict], edit_state: EditState,
                 auto_enhance: bool, db_path: str, archive_base: str, worker_logger):
        """
        Initialize batch edit worker.

        Args:
            records: List of file record dictionaries
            edit_state: Single EditState to apply to all files (ignored if auto_enhance=True)
            auto_enhance: If True, analyze each photo individually
            db_path: Path to database
            archive_base: Base path for archive
            worker_logger: Logger instance
        """
        super().__init__()
        self.records = records
        self.edit_state = edit_state
        self.auto_enhance = auto_enhance
        self.db_path = db_path
        self.archive_base = archive_base
        self.worker_logger = worker_logger
        self.cancelled = False

    def cancel(self):
        """Cancel the operation."""
        self.cancelled = True
        self.worker_logger.info("Batch edit operation cancelled by user")

    def run(self):
        """Execute batch edit operation."""
        from image_modifier import ImageModifier
        from DuplicateFileDetection import PhotoDatabase, hash_file, hash_file_partial
        from database_metadata import DatabaseMetadata
        from audit_manager import AuditManager

        self.worker_logger.info("=" * 80)
        self.worker_logger.info("STARTING BATCH IMAGE EDIT PROCESS")
        self.worker_logger.info(f"Files to edit: {len(self.records)}")
        self.worker_logger.info(f"Auto-enhance mode: {self.auto_enhance}")
        if not self.auto_enhance:
            self.worker_logger.info(f"Edit state: {self.edit_state.to_dict()}")
        self.worker_logger.info("=" * 80)

        # Get Prior Revision Archive location
        db_metadata = DatabaseMetadata(self.db_path)
        prior_archive_base = db_metadata.get_prior_revision_archive_location()

        if not prior_archive_base:
            error_msg = ("Prior Revision Archive not configured. "
                        "Please set location in Archive Settings tab.")
            self.worker_logger.error(error_msg)
            self.finished.emit({'success': 0, 'errors': [error_msg], 'edited_hashes': []})
            return

        if not os.path.exists(prior_archive_base):
            error_msg = f"Prior Revision Archive path does not exist: {prior_archive_base}"
            self.worker_logger.error(error_msg)
            self.finished.emit({'success': 0, 'errors': [error_msg], 'edited_hashes': []})
            return

        success_count = 0
        errors = []
        edited_hashes = []

        # Initialize audit manager
        try:
            audit_manager = AuditManager(self.db_path)
            session_id = audit_manager.start_session(
                operation_mode='batch_edit_image',
                source_directories=[],
                destination_directory=self.archive_base
            )
        except Exception as e:
            self.worker_logger.warning(f"Failed to initialize audit manager: {e}")
            audit_manager = None
            session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        for idx, record in enumerate(self.records):
            if self.cancelled:
                break

            archive_path = record.get('archive_path') or record.get('file_name')
            if not archive_path:
                errors.append(f"File {idx+1}: No archive path")
                continue

            filename = os.path.basename(archive_path)
            self.progress.emit(idx + 1, len(self.records), filename)

            original_hash = None

            try:
                if not os.path.exists(archive_path):
                    raise FileNotFoundError(f"Archive file not found: {archive_path}")

                # Determine edit state for this file
                if self.auto_enhance:
                    # Analyze this specific image
                    success, adjustments, error = ImageModifier.auto_enhance(archive_path)
                    if not success:
                        raise Exception(f"Auto-enhance analysis failed: {error}")

                    current_edit_state = EditState(
                        brightness=adjustments['brightness'],
                        contrast=adjustments['contrast'],
                        saturation=adjustments['saturation']
                    )
                    self.worker_logger.info(f"  Auto-enhance: {adjustments}")
                else:
                    current_edit_state = self.edit_state

                if not current_edit_state.has_changes():
                    self.worker_logger.info(f"  Skipping {filename} - no changes needed")
                    continue

                # Calculate original hash
                original_hash = hash_file(archive_path)

                # Get original metadata
                with PhotoDatabase(self.db_path) as db:
                    cursor = db.get_cursor()
                    cursor.execute("""
                        SELECT create_datetime, create_year, create_month, create_day, file_size
                        FROM UniquePhotos
                        WHERE file_hash = ?
                    """, (original_hash,))

                    result = cursor.fetchone()
                    if not result:
                        raise Exception(f"File not found in database")

                    create_datetime, create_year, create_month, create_day, original_file_size = result

                # Apply edits
                success, edited_path, error = ImageModifier.apply_edits(
                    archive_path,
                    brightness=current_edit_state.brightness,
                    contrast=current_edit_state.contrast,
                    saturation=current_edit_state.saturation,
                    crop_box=current_edit_state.crop_box
                )

                if not success:
                    raise Exception(f"Edit failed: {error}")

                # Calculate new hash
                new_hash = hash_file(edited_path)
                new_file_size = os.path.getsize(edited_path)

                # Move original to prior archive
                prior_revision_path = generate_prior_revision_path(
                    archive_path, original_hash, prior_archive_base
                )
                os.makedirs(os.path.dirname(prior_revision_path), exist_ok=True)

                try:
                    shutil.move(archive_path, prior_revision_path)
                except Exception:
                    shutil.copy2(archive_path, prior_revision_path)
                    os.remove(archive_path)

                # Update original location in database
                with PhotoDatabase(self.db_path) as db:
                    cursor = db.get_cursor()
                    cursor.execute("""
                        UPDATE UniquePhotos SET file_name = ? WHERE file_hash = ?
                    """, (prior_revision_path, original_hash))

                # Place edited file in main archive
                shutil.copy2(edited_path, archive_path)
                os.remove(edited_path)

                # Create revision record
                with PhotoDatabase(self.db_path) as db:
                    partial_hash = None
                    partial_hash_bytes = None
                    if new_file_size >= 1048576:
                        partial_hash_bytes = 16384
                        partial_hash = hash_file_partial(archive_path, partial_hash_bytes)

                    revision_reason = 'auto_enhance' if self.auto_enhance else current_edit_state.get_revision_reason()
                    db.create_revision(
                        new_file_hash=new_hash,
                        parent_hash=original_hash,
                        revision_reason=revision_reason,
                        file_path=archive_path,
                        file_size=new_file_size,
                        create_datetime=create_datetime,
                        create_year=create_year,
                        create_month=create_month,
                        create_day=create_day,
                        partial_hash=partial_hash,
                        partial_hash_bytes=partial_hash_bytes
                    )

                    cursor = db.get_cursor()
                    cursor.execute("""
                        UPDATE UnreliableDates SET file_hash = ? WHERE file_hash = ?
                    """, (new_hash, original_hash))

                success_count += 1
                edited_hashes.append(new_hash)
                self.worker_logger.info(f"  {filename} edited successfully")

            except Exception as e:
                errors.append(f"{filename}: {str(e)}")
                self.worker_logger.error(f"  {filename} failed: {e}")

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
            except Exception:
                pass

        self.worker_logger.info("=" * 80)
        self.worker_logger.info(f"BATCH EDIT COMPLETE: {success_count}/{len(self.records)} successful")
        self.worker_logger.info("=" * 80)

        self.finished.emit({
            'success': success_count,
            'errors': errors,
            'edited_hashes': edited_hashes
        })
