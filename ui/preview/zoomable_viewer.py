"""
Unified Image Viewer

Production-ready image viewer component that consolidates all preview
functionality from the PyPhotoOrganizer application into a single,
reusable component.

Features:
    - Rubber band zoom (drag to select region, release to zoom)
    - Double-click to reset zoom to fit-view
    - EXIF orientation support (automatic rotation based on EXIF tags)
    - Placeholder support for non-image files
    - File type validation
    - Grayscale image support
    - Corrupted file handling
    - Delayed resize for smooth window resizing
    - Configurable background color (light/dark themes)

Usage:
    from ui.preview import UnifiedImageViewer

    viewer = UnifiedImageViewer()
    viewer.load_image("/path/to/image.jpg")

    # Or use aliases for backward compatibility:
    from ui.preview import ZoomableImageViewer, ImagePreviewWidget
"""

import os
import logging
from typing import Optional, Tuple

from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
from PySide6.QtCore import Qt, QRectF, QPointF, QTimer
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QBrush

from PIL import Image, ImageOps

try:
    from ui.theme import ThemeManager, get_theme
    HAS_THEME = True
except ImportError:
    HAS_THEME = False

logger = logging.getLogger(__name__)


class UnifiedImageViewer(QGraphicsView):
    """
    Unified image viewer with rubber band zoom and EXIF orientation support.

    This component consolidates the best features from ZoomableImageViewer
    (date_corrections_tab.py) and ImagePreviewWidget (import_history_tab.py)
    into a single, reusable implementation.

    Features:
        - Rubber band zoom: Click and drag to select zoom region
        - Double-click reset: Double-click anywhere to reset to fit-view
        - EXIF orientation: Automatic rotation based on EXIF tags
        - Placeholder text: Shows helpful text when no image is loaded
        - File validation: Only loads valid image files
        - Grayscale support: Handles grayscale and color images
        - Delayed resize: Smooth resizing without flicker

    Attributes:
        dark_mode (bool): Use dark background (True) or light background (False)
        current_file_path (str): Path to currently loaded image
        image_dimensions (tuple): (width, height) of current image or None

    Example:
        viewer = UnifiedImageViewer(dark_mode=True)
        viewer.load_image("/path/to/photo.jpg")

        # Reset zoom
        viewer.zoom_to_fit()

        # Clear viewer
        viewer.clear()
    """

    # Supported image extensions (lowercase)
    VALID_IMAGE_EXTENSIONS = {
        '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
        '.webp', '.ico', '.heic', '.heif'
    }

    def __init__(self, parent=None, dark_mode: bool = False):
        """
        Initialize the unified image viewer.

        Args:
            parent: Parent widget
            dark_mode: Use dark background (default: False for light background)
        """
        super().__init__(parent)

        # Create scene
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)

        # Enable antialiasing for smooth zooming
        self.setRenderHint(QPainter.Antialiasing)
        self.setRenderHint(QPainter.SmoothPixmapTransform)

        # Configure scrollbars
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Image state
        self._pixmap_item: Optional[QGraphicsPixmapItem] = None
        self._original_pixmap: Optional[QPixmap] = None
        self._current_file_path: Optional[str] = None
        self._image_dimensions: Optional[Tuple[int, int]] = None

        # Rubber band zoom state
        self._rubber_band_origin: Optional[QPointF] = None
        self._rubber_band_rect = None
        self._is_rubber_banding: bool = False
        self._is_custom_zoom: bool = False

        # Dark mode configuration
        self._dark_mode = dark_mode
        self._apply_styling()

        # Timer for delayed fit after resize (50ms debounce)
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._delayed_fit)

        # Set minimum size
        self.setMinimumSize(200, 200)

    def _apply_styling(self):
        """Apply styling based on dark_mode setting or theme."""
        # Use theme system if available, otherwise fall back to hardcoded colors
        if HAS_THEME:
            theme = get_theme()
            c = theme.colors
            self.setBackgroundBrush(QBrush(QColor(c.bg_tertiary)))
            self.setStyleSheet(f"border: 1px solid {c.border_light};")
        elif self._dark_mode:
            self.setBackgroundBrush(QBrush(QColor('#2d2d2d')))
            self.setStyleSheet("border: none;")
        else:
            self.setBackgroundBrush(QBrush(QColor('#f5f5f5')))
            self.setStyleSheet("border: 1px solid #ddd;")

    @property
    def dark_mode(self) -> bool:
        """Get dark mode setting."""
        return self._dark_mode

    @dark_mode.setter
    def dark_mode(self, value: bool):
        """Set dark mode and re-apply styling."""
        self._dark_mode = value
        self._apply_styling()

    def update_theme(self):
        """Re-apply styling from current theme (call after theme changes)."""
        self._apply_styling()

    @property
    def current_file_path(self) -> Optional[str]:
        """Get path to currently loaded image."""
        return self._current_file_path

    @property
    def image_dimensions(self) -> Optional[Tuple[int, int]]:
        """Get dimensions (width, height) of current image, or None."""
        return self._image_dimensions

    # Backward compatibility properties
    @property
    def scene(self) -> QGraphicsScene:
        """Get the graphics scene (backward compatibility)."""
        return self._scene

    @property
    def pixmap_item(self) -> Optional[QGraphicsPixmapItem]:
        """Get the pixmap item (backward compatibility)."""
        return self._pixmap_item

    @property
    def original_pixmap(self) -> Optional[QPixmap]:
        """Get the original pixmap (backward compatibility)."""
        return self._original_pixmap

    @property
    def is_custom_zoom(self) -> bool:
        """Check if user has applied custom zoom."""
        return self._is_custom_zoom

    @is_custom_zoom.setter
    def is_custom_zoom(self, value: bool):
        """Set custom zoom state (backward compatibility)."""
        self._is_custom_zoom = value

    def load_image(self, file_path: str) -> bool:
        """
        Load and display an image from file path.

        Handles EXIF orientation, format conversion, and error recovery.
        If the file is not a valid image or loading fails, a placeholder
        message is displayed.

        Args:
            file_path: Path to the image file to load

        Returns:
            True if image loaded successfully, False otherwise
        """
        # Reset state
        self._scene.clear()
        self._pixmap_item = None
        self._original_pixmap = None
        self._is_custom_zoom = False
        self._rubber_band_rect = None
        self._current_file_path = None
        self._image_dimensions = None

        # Validate path
        if not file_path or not os.path.exists(file_path):
            self._show_placeholder("No image available")
            return False

        # Validate file type by extension
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.VALID_IMAGE_EXTENSIONS:
            self._show_placeholder(f"Not an image file\n({ext})")
            return False

        try:
            # Load image with PIL
            pil_img = Image.open(file_path)

            # Apply EXIF orientation tag to display image correctly
            # Many cameras/phones save images in a default orientation and use EXIF
            # orientation tag to indicate how the image should be displayed
            pil_img = ImageOps.exif_transpose(pil_img)

            # Store dimensions before any conversion
            self._image_dimensions = (pil_img.width, pil_img.height)

            # Convert to compatible format for Qt
            pixmap = self._pil_to_pixmap(pil_img)

            if pixmap.isNull():
                self._show_placeholder("Failed to load image")
                return False

            # Store original pixmap
            self._original_pixmap = pixmap

            # Add to scene
            self._pixmap_item = QGraphicsPixmapItem(pixmap)
            self._scene.addItem(self._pixmap_item)
            self._scene.setSceneRect(self._pixmap_item.boundingRect())

            # Zoom to fit
            self._zoom_to_fit()

            # Store file path
            self._current_file_path = file_path

            logger.debug(f"Loaded image: {file_path} ({pil_img.width}x{pil_img.height})")
            return True

        except Exception as e:
            logger.error(f"Failed to load image {file_path}: {e}", exc_info=True)
            self._show_placeholder(f"Error loading image:\n{str(e)[:50]}")
            return False

    def setImage(self, file_path: str) -> bool:
        """
        Load and display image (alias for load_image).

        Provided for backward compatibility with ImagePreviewWidget.

        Args:
            file_path: Path to image file

        Returns:
            True if successful, False otherwise
        """
        return self.load_image(file_path)

    def _pil_to_pixmap(self, pil_img: Image.Image) -> QPixmap:
        """
        Convert PIL image to QPixmap.

        Handles RGB, RGBA, grayscale, and other modes by converting
        to an appropriate Qt format.

        Args:
            pil_img: PIL Image object

        Returns:
            QPixmap ready for display
        """
        try:
            # Handle different image modes
            if pil_img.mode == 'RGB':
                img_data = pil_img.tobytes('raw', 'RGB')
                qimage = QImage(
                    img_data, pil_img.width, pil_img.height,
                    pil_img.width * 3, QImage.Format_RGB888
                )
            elif pil_img.mode == 'RGBA':
                img_data = pil_img.tobytes('raw', 'RGBA')
                qimage = QImage(
                    img_data, pil_img.width, pil_img.height,
                    pil_img.width * 4, QImage.Format_RGBA8888
                )
            elif pil_img.mode == 'L':
                # Grayscale
                img_data = pil_img.tobytes('raw', 'L')
                qimage = QImage(
                    img_data, pil_img.width, pil_img.height,
                    pil_img.width, QImage.Format_Grayscale8
                )
            else:
                # Convert other modes to RGB
                pil_img = pil_img.convert('RGB')
                img_data = pil_img.tobytes('raw', 'RGB')
                qimage = QImage(
                    img_data, pil_img.width, pil_img.height,
                    pil_img.width * 3, QImage.Format_RGB888
                )

            return QPixmap.fromImage(qimage)

        except Exception as e:
            logger.error(f"Failed to convert PIL image to QPixmap: {e}")
            return QPixmap()

    def _show_placeholder(self, text: str):
        """
        Show placeholder text when no image is available.

        Args:
            text: Placeholder text to display
        """
        self._scene.clear()
        self._pixmap_item = None
        self._original_pixmap = None
        self._current_file_path = None
        self._image_dimensions = None

        text_item = self._scene.addText(text)
        # Use theme color for placeholder text if available
        if HAS_THEME:
            theme = get_theme()
            text_item.setDefaultTextColor(QColor(theme.colors.text_muted))
        else:
            text_item.setDefaultTextColor(QColor('#888888'))
        self._scene.setSceneRect(self._scene.itemsBoundingRect())

    def _zoom_to_fit(self):
        """Zoom image to fit the view while maintaining aspect ratio."""
        if self._pixmap_item:
            # Reset any transforms first
            self.resetTransform()
            # Get the image bounding rect
            rect = self._pixmap_item.boundingRect()
            # Set scene rect to match
            self._scene.setSceneRect(rect)
            # Fit the view to show the entire image
            self.fitInView(rect, Qt.KeepAspectRatio)
            self._is_custom_zoom = False
            logger.debug("Zoom reset to fit-to-view")

    def zoom_to_fit(self):
        """
        Reset zoom to fit image in view (public method).

        This is the recommended way to reset zoom from external code.
        """
        self._zoom_to_fit()

    def _delayed_fit(self):
        """Called after resize timer - ensures proper fitting."""
        if self._pixmap_item and not self._is_rubber_banding and not self._is_custom_zoom:
            self._zoom_to_fit()

    def clear(self):
        """Clear the viewer and reset state."""
        self._scene.clear()
        self._pixmap_item = None
        self._original_pixmap = None
        self._is_custom_zoom = False
        self._rubber_band_rect = None
        self._current_file_path = None
        self._image_dimensions = None

    # =========================================================================
    # Event Handlers
    # =========================================================================

    def resizeEvent(self, event):
        """Handle resize - maintain zoom state or fit to view."""
        super().resizeEvent(event)
        # Use timer to delay fit until after resize is complete (debounce)
        if self._pixmap_item and not self._is_rubber_banding and not self._is_custom_zoom:
            self._resize_timer.start(50)  # 50ms delay

    def mousePressEvent(self, event):
        """Start rubber band selection for zoom."""
        if event.button() == Qt.LeftButton and self._pixmap_item:
            self._rubber_band_origin = self.mapToScene(event.pos())
            self._is_rubber_banding = True
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Update rubber band rectangle during drag."""
        if self._is_rubber_banding and self._rubber_band_origin:
            current_pos = self.mapToScene(event.pos())

            # Remove old rubber band
            if self._rubber_band_rect:
                self._scene.removeItem(self._rubber_band_rect)

            # Create new rubber band rectangle
            x = min(self._rubber_band_origin.x(), current_pos.x())
            y = min(self._rubber_band_origin.y(), current_pos.y())
            width = abs(current_pos.x() - self._rubber_band_origin.x())
            height = abs(current_pos.y() - self._rubber_band_origin.y())

            rect = QRectF(x, y, width, height)

            # Draw rubber band with dashed blue line
            pen = QPen(QColor(0, 120, 215), 2, Qt.DashLine)
            self._rubber_band_rect = self._scene.addRect(rect, pen)

            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Complete rubber band zoom on mouse release."""
        if event.button() == Qt.LeftButton and self._is_rubber_banding:
            if self._rubber_band_origin:
                current_pos = self.mapToScene(event.pos())

                # Calculate zoom rectangle in scene coordinates
                x = min(self._rubber_band_origin.x(), current_pos.x())
                y = min(self._rubber_band_origin.y(), current_pos.y())
                width = abs(current_pos.x() - self._rubber_band_origin.x())
                height = abs(current_pos.y() - self._rubber_band_origin.y())

                logger.debug(f"Rubber band zoom: x={x:.1f}, y={y:.1f}, w={width:.1f}, h={height:.1f}")

                # Only zoom if rectangle is large enough (> 10 pixels)
                if width > 10 and height > 10:
                    zoom_rect = QRectF(x, y, width, height)
                    self.fitInView(zoom_rect, Qt.KeepAspectRatio)
                    self._is_custom_zoom = True
                    self.viewport().update()
                    logger.debug("Zoom applied, custom zoom mode enabled")

                # Remove rubber band
                if self._rubber_band_rect:
                    self._scene.removeItem(self._rubber_band_rect)
                    self._rubber_band_rect = None

            self._rubber_band_origin = None
            self._is_rubber_banding = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Double-click to reset zoom to fit-view."""
        if event.button() == Qt.LeftButton:
            self._zoom_to_fit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)
