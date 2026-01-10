"""
Grid Performance Test Script

Tests the thumbnail grid view with 1,000+ test images to validate:
- Virtual scrolling performance (target: 60 FPS)
- Memory usage (target: <500MB)
- Cache hit rates
- Keyboard shortcuts
- Marking operations
"""

import logging
import os
import sys
import tempfile
import time
import shutil
from pathlib import Path
from datetime import datetime

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QPushButton, QLabel, QHBoxLayout
from PySide6.QtCore import Qt, QTimer

from DuplicateFileDetection import PhotoDatabase
from triage.triage_database import TriageDatabase
from triage.thumbnail_cache import ThumbnailCache
from triage.ui.thumbnail_grid_model import ThumbnailGridModel
from triage.ui.thumbnail_grid_view import ThumbnailGridView

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PerformanceTestWindow(QMainWindow):
    """
    Test window with grid view and performance metrics display.
    """

    def __init__(self, model: ThumbnailGridModel, cache: ThumbnailCache, test_count: int):
        super().__init__()
        self.grid_model = model
        self.cache = cache
        self.test_count = test_count

        self.setWindowTitle(f"Grid Performance Test - {test_count} Items")
        self.resize(1400, 900)

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Top controls
        controls_layout = QHBoxLayout()

        # Size buttons
        btn_small = QPushButton("Small (1)")
        btn_small.clicked.connect(lambda: self.grid_view.set_thumbnail_size('small'))
        controls_layout.addWidget(btn_small)

        btn_medium = QPushButton("Medium (2)")
        btn_medium.clicked.connect(lambda: self.grid_view.set_thumbnail_size('medium'))
        controls_layout.addWidget(btn_medium)

        btn_large = QPushButton("Large (3)")
        btn_large.clicked.connect(lambda: self.grid_view.set_thumbnail_size('large'))
        controls_layout.addWidget(btn_large)

        controls_layout.addStretch()

        # Stats button
        btn_stats = QPushButton("Show Cache Stats")
        btn_stats.clicked.connect(self.show_cache_stats)
        controls_layout.addWidget(btn_stats)

        # Memory button
        btn_memory = QPushButton("Check Memory")
        btn_memory.clicked.connect(self.show_memory_usage)
        controls_layout.addWidget(btn_memory)

        layout.addLayout(controls_layout)

        # Stats label
        self.stats_label = QLabel("Ready. Use keyboard shortcuts: D=delete, F=favorite, C=date_correction, 1/2/3=size")
        self.stats_label.setStyleSheet("padding: 10px; background-color: #f0f0f0;")
        layout.addWidget(self.stats_label)

        # Create grid view
        self.grid_view = ThumbnailGridView(model)
        layout.addWidget(self.grid_view)

        # Connect signals
        self.grid_view.selection_changed.connect(self.on_selection_changed)
        self.grid_view.item_activated.connect(self.on_item_activated)

        # Instructions label
        instructions = QLabel(
            "Instructions:\n"
            "  D: Toggle delete mark | F: Toggle favorite mark | C: Flag for date correction\n"
            "  1/2/3: Change grid size | Space: Activate item | Arrows: Navigate\n"
            "  Ctrl+A: Select all | Escape: Clear selection"
        )
        instructions.setStyleSheet("padding: 10px; background-color: #e0e0e0; font-family: monospace;")
        layout.addWidget(instructions)

        # Performance timer
        self.last_scroll_time = time.perf_counter()
        self.scroll_count = 0

        logger.info("Test window initialized")

    def on_selection_changed(self, selected_hashes):
        """Update stats when selection changes."""
        count = len(selected_hashes)
        marked_delete = len(self.grid_model.marked_for_deletion)
        marked_favorite = len(self.grid_model.marked_as_favorite)
        marked_date = len(self.grid_model.marked_for_date_correction)

        self.stats_label.setText(
            f"Selected: {count} | "
            f"Marked for deletion: {marked_delete} | "
            f"Favorites: {marked_favorite} | "
            f"Date corrections: {marked_date}"
        )

    def on_item_activated(self, file_hash):
        """Handle item activation."""
        logger.info(f"Item activated: {file_hash[:16]}...")

    def show_cache_stats(self):
        """Display cache statistics."""
        stats = self.cache.get_stats()

        msg = (
            f"Cache Statistics:\n\n"
            f"Total requests: {stats['total_requests']}\n"
            f"Memory hits: {stats['memory_hits']} ({stats['memory_hit_rate']:.1f}%)\n"
            f"Disk hits: {stats['disk_hits']} ({stats['disk_hit_rate']:.1f}%)\n"
            f"Misses: {stats['misses']} ({stats['miss_rate']:.1f}%)\n"
            f"Generated: {stats['generated']}\n"
            f"Errors: {stats['errors']}\n\n"
            f"Memory cache size: {stats['memory_size']}\n"
            f"Currently generating: {stats['generating']}"
        )

        self.stats_label.setText(msg.replace('\n', ' | '))
        logger.info(msg)

    def show_memory_usage(self):
        """Display memory usage (requires psutil)."""
        try:
            import psutil
            process = psutil.Process()
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024

            msg = f"Memory usage: {mem_mb:.1f} MB (RSS)"
            self.stats_label.setText(msg)
            logger.info(msg)

            if mem_mb > 500:
                logger.warning(f"Memory usage exceeds 500MB target: {mem_mb:.1f}MB")
            else:
                logger.info(f"✓ Memory usage within target: {mem_mb:.1f}MB < 500MB")

        except ImportError:
            msg = "psutil not installed - cannot check memory usage"
            self.stats_label.setText(msg)
            logger.warning(msg)


