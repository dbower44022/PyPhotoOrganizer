"""
Date Correction Dialog

Dialog for correcting dates on single or multiple files.
Supports batch operations with same date or sequential dates.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QCheckBox, QRadioButton,
                               QButtonGroup, QGroupBox, QMessageBox, QProgressDialog)
from PySide6.QtCore import Qt
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)


class DateCorrectionDialog(QDialog):
    """Dialog for correcting file dates."""

    def __init__(self, parent, records, batch_mode=False):
        """
        Initialize date correction dialog.

        Args:
            parent: Parent widget
            records: List of record dictionaries or single record
            batch_mode: True for batch mode, False for single file mode
        """
        super().__init__(parent)
        self.records = records if isinstance(records, list) else [records]
        self.batch_mode = batch_mode
        self.db_metadata = parent.db_metadata if hasattr(parent, 'db_metadata') else None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Batch Correct Dates" if self.batch_mode else "Correct Date")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout()

        # Header
        if self.batch_mode:
            header = QLabel(f"Batch Correct Dates ({len(self.records)} files)")
        else:
            record = self.records[0]
            filename = os.path.basename(record['source_path'])
            header = QLabel(f"Correct Date - {filename}")

        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Current date info (for single file mode)
        if not self.batch_mode:
            record = self.records[0]
            info_label = QLabel(f"Current Date: {record['original_date'] or 'Unknown'}")
            info_label.setStyleSheet("padding: 5px; color: #666;")
            layout.addWidget(info_label)

        # Batch mode options
        if self.batch_mode:
            mode_group = QGroupBox("Correction Method")
            mode_layout = QVBoxLayout()

            self.batch_mode_group = QButtonGroup()

            self.same_date_radio = QRadioButton("Assign same date to all files")
            self.batch_mode_group.addButton(self.same_date_radio, 0)
            mode_layout.addWidget(self.same_date_radio)

            self.sequential_radio = QRadioButton("Assign sequential dates (increment by 1 day)")
            self.batch_mode_group.addButton(self.sequential_radio, 1)
            mode_layout.addWidget(self.sequential_radio)

            self.same_date_radio.setChecked(True)

            mode_group.setLayout(mode_layout)
            layout.addWidget(mode_group)

        # Date input group
        date_group = QGroupBox("Starting Date" if self.batch_mode else "New Date")
        date_layout = QVBoxLayout()

        # Date spinboxes
        spinbox_layout = QHBoxLayout()

        # Year
        year_layout = QVBoxLayout()
        year_label = QLabel("Year")
        year_layout.addWidget(year_label)
        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)  # Extended range for old photos and future-proofing
        self.year_spin.setValue(datetime.now().year)
        self.year_spin.setMinimumWidth(80)
        year_layout.addWidget(self.year_spin)
        spinbox_layout.addLayout(year_layout)

        # Month
        month_layout = QVBoxLayout()
        month_label = QLabel("Month")
        month_layout.addWidget(month_label)
        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        self.month_spin.setValue(datetime.now().month)
        self.month_spin.setMinimumWidth(60)
        month_layout.addWidget(self.month_spin)
        spinbox_layout.addLayout(month_layout)

        # Day
        day_layout = QVBoxLayout()
        day_label = QLabel("Day")
        day_layout.addWidget(day_label)
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(datetime.now().day)
        self.day_spin.setMinimumWidth(60)
        day_layout.addWidget(self.day_spin)
        spinbox_layout.addLayout(day_layout)

        spinbox_layout.addStretch()

        date_layout.addLayout(spinbox_layout)

        # Connect month/year changes to update day range
        self.year_spin.valueChanged.connect(self.update_day_range)
        self.month_spin.valueChanged.connect(self.update_day_range)

        # Info text for batch sequential mode
        if self.batch_mode:
            self.sequential_info = QLabel("(Sequential mode increments by 1 day for each file)")
            self.sequential_info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
            date_layout.addWidget(self.sequential_info)

        date_group.setLayout(date_layout)
        layout.addWidget(date_group)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout()

        self.write_exif_checkbox = QCheckBox("Write EXIF to source file")
        self.write_exif_checkbox.setChecked(True)
        self.write_exif_checkbox.setToolTip("Write corrected date to image EXIF data")
        options_layout.addWidget(self.write_exif_checkbox)

        self.mark_reorganize_checkbox = QCheckBox("Mark for reorganization")
        self.mark_reorganize_checkbox.setChecked(True)
        self.mark_reorganize_checkbox.setToolTip("Mark file to be moved to correct date folder")
        options_layout.addWidget(self.mark_reorganize_checkbox)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setDefault(True)
        self.apply_btn.clicked.connect(self.apply_corrections)
        button_layout.addWidget(self.apply_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Center on parent
        if self.parent():
            parent_geometry = self.parent().frameGeometry()
            dialog_geometry = self.frameGeometry()
            center_point = parent_geometry.center()
            dialog_geometry.moveCenter(center_point)
            self.move(dialog_geometry.topLeft())

    def update_day_range(self):
        """Update day spinbox range based on selected month and year."""
        year = self.year_spin.value()
        month = self.month_spin.value()

        # Determine days in month
        if month in [1, 3, 5, 7, 8, 10, 12]:
            max_days = 31
        elif month in [4, 6, 9, 11]:
            max_days = 30
        else:  # February
            # Check for leap year
            if (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0):
                max_days = 29
            else:
                max_days = 28

        # Update day spinbox max
        current_day = self.day_spin.value()
        self.day_spin.setMaximum(max_days)

        # Adjust current day if it's now out of range
        if current_day > max_days:
            self.day_spin.setValue(max_days)

    def validate_date(self):
        """
        Validate the entered date.

        Returns:
            tuple: (valid, error_message)
        """
        year = self.year_spin.value()
        month = self.month_spin.value()
        day = self.day_spin.value()

        try:
            # Try to create datetime object
            datetime(year, month, day)
        except ValueError as e:
            return False, f"Invalid date: {str(e)}"

        # Check for suspicious dates
        current_year = datetime.now().year

        if year < 1990:
            response = QMessageBox.question(
                self,
                "Older Date",
                f"The year {year} is before 1990 (before consumer digital cameras).\n\n"
                f"This is fine for scanned photos or film camera photos.\n\n"
                f"Continue with this date?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes  # Default to Yes for scanned photos
            )
            if response == QMessageBox.No:
                return False, "Date validation cancelled by user"

        if year > current_year:
            response = QMessageBox.question(
                self,
                "Future Date",
                f"The year {year} is in the future.\n\n"
                f"Are you sure this is correct?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if response == QMessageBox.No:
                return False, "Date validation cancelled by user"

        return True, ""

    def apply_corrections(self):
        """Apply date corrections to selected files."""
        logger.info("=" * 80)
        logger.info("STARTING DATE CORRECTION PROCESS")
        logger.info(f"Batch mode: {self.batch_mode}, Files to process: {len(self.records)}")

        # Validate date
        valid, error_msg = self.validate_date()
        if not valid:
            logger.error(f"Date validation failed: {error_msg}")
            if error_msg:
                msg_box = QMessageBox(QMessageBox.Warning, "Validation Error", error_msg, QMessageBox.Ok, self)
                self._center_dialog(msg_box)
                msg_box.exec()
            return

        if not self.db_metadata:
            logger.critical("No database connection available")
            msg_box = QMessageBox(QMessageBox.Critical, "Error", "No database connection", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        # Get date components
        year = self.year_spin.value()
        month = self.month_spin.value()
        day = self.day_spin.value()
        logger.info(f"Correction date: {year:04d}-{month:02d}-{day:02d}")

        # Get options
        write_exif = self.write_exif_checkbox.isChecked()
        mark_for_reorg = self.mark_reorganize_checkbox.isChecked()
        logger.info(f"Options - Write EXIF: {write_exif}, Mark for reorganization: {mark_for_reorg}")

        # Determine batch mode
        sequential = False
        if self.batch_mode:
            sequential = self.sequential_radio.isChecked()
            logger.info(f"Batch mode - Sequential: {sequential}")

        # Create progress dialog
        progress = QProgressDialog(
            "Correcting dates...",
            "Cancel",
            0,
            len(self.records),
            self
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)

        success_count = 0
        error_count = 0
        exif_source_success = 0
        exif_archive_success = 0
        exif_failures = []
        db_failures = []
        current_date = datetime(year, month, day)

        for idx, record in enumerate(self.records):
            if progress.wasCanceled():
                logger.warning(f"Date correction cancelled by user at file {idx + 1}/{len(self.records)}")
                break

            progress.setValue(idx)
            filename = os.path.basename(record['source_path'])
            progress.setLabelText(f"Processing {filename}...")

            logger.info("-" * 60)
            logger.info(f"Processing file {idx + 1}/{len(self.records)}: {record['source_path']}")
            logger.info(f"File hash: {record.get('file_hash', 'UNKNOWN')[:16]}...")

            try:
                # Calculate date for this file
                if sequential and idx > 0:
                    current_date = current_date + timedelta(days=1)
                    logger.info(f"Sequential mode - incremented date to: {current_date.strftime('%Y-%m-%d')}")

                # Format date
                corrected_date = current_date.strftime('%Y-%m-%d')
                year_str = f"{current_date.year}"
                month_str = f"{current_date.month:02d}"
                day_str = f"{current_date.day:02d}"
                logger.info(f"Applying correction: {corrected_date} (from original: {record.get('original_date', 'UNKNOWN')})")

                # Write EXIF if requested
                if write_exif:
                    logger.info("Writing EXIF data to files...")
                    from exif_writer import write_exif_date

                    # Write to source file if it exists
                    source_exif_written = False
                    if os.path.exists(record['source_path']):
                        logger.info(f"  → Source file: {record['source_path']}")
                        try:
                            exif_success = write_exif_date(
                                record['source_path'],
                                year_str,
                                month_str,
                                day_str
                            )

                            if exif_success:
                                logger.info(f"  ✓ EXIF written to source file successfully")
                                exif_source_success += 1
                                source_exif_written = True
                            else:
                                logger.error(f"  ✗ EXIF write FAILED for source file (no exception, returned False)")
                                exif_failures.append(f"{filename} (source)")
                        except Exception as e:
                            logger.error(f"  ✗ EXIF write exception for source: {e}", exc_info=True)
                            exif_failures.append(f"{filename} (source): {str(e)}")
                    else:
                        logger.warning(f"  ⚠ Source file not found: {record['source_path']}")

                    # CRITICAL: Also write to archive file (this is what gets reorganized!)
                    archive_exif_written = False
                    if record.get('archive_path'):
                        if os.path.exists(record['archive_path']):
                            logger.info(f"  → Archive file: {record['archive_path']}")
                            try:
                                exif_success = write_exif_date(
                                    record['archive_path'],
                                    year_str,
                                    month_str,
                                    day_str
                                )

                                if exif_success:
                                    logger.info(f"  ✓ EXIF written to archive file successfully")
                                    exif_archive_success += 1
                                    archive_exif_written = True
                                else:
                                    logger.error(f"  ✗ EXIF write FAILED for archive file (no exception, returned False)")
                                    exif_failures.append(f"{filename} (archive)")
                            except Exception as e:
                                logger.error(f"  ✗ EXIF write exception for archive: {e}", exc_info=True)
                                exif_failures.append(f"{filename} (archive): {str(e)}")
                        else:
                            logger.warning(f"  ⚠ Archive file not found: {record.get('archive_path', 'None')}")
                    else:
                        logger.warning(f"  ⚠ No archive_path in record for {filename}")

                    # Summary for this file
                    if source_exif_written or archive_exif_written:
                        logger.info(f"  Summary: EXIF updated - Source: {source_exif_written}, Archive: {archive_exif_written}")
                    else:
                        logger.warning(f"  Summary: NO EXIF data was written for this file!")
                else:
                    logger.info("EXIF writing skipped (checkbox not checked)")

                # Update database
                logger.info(f"Updating database for file_hash: {record['file_hash'][:16]}...")
                try:
                    self.db_metadata.update_corrected_date(
                        record['file_hash'],
                        corrected_date,
                        mark_for_reorganization=mark_for_reorg
                    )
                    logger.info(f"  ✓ Database updated successfully")
                except Exception as e:
                    logger.error(f"  ✗ Database update FAILED: {e}", exc_info=True)
                    db_failures.append(f"{filename}: {str(e)}")
                    raise  # Re-raise to trigger outer exception handler

                success_count += 1
                logger.info(f"✓ File {idx + 1} completed successfully")

            except Exception as e:
                logger.error(f"✗ EXCEPTION processing {record['source_path']}: {e}", exc_info=True)
                error_count += 1

        progress.setValue(len(self.records))

        # Log final summary
        logger.info("=" * 80)
        logger.info("DATE CORRECTION PROCESS COMPLETED")
        logger.info(f"Total files processed: {len(self.records)}")
        logger.info(f"Successful corrections: {success_count}")
        logger.info(f"Failed corrections: {error_count}")
        if write_exif:
            logger.info(f"EXIF written to source files: {exif_source_success}/{len(self.records)}")
            logger.info(f"EXIF written to archive files: {exif_archive_success}/{len(self.records)}")
            if exif_failures:
                logger.error(f"EXIF write failures ({len(exif_failures)}):")
                for failure in exif_failures:
                    logger.error(f"  - {failure}")
        if db_failures:
            logger.error(f"Database update failures ({len(db_failures)}):")
            for failure in db_failures:
                logger.error(f"  - {failure}")
        logger.info("=" * 80)

        # Only show completion dialog if there were errors (to avoid slowing down bulk operations)
        # Success information is already logged in detail
        if error_count > 0 or exif_failures or db_failures:
            details = []
            details.append(f"Successfully corrected: {success_count} file(s)")
            details.append(f"Failed: {error_count} file(s)")

            if write_exif:
                details.append("")
                details.append("EXIF Writing:")
                details.append(f"  Source files: {exif_source_success}/{len(self.records)}")
                details.append(f"  Archive files: {exif_archive_success}/{len(self.records)}")
                if exif_failures:
                    details.append(f"  Failures: {len(exif_failures)}")

            if db_failures:
                details.append("")
                details.append(f"Database failures: {len(db_failures)}")

            details.append("")
            details.append("Check logs for detailed error information.")

            msg_box = QMessageBox(
                QMessageBox.Warning,
                "Corrections Complete with Issues",
                "\n".join(details),
                QMessageBox.Ok,
                self
            )
            self._center_dialog(msg_box)
            msg_box.exec()

        # No success dialog shown - allows rapid bulk corrections without interruption
        self.accept()

    def _center_dialog(self, dialog):
        """Center a dialog on the parent window."""
        if self.parent():
            parent_geo = self.parent().geometry()
            dialog_geo = dialog.geometry()
            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2
            dialog.move(x, y)
