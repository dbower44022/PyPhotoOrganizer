"""
Edit Image Dialog

Combined photo editor dialog with:
- Brightness, Contrast, Saturation adjustments
- Auto-Enhance button for automatic optimization
- Interactive crop selection with aspect ratio presets
- Live preview with before/after toggle
- Version control integration via Prior Revision Archive
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider,
    QGroupBox, QComboBox, QRadioButton, QButtonGroup, QProgressDialog,
    QWidget, QSplitter, QFrame, QMessageBox, QSizePolicy, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, QRect, QPoint, QSize, Signal
from PySide6.QtGui import QPixmap, QImage, QPainter, QPen, QColor, QBrush, QCursor, QCloseEvent
import logging
import os
from typing import Optional, Tuple
from PIL import Image, ImageEnhance, ImageOps

from ui.edit_worker import EditState, EditWorker

logger = logging.getLogger(__name__)


class AdjustmentPanel(QWidget):
    """Panel with adjustment sliders and Auto Enhance button."""

    values_changed = Signal()  # Emitted when any slider changes

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)

        # Header
        header = QLabel("Adjustments")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(header)

        # Auto Enhance button
        self.auto_enhance_btn = QPushButton("Auto Enhance")
        self.auto_enhance_btn.setFixedHeight(40)
        self.auto_enhance_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066FF;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #0055DD;
            }
            QPushButton:pressed {
                background-color: #0044BB;
            }
        """)
        layout.addWidget(self.auto_enhance_btn)

        # Brightness slider
        brightness_group = self._create_slider_group("Brightness", -100, 100, 0)
        self.brightness_slider = brightness_group['slider']
        self.brightness_label = brightness_group['value_label']
        layout.addWidget(brightness_group['widget'])

        # Contrast slider
        contrast_group = self._create_slider_group("Contrast", -100, 100, 0)
        self.contrast_slider = contrast_group['slider']
        self.contrast_label = contrast_group['value_label']
        layout.addWidget(contrast_group['widget'])

        # Saturation slider
        saturation_group = self._create_slider_group("Saturation", -100, 100, 0)
        self.saturation_slider = saturation_group['slider']
        self.saturation_label = saturation_group['value_label']
        layout.addWidget(saturation_group['widget'])

        # Reset button
        self.reset_btn = QPushButton("Reset Adjustments")
        self.reset_btn.setFixedHeight(32)
        self.reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
                border-color: #666666;
            }
        """)
        self.reset_btn.clicked.connect(self.reset_values)
        layout.addWidget(self.reset_btn)

        layout.addStretch()

        self.setStyleSheet("""
            QWidget {
                background-color: #1A1A1A;
            }
        """)

    def _create_slider_group(self, label: str, min_val: int, max_val: int,
                             default: int) -> dict:
        """Create a labeled slider with value display."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Label row
        label_row = QHBoxLayout()
        name_label = QLabel(label)
        name_label.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        label_row.addWidget(name_label)

        value_label = QLabel(f"{default:+d}" if default != 0 else "0")
        value_label.setStyleSheet("color: #888888; font-size: 12px;")
        value_label.setAlignment(Qt.AlignRight)
        label_row.addWidget(value_label)

        layout.addLayout(label_row)

        # Slider
        slider = QSlider(Qt.Horizontal)
        slider.setMinimum(min_val)
        slider.setMaximum(max_val)
        slider.setValue(default)
        slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #333333;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #0066FF;
            }
            QSlider::sub-page:horizontal {
                background: #0066FF;
                border-radius: 3px;
            }
        """)

        # Connect value change
        slider.valueChanged.connect(
            lambda v: self._on_slider_changed(v, value_label)
        )

        layout.addWidget(slider)

        return {
            'widget': widget,
            'slider': slider,
            'value_label': value_label
        }

    def _on_slider_changed(self, value: int, label: QLabel):
        """Handle slider value change."""
        label.setText(f"{value:+d}" if value != 0 else "0")
        self.values_changed.emit()

    def reset_values(self):
        """Reset all sliders to zero."""
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(0)
        self.saturation_slider.setValue(0)

    def get_values(self) -> dict:
        """Get current adjustment values."""
        return {
            'brightness': self.brightness_slider.value(),
            'contrast': self.contrast_slider.value(),
            'saturation': self.saturation_slider.value()
        }

    def set_values(self, brightness: int, contrast: int, saturation: int):
        """Set adjustment values."""
        self.brightness_slider.setValue(brightness)
        self.contrast_slider.setValue(contrast)
        self.saturation_slider.setValue(saturation)


class CropPanel(QWidget):
    """Panel with crop controls and aspect ratio presets."""

    crop_mode_changed = Signal(bool)  # True = entering crop mode, False = exiting
    aspect_ratio_changed = Signal(str)  # Ratio name

    ASPECT_RATIOS = {
        'Free': None,
        '1:1': (1, 1),
        '4:3': (4, 3),
        '3:2': (3, 2),
        '16:9': (16, 9),
        '3:4': (3, 4),
        '2:3': (2, 3),
        '9:16': (9, 16),
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._crop_active = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Header
        header = QLabel("Crop")
        header.setStyleSheet("font-size: 14px; font-weight: bold; color: #FFFFFF;")
        layout.addWidget(header)

        # Aspect ratio selector
        ratio_row = QHBoxLayout()
        ratio_label = QLabel("Ratio:")
        ratio_label.setStyleSheet("color: #CCCCCC; font-size: 12px;")
        ratio_row.addWidget(ratio_label)

        self.ratio_combo = QComboBox()
        for name in self.ASPECT_RATIOS.keys():
            self.ratio_combo.addItem(name)
        self.ratio_combo.setStyleSheet("""
            QComboBox {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 4px 8px;
                min-width: 80px;
            }
            QComboBox:hover {
                border-color: #0066FF;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #FFFFFF;
                margin-right: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: #333333;
                color: #FFFFFF;
                selection-background-color: #0066FF;
            }
        """)
        self.ratio_combo.currentTextChanged.connect(
            lambda t: self.aspect_ratio_changed.emit(t)
        )
        ratio_row.addWidget(self.ratio_combo)
        ratio_row.addStretch()

        layout.addLayout(ratio_row)

        # Crop mode button
        self.crop_btn = QPushButton("Enter Crop Mode")
        self.crop_btn.setFixedHeight(36)
        self.crop_btn.setCheckable(True)
        self.crop_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
                border-color: #666666;
            }
            QPushButton:checked {
                background-color: #0066FF;
                border-color: #0066FF;
            }
        """)
        self.crop_btn.clicked.connect(self._on_crop_btn_clicked)
        layout.addWidget(self.crop_btn)

        # Reset crop button
        self.reset_crop_btn = QPushButton("Reset Crop")
        self.reset_crop_btn.setFixedHeight(32)
        self.reset_crop_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #CCCCCC;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
                border-color: #666666;
            }
        """)
        layout.addWidget(self.reset_crop_btn)

        # Crop info label
        self.crop_info_label = QLabel("No crop selected")
        self.crop_info_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.crop_info_label)

        layout.addStretch()

        self.setStyleSheet("""
            QWidget {
                background-color: #1A1A1A;
            }
        """)

    def _on_crop_btn_clicked(self, checked: bool):
        """Handle crop button click."""
        self._crop_active = checked
        if checked:
            self.crop_btn.setText("Exit Crop Mode")
        else:
            self.crop_btn.setText("Enter Crop Mode")
        self.crop_mode_changed.emit(checked)

    def is_crop_mode_active(self) -> bool:
        """Check if crop mode is active."""
        return self._crop_active

    def get_aspect_ratio(self) -> Optional[Tuple[int, int]]:
        """Get current aspect ratio or None for free."""
        return self.ASPECT_RATIOS.get(self.ratio_combo.currentText())

    def update_crop_info(self, crop_box: Optional[Tuple[int, int, int, int]]):
        """Update crop info display."""
        if crop_box:
            left, upper, right, lower = crop_box
            width = right - left
            height = lower - upper
            self.crop_info_label.setText(f"Crop: {width} x {height} px")
        else:
            self.crop_info_label.setText("No crop selected")

    def exit_crop_mode(self):
        """Exit crop mode."""
        self._crop_active = False
        self.crop_btn.setChecked(False)
        self.crop_btn.setText("Enter Crop Mode")


class PreviewWidget(QWidget):
    """
    Live preview widget with crop overlay support.

    Shows the edited image in real-time with optional crop selection rectangle.
    """

    crop_changed = Signal(object)  # Emits crop box tuple or None

    def __init__(self, parent=None):
        super().__init__(parent)
        self._original_image: Optional[QImage] = None
        self._preview_image: Optional[QImage] = None
        self._pil_image: Optional[Image.Image] = None
        self._display_pixmap: Optional[QPixmap] = None
        self._scale_factor = 1.0
        self._offset = QPoint(0, 0)

        # Crop state
        self._crop_mode = False
        self._crop_rect: Optional[QRect] = None  # In image coordinates
        self._aspect_ratio: Optional[Tuple[int, int]] = None
        self._dragging = False
        self._drag_handle: Optional[str] = None  # 'tl', 'tr', 'bl', 'br', 'move', etc.
        self._drag_start: Optional[QPoint] = None
        self._drag_rect_start: Optional[QRect] = None

        # Adjustment values
        self._brightness = 0
        self._contrast = 0
        self._saturation = 0

        # Before/after toggle
        self._show_original = False

        # Debounce timer for preview updates
        self._update_timer = QTimer()
        self._update_timer.setSingleShot(True)
        self._update_timer.setInterval(50)
        self._update_timer.timeout.connect(self._apply_preview_adjustments)

        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)

        self.setStyleSheet("background-color: #1A1A1A;")

    def load_image(self, image_path: str):
        """Load an image from path."""
        try:
            # Load with PIL for manipulation
            pil_img = Image.open(image_path)
            # Apply EXIF orientation
            pil_img = ImageOps.exif_transpose(pil_img)
            # Convert to RGB if necessary
            if pil_img.mode not in ('RGB', 'RGBA'):
                pil_img = pil_img.convert('RGB')

            self._pil_image = pil_img
            self._original_image = self._pil_to_qimage(pil_img)
            self._preview_image = self._original_image.copy()
            self._crop_rect = None

            self._update_display()
            logger.info(f"Loaded image: {image_path}, size: {pil_img.size}")
        except Exception as e:
            logger.error(f"Failed to load image: {e}")
            self._pil_image = None
            self._original_image = None
            self._preview_image = None

    def _pil_to_qimage(self, pil_img: Image.Image) -> QImage:
        """Convert PIL Image to QImage."""
        if pil_img.mode == 'RGBA':
            data = pil_img.tobytes('raw', 'RGBA')
            return QImage(data, pil_img.width, pil_img.height,
                         pil_img.width * 4, QImage.Format_RGBA8888).copy()
        else:
            # Convert to RGB if needed
            if pil_img.mode != 'RGB':
                pil_img = pil_img.convert('RGB')
            data = pil_img.tobytes('raw', 'RGB')
            return QImage(data, pil_img.width, pil_img.height,
                         pil_img.width * 3, QImage.Format_RGB888).copy()

    def set_adjustments(self, brightness: int, contrast: int, saturation: int):
        """Set adjustment values and schedule preview update."""
        self._brightness = brightness
        self._contrast = contrast
        self._saturation = saturation
        self._update_timer.start()

    def _apply_preview_adjustments(self):
        """Apply current adjustments to generate preview."""
        if self._pil_image is None:
            return

        if self._show_original:
            self._preview_image = self._original_image.copy()
            self._update_display()
            return

        try:
            # Work on a copy
            adjusted = self._pil_image.copy()

            # Apply brightness
            if self._brightness != 0:
                factor = 1.0 + (self._brightness / 100.0)
                enhancer = ImageEnhance.Brightness(adjusted)
                adjusted = enhancer.enhance(factor)

            # Apply contrast
            if self._contrast != 0:
                factor = 1.0 + (self._contrast / 100.0)
                enhancer = ImageEnhance.Contrast(adjusted)
                adjusted = enhancer.enhance(factor)

            # Apply saturation
            if self._saturation != 0:
                factor = 1.0 + (self._saturation / 100.0)
                enhancer = ImageEnhance.Color(adjusted)
                adjusted = enhancer.enhance(factor)

            self._preview_image = self._pil_to_qimage(adjusted)
            self._update_display()

        except Exception as e:
            logger.error(f"Failed to apply preview adjustments: {e}")

    def set_show_original(self, show: bool):
        """Toggle between original and edited view."""
        self._show_original = show
        self._update_timer.start()

    def set_crop_mode(self, active: bool):
        """Enable/disable crop mode."""
        self._crop_mode = active
        if active and self._crop_rect is None and self._preview_image:
            # Initialize crop to full image
            self._crop_rect = QRect(0, 0, self._preview_image.width(),
                                   self._preview_image.height())
        self.update()

    def set_aspect_ratio(self, ratio: Optional[Tuple[int, int]]):
        """Set crop aspect ratio constraint."""
        self._aspect_ratio = ratio
        if self._crop_rect and ratio:
            self._constrain_crop_to_aspect()
        self.update()

    def _constrain_crop_to_aspect(self):
        """Adjust crop rect to match aspect ratio."""
        if not self._crop_rect or not self._aspect_ratio:
            return

        target_ratio = self._aspect_ratio[0] / self._aspect_ratio[1]
        current_ratio = self._crop_rect.width() / self._crop_rect.height()

        if abs(current_ratio - target_ratio) < 0.01:
            return

        center = self._crop_rect.center()

        if current_ratio > target_ratio:
            # Too wide, shrink width
            new_width = int(self._crop_rect.height() * target_ratio)
            self._crop_rect.setWidth(new_width)
        else:
            # Too tall, shrink height
            new_height = int(self._crop_rect.width() / target_ratio)
            self._crop_rect.setHeight(new_height)

        self._crop_rect.moveCenter(center)
        self._clamp_crop_to_image()

    def _clamp_crop_to_image(self):
        """Ensure crop rect stays within image bounds."""
        if not self._crop_rect or not self._preview_image:
            return

        img_rect = QRect(0, 0, self._preview_image.width(), self._preview_image.height())

        if self._crop_rect.left() < 0:
            self._crop_rect.moveLeft(0)
        if self._crop_rect.top() < 0:
            self._crop_rect.moveTop(0)
        if self._crop_rect.right() > img_rect.right():
            self._crop_rect.moveRight(img_rect.right())
        if self._crop_rect.bottom() > img_rect.bottom():
            self._crop_rect.moveBottom(img_rect.bottom())

    def reset_crop(self):
        """Reset crop to full image."""
        if self._preview_image:
            self._crop_rect = QRect(0, 0, self._preview_image.width(),
                                   self._preview_image.height())
            self.crop_changed.emit(None)
            self.update()

    def get_crop_box(self) -> Optional[Tuple[int, int, int, int]]:
        """Get current crop box in image coordinates."""
        if not self._crop_rect or not self._preview_image:
            return None

        img_rect = QRect(0, 0, self._preview_image.width(), self._preview_image.height())
        if self._crop_rect == img_rect:
            return None  # No crop if full image selected

        return (
            self._crop_rect.left(),
            self._crop_rect.top(),
            self._crop_rect.right(),
            self._crop_rect.bottom()
        )

    def _update_display(self):
        """Update the displayed pixmap."""
        if self._preview_image is None:
            self._display_pixmap = None
            self.update()
            return

        # Scale to fit widget while maintaining aspect ratio
        widget_size = self.size()
        img_size = self._preview_image.size()

        # Calculate scale to fit
        scale_x = (widget_size.width() - 20) / img_size.width()
        scale_y = (widget_size.height() - 20) / img_size.height()
        self._scale_factor = min(scale_x, scale_y, 1.0)

        scaled_width = int(img_size.width() * self._scale_factor)
        scaled_height = int(img_size.height() * self._scale_factor)

        # Center offset
        self._offset = QPoint(
            (widget_size.width() - scaled_width) // 2,
            (widget_size.height() - scaled_height) // 2
        )

        # Create scaled pixmap
        scaled = self._preview_image.scaled(
            scaled_width, scaled_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self._display_pixmap = QPixmap.fromImage(scaled)

        self.update()

    def _image_to_widget(self, point: QPoint) -> QPoint:
        """Convert image coordinates to widget coordinates."""
        return QPoint(
            int(point.x() * self._scale_factor) + self._offset.x(),
            int(point.y() * self._scale_factor) + self._offset.y()
        )

    def _widget_to_image(self, point: QPoint) -> QPoint:
        """Convert widget coordinates to image coordinates."""
        if self._scale_factor == 0:
            return QPoint(0, 0)
        return QPoint(
            int((point.x() - self._offset.x()) / self._scale_factor),
            int((point.y() - self._offset.y()) / self._scale_factor)
        )

    def _get_handle_at(self, pos: QPoint) -> Optional[str]:
        """Get crop handle at widget position."""
        if not self._crop_mode or not self._crop_rect:
            return None

        handle_size = 12
        half = handle_size // 2

        # Convert crop rect to widget coordinates
        tl = self._image_to_widget(self._crop_rect.topLeft())
        tr = self._image_to_widget(self._crop_rect.topRight())
        bl = self._image_to_widget(self._crop_rect.bottomLeft())
        br = self._image_to_widget(self._crop_rect.bottomRight())

        # Check corners
        if QRect(tl.x() - half, tl.y() - half, handle_size, handle_size).contains(pos):
            return 'tl'
        if QRect(tr.x() - half, tr.y() - half, handle_size, handle_size).contains(pos):
            return 'tr'
        if QRect(bl.x() - half, bl.y() - half, handle_size, handle_size).contains(pos):
            return 'bl'
        if QRect(br.x() - half, br.y() - half, handle_size, handle_size).contains(pos):
            return 'br'

        # Check edges
        top = QRect(tl.x() + half, tl.y() - half, tr.x() - tl.x() - handle_size, handle_size)
        bottom = QRect(bl.x() + half, bl.y() - half, br.x() - bl.x() - handle_size, handle_size)
        left = QRect(tl.x() - half, tl.y() + half, handle_size, bl.y() - tl.y() - handle_size)
        right = QRect(tr.x() - half, tr.y() + half, handle_size, br.y() - tr.y() - handle_size)

        if top.contains(pos):
            return 't'
        if bottom.contains(pos):
            return 'b'
        if left.contains(pos):
            return 'l'
        if right.contains(pos):
            return 'r'

        # Check inside for move
        crop_widget_rect = QRect(tl, br)
        if crop_widget_rect.contains(pos):
            return 'move'

        return None

    def paintEvent(self, event):
        """Paint the preview with crop overlay."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor('#1A1A1A'))

        if self._display_pixmap:
            # Draw image
            painter.drawPixmap(self._offset, self._display_pixmap)

            # Draw crop overlay if in crop mode
            if self._crop_mode and self._crop_rect:
                self._draw_crop_overlay(painter)

    def _draw_crop_overlay(self, painter: QPainter):
        """Draw crop selection overlay."""
        if not self._crop_rect or not self._display_pixmap:
            return

        # Convert crop rect to widget coordinates
        tl = self._image_to_widget(self._crop_rect.topLeft())
        br = self._image_to_widget(self._crop_rect.bottomRight())
        crop_widget_rect = QRect(tl, br)

        # Draw dimmed area outside crop
        dim_color = QColor(0, 0, 0, 150)
        img_rect = QRect(self._offset, self._display_pixmap.size())

        # Top region
        painter.fillRect(QRect(img_rect.left(), img_rect.top(),
                               img_rect.width(), crop_widget_rect.top() - img_rect.top()),
                        dim_color)
        # Bottom region
        painter.fillRect(QRect(img_rect.left(), crop_widget_rect.bottom(),
                               img_rect.width(), img_rect.bottom() - crop_widget_rect.bottom()),
                        dim_color)
        # Left region
        painter.fillRect(QRect(img_rect.left(), crop_widget_rect.top(),
                               crop_widget_rect.left() - img_rect.left(), crop_widget_rect.height()),
                        dim_color)
        # Right region
        painter.fillRect(QRect(crop_widget_rect.right(), crop_widget_rect.top(),
                               img_rect.right() - crop_widget_rect.right(), crop_widget_rect.height()),
                        dim_color)

        # Draw crop border
        pen = QPen(QColor('#FFFFFF'))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.drawRect(crop_widget_rect)

        # Draw rule-of-thirds grid
        pen.setColor(QColor(255, 255, 255, 100))
        pen.setWidth(1)
        painter.setPen(pen)

        third_w = crop_widget_rect.width() / 3
        third_h = crop_widget_rect.height() / 3

        for i in range(1, 3):
            # Vertical lines
            x = crop_widget_rect.left() + int(third_w * i)
            painter.drawLine(x, crop_widget_rect.top(), x, crop_widget_rect.bottom())
            # Horizontal lines
            y = crop_widget_rect.top() + int(third_h * i)
            painter.drawLine(crop_widget_rect.left(), y, crop_widget_rect.right(), y)

        # Draw corner handles
        handle_size = 10
        handle_color = QColor('#FFFFFF')
        painter.setBrush(QBrush(handle_color))
        painter.setPen(Qt.NoPen)

        corners = [
            crop_widget_rect.topLeft(),
            crop_widget_rect.topRight(),
            crop_widget_rect.bottomLeft(),
            crop_widget_rect.bottomRight()
        ]
        for corner in corners:
            painter.drawRect(corner.x() - handle_size // 2,
                           corner.y() - handle_size // 2,
                           handle_size, handle_size)

    def mousePressEvent(self, event):
        """Handle mouse press for crop interaction."""
        if not self._crop_mode or event.button() != Qt.LeftButton:
            return

        handle = self._get_handle_at(event.pos())
        if handle:
            self._dragging = True
            self._drag_handle = handle
            self._drag_start = event.pos()
            self._drag_rect_start = QRect(self._crop_rect) if self._crop_rect else None

    def mouseMoveEvent(self, event):
        """Handle mouse move for crop interaction."""
        if not self._crop_mode:
            return

        # Update cursor
        handle = self._get_handle_at(event.pos())
        if handle in ('tl', 'br'):
            self.setCursor(Qt.SizeFDiagCursor)
        elif handle in ('tr', 'bl'):
            self.setCursor(Qt.SizeBDiagCursor)
        elif handle in ('t', 'b'):
            self.setCursor(Qt.SizeVerCursor)
        elif handle in ('l', 'r'):
            self.setCursor(Qt.SizeHorCursor)
        elif handle == 'move':
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

        # Handle dragging
        if self._dragging and self._drag_handle and self._drag_rect_start:
            delta = event.pos() - self._drag_start
            delta_img = QPoint(
                int(delta.x() / self._scale_factor),
                int(delta.y() / self._scale_factor)
            )

            if self._drag_handle == 'move':
                self._crop_rect = QRect(self._drag_rect_start)
                self._crop_rect.translate(delta_img)
            else:
                self._resize_crop(delta_img)

            self._clamp_crop_to_image()
            if self._aspect_ratio:
                self._constrain_crop_to_aspect()

            self.update()
            self.crop_changed.emit(self.get_crop_box())

    def _resize_crop(self, delta: QPoint):
        """Resize crop rect based on handle being dragged."""
        if not self._drag_rect_start:
            return

        rect = QRect(self._drag_rect_start)

        if 't' in self._drag_handle:
            rect.setTop(rect.top() + delta.y())
        if 'b' in self._drag_handle:
            rect.setBottom(rect.bottom() + delta.y())
        if 'l' in self._drag_handle:
            rect.setLeft(rect.left() + delta.x())
        if 'r' in self._drag_handle:
            rect.setRight(rect.right() + delta.x())

        # Ensure minimum size
        if rect.width() >= 50 and rect.height() >= 50:
            self._crop_rect = rect

    def mouseReleaseEvent(self, event):
        """Handle mouse release."""
        self._dragging = False
        self._drag_handle = None
        self._drag_start = None
        self._drag_rect_start = None

    def resizeEvent(self, event):
        """Handle widget resize."""
        super().resizeEvent(event)
        self._update_display()


