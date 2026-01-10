"""
Thumbnail Grid Model

QAbstractListModel for high-performance thumbnail grid.
Stores only metadata - thumbnails loaded on-demand by delegate.

Tracks marked items in memory for instant access.
"""

import logging
import os
import sys
from typing import List, Dict, Any, Set, Optional
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
from PySide6.QtGui import QPixmap

from DuplicateFileDetection import PhotoDatabase
from triage.triage_database import TriageDatabase
from triage.thumbnail_cache import ThumbnailCache

logger = logging.getLogger(__name__)


class ThumbnailGridModel(QAbstractListModel):
    """
    Data model for thumbnail grid.

    Stores only file metadata (file_hash, file_path, file_size).
    Thumbnails are loaded on-demand via Qt.DecorationRole.
    Tracks marked items in memory for fast access.

    Performance:
    - Can handle 100,000+ items (stores ~1KB per item)
    - Only visible items are rendered (delegate handles lazy loading)
    - Mark operations are O(1) (set-based tracking)
    """

    def __init__(self, thumbnail_cache: ThumbnailCache, db_path: str, parent=None):
        """
        Initialize model.

        Args:
            thumbnail_cache: ThumbnailCache instance for loading thumbnails
            db_path: Path to SQLite database
            parent: Parent QObject
        """
        super().__init__(parent)
        self.thumbnail_cache = thumbnail_cache
        self.db_path = db_path
        self.triage_db = TriageDatabase(db_path)

        # File data: List of dicts with keys: file_hash, file_path, file_size
        self.file_items: List[Dict[str, Any]] = []

        # Track marked items in memory (fast O(1) lookup)
        self.marked_for_deletion: Set[str] = set()
        self.marked_as_favorite: Set[str] = set()
        self.marked_for_date_correction: Set[str] = set()

        # Current thumbnail size
        self.thumbnail_size = 256  # Default: medium

        # Safety flag: prevent data access during model reset
        self._is_resetting = False

        # CRITICAL FIX: Create a null QPixmap to return for missing thumbnails
        # QPixmap() with no size creates a "null" pixmap (isNull() == True)
        # This is different from QPixmap(1,1) which creates a valid pixmap
        # Qt should handle null pixmaps properly
        self._null_pixmap = QPixmap()  # Creates null QPixmap
        logger.info(f"Model initialized - null pixmap isNull={self._null_pixmap.isNull()}")

        # Connect to cache's thumbnail_ready signal to update view when thumbnails load
        self.thumbnail_cache.thumbnail_ready.connect(self._on_thumbnail_ready)
        logger.info("Connected to thumbnail_ready signal")

    def rowCount(self, parent=QModelIndex()):
        """Return number of items."""
        if parent.isValid():
            return 0
        # Return 0 during reset to prevent Qt from trying to access invalid rows
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
        # CRITICAL DEBUGGING: Log BEFORE try block to catch earliest possible crash point
        logger.info(f"data() ENTRY - index.isValid()={index.isValid() if index else 'None'}, role={role}")

        try:
            # CRITICAL: Don't return full data while model is being reset
            # This prevents crashes when Qt calls data() during beginResetModel/endResetModel
            if self._is_resetting:
                logger.info("data() called while resetting - returning null pixmap")
                # Return null QPixmap for DecorationRole
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            # Validate index
            if not index or not index.isValid():
                logger.debug("data() called with invalid index - returning null pixmap")
                # Return null QPixmap for DecorationRole
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            row = index.row()

            # Validate row bounds
            if row < 0 or row >= len(self.file_items):
                logger.warning(f"data() called with out-of-bounds row: {row}/{len(self.file_items)} - returning null pixmap")
                # Return null QPixmap for DecorationRole
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            # Get item safely
            item = self.file_items[row]
            if not item:
                logger.warning(f"data() row {row} has no item - returning null pixmap")
                # Return null QPixmap for DecorationRole
                if role == Qt.DecorationRole:
                    return self._null_pixmap
                return None

            logger.debug(f"data() called for row {row}, role {role}")

            if role == Qt.DisplayRole:
                # Filename shown below thumbnail
                file_path = item.get('file_path', '')
                if file_path:
                    return os.path.basename(file_path)
                return "Unknown"

            elif role == Qt.DecorationRole:
                # Thumbnail pixmap (loaded from cache)
                file_hash = item.get('file_hash')
                file_path = item.get('file_path')
                if file_hash and file_path:
                    try:
                        pixmap = self.thumbnail_cache.get_thumbnail(
                            file_hash,
                            file_path,
                            size=self.thumbnail_size,
                            priority='high'  # Visible item
                        )

                        # CRITICAL: Validate QPixmap before returning
                        # Qt crashes with invalid pixmaps, use null QPixmap for missing thumbnails
                        if pixmap is None:
                            logger.debug(f"Cache returned None for {file_hash[:8]}... - returning null pixmap")
                            return self._null_pixmap

                        # Check if it's actually a QPixmap
                        if not isinstance(pixmap, QPixmap):
                            logger.error(f"Cache returned non-QPixmap object: {type(pixmap)} - returning null pixmap")
                            return self._null_pixmap

                        # Check if the QPixmap is null (invalid)
                        if pixmap.isNull():
                            logger.warning(f"Cache returned null QPixmap for {file_hash[:8]}... - returning null pixmap")
                            return self._null_pixmap

                        # Pixmap is valid - return it
                        logger.info(f"Returning valid pixmap for {file_hash[:8]}... size={pixmap.width()}x{pixmap.height()}")
                        return pixmap

                    except Exception as cache_error:
                        logger.error(f"Error getting thumbnail from cache: {cache_error} - returning null pixmap", exc_info=True)
                        return self._null_pixmap

                return self._null_pixmap

            elif role == Qt.UserRole:
                # Full item data
                return item

            elif role == Qt.UserRole + 1:
                # Mark flags (for overlay icons)
                file_hash = item.get('file_hash')
                if file_hash:
                    return {
                        'delete': file_hash in self.marked_for_deletion,
                        'favorite': file_hash in self.marked_as_favorite,
                        'date_correction': file_hash in self.marked_for_date_correction
                    }
                return {'delete': False, 'favorite': False, 'date_correction': False}

            elif role == Qt.ToolTipRole:
                # Show full path in tooltip
                return item.get('file_path', '')

            # Return null QPixmap for DecorationRole, None for other roles
            if role == Qt.DecorationRole:
                return self._null_pixmap
            return None

        except Exception as e:
            logger.error(f"Error in data() method for row {index.row() if index else '?'}, role {role}: {e}", exc_info=True)
            # Return null QPixmap for DecorationRole to keep Qt happy even on errors
            if role == Qt.DecorationRole:
                return self._null_pixmap
            return None

    def load_folder(self, folder_path: str, recursive: bool = False):
        """
        Load all images in archive folder from database.

        Args:
            folder_path: Path to folder (e.g., "/archive/2025/02/")
            recursive: If True, include subfolders

        Performance: 10,000 rows in ~100ms with idx_file_name_prefix
        """
        try:
            # CRITICAL: Cancel all pending thumbnail generation from previous folder
            # This prevents race conditions when switching folders
            if hasattr(self, 'thumbnail_cache') and self.thumbnail_cache:
                self.thumbnail_cache.cancel_all_generation()
                # Also clear memory cache to prevent showing stale thumbnails
                self.thumbnail_cache.clear_memory_cache()

            # Set flag to prevent data() from being called during reset
            self._is_resetting = True

            self.beginResetModel()
            self.file_items.clear()

            # Also clear marks (new folder = fresh start)
            self.marked_for_deletion.clear()
            self.marked_as_favorite.clear()
            self.marked_for_date_correction.clear()

            # Video extensions to filter out
            video_extensions = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv', '.MOV', '.MP4', '.AVI'}

            with PhotoDatabase(self.db_path) as db:
                if recursive:
                    # Recursive: all files under folder_path
                    query = """
                        SELECT file_hash, file_name, file_size
                        FROM UniquePhotos
                        WHERE file_name LIKE ?
                        ORDER BY file_name
                    """
                    params = (f"{folder_path}%",)
                else:
                    # Non-recursive: only files directly in folder_path
                    # file_name LIKE '/archive/2025/02/%'
                    # file_name NOT LIKE '/archive/2025/02/%/%' (excludes subfolders)
                    query = """
                        SELECT file_hash, file_name, file_size
                        FROM UniquePhotos
                        WHERE file_name LIKE ?
                          AND file_name NOT LIKE ?
                        ORDER BY file_name
                    """
                    # Ensure folder path ends with /
                    if not folder_path.endswith('/'):
                        folder_path += '/'
                    params = (f"{folder_path}%", f"{folder_path}%/%")

                db.cursor.execute(query, params)

                # Filter out video files
                videos_filtered = 0
                for row in db.cursor.fetchall():
                    file_path = row[1]
                    file_ext = os.path.splitext(file_path)[1]

                    # Skip video files
                    if file_ext in video_extensions:
                        videos_filtered += 1
                        continue

                    self.file_items.append({
                        'file_hash': row[0],
                        'file_path': file_path,
                        'file_size': row[2]
                    })

                if videos_filtered > 0:
                    logger.info(f"Filtered out {videos_filtered} video files")

            # Load existing marks from database
            self._load_existing_marks()

            self.endResetModel()

            # Clear resetting flag AFTER endResetModel
            self._is_resetting = False

            if videos_filtered > 0:
                logger.info(f"Loaded {len(self.file_items)} images from {folder_path} ({videos_filtered} videos filtered)")
            else:
                logger.info(f"Loaded {len(self.file_items)} images from {folder_path}")

        except Exception as e:
            # Make sure to call endResetModel even on error
            self.endResetModel()
            # Clear resetting flag even on error
            self._is_resetting = False
            logger.error(f"Error loading folder {folder_path}: {e}", exc_info=True)
            raise  # Re-raise to be caught by caller

    def _load_existing_marks(self):
        """Load existing marks from database into memory sets."""
        # Get all active marks
        for action_type in ('delete', 'favorite', 'date_correction'):
            marked_hashes = self.triage_db.get_marked_hashes(action_type)

            # Add to appropriate set
            if action_type == 'delete':
                self.marked_for_deletion.update(marked_hashes)
            elif action_type == 'favorite':
                self.marked_as_favorite.update(marked_hashes)
            elif action_type == 'date_correction':
                self.marked_for_date_correction.update(marked_hashes)

        logger.debug(f"Loaded marks: delete={len(self.marked_for_deletion)}, "
                    f"favorite={len(self.marked_as_favorite)}, "
                    f"date_correction={len(self.marked_for_date_correction)}")

    def _on_thumbnail_ready(self, file_hash: str, size: int):
        """
        Handle thumbnail_ready signal from cache.

        Called when a thumbnail finishes generating and is added to cache.
        Notifies the view to repaint the item.

        Args:
            file_hash: SHA-256 hash of file
            size: Thumbnail size (should match current thumbnail_size)
        """
        try:
            logger.info(f"_on_thumbnail_ready: {file_hash[:8]}... size={size}")

            # Only process if size matches current thumbnail size
            if size != self.thumbnail_size:
                logger.debug(f"Ignoring thumbnail_ready for size {size} (current size is {self.thumbnail_size})")
                return

            # Find the row for this file hash
            row = None
            for idx, item in enumerate(self.file_items):
                if item.get('file_hash') == file_hash:
                    row = idx
                    break

            if row is not None:
                # Emit dataChanged for this item to trigger repaint
                index = self.index(row, 0)
                logger.info(f"Emitting dataChanged for row {row} (file {file_hash[:8]}...)")
                self.dataChanged.emit(index, index, [Qt.DecorationRole])
            else:
                logger.debug(f"File hash {file_hash[:8]}... not in current folder (thumbnail may be from previous folder)")

        except Exception as e:
            logger.error(f"Error in _on_thumbnail_ready: {e}", exc_info=True)

    def mark_file(self, file_hash: str, action_type: str, notes: str = None):
        """
        Mark file for action.

        Writes to database and updates in-memory tracking.

        Args:
            file_hash: SHA-256 hash
            action_type: 'delete', 'favorite', or 'date_correction'
            notes: Optional notes
        """
        # Write to database
        self.triage_db.mark_file(file_hash, action_type, notes)

        # Update in-memory tracking
        if action_type == 'delete':
            self.marked_for_deletion.add(file_hash)
        elif action_type == 'favorite':
            self.marked_as_favorite.add(file_hash)
        elif action_type == 'date_correction':
            self.marked_for_date_correction.add(file_hash)

        # Notify view to redraw item
        self._emit_item_changed(file_hash)

    def unmark_file(self, file_hash: str, action_type: str):
        """
        Unmark file (undo action).

        Args:
            file_hash: SHA-256 hash
            action_type: 'delete', 'favorite', or 'date_correction'
        """
        # Write to database
        self.triage_db.unmark_file(file_hash, action_type)

        # Update in-memory tracking
        if action_type == 'delete':
            self.marked_for_deletion.discard(file_hash)
        elif action_type == 'favorite':
            self.marked_as_favorite.discard(file_hash)
        elif action_type == 'date_correction':
            self.marked_for_date_correction.discard(file_hash)

        # Notify view to redraw item
        self._emit_item_changed(file_hash)

    def toggle_mark(self, file_hash: str, action_type: str):
        """
        Toggle mark for file.

        Args:
            file_hash: SHA-256 hash
            action_type: 'delete', 'favorite', or 'date_correction'
        """
        # Check if already marked
        is_marked = False
        if action_type == 'delete':
            is_marked = file_hash in self.marked_for_deletion
        elif action_type == 'favorite':
            is_marked = file_hash in self.marked_as_favorite
        elif action_type == 'date_correction':
            is_marked = file_hash in self.marked_for_date_correction

        # Toggle
        if is_marked:
            self.unmark_file(file_hash, action_type)
        else:
            self.mark_file(file_hash, action_type)

    def _emit_item_changed(self, file_hash: str):
        """
        Emit dataChanged signal for item with given hash.

        Args:
            file_hash: SHA-256 hash of file
        """
        # Find row index for this hash
        for row, item in enumerate(self.file_items):
            if item['file_hash'] == file_hash:
                index = self.index(row, 0)
                # Emit dataChanged for mark flags role
                self.dataChanged.emit(index, index, [Qt.UserRole + 1])
                break

    def get_item(self, row: int) -> Optional[Dict[str, Any]]:
        """
        Get item at row.

        Args:
            row: Row index

        Returns:
            Item dict or None if invalid row
        """
        if 0 <= row < len(self.file_items):
            return self.file_items[row]
        return None

    def get_marked_items(self, action_type: str = None) -> List[Dict[str, Any]]:
        """
        Get all marked items.

        Args:
            action_type: Filter by type ('delete', 'favorite', 'date_correction')
                        or None for all types

        Returns:
            List of item dicts
        """
        marked_items = []

        # Determine which set to use
        if action_type == 'delete':
            marked_hashes = self.marked_for_deletion
        elif action_type == 'favorite':
            marked_hashes = self.marked_as_favorite
        elif action_type == 'date_correction':
            marked_hashes = self.marked_for_date_correction
        else:
            # All types
            marked_hashes = (self.marked_for_deletion |
                           self.marked_as_favorite |
                           self.marked_for_date_correction)

        # Find items with these hashes
        for item in self.file_items:
            if item['file_hash'] in marked_hashes:
                marked_items.append(item)

        return marked_items

    def set_thumbnail_size(self, size: int):
        """
        Change thumbnail size.

        Args:
            size: Size in pixels (128, 256, 512, or 1024)
        """
        if size != self.thumbnail_size:
            self.thumbnail_size = size

            # Notify view to reload all decorations (thumbnails)
            if len(self.file_items) > 0:
                top_left = self.index(0, 0)
                bottom_right = self.index(len(self.file_items) - 1, 0)
                self.dataChanged.emit(top_left, bottom_right, [Qt.DecorationRole])

            logger.info(f"Thumbnail size changed to {size}px")


