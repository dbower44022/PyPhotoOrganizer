"""
Cache Statistics Dialog

Displays thumbnail cache performance statistics:
- Hit rates (memory, disk, miss)
- Cache sizes
- Generation status
- Disk usage
"""

import logging
from pathlib import Path

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QGroupBox, QGridLayout, QPushButton, QProgressBar,
                               QMessageBox)
from PySide6.QtCore import Qt, QTimer

logger = logging.getLogger(__name__)


class CacheStatsDialog(QDialog):
    """
    Dialog to display thumbnail cache statistics.

    Shows:
    - Memory cache hit rate
    - Disk cache hit rate
    - Miss rate
    - Cache sizes
    - Background generation status
    - Disk usage
    """

    def __init__(self, thumbnail_cache, parent=None):
        """
        Initialize cache statistics dialog.

        Args:
            thumbnail_cache: ThumbnailCache instance
            parent: Parent widget
        """
        super().__init__(parent)

        self.thumbnail_cache = thumbnail_cache

        self.setWindowTitle("Cache Statistics")
        self.setModal(False)
        self.resize(500, 400)

        self._create_ui()

        # Auto-refresh every 2 seconds
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_stats)
        self.refresh_timer.start(2000)

        # Initial refresh
        self._refresh_stats()

    def _create_ui(self):
        """Create UI layout."""
        layout = QVBoxLayout(self)

        # Hit rates group
        hit_rates_group = QGroupBox("Hit Rates")
        hit_rates_layout = QGridLayout(hit_rates_group)

        # Memory hits
        hit_rates_layout.addWidget(QLabel("Memory Hits:"), 0, 0)
        self.memory_hits_label = QLabel("0")
        self.memory_hits_label.setAlignment(Qt.AlignRight)
        hit_rates_layout.addWidget(self.memory_hits_label, 0, 1)

        self.memory_hit_rate_label = QLabel("(0.0%)")
        self.memory_hit_rate_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        hit_rates_layout.addWidget(self.memory_hit_rate_label, 0, 2)

        self.memory_hit_bar = QProgressBar()
        self.memory_hit_bar.setMaximum(100)
        hit_rates_layout.addWidget(self.memory_hit_bar, 0, 3)

        # Disk hits
        hit_rates_layout.addWidget(QLabel("Disk Hits:"), 1, 0)
        self.disk_hits_label = QLabel("0")
        self.disk_hits_label.setAlignment(Qt.AlignRight)
        hit_rates_layout.addWidget(self.disk_hits_label, 1, 1)

        self.disk_hit_rate_label = QLabel("(0.0%)")
        self.disk_hit_rate_label.setStyleSheet("color: #2196F3; font-weight: bold;")
        hit_rates_layout.addWidget(self.disk_hit_rate_label, 1, 2)

        self.disk_hit_bar = QProgressBar()
        self.disk_hit_bar.setMaximum(100)
        hit_rates_layout.addWidget(self.disk_hit_bar, 1, 3)

        # Misses
        hit_rates_layout.addWidget(QLabel("Misses:"), 2, 0)
        self.misses_label = QLabel("0")
        self.misses_label.setAlignment(Qt.AlignRight)
        hit_rates_layout.addWidget(self.misses_label, 2, 1)

        self.miss_rate_label = QLabel("(0.0%)")
        self.miss_rate_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        hit_rates_layout.addWidget(self.miss_rate_label, 2, 2)

        self.miss_bar = QProgressBar()
        self.miss_bar.setMaximum(100)
        hit_rates_layout.addWidget(self.miss_bar, 2, 3)

        # Total requests
        hit_rates_layout.addWidget(QLabel("Total Requests:"), 3, 0)
        self.total_requests_label = QLabel("0")
        self.total_requests_label.setAlignment(Qt.AlignRight)
        self.total_requests_label.setStyleSheet("font-weight: bold;")
        hit_rates_layout.addWidget(self.total_requests_label, 3, 1, 1, 3)

        layout.addWidget(hit_rates_group)

        # Generation status group
        gen_group = QGroupBox("Generation Status")
        gen_layout = QGridLayout(gen_group)

        gen_layout.addWidget(QLabel("Generated:"), 0, 0)
        self.generated_label = QLabel("0")
        self.generated_label.setAlignment(Qt.AlignRight)
        gen_layout.addWidget(self.generated_label, 0, 1)

        gen_layout.addWidget(QLabel("Currently Generating:"), 1, 0)
        self.generating_label = QLabel("0")
        self.generating_label.setAlignment(Qt.AlignRight)
        gen_layout.addWidget(self.generating_label, 1, 1)

        gen_layout.addWidget(QLabel("Errors:"), 2, 0)
        self.errors_label = QLabel("0")
        self.errors_label.setAlignment(Qt.AlignRight)
        gen_layout.addWidget(self.errors_label, 2, 1)

        layout.addWidget(gen_group)

        # Cache size group
        size_group = QGroupBox("Cache Sizes")
        size_layout = QGridLayout(size_group)

        size_layout.addWidget(QLabel("Memory Cache:"), 0, 0)
        self.memory_size_label = QLabel("0 items")
        self.memory_size_label.setAlignment(Qt.AlignRight)
        size_layout.addWidget(self.memory_size_label, 0, 1)

        size_layout.addWidget(QLabel("Disk Cache:"), 1, 0)
        self.disk_size_label = QLabel("Calculating...")
        self.disk_size_label.setAlignment(Qt.AlignRight)
        size_layout.addWidget(self.disk_size_label, 1, 1)

        layout.addWidget(size_group)

        # Buttons
        button_layout = QHBoxLayout()

        refresh_btn = QPushButton("Refresh Now")
        refresh_btn.clicked.connect(self._refresh_stats)
        button_layout.addWidget(refresh_btn)

        reset_btn = QPushButton("Reset Statistics")
        reset_btn.clicked.connect(self._reset_stats)
        button_layout.addWidget(reset_btn)

        cleanup_btn = QPushButton("Clean Disk Cache")
        cleanup_btn.setToolTip("Remove old thumbnails from disk cache (LRU)")
        cleanup_btn.clicked.connect(self._cleanup_cache)
        button_layout.addWidget(cleanup_btn)

        clear_btn = QPushButton("Clear All Cache")
        clear_btn.setToolTip("Delete ALL cached thumbnails (memory + disk)")
        clear_btn.clicked.connect(self._clear_all_cache)
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)

        layout.addLayout(button_layout)

    def _refresh_stats(self):
        """Refresh statistics display."""
        try:
            stats = self.thumbnail_cache.get_statistics()

            # Hit rates
            self.memory_hits_label.setText(f"{stats['memory_hits']:,}")
            self.memory_hit_rate_label.setText(f"({stats['memory_hit_rate']:.1f}%)")
            self.memory_hit_bar.setValue(int(stats['memory_hit_rate']))

            self.disk_hits_label.setText(f"{stats['disk_hits']:,}")
            self.disk_hit_rate_label.setText(f"({stats['disk_hit_rate']:.1f}%)")
            self.disk_hit_bar.setValue(int(stats['disk_hit_rate']))

            self.misses_label.setText(f"{stats['misses']:,}")
            self.miss_rate_label.setText(f"({stats['miss_rate']:.1f}%)")
            self.miss_bar.setValue(int(stats['miss_rate']))

            self.total_requests_label.setText(f"{stats['total_requests']:,}")

            # Generation status
            self.generated_label.setText(f"{stats['generated']:,}")
            self.generating_label.setText(f"{stats['generating']:,}")
            self.errors_label.setText(f"{stats['errors']:,}")

            # Cache sizes
            self.memory_size_label.setText(
                f"{stats['memory_size']} items (max {self.thumbnail_cache.memory_size})"
            )

            # Calculate disk cache size
            disk_size = self._calculate_disk_size()
            disk_size_mb = disk_size / (1024 * 1024)
            disk_size_gb = disk_size / (1024 * 1024 * 1024)
            max_size_gb = self.thumbnail_cache.disk_size_bytes / (1024 * 1024 * 1024)

            if disk_size_gb > 0.1:
                self.disk_size_label.setText(f"{disk_size_gb:.2f} GB (max {max_size_gb:.1f} GB)")
            else:
                self.disk_size_label.setText(f"{disk_size_mb:.1f} MB (max {max_size_gb:.1f} GB)")

        except Exception as e:
            logger.error(f"Error refreshing stats: {e}", exc_info=True)

    def _calculate_disk_size(self):
        """Calculate total disk cache size in bytes."""
        total_size = 0
        cache_dir = self.thumbnail_cache.cache_dir

        if cache_dir.exists():
            for file_path in cache_dir.rglob('*.jpg'):
                try:
                    total_size += file_path.stat().st_size
                except OSError:
                    pass

        return total_size

    def _reset_stats(self):
        """Reset cache statistics."""
        reply = QMessageBox.question(
            self,
            "Reset Statistics",
            "Reset all cache statistics?\n\n"
            "This will not clear the cache, only reset counters.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            # Reset stats
            self.thumbnail_cache.stats = {
                'memory_hits': 0,
                'disk_hits': 0,
                'misses': 0,
                'generated': 0,
                'errors': 0
            }

            self._refresh_stats()

    def _cleanup_cache(self):
        """Clean up disk cache using LRU eviction."""
        # Calculate current disk size
        current_size = self._calculate_disk_size()
        current_size_mb = current_size / (1024 * 1024)
        max_size_bytes = self.thumbnail_cache.disk_size_bytes
        max_size_gb = max_size_bytes / (1024 * 1024 * 1024)

        if current_size <= max_size_bytes:
            QMessageBox.information(
                self,
                "Cache OK",
                f"Disk cache is under the limit.\n\n"
                f"Current: {current_size_mb:.1f} MB\n"
                f"Limit: {max_size_gb:.1f} GB\n\n"
                f"No cleanup needed."
            )
            return

        reply = QMessageBox.question(
            self,
            "Clean Disk Cache",
            f"Clean disk cache using LRU (least recently used) eviction?\n\n"
            f"Current size: {current_size_mb:.1f} MB\n"
            f"Target size: {max_size_gb * 0.9:.1f} GB (90% of limit)\n\n"
            f"This will delete oldest thumbnails until cache is under limit.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Use database cleanup method
                deleted_count = self.thumbnail_cache.triage_db.cleanup_lru_thumbnails(max_size_bytes)

                new_size = self._calculate_disk_size()
                new_size_mb = new_size / (1024 * 1024)

                QMessageBox.information(
                    self,
                    "Cleanup Complete",
                    f"Deleted {deleted_count} thumbnails.\n\n"
                    f"Old size: {current_size_mb:.1f} MB\n"
                    f"New size: {new_size_mb:.1f} MB\n"
                    f"Saved: {(current_size - new_size) / (1024 * 1024):.1f} MB"
                )

                self._refresh_stats()

            except Exception as e:
                logger.error(f"Cleanup failed: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Cleanup Error",
                    f"Failed to clean disk cache:\n{e}"
                )

    def _clear_all_cache(self):
        """Clear entire cache (memory + disk)."""
        # Calculate current sizes
        memory_items = len(self.thumbnail_cache.memory_cache)
        disk_size = self._calculate_disk_size()
        disk_size_mb = disk_size / (1024 * 1024)

        reply = QMessageBox.warning(
            self,
            "Clear All Cache",
            f"Delete ALL cached thumbnails?\n\n"
            f"Memory: {memory_items} items\n"
            f"Disk: {disk_size_mb:.1f} MB\n\n"
            f"⚠️ This will delete all thumbnails.\n"
            f"They will be regenerated on demand.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Clear memory cache
                self.thumbnail_cache.memory_cache.clear()
                logger.info(f"Cleared memory cache ({memory_items} items)")

                # Clear disk cache
                deleted_count = 0
                cache_dir = self.thumbnail_cache.cache_dir

                if cache_dir.exists():
                    for file_path in cache_dir.rglob('*.jpg'):
                        try:
                            file_path.unlink()
                            deleted_count += 1
                        except OSError as e:
                            logger.warning(f"Failed to delete {file_path}: {e}")

                # Clear database records
                from DuplicateFileDetection import PhotoDatabase
                with PhotoDatabase(self.thumbnail_cache.db_path) as db:
                    db.cursor.execute("DELETE FROM ThumbnailCache")
                    db.commit()

                logger.info(f"Cleared disk cache ({deleted_count} files)")

                QMessageBox.information(
                    self,
                    "Cache Cleared",
                    f"Cleared all cache data.\n\n"
                    f"Memory: {memory_items} items\n"
                    f"Disk: {deleted_count} files ({disk_size_mb:.1f} MB)\n\n"
                    f"Thumbnails will be regenerated as needed."
                )

                self._refresh_stats()

            except Exception as e:
                logger.error(f"Clear cache failed: {e}", exc_info=True)
                QMessageBox.critical(
                    self,
                    "Clear Cache Error",
                    f"Failed to clear cache:\n{e}"
                )

    def closeEvent(self, event):
        """Stop refresh timer when dialog closes."""
        self.refresh_timer.stop()
        event.accept()


if __name__ == '__main__':
    from PySide6.QtWidgets import QApplication
    import sys

    # Test dialog (requires ThumbnailCache instance)
    app = QApplication(sys.argv)

    # Mock cache for testing
    class MockCache:
        def __init__(self):
            self.memory_size = 500
            self.disk_size_bytes = 5 * 1024 * 1024 * 1024
            self.cache_dir = Path('/tmp/test_cache')
            self.stats = {
                'memory_hits': 1234,
                'disk_hits': 567,
                'misses': 89,
                'generated': 45,
                'errors': 2
            }

        def get_statistics(self):
            total = self.stats['memory_hits'] + self.stats['disk_hits'] + self.stats['misses']
            return {
                'memory_hits': self.stats['memory_hits'],
                'disk_hits': self.stats['disk_hits'],
                'misses': self.stats['misses'],
                'generated': self.stats['generated'],
                'errors': self.stats['errors'],
                'memory_hit_rate': self.stats['memory_hits'] / total * 100 if total > 0 else 0,
                'disk_hit_rate': self.stats['disk_hits'] / total * 100 if total > 0 else 0,
                'miss_rate': self.stats['misses'] / total * 100 if total > 0 else 0,
                'total_requests': total,
                'memory_size': 345,
                'generating': 3
            }

    cache = MockCache()
    dialog = CacheStatsDialog(cache)
    dialog.show()

    sys.exit(app.exec())