def create_test_database(db_path: str, test_count: int = 1000, create_images: bool = True):
    """
    Create test database with mock photo entries.

    Args:
        db_path: Path to database file
        test_count: Number of test files to create (default: 1000)
        create_images: If True, create actual image files (default: True)
    """
    logger.info(f"Creating test database with {test_count} files...")

    # Create temp directory for test images
    test_images_dir = None
    if create_images:
        from PIL import Image, ImageDraw, ImageFont
        test_images_dir = Path(tempfile.gettempdir()) / 'test_triage_images'
        test_images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Creating test images in: {test_images_dir}")

    # Create UniquePhotos table FIRST
    with PhotoDatabase(db_path) as db:
        db.initialize_database()

        # Insert test files spread across multiple dates
        batch_size = 100
        for i in range(test_count):
            # Spread files across 10 days
            day = (i % 10) + 1
            file_hash = f"test_hash_{i:06d}"

            if create_images:
                # Use actual temp directory path
                file_name = str(test_images_dir / f"test_photo_{i:06d}.jpg")

                # Create actual image file if it doesn't exist
                if not os.path.exists(file_name):
                    # Create colorful test image
                    img = Image.new('RGB', (800, 600),
                                   color=(
                                       (i * 37) % 256,  # Red
                                       (i * 73) % 256,  # Green
                                       (i * 113) % 256  # Blue
                                   ))

                    # Add text overlay with image number
                    draw = ImageDraw.Draw(img)
                    text = f"Test Image #{i:06d}"

                    # Draw text in center
                    try:
                        # Try to use a larger font
                        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
                    except:
                        # Fallback to default font
                        font = ImageFont.load_default()

                    # Get text bounding box
                    bbox = draw.textbbox((0, 0), text, font=font)
                    text_width = bbox[2] - bbox[0]
                    text_height = bbox[3] - bbox[1]

                    # Center text
                    x = (800 - text_width) // 2
                    y = (600 - text_height) // 2

                    # Draw white text with black outline
                    draw.text((x-1, y-1), text, fill='black', font=font)
                    draw.text((x+1, y-1), text, fill='black', font=font)
                    draw.text((x-1, y+1), text, fill='black', font=font)
                    draw.text((x+1, y+1), text, fill='black', font=font)
                    draw.text((x, y), text, fill='white', font=font)

                    # Save image
                    img.save(file_name, 'JPEG', quality=85)
            else:
                # Use fake path (won't actually load)
                file_name = f"/archive/2025/02/{day:02d}/test_photo_{i:06d}.jpg"

            file_size = os.path.getsize(file_name) if create_images and os.path.exists(file_name) else 1000000 + (i * 1000)

            db.cursor.execute("""
                INSERT INTO UniquePhotos
                (file_hash, file_name, file_size, create_year, create_month, create_day)
                VALUES (?, ?, ?, '2025', '02', ?)
            """, (file_hash, file_name, file_size, f"{day:02d}"))

            # Commit every batch_size entries
            if (i + 1) % batch_size == 0:
                db.commit()
                if create_images:
                    logger.info(f"Created {i + 1}/{test_count} test images...")
                else:
                    logger.debug(f"Inserted {i + 1}/{test_count} files")

        db.commit()

    # Then initialize triage tables (they reference UniquePhotos)
    triage_db = TriageDatabase(db_path)
    triage_db.ensure_triage_tables()

    logger.info(f"✓ Created database with {test_count} test files")
    if create_images:
        logger.info(f"✓ Test images directory: {test_images_dir}")

    return test_images_dir


