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
    QTableView, QLineEdit, QApplication, QGraphicsView,
    QGraphicsScene, QGraphicsPixmapItem, QFrame, QScrollArea,
    QFormLayout, QSizePolicy, QProgressDialog
)
import subprocess
from PySide6.QtCore import (
    Qt, QAbstractTableModel, QModelIndex, QSortFilterProxyModel,
    QTimer, QSize, QRectF
)
from PySide6.QtGui import QColor, QBrush, QPixmap, QImage, QPainter, QPen
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

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

        elif role == Qt.UserRole:
            # Return raw data for sorting
            return self._get_sort_value(log, col_key)

        return None

    def _get_display_value(self, log: Dict, col_key: str) -> str:
        """Get display value for a column."""
        if col_key == "source_folder":
            source = log.get('source_path', '')
            return os.path.dirname(source) if source else ''

        elif col_key == "source_filename":
            source = log.get('source_path', '')
            return os.path.basename(source) if source else ''

        elif col_key == "dest_folder":
            dest = log.get('destination_path', '')
            return os.path.dirname(dest) if dest else ''

        elif col_key == "dest_filename":
            dest = log.get('destination_path', '')
            return os.path.basename(dest) if dest else ''

        elif col_key == "operation":
            op = log.get('operation', '')
            return op.replace('_', ' ').title()

        elif col_key == "status":
            return log.get('status', '').title()

        elif col_key == "file_hash":
            h = log.get('file_hash', '')
            return h[:12] + "..." if h and len(h) > 12 else h

        elif col_key == "details":
            details = log.get('error_message') or log.get('filter_reason') or ''
            return details[:50] + "..." if len(details) > 50 else details

        return ''

    def _get_tooltip(self, log: Dict, col_key: str) -> str:
        """Get tooltip for a cell."""
        if col_key == "source_folder" or col_key == "source_filename":
            return log.get('source_path', '')
        elif col_key == "dest_folder" or col_key == "dest_filename":
            return log.get('destination_path', '')
        elif col_key == "file_hash":
            return log.get('file_hash', '')
        elif col_key == "details":
            return log.get('error_message') or log.get('filter_reason') or ''
        return ''

    def _get_sort_value(self, log: Dict, col_key: str):
        """Get value for sorting (may differ from display)."""
        if col_key == "source_folder":
            source = log.get('source_path', '')
            return os.path.dirname(source).lower() if source else ''
        elif col_key == "source_filename":
            source = log.get('source_path', '')
            return os.path.basename(source).lower() if source else ''
        elif col_key == "dest_folder":
            dest = log.get('destination_path', '')
            return os.path.dirname(dest).lower() if dest else ''
        elif col_key == "dest_filename":
            dest = log.get('destination_path', '')
            return os.path.basename(dest).lower() if dest else ''
        elif col_key == "operation":
            return log.get('operation', '').lower()
        elif col_key == "status":
            return log.get('status', '').lower()
        elif col_key == "file_hash":
            return log.get('file_hash', '')
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
            op = log.get('operation', '').lower()
            if self._operation_filter not in op:
                return False

        # Status filter
        if self._status_filter:
            status = log.get('status', '').lower()
            if self._status_filter != status:
                return False

        # Search text filter (search across all fields)
        if self._search_text:
            searchable = ' '.join([
                log.get('source_path', ''),
                log.get('destination_path', ''),
                log.get('operation', ''),
                log.get('status', ''),
                log.get('file_hash', ''),
                log.get('error_message', ''),
                log.get('filter_reason', ''),
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
    MIN_WIDTHS = [100, 80, 100, 80, 70, 60, 80, 80]
    # Column weight ratios for proportional resizing
    COLUMN_WEIGHTS = [2.5, 1.5, 2.5, 1.5, 1.0, 0.8, 1.0, 1.5]

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
        if not self.model() or self.model().columnCount() < 8:
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


class ImagePreviewWidget(QGraphicsView):
    """
    Widget for displaying image preview with rubber band zoom capabilities.
    Drag to select area to zoom, double-click to reset to fit-to-view.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._pixmap_item = None
        self.setScene(self._scene)

        # Enable antialiasing for smooth zooming
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

        # Configure scrollbars
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Styling
        self.setBackgroundBrush(QBrush(QColor('#2d2d2d')))
        self.setFrameShape(QFrame.NoFrame)

        # Rubber band zoom state
        self._rubber_band_origin = None
        self._rubber_band_rect = None
        self._is_rubber_banding = False
        self._is_custom_zoom = False

        # Set minimum size
        self.setMinimumSize(200, 200)

        # Timer for delayed fit after resize
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._delayed_fit)

    def setImage(self, file_path: str):
        """Load and display image from file path."""
        self._scene.clear()
        self._pixmap_item = None
        self._is_custom_zoom = False
        self._rubber_band_rect = None

        if not file_path or not os.path.exists(file_path):
            self._show_placeholder("No image available")
            return

        # Check if file is an image
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in image_extensions:
            self._show_placeholder(f"Not an image file\n({ext})")
            return

        try:
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                self._show_placeholder("Failed to load image")
                return

            self._pixmap_item = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._pixmap_item)
            # Set scene rect to image bounds
            self._scene.setSceneRect(self._pixmap_item.boundingRect())
            self._zoom_to_fit()

        except Exception as e:
            logger.error(f"Failed to load image {file_path}: {e}", exc_info=True)
            self._show_placeholder(f"Error loading image:\n{str(e)[:50]}")

    def _zoom_to_fit(self):
        """Zoom image to fit the view."""
        if self._pixmap_item:
            # Reset any transforms first
            self.resetTransform()
            # Get the image bounding rect
            rect = self._pixmap_item.boundingRect()
            # Set scene rect to match
            self._scene.setSceneRect(rect)
            # Fit the view to show the entire image
            self.fitInView(rect, Qt.KeepAspectRatio)
            self._is_custom_zoom = False

    def _delayed_fit(self):
        """Called after resize timer - ensures proper fitting."""
        if self._pixmap_item and not self._is_rubber_banding and not self._is_custom_zoom:
            self._zoom_to_fit()

    def _show_placeholder(self, text: str):
        """Show placeholder text when no image is available."""
        self._scene.clear()
        self._pixmap_item = None
        text_item = self._scene.addText(text)
        text_item.setDefaultTextColor(QColor('#888888'))
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    def clear(self):
        """Clear the preview."""
        self._scene.clear()
        self._pixmap_item = None
        self._is_custom_zoom = False
        self._rubber_band_rect = None
        self._show_placeholder("Select a file to preview")

    def resizeEvent(self, event):
        """Handle resize - maintain zoom state."""
        super().resizeEvent(event)
        # Use timer to delay fit until after resize is complete
        if self._pixmap_item and not self._is_rubber_banding and not self._is_custom_zoom:
            self._resize_timer.start(50)  # 50ms delay

    def mousePressEvent(self, event):
        """Start rubber band selection."""
        if event.button() == Qt.LeftButton and self._pixmap_item:
            self._rubber_band_origin = self.mapToScene(event.pos())
            self._is_rubber_banding = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update rubber band rectangle."""
        if self._is_rubber_banding and self._rubber_band_origin:
            current_pos = self.mapToScene(event.pos())

            # Remove old rubber band
            if self._rubber_band_rect:
                self._scene.removeItem(self._rubber_band_rect)

            # Create new rubber band rectangle
            x = min(self._rubber_band_origin.x(), current_pos.x())
            y = min(self._rubber_band_origin.y(), current_pos.y())
            width = abs(current_pos.x() - self._rubber_band_origin.x())
            height = abs(current_pos.y() - self._rubber_band_origin.y())

            rect = QRectF(x, y, width, height)

            # Draw rubber band
            pen = QPen(QColor(0, 120, 215), 2, Qt.DashLine)
            self._rubber_band_rect = self._scene.addRect(rect, pen)

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Complete rubber band zoom."""
        if event.button() == Qt.LeftButton and self._is_rubber_banding:
            if self._rubber_band_origin:
                current_pos = self.mapToScene(event.pos())

                # Calculate zoom rectangle
                x = min(self._rubber_band_origin.x(), current_pos.x())
                y = min(self._rubber_band_origin.y(), current_pos.y())
                width = abs(current_pos.x() - self._rubber_band_origin.x())
                height = abs(current_pos.y() - self._rubber_band_origin.y())

                # Only zoom if rectangle is large enough (> 10 pixels)
                if width > 10 and height > 10:
                    zoom_rect = QRectF(x, y, width, height)
                    self.fitInView(zoom_rect, Qt.KeepAspectRatio)
                    self._is_custom_zoom = True
                    self.viewport().update()

                # Remove rubber band
                if self._rubber_band_rect:
                    self._scene.removeItem(self._rubber_band_rect)
                    self._rubber_band_rect = None

            self._rubber_band_origin = None
            self._is_rubber_banding = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click to reset zoom to fit."""
        if event.button() == Qt.LeftButton:
            self._zoom_to_fit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)


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
                exif_data = img._getexif()
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
        self.current_session_id = None
        self._sessions_cache = []

        # Model and proxy for file logs
        self._model = FileLogTableModel(self)
        self._proxy = FileLogFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        # Search debounce timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_search)

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
            "Filtered (Icons/Thumbnails)",
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

        grid_layout.addLayout(filter_layout)

        # Table view
        self._view = FileLogTableView(self)
        self._view.setModel(self._proxy)
        self._view.selectionModel().selectionChanged.connect(self._on_file_selected)
        grid_layout.addWidget(self._view)

        # Connect proxy model changes to update count
        self._proxy.rowsInserted.connect(self._update_count)
        self._proxy.rowsRemoved.connect(self._update_count)
        self._proxy.modelReset.connect(self._update_count)
        self._proxy.layoutChanged.connect(self._update_count)

        main_splitter.addWidget(grid_group)

        # === Bottom Section: Preview and File Details ===
        preview_splitter = QSplitter(Qt.Horizontal)

        # Image preview
        preview_group = QGroupBox("Image Preview (drag to zoom, double-click to reset)")
        preview_layout = QVBoxLayout(preview_group)
        preview_layout.setContentsMargins(4, 4, 4, 4)
        self._image_preview = ImagePreviewWidget()
        preview_layout.addWidget(self._image_preview)
        preview_splitter.addWidget(preview_group)

        # File details
        details_file_group = QGroupBox("File Details")
        details_file_layout = QVBoxLayout(details_file_group)
        details_file_layout.setContentsMargins(4, 4, 4, 4)
        self._file_details = FileDetailsWidget()
        details_file_layout.addWidget(self._file_details)
        preview_splitter.addWidget(details_file_group)

        # Set horizontal splitter proportions (60% preview, 40% details)
        preview_splitter.setSizes([400, 300])

        main_splitter.addWidget(preview_splitter)

        # Set vertical splitter proportions (60% grid, 40% preview)
        main_splitter.setSizes([400, 250])

        main_layout.addWidget(main_splitter, 1)

        # === Export Buttons ===
        export_layout = QHBoxLayout()

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
                self.audit_manager = AuditManager(database_path)
                self.refresh_sessions()
            except Exception as e:
                logger.error(f"Failed to initialize audit manager: {e}", exc_info=True)
                self.audit_manager = None
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

            # Select first session
            if sessions:
                self.session_combo.setCurrentIndex(0)
                self.on_session_selected(0)

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

            # Get all file logs (limit to 10,000 most recent)
            all_logs = self.audit_manager.get_all_file_logs(limit=10000)

            # Store full data and pre-compute filtered views
            self._all_logs = all_logs
            self._new_files_logs = [l for l in all_logs if l.get('operation') in ('copy', 'move', 'reprocess')]
            self._duplicate_logs = [l for l in all_logs if l.get('operation') == 'duplicate detected']
            self._filtered_logs = [l for l in all_logs if l.get('operation') == 'skip_filtered']
            self._error_logs = [l for l in all_logs if l.get('status') == 'failed']

            # Apply current show filter
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

            # Get all file logs
            all_logs = self.audit_manager.get_file_logs_for_session(self.current_session_id)

            # Store full data and pre-compute filtered views
            self._all_logs = all_logs
            self._new_files_logs = [l for l in all_logs if l.get('operation') in ('copy', 'move', 'reprocess')]
            self._duplicate_logs = [l for l in all_logs if l.get('operation') == 'duplicate detected']
            self._filtered_logs = [l for l in all_logs if l.get('operation') == 'skip_filtered']
            self._error_logs = [l for l in all_logs if l.get('status') == 'failed']

            # Apply current show filter
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
        elif show == "Filtered (Icons/Thumbnails)":
            self._model.setData(self._filtered_logs)
        elif show == "Errors":
            self._model.setData(self._error_logs)
        else:  # "All Files"
            self._model.setData(self._all_logs)

        self._update_count()

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

        # Update preview and details
        self._image_preview.setImage(preview_path)
        self._file_details.setFileDetails(log, preview_path)

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
