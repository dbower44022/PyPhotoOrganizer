"""
Thumbnail Generation Workers

Background thumbnail generation using QThreadPool.
Generates thumbnails from original images and saves to disk cache.

Performance optimizations:
- Uses PIL/Pillow with LANCZOS resampling (high quality)
- Saves as JPEG with quality=85 (good balance)
- Handles HEIC, RAW formats via pillow_heif
- Runs in separate thread (no UI blocking)
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRunnable, QObject, Signal, Slot, Qt
from PySide6.QtGui import QPixmap, QImage, QColor, QPainter, QFont
from PIL import Image

logger = logging.getLogger(__name__)


class ThumbnailWorkerSignals(QObject):
    """
    Signals for ThumbnailWorker.

    Signals:
        finished: Emitted when thumbnail generation succeeds
                 Args: file_hash (str), size (int), disk_path (str)
                 NOTE: Emits disk path, not QPixmap - QPixmap must be created in main thread!
        error: Emitted when generation fails
               Args: file_hash (str), error_message (str)
        progress: Emitted during generation
                 Args: file_hash (str), message (str)
    """
    finished = Signal(str, int, str)  # file_hash, size, disk_path
    error = Signal(str, str)
    progress = Signal(str, str)


class ThumbnailWorker(QRunnable):
    """
    Background worker for thumbnail generation.

    Generates thumbnail in separate thread:
    1. Opens image with PIL
    2. Converts to RGB if needed
    3. Generates thumbnail (maintains aspect ratio)
    4. Saves to disk cache as JPEG
    5. Converts to QPixmap
    6. Emits finished signal with pixmap

    Handles errors gracefully - emits error signal on failure.
    """

    def __init__(self, file_hash: str, file_path: str, size: int,
                 cache_dir: Path, cache=None):
        """
        Initialize thumbnail worker.

        Args:
            file_hash: SHA-256 hash from UniquePhotos
            file_path: Full path to original image
            size: Thumbnail size in pixels (256, 512, or 1024)
            cache_dir: Root directory for disk cache
            cache: ThumbnailCache instance (for async DB writes)
        """
        super().__init__()
        self.file_hash = file_hash
        self.file_path = file_path
        self.size = size
        self.cache_dir = Path(cache_dir)
        self.cache = cache  # Reference to ThumbnailCache for async writes
        self.signals = ThumbnailWorkerSignals()

        # Auto-delete when done
        self.setAutoDelete(True)

    @Slot()
    def run(self):
        """
        Generate thumbnail in background thread.

        This method runs in a separate thread via QThreadPool.
        """
        try:
            # Check if file is a video (skip - PIL cannot open videos)
            file_ext = os.path.splitext(self.file_path)[1].lower()
            video_extensions = {'.mov', '.mp4', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv'}

            if file_ext in video_extensions:
                # For videos, save a placeholder to disk cache and emit path
                logger.debug(f"Creating video placeholder for: {self.file_path}")

                # Create placeholder and save to disk
                cache_subdir = self.cache_dir / self.file_hash[:2]
                cache_subdir.mkdir(parents=True, exist_ok=True)
                disk_path = cache_subdir / f"{self.file_hash}_{self.size}_video.jpg"

                # Generate and save placeholder
                placeholder = self._create_video_placeholder()
                placeholder.save(str(disk_path), 'JPEG', quality=85)

                # Update database
                self._update_cache_metadata(disk_path)

                # Emit disk path (QPixmap will be created in main thread)
                self.signals.finished.emit(self.file_hash, self.size, str(disk_path))
                return

            # CRITICAL: Validate file exists before trying to open
            if not os.path.exists(self.file_path):
                raise FileNotFoundError(f"Source file not found: {self.file_path}")

            # Validate file size (ensure it's not 0 bytes)
            try:
                file_size = os.path.getsize(self.file_path)
                if file_size == 0:
                    raise ValueError(f"Source file is 0 bytes: {self.file_path}")
            except OSError as e:
                raise OSError(f"Cannot access source file: {e}")

            self.signals.progress.emit(self.file_hash, "Opening image...")

            # Open image with PIL
            img = Image.open(self.file_path)

            # Convert to RGB if needed (handles RGBA, L, CMYK, etc.)
            if img.mode not in ('RGB', 'L'):
                self.signals.progress.emit(self.file_hash, "Converting to RGB...")
                img = img.convert('RGB')

            # Generate thumbnail (maintains aspect ratio)
            self.signals.progress.emit(self.file_hash, f"Generating {self.size}px thumbnail...")
            img.thumbnail((self.size, self.size), Image.LANCZOS)

            # Create disk cache path: {cache_dir}/{hash[:2]}/{hash}_{size}.jpg
            # Organize by first 2 chars of hash for filesystem efficiency
            cache_subdir = self.cache_dir / self.file_hash[:2]
            cache_subdir.mkdir(parents=True, exist_ok=True)

            disk_path = cache_subdir / f"{self.file_hash}_{self.size}.jpg"

            # Save to disk cache
            self.signals.progress.emit(self.file_hash, "Saving to cache...")
            logger.info(f"Worker saving thumbnail to: {disk_path}")
            try:
                img.save(str(disk_path), 'JPEG', quality=85, optimize=True)
                logger.info(f"Worker saved thumbnail successfully")

                # Verify the file was written and is not 0 bytes
                if not os.path.exists(disk_path):
                    raise IOError(f"Thumbnail file not created: {disk_path}")

                saved_size = os.path.getsize(disk_path)
                logger.info(f"Worker verified file size: {saved_size} bytes")
                if saved_size == 0:
                    raise IOError(f"Thumbnail file is 0 bytes (disk write failed): {disk_path}")

            except Exception as save_error:
                # If save failed, ensure we don't leave a corrupted file
                try:
                    if os.path.exists(disk_path):
                        os.remove(disk_path)
                except:
                    pass
                raise IOError(f"Failed to save thumbnail: {save_error}")

            # Update database
            self._update_cache_metadata(disk_path)

            # Emit disk path (QPixmap will be created in main thread)
            # This is CRITICAL: QPixmap must only be created in the main GUI thread!
            logger.info(f"Worker emitting finished signal for {self.file_hash[:8]}... disk_path={disk_path}")
            self.signals.finished.emit(self.file_hash, self.size, str(disk_path))
            logger.info(f"Worker finished successfully: {self.file_hash[:8]}... size={self.size}")

        except FileNotFoundError as e:
            error_msg = f"File not found: {self.file_path}"
            logger.warning(f"Thumbnail generation failed: {error_msg}")
            try:
                self.signals.error.emit(self.file_hash, error_msg)
            except Exception as emit_error:
                logger.error(f"Failed to emit error signal: {emit_error}")

        except Image.UnidentifiedImageError as e:
            error_msg = f"Cannot identify image file: {os.path.basename(self.file_path)}"
            logger.warning(f"Thumbnail generation failed: {error_msg}")
            try:
                self.signals.error.emit(self.file_hash, error_msg)
            except Exception as emit_error:
                logger.error(f"Failed to emit error signal: {emit_error}")

        except (OSError, IOError) as e:
            error_msg = f"OS/IO error: {str(e)}"
            logger.error(f"Thumbnail generation failed for {self.file_path}: {error_msg}")
            try:
                self.signals.error.emit(self.file_hash, error_msg)
            except Exception as emit_error:
                logger.error(f"Failed to emit error signal: {emit_error}")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(f"Thumbnail generation failed for {self.file_path}: {error_msg}", exc_info=True)
            try:
                self.signals.error.emit(self.file_hash, error_msg)
            except Exception as emit_error:
                logger.error(f"Failed to emit error signal: {emit_error}")

    def _create_video_placeholder(self) -> Image.Image:
        """
        Create placeholder thumbnail for video files as PIL Image.

        Returns:
            PIL Image with "VIDEO" text
        """
        from PIL import ImageDraw, ImageFont

        # Create a simple colored placeholder
        img = Image.new('RGB', (self.size, self.size), color=(60, 60, 80))
        draw = ImageDraw.Draw(img)

        # Draw play button triangle
        triangle_size = self.size // 3
        center_x = self.size // 2
        center_y = self.size // 2
        triangle = [
            (center_x - triangle_size//2, center_y - triangle_size//2),
            (center_x - triangle_size//2, center_y + triangle_size//2),
            (center_x + triangle_size//2, center_y)
        ]
        draw.polygon(triangle, fill=(200, 200, 200))

        # Draw "VIDEO" text below triangle
        text = "VIDEO"
        try:
            # Try to use a TrueType font if available
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", max(12, self.size // 20))
        except:
            # Fallback to default PIL font
            font = ImageFont.load_default()

        # Get text bounding box and draw centered at bottom
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = (self.size - text_width) // 2
        text_y = self.size - max(20, self.size // 10)
        draw.text((text_x, text_y), text, fill=(200, 200, 200), font=font)

        return img

    def _pil_to_qpixmap(self, pil_image: Image.Image) -> QPixmap:
        """
        Convert PIL Image to QPixmap.

        Args:
            pil_image: PIL Image object (must be RGB or L mode)

        Returns:
            QPixmap
        """
        # Convert PIL image to bytes
        if pil_image.mode == 'RGB':
            data = pil_image.tobytes('raw', 'RGB')
            qimage = QImage(data, pil_image.width, pil_image.height,
                          pil_image.width * 3, QImage.Format_RGB888)
        elif pil_image.mode == 'L':
            # Grayscale
            data = pil_image.tobytes('raw', 'L')
            qimage = QImage(data, pil_image.width, pil_image.height,
                          pil_image.width, QImage.Format_Grayscale8)
        else:
            # Shouldn't reach here (converted to RGB in run())
            raise ValueError(f"Unsupported image mode: {pil_image.mode}")

        # Convert to QPixmap
        pixmap = QPixmap.fromImage(qimage)
        return pixmap

    def _update_cache_metadata(self, disk_path: Path):
        """
        Queue thumbnail metadata for async database write.

        Args:
            disk_path: Path to saved thumbnail file
        """
        try:
            # Get file modification time
            file_mtime = os.path.getmtime(self.file_path)

            # Queue async database write (non-blocking)
            if self.cache:
                self.cache.queue_database_write(
                    self.file_hash,
                    str(disk_path),
                    self.size,
                    file_mtime
                )
            else:
                # Fallback to direct write (for backwards compatibility)
                from triage.triage_database import TriageDatabase
                triage_db = TriageDatabase(self.cache.db_path if self.cache else '')
                triage_db.add_thumbnail(
                    self.file_hash,
                    str(disk_path),
                    self.size,
                    file_mtime
                )

        except Exception as e:
            logger.debug(f"Failed to queue thumbnail metadata: {e}")
            # Don't fail the whole operation if database update fails


class PlaceholderGenerator:
    """
    Generates placeholder pixmaps for thumbnails that aren't ready yet.

    Creates simple colored rectangles with "Loading..." text.
    """

    @staticmethod
    def create_placeholder(size: int, text: str = "Loading...") -> QPixmap:
        """
        Create placeholder pixmap.

        SIMPLIFIED VERSION: Just a solid color, NO text rendering.
        Text rendering via QPainter might be causing Qt internal crashes.

        Args:
            size: Size in pixels (square)
            text: Text to display (IGNORED - no text rendering for stability)

        Returns:
            QPixmap with placeholder (or null QPixmap on error)
        """
        from PySide6.QtGui import QColor

        try:
            # Validate size
            if size <= 0 or size > 4096:
                logger.error(f"Invalid placeholder size: {size}")
                return QPixmap()  # Return null pixmap

            # Create pixmap - SIMPLIFIED, no QPainter, no text
            pixmap = QPixmap(size, size)

            # Verify pixmap was created
            if pixmap.isNull():
                logger.error("Failed to create placeholder QPixmap")
                return pixmap

            # Fill with solid color - NO PAINTER, NO TEXT
            # This is the safest possible QPixmap creation
            pixmap.fill(QColor(80, 80, 100))  # Dark blue-gray background

            # Verify pixmap is still valid
            if pixmap.isNull():
                logger.error("Placeholder pixmap became null after fill")
                return QPixmap()

            logger.info(f"Created simple placeholder: {size}x{size}, isNull={pixmap.isNull()}")
            return pixmap

        except Exception as e:
            logger.error(f"Unexpected error creating placeholder: {e}", exc_info=True)
            return QPixmap()  # Return null pixmap on any error


if __name__ == '__main__':
    # Test thumbnail generation
    import sys
    import tempfile
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtCore import QThreadPool

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # Create test image
    with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
        test_image_path = f.name

    # Create a test image with PIL
    test_img = Image.new('RGB', (1920, 1080), color=(73, 109, 137))
    test_img.save(test_image_path, 'JPEG')
    print(f"Created test image: {test_image_path}")

    # Create cache directory
    cache_dir = Path(tempfile.gettempdir()) / 'test_thumbnail_cache'
    cache_dir.mkdir(exist_ok=True)

    # Create test database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        test_db_path = f.name

    # Initialize database tables
    from triage.triage_database import TriageDatabase
    triage_db = TriageDatabase(test_db_path)
    triage_db.ensure_triage_tables()

    # Create label to display result
    label = QLabel()
    label.setWindowTitle("Thumbnail Test")
    label.resize(300, 300)
    label.show()

    # Success handler
    def on_finished(file_hash, size, pixmap):
        print(f"✓ Thumbnail generated: {file_hash[:8]}... size={size}")
        label.setPixmap(pixmap.scaled(256, 256, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        print("Thumbnail displayed in window")

        # Cleanup
        QThreadPool.globalInstance().waitForDone()
        os.remove(test_image_path)
        os.remove(test_db_path)
        import shutil
        shutil.rmtree(cache_dir)
        print("Cleaned up test files")
        app.quit()

    # Error handler
    def on_error(file_hash, error_msg):
        print(f"✗ Thumbnail generation failed: {error_msg}")
        app.quit()

    # Create worker
    worker = ThumbnailWorker(
        file_hash="test_hash_123",
        file_path=test_image_path,
        size=256,
        cache_dir=cache_dir,
        db_path=test_db_path
    )

    worker.signals.finished.connect(on_finished)
    worker.signals.error.connect(on_error)

    # Run in thread pool
    QThreadPool.globalInstance().start(worker)

    print("Started thumbnail generation...")
    sys.exit(app.exec())
