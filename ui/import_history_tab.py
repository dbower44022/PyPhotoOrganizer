"""
Import History Tab for PyPhotoOrganizer GUI

Displays audit trail of import sessions with detailed file operation logs,
duplicate tracking, file preview, and export capabilities.

Optimized for handling large datasets (100,000+ records) using QTableView
with a custom model and lazy loading.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QSplitter,
    QLabel, QPushButton, QHeaderView, QFileDialog, QMessageBox,
    QComboBox, QTabWidget, QTextEdit, QAbstractItemView,
    QTableView, QLineEdit, QApplication, QFrame, QScrollArea,
    QFormLayout, QSizePolicy, QProgressDialog
)
import subprocess
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
    QTimer, QSize
)
from PySide6.QtGui import QColor, QBrush
from PIL import Image
from PIL.ExifTags import TAGS
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

# Import profiling utilities
from utils import profile_block

# Import unified preview component
from ui.preview import ImagePreviewWidget

# Import detachable preview window for large image viewing
from ui.detachable_preview_window import DetachablePreviewWindow

# Import duplicate comparison dialog
from ui.duplicate_comparison_dialog import DuplicateComparisonDialog

logger = logging.getLogger(__name__)


class FileLogTableModel(QAbstractTableModel):
    """
    High-performance table model for file operation logs.

    Uses lazy loading and caches data for efficient handling of 100k+ records.
    """

    COLUMNS = [
        ("source_folder", "Source Folder"),
        ("source_filename", "Source Filename"),
        ("dest_folder", "Dest Folder"),
        ("dest_filename", "Dest Filename"),
        ("operation", "Operation"),
        ("status", "Status"),
        ("album", "Album"),
        ("file_hash", "Hash"),
        ("details", "Details"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: List[Dict[str, Any]] = []
        self._display_cache: Dict[tuple, str] = {}

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if row < 0 or row >= len(self._data):
            return None

        log = self._data[row]
        col_key = self.COLUMNS[col][0]

        if role == Qt.DisplayRole:
            # Check cache first
            cache_key = (row, col)
            if cache_key in self._display_cache:
                return self._display_cache[cache_key]

            value = self._get_display_value(log, col_key)
            self._display_cache[cache_key] = value
            return value

        elif role == Qt.ToolTipRole:
            return self._get_tooltip(log, col_key)

        elif role == Qt.ForegroundRole:
            # Dim text for rows being processed
            if log.get('_processing'):
                return QBrush(QColor('#888888'))
            if col_key == "status":
                status = log.get('status', '')
                if status == 'success':
                    return QBrush(QColor('green'))
                elif status == 'failed':
                    return QBrush(QColor('red'))
                elif status == 'skipped':
                    return QBrush(QColor('gray'))
                elif status == 'duplicate':
                    return QBrush(QColor('orange'))
                elif status == 'content_duplicate':
                    return QBrush(QColor('#9966CC'))  # Purple for content duplicates

        elif role == Qt.BackgroundRole:
            # Highlight rows being processed
            if log.get('_processing'):
                return QBrush(QColor('#ffffcc'))  # Light yellow background

        elif role == Qt.UserRole:
            # Return raw data for sorting
            return self._get_sort_value(log, col_key)

        return None

    def _get_display_value(self, log: Dict, col_key: str) -> str:
        """Get display value for a column."""
        if col_key == "source_folder":
            source = log.get('source_path') or ''
            return os.path.dirname(source) if source else ''

        elif col_key == "source_filename":
            source = log.get('source_path') or ''
            return os.path.basename(source) if source else ''

        elif col_key == "dest_folder":
            dest = log.get('destination_path') or ''
            return os.path.dirname(dest) if dest else ''

        elif col_key == "dest_filename":
            dest = log.get('destination_path') or ''
            return os.path.basename(dest) if dest else ''

        elif col_key == "operation":
            op = log.get('operation') or ''
            return op.replace('_', ' ').title()

        elif col_key == "status":
            return (log.get('status') or '').title()

        elif col_key == "album":
            # Display sub-album name if present, otherwise album name
            sub_album = log.get('sub_album_name') or ''
            album_name = log.get('album_name') or ''
            if sub_album:
                return sub_album
            elif album_name:
                return album_name
            return ''

        elif col_key == "file_hash":
            h = log.get('file_hash') or ''
            return h[:12] + "..." if h and len(h) > 12 else h

        elif col_key == "details":
            details = log.get('error_message') or log.get('filter_reason') or ''
            return details[:50] + "..." if len(details) > 50 else details

        return ''

    def _get_tooltip(self, log: Dict, col_key: str) -> str:
        """Get tooltip for a cell."""
        if col_key == "source_folder" or col_key == "source_filename":
            return log.get('source_path') or ''
        elif col_key == "dest_folder" or col_key == "dest_filename":
            return log.get('destination_path') or ''
        elif col_key == "file_hash":
            return log.get('file_hash') or ''
        elif col_key == "album":
            # Show album path in tooltip
            album_path = log.get('album_path') or ''
            album_name = log.get('album_name') or ''
            sub_album = log.get('sub_album_name') or ''
            if album_path:
                return f"Album: {album_name}\nSub-Album: {sub_album}\nPath: {album_path}" if sub_album else f"Album: {album_name}\nPath: {album_path}"
            return ''
        elif col_key == "details":
            return log.get('error_message') or log.get('filter_reason') or ''
        return ''

    def _get_sort_value(self, log: Dict, col_key: str):
        """Get value for sorting (may differ from display)."""
        if col_key == "source_folder":
            source = log.get('source_path') or ''
            return os.path.dirname(source).lower() if source else ''
        elif col_key == "source_filename":
            source = log.get('source_path') or ''
            return os.path.basename(source).lower() if source else ''
        elif col_key == "dest_folder":
            dest = log.get('destination_path') or ''
            return os.path.dirname(dest).lower() if dest else ''
        elif col_key == "dest_filename":
            dest = log.get('destination_path') or ''
            return os.path.basename(dest).lower() if dest else ''
        elif col_key == "operation":
            return (log.get('operation') or '').lower()
        elif col_key == "status":
            return (log.get('status') or '').lower()
        elif col_key == "album":
            # Sort by sub-album name if present, otherwise album name
            sub_album = log.get('sub_album_name') or ''
            album_name = log.get('album_name') or ''
            return (sub_album or album_name).lower()
        elif col_key == "file_hash":
            return log.get('file_hash') or ''
        elif col_key == "details":
            return (log.get('error_message') or log.get('filter_reason') or '').lower()
        return ''

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self.COLUMNS):
                return self.COLUMNS[section][1]
        return None

    def setData(self, logs: List[Dict[str, Any]]):
        """Set the log data."""
        self.beginResetModel()
        self._data = logs
        self._display_cache.clear()
        self.endResetModel()

    def getLog(self, row: int) -> Optional[Dict[str, Any]]:
        """Get log entry at row."""
        if 0 <= row < len(self._data):
            return self._data[row]
        return None

    def clear(self):
        """Clear all data."""
        self.beginResetModel()
        self._data = []
        self._display_cache.clear()
        self.endResetModel()

    def removeRowsBySourcePath(self, source_paths: set) -> int:
        """
        Remove rows matching the given source paths.

        Args:
            source_paths: Set of source file paths to remove

        Returns:
            Number of rows removed
        """
        if not source_paths:
            return 0

        # Find indices to remove (in reverse order to maintain indices during removal)
        indices_to_remove = []
        for i, log in enumerate(self._data):
            if log.get('source_path') in source_paths:
                indices_to_remove.append(i)

        if not indices_to_remove:
            return 0

        # Remove in reverse order to maintain valid indices
        self.beginResetModel()
        for i in reversed(indices_to_remove):
            del self._data[i]
        self._display_cache.clear()
        self.endResetModel()

        return len(indices_to_remove)

    def markRowsAsProcessing(self, source_paths: set):
        """
        Mark rows as being processed (for visual feedback).

        Args:
            source_paths: Set of source file paths being processed
        """
        for i, log in enumerate(self._data):
            if log.get('source_path') in source_paths:
                log['_processing'] = True
                # Emit dataChanged for the row
                top_left = self.index(i, 0)
                bottom_right = self.index(i, self.columnCount() - 1)
                self.dataChanged.emit(top_left, bottom_right)

    def clearProcessingFlags(self):
        """Clear all processing flags."""
        for log in self._data:
            if '_processing' in log:
                del log['_processing']


class FileLogFilterProxyModel(QSortFilterProxyModel):
    """
    Proxy model for filtering and sorting file logs.

    Supports text search across all columns and operation/status filters.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._search_text = ""
        self._operation_filter = ""
        self._status_filter = ""
        self.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self.setSortRole(Qt.UserRole)

    def setSearchText(self, text: str):
        """Set search text filter."""
        self._search_text = text.lower()
        self.invalidateFilter()

    def setOperationFilter(self, operation: str):
        """Set operation filter (empty string = all)."""
        self._operation_filter = operation.lower()
        self.invalidateFilter()

    def setStatusFilter(self, status: str):
        """Set status filter (empty string = all)."""
        self._status_filter = status.lower()
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Determine if row should be visible."""
        model = self.sourceModel()
        if not isinstance(model, FileLogTableModel):
            return True

        log = model.getLog(source_row)
        if not log:
            return False

        # Operation filter
        if self._operation_filter:
            op = (log.get('operation') or '').lower()
            if self._operation_filter not in op:
                return False

        # Status filter
        if self._status_filter:
            status = (log.get('status') or '').lower()
            if self._status_filter != status:
                return False

        # Search text filter (search across all fields)
        if self._search_text:
            # Handle None values by converting to empty string
            searchable = ' '.join([
                log.get('source_path') or '',
                log.get('destination_path') or '',
                log.get('operation') or '',
                log.get('status') or '',
                log.get('file_hash') or '',
                log.get('error_message') or '',
                log.get('filter_reason') or '',
                log.get('album_name') or '',
                log.get('sub_album_name') or '',
            ]).lower()
            if self._search_text not in searchable:
                return False

        return True


class FileLogTableView(QTableView):
    """
    Optimized table view for file logs with sorting, column resizing,
    and automatic column width adjustment on resize.
    """

    # Minimum column widths to prevent columns from becoming too narrow
    MIN_WIDTHS = [100, 80, 100, 80, 70, 60, 80, 80, 80]
    # Column weight ratios for proportional resizing
    COLUMN_WEIGHTS = [2.5, 1.5, 2.5, 1.5, 1.0, 0.8, 1.2, 1.0, 1.5]

    def __init__(self, parent=None):
        super().__init__(parent)

        # Configure view for performance
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSortingEnabled(True)
        self.setWordWrap(False)

        # Optimize for large datasets
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(24)  # Compact rows

        # Configure header
        header = self.horizontalHeader()
        header.setStretchLastSection(True)  # Last column fills remaining space
        header.setSectionsMovable(True)
        header.setSortIndicatorShown(True)
        header.setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # Allow column resizing
        header.setSectionResizeMode(QHeaderView.Interactive)

        # Track if user has manually resized columns
        self._user_resized = False
        self._auto_resizing = False
        header.sectionResized.connect(self._on_section_resized)

        # Timer for delayed resize
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._do_resize_columns)

    def _on_section_resized(self, index, old_size, new_size):
        """Track when user manually resizes columns."""
        # Only set flag if this wasn't triggered by our auto-resize
        if self._auto_resizing:
            return
        self._user_resized = True

    def setModel(self, model):
        """Set model and configure column widths."""
        super().setModel(model)
        self._user_resized = False
        # Delay initial resize to ensure viewport is ready
        QTimer.singleShot(0, self._do_resize_columns)

    def showEvent(self, event):
        """Handle show event - resize columns when first shown."""
        super().showEvent(event)
        if not self._user_resized:
            QTimer.singleShot(0, self._do_resize_columns)

    def resizeEvent(self, event):
        """Handle resize events - adjust column widths proportionally."""
        super().resizeEvent(event)
        if not self._user_resized:
            # Use timer to batch resize events
            self._resize_timer.start(50)

    def _do_resize_columns(self):
        """Actually perform the column resize."""
        if not self.model() or self.model().columnCount() < 9:
            return

        self._auto_resizing = True

        header = self.horizontalHeader()
        # Get viewport width, accounting for scrollbar if visible
        available_width = self.viewport().width()

        if available_width <= 0:
            self._auto_resizing = False
            return

        # Calculate total weight (excluding last column which stretches)
        weights = self.COLUMN_WEIGHTS[:-1]  # All but last
        total_weight = sum(weights)

        # Reserve some space for the last column
        last_col_min = self.MIN_WIDTHS[-1]
        distributable_width = available_width - last_col_min

        # Calculate widths based on weights
        widths = []
        for i, weight in enumerate(weights):
            width = int((weight / total_weight) * distributable_width)
            # Enforce minimum width
            width = max(width, self.MIN_WIDTHS[i])
            widths.append(width)

        # Apply widths to all columns except last (which stretches)
        for i, width in enumerate(widths):
            header.resizeSection(i, width)

        self._auto_resizing = False

    def reset_column_widths(self):
        """Reset to automatic column sizing."""
        self._user_resized = False
        self._do_resize_columns()


class FileDetailsWidget(QScrollArea):
    """
    Widget for displaying file details including EXIF metadata.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setMinimumWidth(250)

        # Create content widget
        self._content = QWidget()
        self._layout = QFormLayout(self._content)
        self._layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self._layout.setLabelAlignment(Qt.AlignRight)
        self.setWidget(self._content)

        # Style
        self._content.setStyleSheet("""
            QLabel {
                padding: 2px;
            }
            QLabel[heading="true"] {
                font-weight: bold;
                color: #0066cc;
                padding-top: 8px;
            }
        """)

        self._clear_details()

    def _clear_details(self):
        """Clear all detail fields."""
        # Clear existing widgets
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        placeholder = QLabel("Select a file to view details")
        placeholder.setStyleSheet("color: #888888; padding: 20px;")
        placeholder.setAlignment(Qt.AlignCenter)
        self._layout.addRow(placeholder)

    def _add_heading(self, text: str):
        """Add a section heading."""
        label = QLabel(text)
        label.setProperty("heading", True)
        self._layout.addRow(label)

    def _add_field(self, label: str, value: str):
        """Add a label-value field."""
        value_label = QLabel(value)
        value_label.setWordWrap(True)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._layout.addRow(f"{label}:", value_label)

    def setFileDetails(self, log: Dict[str, Any], file_path: str = None):
        """Display details for a file log entry."""
        # Clear existing
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not log:
            self._clear_details()
            return

        # Determine which file path to use for reading details
        actual_path = file_path
        if not actual_path or not os.path.exists(actual_path):
            # Try destination path first (file in archive)
            actual_path = log.get('destination_path', '')
        if not actual_path or not os.path.exists(actual_path):
            # Fall back to source path
            actual_path = log.get('source_path', '')

        # Operation details
        self._add_heading("Operation Details")
        self._add_field("Operation", log.get('operation', 'N/A').replace('_', ' ').title())
        self._add_field("Status", log.get('status', 'N/A').title())

        if log.get('error_message'):
            self._add_field("Error", log.get('error_message'))
        if log.get('filter_reason'):
            self._add_field("Filter Reason", log.get('filter_reason'))

        # File paths
        self._add_heading("File Paths")
        source = log.get('source_path', '')
        if source:
            self._add_field("Source", source)
        dest = log.get('destination_path', '')
        if dest:
            self._add_field("Destination", dest)

        # Hash
        if log.get('file_hash'):
            self._add_field("SHA-256", log.get('file_hash'))

        # Album details (if file was added to album)
        album_name = log.get('album_name')
        if album_name:
            self._add_heading("Album Details")
            self._add_field("Album", album_name)
            sub_album_name = log.get('sub_album_name')
            if sub_album_name:
                self._add_field("Sub-Album", sub_album_name)
            album_path = log.get('album_path')
            if album_path:
                self._add_field("Album Path", album_path)

        # File information (if file exists)
        if actual_path and os.path.exists(actual_path):
            self._add_heading("File Information")

            # File size
            try:
                size = os.path.getsize(actual_path)
                self._add_field("Size", self._format_size(size))
            except Exception as e:
                logger.warning(f"Could not get file size: {e}")

            # File dates
            try:
                stat = os.stat(actual_path)
                mtime = datetime.fromtimestamp(stat.st_mtime)
                self._add_field("Modified", mtime.strftime("%Y-%m-%d %H:%M:%S"))
            except Exception as e:
                logger.warning(f"Could not get file dates: {e}")

            # EXIF data for images
            self._load_exif_data(actual_path)

    def _load_exif_data(self, file_path: str):
        """Load and display EXIF data for an image."""
        image_extensions = {'.jpg', '.jpeg', '.png', '.tiff', '.tif'}
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in image_extensions:
            return

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS

            with Image.open(file_path) as img:
                # Image dimensions
                self._add_heading("Image Properties")
                self._add_field("Dimensions", f"{img.width} × {img.height}")
                self._add_field("Format", img.format or "Unknown")
                if img.mode:
                    self._add_field("Color Mode", img.mode)

                # EXIF data
                exif_data = img.getexif()
                if exif_data:
                    self._add_heading("EXIF Data")

                    # Map EXIF tag numbers to names
                    exif_dict = {}
                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, str(tag_id))
                        exif_dict[tag_name] = value

                    # Display key EXIF fields
                    exif_fields = [
                        ('DateTimeOriginal', 'Date Taken'),
                        ('DateTime', 'Date Modified'),
                        ('Make', 'Camera Make'),
                        ('Model', 'Camera Model'),
                        ('ExposureTime', 'Exposure'),
                        ('FNumber', 'Aperture'),
                        ('ISOSpeedRatings', 'ISO'),
                        ('FocalLength', 'Focal Length'),
                        ('Flash', 'Flash'),
                        ('Software', 'Software'),
                        ('Artist', 'Artist'),
                        ('Copyright', 'Copyright'),
                        ('GPSInfo', 'GPS Data'),
                    ]

                    for exif_key, display_name in exif_fields:
                        if exif_key in exif_dict:
                            value = exif_dict[exif_key]
                            # Format special values
                            if exif_key == 'ExposureTime' and isinstance(value, tuple):
                                value = f"{value[0]}/{value[1]}s"
                            elif exif_key == 'FNumber' and isinstance(value, tuple):
                                value = f"f/{value[0]/value[1]:.1f}"
                            elif exif_key == 'FocalLength' and isinstance(value, tuple):
                                value = f"{value[0]/value[1]:.0f}mm"
                            elif exif_key == 'GPSInfo':
                                value = "Present"
                            elif isinstance(value, bytes):
                                try:
                                    value = value.decode('utf-8', errors='ignore')
                                except Exception:
                                    value = str(value)[:50]

                            self._add_field(display_name, str(value))
                else:
                    self._add_heading("EXIF Data")
                    no_exif = QLabel("No EXIF data available")
                    no_exif.setStyleSheet("color: #888888; font-style: italic;")
                    self._layout.addRow(no_exif)

        except ImportError:
            logger.warning("PIL not available for EXIF extraction")
        except Exception as e:
            logger.warning(f"Could not read EXIF data from {file_path}: {e}")

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def clear(self):
        """Clear the details."""
        self._clear_details()


