"""
Date Corrections Tab

Displays files with unreliable date information in a sortable grid.
Allows users to review, preview, and correct file dates.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QCheckBox, QMessageBox,
                               QLineEdit, QApplication, QComboBox, QDialog,
                               QTextBrowser, QAbstractItemView, QProgressDialog)
from PySide6.QtCore import Qt, Signal, QTimer
import os
import logging
from typing import List, Dict, Any, Optional

# Import profiling utilities
from utils import profile_block

# Import unified preview component
from ui.preview import ZoomableImageViewer

# Import grid components
from ui.unreliable_dates_grid_model import UnreliableDatesGridModel
from ui.unreliable_dates_grid_view import UnreliableDatesGridView
from ui.detachable_preview_window import DetachablePreviewWindow

# Import triage thumbnail cache
from triage.thumbnail_cache import ThumbnailCache

logger = logging.getLogger(__name__)


class DateCorrectionsHelpDialog(QDialog):
    """Help dialog showing available actions and keyboard shortcuts."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Date Corrections - Keyboard Shortcuts & Actions")
        self.setMinimumSize(700, 600)

        layout = QVBoxLayout()

        # Create text browser for rich text display
        help_text = QTextBrowser()
        help_text.setOpenExternalLinks(False)
        help_text.setHtml(self._get_help_html())
        layout.addWidget(help_text)

        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_btn.setDefault(True)
        layout.addWidget(close_btn)

        self.setLayout(layout)

    def _get_help_html(self) -> str:
        """Generate HTML help content."""
        return """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; margin: 10px; }
                h2 { color: #2c5aa0; border-bottom: 2px solid #2c5aa0; padding-bottom: 5px; }
                h3 { color: #4a7ac4; margin-top: 15px; margin-bottom: 5px; }
                table { width: 100%; border-collapse: collapse; margin: 10px 0; }
                th { background-color: #e8f0f8; text-align: left; padding: 8px; border: 1px solid #ccc; }
                td { padding: 8px; border: 1px solid #ccc; }
                .key {
                    font-family: 'Courier New', monospace;
                    background-color: #f0f0f0;
                    padding: 2px 6px;
                    border: 1px solid #999;
                    border-radius: 3px;
                    font-weight: bold;
                }
                .action { font-weight: bold; color: #333; }
                .section { margin-bottom: 20px; }
            </style>
        </head>
        <body>
            <h2>Date Corrections Tab - Quick Reference</h2>

            <div class="section">
                <h3>Grid Navigation</h3>
                <table>
                    <tr>
                        <th width="35%">Keyboard Shortcut</th>
                        <th>Action</th>
                    </tr>
                    <tr>
                        <td><span class="key">↑</span> <span class="key">↓</span> <span class="key">←</span> <span class="key">→</span></td>
                        <td>Navigate between thumbnails</td>
                    </tr>
                    <tr>
                        <td><span class="key">Ctrl</span> + Click</td>
                        <td>Add/remove item to/from selection</td>
                    </tr>
                    <tr>
                        <td><span class="key">Shift</span> + Click</td>
                        <td>Select range of items</td>
                    </tr>
                    <tr>
                        <td><span class="key">Ctrl</span> + <span class="key">A</span></td>
                        <td>Select all visible items</td>
                    </tr>
                    <tr>
                        <td><span class="key">Escape</span></td>
                        <td>Clear selection</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h3>Thumbnail Size</h3>
                <table>
                    <tr>
                        <th width="35%">Keyboard Shortcut</th>
                        <th>Action</th>
                    </tr>
                    <tr>
                        <td><span class="key">1</span></td>
                        <td>Small thumbnails (150px)</td>
                    </tr>
                    <tr>
                        <td><span class="key">2</span></td>
                        <td>Medium thumbnails (200px) - Default</td>
                    </tr>
                    <tr>
                        <td><span class="key">3</span></td>
                        <td>Large thumbnails (300px)</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h3>Preview & Actions</h3>
                <table>
                    <tr>
                        <th width="35%">Keyboard Shortcut</th>
                        <th>Action</th>
                    </tr>
                    <tr>
                        <td><span class="key">Space</span></td>
                        <td>Open/focus preview window for selected item</td>
                    </tr>
                    <tr>
                        <td><span class="key">Double-Click</span></td>
                        <td>Open/focus preview window for clicked item</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h3>Preview Window (when open)</h3>
                <table>
                    <tr>
                        <th width="35%">Mouse Action</th>
                        <th>Effect</th>
                    </tr>
                    <tr>
                        <td>Click and drag on image</td>
                        <td>Select region to zoom into (rubber band zoom)</td>
                    </tr>
                    <tr>
                        <td><span class="key">Double-Click</span> on image</td>
                        <td>Reset zoom to fit-to-view</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h3>Button Actions</h3>
                <table>
                    <tr>
                        <th width="35%">Button</th>
                        <th>Description</th>
                    </tr>
                    <tr>
                        <td class="action">Select All</td>
                        <td>Select all filtered items in the grid</td>
                    </tr>
                    <tr>
                        <td class="action">Deselect All</td>
                        <td>Clear all selections</td>
                    </tr>
                    <tr>
                        <td class="action">Batch Correct Selected</td>
                        <td>Open dialog to correct dates for multiple selected files<br/>
                        Options: Same date for all, or sequential dates (auto-increment by 1 day)</td>
                    </tr>
                    <tr>
                        <td class="action">Manage Unreliable Paths...</td>
                        <td>Add/remove folder paths that should be automatically flagged during import<br/>
                        Example: Scanner output folders, legacy photo directories</td>
                    </tr>
                    <tr>
                        <td class="action">Reorganize All Marked</td>
                        <td>Move all corrected files to their correct date-based folders<br/>
                        Uses current organization template and corrected dates</td>
                    </tr>
                    <tr>
                        <td class="action">Open Preview Window</td>
                        <td>Open/close the detachable preview window<br/>
                        Window position and size are saved per database</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h3>Filters</h3>
                <table>
                    <tr>
                        <th width="35%">Filter Type</th>
                        <th>Description</th>
                    </tr>
                    <tr>
                        <td class="action">Flag Reason Filters</td>
                        <td><strong>No EXIF:</strong> Image has no EXIF metadata<br/>
                        <strong>Year 1000:</strong> All date extraction methods failed<br/>
                        <strong>Suspicious:</strong> Date before 1990, future date, or Unix epoch<br/>
                        <strong>User Path:</strong> File from user-specified unreliable folder</td>
                    </tr>
                    <tr>
                        <td class="action">Status Filters</td>
                        <td><strong>Pending:</strong> Not yet corrected (default: shown)<br/>
                        <strong>Corrected:</strong> Date corrected, waiting for reorganization (default: shown)<br/>
                        <strong>Reorganized:</strong> File moved to correct folder (default: hidden)</td>
                    </tr>
                    <tr>
                        <td class="action">Search Box</td>
                        <td>Filter by filename, path, date, or flag reason<br/>
                        Updates as you type (300ms debounce)</td>
                    </tr>
                </table>
            </div>

            <div class="section">
                <h3>Workflow Tips</h3>
                <ul>
                    <li><strong>Review flagged files:</strong> Use filters to focus on specific issues (e.g., "No EXIF" files)</li>
                    <li><strong>Batch corrections:</strong> Select multiple files from same event and correct together</li>
                    <li><strong>Sequential dates:</strong> Use batch correct with sequential mode for vacation photos or scanned albums</li>
                    <li><strong>Preview before correcting:</strong> Use Space or double-click to verify the correct date</li>
                    <li><strong>Two-phase reorganization:</strong> Correct dates first, then reorganize all at once</li>
                    <li><strong>Monitor progress:</strong> Check "Corrected" filter to see files waiting for reorganization</li>
                </ul>
            </div>

            <div class="section">
                <h3>Status Colors (in grid)</h3>
                <table>
                    <tr>
                        <th width="35%">Color</th>
                        <th>Meaning</th>
                    </tr>
                    <tr>
                        <td style="color: #888;">Gray/No overlay</td>
                        <td>Pending - not yet corrected</td>
                    </tr>
                    <tr>
                        <td style="color: #009600; font-weight: bold;">Green overlay</td>
                        <td>Corrected - date fixed, needs reorganization</td>
                    </tr>
                    <tr>
                        <td style="color: #3296ff; font-weight: bold;">Blue overlay</td>
                        <td>Reorganized - file moved to correct folder</td>
                    </tr>
                </table>
            </div>
        </body>
        </html>
        """


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

        # Help button
        help_btn = QPushButton("Help")
        help_btn.setToolTip("Show keyboard shortcuts and available actions")
        help_btn.clicked.connect(self.show_help)
        toolbar_layout.addWidget(help_btn)

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

        self.rotate_btn = QPushButton("Rotate Selected...")
        self.rotate_btn.clicked.connect(self.on_rotate_selected)
        self.rotate_btn.setEnabled(False)
        selection_layout.addWidget(self.rotate_btn)

        self.delete_btn = QPushButton("Delete Selected...")
        self.delete_btn.clicked.connect(self.on_delete_selected)
        self.delete_btn.setEnabled(False)
        selection_layout.addWidget(self.delete_btn)

        selection_layout.addStretch()
        layout.addLayout(selection_layout)

        # Bottom buttons
        button_layout = QHBoxLayout()

        self.manage_paths_btn = QPushButton("Manage Unreliable Paths...")
        self.manage_paths_btn.clicked.connect(self.on_manage_paths)
        button_layout.addWidget(self.manage_paths_btn)

        self.view_deleted_btn = QPushButton("View Deleted Files...")
        self.view_deleted_btn.clicked.connect(self.on_view_deleted_files)
        button_layout.addWidget(self.view_deleted_btn)

        self.reorganize_btn = QPushButton("Reorganize All Marked")
        self.reorganize_btn.clicked.connect(self.on_reorganize_all)
        button_layout.addWidget(self.reorganize_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Status bar at bottom
        self.status_label = QLabel("Total: 0 thumbnails | Selected: 0")
        self.status_label.setStyleSheet("padding: 5px; color: #666; border-top: 1px solid #ddd;")
        layout.addWidget(self.status_label)

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

            # Get cache settings from database (user-configurable)
            cache_memory_mb = self.db_metadata.get_cache_memory_mb()
            worker_threads = self.db_metadata.get_cache_worker_threads()

            # Calculate number of items from MB (assuming ~150KB per thumbnail)
            memory_items = int((cache_memory_mb * 1024 * 1024) / (150 * 1024))

            logger.info(f"Initializing thumbnail cache at {cache_dir}")
            logger.info(f"  Cache memory: {cache_memory_mb}MB (~{memory_items:,} items)")
            logger.info(f"  Worker threads: {worker_threads}")

            self.thumbnail_cache = ThumbnailCache(
                db_path=self.db_metadata.database_path,
                cache_dir=cache_dir,
                memory_size=memory_items,  # Calculated from MB setting
                disk_size_gb=5,            # 5GB disk cache
                worker_threads=worker_threads  # User-configurable
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

            # Connect context menu signals
            self.grid_view.correct_date_requested.connect(self.on_batch_correct)
            self.grid_view.reorganize_corrected_requested.connect(self.on_reorganize_all)
            self.grid_view.deselect_all_requested.connect(self.deselect_all)
            self.grid_view.rotate_requested.connect(self.on_rotate_selected)
            self.grid_view.delete_requested.connect(self.on_delete_selected)
            self.grid_view.refresh_thumbnail_requested.connect(self.on_refresh_thumbnail)

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

            # Block signals while setting initial value to avoid triggering save
            self.thumbnail_size_combo.blockSignals(True)

            if size_text in ["150px", "200px", "300px"]:
                self.thumbnail_size_combo.setCurrentText(size_text)
                self.grid_view.set_thumbnail_size_pixels(saved_size)
                logger.info(f"Loaded saved thumbnail size: {saved_size}px")
            else:
                # Default to 200px if saved size is not in new range
                self.thumbnail_size_combo.setCurrentText("200px")
                self.grid_view.set_thumbnail_size_pixels(200)
                logger.info(f"Using default thumbnail size: 200px (saved was {saved_size}px)")

            # Unblock signals
            self.thumbnail_size_combo.blockSignals(False)

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

            # Update status label with total count
            self._update_status_label()

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
        Handle grid selection change - update preview window and button states.

        Args:
            selected_hashes: List of selected file hashes
        """
        has_selection = len(selected_hashes) > 0

        # Enable/disable action buttons based on selection
        self.rotate_btn.setEnabled(has_selection)
        self.delete_btn.setEnabled(has_selection)

        if self.preview_window and selected_hashes:
            # Update preview with first selected item
            record = self.grid_model.get_record_by_hash(selected_hashes[0])
            if record:
                self.preview_window.update_preview(record)

        # Update status label with selected count
        self._update_status_label()

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

    def on_rotate_selected(self):
        """Handle rotation of selected images."""
        selected_records = self.get_selected_records()

        if not selected_records:
            QMessageBox.warning(self, "No Selection",
                              "Please select one or more files to rotate.")
            return

        # Validate all files have archive paths
        missing_archive = [r for r in selected_records if not r.get('archive_path')]
        if missing_archive:
            QMessageBox.warning(self, "Invalid Selection",
                              f"{len(missing_archive)} file(s) have no archive path.")
            return

        # Store original hashes to invalidate thumbnails after rotation
        original_hashes = [r.get('file_hash') for r in selected_records if r.get('file_hash')]

        # CRITICAL: Store first selected item's file_hash to restore scroll position after refresh
        # After rotation, hash changes, so we need to store the archive_path instead
        first_selected_path = selected_records[0].get('archive_path') if selected_records else None

        # Open rotation dialog
        from ui.rotate_image_dialog import RotateImageDialog
        dialog = RotateImageDialog(self, selected_records, self.db_metadata, logger)
        self._center_dialog(dialog)

        if dialog.exec():
            # Invalidate old thumbnail cache entries (hash changed after rotation)
            if self.thumbnail_cache:
                for old_hash in original_hashes:
                    self.thumbnail_cache.invalidate_hash(old_hash)
                logger.info(f"Invalidated {len(original_hashes)} old thumbnail cache entries")

            # Refresh data
            self.refresh_data()

            # Restore scroll position to show rotated item
            if first_selected_path and self.grid_view and self.grid_model:
                # Find the item by archive_path (path doesn't change, only hash changes)
                for row in range(self.grid_model.rowCount()):
                    record = self.grid_model.get_record(row)
                    if record and record.get('archive_path') == first_selected_path:
                        # Scroll to this item and select it
                        index = self.grid_model.index(row, 0)
                        self.grid_view.scrollTo(index, QAbstractItemView.PositionAtCenter)
                        self.grid_view.setCurrentIndex(index)
                        logger.info(f"Restored scroll position to row {row} after rotation")
                        break

    def on_delete_selected(self):
        """Handle deletion of selected images to Delete Vault."""
        selected_records = self.get_selected_records()

        if not selected_records:
            QMessageBox.warning(self, "No Selection",
                              "Please select one or more files to delete.")
            return

        # Check Delete Vault is configured
        delete_vault = self.db_metadata.get_delete_vault_location()
        if not delete_vault or not os.path.exists(delete_vault):
            QMessageBox.critical(self, "Delete Vault Not Configured",
                               "Please configure the Delete Vault location in System Settings.")
            return

        # Confirmation dialog with risk assessment
        count = len(selected_records)
        reply = QMessageBox.question(
            self, "Confirm Deletion",
            f"Delete {count} file(s) to Delete Vault?\n\n"
            f"Files will be moved to: {delete_vault}\n"
            f"You can restore them later from the Deleted Files dialog.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Create and start deletion worker
        from ui.delete_worker import DeleteWorker

        self.delete_worker = DeleteWorker(
            selected_records,
            delete_vault,
            self.db_metadata.database_path,
            logger
        )

        # Show progress dialog
        progress_dialog = QProgressDialog(
            "Deleting files...", "Cancel", 0, count, self
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)

        self.delete_worker.progress.connect(
            lambda cur, total, fname: progress_dialog.setValue(cur)
        )
        self.delete_worker.finished.connect(
            lambda results: self._on_delete_finished(results, progress_dialog)
        )

        self.delete_worker.start()

    def _on_delete_finished(self, results, progress_dialog):
        """Handle deletion completion."""
        progress_dialog.close()

        success_count = results.get('success', 0)
        errors = results.get('errors', [])

        if errors:
            error_msg = "\n".join([f"- {e}" for e in errors[:10]])
            QMessageBox.warning(
                self, "Deletion Complete with Errors",
                f"Successfully deleted: {success_count}\n"
                f"Failed: {len(errors)}\n\n"
                f"First errors:\n{error_msg}"
            )

        self.refresh_data()

    def on_view_deleted_files(self):
        """Open dialog to view and restore deleted files."""
        # Check Delete Vault is configured
        delete_vault = self.db_metadata.get_delete_vault_location()
        if not delete_vault:
            QMessageBox.information(
                self, "No Delete Vault",
                "Delete Vault is not configured. No files have been deleted yet."
            )
            return

        from ui.deleted_files_dialog import DeletedFilesDialog
        dialog = DeletedFilesDialog(self, self.db_metadata, logger)
        self._center_dialog(dialog)
        dialog.exec()

        # Refresh in case files were restored
        self.refresh_data()

    def on_refresh_thumbnail(self):
        """Manually refresh thumbnails for selected images."""
        selected_records = self.get_selected_records()

        if not selected_records:
            QMessageBox.warning(self, "No Selection",
                              "Please select one or more files to refresh thumbnails.")
            return

        if not self.thumbnail_cache:
            QMessageBox.warning(self, "Cache Not Available",
                              "Thumbnail cache is not initialized.")
            return

        try:
            # Store first selected item's hash to restore scroll position after refresh
            first_selected_hash = selected_records[0].get('file_hash') if selected_records else None

            # Invalidate cache entries for all selected files
            invalidated_count = 0
            for record in selected_records:
                file_hash = record.get('file_hash')
                if file_hash:
                    self.thumbnail_cache.invalidate_hash(file_hash)
                    invalidated_count += 1

            logger.info(f"Invalidated {invalidated_count} thumbnail cache entries")

            # Force grid to refresh - this will trigger regeneration of thumbnails
            if self.grid_model:
                # Use beginResetModel/endResetModel to force complete view refresh
                self.grid_model.beginResetModel()
                self.grid_model.endResetModel()

            # Restore scroll position to show refreshed item
            if first_selected_hash and self.grid_view and self.grid_model:
                # Find the item by file_hash (hash doesn't change for refresh)
                for row in range(self.grid_model.rowCount()):
                    record = self.grid_model.get_record(row)
                    if record and record.get('file_hash') == first_selected_hash:
                        # Scroll to this item and select it
                        index = self.grid_model.index(row, 0)
                        self.grid_view.scrollTo(index, QAbstractItemView.PositionAtCenter)
                        self.grid_view.setCurrentIndex(index)
                        logger.info(f"Restored scroll position to row {row} after thumbnail refresh")
                        break

            # Show confirmation
            QMessageBox.information(
                self, "Thumbnails Refreshed",
                f"Invalidated {invalidated_count} thumbnail(s).\n"
                f"Thumbnails will be regenerated in the background."
            )

        except Exception as e:
            logger.error(f"Error refreshing thumbnails: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Refresh Failed",
                f"Failed to refresh thumbnails: {str(e)}"
            )

    def _update_status_label(self):
        """Update the status label with total and selected counts."""
        try:
            # Get total count from grid model
            total_count = 0
            if self.grid_model:
                total_count = self.grid_model.rowCount()

            # Get selected count from grid view
            selected_count = 0
            if self.grid_view:
                selected_indices = self.grid_view.selectedIndexes()
                selected_count = len(selected_indices)

            # Update label
            self.status_label.setText(
                f"Total: {total_count:,} thumbnails | Selected: {selected_count:,}"
            )

        except Exception as e:
            logger.error(f"Failed to update status label: {e}", exc_info=True)

    def show_help(self):
        """Show keyboard shortcuts and available actions help dialog."""
        try:
            help_dialog = DateCorrectionsHelpDialog(self)
            self._center_dialog(help_dialog)
            help_dialog.exec()
        except Exception as e:
            logger.error(f"Failed to show help dialog: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Help Error",
                f"Failed to display help dialog: {e}"
            )

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
