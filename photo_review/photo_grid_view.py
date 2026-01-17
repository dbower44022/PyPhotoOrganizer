"""
Photo Grid View

QListView-based thumbnail grid for photo review.
Adapted from UnreliableDatesGridView for the Photo Review application.
"""

import logging
import os
import subprocess
import sys

from PySide6.QtWidgets import QListView, QAbstractItemView, QMenu, QApplication
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QKeyEvent, QAction

from photo_review.photo_grid_delegate import PhotoGridDelegate

logger = logging.getLogger(__name__)


class PhotoGridView(QListView):
    """
    Thumbnail grid for photo review.

    Features:
    - Virtual scrolling (only visible items rendered)
    - Keyboard shortcuts: 1/2/3=size, Space=preview, Ctrl+A=select all
    - Scroll-based prefetching
    - Extended selection (Shift/Ctrl)
    - Context menu with actions

    Performance:
    - Can handle 10,000+ items with smooth scrolling
    - Only visible items are rendered
    - Background thumbnail generation via cache
    """

    # Signals
    selection_changed = Signal(list)  # List of selected file hashes
    item_activated = Signal(dict)  # Double-click or Space on record
    delete_requested = Signal()  # Context menu: Delete to Vault
    rotate_requested = Signal()  # Context menu: Rotate Image
    correct_date_requested = Signal()  # Context menu: Correct Date
    reorganize_requested = Signal()  # Context menu: Reorganize Marked Files
    open_file_requested = Signal()  # Context menu: Open File
    open_folder_requested = Signal()  # Context menu: Open in Folder
    copy_path_requested = Signal()  # Context menu: Copy Path
    refresh_thumbnail_requested = Signal()  # Context menu: Refresh Thumbnail
    deselect_all_requested = Signal()  # Context menu: Deselect All

    def __init__(self, model, parent=None):
        """
        Initialize grid view.

        Args:
            model: PhotoGridModel instance
            parent: Parent widget
        """
        super().__init__(parent)

        self.grid_model = model
        self.setModel(model)

        # Create and set delegate
        self.delegate = PhotoGridDelegate(self)
        self.setItemDelegate(self.delegate)

        # Current thumbnail size
        self.current_size_name = 'medium'
        self.size_map = {
            'small': 150,
            'medium': 200,
            'large': 300
        }

        # Configure view for high performance
        self._configure_view()

        # Connect signals
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)
        self.doubleClicked.connect(self._on_double_clicked)

        # Prefetch on scroll
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

        # Enable context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        logger.info("PhotoGridView initialized")

    def _configure_view(self):
        """Configure view for high performance."""
        # View mode
        self.setViewMode(QListView.IconMode)
        self.setResizeMode(QListView.Adjust)
        self.setSpacing(2)  # Minimal spacing to maximize thumbnails on screen

        # CRITICAL for performance!
        self.setUniformItemSizes(True)  # All items same size
        self.setLayoutMode(QListView.Batched)  # Lazy layout
        self.setBatchSize(50)  # Layout 50 items at a time

        # Selection
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)

        # Enable word wrap for filenames
        self.setWordWrap(True)

        # Scrolling
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)

        # Styling
        self.setStyleSheet("""
            QListView {
                background-color: #2d2d2d;
                border: none;
                outline: none;
            }
            QListView::item:selected {
                background-color: rgba(66, 133, 244, 0.3);
            }
            QListView::item:hover {
                background-color: rgba(66, 133, 244, 0.1);
            }
        """)

        # Set initial size
        self.set_thumbnail_size('medium')

    def set_thumbnail_size(self, size_name: str):
        """
        Change grid size.

        Args:
            size_name: 'small' (150px), 'medium' (200px), or 'large' (300px)
        """
        if size_name not in self.size_map:
            logger.warning(f"Invalid thumbnail size: {size_name}")
            return

        self.current_size_name = size_name
        pixel_size = self.size_map[size_name]

        # Update model
        self.grid_model.set_thumbnail_size(pixel_size)

        # Update delegate
        self.delegate.set_thumbnail_size(pixel_size)

        # Update grid size
        # Minimal margins to maximize thumbnails on screen
        item_size = pixel_size + 10  # Small margins for selection border
        self.setIconSize(QSize(item_size, item_size))
        self.setGridSize(QSize(item_size + 4, item_size + 4))  # Minimal spacing between items

        logger.info(f"Grid size changed to {size_name} ({pixel_size}px)")

    def set_thumbnail_size_pixels(self, pixel_size: int):
        """
        Change grid size by pixel value.

        Args:
            pixel_size: Size in pixels (150, 200, or 300)
        """
        # Map pixel size to size name
        size_name_map = {150: 'small', 200: 'medium', 300: 'large'}
        size_name = size_name_map.get(pixel_size, 'medium')
        self.set_thumbnail_size(size_name)

    def _on_scroll(self):
        """Handle scroll event - prefetch thumbnails."""
        try:
            # Get visible range
            first_visible_index = self.indexAt(self.rect().topLeft())
            last_visible_index = self.indexAt(self.rect().bottomRight())

            if first_visible_index.isValid() and last_visible_index.isValid():
                start_row = first_visible_index.row()
                end_row = last_visible_index.row() + 1

                visible_range = (start_row, end_row)

                # Prefetch surrounding items if thumbnail cache has prefetch method
                if hasattr(self.grid_model, 'thumbnail_cache') and self.grid_model.thumbnail_cache:
                    if hasattr(self.grid_model.thumbnail_cache, 'prefetch'):
                        prefetch_count = 50
                        self.grid_model.thumbnail_cache.prefetch(
                            self.grid_model.file_items,
                            visible_range,
                            prefetch_count
                        )

        except Exception as e:
            logger.error(f"Error in scroll handler: {e}", exc_info=True)

    def keyPressEvent(self, event: QKeyEvent):
        """
        Handle keyboard shortcuts.

        Args:
            event: Key event
        """
        try:
            key = event.key()
            modifiers = event.modifiers()

            if key in (Qt.Key_1, Qt.Key_2, Qt.Key_3):
                # Change grid size
                size_map = {Qt.Key_1: 'small', Qt.Key_2: 'medium', Qt.Key_3: 'large'}
                self.set_thumbnail_size(size_map[key])
                event.accept()

            elif key == Qt.Key_Space:
                # Emit signal to show/focus preview window
                selected_indices = self.selectedIndexes()
                if selected_indices:
                    record = self.grid_model.get_record_at(selected_indices[0])
                    if record:
                        self.item_activated.emit(record)
                event.accept()

            elif key == Qt.Key_Escape:
                # Clear selection
                self.clearSelection()
                event.accept()

            elif key == Qt.Key_A and modifiers & Qt.ControlModifier:
                # Select all
                self.selectAll()
                event.accept()

            elif key == Qt.Key_Delete:
                # Delete selected items
                if self.selectedIndexes():
                    self.delete_requested.emit()
                event.accept()

            elif key == Qt.Key_R and modifiers & Qt.ControlModifier:
                # Rotate selected items
                if self.selectedIndexes():
                    self.rotate_requested.emit()
                event.accept()

            elif key == Qt.Key_D and modifiers & Qt.ControlModifier:
                # Correct date for selected items
                if self.selectedIndexes():
                    self.correct_date_requested.emit()
                event.accept()

            elif key == Qt.Key_O and modifiers & Qt.ControlModifier:
                # Open file
                if self.selectedIndexes():
                    self.open_file_requested.emit()
                event.accept()

            elif key == Qt.Key_E and modifiers & Qt.ControlModifier:
                # Open in folder (Explorer/Finder)
                if self.selectedIndexes():
                    self.open_folder_requested.emit()
                event.accept()

            else:
                # Default handling (arrow keys, etc.)
                super().keyPressEvent(event)

        except Exception as e:
            logger.error(f"Error in keyPressEvent: {e}", exc_info=True)
            event.accept()

    def _on_selection_changed(self):
        """Handle selection changed."""
        try:
            selected_indices = self.selectedIndexes()
            selected_hashes = []

            for index in selected_indices:
                if not index.isValid():
                    continue
                record = self.grid_model.get_record_at(index)
                if record:
                    file_hash = record.get('file_hash')
                    if file_hash:
                        selected_hashes.append(file_hash)

            # Emit signal
            self.selection_changed.emit(selected_hashes)

        except Exception as e:
            logger.error(f"Error in selection changed handler: {e}", exc_info=True)

    def _on_double_clicked(self, index):
        """Handle double-click on item."""
        try:
            if not index or not index.isValid():
                return
            record = self.grid_model.get_record_at(index)
            if record:
                self.item_activated.emit(record)
        except Exception as e:
            logger.error(f"Error in double-click handler: {e}", exc_info=True)

    def get_selected_items(self):
        """
        Get all selected records.

        Returns:
            List of record dicts
        """
        selected_indices = self.selectedIndexes()
        records = []

        for index in selected_indices:
            record = self.grid_model.get_record_at(index)
            if record:
                records.append(record)

        return records

    def get_selected_hashes(self):
        """
        Get file hashes for all selected items.

        Returns:
            List of file hash strings
        """
        records = self.get_selected_items()
        return [r.get('file_hash') for r in records if r.get('file_hash')]

    def _show_context_menu(self, position: QPoint):
        """
        Show context menu at the given position.

        Args:
            position: Position where right-click occurred (widget coordinates)
        """
        try:
            # Check if there are any selected items
            selected_indices = self.selectedIndexes()
            has_selection = len(selected_indices) > 0
            selection_count = len(selected_indices)

            # Create context menu with modern styling
            menu = QMenu(self)
            menu.setStyleSheet("""
                QMenu {
                    background-color: #2d2d2d;
                    border: 1px solid #404040;
                    border-radius: 8px;
                    padding: 8px 4px;
                }
                QMenu::item {
                    padding: 8px 32px 8px 16px;
                    border-radius: 4px;
                    margin: 2px 4px;
                    color: #e0e0e0;
                }
                QMenu::item:selected {
                    background-color: #4285f4;
                    color: white;
                }
                QMenu::item:disabled {
                    color: #808080;
                }
                QMenu::separator {
                    height: 1px;
                    background-color: #404040;
                    margin: 6px 12px;
                }
                QMenu::item:disabled:selected {
                    background-color: transparent;
                }
            """)

            # Selection info header
            if has_selection:
                header_action = QAction(f"📷  {selection_count} item(s) selected", self)
                header_action.setEnabled(False)
                menu.addAction(header_action)
                menu.addSeparator()

            # Action: Open File
            open_action = QAction("📂  Open File", self)
            open_action.setShortcut("Ctrl+O")
            open_action.setEnabled(has_selection)
            open_action.triggered.connect(lambda: self.open_file_requested.emit())
            menu.addAction(open_action)

            # Action: Open in Folder
            open_folder_action = QAction("📁  Open in Folder", self)
            open_folder_action.setShortcut("Ctrl+E")
            open_folder_action.setEnabled(has_selection)
            open_folder_action.triggered.connect(lambda: self.open_folder_requested.emit())
            menu.addAction(open_folder_action)

            # Action: Copy Path
            copy_path_action = QAction("📋  Copy Path", self)
            copy_path_action.setEnabled(has_selection)
            copy_path_action.triggered.connect(lambda: self.copy_path_requested.emit())
            menu.addAction(copy_path_action)

            menu.addSeparator()

            # Action: Correct Date
            correct_action = QAction("📅  Correct Date...", self)
            correct_action.setShortcut("Ctrl+D")
            correct_action.setEnabled(has_selection)
            correct_action.triggered.connect(lambda: self.correct_date_requested.emit())
            menu.addAction(correct_action)

            # Action: Reorganize Marked Files
            reorganize_action = QAction("📦  Reorganize Marked Files...", self)
            reorganize_action.setShortcut("Ctrl+M")
            reorganize_action.triggered.connect(lambda: self.reorganize_requested.emit())
            menu.addAction(reorganize_action)

            # Action: Rotate Image
            rotate_action = QAction("🔄  Rotate Image...", self)
            rotate_action.setShortcut("Ctrl+R")
            rotate_action.setEnabled(has_selection)
            rotate_action.triggered.connect(lambda: self.rotate_requested.emit())
            menu.addAction(rotate_action)

            menu.addSeparator()

            # Action: Delete to Vault
            delete_action = QAction("🗑️  Delete to Vault...", self)
            delete_action.setShortcut("Delete")
            delete_action.setEnabled(has_selection)
            delete_action.triggered.connect(lambda: self.delete_requested.emit())
            menu.addAction(delete_action)

            menu.addSeparator()

            # Action: Refresh Thumbnail
            refresh_thumbnail_action = QAction("🔃  Refresh Thumbnail", self)
            refresh_thumbnail_action.setEnabled(has_selection)
            refresh_thumbnail_action.triggered.connect(lambda: self.refresh_thumbnail_requested.emit())
            menu.addAction(refresh_thumbnail_action)

            menu.addSeparator()

            # Action: Deselect All
            deselect_action = QAction("✖️  Deselect All", self)
            deselect_action.setShortcut("Escape")
            deselect_action.setEnabled(has_selection)
            deselect_action.triggered.connect(lambda: self.deselect_all_requested.emit())
            menu.addAction(deselect_action)

            # Show menu at cursor position (convert to global coordinates)
            menu.exec(self.mapToGlobal(position))

        except Exception as e:
            logger.error(f"Error showing context menu: {e}", exc_info=True)

    def open_selected_file(self):
        """Open the first selected file with the default application."""
        records = self.get_selected_items()
        if not records:
            return

        record = records[0]
        file_path = record.get('archive_path') or record.get('source_path')
        if not file_path or not os.path.exists(file_path):
            logger.warning(f"File not found: {file_path}")
            return

        try:
            if sys.platform == 'win32':
                os.startfile(file_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', file_path], check=True)
            else:
                subprocess.run(['xdg-open', file_path], check=True)
            logger.info(f"Opened file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to open file: {e}")

    def open_selected_folder(self):
        """Open the folder containing the first selected file."""
        records = self.get_selected_items()
        if not records:
            return

        record = records[0]
        file_path = record.get('archive_path') or record.get('source_path')
        if not file_path:
            return

        folder_path = os.path.dirname(file_path)
        if not os.path.exists(folder_path):
            logger.warning(f"Folder not found: {folder_path}")
            return

        try:
            if sys.platform == 'win32':
                # Select the file in Explorer
                subprocess.run(['explorer', '/select,', file_path], check=True)
            elif sys.platform == 'darwin':
                # Reveal in Finder
                subprocess.run(['open', '-R', file_path], check=True)
            else:
                # Open folder in file manager
                subprocess.run(['xdg-open', folder_path], check=True)
            logger.info(f"Opened folder: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to open folder: {e}")

    def copy_selected_path(self):
        """Copy the path of the first selected file to clipboard."""
        records = self.get_selected_items()
        if not records:
            return

        record = records[0]
        file_path = record.get('archive_path') or record.get('source_path')
        if not file_path:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(file_path)
        logger.info(f"Copied path to clipboard: {file_path}")

    def refresh_selected_thumbnails(self):
        """Refresh thumbnails for selected items."""
        records = self.get_selected_items()
        for record in records:
            file_hash = record.get('file_hash')
            if file_hash:
                self.grid_model.refresh_thumbnail(file_hash)
        logger.info(f"Refreshed thumbnails for {len(records)} items")
