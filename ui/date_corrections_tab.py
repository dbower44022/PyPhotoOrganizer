"""
Date Corrections Tab

Displays files with unreliable date information in a sortable grid.
Allows users to review, preview, and correct file dates.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QCheckBox, QMessageBox,
                               QGraphicsView, QGraphicsScene, QGraphicsPixmapItem,
                               QLineEdit, QApplication, QComboBox)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PIL import Image
import os
import logging
from typing import List, Dict, Any, Optional

# Import profiling utilities
from utils import profile_block

# Import grid components
from ui.unreliable_dates_grid_model import UnreliableDatesGridModel
from ui.unreliable_dates_grid_view import UnreliableDatesGridView
from ui.detachable_preview_window import DetachablePreviewWindow

# Import triage thumbnail cache
from triage.thumbnail_cache import ThumbnailCache

logger = logging.getLogger(__name__)


class ZoomableImageViewer(QGraphicsView):
    """Image viewer with zoom-to-fit and rubber band zoom capabilities."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        # Enable antialiasing for smooth zooming
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

        # Disable scrollbars (we'll use zoom-to-fit)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Image item
        self.pixmap_item = None
        self.original_pixmap = None

        # Rubber band zoom state
        self.rubber_band_origin = None
        self.rubber_band_rect = None
        self.is_rubber_banding = False
        self.is_custom_zoom = False  # Track if user has applied a custom zoom

        # Styling
        self.setStyleSheet("border: 1px solid #ddd; background-color: #f5f5f5;")

    def load_image(self, file_path):
        """Load and display an image with zoom-to-fit."""
        try:
            # Clear previous image
            self.scene.clear()
            self.pixmap_item = None
            self.original_pixmap = None
            self.is_custom_zoom = False  # Reset zoom state for new image

            if not os.path.exists(file_path):
                return

            # Load image with PIL (handles various formats)
            pil_img = Image.open(file_path)

            # Convert to RGB if necessary
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')

            # Convert PIL image to QPixmap
            img_data = pil_img.tobytes('raw', 'RGB')
            qimage = QImage(img_data, pil_img.width, pil_img.height,
                          pil_img.width * 3, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            # Store original pixmap
            self.original_pixmap = pixmap

            # Add to scene
            self.pixmap_item = QGraphicsPixmapItem(pixmap)
            self.scene.addItem(self.pixmap_item)

            # Zoom to fit
            self.zoom_to_fit()

        except Exception as e:
            logger.error(f"Failed to load image {file_path}: {e}")

    def zoom_to_fit(self):
        """Zoom image to fit the view."""
        if self.pixmap_item:
            # Get the bounding rectangle of the image
            rect = self.pixmap_item.boundingRect()
            # Fit the entire image in the view
            self.fitInView(rect, Qt.KeepAspectRatio)
            self.is_custom_zoom = False  # Reset to fit-to-view mode
            logger.debug("Zoom reset to fit-to-view")

    def resizeEvent(self, event):
        """Handle resize events - maintain zoom state."""
        super().resizeEvent(event)
        # Only auto-fit if not rubber banding and not in custom zoom mode
        if self.pixmap_item and not self.is_rubber_banding and not self.is_custom_zoom:
            self.zoom_to_fit()

    def mousePressEvent(self, event):
        """Start rubber band selection."""
        if event.button() == Qt.LeftButton and self.pixmap_item:
            self.rubber_band_origin = self.mapToScene(event.pos())
            self.is_rubber_banding = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update rubber band rectangle."""
        if self.is_rubber_banding and self.rubber_band_origin:
            current_pos = self.mapToScene(event.pos())

            # Remove old rubber band
            if self.rubber_band_rect:
                self.scene.removeItem(self.rubber_band_rect)

            # Create new rubber band rectangle
            x = min(self.rubber_band_origin.x(), current_pos.x())
            y = min(self.rubber_band_origin.y(), current_pos.y())
            width = abs(current_pos.x() - self.rubber_band_origin.x())
            height = abs(current_pos.y() - self.rubber_band_origin.y())

            rect = QRectF(x, y, width, height)

            # Draw rubber band
            pen = QPen(QColor(0, 120, 215), 2, Qt.DashLine)
            self.rubber_band_rect = self.scene.addRect(rect, pen)

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Complete rubber band zoom."""
        if event.button() == Qt.LeftButton and self.is_rubber_banding:
            if self.rubber_band_origin:
                current_pos = self.mapToScene(event.pos())

                # Calculate zoom rectangle in scene coordinates
                x = min(self.rubber_band_origin.x(), current_pos.x())
                y = min(self.rubber_band_origin.y(), current_pos.y())
                width = abs(current_pos.x() - self.rubber_band_origin.x())
                height = abs(current_pos.y() - self.rubber_band_origin.y())

                logger.info(f"Rubber band zoom: x={x:.1f}, y={y:.1f}, w={width:.1f}, h={height:.1f}")

                # Only zoom if rectangle is large enough (> 10 pixels)
                if width > 10 and height > 10:
                    zoom_rect = QRectF(x, y, width, height)
                    logger.info(f"Applying zoom to rect: {zoom_rect}")

                    # Apply the zoom
                    self.fitInView(zoom_rect, Qt.KeepAspectRatio)
                    self.is_custom_zoom = True  # Mark that user has zoomed in

                    # Force view update
                    self.viewport().update()
                    logger.info("Zoom applied, custom zoom mode enabled, view updated")
                else:
                    logger.info(f"Zoom rectangle too small ({width:.1f} x {height:.1f}), ignoring")

                # Remove rubber band
                if self.rubber_band_rect:
                    self.scene.removeItem(self.rubber_band_rect)
                    self.rubber_band_rect = None

            self.rubber_band_origin = None
            self.is_rubber_banding = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click to reset zoom to fit."""
        if event.button() == Qt.LeftButton:
            self.zoom_to_fit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def clear(self):
        """Clear the viewer."""
        self.scene.clear()
        self.pixmap_item = None
        self.original_pixmap = None
        self.is_custom_zoom = False  # Reset zoom state


class DateCorrectionsTab(QWidget):
    """Tab for managing and correcting files with unreliable dates."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.db_metadata = None
        self.current_records = []

        # Thumbnail cache (initialized when database is set)
        self.thumbnail_cache = None
        self.grid_model = None
        self.grid_view = None

        # Preview window (created when needed)
        self.preview_window = None

        # Search debounce timer
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.apply_filters)

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Header
        header = QLabel("Date Corrections")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        self.file_count_label = QLabel("Total files with unreliable dates (all import sessions): 0")
        self.file_count_label.setStyleSheet("padding: 5px; color: #666;")
        layout.addWidget(self.file_count_label)

        # Toolbar with thumbnail size and preview window controls
        toolbar_layout = QHBoxLayout()

        # Thumbnail size selector
        toolbar_layout.addWidget(QLabel("Thumbnail Size:"))
        self.thumbnail_size_combo = QComboBox()
        self.thumbnail_size_combo.addItems(["150px", "200px", "300px"])
        self.thumbnail_size_combo.setCurrentText("200px")
        self.thumbnail_size_combo.currentTextChanged.connect(self.on_thumbnail_size_changed)
        toolbar_layout.addWidget(self.thumbnail_size_combo)

        # Preview window button
        self.preview_window_btn = QPushButton("Open Preview Window")
        self.preview_window_btn.setCheckable(True)
        self.preview_window_btn.toggled.connect(self.on_toggle_preview_window)
        toolbar_layout.addWidget(self.preview_window_btn)

        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # Search box
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search filename, path, date, or reason...")
        self.search_box.textChanged.connect(self._on_search_changed)
        self.search_box.setClearButtonEnabled(True)
        search_layout.addWidget(self.search_box)
        layout.addLayout(search_layout)

        # Filter group
        filter_group = QGroupBox("Filter by:")
        filter_layout = QHBoxLayout()

        self.filter_no_exif = QCheckBox("No EXIF")
        self.filter_no_exif.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.filter_no_exif)

        self.filter_year_1000 = QCheckBox("Year 1000")
        self.filter_year_1000.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.filter_year_1000)

        self.filter_suspicious = QCheckBox("Suspicious")
        self.filter_suspicious.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.filter_suspicious)

        self.filter_user_path = QCheckBox("User Path")
        self.filter_user_path.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.filter_user_path)

        # Add separator
        separator = QLabel(" | ")
        separator.setStyleSheet("color: #999;")
        filter_layout.addWidget(separator)

        # Status filters
        self.filter_pending = QCheckBox("Pending")
        self.filter_pending.setChecked(True)  # Default: show pending
        self.filter_pending.setToolTip("Files not yet corrected")
        self.filter_pending.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.filter_pending)

        self.filter_corrected = QCheckBox("Corrected")
        self.filter_corrected.setChecked(True)  # Default: show corrected
        self.filter_corrected.setToolTip("Files corrected but not yet reorganized")
        self.filter_corrected.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.filter_corrected)

        self.filter_reorganized = QCheckBox("Reorganized")
        self.filter_reorganized.setChecked(False)  # Default: hide reorganized
        self.filter_reorganized.setToolTip("Files that have been reorganized (for auditing)")
        self.filter_reorganized.stateChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.filter_reorganized)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Grid view (will be created when database is set)
        # Placeholder for grid_view
        self.grid_view_placeholder = QLabel("Please select a database to view files.")
        self.grid_view_placeholder.setStyleSheet("font-size: 14pt; color: #999; padding: 50px;")
        self.grid_view_placeholder.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.grid_view_placeholder, 1)

        # Selection buttons
        selection_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        selection_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        selection_layout.addWidget(self.deselect_all_btn)

        self.batch_correct_btn = QPushButton("Batch Correct Selected")
        self.batch_correct_btn.clicked.connect(self.on_batch_correct)
        selection_layout.addWidget(self.batch_correct_btn)

        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.manage_paths_btn = QPushButton("Manage Unreliable Paths...")
        self.manage_paths_btn.clicked.connect(self.on_manage_paths)
        button_layout.addWidget(self.manage_paths_btn)

        self.reorganize_btn = QPushButton("Reorganize All Marked")
        self.reorganize_btn.clicked.connect(self.on_reorganize_all)
        button_layout.addWidget(self.reorganize_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def set_database(self, db_metadata):
        """
        Set the database and load unreliable dates.

        Args:
            db_metadata: DatabaseMetadata instance
        """
        self.db_metadata = db_metadata

        # Initialize thumbnail cache
        if self.db_metadata:
            db_dir = os.path.dirname(self.db_metadata.database_path)
            cache_dir = os.path.join(db_dir, '.thumbnails')

            logger.info(f"Initializing thumbnail cache at {cache_dir}")
            self.thumbnail_cache = ThumbnailCache(
                db_path=self.db_metadata.database_path,
                cache_dir=cache_dir,
                memory_size=500,  # 500 items in memory
                disk_size_gb=2,   # 2GB disk cache
                worker_threads=4  # 4 background workers
            )

            # Create grid model
            self.grid_model = UnreliableDatesGridModel(
                self.thumbnail_cache,
                self.db_metadata,
                self
            )

            # Create grid view
            self.grid_view = UnreliableDatesGridView(self.grid_model, self)
            self.grid_view.selection_changed.connect(self.on_grid_selection_changed)
            self.grid_view.item_activated.connect(self.on_grid_item_activated)

            # Replace placeholder with grid view
            layout = self.layout()
            # Find placeholder and replace it
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item and item.widget() == self.grid_view_placeholder:
                    self.grid_view_placeholder.hide()
                    layout.insertWidget(i, self.grid_view, 1)
                    break

            # Load saved thumbnail size
            saved_size = self.db_metadata.get_thumbnail_size()
            size_text = f"{saved_size}px"
            if size_text in ["150px", "200px", "300px"]:
                self.thumbnail_size_combo.setCurrentText(size_text)
                self.grid_view.set_thumbnail_size_pixels(saved_size)
            else:
                # Default to 200px if saved size is not in new range
                self.thumbnail_size_combo.setCurrentText("200px")
                self.grid_view.set_thumbnail_size_pixels(200)

        self.refresh_data()

    def showEvent(self, event):
        """
        Handle tab becoming visible - auto-refresh data and open preview.

        This ensures the grid is always up-to-date when the user
        switches to this tab, and auto-opens the preview window if enabled.
        """
        super().showEvent(event)
        # Only refresh if we have a database connection
        if self.db_metadata:
            self.refresh_data()

            # Auto-open preview window on first visit (if enabled in settings)
            if not self.preview_window and self.db_metadata.get_preview_window_visible():
                self.on_toggle_preview_window(True)

    def refresh_data(self):
        """Reload data from database and refresh grid."""
        if not self.db_metadata:
            if self.grid_model:
                self.grid_model.load_data([])
            self.file_count_label.setText("Total files with unreliable dates (all import sessions): 0")
            return

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)

            # Sync archive paths from UniquePhotos (fixes NULL paths from old processing)
            with profile_block("Sync archive paths from UniquePhotos", logger):
                updated_count = self.db_metadata.sync_archive_paths_from_unique_photos()
                if updated_count > 0:
                    logger.info(f"Synced {updated_count} archive paths from UniquePhotos")

            # Get all unreliable dates
            with profile_block("Database query - get_unreliable_dates", logger):
                self.current_records = self.db_metadata.get_unreliable_dates()

            logger.info(f"📊 Loaded {len(self.current_records)} unreliable date records from database")

            # Update count
            self.file_count_label.setText(
                f"Total files with unreliable dates (all import sessions): {len(self.current_records)}"
            )

            # Apply current filters
            with profile_block("Apply filters and populate grid", logger):
                self.apply_filters()

        except Exception as e:
            logger.error(f"Failed to load unreliable dates: {e}")
            msg_box = QMessageBox(QMessageBox.Critical, "Error", f"Failed to load data:\n\n{str(e)}", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
        finally:
            QApplication.restoreOverrideCursor()

    def _on_search_changed(self):
        """Handle search text change with debouncing."""
        # Stop any existing timer
        self.search_timer.stop()
        # Start new timer (300ms delay)
        self.search_timer.start(300)

    def apply_filters(self):
        """Apply filter checkboxes and search to show/hide rows."""
        if not self.current_records:
            if self.grid_model:
                self.grid_model.load_data([])
            return

        with profile_block("Filter by flag_reason", logger):
            # Get active flag_reason filters
            active_flag_filters = []
            if self.filter_no_exif.isChecked():
                active_flag_filters.append('no_exif')
            if self.filter_year_1000.isChecked():
                active_flag_filters.append('year_1000')
            if self.filter_suspicious.isChecked():
                active_flag_filters.append('suspicious')
            if self.filter_user_path.isChecked():
                active_flag_filters.append('user_specified')

            # Filter by flag_reason if any are checked
            if active_flag_filters:
                filtered_records = [r for r in self.current_records if r['flag_reason'] in active_flag_filters]
            else:
                filtered_records = self.current_records

        with profile_block("Filter by status", logger):
            # Get active status filters
            show_pending = self.filter_pending.isChecked()
            show_corrected = self.filter_corrected.isChecked()
            show_reorganized = self.filter_reorganized.isChecked()

            # Filter by status (OR logic - if none checked, show all)
            status_filtered = []
            any_status_filter_active = show_pending or show_corrected or show_reorganized

            for record in filtered_records:
                if not any_status_filter_active:
                    # No status filters active - show all records
                    status_filtered.append(record)
                else:
                    # OR logic: show if matches ANY checked status
                    is_pending = not record['corrected_date']
                    is_reorganized = record['corrected_date'] and not record['needs_reorganization']
                    is_corrected = record['corrected_date'] and record['needs_reorganization']

                    if (show_pending and is_pending) or \
                       (show_corrected and is_corrected) or \
                       (show_reorganized and is_reorganized):
                        status_filtered.append(record)

        with profile_block("Apply search filter", logger):
            # Apply search filter
            search_text = self.search_box.text().strip().lower() if hasattr(self, 'search_box') else ''
            if search_text:
                search_filtered = []
                for record in status_filtered:
                    # Search across all text fields
                    filename = os.path.basename(record.get('source_path', ''))
                    source_path = record.get('source_path', '')
                    archive_path = record.get('archive_path', '')
                    original_date = record.get('original_date', '')
                    flag_reason = record.get('flag_reason', '')
                    corrected_date = record.get('corrected_date', '')
                    date_source = record.get('date_source', '')

                    # Combine all searchable text
                    searchable_text = ' '.join([
                        filename, source_path, archive_path, original_date,
                        flag_reason, corrected_date or '', date_source
                    ]).lower()

                    if search_text in searchable_text:
                        search_filtered.append(record)

                final_filtered = search_filtered
            else:
                final_filtered = status_filtered

        # Update count label to show filtered vs total
        total_count = len(self.current_records)
        filtered_count = len(final_filtered)
        if search_text or filtered_count != total_count:
            self.file_count_label.setText(
                f"Showing {filtered_count:,} of {total_count:,} files with unreliable dates"
            )
        else:
            self.file_count_label.setText(
                f"Total files with unreliable dates (all import sessions): {total_count:,}"
            )

        # Populate grid
        self.populate_grid(final_filtered)

    def populate_grid(self, records):
        """
        Populate grid with records using high-performance model.

        Args:
            records: List of unreliable date records

        Performance Note:
            Uses QAbstractListModel for lazy loading - only visible items are rendered.
            This is 10-100x faster for large datasets (1000+ records).
        """
        if not self.grid_model:
            logger.warning("Grid model not initialized - skipping populate")
            return

        with profile_block(f"Populate grid with {len(records)} records (via model)", logger):
            # Load data into model - it handles everything efficiently
            self.grid_model.load_data(records)

    def _get_exif_date_for_display(self, record):
        """Get EXIF date for display by reading from file."""
        # First check if file has been corrected - read from archive if available
        file_path = record.get('archive_path') or record.get('source_path')

        if not file_path or not os.path.exists(file_path):
            # Fallback to source path
            file_path = record.get('source_path')
            if not file_path or not os.path.exists(file_path):
                return "None"

        # Try to read EXIF date from the actual file
        try:
            from exif_writer import read_exif_date
            year, month, day = read_exif_date(file_path)
            if year and month and day:
                return f"{year}-{month}-{day}"
        except Exception as e:
            logger.debug(f"Could not read EXIF from {file_path}: {e}")
            pass

        # Fallback to database record if EXIF read fails
        if record['date_source'] == 'exif' and record['original_date']:
            return record['original_date']

        return "None"

    def _get_file_date_for_display(self, record):
        """Get file date (OS metadata) for display."""
        try:
            if os.path.exists(record['source_path']):
                import datetime
                mtime = os.path.getmtime(record['source_path'])
                date = datetime.datetime.fromtimestamp(mtime)
                return date.strftime('%Y-%m-%d')
        except Exception as e:
            logger.warning(f"Failed to get file date for {record.get('source_path', 'unknown')}: {e}")
        return "-"

    def on_grid_selection_changed(self, selected_hashes):
        """
        Handle grid selection change - update preview window.

        Args:
            selected_hashes: List of selected file hashes
        """
        if self.preview_window and selected_hashes:
            # Update preview with first selected item
            record = self.grid_model.get_record_by_hash(selected_hashes[0])
            if record:
                self.preview_window.update_preview(record)

    def on_grid_item_activated(self, record):
        """
        Handle grid item activation (double-click or Space key).

        Opens or focuses the preview window.

        Args:
            record: Activated record dict
        """
        # Open preview window if not open
        if not self.preview_window:
            self.on_toggle_preview_window(True)

        # Update and raise preview window
        if self.preview_window:
            self.preview_window.update_preview(record)
            self.preview_window.raise_()
            self.preview_window.activateWindow()

    def on_thumbnail_size_changed(self, size_text):
        """
        Handle thumbnail size change from combo box.

        Args:
            size_text: Size string like "150px", "200px", or "300px"
        """
        if not self.grid_view:
            return

        size = int(size_text.replace('px', ''))

        # Update grid view
        self.grid_view.set_thumbnail_size_pixels(size)

        # Save to database
        if self.db_metadata:
            self.db_metadata.set_thumbnail_size(size)

        logger.info(f"Thumbnail size changed to {size}px")

    def on_toggle_preview_window(self, checked):
        """
        Toggle preview window open/closed.

        Args:
            checked: True to open, False to close
        """
        if checked:
            # Open preview window
            if not self.preview_window:
                self.preview_window = DetachablePreviewWindow(self.db_metadata, self)
                self.preview_window.window_closed.connect(self._on_preview_window_closed)
                self.preview_window.correct_date_clicked.connect(self._on_preview_correct_date)

            self.preview_window.show()
            self.preview_window_btn.setChecked(True)

            # Update with current selection if any
            if self.grid_view:
                selected_items = self.grid_view.get_selected_items()
                if selected_items:
                    self.preview_window.update_preview(selected_items[0])

            # Save visible state
            if self.db_metadata:
                self.db_metadata.set_preview_window_visible(True)

        else:
            # Close preview window
            if self.preview_window:
                self.preview_window.close()

    def _on_preview_window_closed(self):
        """Handle preview window close event."""
        self.preview_window = None
        self.preview_window_btn.setChecked(False)

        # Save visible state
        if self.db_metadata:
            self.db_metadata.set_preview_window_visible(False)

    def _on_preview_correct_date(self, record):
        """
        Handle correct date button clicked in preview window.

        Args:
            record: Record to correct
        """
        from ui.date_correction_dialog import DateCorrectionDialog

        dialog = DateCorrectionDialog(self, [record], batch_mode=False)
        if dialog.exec():
            self.refresh_data()

    def select_all(self):
        """Select all visible items in grid."""
        if self.grid_view:
            self.grid_view.selectAll()

    def deselect_all(self):
        """Deselect all items in grid."""
        if self.grid_view:
            self.grid_view.clearSelection()

    def get_selected_records(self):
        """Get all selected records from grid."""
        if self.grid_view:
            return self.grid_view.get_selected_items()
        return []

    def on_correct_single_date(self):
        """Handle correct date button for single file."""
        # Get selected items from grid view
        selected_records = self.get_selected_records()
        if not selected_records:
            return

        # Open date correction dialog for first selected record
        from ui.date_correction_dialog import DateCorrectionDialog

        dialog = DateCorrectionDialog(self, [selected_records[0]], batch_mode=False)
        if dialog.exec():
            self.refresh_data()

    def on_batch_correct(self):
        """Handle batch correct button."""
        selected_records = self.get_selected_records()

        if not selected_records:
            msg_box = QMessageBox(QMessageBox.Warning, "No Selection", "Please select files to correct.", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        # Open date correction dialog in batch mode
        from ui.date_correction_dialog import DateCorrectionDialog

        dialog = DateCorrectionDialog(self, selected_records, batch_mode=True)
        if dialog.exec():
            self.refresh_data()

    def on_manage_paths(self):
        """Open manage unreliable paths dialog."""
        if not self.db_metadata:
            msg_box = QMessageBox(QMessageBox.Warning, "No Database", "Please select a database first.", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        from ui.manage_unreliable_paths_dialog import ManageUnreliablePathsDialog

        dialog = ManageUnreliablePathsDialog(self, self.db_metadata)
        dialog.exec()

    def on_reorganize_all(self):
        """Reorganize all files marked for reorganization."""
        if not self.db_metadata:
            msg_box = QMessageBox(QMessageBox.Warning, "No Database", "Please select a database first.", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        # Sync archive paths from UniquePhotos first (fixes NULL paths)
        updated_count = self.db_metadata.sync_archive_paths_from_unique_photos()
        if updated_count > 0:
            logger.info(f"Synced {updated_count} archive paths before reorganization")

        # Get files needing reorganization
        files_to_reorganize = self.db_metadata.get_files_needing_reorganization()

        if not files_to_reorganize:
            msg_box = QMessageBox(
                QMessageBox.Information,
                "No Files to Reorganize",
                "There are no files marked for reorganization.",
                QMessageBox.Ok,
                self
            )
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        # Confirm
        msg_box = QMessageBox(
            QMessageBox.Question,
            "Reorganize Files",
            f"Reorganize {len(files_to_reorganize)} file(s) based on corrected dates?\n\n"
            f"This will:\n"
            f"• Move files to correct date-based folders\n"
            f"• Delete files from old locations\n"
            f"• Update database paths\n\n"
            f"Continue?",
            QMessageBox.Yes | QMessageBox.No,
            self
        )
        msg_box.setDefaultButton(QMessageBox.No)
        self._center_dialog(msg_box)
        response = msg_box.exec()

        if response == QMessageBox.Yes:
            # Import and run reorganization
            from ui.reorganize_worker import reorganize_files

            success, failed = reorganize_files(self, self.db_metadata, files_to_reorganize)

            # Show results
            if failed:
                msg_box = QMessageBox(
                    QMessageBox.Warning,
                    "Reorganization Complete with Errors",
                    f"Successfully reorganized: {success} file(s)\n"
                    f"Failed: {failed} file(s)\n\n"
                    f"Check logs for details.",
                    QMessageBox.Ok,
                    self
                )
                self._center_dialog(msg_box)
                msg_box.exec()
            else:
                msg_box = QMessageBox(
                    QMessageBox.Information,
                    "Reorganization Complete",
                    f"Successfully reorganized {success} file(s)!",
                    QMessageBox.Ok,
                    self
                )
                self._center_dialog(msg_box)
                msg_box.exec()

            # Refresh display
            self.refresh_data()

    def _center_dialog(self, dialog):
        """Center a dialog on the main application window."""
        parent = self.parent()
        if parent:
            # Get the top-level window
            main_window = parent.window()
            if main_window:
                # Force dialog to process geometry
                dialog.adjustSize()

                # Get geometries
                parent_geo = main_window.frameGeometry()
                dialog_geo = dialog.frameGeometry()

                # Calculate center position
                x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
                y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2

                # Move dialog to center
                dialog.move(x, y)
