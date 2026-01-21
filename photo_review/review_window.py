"""
Photo Review Window

Modern main window for the Photo Review application with query-based photo selection,
floating search bar, selection action bar, and quick review actions.
"""

import os
import logging
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QStatusBar, QMessageBox, QApplication, QMenu, QProgressDialog,
    QLabel, QLineEdit, QPushButton, QFrame,
    QSizePolicy
)
from PySide6.QtCore import Qt, QSettings, QTimer, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence

from database_metadata import DatabaseMetadata
from ui.database_selector_dialog import DatabaseSelectorDialog
from photo_review.settings_dialog import PhotoReviewSettingsDialog

logger = logging.getLogger(__name__)


class FloatingSearchBar(QWidget):
    """
    Prominent floating search bar above the photo grid.
    """

    search_changed = Signal(str)
    search_submitted = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

        # Fixed height - don't expand vertically
        self.setFixedHeight(64)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(12)

        # Search icon label
        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 18px;")
        layout.addWidget(search_icon)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search photos... (Ctrl+K)")
        self.search_input.setMinimumHeight(40)
        self.search_input.textChanged.connect(self.search_changed.emit)
        self.search_input.returnPressed.connect(self.search_submitted.emit)
        layout.addWidget(self.search_input, 1)

        # Clear button
        self.clear_btn = QPushButton("✕")
        self.clear_btn.setFixedSize(32, 32)
        self.clear_btn.clicked.connect(self._clear_search)
        self.clear_btn.setVisible(False)
        layout.addWidget(self.clear_btn)

        # Keyboard shortcut hint
        hint_label = QLabel("Ctrl+K")
        hint_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(hint_label)

        # Connect text change to show/hide clear button
        self.search_input.textChanged.connect(
            lambda t: self.clear_btn.setVisible(bool(t))
        )

        self.setStyleSheet("""
            QWidget {
                background-color: #262626;
                border-bottom: 1px solid #333333;
            }
            QLineEdit {
                background-color: #333333;
                border: 2px solid #444444;
                border-radius: 12px;
                padding: 8px 16px;
                font-size: 15px;
                color: #FFFFFF;
            }
            QLineEdit:focus {
                border-color: #0066FF;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
            QPushButton {
                background-color: #444444;
                border: none;
                border-radius: 16px;
                color: #FFFFFF;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
        """)

    def _clear_search(self):
        self.search_input.clear()

    def focus_search(self):
        self.search_input.setFocus()
        self.search_input.selectAll()

    def get_text(self):
        return self.search_input.text()

    def set_text(self, text):
        self.search_input.setText(text)


class SelectionActionBar(QWidget):
    """
    Floating action bar that appears when items are selected.
    """

    delete_clicked = Signal()
    rotate_clicked = Signal()
    edit_clicked = Signal()
    correct_date_clicked = Signal()
    album_clicked = Signal()
    deselect_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selection_count = 0
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)  # No margins - parent bottom bar handles spacing
        layout.setSpacing(8)

        # Selection count
        self.count_label = QLabel("0 selected")
        self.count_label.setStyleSheet("""
            color: #FFFFFF;
            font-weight: 600;
            font-size: 14px;
            padding: 0 12px;
        """)
        layout.addWidget(self.count_label)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet("background-color: #555555;")
        layout.addWidget(separator)

        # Action buttons
        self.delete_btn = self._create_action_button("🗑 Delete", self.delete_clicked)
        layout.addWidget(self.delete_btn)

        self.rotate_btn = self._create_action_button("🔄 Rotate", self.rotate_clicked)
        layout.addWidget(self.rotate_btn)

        self.edit_btn = self._create_action_button("✏ Edit", self.edit_clicked)
        layout.addWidget(self.edit_btn)

        self.date_btn = self._create_action_button("📅 Fix Date", self.correct_date_clicked)
        layout.addWidget(self.date_btn)

        self.album_btn = self._create_action_button("📁 Album", self.album_clicked)
        layout.addWidget(self.album_btn)

        layout.addStretch()

        # Deselect button
        self.deselect_btn = self._create_action_button("✕ Deselect All", self.deselect_clicked)
        self.deselect_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: 1px solid #666666;
                color: #CCCCCC;
                padding: 0px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #444444;
                border-color: #888888;
            }
        """)
        layout.addWidget(self.deselect_btn)

        # Transparent background - inherits from parent bottom bar
        self.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)

    def _create_action_button(self, text, signal):
        btn = QPushButton(text)
        btn.clicked.connect(signal.emit)
        btn.setFixedHeight(34)
        btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: none;
                color: #FFFFFF;
                padding: 0px 16px;
                border-radius: 4px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0066FF;
            }
        """)
        return btn

    def update_selection(self, count):
        """Update the selection count display."""
        self._selection_count = count
        if count > 0:
            self.count_label.setText(f"{count:,} selected")
        else:
            self.count_label.setText("No selection")


