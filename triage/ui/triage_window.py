"""
Triage Main Window

Main application window for photo triage tool.
Combines folder browser, thumbnail grid, and preview pane.
"""

import logging
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QSplitter, QToolBar, QStatusBar, QLabel,
                               QPushButton, QMessageBox, QFileDialog, QComboBox)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence

from database_metadata import DatabaseMetadata
from ui.database_selector_dialog import DatabaseSelectorDialog
from triage.triage_config import TriageConfig
from triage.triage_database import TriageDatabase
from triage.thumbnail_cache import ThumbnailCache
from triage.ui.thumbnail_grid_model import ThumbnailGridModel
from triage.ui.thumbnail_grid_view import ThumbnailGridView
from triage.ui.folder_browser import FolderBrowser
from triage.ui.preview_pane import PreviewPane
from triage.ui.cache_stats_dialog import CacheStatsDialog

logger = logging.getLogger(__name__)


class TriageWindow(QMainWindow):
    """
    Main triage application window.

    Layout:
    ┌─────────────────────────────────────────────────────────┐
    │  [Database ▼] [Folder: /archive/2025/]  [Stats]         │
    ├────────────┬────────────────────────────────────────────┤
    │  Folders   │     Thumbnail Grid                         │
    │  ├─ 2025/  │     (virtual scrolling)                    │
    │  │  ├─01/  │                                            │
    │  │  ├─02/  │                                            │
    │  │  └─03/  │                                            │
    ├────────────┴────────────────────────────────────────────┤
    │  Preview Pane (large image + metadata)                  │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self):
        super().__init__()

        # Load configuration
        self.config = TriageConfig.load()

        # Initialize cache (will be set when database is selected)
        self.thumbnail_cache = None
        self.grid_model = None
        self.current_db_path = None
        self.current_archive_path = None

        self.setWindowTitle("Photo Triage - PyPhotoOrganizer")
        self.resize(1600, 1000)

        # Create UI
        self._create_menu_bar()
        self._create_toolbar()
        self._create_central_widget()
        self._create_status_bar()

        # Load last used database if available
        self._load_last_database()

        logger.info("Triage window initialized")

    def _create_menu_bar(self):
        """Create menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        open_db_action = QAction("&Open Database...", self)
        open_db_action.setShortcut(QKeySequence.Open)
        open_db_action.triggered.connect(self._select_database)
        file_menu.addAction(open_db_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        small_action = QAction("&Small Thumbnails", self)
        small_action.setShortcut(Qt.Key_1)
        small_action.triggered.connect(lambda: self._set_grid_size('small'))
        view_menu.addAction(small_action)

        medium_action = QAction("&Medium Thumbnails", self)
        medium_action.setShortcut(Qt.Key_2)
        medium_action.triggered.connect(lambda: self._set_grid_size('medium'))
        view_menu.addAction(medium_action)

        large_action = QAction("&Large Thumbnails", self)
        large_action.setShortcut(Qt.Key_3)
        large_action.triggered.connect(lambda: self._set_grid_size('large'))
        view_menu.addAction(large_action)

        view_menu.addSeparator()

        cache_stats_action = QAction("Cache &Statistics...", self)
        cache_stats_action.triggered.connect(self._show_cache_stats)
        view_menu.addAction(cache_stats_action)

        # Actions menu
        actions_menu = menubar.addMenu("&Actions")

        # Batch operations submenu
        batch_menu = actions_menu.addMenu("&Batch Operations")

        batch_delete_action = QAction("Mark Selected for &Deletion", self)
        batch_delete_action.setShortcut("Shift+D")
        batch_delete_action.triggered.connect(lambda: self._batch_mark_selected('delete'))
        batch_menu.addAction(batch_delete_action)

        batch_favorite_action = QAction("Mark Selected as &Favorite", self)
        batch_favorite_action.setShortcut("Shift+F")
        batch_favorite_action.triggered.connect(lambda: self._batch_mark_selected('favorite'))
        batch_menu.addAction(batch_favorite_action)

        batch_date_action = QAction("Flag Selected for Date &Correction", self)
        batch_date_action.setShortcut("Shift+C")
        batch_date_action.triggered.connect(lambda: self._batch_mark_selected('date_correction'))
        batch_menu.addAction(batch_date_action)

        batch_menu.addSeparator()

        batch_unmark_action = QAction("&Unmark All Selected", self)
        batch_unmark_action.setShortcut("Shift+U")
        batch_unmark_action.triggered.connect(self._batch_unmark_selected)
        batch_menu.addAction(batch_unmark_action)

        actions_menu.addSeparator()

        export_action = QAction("&Export Marked Files...", self)
        export_action.triggered.connect(self._export_marked_files)
        actions_menu.addAction(export_action)

        actions_menu.addSeparator()

        clear_marks_action = QAction("&Clear All Marks", self)
        clear_marks_action.triggered.connect(self._clear_all_marks)
        actions_menu.addAction(clear_marks_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        shortcuts_action = QAction("Keyboard &Shortcuts", self)
        shortcuts_action.setShortcut(QKeySequence.HelpContents)
        shortcuts_action.triggered.connect(self._show_shortcuts)
        help_menu.addAction(shortcuts_action)

        help_menu.addSeparator()

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_toolbar(self):
        """Create toolbar with database info and folder display."""
        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Database info
        toolbar.addWidget(QLabel("Database:"))
        self.db_name_label = QLabel("No database loaded")
        self.db_name_label.setMinimumWidth(200)
        self.db_name_label.setStyleSheet("font-weight: bold; padding: 0 10px;")
        toolbar.addWidget(self.db_name_label)

        # Select database button
        select_db_btn = QPushButton("Select Database...")
        select_db_btn.clicked.connect(self._select_database)
        toolbar.addWidget(select_db_btn)

        toolbar.addSeparator()

        # View filter dropdown
        toolbar.addWidget(QLabel("View:"))
        self.view_filter_combo = QComboBox()
        self.view_filter_combo.addItems([
            "Browse Folders",
            "Content Duplicates"
        ])
        self.view_filter_combo.setToolTip(
            "Browse Folders: Navigate archive by folder structure\n"
            "Content Duplicates: Show files with identical pixel content"
        )
        self.view_filter_combo.currentIndexChanged.connect(self._on_view_filter_changed)
        self.view_filter_combo.setMinimumWidth(150)
        toolbar.addWidget(self.view_filter_combo)

        toolbar.addSeparator()

        # Current folder display
        toolbar.addWidget(QLabel("Folder:"))
        self.folder_label = QLabel("(select folder from tree)")
        self.folder_label.setMinimumWidth(300)
        toolbar.addWidget(self.folder_label)

        toolbar.addSeparator()

        # Batch operation buttons
        toolbar.addWidget(QLabel("Batch:"))

        mark_delete_btn = QPushButton("Delete")
        mark_delete_btn.setToolTip("Mark all selected for deletion (Shift+D)")
        mark_delete_btn.clicked.connect(lambda: self._batch_mark_selected('delete'))
        toolbar.addWidget(mark_delete_btn)

        mark_favorite_btn = QPushButton("Favorite")
        mark_favorite_btn.setToolTip("Mark all selected as favorite (Shift+F)")
        mark_favorite_btn.clicked.connect(lambda: self._batch_mark_selected('favorite'))
        toolbar.addWidget(mark_favorite_btn)

        unmark_btn = QPushButton("Unmark")
        unmark_btn.setToolTip("Unmark all selected (Shift+U)")
        unmark_btn.clicked.connect(self._batch_unmark_selected)
        toolbar.addWidget(unmark_btn)

        toolbar.addSeparator()

        # Statistics
        self.stats_label = QLabel("Ready")
        toolbar.addWidget(self.stats_label)

        # Stretch to push everything left
        toolbar.addWidget(QWidget())  # Spacer

    def _create_central_widget(self):
        """Create central widget with splitters."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main horizontal splitter (folder browser | grid + preview)
        main_splitter = QSplitter(Qt.Horizontal)

        # Folder browser (left side)
        self.folder_browser = FolderBrowser()
        self.folder_browser.folder_selected.connect(self._on_folder_selected)
        main_splitter.addWidget(self.folder_browser)

        # Right side: vertical splitter (grid | preview)
        right_splitter = QSplitter(Qt.Vertical)

        # Placeholder for grid (will be created when database is loaded)
        self.grid_container = QWidget()
        grid_layout = QVBoxLayout(self.grid_container)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        self.grid_view = None  # Will be created when database is loaded
        self.no_db_label = QLabel("Select a database to begin")
        self.no_db_label.setAlignment(Qt.AlignCenter)
        self.no_db_label.setStyleSheet("font-size: 18pt; color: #888;")
        grid_layout.addWidget(self.no_db_label)

        right_splitter.addWidget(self.grid_container)

        # Preview pane (bottom)
        self.preview_pane = PreviewPane()
        right_splitter.addWidget(self.preview_pane)

        # Set splitter proportions (70% grid, 30% preview)
        right_splitter.setStretchFactor(0, 7)
        right_splitter.setStretchFactor(1, 3)

        main_splitter.addWidget(right_splitter)

        # Set main splitter proportions (20% browser, 80% grid+preview)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 8)

        layout.addWidget(main_splitter)

    def _create_status_bar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _load_last_database(self):
        """Load last used database from config."""
        db_path = self.config.database_path
        if db_path and Path(db_path).exists():
            self._load_database(db_path)
        else:
            # Prompt to select database
            logger.info("No database configured, prompting user to select one")
            # Don't auto-show dialog on startup - wait for user to click button

    def _select_database(self):
        """Open database selector dialog."""
        # Search both current directory and parent directory
        # This ensures we find databases created by main app (in parent dir)
        # and databases created from triage app (in current dir)
        search_paths = [
            ".",      # Current directory
            "..",     # Parent directory (where main app runs)
        ]

        dialog = DatabaseSelectorDialog(self, search_paths=search_paths)
        dialog.database_selected.connect(self._on_database_selected)
        dialog.exec()

    def _on_database_selected(self, db_path: str):
        """Handle database selection from dialog."""
        if db_path:
            self._load_database(db_path)

    def _load_database(self, db_path: str):
        """Load database and initialize components."""
        try:
            logger.info(f"Loading database: {db_path}")

            # Get database metadata
            db_meta = DatabaseMetadata(db_path)
            metadata = db_meta.get_metadata()

            archive_path = metadata.get('archive_location')
            if not archive_path:
                QMessageBox.warning(
                    self,
                    "No Archive Location",
                    "This database does not have an archive location configured.\n"
                    "Please configure it in the main PyPhotoOrganizer application."
                )
                return

            self.current_db_path = db_path
            self.current_archive_path = archive_path

            # Ensure triage tables exist (auto-migration)
            triage_db = TriageDatabase(db_path)
            triage_db.ensure_triage_tables()
            logger.info("✓ Triage tables verified/created")

            # Initialize thumbnail cache
            cache_dir = self.config.thumbnail_cache_dir
            self.thumbnail_cache = ThumbnailCache(
                db_path=db_path,
                cache_dir=cache_dir,
                memory_size=self.config.memory_cache_size,
                disk_size_gb=self.config.disk_cache_size_gb,
                worker_threads=self.config.worker_threads
            )

            # Create grid model
            self.grid_model = ThumbnailGridModel(self.thumbnail_cache, db_path)

            # Create or update grid view
            if self.grid_view:
                # Update existing view
                self.grid_view.setModel(self.grid_model)
            else:
                # Create new view
                self.no_db_label.hide()
                self.grid_view = ThumbnailGridView(self.grid_model)
                self.grid_view.selection_changed.connect(self._on_selection_changed)
                self.grid_view.item_activated.connect(self._on_item_activated)
                self.grid_container.layout().addWidget(self.grid_view)

            # Update folder browser
            self.folder_browser.set_archive_root(archive_path)

            # Update UI
            db_name = metadata.get('database_name', Path(db_path).name)
            self.db_name_label.setText(db_name)
            self.setWindowTitle(f"Photo Triage - {db_name}")
            self.status_bar.showMessage(f"Loaded database: {db_name}")

            # Save to config for next time
            self.config.database_path = db_path
            self.config.save()

            logger.info(f"✓ Database loaded successfully: {db_name}")

        except Exception as e:
            logger.error(f"Failed to load database: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Database Load Error",
                f"Failed to load database:\n{e}"
            )

    def _on_view_filter_changed(self, index: int):
        """Handle view filter dropdown change."""
        try:
            if not self.grid_model:
                return

            view_mode = self.view_filter_combo.currentText()
            logger.info(f"View filter changed to: {view_mode}")

            if view_mode == "Content Duplicates":
                # Show content duplicates view
                self.folder_browser.setEnabled(False)
                self.folder_label.setText("(Content Duplicates - all folders)")

                # Load content duplicates
                duplicate_groups = self.grid_model.load_content_duplicates()

                # Update stats
                count = self.grid_model.rowCount()
                self.stats_label.setText(f"{count} images in {duplicate_groups} duplicate groups")
                self.status_bar.showMessage(
                    f"Showing {count} images with duplicate content ({duplicate_groups} groups)"
                )

                if count == 0:
                    self.status_bar.showMessage("No content duplicates found in archive")

            else:
                # Browse Folders mode
                self.folder_browser.setEnabled(True)
                self.folder_label.setText("(select folder from tree)")
                self.stats_label.setText("Select a folder")
                self.status_bar.showMessage("Select a folder from the tree to browse")

                # Clear the grid until user selects a folder
                if self.grid_model:
                    self.grid_model.beginResetModel()
                    self.grid_model.file_items.clear()
                    self.grid_model.endResetModel()

        except Exception as e:
            logger.error(f"Error changing view filter: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "View Filter Error",
                f"Failed to change view:\n{e}"
            )

    def _on_folder_selected(self, folder_path: str):
        """Handle folder selection from browser."""
        try:
            if not self.grid_model:
                return

            # Switch to Browse Folders mode if not already there
            if self.view_filter_combo.currentText() != "Browse Folders":
                self.view_filter_combo.blockSignals(True)
                self.view_filter_combo.setCurrentText("Browse Folders")
                self.view_filter_combo.blockSignals(False)
                self.folder_browser.setEnabled(True)

            logger.info(f"Loading folder: {folder_path}")
            self.folder_label.setText(folder_path)

            # Load folder into grid
            self.grid_model.load_folder(folder_path, recursive=False)

            # Update stats
            count = self.grid_model.rowCount()
            self.stats_label.setText(f"{count} images")
            self.status_bar.showMessage(f"Loaded {count} images from {folder_path}")

        except Exception as e:
            logger.error(f"Error loading folder {folder_path}: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Folder Load Error",
                f"Failed to load folder:\n{folder_path}\n\nError: {e}\n\nCheck triage_app.log for details"
            )
            self.status_bar.showMessage(f"Error loading folder: {e}")

    def _on_selection_changed(self, selected_hashes: list):
        """Handle selection change in grid."""
        try:
            # Update preview for first selected item
            if selected_hashes and self.grid_model:
                # Find first selected item
                for row in range(self.grid_model.rowCount()):
                    item = self.grid_model.get_item(row)
                    if item and item['file_hash'] == selected_hashes[0]:
                        self.preview_pane.show_image(item['file_path'])
                        break
            else:
                self.preview_pane.clear()

            # Update stats
            self._update_stats()

        except Exception as e:
            logger.error(f"Error in selection changed handler: {e}", exc_info=True)
            # Don't show dialog for selection changes (too disruptive)
            # Just log and continue

    def _on_item_activated(self, file_hash: str):
        """Handle item activation (double-click or Space key)."""
        try:
            # Show large preview
            for row in range(self.grid_model.rowCount()):
                item = self.grid_model.get_item(row)
                if item and item['file_hash'] == file_hash:
                    self.preview_pane.show_image(item['file_path'])
                    break

        except Exception as e:
            logger.error(f"Error in item activated handler: {e}", exc_info=True)
            # Don't show dialog (too disruptive)

    def _set_grid_size(self, size: str):
        """Change grid thumbnail size."""
        if self.grid_view:
            self.grid_view.set_thumbnail_size(size)
            self.status_bar.showMessage(f"Grid size: {size}", 2000)

    def _update_stats(self):
        """Update statistics display."""
        if not self.grid_model:
            return

        total = self.grid_model.rowCount()
        marked_delete = len(self.grid_model.marked_for_deletion)
        marked_favorite = len(self.grid_model.marked_as_favorite)
        marked_date = len(self.grid_model.marked_for_date_correction)

        stats_text = f"{total} images"
        if marked_delete > 0:
            stats_text += f" | {marked_delete} marked for deletion"
        if marked_favorite > 0:
            stats_text += f" | {marked_favorite} favorites"
        if marked_date > 0:
            stats_text += f" | {marked_date} date corrections"

        self.stats_label.setText(stats_text)

    def _export_marked_files(self):
        """Export list of marked files."""
        if not self.grid_model:
            return

        # Get all marked items
        delete_items = self.grid_model.get_marked_items('delete')
        favorite_items = self.grid_model.get_marked_items('favorite')
        date_items = self.grid_model.get_marked_items('date_correction')

        total = len(delete_items) + len(favorite_items) + len(date_items)

        if total == 0:
            QMessageBox.information(self, "No Marks", "No files have been marked.")
            return

        # Select export file
        export_path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export Marked Files",
            str(Path.home() / "triage_export.txt"),
            "Text Files (*.txt);;CSV Files (*.csv);;JSON Files (*.json);;All Files (*)"
        )

        if export_path:
            try:
                # Determine format from extension or filter
                export_path_obj = Path(export_path)
                extension = export_path_obj.suffix.lower()

                if extension == '.csv' or 'CSV' in selected_filter:
                    self._export_as_csv(export_path, delete_items, favorite_items, date_items)
                elif extension == '.json' or 'JSON' in selected_filter:
                    self._export_as_json(export_path, delete_items, favorite_items, date_items)
                else:
                    self._export_as_text(export_path, delete_items, favorite_items, date_items)

                QMessageBox.information(
                    self,
                    "Export Complete",
                    f"Exported {total} marked files to:\n{export_path}"
                )

            except Exception as e:
                logger.error(f"Export failed: {e}", exc_info=True)
                QMessageBox.critical(self, "Export Error", f"Failed to export:\n{e}")

    def _export_as_text(self, export_path: str, delete_items, favorite_items, date_items):
        """Export marked files as plain text."""
        with open(export_path, 'w') as f:
            f.write(f"Photo Triage Export\n")
            f.write(f"Database: {self.current_db_path}\n")
            f.write(f"Archive: {self.current_archive_path}\n")
            f.write(f"Export Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            if delete_items:
                f.write(f"\nMarked for Deletion ({len(delete_items)}):\n")
                for item in delete_items:
                    f.write(f"  {item['file_path']}\n")

            if favorite_items:
                f.write(f"\nMarked as Favorites ({len(favorite_items)}):\n")
                for item in favorite_items:
                    f.write(f"  {item['file_path']}\n")

            if date_items:
                f.write(f"\nFlagged for Date Correction ({len(date_items)}):\n")
                for item in date_items:
                    f.write(f"  {item['file_path']}\n")

    def _export_as_csv(self, export_path: str, delete_items, favorite_items, date_items):
        """Export marked files as CSV."""
        import csv

        with open(export_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Write header
            writer.writerow(['Action Type', 'File Path', 'File Hash', 'File Size'])

            # Write delete items
            for item in delete_items:
                writer.writerow([
                    'Delete',
                    item['file_path'],
                    item['file_hash'],
                    item.get('file_size', '')
                ])

            # Write favorite items
            for item in favorite_items:
                writer.writerow([
                    'Favorite',
                    item['file_path'],
                    item['file_hash'],
                    item.get('file_size', '')
                ])

            # Write date correction items
            for item in date_items:
                writer.writerow([
                    'Date Correction',
                    item['file_path'],
                    item['file_hash'],
                    item.get('file_size', '')
                ])

    def _export_as_json(self, export_path: str, delete_items, favorite_items, date_items):
        """Export marked files as JSON."""
        import json

        export_data = {
            'metadata': {
                'database_path': self.current_db_path,
                'archive_path': self.current_archive_path,
                'export_date': datetime.now().isoformat(),
                'total_files': len(delete_items) + len(favorite_items) + len(date_items)
            },
            'marked_for_deletion': [
                {
                    'file_path': item['file_path'],
                    'file_hash': item['file_hash'],
                    'file_size': item.get('file_size', None)
                }
                for item in delete_items
            ],
            'marked_as_favorites': [
                {
                    'file_path': item['file_path'],
                    'file_hash': item['file_hash'],
                    'file_size': item.get('file_size', None)
                }
                for item in favorite_items
            ],
            'flagged_for_date_correction': [
                {
                    'file_path': item['file_path'],
                    'file_hash': item['file_hash'],
                    'file_size': item.get('file_size', None)
                }
                for item in date_items
            ]
        }

        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=2)

    def _clear_all_marks(self):
        """Clear all marks from all files."""
        if not self.grid_model:
            return

        total = (len(self.grid_model.marked_for_deletion) +
                len(self.grid_model.marked_as_favorite) +
                len(self.grid_model.marked_for_date_correction))

        if total == 0:
            return

        reply = QMessageBox.question(
            self,
            "Clear All Marks",
            f"Clear all marks from {total} files?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Clear all marks
            triage_db = TriageDatabase(self.current_db_path)

            for file_hash in list(self.grid_model.marked_for_deletion):
                triage_db.unmark_file(file_hash, 'delete')

            for file_hash in list(self.grid_model.marked_as_favorite):
                triage_db.unmark_file(file_hash, 'favorite')

            for file_hash in list(self.grid_model.marked_for_date_correction):
                triage_db.unmark_file(file_hash, 'date_correction')

            # Clear in-memory sets
            self.grid_model.marked_for_deletion.clear()
            self.grid_model.marked_as_favorite.clear()
            self.grid_model.marked_for_date_correction.clear()

            # Reload model to update display
            self.grid_model._load_existing_marks()

            self._update_stats()
            self.status_bar.showMessage("All marks cleared", 3000)

    def _batch_mark_selected(self, action_type: str):
        """Mark all selected files for specified action."""
        if not self.grid_view:
            return

        selected_indices = self.grid_view.selectedIndexes()
        if not selected_indices:
            QMessageBox.information(self, "No Selection", "Please select files to mark.")
            return

        count = 0
        action_names = {
            'delete': 'deletion',
            'favorite': 'favorites',
            'date_correction': 'date correction'
        }

        for index in selected_indices:
            item = self.grid_model.get_item(index.row())
            if item:
                file_hash = item['file_hash']
                # Always mark (don't toggle)
                if action_type == 'delete':
                    if file_hash not in self.grid_model.marked_for_deletion:
                        self.grid_model.mark_file(file_hash, action_type)
                        count += 1
                elif action_type == 'favorite':
                    if file_hash not in self.grid_model.marked_as_favorite:
                        self.grid_model.mark_file(file_hash, action_type)
                        count += 1
                elif action_type == 'date_correction':
                    if file_hash not in self.grid_model.marked_for_date_correction:
                        self.grid_model.mark_file(file_hash, action_type)
                        count += 1

        if count > 0:
            action_name = action_names.get(action_type, action_type)
            self.status_bar.showMessage(f"Marked {count} files for {action_name}", 3000)
            self._update_stats()
            self.grid_view.viewport().update()  # Trigger redraw

    def _batch_unmark_selected(self):
        """Unmark all selected files (all action types)."""
        if not self.grid_view:
            return

        selected_indices = self.grid_view.selectedIndexes()
        if not selected_indices:
            QMessageBox.information(self, "No Selection", "Please select files to unmark.")
            return

        count = 0
        triage_db = TriageDatabase(self.current_db_path)

        for index in selected_indices:
            item = self.grid_model.get_item(index.row())
            if item:
                file_hash = item['file_hash']

                # Unmark all action types
                if file_hash in self.grid_model.marked_for_deletion:
                    triage_db.unmark_file(file_hash, 'delete')
                    self.grid_model.marked_for_deletion.discard(file_hash)
                    count += 1

                if file_hash in self.grid_model.marked_as_favorite:
                    triage_db.unmark_file(file_hash, 'favorite')
                    self.grid_model.marked_as_favorite.discard(file_hash)
                    count += 1

                if file_hash in self.grid_model.marked_for_date_correction:
                    triage_db.unmark_file(file_hash, 'date_correction')
                    self.grid_model.marked_for_date_correction.discard(file_hash)
                    count += 1

        if count > 0:
            self.status_bar.showMessage(f"Removed {count} marks", 3000)
            self._update_stats()
            self.grid_view.viewport().update()  # Trigger redraw

    def _show_cache_stats(self):
        """Show cache statistics dialog."""
        if not self.thumbnail_cache:
            QMessageBox.information(
                self,
                "No Cache",
                "Please load a database first to view cache statistics."
            )
            return

        dialog = CacheStatsDialog(self.thumbnail_cache, self)
        dialog.exec()

    def _show_shortcuts(self):
        """Show keyboard shortcuts dialog."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Keyboard Shortcuts")
        msg.setTextFormat(Qt.RichText)
        msg.setText(
            "<h3>Photo Triage Keyboard Shortcuts</h3>"
            "<table cellpadding='5'>"
            "<tr><td><b>D</b></td><td>Toggle delete mark</td></tr>"
            "<tr><td><b>F</b></td><td>Toggle favorite mark</td></tr>"
            "<tr><td><b>C</b></td><td>Flag for date correction</td></tr>"
            "<tr><td><b>1 / 2 / 3</b></td><td>Grid size (small/medium/large)</td></tr>"
            "<tr><td><b>Space</b></td><td>Show large preview</td></tr>"
            "<tr><td><b>Arrow keys</b></td><td>Navigate grid</td></tr>"
            "<tr><td><b>Ctrl+A</b></td><td>Select all</td></tr>"
            "<tr><td><b>Escape</b></td><td>Clear selection</td></tr>"
            "<tr><td><b>Shift+Click</b></td><td>Range select</td></tr>"
            "<tr><td><b>Ctrl+Click</b></td><td>Toggle selection</td></tr>"
            "</table>"
        )
        msg.exec()

    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Photo Triage",
            "<h3>Photo Triage</h3>"
            "<p>High-performance photo review and organization tool</p>"
            "<p>Part of PyPhotoOrganizer</p>"
            "<p>Built with Python and PySide6</p>"
        )


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)
    window = TriageWindow()
    window.show()
    sys.exit(app.exec())
