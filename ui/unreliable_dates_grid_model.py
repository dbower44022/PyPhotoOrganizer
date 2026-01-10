"""
Unreliable Dates Grid Model

QAbstractListModel for displaying unreliable dates records in a thumbnail grid.
Stores only metadata - thumbnails loaded on-demand by delegate.
"""

import logging
import os
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)


class UnreliableDatesGridModel(QAbstractListModel):
    """
    Data model for unreliable dates thumbnail grid.

    Stores file metadata from UnreliableDates table.
    Thumbnails are loaded on-demand via Qt.DecorationRole from ThumbnailCache.
    Tracks status overlay info for rendering.

    Performance:
    - Can handle 10,000+ items (stores ~1KB per item)
    - Only visible items are rendered (delegate handles lazy loading)
    - Thumbnail loading is async (via ThumbnailCache)
    """

    # Signal emitted when model data is fully loaded
    data_loaded = Signal(int)  # Number of records loaded

    def __init__(self, thumbnail_cache, db_metadata, parent=None):
        """
        Initialize model.

        Args:
            thumbnail_cache: ThumbnailCache instance for loading thumbnails
            db_metadata: DatabaseMetadata instance for settings
            parent: Parent QObject
        """
        super().__init__(parent)
        self.thumbnail_cache = thumbnail_cache
        self.db_metadata = db_metadata

        # File data: List of dicts from UnreliableDates table
        # Keys: file_hash, source_path, archive_path, original_date, corrected_date,
        #       date_source, flag_reason, needs_reorganization
        self.file_items: List[Dict[str, Any]] = []

        # Current thumbnail size (64, 100, or 150)
        self.thumbnail_size = 100

        # Safety flag: prevent data access during model reset
        self._is_resetting = False

        # Null pixmap for missing thumbnails
        self._null_pixmap = QPixmap()

        # Connect to cache's thumbnail_ready signal to update view when thumbnails load
        self.thumbnail_cache.thumbnail_ready.connect(self._on_thumbnail_ready)
        logger.info("UnreliableDatesGridModel initialized")

    def rowCount(self, parent=QModelIndex()):
        """Return number of items."""
        if parent.isValid():
            return 0
        # Return 0 during reset to prevent Qt from accessing invalid rows
        if self._is_resetting:
            return 0
        return len(self.file_items)

    def data(self, index: QModelIndex, role: int):
        """
        Get data for index and role.

        Args:
            index: Model index
            role: Qt data role

        Returns:
            Data for the given role
        """
        try:
            # Don't return data while resetting
            if self._is_resetting:
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            # Validate index
            if not index or not index.isValid():
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            row = index.row()

            # Validate row bounds
            if row < 0 or row >= len(self.file_items):
                logger.warning(f"data() called with out-of-bounds row: {row}/{len(self.file_items)}")
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            # Get item safely
            item = self.file_items[row]
            if not item:
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            if role == Qt.DisplayRole:
                # Filename shown below thumbnail
                file_path = item.get('source_path', '')
                if file_path:
                    return os.path.basename(file_path)
                return "Unknown"

            elif role == Qt.DecorationRole:
                # Thumbnail pixmap (loaded from cache)
                file_hash = item.get('file_hash')
                file_path = item.get('source_path')
                if file_hash and file_path:
                    try:
                        pixmap = self.thumbnail_cache.get_thumbnail(
                            file_hash,
                            file_path,
                            size=self.thumbnail_size,
                            priority='high'  # Visible item
                        )

                        # Validate QPixmap before returning
                        if pixmap is None:
                            return self._null_pixmap

                        if not isinstance(pixmap, QPixmap):
                            logger.error(f"Cache returned non-QPixmap: {type(pixmap)}")
                            return self._null_pixmap

                        if pixmap.isNull():
                            return self._null_pixmap

                        return pixmap

                    except Exception as cache_error:
                        logger.error(f"Error getting thumbnail: {cache_error}", exc_info=True)
                        return self._null_pixmap

                return self._null_pixmap

            elif role == Qt.UserRole:
                # Full record for selection/detail display
                return item

            elif role == Qt.UserRole + 1:
                # Status overlay info (for delegate rendering)
                if item.get('corrected_date'):
                    if item.get('needs_reorganization'):
                        return 'corrected'  # Green overlay
                    else:
                        return 'reorganized'  # Blue overlay
                return 'pending'  # No overlay

            elif role == Qt.ToolTipRole:
                # Tooltip with file info
                filename = os.path.basename(item.get('source_path', ''))
                status_text = "Pending"
                if item.get('corrected_date'):
                    if item.get('needs_reorganization'):
                        status_text = f"Corrected: {item['corrected_date']} (Needs reorganization)"
                    else:
                        status_text = f"Reorganized: {item['corrected_date']}"

                return f"{filename}\nStatus: {status_text}"

            return None

        except Exception as e:
            logger.error(f"Error in data() for row {index.row()}: {e}", exc_info=True)
            if role == Qt.DecorationRole:
                return self._null_pixmap
            return None

    def load_data(self, records: List[Dict[str, Any]]):
        """
        Load unreliable dates records into model.

        Args:
            records: List of dicts from UnreliableDates table
        """
        try:
            logger.info(f"Loading {len(records)} records into grid model")

            self._is_resetting = True
            self.beginResetModel()

            self.file_items = records

            self.endResetModel()
            self._is_resetting = False

            logger.info(f"Grid model loaded with {len(records)} records")
            self.data_loaded.emit(len(records))

        except Exception as e:
            logger.error(f"Error loading data into grid model: {e}", exc_info=True)
            self._is_resetting = False

    def set_thumbnail_size(self, size: int):
        """
        Change thumbnail size and refresh all items.

        Args:
            size: New thumbnail size in pixels (64, 100, or 150)
        """
        logger.info(f"Changing thumbnail size from {self.thumbnail_size}px to {size}px")
        self.thumbnail_size = size

        # Clear memory cache (different size needs regeneration)
        self.thumbnail_cache.clear_memory_cache()

        # Trigger complete repaint
        if len(self.file_items) > 0:
            self.dataChanged.emit(
                self.index(0, 0),
                self.index(self.rowCount() - 1, 0),
                [Qt.DecorationRole]
            )

    def get_record(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get record at row.

        Args:
            row: Row index

        Returns:
            Record dict or None if invalid row
        """
        if 0 <= row < len(self.file_items):
            return self.file_items[row]
        return None

    def get_record_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """
        Find record by file hash.

        Args:
            file_hash: SHA-256 file hash

        Returns:
            Record dict or None if not found
        """
        for item in self.file_items:
            if item.get('file_hash') == file_hash:
                return item
        return None

    def get_item(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get item at row (alias for get_record).

        Args:
            row: Row index

        Returns:
            Item dict or None if invalid row
        """
        return self.get_record(row)

    def _on_thumbnail_ready(self, file_hash: str, size: int):
        """
        Handle thumbnail_ready signal from cache.

        Updates the view when a thumbnail finishes generating.

        Args:
            file_hash: File hash of loaded thumbnail
            size: Size of loaded thumbnail
        """
        try:
            # Only update if size matches current size
            if size != self.thumbnail_size:
                return

            # Find row with this hash
            for row, item in enumerate(self.file_items):
                if item.get('file_hash') == file_hash:
                    # Emit dataChanged to trigger repaint
                    index = self.index(row, 0)
                    self.dataChanged.emit(index, index, [Qt.DecorationRole])
                    logger.debug(f"Updated thumbnail for row {row}")
                    break

        except Exception as e:
            logger.error(f"Error handling thumbnail_ready: {e}", exc_info=True)
