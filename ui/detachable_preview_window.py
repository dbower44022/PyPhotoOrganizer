"""
Detachable Preview Window

Separate window for large image viewing with zoom capabilities.
Can be moved to second monitor for dual-screen workflows.
Enhanced with Source/Archive file actions, revision history, and comprehensive file details.
"""

import logging
import os
import json
import subprocess
import platform
from datetime import datetime
from math import gcd
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QApplication, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QMessageBox, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont

from ui.theme import ThemeManager, get_theme

logger = logging.getLogger(__name__)


class StyledLabel(QLabel):
    """Label with consistent styling for file details, theme-aware."""

    def __init__(self, text: str = "", is_value: bool = False, parent=None):
        super().__init__(text, parent)
        self.is_value = is_value
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._apply_style()

    def _apply_style(self):
        """Apply theme-aware styling."""
        theme = get_theme()
        c = theme.colors

        if self.is_value:
            # Value labels - normal weight, primary text color
            self.setStyleSheet(f"color: {c.text_primary}; font-size: 10pt;")
        else:
            # Label/header labels - bold and primary color
            self.setStyleSheet(f"color: {c.primary}; font-weight: bold; font-size: 10pt;")

    def update_theme(self):
        """Update styling when theme changes."""
        self._apply_style()


class CollapsibleSection(QWidget):
    """
    A collapsible section with header and content area for file details.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._is_expanded = True
        self._title = title
        self._init_ui()

    def _init_ui(self):
        theme = get_theme()
        c = theme.colors

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header button
        self.header_btn = QPushButton(f"▼ {self._title}")
        self.header_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.bg_tertiary};
                border: none;
                border-radius: 4px;
                color: {c.text_primary};
                font-weight: 600;
                font-size: 13px;
                text-align: left;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: {c.hover_bg};
            }}
        """)
        self.header_btn.clicked.connect(self._toggle)
        main_layout.addWidget(self.header_btn)

        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(8, 6, 8, 6)
        self.content_layout.setSpacing(2)
        main_layout.addWidget(self.content_widget)

    def _toggle(self):
        self._is_expanded = not self._is_expanded
        self.content_widget.setVisible(self._is_expanded)
        arrow = "▼" if self._is_expanded else "▶"
        self.header_btn.setText(f"{arrow} {self._title}")

    def add_row(self, label: str, value: str):
        """Add a label-value row to the content."""
        theme = get_theme()
        c = theme.colors

        row = QWidget()
        row.setStyleSheet(f"background-color: transparent;")
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        label_widget = QLabel(f"{label}:")
        label_widget.setStyleSheet(f"color: {c.text_muted}; font-size: 12px; min-width: 85px; background-color: transparent;")
        label_widget.setAlignment(Qt.AlignRight | Qt.AlignTop)
        row_layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet(f"color: {c.text_primary}; font-size: 12px; background-color: transparent;")
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row_layout.addWidget(value_widget, 1)

        self.content_layout.addWidget(row)

    def add_widget(self, widget: QWidget):
        """Add a custom widget to the content area."""
        self.content_layout.addWidget(widget)

    def clear_content(self):
        """Clear all content rows."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def update_theme(self):
        """Update styling when theme changes."""
        theme = get_theme()
        c = theme.colors
        self.header_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.bg_tertiary};
                border: none;
                border-radius: 4px;
                color: {c.text_primary};
                font-weight: 600;
                font-size: 13px;
                text-align: left;
                padding: 8px 12px;
            }}
            QPushButton:hover {{
                background-color: {c.hover_bg};
            }}
        """)


