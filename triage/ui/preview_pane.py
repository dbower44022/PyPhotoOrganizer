"""
Preview Pane

Large image preview with EXIF metadata display.
Shows selected image from grid in detail.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QGraphicsView, QGraphicsScene, QSplitter,
                               QTextEdit)
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPixmap, QPainter, QWheelEvent

from PIL import Image
from PIL.ExifTags import TAGS

logger = logging.getLogger(__name__)


class ZoomableGraphicsView(QGraphicsView):
    """
    Graphics view with zoom support.

    Features:
    - Rubber band zoom (click and drag)
    - Wheel zoom (Ctrl+Wheel)
    - Double-click to reset
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)

        # Dark background
        self.setStyleSheet("background-color: #2d2d2d;")

        self.is_custom_zoom = False

    def wheelEvent(self, event: QWheelEvent):
        """Handle wheel zoom with Ctrl key."""
        if event.modifiers() & Qt.ControlModifier:
            # Zoom with Ctrl+Wheel
            zoom_factor = 1.15 if event.angleDelta().y() > 0 else 0.85
            self.scale(zoom_factor, zoom_factor)
            self.is_custom_zoom = True
            event.accept()
        else:
            super().wheelEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Reset zoom on double-click."""
        self.resetTransform()
        self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)
        self.is_custom_zoom = False
        event.accept()

    def resizeEvent(self, event):
        """Handle resize - maintain fit if not custom zoomed."""
        super().resizeEvent(event)
        if not self.is_custom_zoom and self.scene():
            self.fitInView(self.sceneRect(), Qt.KeepAspectRatio)


class PreviewPane(QWidget):
    """
    Preview pane for large image display with metadata.

    Layout:
    ┌────────────────────────────────────┐
    │  [Filename]                        │
    ├────────────────────────────────────┤
    │                                    │
    │        Large Image Preview         │
    │     (zoomable, drag to pan)        │
    │                                    │
    ├────────────────────────────────────┤
    │  File Info | EXIF Data             │
    └────────────────────────────────────┘
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_image_path: Optional[str] = None

        layout = QVBoxLayout(self)

        # Filename label
        self.filename_label = QLabel("No image selected")
        self.filename_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self.filename_label)

        # Splitter for image and metadata
        splitter = QSplitter(Qt.Vertical)

        # Image viewer
        self.scene = QGraphicsScene()
        self.view = ZoomableGraphicsView()
        self.view.setScene(self.scene)
        splitter.addWidget(self.view)

        # Metadata display
        self.metadata_text = QTextEdit()
        self.metadata_text.setReadOnly(True)
        self.metadata_text.setMaximumHeight(150)
        self.metadata_text.setStyleSheet("font-family: monospace; font-size: 9pt;")
        splitter.addWidget(self.metadata_text)

        # Set splitter proportions (70% image, 30% metadata)
        splitter.setStretchFactor(0, 7)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def show_image(self, image_path: str):
        """
        Display image and metadata.

        Args:
            image_path: Path to image file
        """
        try:
            if not os.path.exists(image_path):
                logger.warning(f"Image not found: {image_path}")
                self.clear()
                self.filename_label.setText(f"File not found: {os.path.basename(image_path)}")
                return

            self.current_image_path = image_path
            filename = os.path.basename(image_path)
            self.filename_label.setText(filename)

            try:
                # Load and display image
                pixmap = QPixmap(image_path)

                if pixmap.isNull():
                    logger.warning(f"Failed to load image: {image_path}")
                    self.clear()
                    self.metadata_text.setPlainText(f"Failed to load image:\n{image_path}")
                    return

                self.scene.clear()
                self.scene.addPixmap(pixmap)
                self.scene.setSceneRect(QRectF(pixmap.rect()))
                self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
                self.view.is_custom_zoom = False

                # Load and display metadata
                self._load_metadata(image_path)

            except Exception as e:
                logger.error(f"Error displaying image: {e}", exc_info=True)
                self.clear()
                self.metadata_text.setPlainText(f"Error loading image:\n{e}")

        except Exception as e:
            # Outer catch for any unexpected errors
            logger.error(f"Unexpected error in show_image: {e}", exc_info=True)
            self.clear()

    def _load_metadata(self, image_path: str):
        """
        Load and display image metadata.

        Args:
            image_path: Path to image file
        """
        try:
            # File information
            file_stats = os.stat(image_path)
            file_size = file_stats.st_size
            file_size_mb = file_size / (1024 * 1024)

            metadata_lines = []
            metadata_lines.append("=== File Information ===")
            metadata_lines.append(f"Path: {image_path}")
            metadata_lines.append(f"Size: {file_size_mb:.2f} MB ({file_size:,} bytes)")

            # Try to load EXIF data
            try:
                image = Image.open(image_path)

                # Image properties
                metadata_lines.append(f"\n=== Image Properties ===")
                metadata_lines.append(f"Format: {image.format}")
                metadata_lines.append(f"Mode: {image.mode}")
                metadata_lines.append(f"Dimensions: {image.width} x {image.height}")

                # EXIF data
                exif_data = image.getexif()
                if exif_data:
                    metadata_lines.append(f"\n=== EXIF Data ===")

                    # Key EXIF fields to display
                    key_fields = {
                        'DateTime': 'Date Taken',
                        'DateTimeOriginal': 'Date Original',
                        'Make': 'Camera Make',
                        'Model': 'Camera Model',
                        'ExposureTime': 'Shutter Speed',
                        'FNumber': 'Aperture',
                        'ISOSpeedRatings': 'ISO',
                        'FocalLength': 'Focal Length',
                        'LensModel': 'Lens',
                    }

                    for tag_id, value in exif_data.items():
                        tag_name = TAGS.get(tag_id, str(tag_id))

                        # Show key fields
                        if tag_name in key_fields:
                            display_name = key_fields[tag_name]
                            metadata_lines.append(f"{display_name}: {value}")

                else:
                    metadata_lines.append(f"\n=== EXIF Data ===")
                    metadata_lines.append("No EXIF data found")

            except Exception as e:
                metadata_lines.append(f"\n=== EXIF Error ===")
                metadata_lines.append(f"Failed to read EXIF: {e}")

            # Display metadata
            self.metadata_text.setPlainText("\n".join(metadata_lines))

        except Exception as e:
            logger.error(f"Error loading metadata: {e}", exc_info=True)
            self.metadata_text.setPlainText(f"Error loading metadata:\n{e}")

    def clear(self):
        """Clear preview pane."""
        self.scene.clear()
        self.filename_label.setText("No image selected")
        self.metadata_text.clear()
        self.current_image_path = None


if __name__ == '__main__':
    # Test preview pane
    from PySide6.QtWidgets import QApplication
    import sys

    logging.basicConfig(level=logging.INFO)

    app = QApplication(sys.argv)

    pane = PreviewPane()
    pane.resize(800, 600)
    pane.show()

    # Test with an image (if available)
    test_image = "/path/to/test/image.jpg"  # Change to a real image path
    if Path(test_image).exists():
        pane.show_image(test_image)

    sys.exit(app.exec())
