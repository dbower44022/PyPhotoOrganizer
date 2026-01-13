"""
Unreliable Dates Grid View

QListView-based thumbnail grid for unreliable dates records.
Simplified version of triage ThumbnailGridView adapted for date corrections.
"""

import logging
from PySide6.QtWidgets import QListView, QAbstractItemView, QMenu
from PySide6.QtCore import Qt, Signal, QSize, QPoint
from PySide6.QtGui import QKeyEvent, QAction

from ui.unreliable_dates_delegate import UnreliableDatesDelegate

logger = logging.getLogger(__name__)


class UnreliableDatesGridView(QListView):
    """
    Thumbnail grid for unreliable dates.

    Features:
    - Virtual scrolling (only visible items rendered)
    - Keyboard shortcuts: 1/2/3=size, Space=preview, Ctrl+A=select all
    - Scroll-based prefetching
    - Extended selection (Shift/Ctrl)

    Performance:
    - Can handle 10,000+ items with smooth scrolling
    - Only visible items are rendered
    - Background thumbnail generation via cache
    """

    # Signals
    selection_changed = Signal(list)  # List of selected file hashes
    item_activated = Signal(dict)  # Double-click on record
    correct_date_requested = Signal()  # Context menu: Correct Date
    reorganize_corrected_requested = Signal()  # Context menu: Reorganize Corrected
    deselect_all_requested = Signal()  # Context menu: Deselect All

    def __init__(self, model, parent=None):
        """
        Initialize grid view.

        Args:
            model: UnreliableDatesGridModel instance
            parent: Parent widget
        """
        super().__init__(parent)

        self.grid_model = model
        self.setModel(model)

        # Create and set delegate
        self.delegate = UnreliableDatesDelegate(self)
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

        logger.info("UnreliableDatesGridView initialized")

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

                # Prefetch surrounding items
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
                    record = self.grid_model.get_record(selected_indices[0].row())
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
                record = self.grid_model.get_record(index.row())
                if record:
                    selected_hashes.append(record['file_hash'])

            # Emit signal
            self.selection_changed.emit(selected_hashes)

        except Exception as e:
            logger.error(f"Error in selection changed handler: {e}", exc_info=True)

    def _on_double_clicked(self, index):
        """Handle double-click on item."""
        try:
            if not index or not index.isValid():
                return
            record = self.grid_model.get_record(index.row())
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
            record = self.grid_model.get_record(index.row())
            if record:
                records.append(record)

        return records

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

            # Create context menu
            menu = QMenu(self)

            # Action 1: Correct Date
            correct_action = QAction("Correct Date", self)
            correct_action.setEnabled(has_selection)
            correct_action.triggered.connect(lambda: self.correct_date_requested.emit())
            menu.addAction(correct_action)

            # Action 2: Reorganize Corrected
            reorganize_action = QAction("Reorganize Corrected", self)
            reorganize_action.triggered.connect(lambda: self.reorganize_corrected_requested.emit())
            menu.addAction(reorganize_action)

            # Action 3: Deselect All
            deselect_action = QAction("Deselect All", self)
            deselect_action.setEnabled(has_selection)
            deselect_action.triggered.connect(lambda: self.deselect_all_requested.emit())
            menu.addAction(deselect_action)

            # Show menu at cursor position (convert to global coordinates)
            menu.exec(self.mapToGlobal(position))

        except Exception as e:
            logger.error(f"Error showing context menu: {e}", exc_info=True)