class EditImageDialog(QDialog):
    """
    Main photo editor dialog.

    Combines adjustment controls, crop tools, and live preview in a single interface.
    """

    def __init__(self, parent, record: dict, db_metadata, logger_instance):
        """
        Initialize edit image dialog.

        Args:
            parent: Parent widget
            record: File record dictionary
            db_metadata: DatabaseMetadata instance
            logger_instance: Logger instance
        """
        super().__init__(parent)
        self.parent_widget = parent
        self.record = record
        self.db_metadata = db_metadata
        self.logger = logger_instance
        self.edit_state = EditState()
        self.edit_worker = None

        self._init_ui()
        self._load_image()
        self._connect_signals()

    def _init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Edit Photo")
        self.setMinimumSize(1000, 700)
        self.setModal(True)

        # Dark theme
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1A1A;
            }
            QLabel {
                color: #FFFFFF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet("background-color: #262626; border-bottom: 1px solid #333333;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 12, 16, 12)

        filename = os.path.basename(self.record.get('archive_path', 'Unknown'))
        title_label = QLabel(f"Edit Photo - {filename}")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        layout.addWidget(header)

        # Main content area with splitter
        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #333333;
                width: 1px;
            }
        """)

        # Left panel - Controls
        left_panel = QWidget()
        left_panel.setFixedWidth(260)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        # Adjustment panel
        self.adjustment_panel = AdjustmentPanel()
        left_layout.addWidget(self.adjustment_panel)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setStyleSheet("background-color: #333333;")
        left_layout.addWidget(separator)

        # Crop panel
        self.crop_panel = CropPanel()
        left_layout.addWidget(self.crop_panel)

        main_splitter.addWidget(left_panel)

        # Right panel - Preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Preview widget
        self.preview_widget = PreviewWidget()
        right_layout.addWidget(self.preview_widget, 1)

        # Before/After toggle bar
        toggle_bar = QWidget()
        toggle_bar.setStyleSheet("background-color: #262626; border-top: 1px solid #333333;")
        toggle_layout = QHBoxLayout(toggle_bar)
        toggle_layout.setContentsMargins(16, 8, 16, 8)

        self.before_radio = QRadioButton("Before")
        self.before_radio.setStyleSheet("color: #CCCCCC;")
        self.after_radio = QRadioButton("After")
        self.after_radio.setStyleSheet("color: #CCCCCC;")
        self.after_radio.setChecked(True)

        toggle_group = QButtonGroup(self)
        toggle_group.addButton(self.before_radio)
        toggle_group.addButton(self.after_radio)

        toggle_layout.addWidget(self.before_radio)
        toggle_layout.addWidget(self.after_radio)
        toggle_layout.addStretch()

        # Info label
        self.info_label = QLabel("Original preserved in Prior Revision Archive")
        self.info_label.setStyleSheet("color: #666666; font-size: 11px;")
        toggle_layout.addWidget(self.info_label)

        right_layout.addWidget(toggle_bar)

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([260, 740])
        main_splitter.setStretchFactor(0, 0)
        main_splitter.setStretchFactor(1, 1)

        layout.addWidget(main_splitter, 1)

        # Footer with buttons
        footer = QWidget()
        footer.setStyleSheet("background-color: #262626; border-top: 1px solid #333333;")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)

        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedSize(100, 36)
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #333333;
                color: #FFFFFF;
                border: 1px solid #555555;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #444444;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedSize(100, 36)
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #0066FF;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0055DD;
            }
        """)
        self.apply_btn.clicked.connect(self._apply_edits)
        footer_layout.addWidget(self.apply_btn)

        layout.addWidget(footer)

    def _load_image(self):
        """Load the image into preview."""
        archive_path = self.record.get('archive_path') or self.record.get('file_name', '')
        if archive_path and os.path.exists(archive_path):
            self.preview_widget.load_image(archive_path)

    def _connect_signals(self):
        """Connect all signals."""
        # Adjustment panel
        self.adjustment_panel.values_changed.connect(self._on_adjustments_changed)
        self.adjustment_panel.auto_enhance_btn.clicked.connect(self._on_auto_enhance)

        # Crop panel
        self.crop_panel.crop_mode_changed.connect(self._on_crop_mode_changed)
        self.crop_panel.aspect_ratio_changed.connect(self._on_aspect_ratio_changed)
        self.crop_panel.reset_crop_btn.clicked.connect(self._on_reset_crop)

        # Preview
        self.preview_widget.crop_changed.connect(self._on_crop_changed)

        # Before/After toggle
        self.before_radio.toggled.connect(
            lambda checked: self.preview_widget.set_show_original(checked)
        )

    def _on_adjustments_changed(self):
        """Handle adjustment slider changes."""
        values = self.adjustment_panel.get_values()
        self.edit_state.brightness = values['brightness']
        self.edit_state.contrast = values['contrast']
        self.edit_state.saturation = values['saturation']
        self.preview_widget.set_adjustments(
            values['brightness'],
            values['contrast'],
            values['saturation']
        )

    def _on_auto_enhance(self):
        """Handle Auto Enhance button click."""
        from image_modifier import ImageModifier

        archive_path = self.record.get('archive_path') or self.record.get('file_name', '')
        if not archive_path or not os.path.exists(archive_path):
            QMessageBox.warning(self, "Error", "Could not load image for analysis.")
            return

        success, adjustments, error = ImageModifier.auto_enhance(archive_path)

        if success:
            self.adjustment_panel.set_values(
                adjustments['brightness'],
                adjustments['contrast'],
                adjustments['saturation']
            )
            self._on_adjustments_changed()
        else:
            QMessageBox.warning(self, "Auto Enhance Failed", f"Could not analyze image:\n{error}")

    def _on_crop_mode_changed(self, active: bool):
        """Handle crop mode toggle."""
        self.preview_widget.set_crop_mode(active)

    def _on_aspect_ratio_changed(self, ratio_name: str):
        """Handle aspect ratio change."""
        ratio = CropPanel.ASPECT_RATIOS.get(ratio_name)
        self.preview_widget.set_aspect_ratio(ratio)

    def _on_reset_crop(self):
        """Handle reset crop button."""
        self.preview_widget.reset_crop()
        self.crop_panel.update_crop_info(None)
        self.edit_state.crop_box = None

    def _on_crop_changed(self, crop_box):
        """Handle crop selection change."""
        self.edit_state.crop_box = crop_box
        self.crop_panel.update_crop_info(crop_box)

    def _apply_edits(self):
        """Apply edits and close dialog."""
        if not self.edit_state.has_changes():
            QMessageBox.information(
                self,
                "No Changes",
                "No edits have been made. Use the sliders to adjust the image\n"
                "or enter Crop mode to select a region."
            )
            return

        # Confirm operation
        changes = []
        if self.edit_state.has_color_changes():
            changes.append("color adjustments")
        if self.edit_state.has_crop():
            changes.append("crop")

        reply = QMessageBox.question(
            self,
            "Apply Edits",
            f"Apply {' and '.join(changes)} to this image?\n\n"
            f"The original will be preserved in Prior Revision Archive.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Get archive base
        archive_base = self.db_metadata.get_archive_location()
        if not archive_base:
            QMessageBox.critical(self, "Error", "Archive location not configured.")
            return

        # Check Prior Revision Archive
        prior_archive = self.db_metadata.get_prior_revision_archive_location()
        if not prior_archive:
            QMessageBox.warning(
                self, "Prior Revision Archive Not Configured",
                "Please configure Prior Revision Archive location in Archive Settings."
            )
            return

        # Disable buttons during processing
        self.apply_btn.setEnabled(False)
        self.cancel_btn.setEnabled(False)

        # Create progress dialog
        progress_dialog = QProgressDialog("Applying edits...", "Cancel", 0, 1, self)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)
        progress_dialog.setAutoClose(False)

        # Create worker
        file_hash = self.record.get('file_hash')
        edit_states = {file_hash: self.edit_state}

        self.edit_worker = EditWorker(
            records=[self.record],
            edit_states=edit_states,
            db_path=self.db_metadata.database_path,
            archive_base=archive_base,
            worker_logger=self.logger
        )

        # Connect signals
        self.edit_worker.progress.connect(
            lambda cur, total, fname: progress_dialog.setLabelText(f"Editing: {fname}")
        )
        self.edit_worker.finished.connect(
            lambda results: self._on_edit_finished(results, progress_dialog)
        )

        progress_dialog.canceled.connect(self.edit_worker.cancel)

        # Start worker
        self.edit_worker.start()

    def _on_edit_finished(self, results: dict, progress_dialog: QProgressDialog):
        """Handle edit completion."""
        progress_dialog.close()

        self.apply_btn.setEnabled(True)
        self.cancel_btn.setEnabled(True)

        success_count = results.get('success', 0)
        errors = results.get('errors', [])

        if errors:
            QMessageBox.warning(
                self,
                "Edit Complete with Errors",
                f"Edit failed:\n{errors[0]}"
            )
        elif success_count > 0:
            self.logger.info("Edit applied successfully")
            self.accept()

    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self._apply_edits()
        elif event.key() == Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close - ensure worker thread is properly stopped."""
        if self.edit_worker and self.edit_worker.isRunning():
            self.logger.info("Stopping edit worker before dialog close...")
            self.edit_worker.cancel()
            self.edit_worker.wait()  # Wait for thread to finish
            self.logger.info("Edit worker stopped")
        event.accept()