class DetachablePreviewWindow(QMainWindow):
    """
    Detachable preview window for large image viewing.

    Features:
    - ZoomableImageViewer (rubber band zoom, double-click reset)
    - File details panel with styled labels (paths, dates, status)
    - Source file actions (Open, Open Folder, Copy Path)
    - Archive file actions (Open, Open Folder, Copy Path)
    - Revision history panel showing all versions
    - Double-click revision to preview or launch externally
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
        self.revisions: List[Dict] = []
        self.revision_preview_window = None  # Secondary preview window

        self.setWindowTitle("Image Preview - Date Corrections")
        self.setWindowFlags(Qt.Window)  # Independent window

        self._init_ui()
        self._restore_geometry()

        logger.info("DetachablePreviewWindow initialized")

    def _init_ui(self):
        """Initialize user interface with image viewer and comprehensive file details."""
        theme = get_theme()
        c = theme.colors

        # Central widget
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(4)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # Header: filename
        self.filename_label = QLabel("No file selected")
        main_layout.addWidget(self.filename_label)

        # Main horizontal splitter: Image Viewer | Details Panel
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Left side: Image viewer
        try:
            from ui.preview import ZoomableImageViewer
            self.viewer = ZoomableImageViewer()
        except ImportError:
            logger.error("Failed to import ZoomableImageViewer from ui.preview")
            self.viewer = QLabel("Image viewer not available")
        self.main_splitter.addWidget(self.viewer)

        # Right side: Scrollable details panel
        details_scroll = QScrollArea()
        details_scroll.setWidgetResizable(True)
        details_scroll.setFrameShape(QFrame.NoFrame)
        details_scroll.setMinimumWidth(320)
        details_scroll.setMaximumWidth(500)
        details_scroll.setStyleSheet(f"""
            QScrollArea {{
                background-color: {c.bg_secondary};
                border: none;
            }}
            QScrollBar:vertical {{
                background-color: {c.bg_tertiary};
                width: 10px;
                border-radius: 5px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {c.gray_500};
                border-radius: 5px;
                min-height: 30px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {c.gray_400};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        details_content = QWidget()
        details_content.setStyleSheet(f"background-color: {c.bg_secondary};")
        details_layout = QVBoxLayout(details_content)
        details_layout.setContentsMargins(10, 10, 10, 10)
        details_layout.setSpacing(8)

        # Database Info section
        self.db_section = CollapsibleSection("Database Info")
        details_layout.addWidget(self.db_section)

        # File Information section
        self.file_section = CollapsibleSection("File Information")
        details_layout.addWidget(self.file_section)

        # Image Properties section
        self.image_section = CollapsibleSection("Image Properties")
        details_layout.addWidget(self.image_section)

        # EXIF Data section
        self.exif_section = CollapsibleSection("EXIF Data")
        details_layout.addWidget(self.exif_section)

        # Revisions section
        self.revisions_section = CollapsibleSection("Revisions")
        self.revisions_list = QListWidget()
        self.revisions_list.setAlternatingRowColors(True)
        self.revisions_list.setMaximumHeight(150)
        self.revisions_list.itemDoubleClicked.connect(self._on_revision_double_clicked)
        self.revisions_section.add_widget(self.revisions_list)
        self.revision_info_label = QLabel("No revisions found")
        self.revision_info_label.setStyleSheet(f"color: {c.text_muted}; font-style: italic; font-size: 12px; background-color: transparent;")
        self.revisions_section.add_widget(self.revision_info_label)
        details_layout.addWidget(self.revisions_section)

        details_layout.addStretch()

        details_scroll.setWidget(details_content)
        self.main_splitter.addWidget(details_scroll)

        # Set splitter sizes (70% image, 30% details)
        self.main_splitter.setSizes([700, 350])
        self.main_splitter.setStretchFactor(0, 1)  # Image stretches
        self.main_splitter.setStretchFactor(1, 0)  # Details fixed width

        main_layout.addWidget(self.main_splitter, 1)

        # Action buttons in a compact row
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(0, 4, 0, 0)
        actions_layout.setSpacing(6)

        # Source file buttons
        self.open_source_file_btn = QPushButton("📂 Source")
        self.open_source_file_btn.setMinimumHeight(32)
        self.open_source_file_btn.clicked.connect(self._on_open_source_file)
        self.open_source_file_btn.setEnabled(False)
        self.open_source_file_btn.setToolTip("Open source file location")
        actions_layout.addWidget(self.open_source_file_btn)

        self.open_source_folder_btn = QPushButton("📁 Source Folder")
        self.open_source_folder_btn.setMinimumHeight(32)
        self.open_source_folder_btn.clicked.connect(self._on_open_source_folder)
        self.open_source_folder_btn.setEnabled(False)
        actions_layout.addWidget(self.open_source_folder_btn)

        self.copy_source_path_btn = QPushButton("📋 Copy Source")
        self.copy_source_path_btn.setMinimumHeight(32)
        self.copy_source_path_btn.clicked.connect(self._on_copy_source_path)
        self.copy_source_path_btn.setEnabled(False)
        actions_layout.addWidget(self.copy_source_path_btn)

        # Separator
        sep1 = QFrame()
        sep1.setFrameShape(QFrame.VLine)
        sep1.setStyleSheet(f"background-color: {c.border_light};")
        actions_layout.addWidget(sep1)

        # Archive file buttons
        self.open_archive_file_btn = QPushButton("📂 Archive")
        self.open_archive_file_btn.setMinimumHeight(32)
        self.open_archive_file_btn.clicked.connect(self._on_open_archive_file)
        self.open_archive_file_btn.setEnabled(False)
        self.open_archive_file_btn.setToolTip("Open archive file location")
        actions_layout.addWidget(self.open_archive_file_btn)

        self.open_archive_folder_btn = QPushButton("📁 Archive Folder")
        self.open_archive_folder_btn.setMinimumHeight(32)
        self.open_archive_folder_btn.clicked.connect(self._on_open_archive_folder)
        self.open_archive_folder_btn.setEnabled(False)
        actions_layout.addWidget(self.open_archive_folder_btn)

        self.copy_archive_path_btn = QPushButton("📋 Copy Archive")
        self.copy_archive_path_btn.setMinimumHeight(32)
        self.copy_archive_path_btn.clicked.connect(self._on_copy_archive_path)
        self.copy_archive_path_btn.setEnabled(False)
        actions_layout.addWidget(self.copy_archive_path_btn)

        actions_layout.addStretch()

        # Correct date button
        self.correct_btn = QPushButton("📅 Correct Date...")
        self.correct_btn.setMinimumHeight(36)
        self.correct_btn.clicked.connect(self.on_correct_date)
        self.correct_btn.setEnabled(False)
        actions_layout.addWidget(self.correct_btn)

        # Close button
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(36)
        self.close_btn.setMinimumWidth(80)
        self.close_btn.clicked.connect(self.close)
        actions_layout.addWidget(self.close_btn)

        main_layout.addWidget(actions_widget)

        self.setCentralWidget(central)

        # Apply theme-aware styling
        self._apply_theme()

    def _apply_theme(self):
        """Apply theme-aware styling to all components."""
        theme = get_theme()
        c = theme.colors

        # Apply global theme stylesheet to window
        self.setStyleSheet(theme.get_global_stylesheet())

        # Filename header
        self.filename_label.setStyleSheet(f"""
            font-size: 13pt;
            font-weight: bold;
            padding: 8px 12px;
            background-color: {c.bg_secondary};
            border-radius: 4px;
            color: {c.text_primary};
        """)

        # Revisions list
        self.revisions_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 6px;
                border-bottom: 1px solid {c.border_light};
                color: {c.text_primary};
                font-size: 12px;
            }}
            QListWidget::item:selected {{
                background-color: {c.primary};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {c.hover_bg};
            }}
            QListWidget::item:alternate {{
                background-color: {c.bg_secondary};
            }}
        """)

        # Revision info label
        self.revision_info_label.setStyleSheet(f"color: {c.text_muted}; font-style: italic; font-size: 12px; background-color: transparent;")

        # Action buttons (secondary style with good contrast)
        action_button_style = f"""
            QPushButton {{
                background-color: {c.bg_tertiary};
                color: {c.text_primary};
                font-weight: 500;
                border-radius: 4px;
                border: 1px solid {c.border_light};
                padding: 4px 12px;
            }}
            QPushButton:hover {{
                background-color: {c.primary};
                color: white;
                border-color: {c.primary};
            }}
            QPushButton:disabled {{
                background-color: {c.bg_secondary};
                color: {c.text_disabled};
                border-color: {c.border_light};
            }}
        """
        self.open_source_file_btn.setStyleSheet(action_button_style)
        self.open_source_folder_btn.setStyleSheet(action_button_style)
        self.copy_source_path_btn.setStyleSheet(action_button_style)
        self.open_archive_file_btn.setStyleSheet(action_button_style)
        self.open_archive_folder_btn.setStyleSheet(action_button_style)
        self.copy_archive_path_btn.setStyleSheet(action_button_style)

        # Correct date button (primary action)
        self.correct_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
            QPushButton:disabled {{
                background-color: {c.gray_400};
                color: {c.text_disabled};
            }}
        """)

        # Close button (red for visibility)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.error};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #DC2626;
            }}
        """)

        # Update all StyledLabels
        for label in self.findChildren(StyledLabel):
            label.update_theme()

        # Update collapsible sections
        for section in self.findChildren(CollapsibleSection):
            section.update_theme()

        # Update the viewer theme if it has that capability
        if hasattr(self.viewer, 'update_theme'):
            self.viewer.update_theme()
        elif hasattr(self.viewer, 'setStyleSheet'):
            self.viewer.setStyleSheet(f"background-color: {c.bg_tertiary};")

    def update_preview(self, record: Dict[str, Any]):
        """
        Update preview from selected record.

        Args:
            record: UnreliableDates record dict or UniquePhotos record
        """
        try:
            self.current_record = record

            # Update image
            # CRITICAL: Prefer archive_path over source_path because:
            # 1. Rotations/modifications happen on archive files (never modify source files)
            # 2. Archive file reflects current state after any rotations/corrections
            # 3. Source files remain pristine and unmodified
            archive_path = record.get('archive_path') or record.get('file_name', '')
            source_path = record.get('source_path', '')

            # Prefer archive if available, fallback to source
            preview_path = archive_path if (archive_path and os.path.exists(archive_path)) else source_path

            if preview_path and os.path.exists(preview_path):
                if hasattr(self.viewer, 'load_image'):
                    self.viewer.load_image(preview_path)
            else:
                if hasattr(self.viewer, 'clear'):
                    self.viewer.clear()

            # Update filename header
            filename = os.path.basename(source_path) if source_path else os.path.basename(archive_path)
            self.filename_label.setText(filename or "Unknown")

            # Get file hash for later use
            file_hash = record.get('file_hash', 'N/A')
            logger.debug(f"update_preview: file_hash={file_hash[:16] if file_hash and file_hash != 'N/A' else file_hash}...")

            # Populate Database Info section
            self._populate_db_section(record, file_hash, source_path, archive_path)

            # Populate File Information section
            self._populate_file_section(preview_path)

            # Populate Image Properties section
            self._populate_image_section(preview_path)

            # Populate EXIF Data section
            self._populate_exif_section(preview_path)

            # Enable buttons based on path existence
            has_source = bool(source_path and os.path.exists(source_path))
            self.open_source_file_btn.setEnabled(has_source)
            self.open_source_folder_btn.setEnabled(has_source)
            self.copy_source_path_btn.setEnabled(bool(source_path))

            has_archive = bool(archive_path and os.path.exists(archive_path))
            self.open_archive_file_btn.setEnabled(has_archive)
            self.open_archive_folder_btn.setEnabled(has_archive)
            self.copy_archive_path_btn.setEnabled(bool(archive_path))

            self.correct_btn.setEnabled(True)

            # Load revisions
            self._load_revisions(file_hash)

        except Exception as e:
            logger.error(f"Error updating preview: {e}", exc_info=True)

    def _populate_db_section(self, record: Dict, file_hash: str, source_path: str, archive_path: str):
        """Populate the Database Info collapsible section."""
        self.db_section.clear_content()
        theme = get_theme()
        c = theme.colors

        # Hash
        self.db_section.add_row("Hash", file_hash if file_hash != 'N/A' else "Not available")

        # Source path
        self.db_section.add_row("Source", source_path or "N/A")

        # Archive path
        self.db_section.add_row("Archive", archive_path or "Not organized")

        # Detected date
        detected_date = record.get('original_date') or record.get('create_datetime', '-')
        date_source = record.get('date_source', '')
        if date_source:
            self.db_section.add_row("Detected Date", f"{detected_date} (from {date_source})")
        else:
            self.db_section.add_row("Detected Date", detected_date)

        # Corrected date
        corrected_date = record.get('corrected_date')
        self.db_section.add_row("Corrected Date", corrected_date or "Not corrected")

        # Flag reason
        reason = record.get('flag_reason') or '-'
        reason_display = reason.replace('_', ' ').title()
        self.db_section.add_row("Flag Reason", reason_display)

        # Status with color
        if corrected_date:
            if record.get('needs_reorganization'):
                status_text = "Corrected (Needs reorganization)"
            else:
                status_text = "Reorganized"
        else:
            status_text = "Pending correction"
        self.db_section.add_row("Status", status_text)

    def _populate_file_section(self, file_path: str):
        """Populate the File Information collapsible section."""
        self.file_section.clear_content()

        if not file_path or not os.path.exists(file_path):
            self.file_section.add_row("Status", "File not found")
            return

        try:
            stat = os.stat(file_path)

            # File size
            size_bytes = stat.st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            else:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            self.file_section.add_row("Size", size_str)

            # File type
            ext = os.path.splitext(file_path)[1].upper()
            self.file_section.add_row("Type", ext or "Unknown")

            # Modified time
            mtime = datetime.fromtimestamp(stat.st_mtime)
            self.file_section.add_row("Modified", mtime.strftime("%Y-%m-%d %H:%M:%S"))

            # Created time (if available)
            try:
                if hasattr(stat, 'st_birthtime'):
                    ctime = datetime.fromtimestamp(stat.st_birthtime)
                else:
                    ctime = datetime.fromtimestamp(stat.st_ctime)
                self.file_section.add_row("Created", ctime.strftime("%Y-%m-%d %H:%M:%S"))
            except:
                pass

        except Exception as e:
            logger.debug(f"Could not get file stats: {e}")
            self.file_section.add_row("Error", str(e))

    def _populate_image_section(self, file_path: str):
        """Populate the Image Properties collapsible section."""
        self.image_section.clear_content()

        if not file_path or not os.path.exists(file_path):
            self.image_section.add_row("Status", "File not found")
            return

        try:
            from PIL import Image

            with Image.open(file_path) as img:
                # Dimensions
                width, height = img.size
                self.image_section.add_row("Dimensions", f"{width} × {height} px")

                # Megapixels
                megapixels = (width * height) / 1_000_000
                self.image_section.add_row("Megapixels", f"{megapixels:.1f} MP")

                # Aspect ratio
                divisor = gcd(width, height)
                aspect_w = width // divisor
                aspect_h = height // divisor
                # Simplify common ratios
                if (aspect_w, aspect_h) in [(16, 9), (4, 3), (3, 2), (1, 1), (9, 16), (3, 4), (2, 3)]:
                    self.image_section.add_row("Aspect Ratio", f"{aspect_w}:{aspect_h}")
                else:
                    ratio = width / height
                    self.image_section.add_row("Aspect Ratio", f"{ratio:.2f}:1")

                # Format
                self.image_section.add_row("Format", img.format or "Unknown")

                # Color mode
                mode_names = {
                    '1': 'Black & White (1-bit)',
                    'L': 'Grayscale (8-bit)',
                    'P': 'Palette (8-bit)',
                    'RGB': 'RGB Color (24-bit)',
                    'RGBA': 'RGBA Color (32-bit)',
                    'CMYK': 'CMYK Color',
                    'YCbCr': 'YCbCr Color',
                    'LAB': 'LAB Color',
                    'HSV': 'HSV Color',
                    'I': 'Integer (32-bit)',
                    'F': 'Float (32-bit)',
                }
                mode_display = mode_names.get(img.mode, img.mode)
                self.image_section.add_row("Color Mode", mode_display)

                # Bit depth
                mode_bits = {
                    '1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32,
                    'CMYK': 32, 'YCbCr': 24, 'LAB': 24, 'HSV': 24,
                    'I': 32, 'F': 32, 'I;16': 16, 'I;16L': 16, 'I;16B': 16
                }
                bits = mode_bits.get(img.mode, 0)
                if bits:
                    self.image_section.add_row("Bit Depth", f"{bits} bits")

        except Exception as e:
            logger.debug(f"Could not get image properties: {e}")
            self.image_section.add_row("Error", "Could not read image properties")

    def _populate_exif_section(self, file_path: str):
        """Populate the EXIF Data collapsible section."""
        self.exif_section.clear_content()

        if not file_path or not os.path.exists(file_path):
            self.exif_section.add_row("Status", "File not found")
            return

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            with Image.open(file_path) as img:
                exif_data = img.getexif()

                if not exif_data:
                    self.exif_section.add_row("Status", "No EXIF data found")
                    return

                # Priority EXIF fields to display
                priority_tags = {
                    'DateTimeOriginal': 'Date Taken',
                    'DateTime': 'Date Modified',
                    'Make': 'Camera Make',
                    'Model': 'Camera Model',
                    'ExposureTime': 'Exposure',
                    'FNumber': 'Aperture',
                    'ISOSpeedRatings': 'ISO',
                    'FocalLength': 'Focal Length',
                    'Flash': 'Flash',
                    'WhiteBalance': 'White Balance',
                    'ExposureProgram': 'Exposure Program',
                    'MeteringMode': 'Metering Mode',
                    'LensModel': 'Lens',
                    'Software': 'Software',
                    'Artist': 'Artist',
                    'Copyright': 'Copyright',
                }

                # Build reverse lookup
                tag_names = {v: k for k, v in TAGS.items()}

                displayed = 0
                for tag_name, display_name in priority_tags.items():
                    tag_id = tag_names.get(tag_name)
                    if tag_id and tag_id in exif_data:
                        value = exif_data[tag_id]
                        formatted = self._format_exif_value(tag_name, value)
                        if formatted:
                            self.exif_section.add_row(display_name, formatted)
                            displayed += 1

                # GPS info if available
                gps_tag_id = tag_names.get('GPSInfo')
                if gps_tag_id and gps_tag_id in exif_data:
                    gps_info = exif_data[gps_tag_id]
                    coords = self._parse_gps_info(gps_info)
                    if coords:
                        self.exif_section.add_row("GPS Location", coords)
                        displayed += 1

                if displayed == 0:
                    self.exif_section.add_row("Status", "No readable EXIF data")

        except Exception as e:
            logger.debug(f"Could not read EXIF data: {e}")
            self.exif_section.add_row("Error", "Could not read EXIF data")

    def _format_exif_value(self, tag_name: str, value) -> str:
        """Format an EXIF value for display."""
        try:
            if tag_name == 'ExposureTime':
                if isinstance(value, tuple) and len(value) == 2:
                    num, denom = value
                    if denom and num:
                        if num < denom:
                            return f"1/{int(denom/num)}s"
                        else:
                            return f"{num/denom:.1f}s"
                return str(value)

            elif tag_name == 'FNumber':
                if isinstance(value, tuple) and len(value) == 2:
                    num, denom = value
                    if denom:
                        return f"f/{num/denom:.1f}"
                elif hasattr(value, 'numerator'):
                    return f"f/{float(value):.1f}"
                return f"f/{value}"

            elif tag_name == 'FocalLength':
                if isinstance(value, tuple) and len(value) == 2:
                    num, denom = value
                    if denom:
                        return f"{num/denom:.0f}mm"
                elif hasattr(value, 'numerator'):
                    return f"{float(value):.0f}mm"
                return f"{value}mm"

            elif tag_name == 'ISOSpeedRatings':
                if isinstance(value, tuple):
                    return str(value[0])
                return str(value)

            elif tag_name == 'Flash':
                flash_modes = {
                    0: 'No Flash',
                    1: 'Flash Fired',
                    5: 'Flash Fired, Strobe Return Not Detected',
                    7: 'Flash Fired, Strobe Return Detected',
                    9: 'Flash Fired, Compulsory',
                    13: 'Flash Fired, Compulsory, Return Not Detected',
                    15: 'Flash Fired, Compulsory, Return Detected',
                    16: 'No Flash Function',
                    24: 'No Flash, Auto',
                    25: 'Flash Fired, Auto',
                    29: 'Flash Fired, Auto, Return Not Detected',
                    31: 'Flash Fired, Auto, Return Detected',
                }
                return flash_modes.get(value, f"Mode {value}")

            elif tag_name == 'WhiteBalance':
                wb_modes = {0: 'Auto', 1: 'Manual'}
                return wb_modes.get(value, f"Mode {value}")

            elif tag_name == 'ExposureProgram':
                programs = {
                    0: 'Not Defined',
                    1: 'Manual',
                    2: 'Program AE',
                    3: 'Aperture Priority',
                    4: 'Shutter Priority',
                    5: 'Creative',
                    6: 'Action',
                    7: 'Portrait',
                    8: 'Landscape',
                }
                return programs.get(value, f"Mode {value}")

            elif tag_name == 'MeteringMode':
                modes = {
                    0: 'Unknown',
                    1: 'Average',
                    2: 'Center-Weighted',
                    3: 'Spot',
                    4: 'Multi-Spot',
                    5: 'Multi-Segment',
                    6: 'Partial',
                }
                return modes.get(value, f"Mode {value}")

            else:
                # Default: convert to string
                if isinstance(value, bytes):
                    try:
                        return value.decode('utf-8', errors='ignore').strip('\x00')
                    except:
                        return "(binary data)"
                return str(value)

        except Exception as e:
            logger.debug(f"Error formatting EXIF value {tag_name}: {e}")
            return str(value)

    def _parse_gps_info(self, gps_info: Dict) -> Optional[str]:
        """Parse GPS info from EXIF and return formatted coordinates."""
        try:
            from PIL.ExifTags import GPSTAGS

            # Build reverse lookup for GPS tags
            gps_tag_names = {v: k for k, v in GPSTAGS.items()}

            def get_gps_value(tag_name):
                tag_id = gps_tag_names.get(tag_name)
                return gps_info.get(tag_id) if tag_id else None

            lat = get_gps_value('GPSLatitude')
            lat_ref = get_gps_value('GPSLatitudeRef')
            lon = get_gps_value('GPSLongitude')
            lon_ref = get_gps_value('GPSLongitudeRef')

            if not all([lat, lat_ref, lon, lon_ref]):
                return None

            def convert_to_degrees(value):
                """Convert GPS coordinates to degrees."""
                if isinstance(value, tuple) and len(value) == 3:
                    d, m, s = value
                    # Handle IFDRational objects
                    if hasattr(d, 'numerator'):
                        d = float(d)
                    if hasattr(m, 'numerator'):
                        m = float(m)
                    if hasattr(s, 'numerator'):
                        s = float(s)
                    return d + m / 60.0 + s / 3600.0
                return 0

            lat_deg = convert_to_degrees(lat)
            lon_deg = convert_to_degrees(lon)

            if lat_ref == 'S':
                lat_deg = -lat_deg
            if lon_ref == 'W':
                lon_deg = -lon_deg

            return f"{lat_deg:.6f}, {lon_deg:.6f}"

        except Exception as e:
            logger.debug(f"Error parsing GPS info: {e}")
            return None

    def _load_revisions(self, file_hash: str):
        """Load and display revision history for the current file."""
        self.revisions_list.clear()
        self.revisions = []

        if not file_hash or file_hash == 'N/A':
            self.revision_info_label.setText("No hash available")
            return

        try:
            # Use PhotoDatabase to get revision chain
            from DuplicateFileDetection import PhotoDatabase

            db_path = self.db_metadata.database_path
            logger.debug(f"Loading revisions for hash {file_hash[:16]}... from database: {db_path}")

            with PhotoDatabase(db_path) as db:
                # Get the full revision chain (original to current)
                chain = db.get_revision_chain(file_hash)
                logger.debug(f"get_revision_chain returned {len(chain) if chain else 0} entries")

                if not chain:
                    logger.debug(f"No revision chain found for hash {file_hash[:16]}...")
                    self.revision_info_label.setText("No revisions found")
                    return

                self.revisions = chain
                logger.info(f"Revision chain for {file_hash[:16]}...: {len(chain)} entries")

                # Populate the list
                for i, rev in enumerate(chain):
                    rev_hash = rev.get('file_hash', '')
                    rev_path = rev.get('file_name', '')
                    rev_reason = rev.get('revision_reason')
                    rev_timestamp = rev.get('revision_timestamp', '')
                    is_current = (rev_hash == file_hash)
                    logger.debug(f"  [{i}] hash={rev_hash[:16]}..., reason={rev_reason}, is_current={is_current}")

                    # Format display text
                    if rev_reason:
                        label = f"v{i}: {rev_reason.title()}"
                    else:
                        label = f"v{i}: Original"

                    if rev_timestamp:
                        # Just show date portion
                        label += f" ({rev_timestamp[:10]})"

                    if is_current:
                        label += " [CURRENT]"

                    # Check if file exists
                    exists = os.path.exists(rev_path) if rev_path else False
                    if not exists:
                        label += " (missing)"

                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, rev)  # Store full revision data

                    # Style current item
                    if is_current:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)

                    # Gray out missing files
                    if not exists:
                        item.setForeground(Qt.gray)

                    self.revisions_list.addItem(item)

                count = len(chain)
                if count == 1:
                    self.revision_info_label.setText("Original file (no revisions)")
                else:
                    self.revision_info_label.setText(f"{count} versions in chain")

        except Exception as e:
            logger.error(f"Failed to load revisions: {e}", exc_info=True)
            self.revision_info_label.setText(f"Error loading revisions")

    def _on_revision_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on a revision item."""
        rev_data = item.data(Qt.UserRole)
        if not rev_data:
            return

        rev_path = rev_data.get('file_name', '')
        if not rev_path or not os.path.exists(rev_path):
            QMessageBox.warning(
                self, "File Not Found",
                f"Revision file not found:\n{rev_path}"
            )
            return

        # Ask user what to do
        from PySide6.QtWidgets import QInputDialog

        choice, ok = QInputDialog.getItem(
            self, "Open Revision",
            "How would you like to view this revision?",
            ["Preview in new window", "Open with system viewer"],
            0, False
        )

        if not ok:
            return

        if choice == "Preview in new window":
            self._show_revision_preview(rev_data)
        else:
            self._open_file_external(rev_path)

    def _show_revision_preview(self, rev_data: Dict):
        """Show a revision in a secondary preview window."""
        rev_path = rev_data.get('file_name', '')
        theme = get_theme()
        c = theme.colors

        # Create or reuse secondary preview window
        if not self.revision_preview_window:
            from ui.preview import ZoomableImageViewer

            self.revision_preview_window = QMainWindow(self)
            self.revision_preview_window.setWindowTitle("Revision Preview")
            self.revision_preview_window.setWindowFlags(Qt.Window)
            self.revision_preview_window.resize(800, 600)

            central = QWidget()
            layout = QVBoxLayout(central)

            # Header
            self._revision_header = QLabel()
            layout.addWidget(self._revision_header)

            # Viewer
            self._revision_viewer = ZoomableImageViewer()
            layout.addWidget(self._revision_viewer, 1)

            # Info
            self._revision_info = QLabel()
            self._revision_info.setWordWrap(True)
            layout.addWidget(self._revision_info)

            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.revision_preview_window.hide)
            layout.addWidget(close_btn)

            self.revision_preview_window.setCentralWidget(central)

        # Apply global and specific theme styling to secondary window
        self.revision_preview_window.setStyleSheet(theme.get_global_stylesheet())
        self._revision_header.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: bold;
            padding: 8px;
            background-color: {c.bg_secondary};
            color: {c.text_primary};
            border-radius: 4px;
        """)
        self._revision_info.setStyleSheet(f"padding: 8px; color: {c.text_muted};")
        if hasattr(self._revision_viewer, 'update_theme'):
            self._revision_viewer.update_theme()
        else:
            self._revision_viewer.setStyleSheet(f"background-color: {c.bg_tertiary};")

        # Update content
        rev_reason = rev_data.get('revision_reason', 'Original')
        rev_timestamp = rev_data.get('revision_timestamp', 'Unknown')
        rev_hash = rev_data.get('file_hash', 'N/A')

        self._revision_header.setText(
            f"Revision: {rev_reason.title() if rev_reason else 'Original'}"
        )

        self._revision_info.setText(
            f"Path: {rev_path}\n"
            f"Timestamp: {rev_timestamp}\n"
            f"Hash: {rev_hash}"
        )

        self._revision_viewer.load_image(rev_path)

        # Show window
        self.revision_preview_window.show()
        self.revision_preview_window.raise_()
        self.revision_preview_window.activateWindow()

    def _open_file_external(self, file_path: str):
        """Open file with system default application."""
        try:
            system = platform.system()
            if system == 'Windows':
                os.startfile(file_path)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', file_path], check=True)
            else:  # Linux and others
                subprocess.run(['xdg-open', file_path], check=True)
            logger.info(f"Opened file externally: {file_path}")
        except Exception as e:
            logger.error(f"Failed to open file: {e}", exc_info=True)
            QMessageBox.warning(
                self, "Error",
                f"Failed to open file:\n{str(e)}"
            )

    def _open_folder(self, file_path: str):
        """Open folder containing the file."""
        try:
            folder_path = os.path.dirname(file_path)
            system = platform.system()
            if system == 'Windows':
                subprocess.run(['explorer', '/select,', file_path], check=True)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', '-R', file_path], check=True)
            else:  # Linux and others
                subprocess.run(['xdg-open', folder_path], check=True)
            logger.info(f"Opened folder: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to open folder: {e}", exc_info=True)
            QMessageBox.warning(
                self, "Error",
                f"Failed to open folder:\n{str(e)}"
            )

    # Source file actions
    def _on_open_source_file(self):
        """Open source file with default application."""
        if not self.current_record:
            return
        source_path = self.current_record.get('source_path', '')
        if source_path and os.path.exists(source_path):
            self._open_file_external(source_path)

    def _on_open_source_folder(self):
        """Open folder containing the source file."""
        if not self.current_record:
            return
        source_path = self.current_record.get('source_path', '')
        if source_path and os.path.exists(source_path):
            self._open_folder(source_path)

    def _on_copy_source_path(self):
        """Copy source file path to clipboard."""
        if not self.current_record:
            return
        source_path = self.current_record.get('source_path', '')
        if source_path:
            QApplication.clipboard().setText(source_path)
            logger.info(f"Copied source path to clipboard: {source_path}")

    # Archive file actions
    def _on_open_archive_file(self):
        """Open archive file with default application."""
        if not self.current_record:
            return
        archive_path = self.current_record.get('archive_path') or self.current_record.get('file_name', '')
        if archive_path and os.path.exists(archive_path):
            self._open_file_external(archive_path)

    def _on_open_archive_folder(self):
        """Open folder containing the archive file."""
        if not self.current_record:
            return
        archive_path = self.current_record.get('archive_path') or self.current_record.get('file_name', '')
        if archive_path and os.path.exists(archive_path):
            self._open_folder(archive_path)

    def _on_copy_archive_path(self):
        """Copy archive file path to clipboard."""
        if not self.current_record:
            return
        archive_path = self.current_record.get('archive_path') or self.current_record.get('file_name', '')
        if archive_path:
            QApplication.clipboard().setText(archive_path)
            logger.info(f"Copied archive path to clipboard: {archive_path}")

    # Legacy method aliases for backward compatibility
    def on_open_file(self):
        """Open source file (legacy method)."""
        self._on_open_source_file()

    def on_open_folder(self):
        """Open source folder (legacy method)."""
        self._on_open_source_folder()

    def on_copy_path(self):
        """Copy source path (legacy method)."""
        self._on_copy_source_path()

    def on_correct_date(self):
        """Handle correct date button click."""
        if not self.current_record:
            return
        # Emit signal for parent to handle (opens dialog)
        self.correct_date_clicked.emit(self.current_record)

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event - save geometry."""
        self._save_geometry()

        # Close secondary preview if open
        if self.revision_preview_window:
            self.revision_preview_window.close()

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

        # Default: 1100x900 centered on parent
        self.resize(1100, 900)
        if self.parent():
            try:
                parent_geo = self.parent().window().frameGeometry()
                x = parent_geo.x() + (parent_geo.width() - 1100) // 2
                y = parent_geo.y() + (parent_geo.height() - 900) // 2
                self.move(x, y)
            except:
                pass  # Use default position if centering fails

        logger.debug("Using default preview window geometry (1100x900)")