def run_performance_tests(model: ThumbnailGridModel, cache: ThumbnailCache, test_images_dir: Path):
    """
    Run automated performance tests.

    Args:
        model: ThumbnailGridModel instance
        cache: ThumbnailCache instance
        test_images_dir: Path to test images directory
    """
    logger.info("="* 80)
    logger.info("RUNNING PERFORMANCE TESTS")
    logger.info("="* 80)

    # Test 1: Load time
    logger.info("\n1. Testing folder load time...")
    start = time.perf_counter()
    # Use the actual temp directory path (load all files in that directory)
    model.load_folder(str(test_images_dir), recursive=False)
    elapsed = time.perf_counter() - start
    logger.info(f"   Loaded {model.rowCount()} items in {elapsed*1000:.1f}ms")

    if elapsed < 0.2:
        logger.info(f"   ✓ Load time within target: {elapsed*1000:.1f}ms < 200ms")
    else:
        logger.warning(f"   ✗ Load time exceeds target: {elapsed*1000:.1f}ms > 200ms")

    # Test 2: Random access speed (simulates scrolling)
    logger.info("\n2. Testing random access speed (100 items)...")
    import random
    start = time.perf_counter()
    for _ in range(100):
        row = random.randint(0, model.rowCount() - 1)
        index = model.index(row, 0)
        _ = model.data(index, Qt.DisplayRole)
        _ = model.data(index, Qt.DecorationRole)  # Get thumbnail
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / 100) * 1000

    logger.info(f"   100 random accesses in {elapsed*1000:.1f}ms")
    logger.info(f"   Average: {avg_ms:.2f}ms per item")

    if avg_ms < 5:
        logger.info(f"   ✓ Access time within target: {avg_ms:.2f}ms < 5ms")
    else:
        logger.warning(f"   ✗ Access time exceeds target: {avg_ms:.2f}ms > 5ms")

    # Test 3: Sequential access (simulates smooth scrolling)
    logger.info("\n3. Testing sequential access (500 items)...")
    start = time.perf_counter()
    for row in range(min(500, model.rowCount())):
        index = model.index(row, 0)
        _ = model.data(index, Qt.DisplayRole)
        _ = model.data(index, Qt.DecorationRole)
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / 500) * 1000

    logger.info(f"   500 sequential accesses in {elapsed*1000:.1f}ms")
    logger.info(f"   Average: {avg_ms:.2f}ms per item")

    # 60 FPS = 16.67ms per frame, assume 20 items visible
    target_per_item = 16.67 / 20  # ~0.83ms per item
    if avg_ms < target_per_item:
        logger.info(f"   ✓ Sequential access within 60 FPS target: {avg_ms:.2f}ms < {target_per_item:.2f}ms")
    else:
        logger.warning(f"   ✗ Sequential access may not achieve 60 FPS: {avg_ms:.2f}ms > {target_per_item:.2f}ms")

    # Test 4: Mark operations
    logger.info("\n4. Testing mark operations...")
    test_items = [model.get_item(i) for i in range(min(100, model.rowCount()))]

    start = time.perf_counter()
    for item in test_items:
        model.mark_file(item['file_hash'], 'delete')
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / len(test_items)) * 1000

    logger.info(f"   Marked {len(test_items)} items in {elapsed*1000:.1f}ms")
    logger.info(f"   Average: {avg_ms:.2f}ms per mark")

    if avg_ms < 10:
        logger.info(f"   ✓ Mark time within target: {avg_ms:.2f}ms < 10ms")
    else:
        logger.warning(f"   ✗ Mark time exceeds target: {avg_ms:.2f}ms > 10ms")

    # Test 5: Cache statistics
    logger.info("\n5. Cache statistics:")
    stats = cache.get_stats()
    logger.info(f"   Total requests: {stats['total_requests']}")
    logger.info(f"   Memory hit rate: {stats['memory_hit_rate']:.1f}%")
    logger.info(f"   Disk hit rate: {stats['disk_hit_rate']:.1f}%")
    logger.info(f"   Miss rate: {stats['miss_rate']:.1f}%")
    logger.info(f"   Generated: {stats['generated']}")
    logger.info(f"   Errors: {stats['errors']}")

    if stats['memory_hit_rate'] > 50 or stats['total_requests'] < 100:
        logger.info(f"   ✓ Cache hit rate acceptable")
    else:
        logger.warning(f"   ⚠ Low memory hit rate (expected on first run)")

    logger.info("\n" + "="* 80)
    logger.info("PERFORMANCE TESTS COMPLETE")
    logger.info("="* 80)


