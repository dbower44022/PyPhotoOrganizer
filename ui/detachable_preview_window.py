"""
Detachable Preview Window

Separate window for large image viewing with zoom capabilities.
Can be moved to second monitor for dual-screen workflows.
"""

import logging
import os
import json
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLabel, QPushButton, QGroupBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent

logger = logging.getLogger(__name__)


class DetachablePreviewWindow(QMainWindow):
    """
    Detachable preview window for large image viewing.

    Features:
    - ZoomableImageViewer (rubber band zoom, double-click reset)
    - File details panel (paths, dates, EXIF, status)
    - Geometry persistence across sessions
    - Independent window (can move to second monitor)
    """

    # Signal when window is closed
    window_closed = Signal()

    # Signal when correct date button is clicked
    correct_date_clicked = Signal(dict)  # Emits current record

    def __init__(self, db_metadata, parent=None):
        """
        Initialize preview window.

        Args:
            db_metadata: DatabaseMetadata instance for settings
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_metadata = db_metadata
        self.current_record: Optional[Dict[str, Any]] = None

        self.setWindowTitle("Image Preview - Date Corrections")
        self.setWindowFlags(Qt.Window)  # Independent window

        self._init_ui()
        self._restore_geometry()

        logger.info("DetachablePreviewWindow initialized")

    def _init_ui(self):
        """Initialize user interface."""
        # Central widget
        central = QWidget()
        layout = QVBoxLayout(central)

        # Header: filename
        self.filename_label = QLabel("No file selected")
        self.filename_label.setStyleSheet("font-size: 14pt; font-weight: bold; padding: 10px;")
        layout.addWidget(self.filename_label)

        # Image viewer (import from date_corrections_tab)
        try:
            from ui.date_corrections_tab import ZoomableImageViewer
            self.viewer = ZoomableImageViewer()
            layout.addWidget(self.viewer, 1)  # Stretch factor 1
        except ImportError:
            logger.error("Failed to import ZoomableImageViewer")
            self.viewer = QLabel("Image viewer not available")
            layout.addWidget(self.viewer, 1)

        # File details panel
        details_group = QGroupBox("File Details")
        details_layout = QVBoxLayout()

        self.detail_source = QLabel("Source: -")
        self.detail_source.setWordWrap(True)
        details_layout.addWidget(self.detail_source)

        self.detail_archive = QLabel("Archive: -")
        self.detail_archive.setWordWrap(True)
        details_layout.addWidget(self.detail_archive)

        self.detail_dates = QLabel("Detected Date: -")
        self.detail_dates.setWordWrap(True)
        details_layout.addWidget(self.detail_dates)

        self.detail_reason = QLabel("Flag Reason: -")
        details_layout.addWidget(self.detail_reason)

        self.detail_status = QLabel("Status: -")
        details_layout.addWidget(self.detail_status)

        self.detail_hash = QLabel("Hash: -")
        self.detail_hash.setWordWrap(True)
        self.detail_hash.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.detail_hash.setStyleSheet("font-family: monospace; font-size: 9pt;")
        details_layout.addWidget(self.detail_hash)

        details_group.setLayout(details_layout)
        layout.addWidget(details_group)

        # Button layout
        button_layout = QHBoxLayout()

        # Correct date button
        self.correct_btn = QPushButton("Correct Date...")
        self.correct_btn.setMinimumHeight(40)
        self.correct_btn.clicked.connect(self.on_correct_date)
        self.correct_btn.setEnabled(False)
        button_layout.addWidget(self.correct_btn)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.setMinimumHeight(40)
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

        self.setCentralWidget(central)

    def update_preview(self, record: Dict[str, Any]):
        """
        Update preview from selected record.

        Args:
            record: UnreliableDates record dict
        """
        try:
            self.current_record = record

            # Update image
            source_path = record.get('source_path', '')
            if source_path and os.path.exists(source_path):
                if hasattr(self.viewer, 'load_image'):
                    self.viewer.load_image(source_path)
            else:
                if hasattr(self.viewer, 'clear'):
                    self.viewer.clear()

            # Update labels
            self.filename_label.setText(os.path.basename(source_path) if source_path else "Unknown")

            self.detail_source.setText(f"Source: {source_path}")

            archive_path = record.get('archive_path', '')
            original_archive_path = record.get('original_archive_path', '')
            if original_archive_path and archive_path != original_archive_path:
                archive_text = f"Archive: {archive_path}\nOriginal: {original_archive_path}"
            else:
                archive_text = f"Archive: {archive_path or 'Not organized'}"
            self.detail_archive.setText(archive_text)

            # Dates
            detected_date = record.get('original_date', '-')
            date_source = record.get('date_source', '-')
            corrected_date = record.get('corrected_date')

            dates_text = f"Detected Date: {detected_date} (from {date_source})"
            if corrected_date:
                dates_text += f"\nCorrected Date: {corrected_date}"
            self.detail_dates.setText(dates_text)

            # Reason
            reason = record.get('flag_reason', '-').replace('_', ' ').title()
            self.detail_reason.setText(f"Flag Reason: {reason}")

            # Status
            if corrected_date:
                if record.get('needs_reorganization'):
                    status_text = f"Corrected: {corrected_date} (Needs reorganization)"
                else:
                    status_text = f"Reorganized: {corrected_date}"
            else:
                status_text = "Pending correction"
            self.detail_status.setText(f"Status: {status_text}")

            # Hash
            file_hash = record.get('file_hash', 'N/A')
            self.detail_hash.setText(f"Hash: {file_hash}")

            self.correct_btn.setEnabled(True)

        except Exception as e:
            logger.error(f"Error updating preview: {e}", exc_info=True)

    def on_correct_date(self):
        """Handle correct date button click."""
        if not self.current_record:
            return

        # Emit signal for parent to handle (opens dialog)
        self.correct_date_clicked.emit(self.current_record)

    def closeEvent(self, event: QCloseEvent):
        """
        Handle window close event - save geometry.

        Args:
            event: Close event
        """
        self._save_geometry()
        self.window_closed.emit()
        super().closeEvent(event)

    def _save_geometry(self):
        """Save window geometry to database."""
        try:
            geo = self.geometry()
            geometry_dict = {
                'x': geo.x(),
                'y': geo.y(),
                'width': geo.width(),
                'height': geo.height()
            }
            self.db_metadata.set_preview_window_geometry(json.dumps(geometry_dict))
            logger.debug(f"Saved preview window geometry: {geometry_dict}")

        except Exception as e:
            logger.error(f"Failed to save preview window geometry: {e}")

    def _restore_geometry(self):
        """Restore window geometry from database."""
        try:
            geo_json = self.db_metadata.get_preview_window_geometry()
            if geo_json:
                geo = json.loads(geo_json)
                self.setGeometry(geo['x'], geo['y'], geo['width'], geo['height'])
                logger.debug(f"Restored preview window geometry: {geo}")
                return

        except Exception as e:
            logger.debug(f"Could not restore preview window geometry: {e}")

        # Default: 1000x800 centered on parent
        self.resize(1000, 800)
        if self.parent():
            try:
                parent_geo = self.parent().window().frameGeometry()
                x = parent_geo.x() + (parent_geo.width() - 1000) // 2
                y = parent_geo.y() + (parent_geo.height() - 800) // 2
                self.move(x, y)
            except:
                pass  # Use default position if centering fails

        logger.debug("Using default preview window geometry (1000x800)")
