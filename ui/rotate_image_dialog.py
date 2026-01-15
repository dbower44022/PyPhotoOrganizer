"""
Rotate Image Dialog

Dialog for rotating single or multiple images with version tracking.
Supports standard rotation angles (90° CW, 90° CCW, 180°) and custom angles.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QSpinBox, QCheckBox, QRadioButton,
                               QButtonGroup, QGroupBox, QMessageBox, QProgressDialog)
from PySide6.QtCore import Qt
import logging
import os

logger = logging.getLogger(__name__)


class RotateImageDialog(QDialog):
    """Dialog for rotating images."""

    def __init__(self, parent, selected_records, db_metadata, logger):
        """
        Initialize rotate image dialog.

        Args:
            parent: Parent widget
            selected_records: List of record dictionaries
            db_metadata: DatabaseMetadata instance
            logger: Logger instance
        """
        super().__init__(parent)
        self.parent_widget = parent
        self.selected_records = selected_records if isinstance(selected_records, list) else [selected_records]
        self.db_metadata = db_metadata
        self.logger = logger
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Rotate Images")
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout()

        # Header
        if len(self.selected_records) == 1:
            record = self.selected_records[0]
            filename = os.path.basename(record.get('archive_path', 'Unknown'))
            header = QLabel(f"Rotate Image - {filename}")
        else:
            header = QLabel(f"Rotate {len(self.selected_records)} Images")

        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Rotation angle selection
        angle_group = QGroupBox("Rotation Angle")
        angle_layout = QVBoxLayout()

        self.angle_group = QButtonGroup()

        self.rotate_90cw_radio = QRadioButton("90° Clockwise")
        self.angle_group.addButton(self.rotate_90cw_radio, 90)
        angle_layout.addWidget(self.rotate_90cw_radio)

        self.rotate_90ccw_radio = QRadioButton("90° Counter-Clockwise")
        self.angle_group.addButton(self.rotate_90ccw_radio, -90)
        angle_layout.addWidget(self.rotate_90ccw_radio)

        self.rotate_180_radio = QRadioButton("180°")
        self.angle_group.addButton(self.rotate_180_radio, 180)
        angle_layout.addWidget(self.rotate_180_radio)

        self.rotate_custom_radio = QRadioButton("Custom Angle:")
        self.angle_group.addButton(self.rotate_custom_radio, 0)  # ID 0 for custom
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(self.rotate_custom_radio)

        self.custom_angle_spin = QSpinBox()
        self.custom_angle_spin.setRange(0, 359)
        self.custom_angle_spin.setValue(0)
        self.custom_angle_spin.setSuffix("°")
        self.custom_angle_spin.setEnabled(False)
        custom_layout.addWidget(self.custom_angle_spin)
        custom_layout.addStretch()

        angle_layout.addLayout(custom_layout)

        # Connect custom radio to enable/disable spinner
        self.rotate_custom_radio.toggled.connect(self.on_custom_angle_toggled)

        # Default to 90° CW
        self.rotate_90cw_radio.setChecked(True)

        angle_group.setLayout(angle_layout)
        layout.addWidget(angle_group)

        # Information
        info_group = QGroupBox("Information")
        info_layout = QVBoxLayout()

        info_text = QLabel(
            "• Original images will be preserved as version 0 in .pyphotoorg_versions/\n"
            "• Rotated images will replace the archive files\n"
            "• Rotation is tracked for duplicate detection\n"
            "• EXIF orientation data will be updated\n"
            "• Source files are never modified"
        )
        info_text.setWordWrap(True)
        info_text.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        info_layout.addWidget(info_text)

        info_group.setLayout(info_layout)
        layout.addWidget(info_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.apply_btn = QPushButton("Rotate")
        self.apply_btn.clicked.connect(self.apply_rotation)
        self.apply_btn.setDefault(True)
        button_layout.addWidget(self.apply_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def on_custom_angle_toggled(self, checked):
        """Enable/disable custom angle spinner based on radio button state."""
        self.custom_angle_spin.setEnabled(checked)
        if checked:
            self.custom_angle_spin.setFocus()

    def get_rotation_angle(self):
        """
        Get the selected rotation angle.

        Returns:
            int: Rotation angle in degrees
        """
        if self.rotate_custom_radio.isChecked():
            return self.custom_angle_spin.value()
        else:
            # Get ID from button group (90, -90, or 180)
            checked_button = self.angle_group.checkedButton()
            return self.angle_group.id(checked_button)

    def apply_rotation(self):
        """Apply rotation to selected images."""
        from ui.rotate_worker import RotateWorker

        # Get rotation angle
        angle = self.get_rotation_angle()

        if angle == 0:
            QMessageBox.warning(
                self,
                "No Rotation",
                "Please select a rotation angle."
            )
            return

        # Confirm operation
        count = len(self.selected_records)
        reply = QMessageBox.question(
            self,
            "Confirm Rotation",
            f"Rotate {count} image(s) by {angle}°?\n\n"
            f"Original images will be preserved as version 0.\n"
            f"Archive files will be replaced with rotated versions.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Get archive base for version manager
        archive_base = self.db_metadata.get_archive_location()
        if not archive_base:
            QMessageBox.critical(
                self,
                "Error",
                "Archive location not configured in database."
            )
            return

        # Disable buttons during processing
        self.apply_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        # Create progress dialog
        progress_dialog = QProgressDialog(
            "Rotating images...", "Cancel", 0, count, self
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)

        # Create and start rotation worker
        self.rotate_worker = RotateWorker(
            self.selected_records,
            angle,
            self.db_metadata.database_path,
            archive_base,
            self.logger
        )

        # Connect signals
        self.rotate_worker.progress.connect(
            lambda cur, total, fname: self._update_progress(progress_dialog, cur, total, fname)
        )
        self.rotate_worker.finished.connect(
            lambda results: self._on_rotation_finished(results, progress_dialog)
        )

        # Handle cancellation
        progress_dialog.canceled.connect(lambda: self.rotate_worker.cancel())

        # Start worker
        self.rotate_worker.start()

    def _update_progress(self, progress_dialog, current, total, filename):
        """Update progress dialog."""
        progress_dialog.setMaximum(total)
        progress_dialog.setValue(current)
        progress_dialog.setLabelText(f"Rotating: {filename}\n({current}/{total})")

    def _on_rotation_finished(self, results, progress_dialog):
        """Handle rotation worker completion."""
        progress_dialog.close()

        success_count = results.get('success', 0)
        errors = results.get('errors', [])

        # Re-enable buttons
        self.apply_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

        if errors:
            error_msg = "\n".join([f"- {e}" for e in errors[:10]])
            if len(errors) > 10:
                error_msg += f"\n... and {len(errors) - 10} more errors"

            QMessageBox.warning(
                self,
                "Rotation Complete with Errors",
                f"Successfully rotated: {success_count}\n"
                f"Failed: {len(errors)}\n\n"
                f"First errors:\n{error_msg}"
            )
        elif success_count > 0:
            # Silent success - no dialog for successful operations
            self.logger.info(f"✓ Successfully rotated {success_count} image(s)")

        # Close dialog if successful or no errors to report
        if success_count > 0 or not errors:
            self.accept()