def main():
    """Main test entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Grid performance test")
    parser.add_argument('--count', type=int, default=1000,
                       help='Number of test files to create (default: 1000)')
    parser.add_argument('--no-cleanup', action='store_true',
                       help='Keep test database and cache after exit')
    args = parser.parse_args()

    app = QApplication(sys.argv)

    # Create temporary database and cache
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    cache_dir = Path(tempfile.gettempdir()) / 'test_triage_cache'

    test_images_dir = None
    try:
        logger.info(f"Test database: {test_db_path}")
        logger.info(f"Test cache: {cache_dir}")

        # Create test data (with actual images)
        test_images_dir = create_test_database(test_db_path, test_count=args.count, create_images=True)

        # Initialize cache
        cache = ThumbnailCache(
            db_path=test_db_path,
            cache_dir=str(cache_dir),
            memory_size=500,
            disk_size_gb=1,
            worker_threads=8
        )

        # Create model
        model = ThumbnailGridModel(cache, test_db_path)

        # Run automated tests
        run_performance_tests(model, cache, test_images_dir)

        # Show interactive window
        logger.info("\nOpening interactive test window...")
        logger.info("Test the following:")
        logger.info("  1. Scroll through the grid smoothly")
        logger.info("  2. Try keyboard shortcuts (D/F/C)")
        logger.info("  3. Change grid sizes (1/2/3)")
        logger.info("  4. Select multiple items (Shift/Ctrl)")
        logger.info("  5. Check cache stats and memory usage")
        logger.info("\nPress Ctrl+C or close window to exit\n")

        window = PerformanceTestWindow(model, cache, args.count)
        window.show()

        # Wait for thumbnails to generate
        logger.info("Waiting for initial thumbnails to generate...")
        QTimer.singleShot(2000, lambda: logger.info("✓ Initial thumbnails should be ready"))

        sys.exit(app.exec())

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1

    finally:
        if not args.no_cleanup:
            # Cleanup
            logger.info("\nCleaning up test files...")
            if os.path.exists(test_db_path):
                os.remove(test_db_path)
            if cache_dir.exists():
                shutil.rmtree(cache_dir)
            if test_images_dir and test_images_dir.exists():
                shutil.rmtree(test_images_dir)
            logger.info("✓ Cleanup complete")
        else:
            logger.info(f"\nTest files preserved:")
            logger.info(f"  Database: {test_db_path}")
            logger.info(f"  Cache: {cache_dir}")
            if test_images_dir:
                logger.info(f"  Images: {test_images_dir}")


if __name__ == '__main__':
    main()