class CollapsibleSection(QWidget):
    """
    A collapsible section with header and content area.
    """

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        self._is_expanded = True
        self._title = title
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header button
        self.header_btn = QPushButton(f"▼ {self._title}")
        self.header_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                border: none;
                border-radius: 4px;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 12px;
                text-align: left;
                padding: 8px 12px;
            }
            QPushButton:hover {
                background-color: #3d3d3d;
            }
        """)
        self.header_btn.clicked.connect(self._toggle)
        main_layout.addWidget(self.header_btn)

        # Content widget
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content_layout.setSpacing(4)
        main_layout.addWidget(self.content_widget)

    def _toggle(self):
        self._is_expanded = not self._is_expanded
        self.content_widget.setVisible(self._is_expanded)
        arrow = "▼" if self._is_expanded else "▶"
        self.header_btn.setText(f"{arrow} {self._title}")

    def add_row(self, label: str, value: str):
        """Add a label-value row to the content."""
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 2, 0, 2)
        row_layout.setSpacing(8)

        label_widget = QLabel(f"{label}:")
        label_widget.setStyleSheet("color: #888888; font-size: 11px; min-width: 80px;")
        label_widget.setAlignment(Qt.AlignRight | Qt.AlignTop)
        row_layout.addWidget(label_widget)

        value_widget = QLabel(value)
        value_widget.setStyleSheet("color: #FFFFFF; font-size: 11px;")
        value_widget.setWordWrap(True)
        value_widget.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row_layout.addWidget(value_widget, 1)

        self.content_layout.addWidget(row)

    def clear_content(self):
        """Clear all content rows."""
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


class FileDetailsPanel(QWidget):
    """
    Comprehensive file details panel showing file information, image properties, and EXIF data.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_file_path = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        # Create scroll area for content
        scroll_area = QWidget()
        scroll_layout = QVBoxLayout(scroll_area)
        scroll_layout.setContentsMargins(8, 8, 8, 8)
        scroll_layout.setSpacing(8)

        # Header with filename
        self.filename_label = QLabel("No file selected")
        self.filename_label.setStyleSheet("""
            font-weight: 600;
            font-size: 14px;
            color: #FFFFFF;
            padding: 8px 12px;
            background-color: #333333;
            border-radius: 4px;
        """)
        self.filename_label.setWordWrap(True)
        scroll_layout.addWidget(self.filename_label)

        # Quick status bar
        self.status_bar = QLabel("")
        self.status_bar.setStyleSheet("""
            font-size: 12px;
            color: #888888;
            padding: 4px 12px;
        """)
        scroll_layout.addWidget(self.status_bar)

        # Database Info section
        self.db_section = CollapsibleSection("Database Info")
        scroll_layout.addWidget(self.db_section)

        # File Info section
        self.file_section = CollapsibleSection("File Information")
        scroll_layout.addWidget(self.file_section)

        # Image Properties section
        self.image_section = CollapsibleSection("Image Properties")
        scroll_layout.addWidget(self.image_section)

        # EXIF section
        self.exif_section = CollapsibleSection("EXIF Data")
        scroll_layout.addWidget(self.exif_section)

        scroll_layout.addStretch()

        # Put scroll area in a QScrollArea widget
        from PySide6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidget(scroll_area)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background-color: #1A1A1A;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #262626;
                width: 10px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background-color: #444444;
                border-radius: 5px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #555555;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        main_layout.addWidget(scroll)

        self.setStyleSheet("""
            QWidget {
                background-color: #1A1A1A;
            }
        """)

    def update_info(self, record: dict):
        """Update all sections with file information."""
        # Clear all sections
        self.db_section.clear_content()
        self.file_section.clear_content()
        self.image_section.clear_content()
        self.exif_section.clear_content()

        if not record:
            self.filename_label.setText("No file selected")
            self.status_bar.setText("")
            self._current_file_path = None
            return

        # Get file path - prefer archive over source
        archive_path = record.get('archive_path') or record.get('file_name', '')
        source_path = record.get('source_path', '')
        file_path = archive_path if (archive_path and os.path.exists(archive_path)) else source_path
        self._current_file_path = file_path

        # Filename header
        filename = os.path.basename(file_path) if file_path else "Unknown"
        self.filename_label.setText(filename)

        # Build quick status
        status_parts = []
        year = record.get('create_year')
        month = record.get('create_month')
        day = record.get('create_day')
        if year:
            date_str = f"{year}"
            if month:
                date_str += f"-{str(month).zfill(2)}"
                if day:
                    date_str += f"-{str(day).zfill(2)}"
            status_parts.append(f"📅 {date_str}")

        date_source = record.get('date_source', '')
        if date_source:
            source_icons = {
                'exif': '✓ EXIF',
                'video_metadata': '🎬 Video',
                'os_metadata': '📂 File',
                'fallback': '⚠ Fallback'
            }
            status_parts.append(source_icons.get(date_source, date_source))

        status = self._get_status(record)
        if status and status != 'normal':
            status_labels = {
                'unreliable': '⚠ Unreliable',
                'corrected': '✓ Corrected',
                'reorganized': '📦 Reorganized',
                'revision': '🔄 Has Revisions'
            }
            status_parts.append(status_labels.get(status, status))

        self.status_bar.setText("  •  ".join(status_parts) if status_parts else "")

        # Populate Database Info section
        self._populate_db_info(record)

        # Populate File Info section
        if file_path and os.path.exists(file_path):
            self._populate_file_info(file_path)
            self._populate_image_info(file_path)
            self._populate_exif_info(file_path)
        else:
            self.file_section.add_row("Status", "File not found")

    def _get_status(self, record):
        """Determine status from record."""
        has_unreliable = record.get('has_unreliable_date', False)
        corrected_date = record.get('corrected_date')
        needs_reorg = record.get('needs_reorganization', False)
        has_revisions = record.get('revised_photo') is not None

        if has_revisions:
            return 'revision'
        if corrected_date and not needs_reorg:
            return 'reorganized'
        if corrected_date and needs_reorg:
            return 'corrected'
        if has_unreliable:
            return 'unreliable'
        return 'normal'

    def _populate_db_info(self, record: dict):
        """Populate database information section."""
        # File hash
        file_hash = record.get('file_hash', '')
        if file_hash:
            # Show truncated hash with full hash as tooltip
            short_hash = f"{file_hash[:16]}...{file_hash[-8:]}" if len(file_hash) > 24 else file_hash
            self.db_section.add_row("Hash", short_hash)

        # Archive path
        archive_path = record.get('archive_path') or record.get('file_name', '')
        if archive_path:
            self.db_section.add_row("Archive", archive_path)

        # Source path
        source_path = record.get('source_path', '')
        if source_path:
            self.db_section.add_row("Source", source_path)

        # Creation date from database
        year = record.get('create_year')
        month = record.get('create_month')
        day = record.get('create_day')
        if year:
            date_str = f"{year}"
            if month:
                date_str += f"-{str(month).zfill(2)}"
                if day:
                    date_str += f"-{str(day).zfill(2)}"
            self.db_section.add_row("DB Date", date_str)

        # Date source
        date_source = record.get('date_source', '')
        if date_source:
            self.db_section.add_row("Date Source", date_source.replace('_', ' ').title())

        # Corrected date
        corrected_date = record.get('corrected_date')
        if corrected_date:
            self.db_section.add_row("Corrected", corrected_date)

        # Flag reason
        flag_reason = record.get('flag_reason')
        if flag_reason:
            self.db_section.add_row("Flag Reason", flag_reason.replace('_', ' ').title())

        # Status
        status = self._get_status(record)
        self.db_section.add_row("Status", status.replace('_', ' ').title())

        # Revision info
        revised_photo = record.get('revised_photo')
        if revised_photo:
            self.db_section.add_row("Parent Hash", f"{revised_photo[:16]}...")

        original_hash = record.get('original_hash')
        if original_hash and original_hash != record.get('file_hash'):
            self.db_section.add_row("Original Hash", f"{original_hash[:16]}...")

    def _populate_file_info(self, file_path: str):
        """Populate file information section."""
        try:
            stat_info = os.stat(file_path)

            # File size
            size_bytes = stat_info.st_size
            if size_bytes < 1024:
                size_str = f"{size_bytes} bytes"
            elif size_bytes < 1024 * 1024:
                size_str = f"{size_bytes / 1024:.1f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                size_str = f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
            self.file_section.add_row("Size", size_str)

            # File extension
            _, ext = os.path.splitext(file_path)
            if ext:
                self.file_section.add_row("Type", ext.upper().lstrip('.'))

            # Modified time
            from datetime import datetime
            mtime = datetime.fromtimestamp(stat_info.st_mtime)
            self.file_section.add_row("Modified", mtime.strftime("%Y-%m-%d %H:%M:%S"))

            # Access time
            atime = datetime.fromtimestamp(stat_info.st_atime)
            self.file_section.add_row("Accessed", atime.strftime("%Y-%m-%d %H:%M:%S"))

            # Creation time (platform dependent)
            if hasattr(stat_info, 'st_birthtime'):
                # macOS
                ctime = datetime.fromtimestamp(stat_info.st_birthtime)
                self.file_section.add_row("Created", ctime.strftime("%Y-%m-%d %H:%M:%S"))
            elif hasattr(stat_info, 'st_ctime'):
                # Windows uses st_ctime as creation time, Linux as change time
                import platform
                if platform.system() == 'Windows':
                    ctime = datetime.fromtimestamp(stat_info.st_ctime)
                    self.file_section.add_row("Created", ctime.strftime("%Y-%m-%d %H:%M:%S"))

        except Exception as e:
            logger.warning(f"Could not get file info: {e}")
            self.file_section.add_row("Error", str(e))

    def _populate_image_info(self, file_path: str):
        """Populate image properties section."""
        # Check if it's an image
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif', '.bmp', '.webp', '.heic', '.heif'}
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in image_extensions:
            self.image_section.add_row("Type", "Not an image file")
            return

        try:
            from PIL import Image

            with Image.open(file_path) as img:
                # Dimensions
                width, height = img.size
                self.image_section.add_row("Dimensions", f"{width} × {height} px")

                # Megapixels
                megapixels = (width * height) / 1_000_000
                self.image_section.add_row("Megapixels", f"{megapixels:.2f} MP")

                # Aspect ratio
                from math import gcd
                divisor = gcd(width, height)
                aspect_w = width // divisor
                aspect_h = height // divisor
                # Simplify common ratios
                if aspect_w > 100 or aspect_h > 100:
                    ratio = width / height
                    if abs(ratio - 16/9) < 0.01:
                        aspect_str = "16:9"
                    elif abs(ratio - 4/3) < 0.01:
                        aspect_str = "4:3"
                    elif abs(ratio - 3/2) < 0.01:
                        aspect_str = "3:2"
                    elif abs(ratio - 1) < 0.01:
                        aspect_str = "1:1"
                    else:
                        aspect_str = f"{ratio:.2f}:1"
                else:
                    aspect_str = f"{aspect_w}:{aspect_h}"
                self.image_section.add_row("Aspect Ratio", aspect_str)

                # Format
                self.image_section.add_row("Format", img.format or "Unknown")

                # Color mode
                mode_descriptions = {
                    '1': '1-bit (B&W)',
                    'L': 'Grayscale',
                    'P': 'Palette',
                    'RGB': 'RGB Color',
                    'RGBA': 'RGB + Alpha',
                    'CMYK': 'CMYK',
                    'YCbCr': 'YCbCr',
                    'LAB': 'LAB Color',
                    'HSV': 'HSV Color',
                    'I': '32-bit Integer',
                    'F': '32-bit Float'
                }
                mode_str = mode_descriptions.get(img.mode, img.mode)
                self.image_section.add_row("Color Mode", mode_str)

                # Bits per pixel (approximate)
                mode_bits = {
                    '1': 1, 'L': 8, 'P': 8, 'RGB': 24, 'RGBA': 32,
                    'CMYK': 32, 'YCbCr': 24, 'LAB': 24, 'HSV': 24,
                    'I': 32, 'F': 32
                }
                bits = mode_bits.get(img.mode, 0)
                if bits:
                    self.image_section.add_row("Bit Depth", f"{bits} bits")

                # Animation info for GIFs
                if img.format == 'GIF':
                    try:
                        frames = 0
                        while True:
                            frames += 1
                            img.seek(frames)
                    except EOFError:
                        pass
                    if frames > 1:
                        self.image_section.add_row("Frames", str(frames))

        except Exception as e:
            logger.warning(f"Could not get image info: {e}")
            self.image_section.add_row("Error", str(e))

    def _populate_exif_info(self, file_path: str):
        """Populate EXIF data section."""
        # Check if it's an image that might have EXIF
        image_extensions = {'.jpg', '.jpeg', '.tiff', '.tif', '.heic', '.heif'}
        _, ext = os.path.splitext(file_path)
        if ext.lower() not in image_extensions:
            self.exif_section.add_row("Info", "EXIF not supported for this format")
            return

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS

            with Image.open(file_path) as img:
                exif_data = img._getexif()
                if not exif_data:
                    self.exif_section.add_row("Info", "No EXIF data found")
                    return

                # Map EXIF tag numbers to names
                exif_dict = {}
                for tag_id, value in exif_data.items():
                    tag_name = TAGS.get(tag_id, str(tag_id))
                    exif_dict[tag_name] = value

                # Define fields to display with formatting
                exif_fields = [
                    ('DateTimeOriginal', 'Date Taken', None),
                    ('DateTime', 'Date Modified', None),
                    ('Make', 'Camera Make', None),
                    ('Model', 'Camera Model', None),
                    ('LensModel', 'Lens', None),
                    ('ExposureTime', 'Exposure', self._format_exposure),
                    ('FNumber', 'Aperture', self._format_fnumber),
                    ('ISOSpeedRatings', 'ISO', None),
                    ('FocalLength', 'Focal Length', self._format_focal_length),
                    ('FocalLengthIn35mmFilm', '35mm Equiv', lambda v: f"{v}mm"),
                    ('ExposureBiasValue', 'Exp. Comp.', self._format_exposure_bias),
                    ('MeteringMode', 'Metering', self._format_metering_mode),
                    ('Flash', 'Flash', self._format_flash),
                    ('WhiteBalance', 'White Balance', lambda v: 'Auto' if v == 0 else 'Manual'),
                    ('ExposureProgram', 'Program', self._format_exposure_program),
                    ('Software', 'Software', None),
                    ('Artist', 'Artist', None),
                    ('Copyright', 'Copyright', None),
                    ('ImageDescription', 'Description', None),
                    ('Orientation', 'Orientation', self._format_orientation),
                ]

                fields_found = 0
                for exif_key, display_name, formatter in exif_fields:
                    if exif_key in exif_dict:
                        value = exif_dict[exif_key]
                        try:
                            if formatter:
                                value = formatter(value)
                            elif isinstance(value, bytes):
                                value = value.decode('utf-8', errors='ignore').strip()
                            else:
                                value = str(value)
                            if value:
                                self.exif_section.add_row(display_name, value)
                                fields_found += 1
                        except Exception:
                            pass

                # Handle GPS info separately
                if 'GPSInfo' in exif_dict:
                    gps_info = exif_dict['GPSInfo']
                    gps_str = self._format_gps(gps_info)
                    if gps_str:
                        self.exif_section.add_row("GPS", gps_str)
                        fields_found += 1

                if fields_found == 0:
                    self.exif_section.add_row("Info", "EXIF data present but no recognized fields")

        except ImportError:
            self.exif_section.add_row("Error", "PIL not available")
        except Exception as e:
            logger.warning(f"Could not read EXIF data: {e}")
            self.exif_section.add_row("Error", str(e))

    def _format_exposure(self, value):
        """Format exposure time value."""
        if isinstance(value, tuple) and len(value) == 2:
            if value[0] == 0 or value[1] == 0:
                return None
            ratio = value[0] / value[1]
            if ratio >= 1:
                return f"{ratio:.1f}s"
            else:
                return f"1/{int(1/ratio)}s"
        return f"{value}s"

    def _format_fnumber(self, value):
        """Format f-number value."""
        if isinstance(value, tuple) and len(value) == 2:
            if value[1] == 0:
                return None
            return f"f/{value[0]/value[1]:.1f}"
        return f"f/{value}"

    def _format_focal_length(self, value):
        """Format focal length value."""
        if isinstance(value, tuple) and len(value) == 2:
            if value[1] == 0:
                return None
            return f"{value[0]/value[1]:.0f}mm"
        return f"{value}mm"

    def _format_exposure_bias(self, value):
        """Format exposure bias value."""
        if isinstance(value, tuple) and len(value) == 2:
            if value[1] == 0:
                return None
            ev = value[0] / value[1]
            sign = '+' if ev > 0 else ''
            return f"{sign}{ev:.1f} EV"
        return f"{value} EV"

    def _format_metering_mode(self, value):
        """Format metering mode value."""
        modes = {
            0: 'Unknown',
            1: 'Average',
            2: 'Center-weighted',
            3: 'Spot',
            4: 'Multi-spot',
            5: 'Multi-segment',
            6: 'Partial',
            255: 'Other'
        }
        return modes.get(value, f'Mode {value}')

    def _format_flash(self, value):
        """Format flash value."""
        if value == 0:
            return 'No Flash'
        elif value == 1:
            return 'Fired'
        elif value == 5:
            return 'Fired, No Strobe'
        elif value == 7:
            return 'Fired, Strobe'
        elif value == 9:
            return 'Fired, Compulsory'
        elif value == 16:
            return 'No Flash (Compulsory)'
        elif value == 24:
            return 'No Flash (Auto)'
        elif value == 25:
            return 'Fired (Auto)'
        elif value == 32:
            return 'No Flash Function'
        else:
            return f'Flash ({value})'

    def _format_exposure_program(self, value):
        """Format exposure program value."""
        programs = {
            0: 'Not Defined',
            1: 'Manual',
            2: 'Program AE',
            3: 'Aperture Priority',
            4: 'Shutter Priority',
            5: 'Creative',
            6: 'Action',
            7: 'Portrait',
            8: 'Landscape'
        }
        return programs.get(value, f'Program {value}')

    def _format_orientation(self, value):
        """Format orientation value."""
        orientations = {
            1: 'Normal',
            2: 'Mirrored',
            3: 'Rotated 180°',
            4: 'Mirrored & 180°',
            5: 'Mirrored & 90° CW',
            6: 'Rotated 90° CW',
            7: 'Mirrored & 90° CCW',
            8: 'Rotated 90° CCW'
        }
        return orientations.get(value, f'Orientation {value}')

    def _format_gps(self, gps_info):
        """Format GPS information."""
        try:
            from PIL.ExifTags import GPSTAGS

            # Parse GPS dict
            gps_dict = {}
            for key, value in gps_info.items():
                tag = GPSTAGS.get(key, key)
                gps_dict[tag] = value

            lat = gps_dict.get('GPSLatitude')
            lat_ref = gps_dict.get('GPSLatitudeRef', 'N')
            lon = gps_dict.get('GPSLongitude')
            lon_ref = gps_dict.get('GPSLongitudeRef', 'E')

            if lat and lon:
                # Convert to decimal degrees
                def to_degrees(values):
                    d = float(values[0][0]) / float(values[0][1]) if isinstance(values[0], tuple) else float(values[0])
                    m = float(values[1][0]) / float(values[1][1]) if isinstance(values[1], tuple) else float(values[1])
                    s = float(values[2][0]) / float(values[2][1]) if isinstance(values[2], tuple) else float(values[2])
                    return d + m/60 + s/3600

                lat_deg = to_degrees(lat)
                lon_deg = to_degrees(lon)

                if lat_ref == 'S':
                    lat_deg = -lat_deg
                if lon_ref == 'W':
                    lon_deg = -lon_deg

                return f"{lat_deg:.6f}, {lon_deg:.6f}"
            return "Present"
        except Exception:
            return "Present"


