"""
Batch Edit Dialog

Dialog for applying edits to multiple photos at once.
Supports:
- Auto-Enhance All: Analyze each photo individually
- Manual adjustments: Apply same values to all photos
- No crop support in batch mode (too complex for batch)
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QGroupBox, QProgressDialog, QWidget, QMessageBox, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
import logging
import os
from typing import List

from ui.edit_worker import EditState, BatchEditWorker

logger = logging.getLogger(__name__)


class BatchAdjustmentPanel(QWidget):
    """Simplified adjustment panel for batch editing."""

    values_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Brightness slider
        brightness_group = self._create_slider_group("Brightness", -100, 100, 0)
        self.brightness_slider = brightness_group['slider']
        self.brightness_label = brightness_group['value_label']
        layout.addWidget(brightness_group['widget'])

        # Contrast slider
        contrast_group = self._create_slider_group("Contrast", -100, 100, 0)
        self.contrast_slider = contrast_group['slider']
        self.contrast_label = contrast_group['value_label']
        layout.addWidget(contrast_group['widget'])

        # Saturation slider
        saturation_group = self._create_slider_group("Saturation", -100, 100, 0)
        self.saturation_slider = saturation_group['slider']
        self.saturation_label = saturation_group['value_label']
        layout.addWidget(saturation_group['widget'])

        # Reset button
        self.reset_btn = QPushButton("Reset All")
        self.reset_btn.setFixedHeight(28)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_values)
        layout.addWidget(self.reset_btn)

    def _create_slider_group(self, label: str, min_val: int, max_val: int,
                             default: int) -> dict:
        """Create a labeled slider with value display."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Label row
        label_row = QHBoxLayout()
        name_label = QLabel(label)
        name_label.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        label_row.addWidget(name_label)

        value_label = QLabel("0")
        value_label.setStyleSheet("color: #888888; font-size: 12px;")
        value_label.setAlignment(Qt.AlignRight)
        label_row.addWidget(value_label)

        layout.addLayout(label_row)

        # Slider
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333333;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #0066FF;
            }
            QSlider::sub-page:horizontal {
                background: #0066FF;
                border-radius: 3px;
            }
        """)

        slider.valueChanged.connect(
            lambda v: self._on_slider_changed(v, value_label)
        )

        layout.addWidget(slider)

        return {
            'widget': widget,
            'slider': slider,
            'value_label': value_label
        }

    def _on_slider_changed(self, value: int, label: QLabel):
        """Handle slider value change."""
        label.setText(f"{value:+d}" if value != 0 else "0")
        self.values_changed.emit()

    def reset_values(self):
        """Reset all sliders to zero."""
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.saturation_slider.setValue(0)

    def get_edit_state(self) -> EditState:
        """Get current adjustment values as EditState."""
        return EditState(
            brightness=self.brightness_slider.value(),
            contrast=self.contrast_slider.value(),
            saturation=self.saturation_slider.value()
        )

    def setEnabled(self, enabled: bool):
        """Enable/disable all controls."""
        self.brightness_slider.setEnabled(enabled)
        self.contrast_slider.setEnabled(enabled)
        self.saturation_slider.setEnabled(enabled)
        self.reset_btn.setEnabled(enabled)


class BatchEditDialog(QDialog):
    """
    Dialog for batch editing multiple photos.

    Provides two modes:
    1. Auto-Enhance All: Analyze each photo individually and apply optimal settings
    2. Manual: Apply the same adjustment values to all selected photos
    """

    def __init__(self, parent, records: List[dict], db_metadata, logger_instance):
        """
        Initialize batch edit dialog.

        Args:
            parent: Parent widget
            records: List of file record dictionaries
            db_metadata: DatabaseMetadata instance
            logger_instance: Logger instance
        """
        super().__init__(parent)
        self.parent_widget = parent
        self.records = records
        self.db_metadata = db_metadata
        self.logger = logger_instance
        self.batch_worker = None

        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle(f"Batch Edit - {len(self.records)} Photos")
        self.setMinimumSize(450, 450)
        self.setModal(True)

        # Dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1A1A;
            }
            QLabel {
                color: #FFFFFF;
            }
            QGroupBox {
                color: #FFFFFF;
                font-weight: bold;
                border: 1px solid #333333;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # Header
        header = QLabel(f"Edit {len(self.records)} Photos")
        header.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(header)

        # Info text
        info = QLabel(
            "Choose how to edit the selected photos. Auto-Enhance analyzes each photo\n"
            "individually. Manual adjustments apply the same values to all photos.\n\n"
            "Note: Crop is not available in batch mode."
        )
        info.setStyleSheet("color: #888888; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Auto-Enhance option
        auto_group = QGroupBox("Auto-Enhance")
        auto_layout = QVBoxLayout(auto_group)

        auto_desc = QLabel(
            "Automatically analyze each photo and apply optimal\n"
            "brightness, contrast, and saturation settings."
        )
        auto_desc.setStyleSheet("color: #CCCCCC; font-size: 11px; font-weight: normal;")
        auto_layout.addWidget(auto_desc)

        self.auto_enhance_btn = QPushButton("Auto-Enhance All Photos")
        self.auto_enhance_btn.setFixedHeight(40)
        self.auto_enhance_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066FF;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0055DD;
            }
        """)
        auto_layout.addWidget(self.auto_enhance_btn)

        layout.addWidget(auto_group)

        # Manual adjustments option
        manual_group = QGroupBox("Manual Adjustments")
        manual_layout = QVBoxLayout(manual_group)

        manual_desc = QLabel(
            "Apply the same adjustment values to all selected photos."
        )
        manual_desc.setStyleSheet("color: #CCCCCC; font-size: 11px; font-weight: normal;")
        manual_layout.addWidget(manual_desc)

        # Adjustment sliders
        self.adjustment_panel = BatchAdjustmentPanel()
        manual_layout.addWidget(self.adjustment_panel)

        self.apply_manual_btn = QPushButton("Apply Manual Adjustments")
        self.apply_manual_btn.setFixedHeight(36)
        self.apply_manual_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        manual_layout.addWidget(self.apply_manual_btn)

        layout.addWidget(manual_group)

        layout.addStretch()

        # Footer
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(100, 36)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        layout.addLayout(footer_layout)

    def _connect_signals(self):
        """Connect signals."""
        self.auto_enhance_btn.clicked.connect(self._on_auto_enhance_all)
        self.apply_manual_btn.clicked.connect(self._on_apply_manual)
        self.adjustment_panel.values_changed.connect(self._update_manual_button)
        self._update_manual_button()

    def _update_manual_button(self):
        """Update manual apply button based on current values."""
        edit_state = self.adjustment_panel.get_edit_state()
        if edit_state.has_changes():
            self.apply_manual_btn.setEnabled(True)
            self.apply_manual_btn.setText("Apply Manual Adjustments")
        else:
            self.apply_manual_btn.setEnabled(False)
            self.apply_manual_btn.setText("Adjust sliders to enable")

    def _validate_prerequisites(self) -> bool:
        """Check that prerequisites are met for editing."""
        # Check archive location
        archive_base = self.db_metadata.get_archive_location()
        if not archive_base:
            QMessageBox.critical(self, "Error", "Archive location not configured.")
            return False

        # Check Prior Revision Archive
        prior_archive = self.db_metadata.get_prior_revision_archive_location()
        if not prior_archive:
            QMessageBox.warning(
                self, "Prior Revision Archive Not Configured",
                "Please configure Prior Revision Archive location in Archive Settings."
            )
            return False

        if not os.path.exists(prior_archive):
            QMessageBox.warning(
                self, "Prior Revision Archive Not Found",
                f"Prior Revision Archive path does not exist:\n{prior_archive}"
            )
            return False

        return True

    def _on_auto_enhance_all(self):
        """Handle Auto-Enhance All button click."""
        if not self._validate_prerequisites():
            return

        # Confirm operation
        reply = QMessageBox.question(
            self,
            "Auto-Enhance All Photos",
            f"Auto-enhance {len(self.records)} photos?\n\n"
            f"Each photo will be analyzed individually and optimal\n"
            f"adjustments will be applied.\n\n"
            f"Originals will be preserved in Prior Revision Archive.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self._start_batch_edit(auto_enhance=True, edit_state=EditState())

    def _on_apply_manual(self):
        """Handle Apply Manual Adjustments button click."""
        if not self._validate_prerequisites():
            return

        edit_state = self.adjustment_panel.get_edit_state()
        if not edit_state.has_changes():
            QMessageBox.information(
                self, "No Changes",
                "Please adjust the sliders to make changes."
            )
            return

        # Confirm operation
        reply = QMessageBox.question(
            self,
            "Apply Manual Adjustments",
            f"Apply adjustments to {len(self.records)} photos?\n\n"
            f"Brightness: {edit_state.brightness:+d}\n"
            f"Contrast: {edit_state.contrast:+d}\n"
            f"Saturation: {edit_state.saturation:+d}\n\n"
            f"Originals will be preserved in Prior Revision Archive.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        self._start_batch_edit(auto_enhance=False, edit_state=edit_state)

    def _start_batch_edit(self, auto_enhance: bool, edit_state: EditState):
        """Start the batch edit operation."""
        # Disable all buttons
        self.auto_enhance_btn.setEnabled(False)
        self.apply_manual_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)
        self.adjustment_panel.setEnabled(False)

        # Create progress dialog
        progress_dialog = QProgressDialog(
            "Processing photos...", "Cancel", 0, len(self.records), self
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)
        progress_dialog.setAutoReset(False)

        # Create worker
        archive_base = self.db_metadata.get_archive_location()

        self.batch_worker = BatchEditWorker(
            records=self.records,
            edit_state=edit_state,
            auto_enhance=auto_enhance,
            db_path=self.db_metadata.database_path,
            archive_base=archive_base,
            worker_logger=self.logger
        )

        # Connect signals
        self.batch_worker.progress.connect(
            lambda cur, total, fname: self._update_progress(progress_dialog, cur, total, fname)
        )
        self.batch_worker.finished.connect(
            lambda results: self._on_batch_finished(results, progress_dialog)
        )

        progress_dialog.canceled.connect(self.batch_worker.cancel)

        # Start worker
        self.batch_worker.start()

    def _update_progress(self, progress_dialog: QProgressDialog, current: int,
                        total: int, filename: str):
        """Update progress dialog."""
        progress_dialog.setMaximum(total)
        progress_dialog.setValue(current)
        progress_dialog.setLabelText(f"Processing: {filename}\n({current}/{total})")

    def _on_batch_finished(self, results: dict, progress_dialog: QProgressDialog):
        """Handle batch edit completion."""
        progress_dialog.close()

        # Re-enable buttons
        self.auto_enhance_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)
        self.adjustment_panel.setEnabled(True)
        self._update_manual_button()

        success_count = results.get('success', 0)
        errors = results.get('errors', [])

        if errors:
            error_msg = "\n".join([f"- {e}" for e in errors[:10]])
            if len(errors) > 10:
                error_msg += f"\n... and {len(errors) - 10} more errors"

            QMessageBox.warning(
                self,
                "Batch Edit Complete with Errors",
                f"Successfully edited: {success_count}\n"
                f"Failed: {len(errors)}\n\n"
                f"Errors:\n{error_msg}"
            )
        elif success_count > 0:
            self.logger.info(f"Batch edit completed: {success_count} photos")
            QMessageBox.information(
                self,
                "Batch Edit Complete",
                f"Successfully edited {success_count} photos."
            )
            self.accept()
        else:
            QMessageBox.information(
                self,
                "No Changes",
                "No photos were edited."
            )

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close - ensure worker thread is properly stopped."""
        if self.batch_worker and self.batch_worker.isRunning():
            self.logger.info("Stopping batch edit worker before dialog close...")
            self.batch_worker.cancel()
            self.batch_worker.wait()  # Wait for thread to finish
            self.logger.info("Batch edit worker stopped")
        event.accept()
