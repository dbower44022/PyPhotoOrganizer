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
    logger.info("=" * 80)
    logger.info("STARTING FILE REORGANIZATION PROCESS")
    logger.info(f"Files to reorganize: {len(files_to_reorganize)}")

    if not files_to_reorganize:
        logger.warning("No files to reorganize")
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

        logger.info(f"Organization template: {template_str}")
        logger.info(f"Archive base location: {archive_base}")

        if not archive_base:
            logger.critical("No archive location configured for this database")
            QMessageBox.critical(
                parent_widget,
                "Error",
                "No archive location configured for this database."
            )
            return 0, len(files_to_reorganize)

        if not os.path.exists(archive_base):
            logger.critical(f"Archive location does not exist: {archive_base}")
            QMessageBox.critical(
                parent_widget,
                "Error",
                f"Archive location does not exist:\n\n{archive_base}"
            )
            return 0, len(files_to_reorganize)

    except Exception as e:
        logger.error(f"Failed to get organization settings: {e}", exc_info=True)
        QMessageBox.critical(
            parent_widget,
            "Error",
            f"Failed to get organization settings:\n\n{str(e)}"
        )
        return 0, len(files_to_reorganize)

    # Process each file
    for idx, record in enumerate(files_to_reorganize):
        if progress.wasCanceled():
            logger.warning(f"Reorganization cancelled by user at file {idx + 1}/{len(files_to_reorganize)}")
            break

        # Update progress
        progress.setValue(idx)
        filename = os.path.basename(record['source_path'])
        progress.setLabelText(f"Reorganizing {filename}...")

        logger.info("-" * 60)
        logger.info(f"Reorganizing file {idx + 1}/{len(files_to_reorganize)}: {filename}")
        logger.info(f"File hash: {record['file_hash'][:16]}...")
        logger.info(f"Original date: {record.get('original_date', 'UNKNOWN')}")
        logger.info(f"Corrected date: {record.get('corrected_date', 'UNKNOWN')}")

        try:
            # Parse corrected date
            corrected_date = record['corrected_date']  # Format: "YYYY-MM-DD"
            year, month, day = corrected_date.split('-')
            logger.info(f"Parsed date components: {year}-{month}-{day}")

            # Generate new folder path using template
            # OrganizationTemplate.parse() is a classmethod, takes template string and datetime
            file_date = datetime(int(year), int(month), int(day))
            folder_path = OrganizationTemplate.parse(template_str, file_date)
            logger.info(f"Generated folder path from template: {folder_path}")

            # Build full new path
            new_archive_path = os.path.join(archive_base, folder_path, filename)
            logger.info(f"New archive path: {new_archive_path}")

            # Get old archive path
            old_archive_path = record['archive_path']
            logger.info(f"Old archive path: {old_archive_path}")

            if not old_archive_path:
                logger.error(f"✗ Old archive path is NULL for {filename}")
                logger.error(f"  This file may not have been organized yet")
                logger.error(f"  Marking as reorganized and skipping")
                success_count += 1
                db_metadata.mark_reorganized(record['file_hash'])
                continue

            if not os.path.exists(old_archive_path):
                logger.error(f"✗ Old archive file not found: {old_archive_path}")
                logger.error(f"  File may have been moved or deleted")
                logger.error(f"  Marking as reorganized and skipping")
                success_count += 1
                db_metadata.mark_reorganized(record['file_hash'])
                continue

            # Verify file is accessible
            if not os.access(old_archive_path, os.R_OK):
                logger.error(f"✗ Old archive file is not readable: {old_archive_path}")
                logger.error(f"  Permission denied or file locked")
                failed_count += 1
                continue

            # Check if old and new paths are the same
            if os.path.normpath(old_archive_path) == os.path.normpath(new_archive_path):
                logger.info(f"✓ File already in correct location: {filename}")
                logger.info(f"  Marking as reorganized")
                db_metadata.mark_reorganized(record['file_hash'])
                success_count += 1
                continue

            logger.info(f"Moving file:")
            logger.info(f"  FROM: {old_archive_path}")
            logger.info(f"  TO:   {new_archive_path}")

            # Create new directory if needed
            new_dir = os.path.dirname(new_archive_path)
            logger.info(f"Creating directory (if needed): {new_dir}")
            os.makedirs(new_dir, exist_ok=True)
            logger.info(f"  ✓ Directory ready")

            # Handle filename collision
            original_new_path = new_archive_path
            if os.path.exists(new_archive_path):
                logger.warning(f"⚠ File collision detected: {new_archive_path}")
                # Generate unique filename
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(new_archive_path):
                    new_filename = f"{base}_{counter}{ext}"
                    new_archive_path = os.path.join(new_dir, new_filename)
                    counter += 1
                logger.info(f"  Renamed to avoid collision: {new_filename}")
                logger.info(f"  New path: {new_archive_path}")

            # Save original archive path if not already saved
            if not record.get('original_archive_path'):
                logger.info(f"Saving original archive path to database...")
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
                        logger.info(f"  ✓ Original archive path saved")
                except Exception as e:
                    logger.error(f"  ✗ Could not save original archive path: {e}", exc_info=True)
            else:
                logger.info(f"Original archive path already saved: {record.get('original_archive_path')}")

            # Copy file to new location
            logger.info(f"Copying file...")
            old_size = os.path.getsize(old_archive_path)
            logger.info(f"  Source size: {old_size:,} bytes")
            shutil.copy2(old_archive_path, new_archive_path)
            logger.info(f"  ✓ Copy completed")

            # Verify copy succeeded
            if not os.path.exists(new_archive_path):
                logger.error(f"  ✗ VERIFICATION FAILED: File not found at new location")
                raise Exception("Copy verification failed - file not found at new location")

            # Verify file size matches
            new_size = os.path.getsize(new_archive_path)
            logger.info(f"  Destination size: {new_size:,} bytes")

            if old_size != new_size:
                logger.error(f"  ✗ SIZE MISMATCH: {old_size:,} vs {new_size:,}")
                raise Exception(f"Copy verification failed - size mismatch ({old_size} vs {new_size})")

            logger.info(f"  ✓ Size verification passed")

            # Delete old file
            logger.info(f"Deleting old file...")
            os.remove(old_archive_path)
            logger.info(f"  ✓ Old file deleted")

            # Clean up empty directories
            logger.info(f"Cleaning up empty directories...")
            dirs_removed = 0
            try:
                old_dir = os.path.dirname(old_archive_path)
                # Try to remove directory (will only succeed if empty)
                os.rmdir(old_dir)
                logger.info(f"  ✓ Removed empty directory: {old_dir}")
                dirs_removed += 1

                # Try parent directories too
                parent_dir = os.path.dirname(old_dir)
                while parent_dir and parent_dir != archive_base:
                    try:
                        os.rmdir(parent_dir)
                        logger.info(f"  ✓ Removed empty directory: {parent_dir}")
                        dirs_removed += 1
                        parent_dir = os.path.dirname(parent_dir)
                    except OSError:
                        # Directory not empty, stop
                        logger.info(f"  ℹ Directory not empty (stopped cleanup): {parent_dir}")
                        break
            except OSError as e:
                # Directory not empty, that's fine
                logger.info(f"  ℹ Directory not empty: {old_dir}")

            if dirs_removed > 0:
                logger.info(f"  Removed {dirs_removed} empty director{'y' if dirs_removed == 1 else 'ies'}")

            # Update database with new path
            logger.info(f"Updating database...")
            try:
                db_metadata.update_photo_path(record['file_hash'], new_archive_path)
                logger.info(f"  ✓ Updated UniquePhotos and UnreliableDates tables")
            except Exception as e:
                logger.error(f"  ✗ Database update failed: {e}", exc_info=True)
                raise

            # Mark as reorganized
            try:
                db_metadata.mark_reorganized(record['file_hash'])
                logger.info(f"  ✓ Marked as reorganized (needs_reorganization=0)")
            except Exception as e:
                logger.error(f"  ✗ Failed to mark as reorganized: {e}", exc_info=True)
                raise

            success_count += 1
            logger.info(f"✓✓✓ FILE REORGANIZATION COMPLETED SUCCESSFULLY ✓✓✓")
            logger.info(f"    {old_archive_path}")
            logger.info(f"    → {new_archive_path}")

        except Exception as e:
            logger.error(f"✗✗✗ REORGANIZATION FAILED ✗✗✗")
            logger.error(f"File: {record.get('source_path', 'unknown')}")
            logger.error(f"Error: {e}", exc_info=True)
            failed_count += 1

    progress.setValue(len(files_to_reorganize))

    # Log final summary
    logger.info("=" * 80)
    logger.info("FILE REORGANIZATION PROCESS COMPLETED")
    logger.info(f"Total files: {len(files_to_reorganize)}")
    logger.info(f"Successfully reorganized: {success_count}")
    logger.info(f"Failed: {failed_count}")
    if success_count > 0:
        success_rate = (success_count / len(files_to_reorganize)) * 100
        logger.info(f"Success rate: {success_rate:.1f}%")
    logger.info("=" * 80)

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