class PhotoReviewWindow(QMainWindow):
    """Modern main window for Photo Review application."""

    def __init__(self, splash_callback=None):
        super().__init__()
        self.current_database_path = None
        self.database_metadata = None
        self.thumbnail_cache = None
        self.settings = QSettings("PyPhotoOrganizer", "PhotoReview")
        self.splash_callback = splash_callback
        self._is_dark_mode = True  # Default to dark mode

        # Components (initialized after database selection)
        self.query_panel = None
        self.grid_view = None
        self.grid_model = None
        self.preview_panel = None
        self.detached_preview = None
        self.search_bar = None
        self.action_bar = None
        self.file_details_panel = None
        self.preview_splitter = None

        if self.splash_callback:
            self.splash_callback("Creating interface...")

        self.init_ui()

        if self.splash_callback:
            self.splash_callback("Restoring window position...")

        self.restore_window_geometry()

        if self.splash_callback:
            self.splash_callback("Loading settings...")

        QTimer.singleShot(100, self.select_database_on_startup)

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Photo Review - PyPhotoOrganizer")
        self.resize(1400, 900)

        # Apply dark theme by default
        self._apply_theme()

        self._create_menu_bar()

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Select a database to begin")

        # Create central widget with placeholder
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Placeholder label
        self.placeholder_label = QLabel(
            "📸 Select a database to begin reviewing photos.\n\n"
            "Use File > Open Database to select a different database."
        )
        self.placeholder_label.setAlignment(Qt.AlignCenter)
        self.placeholder_label.setStyleSheet(
            "font-size: 16px; color: #888888; padding: 50px;"
        )
        self.main_layout.addWidget(self.placeholder_label)

        # Set up keyboard shortcut for search
        self._setup_shortcuts()

    def _apply_theme(self):
        """Apply the current theme to the window."""
        if self._is_dark_mode:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #1A1A1A;
                }
                QStatusBar {
                    background-color: #262626;
                    color: #888888;
                    border-top: 1px solid #333333;
                }
                QMenuBar {
                    background-color: #262626;
                    color: #FFFFFF;
                    border-bottom: 1px solid #333333;
                }
                QMenuBar::item:selected {
                    background-color: #333333;
                }
                QMenu {
                    background-color: #262626;
                    color: #FFFFFF;
                    border: 1px solid #333333;
                }
                QMenu::item:selected {
                    background-color: #0066FF;
                }
                QMenu::separator {
                    background-color: #333333;
                    height: 1px;
                    margin: 4px 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                QMainWindow {
                    background-color: #F5F5F5;
                }
                QStatusBar {
                    background-color: #FFFFFF;
                    color: #666666;
                    border-top: 1px solid #E0E0E0;
                }
                QMenuBar {
                    background-color: #FFFFFF;
                    color: #333333;
                    border-bottom: 1px solid #E0E0E0;
                }
                QMenuBar::item:selected {
                    background-color: #E8E8E8;
                }
                QMenu {
                    background-color: #FFFFFF;
                    color: #333333;
                    border: 1px solid #E0E0E0;
                }
                QMenu::item:selected {
                    background-color: #0066FF;
                    color: white;
                }
            """)

    def _setup_shortcuts(self):
        """Set up keyboard shortcuts."""
        # Ctrl+K for search focus
        from PySide6.QtGui import QShortcut
        search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        search_shortcut.activated.connect(self._focus_search)

    def _focus_search(self):
        """Focus the search bar."""
        if self.search_bar:
            self.search_bar.focus_search()

    def _create_menu_bar(self):
        """Create the menu bar with icons."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_db_action = QAction("📂 &Open Database...", self)
        open_db_action.setShortcut("Ctrl+O")
        open_db_action.triggered.connect(self.open_database_dialog)
        file_menu.addAction(open_db_action)

        file_menu.addSeparator()

        exit_action = QAction("🚪 E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Query menu
        query_menu = menubar.addMenu("&Query")

        run_query_action = QAction("▶ &Run Query", self)
        run_query_action.setShortcut("F5")
        run_query_action.triggered.connect(self.run_current_query)
        query_menu.addAction(run_query_action)

        save_query_action = QAction("💾 &Save Query...", self)
        save_query_action.setShortcut("Ctrl+S")
        save_query_action.triggered.connect(self.save_current_query)
        query_menu.addAction(save_query_action)

        query_menu.addSeparator()

        clear_filters_action = QAction("✕ &Clear All Filters", self)
        clear_filters_action.setShortcut("Ctrl+Shift+C")
        clear_filters_action.triggered.connect(self.clear_all_filters)
        query_menu.addAction(clear_filters_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        small_thumb_action = QAction("🔍 Small Thumbnails (150px)", self)
        small_thumb_action.setShortcut("1")
        small_thumb_action.triggered.connect(lambda: self.set_thumbnail_size(150))
        view_menu.addAction(small_thumb_action)

        medium_thumb_action = QAction("🔍 Medium Thumbnails (200px)", self)
        medium_thumb_action.setShortcut("2")
        medium_thumb_action.triggered.connect(lambda: self.set_thumbnail_size(200))
        view_menu.addAction(medium_thumb_action)

        large_thumb_action = QAction("🔍 Large Thumbnails (300px)", self)
        large_thumb_action.setShortcut("3")
        large_thumb_action.triggered.connect(lambda: self.set_thumbnail_size(300))
        view_menu.addAction(large_thumb_action)

        view_menu.addSeparator()

        toggle_preview_action = QAction("👁 Toggle &Preview Panel", self)
        toggle_preview_action.setShortcut("P")
        toggle_preview_action.triggered.connect(self.toggle_preview_panel)
        view_menu.addAction(toggle_preview_action)

        view_menu.addSeparator()

        # Theme toggle
        self.theme_action = QAction("🌙 Switch to Light Mode", self)
        self.theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.theme_action)

        view_menu.addSeparator()

        # Settings
        settings_action = QAction("⚙ &Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self.show_settings_dialog)
        view_menu.addAction(settings_action)

        # Actions menu
        actions_menu = menubar.addMenu("&Actions")

        delete_action = QAction("🗑 &Delete Selected...", self)
        delete_action.setShortcut("Delete")
        delete_action.triggered.connect(self.delete_selected)
        actions_menu.addAction(delete_action)

        rotate_action = QAction("🔄 &Rotate Selected...", self)
        rotate_action.setShortcut("R")
        rotate_action.triggered.connect(self.rotate_selected)
        actions_menu.addAction(rotate_action)

        edit_action = QAction("✏ &Edit Selected...", self)
        edit_action.setShortcut("E")
        edit_action.triggered.connect(self.edit_selected)
        actions_menu.addAction(edit_action)

        correct_date_action = QAction("📅 &Correct Date...", self)
        correct_date_action.setShortcut("D")
        correct_date_action.triggered.connect(self.correct_date_selected)
        actions_menu.addAction(correct_date_action)

        reorganize_action = QAction("📦 Reorganize &Marked Files...", self)
        reorganize_action.setShortcut("Ctrl+M")
        reorganize_action.triggered.connect(self.reorganize_marked_files)
        actions_menu.addAction(reorganize_action)

        actions_menu.addSeparator()

        manage_paths_action = QAction("⚠ Manage &Unreliable Paths...", self)
        manage_paths_action.triggered.connect(self.manage_unreliable_paths)
        actions_menu.addAction(manage_paths_action)

        actions_menu.addSeparator()

        select_all_action = QAction("☑ Select &All", self)
        select_all_action.setShortcut("Ctrl+A")
        select_all_action.triggered.connect(self.select_all)
        actions_menu.addAction(select_all_action)

        deselect_all_action = QAction("☐ D&eselect All", self)
        deselect_all_action.setShortcut("Escape")
        deselect_all_action.triggered.connect(self.deselect_all)
        actions_menu.addAction(deselect_all_action)

        # Albums menu
        albums_menu = menubar.addMenu("Al&bums")

        add_to_album_action = QAction("➕ Add to &Album...", self)
        add_to_album_action.setShortcut("Ctrl+Shift+A")
        add_to_album_action.triggered.connect(self.add_selected_to_album)
        albums_menu.addAction(add_to_album_action)

        albums_menu.addSeparator()

        manage_albums_action = QAction("📁 &Manage Albums...", self)
        manage_albums_action.triggered.connect(self.manage_albums)
        albums_menu.addAction(manage_albums_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        shortcuts_action = QAction("⌨ &Keyboard Shortcuts", self)
        shortcuts_action.setShortcut("F1")
        shortcuts_action.triggered.connect(self.show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("ℹ &About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def toggle_theme(self):
        """Toggle between light and dark mode."""
        self._is_dark_mode = not self._is_dark_mode
        self._apply_theme()

        if self._is_dark_mode:
            self.theme_action.setText("🌙 Switch to Light Mode")
        else:
            self.theme_action.setText("☀ Switch to Dark Mode")

        # Save preference
        self.settings.setValue("dark_mode", self._is_dark_mode)

    def show_settings_dialog(self):
        """Show the settings dialog."""
        if not hasattr(self, 'database_metadata') or not self.database_metadata:
            QMessageBox.information(
                self,
                "No Database",
                "Please open a database first before accessing settings."
            )
            return

        # Get thumbnail cache if available
        thumbnail_cache = getattr(self, 'thumbnail_cache', None)

        dialog = PhotoReviewSettingsDialog(
            db_metadata=self.database_metadata,
            thumbnail_cache=thumbnail_cache,
            is_dark_mode=self._is_dark_mode,
            parent=self
        )

        # Connect settings changed signal to reinitialize cache
        dialog.settings_changed.connect(self._on_cache_settings_changed)

        dialog.exec()

    def _on_cache_settings_changed(self):
        """Handle cache settings change - reinitialize thumbnail cache."""
        logger.info("Cache settings changed, reinitializing thumbnail cache...")

        # Store current state
        old_cache = getattr(self, 'thumbnail_cache', None)

        # Reinitialize the thumbnail cache with new settings
        self._init_thumbnail_cache()

        # Update grid view with new cache if it exists
        if hasattr(self, 'grid_view') and self.grid_view:
            self.grid_view.set_thumbnail_cache(self.thumbnail_cache)
            # Refresh the current view to use new cache
            self.grid_view.viewport().update()

        # Clean up old cache if it exists
        if old_cache:
            try:
                old_cache.shutdown()
            except Exception as e:
                logger.warning(f"Failed to shutdown old cache: {e}")

        self.status_bar.showMessage("Cache settings applied", 3000)

    def select_database_on_startup(self):
        """Show database selector on startup."""
        dialog = DatabaseSelectorDialog(self)
        result = dialog.exec()

        if result:
            database_path = dialog.get_selected_database()
            if database_path:
                self.set_database(database_path)
        else:
            QMessageBox.warning(
                self,
                "Database Required",
                "Photo Review requires a database to operate.\n\n"
                "You must either:\n"
                "- Select an existing database\n"
                "- Create a new database\n\n"
                "The application will now close."
            )
            QApplication.quit()

    def open_database_dialog(self):
        """Show database selector dialog."""
        dialog = DatabaseSelectorDialog(self)
        result = dialog.exec()

        if result:
            database_path = dialog.get_selected_database()
            if database_path:
                self.set_database(database_path)

    def set_database(self, database_path: str):
        """Set the current database and initialize components."""
        logger.info(f"Loading database: {database_path}")

        self.current_database_path = database_path
        self.database_metadata = DatabaseMetadata(database_path)
        self.db_metadata = self.database_metadata

        self.database_metadata.ensure_all_tables()
        self._init_thumbnail_cache()
        self._build_main_ui()

        metadata = self.database_metadata.get_metadata()
        if metadata:
            db_name = metadata.get('database_name', 'Unknown')
            self.setWindowTitle(f"Photo Review - {db_name}")
            self.status_bar.showMessage(f"Database loaded: {db_name}")

        self._restore_last_query()

    def _init_thumbnail_cache(self):
        """Initialize the thumbnail cache system using database settings."""
        from triage.thumbnail_cache import ThumbnailCache

        cache_dir = self.database_metadata.get_thumbnail_cache_dir()
        if not cache_dir:
            archive_location = self.database_metadata.get_archive_location()
            if archive_location:
                cache_dir = os.path.join(archive_location, '.thumbnails')
            else:
                cache_dir = os.path.join(os.path.dirname(self.current_database_path), '.thumbnails')

        # Read cache settings from database
        cache_memory_mb = self.database_metadata.get_cache_memory_mb()
        worker_threads = self.database_metadata.get_cache_worker_threads()

        # Calculate memory items from MB (estimate ~150KB per thumbnail)
        memory_items = int((cache_memory_mb * 1024 * 1024) / (150 * 1024))

        logger.info(f"Initializing thumbnail cache at: {cache_dir}")
        logger.info(f"  Memory cache: {cache_memory_mb}MB (~{memory_items:,} thumbnails)")
        logger.info(f"  Worker threads: {worker_threads}")

        self.thumbnail_cache = ThumbnailCache(
            db_path=self.current_database_path,
            cache_dir=cache_dir,
            memory_size=memory_items,
            disk_size_gb=5,
            worker_threads=worker_threads
        )

    def _build_main_ui(self):
        """Build the main UI after database is loaded."""
        if self.placeholder_label:
            self.main_layout.removeWidget(self.placeholder_label)
            self.placeholder_label.deleteLater()
            self.placeholder_label = None

        from photo_review.query_panel import QueryPanel
        from photo_review.photo_grid_view import PhotoGridView
        from photo_review.photo_grid_model import PhotoGridModel

        # Floating search bar at top
        self.search_bar = FloatingSearchBar()
        self.search_bar.search_changed.connect(self._on_search_changed)
        self.search_bar.search_submitted.connect(self._on_search_submitted)
        self.main_layout.addWidget(self.search_bar)

        # Main content area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)
        content_layout.addWidget(self.main_splitter)

        # Left: Query Panel
        self.query_panel = QueryPanel(
            db_metadata=self.database_metadata,
            db_path=self.current_database_path,
            parent=self
        )
        self.query_panel.setMinimumWidth(280)
        self.query_panel.setMaximumWidth(400)
        self.main_splitter.addWidget(self.query_panel)

        # Right: Grid + Preview
        self.right_splitter = QSplitter(Qt.Vertical)
        self.main_splitter.addWidget(self.right_splitter)

        # Grid container
        grid_container = QWidget()
        grid_layout = QVBoxLayout(grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setSpacing(0)

        # Grid info bar
        self.grid_info_bar = QWidget()
        self.grid_info_bar.setStyleSheet("""
            background-color: #262626;
            border-bottom: 1px solid #333333;
        """)
        info_layout = QHBoxLayout(self.grid_info_bar)
        info_layout.setContentsMargins(12, 8, 12, 8)

        self.photo_count_label = QLabel("No photos loaded")
        self.photo_count_label.setStyleSheet("color: #888888; font-size: 13px;")
        info_layout.addWidget(self.photo_count_label)
        info_layout.addStretch()

        self.selection_count_label = QLabel("")
        self.selection_count_label.setStyleSheet("color: #0066FF; font-weight: 600; font-size: 13px;")
        info_layout.addWidget(self.selection_count_label)

        grid_layout.addWidget(self.grid_info_bar)

        # Grid model and view
        self.grid_model = PhotoGridModel(self.thumbnail_cache, parent=self)
        self.grid_view = PhotoGridView(self.grid_model, parent=self)
        grid_layout.addWidget(self.grid_view)

        self.right_splitter.addWidget(grid_container)

        # Preview panel with info bar
        self._create_preview_panel()
        self.right_splitter.addWidget(self.preview_panel)

        self.main_layout.addWidget(content_widget)

        # Bottom bar with action buttons (left) and close button (right)
        bottom_bar = QWidget()
        bottom_bar.setStyleSheet("""
            QWidget {
                background-color: #262626;
                border-top: 1px solid #333333;
            }
        """)
        bottom_bar.setFixedHeight(50)
        bottom_layout = QHBoxLayout(bottom_bar)
        bottom_layout.setContentsMargins(16, 8, 16, 8)

        # Selection action bar (left side of bottom bar)
        self.action_bar = SelectionActionBar()
        self.action_bar.delete_clicked.connect(self.delete_selected)
        self.action_bar.rotate_clicked.connect(self.rotate_selected)
        self.action_bar.edit_clicked.connect(self.edit_selected)
        self.action_bar.correct_date_clicked.connect(self.correct_date_selected)
        self.action_bar.album_clicked.connect(self.add_selected_to_album)
        self.action_bar.deselect_clicked.connect(self.deselect_all)
        bottom_layout.addWidget(self.action_bar)

        bottom_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setFixedHeight(34)
        self.close_btn.setMinimumWidth(100)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                border: none;
                padding: 0px 20px;
            }
            QPushButton:hover {
                background-color: #DC2626;
            }
        """)
        self.close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self.close_btn)

        self.main_layout.addWidget(bottom_bar)

        # Set splitter sizes and stretch factors
        self.main_splitter.setSizes([300, 1100])
        # Query panel (index 0) doesn't stretch, grid area (index 1) takes all extra space
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)

        self.right_splitter.setSizes([700, 200])
        # Grid (index 0) takes extra space, preview (index 1) stays fixed
        self.right_splitter.setStretchFactor(0, 1)
        self.right_splitter.setStretchFactor(1, 0)

        self._connect_signals()
        self._restore_splitter_states()

        saved_thumb_size = self.settings.value("thumbnail_size", 200, type=int)
        self.grid_view.set_thumbnail_size_pixels(saved_thumb_size)

    def _create_preview_panel(self):
        """Create the preview panel with image viewer and file details."""
        from ui.preview import ZoomableImageViewer

        self.preview_panel = QWidget()
        preview_layout = QVBoxLayout(self.preview_panel)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(0)

        # Preview header
        preview_header = QWidget()
        preview_header.setStyleSheet("""
            background-color: #262626;
            border-bottom: 1px solid #333333;
        """)
        header_layout = QHBoxLayout(preview_header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        header_label = QLabel("👁 Preview & Details")
        header_label.setStyleSheet("font-weight: 600; color: #FFFFFF; font-size: 13px;")
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        preview_layout.addWidget(preview_header)

        # Horizontal splitter for image viewer and file details
        self.preview_splitter = QSplitter(Qt.Horizontal)

        # Image viewer (left side)
        self.image_viewer = ZoomableImageViewer(dark_mode=True)
        self.preview_splitter.addWidget(self.image_viewer)

        # File details panel (right side)
        self.file_details_panel = FileDetailsPanel()
        self.file_details_panel.setMinimumWidth(280)
        self.file_details_panel.setMaximumWidth(500)
        self.preview_splitter.addWidget(self.file_details_panel)

        # Set splitter sizes (70% image, 30% details)
        self.preview_splitter.setSizes([700, 300])
        self.preview_splitter.setStretchFactor(0, 1)  # Image viewer stretches
        self.preview_splitter.setStretchFactor(1, 0)  # Details panel fixed

        preview_layout.addWidget(self.preview_splitter, 1)

    def _connect_signals(self):
        """Connect component signals."""
        self.query_panel.query_executed.connect(self.on_query_executed)
        self.query_panel.folder_selected.connect(self.on_folder_selected)

        self.grid_model.data_loaded.connect(self.on_data_loaded)
        self.grid_view.selection_changed.connect(self.on_selection_changed)
        self.grid_view.item_activated.connect(self.on_item_activated)

        self.grid_view.delete_requested.connect(self.delete_selected)
        self.grid_view.rotate_requested.connect(self.rotate_selected)
        self.grid_view.correct_date_requested.connect(self.correct_date_selected)
        self.grid_view.add_to_album_requested.connect(self.add_selected_to_album)
        self.grid_view.reorganize_requested.connect(self.reorganize_marked_files)
        self.grid_view.open_file_requested.connect(self.open_selected_file)
        self.grid_view.open_folder_requested.connect(self.open_selected_folder)
        self.grid_view.copy_path_requested.connect(self.copy_selected_path)
        self.grid_view.refresh_thumbnail_requested.connect(self.refresh_selected_thumbnails)
        self.grid_view.deselect_all_requested.connect(self.deselect_all)

    def _on_search_changed(self, text):
        """Handle floating search bar text change."""
        # Sync with query panel
        if self.query_panel:
            self.query_panel.search_input.setText(text)

    def _on_search_submitted(self):
        """Handle search submit from floating search bar."""
        if self.query_panel:
            self.query_panel.execute_query()

    def _restore_last_query(self):
        """Restore the last query or folder from settings."""
        state = self.database_metadata.get_photo_review_state()
        if state:
            last_query = state.get('last_query')
            last_folder = state.get('last_folder')

            if last_query:
                logger.info(f"Restoring last query: {last_query}")
                self.query_panel.set_filters(last_query)

                # Sync search to floating bar
                if last_query.get('search_text') and self.search_bar:
                    self.search_bar.set_text(last_query['search_text'])

                self.query_panel.execute_query()
            elif last_folder:
                logger.info(f"Restoring last folder: {last_folder}")
                self.query_panel.set_folder(last_folder)

    def _restore_splitter_states(self):
        """Restore splitter states from settings."""
        main_splitter_state = self.settings.value("main_splitter")
        if main_splitter_state:
            self.main_splitter.restoreState(main_splitter_state)

        right_splitter_state = self.settings.value("right_splitter")
        if right_splitter_state:
            self.right_splitter.restoreState(right_splitter_state)

        preview_splitter_state = self.settings.value("preview_splitter")
        if preview_splitter_state and self.preview_splitter:
            self.preview_splitter.restoreState(preview_splitter_state)

        # Restore preview panel visibility (default to hidden for performance)
        preview_visible = self.settings.value("preview_panel_visible", False, type=bool)
        if self.preview_panel:
            if preview_visible:
                self.preview_panel.show()
            else:
                self.preview_panel.hide()

    # -------------------------------------------------------------------------
    # Query and Data Loading
    # -------------------------------------------------------------------------

    def on_query_executed(self, results: list):
        """Handle query execution results."""
        logger.info(f"Query returned {len(results)} results")
        self.grid_model.load_data(results)

    def on_folder_selected(self, folder_path: str):
        """Handle folder selection."""
        logger.info(f"Folder selected: {folder_path}")

    def on_data_loaded(self, count: int):
        """Handle data loaded into grid."""
        self.photo_count_label.setText(f"{count:,} photos")
        self.status_bar.showMessage(f"Loaded {count:,} photos")

    def on_selection_changed(self, selected_hashes: list):
        """Handle grid selection change."""
        count = len(selected_hashes)

        # Update selection count label
        if count > 0:
            self.selection_count_label.setText(f"{count:,} selected")
        else:
            self.selection_count_label.setText("")

        # Update action bar
        if self.action_bar:
            self.action_bar.update_selection(count)

        # Update preview - ONLY if preview panel is visible (performance optimization)
        # When preview is hidden, skip loading images and parsing EXIF data
        if self.preview_panel and self.preview_panel.isVisible():
            if count == 1 and selected_hashes:
                record = self.grid_model.get_record_by_hash(selected_hashes[0])
                if record:
                    file_path = record.get('archive_path') or record.get('source_path', '')
                    if file_path and os.path.exists(file_path):
                        self.image_viewer.load_image(file_path)

                    # Update file details panel
                    if self.file_details_panel:
                        self.file_details_panel.update_info(record)
            elif count == 0:
                # Clear file details panel
                if self.file_details_panel:
                    self.file_details_panel.update_info(None)

        # Also update detached preview window if it's open (keep in sync with selection)
        if self.detached_preview and self.detached_preview.isVisible():
            if count >= 1 and selected_hashes:
                record = self.grid_model.get_record_by_hash(selected_hashes[0])
                if record:
                    self.detached_preview.update_preview(record)

    def on_item_activated(self, record: dict):
        """Handle double-click or space on grid item."""
        self._show_detached_preview(record)

    def _show_detached_preview(self, record: dict):
        """Show the detached preview window with the given record."""
        from ui.detachable_preview_window import DetachablePreviewWindow

        if not self.detached_preview:
            self.detached_preview = DetachablePreviewWindow(
                db_metadata=self.database_metadata,
                parent=self
            )
            self.detached_preview.setWindowTitle("Photo Preview - Photo Review")
            self.detached_preview.correct_date_clicked.connect(self._on_preview_correct_date)

        self.detached_preview.update_preview(record)
        self.detached_preview.show()
        self.detached_preview.raise_()
        self.detached_preview.activateWindow()

    def _on_preview_correct_date(self, record: dict):
        """Handle correct date request from preview window."""
        from ui.date_correction_dialog import DateCorrectionDialog

        dialog = DateCorrectionDialog(self, [record], batch_mode=False)
        dialog.exec()
        self.run_current_query()

    # -------------------------------------------------------------------------
    # Query Actions
    # -------------------------------------------------------------------------

    def run_current_query(self):
        """Run the current query."""
        if self.query_panel:
            self.query_panel.execute_query()

    def save_current_query(self):
        """Save the current query."""
        if self.query_panel:
            self.query_panel.save_current_query()

    def clear_all_filters(self):
        """Clear all query filters."""
        if self.query_panel:
            self.query_panel.clear_filters()
        if self.search_bar:
            self.search_bar.set_text("")

    # -------------------------------------------------------------------------
    # View Actions
    # -------------------------------------------------------------------------

    def set_thumbnail_size(self, size: int):
        """Set thumbnail size."""
        if self.grid_view:
            self.grid_view.set_thumbnail_size_pixels(size)
        self.settings.setValue("thumbnail_size", size)

    def toggle_preview_panel(self):
        """Toggle preview panel visibility."""
        if self.preview_panel:
            if self.preview_panel.isVisible():
                self.preview_panel.hide()
            else:
                self.preview_panel.show()
                # When showing the panel, load content for the current selection
                self._load_preview_for_current_selection()

    def _load_preview_for_current_selection(self):
        """Load preview content for the currently selected item."""
        if not self.grid_view:
            return

        selected_hashes = self.grid_view.get_selected_hashes()
        if len(selected_hashes) == 1:
            record = self.grid_model.get_record_by_hash(selected_hashes[0])
            if record:
                file_path = record.get('archive_path') or record.get('source_path', '')
                if file_path and os.path.exists(file_path):
                    self.image_viewer.load_image(file_path)

                if self.file_details_panel:
                    self.file_details_panel.update_info(record)

    # -------------------------------------------------------------------------
    # File Actions
    # -------------------------------------------------------------------------

    def delete_selected(self):
        """Delete selected files to vault."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to delete.")
            return

        delete_vault = self.database_metadata.get_delete_vault_location()
        if not delete_vault:
            QMessageBox.warning(
                self, "Delete Vault Not Configured",
                "Please configure Delete Vault location in the main application settings."
            )
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"🗑 Delete {len(selected)} file(s) to Delete Vault?\n\n"
            f"Files will be moved to:\n{delete_vault}\n\n"
            f"Files can be restored later.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        from ui.delete_worker import DeleteWorker

        self.delete_worker = DeleteWorker(
            records=selected,
            delete_vault_path=delete_vault,
            db_path=self.current_database_path,
            worker_logger=logger
        )

        self.delete_progress = QProgressDialog(
            "Deleting files...", "Cancel", 0, len(selected), self
        )
        self.delete_progress.setWindowModality(Qt.WindowModal)
        self.delete_progress.show()

        self.delete_worker.progress.connect(self._on_delete_progress)
        self.delete_worker.finished.connect(self._on_delete_finished)
        self.delete_worker.start()

    def _on_delete_progress(self, current, total, filename):
        """Handle delete progress."""
        self.delete_progress.setValue(current)
        self.delete_progress.setLabelText(f"Deleting: {filename}")

    def _on_delete_finished(self, results):
        """Handle delete completion."""
        self.delete_progress.close()

        success = results.get('success', 0)
        errors = results.get('errors', [])
        deleted_hashes = results.get('deleted_hashes', [])

        if deleted_hashes and self.grid_model:
            self.grid_model.remove_items(deleted_hashes)

        if errors:
            QMessageBox.warning(
                self, "Delete Complete with Errors",
                f"✓ Deleted {success} files.\n\n"
                f"✗ {len(errors)} errors occurred."
            )
        else:
            self.status_bar.showMessage(f"✓ Deleted {success} files")

        if self.grid_model:
            count = len(self.grid_model.file_items)
            self.photo_count_label.setText(f"{count:,} photos")

    def rotate_selected(self):
        """Rotate selected files."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to rotate.")
            return

        prior_archive = self.database_metadata.get_prior_revision_archive_location()
        if not prior_archive:
            QMessageBox.warning(
                self, "Prior Revision Archive Not Configured",
                "Please configure Prior Revision Archive location in the main application settings."
            )
            return

        from ui.rotate_image_dialog import RotateImageDialog

        dialog = RotateImageDialog(
            parent=self,
            selected_records=selected,
            db_metadata=self.database_metadata,
            logger=logger
        )
        dialog.exec()
        self.run_current_query()

    def edit_selected(self):
        """Edit selected files (brightness, contrast, saturation, crop)."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to edit.")
            return

        # Check Prior Revision Archive is configured
        prior_archive = self.database_metadata.get_prior_revision_archive_location()
        if not prior_archive:
            QMessageBox.warning(
                self, "Prior Revision Archive Not Configured",
                "Please configure Prior Revision Archive location in the main application settings."
            )
            return

        if len(selected) == 1:
            # Single photo edit dialog
            from ui.edit_image_dialog import EditImageDialog

            dialog = EditImageDialog(
                parent=self,
                record=selected[0],
                db_metadata=self.database_metadata,
                logger_instance=logger
            )
            dialog.exec()
        else:
            # Batch edit dialog (multiple photos)
            from ui.batch_edit_dialog import BatchEditDialog

            dialog = BatchEditDialog(
                parent=self,
                records=selected,
                db_metadata=self.database_metadata,
                logger_instance=logger
            )
            dialog.exec()

        self.run_current_query()

    def correct_date_selected(self):
        """Correct dates for selected files."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(self, "No Selection", "Please select files to correct.")
            return

        from ui.date_correction_dialog import DateCorrectionDialog

        batch_mode = len(selected) > 1
        dialog = DateCorrectionDialog(self, selected, batch_mode=batch_mode)
        dialog.exec()
        self.run_current_query()

    def reorganize_marked_files(self):
        """Reorganize files that have been marked for reorganization after date correction."""
        if not self.database_metadata:
            QMessageBox.warning(
                self, "No Database",
                "Please select a database first."
            )
            return

        # Get files needing reorganization
        files_to_reorganize = self.database_metadata.get_files_needing_reorganization()

        if not files_to_reorganize:
            QMessageBox.information(
                self, "No Files to Reorganize",
                "There are no files marked for reorganization.\n\n"
                "Files are marked for reorganization when you correct their dates."
            )
            return

        # Confirm reorganization
        reply = QMessageBox.question(
            self, "Confirm Reorganization",
            f"📦 Reorganize {len(files_to_reorganize)} file(s)?\n\n"
            f"Files will be moved to folders matching their corrected dates.\n\n"
            f"This operation can be undone by correcting dates again.",
            QMessageBox.Yes | QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Use the reorganize_files function which handles progress dialog internally
        from ui.reorganize_worker import reorganize_files

        success_count, failed_count = reorganize_files(
            parent_widget=self,
            db_metadata=self.database_metadata,
            files_to_reorganize=files_to_reorganize
        )

        # Show completion message
        if failed_count > 0:
            QMessageBox.warning(
                self, "Reorganization Complete with Errors",
                f"✓ Reorganized {success_count} files.\n"
                f"✗ {failed_count} files failed.\n\n"
                f"Check the logs for details."
            )
        elif success_count > 0:
            QMessageBox.information(
                self, "Reorganization Complete",
                f"✓ Successfully reorganized {success_count} files."
            )

        # Refresh the query to show updated data
        self.run_current_query()

    # -------------------------------------------------------------------------
    # Album Actions
    # -------------------------------------------------------------------------

    def add_selected_to_album(self):
        """Add selected photos to an album."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            QMessageBox.information(
                self, "No Selection",
                "Please select photos to add to an album."
            )
            return

        if not self.current_database_path:
            QMessageBox.warning(
                self, "No Database",
                "Please select a database first."
            )
            return

        from ui.add_to_album_dialog import AddToAlbumDialog

        dialog = AddToAlbumDialog(selected, self.current_database_path, self)
        dialog.exec()

    def manage_albums(self):
        """Open album management dialog."""
        if not self.current_database_path:
            QMessageBox.warning(
                self, "No Database",
                "Please select a database first."
            )
            return

        from ui.album_management_dialog import AlbumManagementDialog

        dialog = AlbumManagementDialog(self.current_database_path, self)
        dialog.exec()

    def manage_unreliable_paths(self):
        """Open dialog to manage user-specified unreliable paths."""
        if not self.database_metadata:
            QMessageBox.warning(
                self, "No Database",
                "Please select a database first."
            )
            return

        from ui.manage_unreliable_paths_dialog import ManageUnreliablePathsDialog

        dialog = ManageUnreliablePathsDialog(self.database_metadata, self)
        dialog.exec()

    def open_selected_file(self):
        """Open selected file with default application."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            return

        file_path = selected[0].get('archive_path') or selected[0].get('source_path', '')
        if file_path and os.path.exists(file_path):
            import subprocess
            import platform

            if platform.system() == 'Darwin':
                subprocess.call(('open', file_path))
            elif platform.system() == 'Windows':
                os.startfile(file_path)
            else:
                subprocess.call(('xdg-open', file_path))

    def open_selected_folder(self):
        """Open folder containing selected file."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            return

        file_path = selected[0].get('archive_path') or selected[0].get('source_path', '')
        if file_path:
            folder = os.path.dirname(file_path)
            if os.path.exists(folder):
                import subprocess
                import platform

                if platform.system() == 'Darwin':
                    subprocess.call(('open', folder))
                elif platform.system() == 'Windows':
                    os.startfile(folder)
                else:
                    subprocess.call(('xdg-open', folder))

    def copy_selected_path(self):
        """Copy path of first selected file to clipboard."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        if not selected:
            return

        file_path = selected[0].get('archive_path') or selected[0].get('source_path', '')
        if file_path:
            clipboard = QApplication.clipboard()
            clipboard.setText(file_path)
            self.status_bar.showMessage(f"📋 Path copied: {file_path}")

    def refresh_selected_thumbnails(self):
        """Refresh thumbnails for selected files."""
        if not self.grid_view:
            return

        selected = self.grid_view.get_selected_items()
        for record in selected:
            file_hash = record.get('file_hash')
            if file_hash:
                self.grid_model.refresh_thumbnail(file_hash)

        self.status_bar.showMessage(f"🔄 Refreshed thumbnails for {len(selected)} items")

    # -------------------------------------------------------------------------
    # Selection Actions
    # -------------------------------------------------------------------------

    def select_all(self):
        """Select all items in grid."""
        if self.grid_view:
            self.grid_view.selectAll()

    def deselect_all(self):
        """Deselect all items in grid."""
        if self.grid_view:
            self.grid_view.clearSelection()

    # -------------------------------------------------------------------------
    # Help Actions
    # -------------------------------------------------------------------------

    def show_shortcuts(self):
        """Show keyboard shortcuts help."""
        shortcuts = """
<h3>⌨ Keyboard Shortcuts</h3>

<h4>🔍 Search & Navigation</h4>
<table>
<tr><td><b>Ctrl+K</b></td><td>Focus search bar</td></tr>
<tr><td><b>F5</b></td><td>Run query</td></tr>
<tr><td><b>Ctrl+Shift+C</b></td><td>Clear all filters</td></tr>
</table>

<h4>🖼 View</h4>
<table>
<tr><td><b>1</b></td><td>Small thumbnails (150px)</td></tr>
<tr><td><b>2</b></td><td>Medium thumbnails (200px)</td></tr>
<tr><td><b>3</b></td><td>Large thumbnails (300px)</td></tr>
<tr><td><b>P</b></td><td>Toggle preview panel</td></tr>
<tr><td><b>Space</b></td><td>Show selected in large preview</td></tr>
</table>

<h4>☑ Selection</h4>
<table>
<tr><td><b>Ctrl+A</b></td><td>Select all</td></tr>
<tr><td><b>Escape</b></td><td>Deselect all</td></tr>
<tr><td><b>Shift+Click</b></td><td>Select range</td></tr>
<tr><td><b>Ctrl+Click</b></td><td>Toggle selection</td></tr>
</table>

<h4>⚡ Actions</h4>
<table>
<tr><td><b>Delete</b></td><td>Delete selected to vault</td></tr>
<tr><td><b>R</b></td><td>Rotate selected</td></tr>
<tr><td><b>E</b></td><td>Edit selected (brightness, contrast, crop)</td></tr>
<tr><td><b>D</b></td><td>Correct date</td></tr>
</table>
"""
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self, "About Photo Review",
            "📸 Photo Review\n"
            "Part of PyPhotoOrganizer\n\n"
            "Fast photo review with query-based selection.\n\n"
            "Built with PySide6"
        )

    # -------------------------------------------------------------------------
    # Window Geometry
    # -------------------------------------------------------------------------

    def restore_window_geometry(self):
        """Restore window geometry from settings."""
        geometry = self.settings.value("geometry")

        # Restore dark mode preference
        self._is_dark_mode = self.settings.value("dark_mode", True, type=bool)
        self._apply_theme()
        if self._is_dark_mode:
            self.theme_action.setText("🌙 Switch to Light Mode")
        else:
            self.theme_action.setText("☀ Switch to Dark Mode")

        if geometry:
            self.restoreGeometry(geometry)
            self.ensure_window_on_screen()
        else:
            self.center_on_screen()

    def center_on_screen(self):
        """Center window on primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)
            self.move(window_geometry.topLeft())

    def ensure_window_on_screen(self):
        """Ensure window is visible on screen."""
        screen = QApplication.primaryScreen()
        if not screen:
            return

        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()

        if window_geometry.left() < screen_geometry.left():
            self.move(screen_geometry.left(), window_geometry.top())
            window_geometry = self.frameGeometry()
        elif window_geometry.right() > screen_geometry.right():
            self.move(screen_geometry.right() - window_geometry.width(), window_geometry.top())
            window_geometry = self.frameGeometry()

        if window_geometry.top() < screen_geometry.top():
            self.move(window_geometry.left(), screen_geometry.top())
        elif window_geometry.top() > screen_geometry.bottom() - 50:
            self.move(window_geometry.left(), screen_geometry.bottom() - 50)

    def closeEvent(self, event):
        """Handle window close event."""
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("dark_mode", self._is_dark_mode)

        if hasattr(self, 'main_splitter') and self.main_splitter:
            self.settings.setValue("main_splitter", self.main_splitter.saveState())
        if hasattr(self, 'right_splitter') and self.right_splitter:
            self.settings.setValue("right_splitter", self.right_splitter.saveState())
        if hasattr(self, 'preview_splitter') and self.preview_splitter:
            self.settings.setValue("preview_splitter", self.preview_splitter.saveState())
        if hasattr(self, 'preview_panel') and self.preview_panel:
            self.settings.setValue("preview_panel_visible", self.preview_panel.isVisible())

        if self.grid_model:
            self.settings.setValue("thumbnail_size", self.grid_model.thumbnail_size)

        if self.query_panel and self.database_metadata:
            state = {
                'last_query': self.query_panel.get_current_filters(),
                'last_folder': self.query_panel.get_current_folder()
            }
            self.database_metadata.set_photo_review_state(state)

        event.accept()
