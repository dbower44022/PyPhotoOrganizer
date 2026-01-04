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
        # Validate date
        valid, error_msg = self.validate_date()
        if not valid:
            if error_msg:
                QMessageBox.warning(self, "Validation Error", error_msg)
            return

        if not self.db_metadata:
            QMessageBox.critical(self, "Error", "No database connection")
            return

        # Get date components
        year = self.year_spin.value()
        month = self.month_spin.value()
        day = self.day_spin.value()

        # Get options
        write_exif = self.write_exif_checkbox.isChecked()
        mark_for_reorg = self.mark_reorganize_checkbox.isChecked()

        # Determine batch mode
        sequential = False
        if self.batch_mode:
            sequential = self.sequential_radio.isChecked()

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
        current_date = datetime(year, month, day)

        for idx, record in enumerate(self.records):
            if progress.wasCanceled():
                break

            progress.setValue(idx)
            progress.setLabelText(f"Processing {os.path.basename(record['source_path'])}...")

            try:
                # Calculate date for this file
                if sequential and idx > 0:
                    current_date = current_date + timedelta(days=1)

                # Format date
                corrected_date = current_date.strftime('%Y-%m-%d')
                year_str = f"{current_date.year}"
                month_str = f"{current_date.month:02d}"
                day_str = f"{current_date.day:02d}"

                # Write EXIF if requested
                if write_exif:
                    from exif_writer import write_exif_date

                    # Write to source file if it exists
                    if os.path.exists(record['source_path']):
                        exif_success = write_exif_date(
                            record['source_path'],
                            year_str,
                            month_str,
                            day_str
                        )

                        if not exif_success:
                            logger.warning(f"Failed to write EXIF for source: {record['source_path']}")
                        else:
                            logger.info(f"Updated EXIF in source file: {record['source_path']}")
                    else:
                        logger.warning(f"Source file not found: {record['source_path']}")

                    # CRITICAL: Also write to archive file (this is what gets reorganized!)
                    if record.get('archive_path') and os.path.exists(record['archive_path']):
                        exif_success = write_exif_date(
                            record['archive_path'],
                            year_str,
                            month_str,
                            day_str
                        )

                        if not exif_success:
                            logger.warning(f"Failed to write EXIF for archive: {record['archive_path']}")
                        else:
                            logger.info(f"Updated EXIF in archive file: {record['archive_path']}")
                    else:
                        logger.warning(f"Archive file not found: {record.get('archive_path', 'None')}")

                # Update database
                self.db_metadata.update_corrected_date(
                    record['file_hash'],
                    corrected_date,
                    mark_for_reorganization=mark_for_reorg
                )

                success_count += 1

            except Exception as e:
                logger.error(f"Error correcting date for {record['source_path']}: {e}")
                error_count += 1

        progress.setValue(len(self.records))

        # Show results
        if error_count > 0:
            QMessageBox.warning(
                self,
                "Corrections Complete with Errors",
                f"Successfully corrected: {success_count} file(s)\n"
                f"Failed: {error_count} file(s)\n\n"
                f"Check logs for details."
            )
        else:
            QMessageBox.information(
                self,
                "Corrections Complete",
                f"Successfully corrected {success_count} file(s)!"
            )

        self.accept()