if __name__ == '__main__':
    # Test model
    import tempfile
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # Create test database with some files
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    try:
        # Initialize database
        from DuplicateFileDetection import PhotoDatabase
        from triage.triage_database import TriageDatabase

        triage_db = TriageDatabase(test_db_path)
        triage_db.ensure_triage_tables()

        # Add some test files
        with PhotoDatabase(test_db_path) as db:
            db.initialize_database()

            # Insert test files
            for i in range(10):
                db.cursor.execute("""
                    INSERT INTO UniquePhotos
                    (file_hash, file_name, file_size, create_year, create_month, create_day)
                    VALUES (?, ?, ?, '2025', '02', '15')
                """, (f"hash_{i:03d}", f"/archive/2025/02/15/test_{i:03d}.jpg", 1000000 + i))
            db.commit()

        # Create cache
        cache_dir = Path(tempfile.gettempdir()) / 'test_model_cache'
        cache = ThumbnailCache(test_db_path, str(cache_dir), memory_size=10)

        # Create model
        model = ThumbnailGridModel(cache, test_db_path)

        # Load folder
        print("\n1. Loading folder...")
        model.load_folder("/archive/2025/02/15/", recursive=False)
        print(f"   Loaded {model.rowCount()} items")

        # Get some data
        print("\n2. Getting data for first item...")
        index = model.index(0, 0)
        filename = model.data(index, Qt.DisplayRole)
        item = model.data(index, Qt.UserRole)
        print(f"   Filename: {filename}")
        print(f"   File hash: {item['file_hash']}")

        # Mark a file
        print("\n3. Marking file for deletion...")
        model.mark_file(item['file_hash'], 'delete')
        marks = model.data(index, Qt.UserRole + 1)
        print(f"   Marks: {marks}")
        assert marks['delete'] == True

        # Toggle mark
        print("\n4. Toggling mark...")
        model.toggle_mark(item['file_hash'], 'delete')
        marks = model.data(index, Qt.UserRole + 1)
        print(f"   Marks: {marks}")
        assert marks['delete'] == False

        # Get marked items
        print("\n5. Marking multiple files...")
        for i in range(3):
            item = model.get_item(i)
            model.mark_file(item['file_hash'], 'favorite')

        marked = model.get_marked_items('favorite')
        print(f"   Marked {len(marked)} items as favorite")
        assert len(marked) == 3

        print("\n✓ All tests passed!")

    finally:
        # Cleanup
        import shutil
        if os.path.exists(test_db_path):
            os.remove(test_db_path)
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        print("Cleaned up test files")
