"""
Date Corrections Tab

Displays files with unreliable date information in a sortable grid.
Allows users to review, preview, and correct file dates.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QGroupBox, QCheckBox, QMessageBox,
                               QSplitter, QAbstractItemView, QGraphicsView,
                               QGraphicsScene, QGraphicsPixmapItem)
from PySide6.QtCore import Qt, Signal, QRectF, QPointF
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor
from PIL import Image
import os
import logging

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
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Header
        header = QLabel("Date Corrections")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        self.file_count_label = QLabel("Files with unreliable date information: 0")
        self.file_count_label.setStyleSheet("padding: 5px; color: #666;")
        layout.addWidget(self.file_count_label)

        # Create main splitter for table and preview
        splitter = QSplitter(Qt.Horizontal)

        # Left side: Table and filters
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)

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
        left_layout.addWidget(filter_group)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "", "Filename", "Source Location", "Archive Location",
            "Detected Date", "EXIF Date", "File Date", "Flag Reason", "Status"
        ])

        # Configure table
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Supports Shift/Ctrl selection
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Checkbox
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Filename
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Source
        header.setSectionResizeMode(3, QHeaderView.Stretch)  # Archive
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Detected Date
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # EXIF Date
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # File Date
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Flag Reason
        header.setSectionResizeMode(8, QHeaderView.ResizeToContents)  # Status

        self.table.setColumnWidth(0, 30)  # Checkbox column

        # Connect selection change and double-click
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.itemDoubleClicked.connect(self.on_item_double_clicked)

        left_layout.addWidget(self.table)

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
        left_layout.addLayout(selection_layout)

        left_widget.setLayout(left_layout)
        splitter.addWidget(left_widget)

        # Right side: Preview panel
        preview_widget = QWidget()
        preview_layout = QVBoxLayout()

        preview_header = QLabel("Preview (drag to zoom, double-click to reset)")
        preview_header.setStyleSheet("font-weight: bold; font-size: 14px;")
        preview_layout.addWidget(preview_header)

        # Image preview with zoom capabilities
        self.preview_viewer = ZoomableImageViewer()
        self.preview_viewer.setMinimumSize(300, 300)
        preview_layout.addWidget(self.preview_viewer, 1)

        # File details
        details_group = QGroupBox("File Details")
        details_layout = QVBoxLayout()

        self.detail_filename = QLabel("Filename: -")
        self.detail_filename.setWordWrap(True)
        details_layout.addWidget(self.detail_filename)

        self.detail_source = QLabel("Source: -")
        self.detail_source.setWordWrap(True)
        details_layout.addWidget(self.detail_source)

        self.detail_archive = QLabel("Archive: -")
        self.detail_archive.setWordWrap(True)
        details_layout.addWidget(self.detail_archive)

        self.detail_detected = QLabel("Detected Date: -")
        details_layout.addWidget(self.detail_detected)

        self.detail_exif = QLabel("EXIF Date: -")
        details_layout.addWidget(self.detail_exif)

        self.detail_file_date = QLabel("File Date: -")
        details_layout.addWidget(self.detail_file_date)

        self.detail_reason = QLabel("Reason: -")
        details_layout.addWidget(self.detail_reason)

        self.detail_status = QLabel("Status: -")
        details_layout.addWidget(self.detail_status)

        details_group.setLayout(details_layout)
        preview_layout.addWidget(details_group)

        # Correct date button
        self.correct_date_btn = QPushButton("Correct Date...")
        self.correct_date_btn.setMinimumHeight(35)
        self.correct_date_btn.clicked.connect(self.on_correct_single_date)
        self.correct_date_btn.setEnabled(False)
        preview_layout.addWidget(self.correct_date_btn)

        preview_widget.setLayout(preview_layout)
        splitter.addWidget(preview_widget)

        # Set splitter sizes (table gets 60%, preview gets 40%)
        splitter.setSizes([600, 400])

        layout.addWidget(splitter, 1)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.manage_paths_btn = QPushButton("Manage Unreliable Paths...")
        self.manage_paths_btn.clicked.connect(self.on_manage_paths)
        button_layout.addWidget(self.manage_paths_btn)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_data)
        button_layout.addWidget(self.refresh_btn)

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
        self.refresh_data()

    def refresh_data(self):
        """Reload data from database and refresh table."""
        if not self.db_metadata:
            self.table.setRowCount(0)
            self.file_count_label.setText("Files with unreliable date information: 0")
            return

        try:
            # Sync archive paths from UniquePhotos (fixes NULL paths from old processing)
            updated_count = self.db_metadata.sync_archive_paths_from_unique_photos()
            if updated_count > 0:
                logger.info(f"Synced {updated_count} archive paths from UniquePhotos")

            # Get all unreliable dates
            self.current_records = self.db_metadata.get_unreliable_dates()

            # Update count
            self.file_count_label.setText(
                f"Files with unreliable date information: {len(self.current_records)}"
            )

            # Apply current filters
            self.apply_filters()

        except Exception as e:
            logger.error(f"Failed to load unreliable dates: {e}")
            msg_box = QMessageBox(QMessageBox.Critical, "Error", f"Failed to load data:\n\n{str(e)}", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()

    def apply_filters(self):
        """Apply filter checkboxes to show/hide rows."""
        if not self.current_records:
            self.table.setRowCount(0)
            return

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

        # Get active status filters
        show_pending = self.filter_pending.isChecked()
        show_corrected = self.filter_corrected.isChecked()
        show_reorganized = self.filter_reorganized.isChecked()

        # Filter by status
        status_filtered = []
        for record in filtered_records:
            is_pending = not record['corrected_date']
            is_reorganized = record['corrected_date'] and not record['needs_reorganization']
            is_corrected = record['corrected_date'] and record['needs_reorganization']

            if (show_pending and is_pending) or \
               (show_corrected and is_corrected) or \
               (show_reorganized and is_reorganized):
                status_filtered.append(record)

        # Populate table
        self.populate_table(status_filtered)

    def populate_table(self, records):
        """
        Populate table with records.

        Args:
            records: List of unreliable date records
        """
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(records))

        for row, record in enumerate(records):
            # Checkbox
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            checkbox.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, checkbox)

            # Filename
            filename = os.path.basename(record['source_path'])
            filename_item = QTableWidgetItem(filename)
            filename_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, filename_item)

            # Source location (truncated with tooltip)
            source_item = QTableWidgetItem(self._truncate_path(record['source_path'], 50))
            source_item.setToolTip(record['source_path'])
            source_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 2, source_item)

            # Archive location
            archive_path = record['archive_path'] or "Not yet organized"
            archive_item = QTableWidgetItem(self._truncate_path(archive_path, 50))
            archive_item.setToolTip(archive_path)
            archive_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 3, archive_item)

            # Detected date
            detected_item = QTableWidgetItem(record['original_date'] or "-")
            detected_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 4, detected_item)

            # EXIF date (read from file if possible)
            exif_date = self._get_exif_date_for_display(record)
            exif_item = QTableWidgetItem(exif_date)
            exif_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 5, exif_item)

            # File date (OS metadata)
            file_date = self._get_file_date_for_display(record)
            file_date_item = QTableWidgetItem(file_date)
            file_date_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 6, file_date_item)

            # Flag reason
            reason_text = record['flag_reason'].replace('_', ' ').title()
            reason_item = QTableWidgetItem(reason_text)
            reason_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 7, reason_item)

            # Status
            if record['corrected_date']:
                if record['needs_reorganization']:
                    status = f"Corrected: {record['corrected_date']}"
                    status_item = QTableWidgetItem(status)
                    status_item.setForeground(Qt.darkGreen)
                else:
                    status = f"Reorganized: {record['corrected_date']}"
                    status_item = QTableWidgetItem(status)
                    status_item.setForeground(Qt.blue)
            else:
                status = "Pending"
                status_item = QTableWidgetItem(status)
                status_item.setForeground(Qt.darkGray)
            status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 8, status_item)

            # Store record data in first column for later retrieval
            self.table.item(row, 1).setData(Qt.UserRole, record)

        self.table.setSortingEnabled(True)

    def _truncate_path(self, path, max_length):
        """Truncate path for display."""
        if len(path) <= max_length:
            return path
        return "..." + path[-(max_length-3):]

    def _get_exif_date_for_display(self, record):
        """Get EXIF date for display in table."""
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
        except:
            pass
        return "-"

    def on_selection_changed(self):
        """Handle table row selection change."""
        selected_rows = self.table.selectionModel().selectedRows()

        if not selected_rows:
            self.preview_viewer.clear()
            self.detail_filename.setText("Filename: -")
            self.detail_source.setText("Source: -")
            self.detail_archive.setText("Archive: -")
            self.detail_detected.setText("Detected Date: -")
            self.detail_exif.setText("EXIF Date: -")
            self.detail_file_date.setText("File Date: -")
            self.detail_reason.setText("Reason: -")
            self.detail_status.setText("Status: -")
            self.correct_date_btn.setEnabled(False)
            return

        # Get selected record
        row = selected_rows[0].row()
        record = self.table.item(row, 1).data(Qt.UserRole)

        # Update preview image
        self.load_preview(record['source_path'])

        # Update details
        self.detail_filename.setText(f"Filename: {os.path.basename(record['source_path'])}")
        self.detail_source.setText(f"Source: {record['source_path']}")

        # Show archive location (with original if reorganized)
        if record.get('original_archive_path') and record['archive_path'] != record['original_archive_path']:
            archive_text = f"Archive: {record['archive_path']}\nOriginal: {record['original_archive_path']}"
        else:
            archive_text = f"Archive: {record['archive_path'] or 'Not yet organized'}"
        self.detail_archive.setText(archive_text)

        self.detail_detected.setText(f"Detected Date: {record['original_date'] or '-'}")
        self.detail_exif.setText(f"EXIF Date: {self._get_exif_date_for_display(record)}")
        self.detail_file_date.setText(f"File Date: {self._get_file_date_for_display(record)}")
        self.detail_reason.setText(f"Reason: {record['flag_reason'].replace('_', ' ').title()}")

        if record['corrected_date']:
            if record['needs_reorganization']:
                status_text = f"Corrected to: {record['corrected_date']} (Needs reorganization)"
            else:
                status_text = f"Reorganized to: {record['corrected_date']}"
        else:
            status_text = "Pending correction"
        self.detail_status.setText(f"Status: {status_text}")

        self.correct_date_btn.setEnabled(True)

    def on_item_double_clicked(self, item):
        """Handle double-click on table item - toggle checkbox."""
        if item is None:
            return

        row = item.row()
        checkbox_item = self.table.item(row, 0)

        if checkbox_item:
            # Toggle checkbox state
            current_state = checkbox_item.checkState()
            new_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
            checkbox_item.setCheckState(new_state)

    def load_preview(self, file_path):
        """Load and display image preview with zoom capabilities."""
        try:
            if not os.path.exists(file_path):
                self.preview_viewer.clear()
                return

            # Load image using the zoomable viewer
            self.preview_viewer.load_image(file_path)

        except Exception as e:
            logger.error(f"Failed to load preview for {file_path}: {e}")
            self.preview_viewer.clear()

    def select_all(self):
        """Select all visible rows."""
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.Checked)

    def deselect_all(self):
        """Deselect all rows."""
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(Qt.Unchecked)

    def get_selected_records(self):
        """Get all checked records."""
        selected = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.Checked:
                record = self.table.item(row, 1).data(Qt.UserRole)
                selected.append(record)
        return selected

    def on_correct_single_date(self):
        """Handle correct date button for single file."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return

        row = selected_rows[0].row()
        record = self.table.item(row, 1).data(Qt.UserRole)

        # Open date correction dialog
        from ui.date_correction_dialog import DateCorrectionDialog

        dialog = DateCorrectionDialog(self, [record], batch_mode=False)
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
        """Center a dialog on the main window."""
        if self.parent():
            parent_geo = self.parent().geometry()
            dialog_geo = dialog.geometry()
            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2
            dialog.move(x, y)