class ImportHistoryTab(QWidget):
    """Tab for displaying import session history and audit logs."""

    def __init__(self):
        super().__init__()
        self.audit_manager = None
        self.database_path = None
        self.db_metadata = None  # DatabaseMetadata instance for DetachablePreviewWindow
        self.current_session_id = None
        self._sessions_cache = []

        # Detachable preview window (created on demand)
        self._detached_preview_window = None

        # Duplicate comparison dialog (created on demand)
        self._comparison_dialog = None

        # Model and proxy for file logs
        self._model = FileLogTableModel(self)
        self._proxy = FileLogFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        # Search debounce timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)

        # Track recently overridden files (for filter and undo)
        self._recently_overridden_logs = []
        self._last_override_skip_results = None  # For undo capability

        # Track state for preserving selection after operations
        self._preserved_session_id = None
        self._preserved_scroll_position = 0
        self._preserved_selection_paths = set()

        # Worker thread references (for cleanup on close)
        self.reprocess_worker = None
        self.override_skip_worker = None

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(4)

        # === Top Section: Session Selection and Details (compact) ===
        # Row 1: Session selector, status filter, and session info
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        row1.addWidget(QLabel("Session:"))
        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(280)
        self.session_combo.setMaximumWidth(400)
        self.session_combo.setToolTip("Select a session to view details, or 'All Sessions' to view aggregate data")
        self.session_combo.currentIndexChanged.connect(self.on_session_selected)
        row1.addWidget(self.session_combo)

        row1.addWidget(QLabel("Status:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Completed", "Running", "Failed", "Cancelled"])
        self.status_filter.currentIndexChanged.connect(self.refresh_sessions)
        row1.addWidget(self.status_filter)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_sessions)
        row1.addWidget(refresh_btn)

        row1.addSpacing(30)

        # Session info inline (selected session details)
        row1.addWidget(QLabel("Result:"))
        self._detail_status = QLabel("--")
        self._detail_status.setMinimumWidth(70)
        row1.addWidget(self._detail_status)

        row1.addWidget(QLabel("Started:"))
        self._detail_started = QLabel("--")
        row1.addWidget(self._detail_started)

        row1.addWidget(QLabel("Duration:"))
        self._detail_duration = QLabel("--")
        row1.addWidget(self._detail_duration)

        row1.addStretch()
        main_layout.addLayout(row1)

        # Row 2: Statistics (compact inline)
        row2 = QHBoxLayout()
        row2.setSpacing(8)

        row2.addWidget(QLabel("Scanned:"))
        self._detail_scanned = QLabel("--")
        self._detail_scanned.setMinimumWidth(50)
        row2.addWidget(self._detail_scanned)

        row2.addWidget(QLabel("Processed:"))
        self._detail_processed = QLabel("--")
        self._detail_processed.setMinimumWidth(50)
        row2.addWidget(self._detail_processed)

        row2.addWidget(QLabel("New:"))
        self._detail_unique = QLabel("--")
        self._detail_unique.setMinimumWidth(50)
        row2.addWidget(self._detail_unique)

        row2.addWidget(QLabel("Duplicates:"))
        self._detail_duplicates = QLabel("--")
        self._detail_duplicates.setMinimumWidth(50)
        row2.addWidget(self._detail_duplicates)

        row2.addWidget(QLabel("Filtered:"))
        self._detail_filtered = QLabel("--")
        self._detail_filtered.setMinimumWidth(50)
        row2.addWidget(self._detail_filtered)

        row2.addWidget(QLabel("Errors:"))
        self._detail_errors = QLabel("--")
        self._detail_errors.setMinimumWidth(50)
        row2.addWidget(self._detail_errors)

        row2.addStretch()
        main_layout.addLayout(row2)

        # === Main Content Splitter (Grid above, Preview below) ===
        main_splitter = QSplitter(Qt.Vertical)

        # === Middle Section: File Grid with Filters ===
        grid_group = QGroupBox("File Operations")
        grid_layout = QVBoxLayout(grid_group)
        grid_layout.setContentsMargins(8, 8, 8, 8)

        # Filter/search bar
        filter_layout = QHBoxLayout()

        # Single "Show" dropdown for filtering by outcome
        filter_layout.addWidget(QLabel("Show:"))
        self._show_combo = QComboBox()
        self._show_combo.addItems([
            "All Files",
            "New Files (Added to Archive)",
            "Duplicates",
            "Content Duplicates",
            "Filtered (Icons/Thumbnails)",
            "Recently Overridden",
            "External Modifications",
            "Errors"
        ])
        self._show_combo.currentTextChanged.connect(self._on_show_filter_changed)
        filter_layout.addWidget(self._show_combo)

        filter_layout.addSpacing(20)

        # Search box
        filter_layout.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Type to search filenames...")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self._search_edit, 2)

        # Record count label
        self._count_label = QLabel("0 records")
        filter_layout.addWidget(self._count_label)

        # Select All Visible button
        self._select_all_btn = QPushButton("Select All Visible")
        self._select_all_btn.setToolTip("Select all visible rows in the current view")
        self._select_all_btn.clicked.connect(self._select_all_visible)
        filter_layout.addWidget(self._select_all_btn)

        grid_layout.addLayout(filter_layout)

        # Table view
        self._view = FileLogTableView(self)
        self._view.setModel(self._proxy)
        self._view.selectionModel().selectionChanged.connect(self._on_file_selected)
        self._view.doubleClicked.connect(self._on_file_double_clicked)  # Open detached preview
        grid_layout.addWidget(self._view)

        # Connect proxy model changes to update count
        self._proxy.rowsInserted.connect(self._update_count)
        self._proxy.rowsRemoved.connect(self._update_count)
        self._proxy.modelReset.connect(self._update_count)
        self._proxy.layoutChanged.connect(self._update_count)

        main_splitter.addWidget(grid_group)

        # === Bottom Section: Preview and File Details ===
        # Store reference to preview splitter for visibility toggling
        self._preview_splitter = QSplitter(Qt.Horizontal)

        # Image preview
        preview_group = QGroupBox("Image Preview (drag to zoom, double-click to reset)")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        self._image_preview = ImagePreviewWidget(dark_mode=True)
        preview_layout.addWidget(self._image_preview)
        self._preview_splitter.addWidget(preview_group)

        # File details
        details_file_group = QGroupBox("File Details")
        details_file_layout = QVBoxLayout(details_file_group)
        details_file_layout.setContentsMargins(4, 4, 4, 4)
        self._file_details = FileDetailsWidget()
        details_file_layout.addWidget(self._file_details)
        self._preview_splitter.addWidget(details_file_group)

        # Set horizontal splitter proportions (60% preview, 40% details)
        self._preview_splitter.setSizes([400, 300])

        main_splitter.addWidget(self._preview_splitter)

        # Set vertical splitter proportions (60% grid, 40% preview)
        main_splitter.setSizes([400, 250])

        # Hide inline preview by default - use detached preview instead (double-click)
        self._preview_splitter.setVisible(False)

        main_layout.addWidget(main_splitter, 1)

        # === Export Buttons ===
        export_layout = QHBoxLayout()

        # Toggle inline preview button
        self._toggle_preview_btn = QPushButton("Show Preview Panel")
        self._toggle_preview_btn.setCheckable(True)
        self._toggle_preview_btn.setChecked(False)  # Hidden by default
        self._toggle_preview_btn.clicked.connect(self._toggle_inline_preview)
        self._toggle_preview_btn.setToolTip("Toggle inline preview panel (or double-click a file for detached preview)")
        export_layout.addWidget(self._toggle_preview_btn)

        export_layout.addSpacing(10)

        self.export_json_btn = QPushButton("Export to JSON...")
        self.export_json_btn.clicked.connect(self.export_to_json)
        self.export_json_btn.setEnabled(False)
        export_layout.addWidget(self.export_json_btn)

        self.export_csv_btn = QPushButton("Export to CSV...")
        self.export_csv_btn.clicked.connect(self.export_to_csv)
        self.export_csv_btn.setEnabled(False)
        export_layout.addWidget(self.export_csv_btn)

        self.export_duplicates_btn = QPushButton("Export Duplicates...")
        self.export_duplicates_btn.clicked.connect(self.export_duplicates)
        self.export_duplicates_btn.setEnabled(False)
        export_layout.addWidget(self.export_duplicates_btn)

        export_layout.addStretch()

        # File action buttons
        self.open_file_btn = QPushButton("Open Source File")
        self.open_file_btn.clicked.connect(self.open_selected_file)
        self.open_file_btn.setEnabled(False)
        self.open_file_btn.setToolTip("Open source file with default application")
        export_layout.addWidget(self.open_file_btn)

        self.open_folder_btn = QPushButton("Open Source Folder")
        self.open_folder_btn.clicked.connect(self.open_file_folder)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.setToolTip("Open folder containing the source file")
        export_layout.addWidget(self.open_folder_btn)

        self.copy_path_btn = QPushButton("Copy Source Path")
        self.copy_path_btn.clicked.connect(self.copy_file_path)
        self.copy_path_btn.setEnabled(False)
        self.copy_path_btn.setToolTip("Copy source file path to clipboard")
        export_layout.addWidget(self.copy_path_btn)

        export_layout.addSpacing(20)

        # Process File(s) button
        self.reprocess_btn = QPushButton("Process File(s)")
        self.reprocess_btn.clicked.connect(self.reprocess_files)
        self.reprocess_btn.setEnabled(False)
        self.reprocess_btn.setToolTip("Reprocess selected file(s) with current settings")
        export_layout.addWidget(self.reprocess_btn)

        # Override Skip button (for filtered files)
        self.override_skip_btn = QPushButton("Override Skip")
        self.override_skip_btn.clicked.connect(self.override_skip_files)
        self.override_skip_btn.setToolTip(
            "Import selected filtered files, bypassing size/dimension filters"
        )
        export_layout.addWidget(self.override_skip_btn)

        # Compare Duplicates button
        self.compare_duplicates_btn = QPushButton("Compare Duplicates")
        self.compare_duplicates_btn.clicked.connect(self._compare_selected_duplicate)
        self.compare_duplicates_btn.setToolTip(
            "Open side-by-side comparison of selected duplicate with archive file"
        )
        export_layout.addWidget(self.compare_duplicates_btn)

        # Undo Override Skip button
        self.undo_override_btn = QPushButton("Undo Override")
        self.undo_override_btn.clicked.connect(self.undo_last_override_skip)
        self.undo_override_btn.setToolTip(
            "Undo the last override skip operation (delete imported files)"
        )
        export_layout.addWidget(self.undo_override_btn)

        # Delete session button
        self.delete_btn = QPushButton("Delete Session")
        self.delete_btn.clicked.connect(self.delete_session)
        self.delete_btn.setEnabled(False)
        export_layout.addWidget(self.delete_btn)

        main_layout.addLayout(export_layout)

    def set_database(self, database_path):
        """Set the database path and initialize audit manager."""
        self.database_path = database_path
        if database_path:
            try:
                from audit_manager import AuditManager
                from database_metadata import DatabaseMetadata
                self.audit_manager = AuditManager(database_path)
                self.db_metadata = DatabaseMetadata(database_path)
                self.refresh_sessions()
            except Exception as e:
                logger.error(f"Failed to initialize audit manager: {e}", exc_info=True)
                self.audit_manager = None
                self.db_metadata = None
                self.session_combo.clear()
                self._clear_session_display()

    def showEvent(self, event):
        """Handle tab becoming visible - refresh data."""
        super().showEvent(event)
        if self.audit_manager:
            self.refresh_sessions()

    def refresh_sessions(self):
        """Refresh the session list from database."""
        if not self.audit_manager:
            return

        # Get filter value
        status_filter = self.status_filter.currentText()
        if status_filter == "All":
            status_filter = None
        else:
            status_filter = status_filter.lower()

        try:
            with profile_block("Database query - get_recent_sessions", logger):
                sessions = self.audit_manager.get_recent_sessions(
                    limit=100,
                    status_filter=status_filter
                )

            self._sessions_cache = sessions

            # Block signals during update
            self.session_combo.blockSignals(True)
            self.session_combo.clear()

            # Add "All Sessions" option as first item
            self.session_combo.addItem("All Sessions", "__ALL__")

            if not sessions:
                self.session_combo.blockSignals(False)
                # Still allow "All Sessions" to be selected
                self.session_combo.setCurrentIndex(0)
                self.on_session_selected(0)
                return

            for session in sessions:
                session_id = session.get('session_id', '')
                start_ts = session.get('start_timestamp', '')
                status = session.get('status', 'unknown')
                total_files = session.get('total_files_processed', 0)

                # Format display text
                try:
                    dt = datetime.fromisoformat(start_ts)
                    date_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    date_str = start_ts[:16] if start_ts else "Unknown"

                display_text = f"{date_str} - {status.title()} - {total_files:,} files"
                self.session_combo.addItem(display_text, session_id)

            self.session_combo.blockSignals(False)

            # Select most recent session (index 1, since index 0 is "All Sessions")
            # This is faster to load and more likely what the user wants to see
            if sessions:
                self.session_combo.setCurrentIndex(1)
                self.on_session_selected(1)

        except Exception as e:
            logger.error(f"Failed to refresh sessions: {e}", exc_info=True)
            QMessageBox.warning(self, "Error", f"Failed to load sessions: {e}")

    def on_session_selected(self, index):
        """Handle session selection."""
        if index < 0:
            self._clear_session_display()
            return

        session_id = self.session_combo.itemData(index)
        if not session_id:
            self._clear_session_display()
            return

        self.current_session_id = session_id

        # Check if "All Sessions" is selected
        if session_id == "__ALL__":
            self._load_all_sessions_view()
        else:
            self._load_session_details()
            self._load_file_logs()

        self._set_export_buttons_enabled(session_id != "__ALL__")

        # Clear preview
        self._image_preview.clear()
        self._file_details.clear()

    def _clear_session_display(self):
        """Clear session display elements."""
        self.current_session_id = None
        self._clear_detail_labels()
        self._model.clear()
        self._update_count()
        self._image_preview.clear()
        self._file_details.clear()
        self._set_export_buttons_enabled(False)

    def _clear_detail_labels(self):
        """Clear all session detail labels."""
        self._detail_started.setText("--")
        self._detail_status.setText("--")
        self._detail_status.setStyleSheet("")
        self._detail_duration.setText("--")
        self._detail_scanned.setText("--")
        self._detail_processed.setText("--")
        self._detail_unique.setText("--")
        self._detail_duplicates.setText("--")
        self._detail_filtered.setText("--")
        self._detail_errors.setText("--")
        self._detail_errors.setStyleSheet("")

    def _load_all_sessions_view(self):
        """Load aggregate view of all sessions."""
        if not self.audit_manager:
            return

        try:
            # Get aggregate statistics
            stats = self.audit_manager.get_aggregate_statistics()

            if not stats:
                self._clear_detail_labels()
                return

            # Display aggregate information
            total_sessions = stats.get('total_sessions', 0)
            first_date = stats.get('first_session_date', '')
            last_date = stats.get('last_session_date', '')

            # Format date range
            if first_date and last_date:
                try:
                    first_dt = datetime.fromisoformat(first_date)
                    last_dt = datetime.fromisoformat(last_date)
                    date_range = f"{first_dt.strftime('%Y-%m-%d')} to {last_dt.strftime('%Y-%m-%d')}"
                    self._detail_started.setText(date_range)
                except Exception:
                    self._detail_started.setText("Multiple sessions")
            else:
                self._detail_started.setText("No sessions")

            # Status shows session count
            self._detail_status.setText(f"{total_sessions} sessions")
            self._detail_status.setStyleSheet("color: blue; font-weight: bold;")

            # Duration not applicable
            self._detail_duration.setText("--")

            # Display aggregate statistics
            self._detail_scanned.setText(f"{stats.get('total_files_scanned', 0):,}")
            self._detail_processed.setText(f"{stats.get('total_files_processed', 0):,}")
            self._detail_unique.setText(f"{stats.get('total_unique_files', 0):,}")
            self._detail_duplicates.setText(f"{stats.get('total_duplicates', 0):,}")
            self._detail_filtered.setText(f"{stats.get('total_filtered', 0):,}")

            # Errors with color if > 0
            errors = stats.get('total_errors', 0)
            self._detail_errors.setText(f"{errors:,}")
            if errors > 0:
                self._detail_errors.setStyleSheet("color: red; font-weight: bold;")
            else:
                self._detail_errors.setStyleSheet("")

            # Load all file logs
            self._load_all_file_logs()

        except Exception as e:
            logger.error(f"Failed to load all sessions view: {e}", exc_info=True)
            self._clear_detail_labels()

    def _load_session_details(self):
        """Load and display session details."""
        if not self.audit_manager or not self.current_session_id:
            return

        try:
            session = self.audit_manager.get_session(self.current_session_id)
            if not session:
                self._clear_detail_labels()
                return

            # Started timestamp
            start_ts = session.get('start_timestamp', '')
            if start_ts:
                try:
                    start_dt = datetime.fromisoformat(start_ts)
                    self._detail_started.setText(start_dt.strftime("%Y-%m-%d %H:%M:%S"))
                except Exception:
                    self._detail_started.setText(start_ts)
            else:
                self._detail_started.setText("--")

            # Status with color
            status = session.get('status', 'unknown')
            self._detail_status.setText(status.title())
            if status == 'completed':
                self._detail_status.setStyleSheet("color: green; font-weight: bold;")
            elif status == 'failed':
                self._detail_status.setStyleSheet("color: red; font-weight: bold;")
            elif status == 'running':
                self._detail_status.setStyleSheet("color: blue; font-weight: bold;")
            elif status == 'cancelled':
                self._detail_status.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self._detail_status.setStyleSheet("")

            # Duration
            end_ts = session.get('end_timestamp', '')
            if start_ts and end_ts:
                try:
                    start_dt = datetime.fromisoformat(start_ts)
                    end_dt = datetime.fromisoformat(end_ts)
                    duration = end_dt - start_dt
                    # Format duration nicely
                    total_seconds = int(duration.total_seconds())
                    hours, remainder = divmod(total_seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    if hours > 0:
                        self._detail_duration.setText(f"{hours}h {minutes}m {seconds}s")
                    elif minutes > 0:
                        self._detail_duration.setText(f"{minutes}m {seconds}s")
                    else:
                        self._detail_duration.setText(f"{seconds}s")
                except Exception:
                    self._detail_duration.setText("--")
            elif status == 'running':
                self._detail_duration.setText("In progress...")
            else:
                self._detail_duration.setText("--")

            # Statistics
            self._detail_scanned.setText(f"{session.get('total_files_scanned', 0):,}")
            self._detail_processed.setText(f"{session.get('total_files_processed', 0):,}")
            self._detail_unique.setText(f"{session.get('total_unique_files', 0):,}")
            self._detail_duplicates.setText(f"{session.get('total_duplicates', 0):,}")
            self._detail_filtered.setText(f"{session.get('total_filtered', 0):,}")

            # Errors with color if > 0
            errors = session.get('total_errors', 0)
            self._detail_errors.setText(f"{errors:,}")
            if errors > 0:
                self._detail_errors.setStyleSheet("color: red; font-weight: bold;")
            else:
                self._detail_errors.setStyleSheet("")

        except Exception as e:
            logger.error(f"Failed to load session details: {e}", exc_info=True)
            self._clear_detail_labels()

    def _load_all_file_logs(self):
        """Load file operation logs from all sessions."""
        if not self.audit_manager:
            self._model.clear()
            return

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)

            # Get all file logs (limit to 1,000 most recent for performance)
            with profile_block("Database query - get_all_file_logs", logger):
                all_logs = self.audit_manager.get_all_file_logs(limit=1000)

            logger.info(f"📊 Loaded {len(all_logs)} records from database")

            # Store full data and pre-compute filtered views in single pass
            with profile_block("Pre-compute filtered views (optimized single-pass)", logger):
                self._all_logs = all_logs
                self._new_files_logs = []
                self._duplicate_logs = []
                self._content_duplicate_logs = []
                self._filtered_logs = []
                self._external_modification_logs = []
                self._error_logs = []

                # Single-pass filtering (much faster than 4 separate list comprehensions)
                for log in all_logs:
                    op = log.get('operation') or ''
                    status = log.get('status') or ''

                    # Categorize by operation
                    if op in ('copy', 'move', 'reprocess'):
                        self._new_files_logs.append(log)
                    elif op == 'duplicate detected':
                        self._duplicate_logs.append(log)
                    elif op == 'content_duplicate_detected':
                        self._content_duplicate_logs.append(log)
                    elif op == 'skip_filtered':
                        self._filtered_logs.append(log)
                    elif op == 'external_modification_detected':
                        self._external_modification_logs.append(log)

                    # Check for errors (can overlap with other categories)
                    if status == 'failed':
                        self._error_logs.append(log)

            logger.info(f"📊 Filtered views - New: {len(self._new_files_logs)}, Duplicates: {len(self._duplicate_logs)}, Content Duplicates: {len(self._content_duplicate_logs)}, Filtered: {len(self._filtered_logs)}, External Mods: {len(self._external_modification_logs)}, Errors: {len(self._error_logs)}")

            # Enrich duplicate logs with archive file paths
            with profile_block("Enrich duplicate logs with archive paths", logger):
                self._enrich_duplicate_logs()

            # Apply current show filter
            with profile_block("Apply show filter and populate model", logger):
                self._apply_show_filter()

        except Exception as e:
            logger.error(f"Failed to load all file logs: {e}", exc_info=True)
            self._model.clear()
            QMessageBox.warning(self, "Error", f"Failed to load file logs: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _load_file_logs(self):
        """Load file operation logs for current session."""
        if not self.audit_manager or not self.current_session_id:
            self._model.clear()
            return

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)

            # Get all file logs for this session
            with profile_block(f"Database query - get_file_logs_for_session({self.current_session_id})", logger):
                all_logs = self.audit_manager.get_file_logs_for_session(self.current_session_id)

            logger.info(f"📊 Loaded {len(all_logs)} records for session {self.current_session_id}")

            # Store full data and pre-compute filtered views in single pass
            with profile_block("Pre-compute filtered views (optimized single-pass)", logger):
                self._all_logs = all_logs
                self._new_files_logs = []
                self._duplicate_logs = []
                self._content_duplicate_logs = []
                self._filtered_logs = []
                self._external_modification_logs = []
                self._error_logs = []

                # Single-pass filtering (much faster than 4 separate list comprehensions)
                for log in all_logs:
                    op = log.get('operation') or ''
                    status = log.get('status') or ''

                    # Categorize by operation
                    if op in ('copy', 'move', 'reprocess'):
                        self._new_files_logs.append(log)
                    elif op == 'duplicate detected':
                        self._duplicate_logs.append(log)
                    elif op == 'content_duplicate_detected':
                        self._content_duplicate_logs.append(log)
                    elif op == 'skip_filtered':
                        self._filtered_logs.append(log)
                    elif op == 'external_modification_detected':
                        self._external_modification_logs.append(log)

                    # Check for errors (can overlap with other categories)
                    if status == 'failed':
                        self._error_logs.append(log)

            logger.info(f"📊 Filtered views - New: {len(self._new_files_logs)}, Duplicates: {len(self._duplicate_logs)}, Content Duplicates: {len(self._content_duplicate_logs)}, Filtered: {len(self._filtered_logs)}, External Mods: {len(self._external_modification_logs)}, Errors: {len(self._error_logs)}")

            # Enrich duplicate logs with archive file paths
            with profile_block("Enrich duplicate logs with archive paths", logger):
                self._enrich_duplicate_logs()

            # Apply current show filter
            with profile_block("Apply show filter and populate model", logger):
                self._apply_show_filter()

        except Exception as e:
            logger.error(f"Failed to load file logs: {e}", exc_info=True)
            self._model.clear()
            QMessageBox.warning(self, "Error", f"Failed to load file logs: {e}")
        finally:
            QApplication.restoreOverrideCursor()

    def _on_show_filter_changed(self, text: str):
        """Handle show filter dropdown change."""
        self._apply_show_filter()

    def _apply_show_filter(self):
        """Apply the show filter to display appropriate records."""
        if not hasattr(self, '_all_logs'):
            return

        show = self._show_combo.currentText()
        if show == "New Files (Added to Archive)":
            self._model.setData(self._new_files_logs)
        elif show == "Duplicates":
            self._model.setData(self._duplicate_logs)
        elif show == "Content Duplicates":
            self._model.setData(getattr(self, '_content_duplicate_logs', []))
        elif show == "Filtered (Icons/Thumbnails)":
            self._model.setData(self._filtered_logs)
        elif show == "Recently Overridden":
            self._model.setData(getattr(self, '_recently_overridden_logs', []))
        elif show == "External Modifications":
            self._model.setData(getattr(self, '_external_modification_logs', []))
        elif show == "Errors":
            self._model.setData(self._error_logs)
        else:  # "All Files"
            self._model.setData(self._all_logs)

        self._update_count()

    def _select_all_visible(self):
        """Select all visible rows in the current view."""
        row_count = self._proxy.rowCount()
        if row_count == 0:
            QMessageBox.information(self, "No Records",
                "No records to select in the current view.")
            return

        # Select all visible rows
        self._view.selectAll()
        logger.info(f"Selected all {row_count} visible rows")

    def _on_search_changed(self, text: str):
        """Handle search text change with debounce."""
        self._search_timer.stop()
        self._search_timer.start(300)

    def _apply_search(self):
        """Apply the search filter."""
        text = self._search_edit.text()
        self._proxy.setSearchText(text)
        self._update_count()

    def _update_count(self):
        """Update the record count label."""
        visible = self._proxy.rowCount()
        total = self._model.rowCount()
        if visible == total:
            self._count_label.setText(f"{total:,} records")
        else:
            self._count_label.setText(f"{visible:,} of {total:,} records")

    def _on_file_selected(self):
        """Handle file selection in grid."""
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            self._image_preview.clear()
            self._file_details.clear()
            self.reprocess_btn.setEnabled(False)
            self.open_file_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.copy_path_btn.setEnabled(False)
            return

        # Enable reprocess button when files are selected (but not for "All Sessions" view)
        can_reprocess = self.current_session_id != "__ALL__"
        self.reprocess_btn.setEnabled(can_reprocess and len(indexes) > 0)

        # Get selected row for preview (use first selected)
        proxy_index = indexes[0]
        source_index = self._proxy.mapToSource(proxy_index)
        log = self._model.getLog(source_index.row())

        if not log:
            self._image_preview.clear()
            self._file_details.clear()
            self.open_file_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.copy_path_btn.setEnabled(False)
            return

        # Determine file path to preview (prefer destination, fall back to source)
        preview_path = log.get('destination_path', '')
        if not preview_path or not os.path.exists(preview_path):
            preview_path = log.get('source_path', '')

        # Enable file action buttons if we have a valid path
        has_path = bool(preview_path)
        self.open_file_btn.setEnabled(has_path and os.path.exists(preview_path))
        self.open_folder_btn.setEnabled(has_path)
        self.copy_path_btn.setEnabled(has_path)

        # Update preview and details ONLY if inline preview is visible (performance optimization)
        if self._preview_splitter.isVisible():
            self._image_preview.setImage(preview_path)
            self._file_details.setFileDetails(log, preview_path)

        # Also update detached preview window if it's open (keep in sync with selection)
        if self._detached_preview_window and self._detached_preview_window.isVisible():
            # Build a record dict compatible with DetachablePreviewWindow
            record = {
                'file_hash': log.get('file_hash', ''),
                'source_path': log.get('source_path', ''),
                'archive_path': log.get('destination_path', ''),
                'original_date': log.get('creation_date', ''),
                'date_source': log.get('date_source', ''),
                'flag_reason': log.get('filter_reason', ''),
                'corrected_date': None,
                'needs_reorganization': False,
            }
            self._detached_preview_window.update_preview(record)

        # Also update comparison dialog if it's open and selected file is a duplicate
        if self._comparison_dialog and self._comparison_dialog.isVisible():
            if self._is_duplicate_log(log):
                self._update_comparison_dialog(log)

    def _toggle_inline_preview(self, checked: bool):
        """Toggle the inline preview panel visibility."""
        self._preview_splitter.setVisible(checked)
        self._toggle_preview_btn.setText("Hide Preview Panel" if checked else "Show Preview Panel")

        # If showing preview and a file is selected, load it now
        if checked:
            indexes = self._view.selectionModel().selectedRows()
            if indexes:
                proxy_index = indexes[0]
                source_index = self._proxy.mapToSource(proxy_index)
                log = self._model.getLog(source_index.row())
                if log:
                    preview_path = log.get('destination_path', '')
                    if not preview_path or not os.path.exists(preview_path):
                        preview_path = log.get('source_path', '')
                    self._image_preview.setImage(preview_path)
                    self._file_details.setFileDetails(log, preview_path)

    def _on_file_double_clicked(self, index):
        """Handle double-click on file row - open detached preview or comparison."""
        if not index.isValid():
            return

        # Get the log entry for the clicked row
        source_index = self._proxy.mapToSource(index)
        log = self._model.getLog(source_index.row())
        if not log:
            return

        # For duplicates, open the comparison dialog instead
        if self._is_duplicate_log(log):
            self._open_comparison_dialog(log)
        else:
            self._open_detached_preview(log)

    def _open_detached_preview(self, log: dict):
        """Open the detached preview window for a file log entry."""
        if not self.db_metadata:
            logger.warning("Cannot open detached preview: database metadata not available")
            return

        # Create the detached preview window if it doesn't exist
        if not self._detached_preview_window:
            self._detached_preview_window = DetachablePreviewWindow(
                db_metadata=self.db_metadata,
                parent=self.window()
            )
            logger.info("Created DetachablePreviewWindow for Import History tab")

        # Build a record dict compatible with DetachablePreviewWindow
        # The log dict has slightly different keys than UnreliableDates records
        record = {
            'file_hash': log.get('file_hash', ''),
            'source_path': log.get('source_path', ''),
            'archive_path': log.get('destination_path', ''),  # destination_path is the archive location
            'original_date': log.get('creation_date', ''),
            'date_source': log.get('date_source', ''),
            'flag_reason': log.get('filter_reason', ''),
            'corrected_date': None,  # Not applicable for import history
            'needs_reorganization': False,
        }

        # Update and show the preview window
        self._detached_preview_window.update_preview(record)
        self._detached_preview_window.show()
        self._detached_preview_window.raise_()
        self._detached_preview_window.activateWindow()

    def _enrich_duplicate_logs(self):
        """
        Enrich duplicate logs with archive file paths.

        For duplicate entries, looks up the archive path of the original file
        using the duplicate_of_hash or content_duplicate_of_hash field.
        This allows displaying the path to the existing archive file.
        """
        if not self.database_path:
            return

        # Combine both duplicate lists
        all_duplicates = self._duplicate_logs + getattr(self, '_content_duplicate_logs', [])
        if not all_duplicates:
            return

        try:
            from DuplicateFileDetection import PhotoDatabase

            with PhotoDatabase(self.database_path) as db:
                enriched_count = 0
                for log in all_duplicates:
                    # Get the hash of the original file (the one in the archive)
                    original_hash = log.get('duplicate_of_hash') or log.get('content_duplicate_of_hash')
                    if not original_hash:
                        continue

                    # Look up the archive path for this hash
                    archive_path = db.get_file_path_for_hash(original_hash)
                    if archive_path:
                        # Store the archive path in destination_path so it shows in the dest columns
                        log['destination_path'] = archive_path
                        log['_archive_duplicate_path'] = archive_path  # Also store explicitly
                        enriched_count += 1

                logger.info(f"Enriched {enriched_count}/{len(all_duplicates)} duplicate logs with archive paths")

        except Exception as e:
            logger.error(f"Failed to enrich duplicate logs: {e}", exc_info=True)

    def _is_duplicate_log(self, log: dict) -> bool:
        """Check if a log entry is a duplicate (regular or content duplicate)."""
        operation = log.get('operation', '')
        return operation in ('duplicate detected', 'content_duplicate_detected')

    def _compare_selected_duplicate(self):
        """Open comparison dialog for the selected duplicate entry."""
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(
                self, "No Selection",
                "Please select a duplicate entry to compare.\n\n"
                "Tip: Switch to 'Duplicates' or 'Content Duplicates' view "
                "and select a file to compare."
            )
            return

        # Get the first selected row
        source_index = self._proxy.mapToSource(indexes[0])
        log = self._model.getLog(source_index.row())
        if not log:
            return

        # Check if it's a duplicate
        if not self._is_duplicate_log(log):
            QMessageBox.information(
                self, "Not a Duplicate",
                "The selected file is not a duplicate.\n\n"
                "Comparison is only available for files marked as duplicates. "
                "Switch to 'Duplicates' or 'Content Duplicates' view to see duplicate files."
            )
            return

        self._open_comparison_dialog(log)

    def _open_comparison_dialog(self, log: dict):
        """Open the duplicate comparison dialog for a log entry."""
        source_path = log.get('source_path', '')
        archive_path = log.get('destination_path') or log.get('_archive_duplicate_path', '')

        if not source_path:
            QMessageBox.warning(
                self, "Missing Source",
                "Source file path is not available for this entry."
            )
            return

        if not archive_path:
            # Try to look up the archive path
            original_hash = log.get('duplicate_of_hash') or log.get('content_duplicate_of_hash')
            if original_hash and self.database_path:
                try:
                    from DuplicateFileDetection import PhotoDatabase
                    with PhotoDatabase(self.database_path) as db:
                        archive_path = db.get_file_path_for_hash(original_hash)
                except Exception as e:
                    logger.error(f"Failed to look up archive path: {e}")

        if not archive_path:
            QMessageBox.warning(
                self, "Missing Archive Path",
                "Could not find the archive file path for this duplicate.\n\n"
                "The original file may have been deleted from the archive."
            )
            return

        # Create comparison dialog if needed
        if not self._comparison_dialog:
            self._comparison_dialog = DuplicateComparisonDialog(parent=self.window())
            logger.info("Created DuplicateComparisonDialog")

        # Set the files and show
        self._comparison_dialog.set_files(source_path, archive_path)
        self._comparison_dialog.show()
        self._comparison_dialog.raise_()
        self._comparison_dialog.activateWindow()

    def _update_comparison_dialog(self, log: dict):
        """
        Update the comparison dialog with a new log entry.

        Called when selection changes in the grid and comparison dialog is visible.
        Unlike _open_comparison_dialog, this doesn't show warnings for missing paths
        since it's an automatic update, not a user-initiated action.
        """
        if not self._comparison_dialog:
            return

        source_path = log.get('source_path', '')
        archive_path = log.get('destination_path') or log.get('_archive_duplicate_path', '')

        # Try to look up archive path if not available
        if not archive_path:
            original_hash = log.get('duplicate_of_hash') or log.get('content_duplicate_of_hash')
            if original_hash and self.database_path:
                try:
                    from DuplicateFileDetection import PhotoDatabase
                    with PhotoDatabase(self.database_path) as db:
                        archive_path = db.get_file_path_for_hash(original_hash)
                except Exception as e:
                    logger.debug(f"Failed to look up archive path for selection update: {e}")

        # Only update if we have both paths (silently skip otherwise)
        if source_path and archive_path:
            self._comparison_dialog.set_files(source_path, archive_path)

    def _set_export_buttons_enabled(self, enabled):
        """Enable or disable export buttons."""
        self.export_json_btn.setEnabled(enabled)
        self.export_csv_btn.setEnabled(enabled)
        self.export_duplicates_btn.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)

    def export_to_json(self):
        """Export session data to JSON file."""
        if not self.audit_manager or not self.current_session_id:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to JSON",
            f"session_{self.current_session_id}.json",
            "JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            self.audit_manager.export_session_to_json(self.current_session_id, file_path)
            QMessageBox.information(self, "Export Successful",
                                   f"Session exported to:\n{file_path}")
        except Exception as e:
            logger.error(f"Failed to export to JSON: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export session:\n{e}")

    def export_to_csv(self):
        """Export session data to CSV file."""
        if not self.audit_manager or not self.current_session_id:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export to CSV",
            f"session_{self.current_session_id}.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            self.audit_manager.export_session_to_csv(self.current_session_id, file_path)
            QMessageBox.information(self, "Export Successful",
                                   f"Session exported to:\n{file_path}")
        except Exception as e:
            logger.error(f"Failed to export to CSV: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export session:\n{e}")

    def export_duplicates(self):
        """Export duplicate relationships to CSV file."""
        if not self.audit_manager or not self.current_session_id:
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Duplicates",
            f"duplicates_{self.current_session_id}.csv",
            "CSV Files (*.csv)"
        )

        if not file_path:
            return

        try:
            self.audit_manager.export_duplicates_to_csv(self.current_session_id, file_path)
            QMessageBox.information(self, "Export Successful",
                                   f"Duplicates exported to:\n{file_path}")
        except Exception as e:
            logger.error(f"Failed to export duplicates: {e}", exc_info=True)
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export duplicates:\n{e}")

    def delete_session(self):
        """Delete the selected session."""
        if not self.audit_manager or not self.current_session_id:
            QMessageBox.warning(self, "No Selection", "Please select a session to delete.")
            return

        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete this session?\n\n"
            "This will permanently remove the session and all its file logs.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            self.audit_manager.delete_session(self.current_session_id)
            self.current_session_id = None
            self.refresh_sessions()
            QMessageBox.information(self, "Deleted", "Session deleted successfully.")
        except Exception as e:
            logger.error(f"Failed to delete session: {e}", exc_info=True)
            QMessageBox.critical(self, "Delete Failed",
                               f"Failed to delete session:\n{e}")

    def reprocess_files(self):
        """Reprocess selected files from import history."""
        if not self.database_path:
            QMessageBox.warning(self, "No Database", "No database selected.")
            return

        # Get selected files
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.warning(self, "No Selection", "Please select one or more files to reprocess.")
            return

        # Collect file records
        file_records = []
        for proxy_index in indexes:
            source_index = self._proxy.mapToSource(proxy_index)
            log = self._model.getLog(source_index.row())
            if log:
                file_records.append(log)

        if not file_records:
            QMessageBox.warning(self, "No Files", "No valid files selected.")
            return

        # Get archive location and organization template from database metadata
        try:
            from database_metadata import DatabaseMetadata
            db_metadata = DatabaseMetadata(self.database_path)
            metadata = db_metadata.get_metadata()

            if not metadata:
                QMessageBox.critical(self, "Database Error",
                                   "Failed to load database metadata.")
                return

            archive_location = metadata.get('archive_location')
            organization_template = metadata.get('organization_template', '{YYYY}/{MM}/{DD}')

            if not archive_location:
                QMessageBox.critical(self, "Configuration Error",
                                   "Archive location not configured in database.")
                return

        except Exception as e:
            logger.error(f"Failed to load database metadata: {e}", exc_info=True)
            QMessageBox.critical(self, "Error",
                               f"Failed to load database settings:\n{e}")
            return

        # Show confirmation dialog
        count = len(file_records)
        reply = QMessageBox.question(
            self, "Confirm Reprocess",
            f"Reprocess {count} file(s)?\n\n"
            f"Files will be copied to:\n{archive_location}\n\n"
            f"Organization: {organization_template}\n\n"
            "Note: Duplicate files will be skipped automatically.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Create and start reprocess worker
        try:
            from ui.reprocess_worker import ReprocessWorker

            self.reprocess_worker = ReprocessWorker(
                database_path=self.database_path,
                file_records=file_records,
                archive_location=archive_location,
                organization_template=organization_template,
                copy_mode=True,  # Always copy (never move from import history)
                audit_manager=self.audit_manager  # Pass audit manager for tracking
            )

            # Connect signals
            self.reprocess_worker.progress_update.connect(self._on_reprocess_progress)
            self.reprocess_worker.status_update.connect(self._on_reprocess_status)
            self.reprocess_worker.completed.connect(self._on_reprocess_completed)
            self.reprocess_worker.error_occurred.connect(self._on_reprocess_error)

            # Create progress dialog
            self.reprocess_progress_dialog = QProgressDialog(
                "Initializing...", "Cancel", 0, count, self
            )
            self.reprocess_progress_dialog.setWindowTitle("Reprocessing Files")
            self.reprocess_progress_dialog.setWindowModality(Qt.WindowModal)
            self.reprocess_progress_dialog.setMinimumDuration(0)
            self.reprocess_progress_dialog.canceled.connect(self._on_reprocess_cancel)

            # Start worker
            self.reprocess_worker.start()
            logger.info(f"Started reprocessing {count} file(s)")

        except Exception as e:
            logger.error(f"Failed to start reprocess worker: {e}", exc_info=True)
            QMessageBox.critical(self, "Error",
                               f"Failed to start reprocessing:\n{e}")

    def _on_reprocess_progress(self, current, total, filename):
        """Update progress dialog."""
        if hasattr(self, 'reprocess_progress_dialog'):
            self.reprocess_progress_dialog.setValue(current)
            self.reprocess_progress_dialog.setLabelText(f"Processing {filename}...")

    def _on_reprocess_status(self, message):
        """Update status in progress dialog."""
        if hasattr(self, 'reprocess_progress_dialog'):
            self.reprocess_progress_dialog.setLabelText(message)

    def _on_reprocess_completed(self, results):
        """Handle reprocess completion."""
        if hasattr(self, 'reprocess_progress_dialog'):
            self.reprocess_progress_dialog.close()

        total = results.get('total', 0)
        successful = results.get('successful', 0)
        failed = results.get('failed', 0)
        skipped = results.get('skipped', 0)
        session_id = results.get('session_id')

        # Build result message
        message_parts = [
            f"Reprocessing complete!",
            f"",
            f"Total: {total}",
            f"Successful: {successful}",
            f"Skipped (duplicates): {skipped}",
            f"Failed: {failed}"
        ]

        # Add session info if available
        if session_id:
            message_parts.append("")
            message_parts.append(f"Session ID: {session_id}")
            message_parts.append("View details in Import History tab")

        # Add details about failures if any
        if failed > 0:
            failed_files = results.get('failed_files', [])
            message_parts.append("")
            message_parts.append("Failed files:")
            for item in failed_files[:5]:  # Show first 5 failures
                filename = item.get('filename', 'Unknown')
                reason = item.get('reason', 'Unknown error')
                message_parts.append(f"  • {filename}: {reason}")
            if len(failed_files) > 5:
                message_parts.append(f"  ... and {len(failed_files) - 5} more")

        # Add destination info for successful files
        if successful > 0:
            successful_files = results.get('successful_files', [])
            if successful_files:
                first_file = successful_files[0]
                dest_path = first_file.get('destination_path', '')
                if dest_path:
                    message_parts.append("")
                    message_parts.append(f"Files copied to: {os.path.dirname(dest_path)}")

        message = "\n".join(message_parts)

        # Show appropriate dialog based on results
        if failed > 0:
            QMessageBox.warning(self, "Reprocess Complete with Errors", message)
        else:
            QMessageBox.information(self, "Reprocess Complete", message)

        # Refresh the session view
        self.refresh_sessions()
        logger.info(f"Reprocessing completed: {successful} successful, {skipped} skipped, {failed} failed (session: {session_id})")

    def _on_reprocess_error(self, error_message):
        """Handle reprocess error."""
        if hasattr(self, 'reprocess_progress_dialog'):
            self.reprocess_progress_dialog.close()

        QMessageBox.critical(self, "Reprocess Error",
                           f"An error occurred during reprocessing:\n\n{error_message}")
        logger.error(f"Reprocess error: {error_message}")

    def _on_reprocess_cancel(self):
        """Handle reprocess cancellation."""
        if hasattr(self, 'reprocess_worker'):
            self.reprocess_worker.stop()
            logger.info("Reprocess cancelled by user")

    def override_skip_files(self):
        """Import selected filtered files, bypassing PhotoFilter criteria."""
        # 1. Check database connection
        if not self.database_path:
            QMessageBox.information(self, "No Database",
                "Please open a database first.")
            return

        # 2. Get selected rows
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(self, "No Selection",
                "Please select one or more files to import.")
            return

        # 3. Filter to only skip_filtered records
        filtered_records = []
        for proxy_index in indexes:
            source_index = self._proxy.mapToSource(proxy_index)
            log = self._model.getLog(source_index.row())
            if log and log.get('operation') == 'skip_filtered':
                filtered_records.append(log)

        if not filtered_records:
            QMessageBox.information(self, "No Filtered Files",
                "Please select files that were filtered.\n\n"
                "Tip: Use the 'Show' dropdown and select "
                "'Filtered (Icons/Thumbnails)' to see filtered files.")
            return

        # 4. Verify source files exist and calculate total size
        missing_files = []
        valid_records = []
        total_size = 0
        for record in filtered_records:
            source_path = record.get('source_path', '')
            if os.path.exists(source_path):
                valid_records.append(record)
                try:
                    total_size += os.path.getsize(source_path)
                except OSError:
                    pass
            else:
                missing_files.append(os.path.basename(source_path))

        if missing_files:
            msg = f"{len(missing_files)} file(s) no longer exist:\n"
            msg += "\n".join(missing_files[:5])
            if len(missing_files) > 5:
                msg += f"\n... and {len(missing_files) - 5} more"
            if not valid_records:
                QMessageBox.information(self, "Files Not Found", msg)
                return
            QMessageBox.warning(self, "Some Files Missing", msg)

        if not valid_records:
            return

        # 5. Get archive settings
        from database_metadata import DatabaseMetadata
        db_metadata = DatabaseMetadata(self.database_path)
        metadata = db_metadata.get_metadata()
        archive_location = metadata.get('archive_location')
        organization_template = metadata.get('organization_template', '{year}/{month}/{day}')

        if not archive_location:
            QMessageBox.critical(self, "Configuration Error",
                "Archive location not configured.")
            return

        # Format total size for display
        size_str = self._format_file_size(total_size)

        # 6. Show confirmation with file size
        count = len(valid_records)
        reply = QMessageBox.question(
            self, "Confirm Override Skip",
            f"Import {count} filtered file(s)?\n\n"
            f"Total size: {size_str}\n\n"
            f"These files were previously skipped by the photo filter "
            f"(size/dimension criteria).\n\n"
            f"Destination: {archive_location}\n"
            f"Organization: {organization_template}\n\n"
            "Duplicate files will be skipped automatically.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # 6.5. Preserve current state for restoration after completion
        self._preserved_session_id = self.current_session_id
        self._preserved_scroll_position = self._view.verticalScrollBar().value()
        # Store source paths of selected rows for position restoration
        self._preserved_selection_paths = set()
        for record in valid_records:
            self._preserved_selection_paths.add(record.get('source_path', ''))

        # 7. Build source album mapping from database
        source_album_mapping = {}
        try:
            source_dirs = db_metadata.get_source_directories()
            for sd in source_dirs:
                if sd.get('album_id'):
                    source_album_mapping[sd['path']] = {
                        'album_id': sd['album_id'],
                        'enable_sub_albums': bool(sd.get('enable_sub_albums', 0))
                    }
        except Exception as e:
            logger.warning(f"Failed to load source album mappings: {e}")

        # 8. Get album manager if albums configured
        album_manager = None
        if source_album_mapping:
            from album_manager import AlbumManager
            album_manager = AlbumManager(self.database_path)

        # 9. Mark selected rows as processing (visual feedback)
        self._model.markRowsAsProcessing(self._preserved_selection_paths)

        # 10. Create and start worker (reuse ReprocessWorker)
        from ui.reprocess_worker import ReprocessWorker

        self.override_skip_worker = ReprocessWorker(
            database_path=self.database_path,
            file_records=valid_records,
            archive_location=archive_location,
            organization_template=organization_template,
            copy_mode=True,
            audit_manager=self.audit_manager,
            album_manager=album_manager,
            source_album_mapping=source_album_mapping
        )

        # Connect signals
        self.override_skip_worker.progress_update.connect(self._on_override_skip_progress)
        self.override_skip_worker.status_update.connect(self._on_override_skip_status)
        self.override_skip_worker.completed.connect(self._on_override_skip_completed)
        self.override_skip_worker.error_occurred.connect(self._on_override_skip_error)
        self.override_skip_worker.file_processed.connect(self._on_override_skip_file_processed)

        # Create progress dialog
        self.override_skip_progress_dialog = QProgressDialog(
            "Initializing...", "Cancel", 0, count, self
        )
        self.override_skip_progress_dialog.setWindowTitle("Importing Filtered Files")
        self.override_skip_progress_dialog.setWindowModality(Qt.WindowModal)
        self.override_skip_progress_dialog.setMinimumDuration(0)
        self.override_skip_progress_dialog.canceled.connect(self._on_override_skip_cancel)

        # Start worker
        self.override_skip_worker.start()
        logger.info(f"Started override skip import for {count} file(s)")

    def _on_override_skip_progress(self, current, total, filename):
        """Update progress dialog for override skip operation."""
        if hasattr(self, 'override_skip_progress_dialog'):
            self.override_skip_progress_dialog.setValue(current)
            self.override_skip_progress_dialog.setLabelText(f"Importing: {filename}")

    def _on_override_skip_status(self, message):
        """Update status for override skip operation."""
        logger.info(f"Override skip status: {message}")

    def _on_override_skip_file_processed(self, source_path: str, result: str):
        """Handle per-file processing result for real-time UI updates."""
        if result in ('success', 'skipped'):
            # Find the proxy row index for this source path before removal
            proxy_row_to_select = -1
            for row in range(self._proxy.rowCount()):
                proxy_index = self._proxy.index(row, 0)
                source_index = self._proxy.mapToSource(proxy_index)
                log = self._model._data[source_index.row()]
                if log.get('source_path') == source_path:
                    proxy_row_to_select = row
                    break

            # Remove the row from the view immediately
            self._model.removeRowsBySourcePath({source_path})

            # Also remove from cached filtered logs
            if hasattr(self, '_filtered_logs'):
                self._filtered_logs = [
                    log for log in self._filtered_logs
                    if log.get('source_path') != source_path
                ]

            self._update_count()

            # Select the next row to maintain user's place
            if proxy_row_to_select >= 0 and self._proxy.rowCount() > 0:
                # Select the same row index (which now contains the next item)
                # or the last row if we removed the last item
                new_row = min(proxy_row_to_select, self._proxy.rowCount() - 1)
                new_index = self._proxy.index(new_row, 0)
                self._view.selectionModel().select(
                    new_index,
                    self._view.selectionModel().SelectionFlag.ClearAndSelect |
                    self._view.selectionModel().SelectionFlag.Rows
                )
                self._view.scrollTo(new_index)

    def _on_override_skip_completed(self, results):
        """Handle override skip completion."""
        if hasattr(self, 'override_skip_progress_dialog'):
            self.override_skip_progress_dialog.close()

        successful = results.get('successful', 0)
        failed = results.get('failed', 0)
        skipped = results.get('skipped', 0)
        successful_files = results.get('successful_files', [])
        skipped_files = results.get('skipped_files', [])

        # Store results for undo capability
        self._last_override_skip_results = results

        # Build set of source paths that were successfully processed or skipped as duplicates
        # These should be removed from the filtered view
        paths_to_remove = set()
        for item in successful_files:
            paths_to_remove.add(item.get('source_path', ''))
        for item in skipped_files:
            paths_to_remove.add(item.get('source_path', ''))

        # Add successful files to recently overridden list (for the filter)
        for item in successful_files:
            # Create a log-like entry for the recently overridden view
            override_log = {
                'source_path': item.get('source_path', ''),
                'destination_path': item.get('destination_path', ''),
                'operation': 'override_skip',
                'status': 'success',
                'file_hash': item.get('file_hash', ''),
            }
            self._recently_overridden_logs.append(override_log)

        # Clear processing flags (in case any remain)
        self._model.clearProcessingFlags()

        # Note: Rows are already removed incrementally via _on_override_skip_file_processed
        # This is a safety net to ensure any missed rows are cleaned up
        if paths_to_remove:
            # Try to remove any remaining rows (should be 0 if incremental removal worked)
            remaining_removed = self._model.removeRowsBySourcePath(paths_to_remove)
            if remaining_removed > 0:
                logger.info(f"Safety cleanup removed {remaining_removed} additional rows from view")

        # Restore scroll position
        if self._preserved_scroll_position > 0:
            QTimer.singleShot(50, lambda: self._view.verticalScrollBar().setValue(
                min(self._preserved_scroll_position, self._view.verticalScrollBar().maximum())
            ))

        # Update the count label
        self._update_count()

        # Build result message
        msg = f"Override Skip Complete\n\n"
        msg += f"Successfully imported: {successful}\n"
        msg += f"Duplicates skipped: {skipped}\n"
        msg += f"Failed: {failed}"

        # Add destination info for successful files
        if successful > 0 and successful_files:
            first_file = successful_files[0]
            dest_path = first_file.get('destination_path', '')
            if dest_path:
                msg += f"\n\nFiles copied to: {os.path.dirname(dest_path)}"

        # Note about viewing imported files
        if successful > 0:
            msg += "\n\nTip: Use 'Recently Overridden' filter to see imported files."

        QMessageBox.information(self, "Override Skip Complete", msg)

        # Note: We intentionally do NOT call refresh_sessions() here
        # to preserve the current session view and scroll position
        logger.info(f"Override skip completed: {successful} successful, {skipped} skipped, {failed} failed")

    def _on_override_skip_error(self, error_message):
        """Handle override skip error."""
        if hasattr(self, 'override_skip_progress_dialog'):
            self.override_skip_progress_dialog.close()
        # Clear processing flags on error
        self._model.clearProcessingFlags()
        QMessageBox.critical(self, "Error", f"Override skip failed:\n{error_message}")
        logger.error(f"Override skip error: {error_message}")

    def _on_override_skip_cancel(self):
        """Handle override skip cancellation."""
        if hasattr(self, 'override_skip_worker'):
            self.override_skip_worker.stop()
            # Clear processing flags on cancel
            self._model.clearProcessingFlags()
            logger.info("Override skip cancelled by user")

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} PB"

    def undo_last_override_skip(self):
        """Undo the last override skip operation."""
        if not self._last_override_skip_results:
            QMessageBox.information(self, "Nothing to Undo",
                "No recent override skip operation to undo.")
            return

        successful_files = self._last_override_skip_results.get('successful_files', [])
        if not successful_files:
            QMessageBox.information(self, "Nothing to Undo",
                "No files were imported in the last override skip operation.")
            return

        # Show confirmation
        count = len(successful_files)
        reply = QMessageBox.question(
            self, "Confirm Undo",
            f"Undo the import of {count} file(s)?\n\n"
            "This will:\n"
            "- Delete files from the archive\n"
            "- Remove entries from the database\n"
            "- Restore rows to the filtered view\n\n"
            "Source files will not be affected.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            import DuplicateFileDetection

            deleted_count = 0
            db_removed_count = 0
            restored_to_view = []

            with DuplicateFileDetection.PhotoDatabase(self.database_path) as db:
                for item in successful_files:
                    dest_path = item.get('destination_path', '')
                    source_path = item.get('source_path', '')
                    file_hash = item.get('file_hash', '')

                    # Delete archive file
                    if dest_path and os.path.exists(dest_path):
                        try:
                            os.remove(dest_path)
                            deleted_count += 1
                            logger.info(f"Deleted archive file: {dest_path}")
                        except OSError as e:
                            logger.warning(f"Failed to delete {dest_path}: {e}")

                    # Remove from database
                    if file_hash:
                        try:
                            db.cursor.execute(
                                "DELETE FROM UniquePhotos WHERE file_hash = ?",
                                (file_hash,)
                            )
                            if db.cursor.rowcount > 0:
                                db_removed_count += 1
                        except Exception as e:
                            logger.warning(f"Failed to remove hash {file_hash} from DB: {e}")

                    # Restore to filtered view (recreate the log entry)
                    if source_path:
                        restored_log = {
                            'source_path': source_path,
                            'operation': 'skip_filtered',
                            'status': 'skipped',
                            'filter_reason': 'Restored after undo',
                        }
                        restored_to_view.append(restored_log)

                db.conn.commit()

            # Add restored items back to filtered logs
            if restored_to_view and hasattr(self, '_filtered_logs'):
                self._filtered_logs.extend(restored_to_view)
                # If currently showing filtered view, refresh it
                if self._show_combo.currentText() == "Filtered (Icons/Thumbnails)":
                    self._apply_show_filter()

            # Remove from recently overridden
            paths_undone = {item.get('source_path', '') for item in successful_files}
            self._recently_overridden_logs = [
                log for log in self._recently_overridden_logs
                if log.get('source_path') not in paths_undone
            ]

            # Clear the undo state
            self._last_override_skip_results = None

            QMessageBox.information(self, "Undo Complete",
                f"Undo completed:\n\n"
                f"Archive files deleted: {deleted_count}\n"
                f"Database entries removed: {db_removed_count}\n"
                f"Rows restored to view: {len(restored_to_view)}")

            logger.info(f"Undo override skip: deleted {deleted_count} files, "
                       f"removed {db_removed_count} DB entries, "
                       f"restored {len(restored_to_view)} rows")

        except Exception as e:
            logger.error(f"Failed to undo override skip: {e}", exc_info=True)
            QMessageBox.critical(self, "Undo Failed",
                f"Failed to undo override skip:\n{e}")

    def open_selected_file(self):
        """Open the selected file with default application."""
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            return

        # Get first selected file
        proxy_index = indexes[0]
        source_index = self._proxy.mapToSource(proxy_index)
        log = self._model.getLog(source_index.row())

        if not log:
            return

        # Determine file path (prefer destination, fall back to source)
        file_path = log.get('destination_path', '')
        if not file_path or not os.path.exists(file_path):
            file_path = log.get('source_path', '')

        if not file_path or not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found",
                              f"File does not exist:\n{file_path}")
            return

        try:
            # Open file with default application (platform-independent)
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # Linux/Mac
                subprocess.run(['xdg-open', file_path], check=False)

        except Exception as e:
            logger.error(f"Failed to open file: {e}", exc_info=True)
            QMessageBox.critical(self, "Error Opening File",
                               f"Failed to open file:\n{str(e)}")

    def open_file_folder(self):
        """Open the folder containing the selected file."""
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            return

        # Get first selected file
        proxy_index = indexes[0]
        source_index = self._proxy.mapToSource(proxy_index)
        log = self._model.getLog(source_index.row())

        if not log:
            return

        # Determine file path (prefer destination, fall back to source)
        file_path = log.get('destination_path', '')
        if not file_path or not os.path.exists(file_path):
            file_path = log.get('source_path', '')

        folder_path = os.path.dirname(file_path) if file_path else ''

        if not folder_path or not os.path.exists(folder_path):
            QMessageBox.warning(self, "Folder Not Found",
                              f"Folder does not exist:\n{folder_path}")
            return

        try:
            # Open folder with file manager (platform-independent)
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            elif os.name == 'posix':  # Linux/Mac
                subprocess.run(['xdg-open', folder_path], check=False)

        except Exception as e:
            logger.error(f"Failed to open folder: {e}", exc_info=True)
            QMessageBox.critical(self, "Error Opening Folder",
                               f"Failed to open folder:\n{str(e)}")

    def copy_file_path(self):
        """Copy the selected file path to clipboard."""
        indexes = self._view.selectionModel().selectedRows()
        if not indexes:
            return

        # Get first selected file
        proxy_index = indexes[0]
        source_index = self._proxy.mapToSource(proxy_index)
        log = self._model.getLog(source_index.row())

        if not log:
            return

        # Determine file path (prefer destination, fall back to source)
        file_path = log.get('destination_path', '')
        if not file_path or not os.path.exists(file_path):
            file_path = log.get('source_path', '')

        if not file_path:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(file_path)

        # Show brief confirmation (no blocking dialog)
        logger.info(f"Copied to clipboard: {file_path}")

    def cleanup_workers(self):
        """
        Stop and wait for any running worker threads.

        Called by main window before closing to prevent
        'QThread destroyed while thread is still running' errors.
        """
        if self.reprocess_worker and self.reprocess_worker.isRunning():
            logger.info("Stopping reprocess worker before close...")
            self.reprocess_worker.stop()
            self.reprocess_worker.wait()
            logger.info("Reprocess worker stopped")

        if self.override_skip_worker and self.override_skip_worker.isRunning():
            logger.info("Stopping override skip worker before close...")
            self.override_skip_worker.stop()
            self.override_skip_worker.wait()
            logger.info("Override skip worker stopped")
