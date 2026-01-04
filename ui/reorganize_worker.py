"""
Reorganization Worker

Handles reorganizing files with corrected dates to proper date-based folders.
"""

from PySide6.QtWidgets import QProgressDialog, QMessageBox
from PySide6.QtCore import Qt
import os
import shutil
import logging
from datetime import datetime
from organization_template import OrganizationTemplate

logger = logging.getLogger(__name__)


def reorganize_files(parent_widget, db_metadata, files_to_reorganize):
    """
    Reorganize files with corrected dates.

    Args:
        parent_widget: Parent widget for progress dialog
        db_metadata: DatabaseMetadata instance
        files_to_reorganize: List of file records needing reorganization

    Returns:
        tuple: (success_count, failed_count)
    """
    if not files_to_reorganize:
        return 0, 0

    # Create progress dialog
    progress = QProgressDialog(
        "Reorganizing files...",
        "Cancel",
        0,
        len(files_to_reorganize),
        parent_widget
    )
    progress.setWindowModality(Qt.WindowModal)
    progress.setMinimumDuration(0)
    progress.setWindowTitle("Reorganizing Files")

    success_count = 0
    failed_count = 0

    # Get organization template and archive location
    try:
        template_str = db_metadata.get_organization_template()
        archive_base = db_metadata.get_archive_location()

        if not archive_base:
            QMessageBox.critical(
                parent_widget,
                "Error",
                "No archive location configured for this database."
            )
            return 0, len(files_to_reorganize)

    except Exception as e:
        logger.error(f"Failed to get organization settings: {e}")
        QMessageBox.critical(
            parent_widget,
            "Error",
            f"Failed to get organization settings:\n\n{str(e)}"
        )
        return 0, len(files_to_reorganize)

    # Process each file
    for idx, record in enumerate(files_to_reorganize):
        if progress.wasCanceled():
            logger.info("Reorganization cancelled by user")
            break

        # Update progress
        progress.setValue(idx)
        filename = os.path.basename(record['source_path'])
        progress.setLabelText(f"Reorganizing {filename}...")

        try:
            # Parse corrected date
            corrected_date = record['corrected_date']  # Format: "YYYY-MM-DD"
            year, month, day = corrected_date.split('-')

            # Generate new folder path using template
            # OrganizationTemplate.parse() is a classmethod, takes template string and datetime
            file_date = datetime(int(year), int(month), int(day))
            folder_path = OrganizationTemplate.parse(template_str, file_date)

            # Build full new path
            new_archive_path = os.path.join(archive_base, folder_path, filename)

            # Get old archive path
            old_archive_path = record['archive_path']

            if not old_archive_path or not os.path.exists(old_archive_path):
                logger.warning(f"Old archive file not found: {old_archive_path}")
                # File might not have been organized yet, skip
                success_count += 1
                db_metadata.mark_reorganized(record['file_hash'])
                continue

            # Check if old and new paths are the same
            if os.path.normpath(old_archive_path) == os.path.normpath(new_archive_path):
                logger.info(f"File already in correct location: {filename}")
                db_metadata.mark_reorganized(record['file_hash'])
                success_count += 1
                continue

            # Create new directory if needed
            new_dir = os.path.dirname(new_archive_path)
            os.makedirs(new_dir, exist_ok=True)

            # Handle filename collision
            if os.path.exists(new_archive_path):
                # Generate unique filename
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(new_archive_path):
                    new_filename = f"{base}_{counter}{ext}"
                    new_archive_path = os.path.join(new_dir, new_filename)
                    counter += 1
                logger.info(f"Renamed to avoid collision: {new_filename}")

            # Save original archive path if not already saved
            if not record.get('original_archive_path'):
                try:
                    import sqlite3
                    with sqlite3.connect(db_metadata.database_path) as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            UPDATE UnreliableDates
                            SET original_archive_path = ?
                            WHERE file_hash = ? AND original_archive_path IS NULL
                        """, (old_archive_path, record['file_hash']))
                        conn.commit()
                        logger.debug(f"Saved original archive path: {old_archive_path}")
                except Exception as e:
                    logger.warning(f"Could not save original archive path: {e}")

            # Copy file to new location
            shutil.copy2(old_archive_path, new_archive_path)

            # Verify copy succeeded
            if not os.path.exists(new_archive_path):
                raise Exception("Copy verification failed - file not found at new location")

            # Verify file size matches
            old_size = os.path.getsize(old_archive_path)
            new_size = os.path.getsize(new_archive_path)

            if old_size != new_size:
                raise Exception(f"Copy verification failed - size mismatch ({old_size} vs {new_size})")

            # Delete old file
            os.remove(old_archive_path)

            # Clean up empty directories
            try:
                old_dir = os.path.dirname(old_archive_path)
                # Try to remove directory (will only succeed if empty)
                os.rmdir(old_dir)
                logger.info(f"Removed empty directory: {old_dir}")

                # Try parent directories too
                parent_dir = os.path.dirname(old_dir)
                while parent_dir and parent_dir != archive_base:
                    try:
                        os.rmdir(parent_dir)
                        logger.info(f"Removed empty directory: {parent_dir}")
                        parent_dir = os.path.dirname(parent_dir)
                    except OSError:
                        # Directory not empty, stop
                        break
            except OSError:
                # Directory not empty, that's fine
                pass

            # Update database with new path
            db_metadata.update_photo_path(record['file_hash'], new_archive_path)

            # Mark as reorganized
            db_metadata.mark_reorganized(record['file_hash'])

            success_count += 1
            logger.info(f"Successfully reorganized {filename}: {old_archive_path} -> {new_archive_path}")

        except Exception as e:
            logger.error(f"Failed to reorganize {record.get('source_path', 'unknown')}: {e}")
            failed_count += 1

    progress.setValue(len(files_to_reorganize))

    return success_count, failed_count


def verify_reorganization_safe(parent_widget, db_metadata, files_to_reorganize):
    """
    Verify that reorganization can be performed safely.

    Args:
        parent_widget: Parent widget for dialogs
        db_metadata: DatabaseMetadata instance
        files_to_reorganize: List of file records

    Returns:
        bool: True if safe to proceed, False otherwise
    """
    # Check archive location exists
    archive_base = db_metadata.get_archive_location()

    if not archive_base:
        QMessageBox.critical(
            parent_widget,
            "Error",
            "No archive location configured for this database."
        )
        return False

    if not os.path.exists(archive_base):
        QMessageBox.critical(
            parent_widget,
            "Error",
            f"Archive location does not exist:\n\n{archive_base}\n\n"
            f"Cannot reorganize files."
        )
        return False

    # Check if archive location is writable
    if not os.access(archive_base, os.W_OK):
        QMessageBox.critical(
            parent_widget,
            "Permission Error",
            f"Archive location is not writable:\n\n{archive_base}\n\n"
            f"Cannot reorganize files."
        )
        return False

    # Check if any files have missing archive paths
    missing_count = sum(1 for record in files_to_reorganize
                       if not record.get('archive_path') or not os.path.exists(record['archive_path']))

    if missing_count > 0:
        response = QMessageBox.question(
            parent_widget,
            "Missing Files",
            f"{missing_count} file(s) cannot be found in the archive.\n\n"
            f"These files may not have been organized yet.\n"
            f"They will be skipped during reorganization.\n\n"
            f"Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if response == QMessageBox.No:
            return False

    return True
