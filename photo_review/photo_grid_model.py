"""
Photo Grid Model

QAbstractListModel for displaying photos in a thumbnail grid.
Adapted from UnreliableDatesGridModel for the Photo Review application.

Performance Features:
- O(1) hash-to-index lookup for thumbnail ready notifications
- Efficient model reset with index pre-building
"""

import logging
import os
from typing import List, Dict, Any, Optional

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)


class PhotoGridModel(QAbstractListModel):
    """
    Data model for photo thumbnail grid.

    Works with any query results containing file_hash and archive_path.
    Thumbnails are loaded on-demand via ThumbnailCache.

    Performance:
    - Can handle 10,000+ items (stores ~1KB per item)
    - Only visible items are rendered (delegate handles lazy loading)
    - Thumbnail loading is async (via ThumbnailCache)
    """

    # Custom roles
    RecordRole = Qt.UserRole + 100      # Full record dict
    StatusRole = Qt.UserRole + 101      # Status for overlay
    HashRole = Qt.UserRole + 102        # File hash
    PathRole = Qt.UserRole + 103        # Archive path

    # Signal emitted when model data is fully loaded
    data_loaded = Signal(int)  # Number of records loaded

    def __init__(self, thumbnail_cache, parent=None):
        """
        Initialize model.

        Args:
            thumbnail_cache: ThumbnailCache instance for loading thumbnails
            parent: Parent QObject
        """
        super().__init__(parent)
        self.thumbnail_cache = thumbnail_cache

        # File data: List of dicts from query results
        self.file_items: List[Dict[str, Any]] = []

        # Hash-to-index lookup for O(1) thumbnail ready notifications
        self._hash_to_index: Dict[str, int] = {}

        # Current thumbnail size
        self.thumbnail_size = 200

        # Safety flag: prevent data access during model reset
        self._is_resetting = False

        # Null pixmap for missing thumbnails
        self._null_pixmap = QPixmap()

        # Connect to cache's thumbnail_ready signal to update view
        if self.thumbnail_cache:
            self.thumbnail_cache.thumbnail_ready.connect(self._on_thumbnail_ready)

        logger.info("PhotoGridModel initialized")

    def rowCount(self, parent=QModelIndex()):
        """Return number of items."""
        if parent.isValid():
            return 0
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
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            item = self.file_items[row]
            if not item:
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            if role == Qt.DisplayRole:
                # Filename shown below thumbnail
                file_path = item.get('archive_path') or item.get('source_path', '')
                if file_path:
                    return os.path.basename(file_path)
                return "Unknown"

            elif role == Qt.DecorationRole:
                # Thumbnail pixmap (loaded from cache)
                file_hash = item.get('file_hash')
                archive_path = item.get('archive_path', '')
                source_path = item.get('source_path', '')

                # Prefer archive if available, fallback to source
                file_path = archive_path if archive_path else source_path

                if file_hash and file_path and self.thumbnail_cache:
                    try:
                        pixmap = self.thumbnail_cache.get_thumbnail(
                            file_hash,
                            file_path,
                            size=self.thumbnail_size,
                            priority='high'
                        )

                        if pixmap is None or not isinstance(pixmap, QPixmap) or pixmap.isNull():
                            return self._null_pixmap

                        return pixmap

                    except Exception as e:
                        logger.error(f"Error getting thumbnail: {e}")
                        return self._null_pixmap

                return self._null_pixmap

            elif role == Qt.UserRole or role == self.RecordRole:
                # Full record for selection/detail display
                return item

            elif role == self.StatusRole or role == Qt.UserRole + 1:
                # Status overlay info (for delegate rendering)
                return self._get_status(item)

            elif role == self.HashRole:
                return item.get('file_hash', '')

            elif role == self.PathRole:
                return item.get('archive_path') or item.get('source_path', '')

            elif role == Qt.ToolTipRole:
                # Tooltip with file info
                return self._build_tooltip(item)

            return None

        except Exception as e:
            logger.error(f"Error in data() for row {index.row()}: {e}")
            if role == Qt.DecorationRole:
                return self._null_pixmap
            return None

    def _get_status(self, item: dict) -> str:
        """Determine status for overlay rendering."""
        if item.get('corrected_date'):
            if item.get('needs_reorganization'):
                return 'corrected'  # Green overlay
            else:
                return 'reorganized'  # Blue overlay
        elif item.get('flag_reason'):
            return 'unreliable'  # Yellow/orange overlay
        elif item.get('revised_photo'):
            return 'revision'  # Purple overlay
        return 'normal'  # No overlay

    def _build_tooltip(self, item: dict) -> str:
        """Build tooltip text for an item."""
        parts = []

        # Filename
        file_path = item.get('archive_path') or item.get('source_path', '')
        if file_path:
            parts.append(os.path.basename(file_path))

        # Date
        date_parts = []
        year = item.get('create_year')
        month = item.get('create_month')
        day = item.get('create_day')
        if year:
            date_parts.append(str(year))
            if month:
                date_parts.append(str(month).zfill(2))
                if day:
                    date_parts.append(str(day).zfill(2))
        if date_parts:
            parts.append(f"Date: {'-'.join(date_parts)}")

        # Status
        status = self._get_status(item)
        if status != 'normal':
            status_text = {
                'corrected': 'Date corrected (needs reorganization)',
                'reorganized': 'Reorganized',
                'unreliable': f"Unreliable date: {item.get('flag_reason', 'unknown')}",
                'revision': 'Has revisions'
            }.get(status, status)
            parts.append(f"Status: {status_text}")

        # File size
        size = item.get('file_size')
        if size:
            if size > 1024 * 1024:
                parts.append(f"Size: {size / (1024*1024):.1f} MB")
            elif size > 1024:
                parts.append(f"Size: {size / 1024:.1f} KB")

        return '\n'.join(parts)

    def load_data(self, records: List[Dict[str, Any]]):
        """
        Load records into model.

        Args:
            records: List of record dicts from query results
        """
        logger.info(f"Loading {len(records)} records into PhotoGridModel")

        # Stop any ongoing cache warming from previous data
        if self.thumbnail_cache and hasattr(self.thumbnail_cache, 'stop_warming'):
            self.thumbnail_cache.stop_warming()

        # Cancel pending thumbnail generations from previous data
        if self.thumbnail_cache and hasattr(self.thumbnail_cache, 'cancel_all_generation'):
            self.thumbnail_cache.cancel_all_generation()

        # Clear memory thumbnail cache to force fresh thumbnails
        if self.thumbnail_cache:
            self.thumbnail_cache.clear_memory_cache()

        # Set resetting flag to prevent Qt crashes during model reset
        self._is_resetting = True

        self.beginResetModel()
        self.file_items = records

        # Build hash-to-index lookup for O(1) thumbnail ready notifications
        self._hash_to_index = {}
        for i, item in enumerate(records):
            file_hash = item.get('file_hash')
            if file_hash:
                self._hash_to_index[file_hash] = i

        self.endResetModel()

        self._is_resetting = False

        self.data_loaded.emit(len(records))
        logger.info(f"PhotoGridModel loaded {len(records)} records")

        # Start background cache warming for all items
        # This runs in a background thread and won't block the UI
        self._start_background_warming()

    def get_record_at(self, index: QModelIndex) -> Optional[Dict[str, Any]]:
        """Get record at model index."""
        if not index.isValid():
            return None

        row = index.row()
        if 0 <= row < len(self.file_items):
            return self.file_items[row]
        return None

    def get_record_by_hash(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Get record by file hash (O(1) lookup)."""
        row = self._hash_to_index.get(file_hash)
        if row is not None and 0 <= row < len(self.file_items):
            return self.file_items[row]
        return None

    def get_index_for_hash(self, file_hash: str) -> Optional[QModelIndex]:
        """Get model index for a file hash (O(1) lookup)."""
        row = self._hash_to_index.get(file_hash)
        if row is not None and 0 <= row < len(self.file_items):
            return self.index(row, 0)
        return None

    def set_thumbnail_size(self, size: int):
        """
        Set thumbnail size and refresh.

        Args:
            size: Thumbnail size in pixels
        """
        if size != self.thumbnail_size:
            self.thumbnail_size = size
            # Force refresh of all visible thumbnails
            if self.file_items:
                self.dataChanged.emit(
                    self.index(0, 0),
                    self.index(len(self.file_items) - 1, 0),
                    [Qt.DecorationRole]
                )

    def _on_thumbnail_ready(self, file_hash: str, size: int):
        """
        Handle thumbnail ready signal from cache.

        Updates the view when a thumbnail finishes loading.
        Uses O(1) hash lookup instead of linear search for performance.

        Args:
            file_hash: SHA-256 hash of the file
            size: Thumbnail size in pixels
        """
        # Skip if size doesn't match current display size
        if size != self.thumbnail_size:
            return

        # O(1) lookup using hash index
        row = self._hash_to_index.get(file_hash)
        if row is not None and 0 <= row < len(self.file_items):
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [Qt.DecorationRole])

    def refresh_thumbnail(self, file_hash: str):
        """
        Force refresh of a specific thumbnail (O(1) lookup).

        Args:
            file_hash: Hash of file to refresh
        """
        if self.thumbnail_cache:
            # Invalidate the cached thumbnail
            if hasattr(self.thumbnail_cache, 'invalidate_hash'):
                self.thumbnail_cache.invalidate_hash(file_hash)
            elif hasattr(self.thumbnail_cache, 'invalidate'):
                self.thumbnail_cache.invalidate(file_hash)

        # Find and update the item using hash index
        row = self._hash_to_index.get(file_hash)
        if row is not None and 0 <= row < len(self.file_items):
            index = self.index(row, 0)
            self.dataChanged.emit(index, index, [Qt.DecorationRole])

    def remove_items(self, file_hashes: List[str]):
        """
        Remove items by their file hashes.

        Args:
            file_hashes: List of file hashes to remove
        """
        hash_set = set(file_hashes)
        indices_to_remove = []

        # Use hash index for O(1) lookups
        for file_hash in file_hashes:
            row = self._hash_to_index.get(file_hash)
            if row is not None:
                indices_to_remove.append(row)
                # Remove from hash index
                del self._hash_to_index[file_hash]

        # Sort and remove in reverse order to maintain indices
        indices_to_remove.sort(reverse=True)
        for i in indices_to_remove:
            if 0 <= i < len(self.file_items):
                self.beginRemoveRows(QModelIndex(), i, i)
                del self.file_items[i]
                self.endRemoveRows()

        # Rebuild hash index after removals (indices have shifted)
        self._hash_to_index = {}
        for i, item in enumerate(self.file_items):
            file_hash = item.get('file_hash')
            if file_hash:
                self._hash_to_index[file_hash] = i

    def update_item(self, file_hash: str, updates: Dict[str, Any]):
        """
        Update an item's data (O(1) lookup).

        Args:
            file_hash: Hash of file to update
            updates: Dictionary of fields to update
        """
        row = self._hash_to_index.get(file_hash)
        if row is not None and 0 <= row < len(self.file_items):
            self.file_items[row].update(updates)
            index = self.index(row, 0)
            self.dataChanged.emit(index, index)

    def _start_background_warming(self):
        """
        Start background cache warming for loaded items.

        Uses a delayed start to let the UI settle first, then warms
        thumbnails gradually in the background without blocking.
        """
        if not self.thumbnail_cache:
            return

        if not self.file_items:
            return

        if not hasattr(self.thumbnail_cache, 'warm_cache_async'):
            logger.debug("Thumbnail cache doesn't support async warming")
            return

        # Prepare items for warming - need file_hash and file_path
        warming_items = []
        for item in self.file_items:
            file_hash = item.get('file_hash')
            file_path = item.get('archive_path') or item.get('source_path')
            if file_hash and file_path:
                warming_items.append({
                    'file_hash': file_hash,
                    'file_path': file_path
                })

        if not warming_items:
            return

        # Limit warming to prevent resource exhaustion
        # Start with first 2000 items - enough for most browsing sessions
        max_warming_items = 2000
        if len(warming_items) > max_warming_items:
            logger.info(f"Limiting cache warming to first {max_warming_items} of {len(warming_items)} items")
            warming_items = warming_items[:max_warming_items]

        # Use a timer to delay warming start, letting the UI render first
        from PySide6.QtCore import QTimer
        QTimer.singleShot(500, lambda: self._do_background_warming(warming_items))

    def _do_background_warming(self, warming_items):
        """Execute background warming after delay."""
        if not self.thumbnail_cache:
            return

        # Check if data has changed (user loaded different query)
        if not self.file_items:
            return

        logger.info(f"Starting background cache warming for {len(warming_items)} items")
        self.thumbnail_cache.warm_cache_async(warming_items, size=self.thumbnail_size)
