"""
Photo Grid Delegate

Custom delegate for rendering thumbnail grid items with modern status overlays,
selection checkmarks, hover effects, and improved visual design.

Adapted from UnreliableDatesDelegate for the Photo Review application.
"""

import logging
from PySide6.QtWidgets import QStyledItemDelegate, QStyle, QToolTip
from PySide6.QtCore import Qt, QRect, QSize, QPoint, QRectF, QEvent
from PySide6.QtGui import (
    QPainter, QPixmap, QPen, QColor, QBrush, QFont,
    QPainterPath, QLinearGradient
)

logger = logging.getLogger(__name__)


class PhotoGridDelegate(QStyledItemDelegate):
    """
    Modern delegate for rendering photo review thumbnails.

    Features:
    - Draws thumbnail centered in cell with subtle shadow
    - Modern pill-shaped status overlays with labels
    - Selection checkmark overlay (top-left)
    - Hover effects (slight brightness increase)
    - Rich tooltips with file info
    - Loading animation placeholder
    - Modern color palette from theme system
    """

    # Modern status colors (accessible, cohesive palette)
    STATUS_COLORS = {
        'unreliable': QColor('#F59E0B'),   # Amber - needs attention
        'corrected': QColor('#10B981'),     # Emerald - corrected, needs reorg
        'reorganized': QColor('#0EA5E9'),   # Sky - complete
        'revision': QColor('#8B5CF6'),      # Violet - has revisions
        'normal': None
    }

    # Status labels for pill badges
    STATUS_LABELS = {
        'unreliable': 'Unreliable',
        'corrected': 'Needs Move',
        'reorganized': 'Done',
        'revision': 'Revisions',
        'normal': ''
    }

    # Short symbols for small thumbnails
    STATUS_SYMBOLS = {
        'unreliable': '!',
        'corrected': '!',
        'reorganized': '✓',
        'revision': 'R',
        'normal': ''
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnail_size = 200  # Default size
        self._hover_index = None  # Track hovered item
        self._loading_angle = 0  # For loading animation
        logger.debug("PhotoGridDelegate initialized with modern styling")

    def paint(self, painter: QPainter, option, index):
        """
        Render thumbnail with modern styling, status overlays, and selection indicators.

        Args:
            painter: QPainter for drawing
            option: Style options
            index: Model index
        """
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        try:
            # Get data from model
            pixmap = index.data(Qt.DecorationRole)
            filename = index.data(Qt.DisplayRole) or ""
            status = index.data(Qt.UserRole + 1)  # StatusRole

            # Calculate rects
            rect = option.rect
            margin = 6
            thumb_rect = QRect(
                rect.x() + margin,
                rect.y() + margin,
                self.thumbnail_size,
                self.thumbnail_size
            )

            # Determine states
            is_selected = bool(option.state & QStyle.State_Selected)
            is_hovered = bool(option.state & QStyle.State_MouseOver)

            # Draw cell background
            self._draw_cell_background(painter, rect, is_selected, is_hovered)

            # Draw thumbnail with shadow effect
            if pixmap and isinstance(pixmap, QPixmap) and not pixmap.isNull():
                self._draw_thumbnail(painter, thumb_rect, pixmap, is_hovered)
            else:
                self._draw_loading_placeholder(painter, thumb_rect)

            # Draw selection checkmark (top-left)
            if is_selected:
                self._draw_selection_checkmark(painter, thumb_rect)

            # Draw status overlay (bottom-left, pill-shaped)
            self._draw_status_overlay(painter, thumb_rect, status)

            # Draw selection border
            if is_selected:
                self._draw_selection_border(painter, thumb_rect)

        except Exception as e:
            logger.error(f"Error in paint(): {e}", exc_info=True)
            try:
                painter.fillRect(option.rect, QColor(100, 0, 0, 30))
            except:
                pass

        painter.restore()

    def _draw_cell_background(self, painter: QPainter, rect: QRect,
                               is_selected: bool, is_hovered: bool):
        """Draw the cell background with selection/hover states."""
        if is_selected:
            # Selected: Light blue tint
            painter.fillRect(rect, QColor(0, 102, 255, 40))
        elif is_hovered:
            # Hovered: Very subtle blue tint
            painter.fillRect(rect, QColor(0, 102, 255, 20))
        else:
            # Normal: Dark background
            painter.fillRect(rect, QColor(26, 26, 26))

    def _draw_thumbnail(self, painter: QPainter, thumb_rect: QRect,
                        pixmap: QPixmap, is_hovered: bool):
        """Draw thumbnail with optional hover brightness effect."""
        # Scale pixmap to fit thumb_rect while maintaining aspect ratio
        scaled = pixmap.scaled(
            thumb_rect.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        # Center the scaled pixmap
        x = thumb_rect.x() + (thumb_rect.width() - scaled.width()) // 2
        y = thumb_rect.y() + (thumb_rect.height() - scaled.height()) // 2

        # Draw subtle shadow behind thumbnail
        shadow_offset = 2
        shadow_rect = QRect(x + shadow_offset, y + shadow_offset,
                           scaled.width(), scaled.height())
        painter.fillRect(shadow_rect, QColor(0, 0, 0, 40))

        # Draw the pixmap
        painter.drawPixmap(x, y, scaled)

        # Hover effect: slight white overlay for brightness
        if is_hovered:
            overlay_rect = QRect(x, y, scaled.width(), scaled.height())
            painter.fillRect(overlay_rect, QColor(255, 255, 255, 20))

    def _draw_loading_placeholder(self, painter: QPainter, thumb_rect: QRect):
        """Draw modern loading placeholder with animation."""
        # Background
        painter.setBrush(QColor(40, 40, 40))
        painter.setPen(Qt.NoPen)
        path = QPainterPath()
        path.addRoundedRect(QRectF(thumb_rect), 8, 8)
        painter.drawPath(path)

        # Pulsing gradient effect
        center = thumb_rect.center()
        gradient = QLinearGradient(thumb_rect.topLeft(), thumb_rect.bottomRight())
        gradient.setColorAt(0, QColor(50, 50, 50))
        gradient.setColorAt(0.5, QColor(60, 60, 60))
        gradient.setColorAt(1, QColor(50, 50, 50))

        painter.setBrush(gradient)
        painter.drawPath(path)

        # Loading text
        painter.setPen(QColor(100, 100, 100))
        font = painter.font()
        font.setPixelSize(12)
        painter.setFont(font)
        painter.drawText(thumb_rect, Qt.AlignCenter, "Loading...")

        # Spinner circle (static for now - animation would require timer)
        spinner_size = min(30, self.thumbnail_size // 6)
        spinner_rect = QRect(
            center.x() - spinner_size // 2,
            center.y() - spinner_size // 2 - 15,
            spinner_size, spinner_size
        )
        painter.setPen(QPen(QColor(80, 80, 80), 3))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(spinner_rect)

        # Partial arc for spinner effect
        painter.setPen(QPen(QColor(0, 102, 255), 3))
        painter.drawArc(spinner_rect, 0, 90 * 16)

    def _draw_selection_checkmark(self, painter: QPainter, thumb_rect: QRect):
        """Draw selection checkmark in top-left corner."""
        # Circle background
        check_size = max(22, self.thumbnail_size // 8)
        check_rect = QRect(
            thumb_rect.left() + 4,
            thumb_rect.top() + 4,
            check_size,
            check_size
        )

        # Draw filled circle
        painter.setBrush(QColor(0, 102, 255))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(check_rect)

        # Draw checkmark
        painter.setPen(QPen(Qt.white, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))

        cx = check_rect.center().x()
        cy = check_rect.center().y()
        size = check_size // 4

        # Checkmark path
        path = QPainterPath()
        path.moveTo(cx - size, cy)
        path.lineTo(cx - size // 3, cy + size)
        path.lineTo(cx + size, cy - size)
        painter.drawPath(path)

    def _draw_selection_border(self, painter: QPainter, thumb_rect: QRect):
        """Draw prominent selection border."""
        painter.setPen(QPen(QColor(0, 102, 255), 3))
        painter.setBrush(Qt.NoBrush)

        # Rounded rectangle border
        border_rect = thumb_rect.adjusted(-2, -2, 2, 2)
        path = QPainterPath()
        path.addRoundedRect(QRectF(border_rect), 6, 6)
        painter.drawPath(path)

    def _draw_status_overlay(self, painter: QPainter, thumb_rect: QRect, status: str):
        """
        Draw modern pill-shaped status overlay in bottom-left corner.

        Uses labels for larger thumbnails, symbols for smaller ones.
        """
        if not status or status == 'normal':
            return

        overlay_color = self.STATUS_COLORS.get(status)
        if not overlay_color:
            return

        # Determine if we should show label or symbol based on thumbnail size
        use_label = self.thumbnail_size >= 180

        if use_label:
            label = self.STATUS_LABELS.get(status, '')
            self._draw_pill_badge(painter, thumb_rect, label, overlay_color)
        else:
            symbol = self.STATUS_SYMBOLS.get(status, '')
            self._draw_symbol_badge(painter, thumb_rect, symbol, overlay_color)

    def _draw_pill_badge(self, painter: QPainter, thumb_rect: QRect,
                         label: str, color: QColor):
        """Draw pill-shaped badge with label text."""
        if not label:
            return

        # Calculate text size
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(11)
        painter.setFont(font)

        from PySide6.QtGui import QFontMetrics
        metrics = QFontMetrics(font)
        text_width = metrics.horizontalAdvance(label)
        text_height = metrics.height()

        # Pill dimensions
        padding_h = 8
        padding_v = 4
        pill_width = text_width + padding_h * 2
        pill_height = text_height + padding_v

        # Position in bottom-left
        pill_rect = QRect(
            thumb_rect.left() + 4,
            thumb_rect.bottom() - pill_height - 4,
            pill_width,
            pill_height
        )

        # Draw pill background with slight transparency
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 230))
        painter.setPen(Qt.NoPen)

        path = QPainterPath()
        path.addRoundedRect(QRectF(pill_rect), pill_height // 2, pill_height // 2)
        painter.drawPath(path)

        # Draw text
        painter.setPen(Qt.white)
        text_rect = pill_rect.adjusted(padding_h, 0, -padding_h, 0)
        painter.drawText(text_rect, Qt.AlignCenter, label)

    def _draw_symbol_badge(self, painter: QPainter, thumb_rect: QRect,
                           symbol: str, color: QColor):
        """Draw compact symbol badge for small thumbnails."""
        if not symbol:
            return

        # Badge size
        badge_size = max(20, self.thumbnail_size // 8)

        # Position in bottom-left
        badge_rect = QRect(
            thumb_rect.left() + 4,
            thumb_rect.bottom() - badge_size - 4,
            badge_size,
            badge_size
        )

        # Draw circular background
        painter.setBrush(QColor(color.red(), color.green(), color.blue(), 230))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(badge_rect)

        # Draw symbol
        painter.setPen(Qt.white)
        font = painter.font()
        font.setBold(True)
        font.setPixelSize(badge_size - 6)
        painter.setFont(font)
        painter.drawText(badge_rect, Qt.AlignCenter, symbol)

    def sizeHint(self, option, index) -> QSize:
        """
        Return item size (thumbnail + margins for selection indicators).

        Args:
            option: Style options
            index: Model index

        Returns:
            QSize for the item
        """
        # Margins for selection border and shadow
        size = self.thumbnail_size + 14
        return QSize(size, size)

    def set_thumbnail_size(self, size: int):
        """
        Change thumbnail size.

        Args:
            size: New thumbnail size in pixels
        """
        self.thumbnail_size = size
        logger.debug(f"Delegate thumbnail size changed to {size}px")

    def helpEvent(self, event, view, option, index):
        """
        Show rich tooltip on hover.

        Displays: filename, dimensions, file size, date, status
        """
        if event.type() == QEvent.ToolTip:
            # Get data from model
            filename = index.data(Qt.DisplayRole) or "Unknown"
            status = index.data(Qt.UserRole + 1) or "normal"

            # Get extended info if available (model might provide these)
            file_size = index.data(Qt.UserRole + 10)  # FileSizeRole
            dimensions = index.data(Qt.UserRole + 11)  # DimensionsRole
            date_str = index.data(Qt.UserRole + 12)  # DateRole

            # Build tooltip
            tooltip_lines = [f"<b>{filename}</b>"]

            if dimensions:
                tooltip_lines.append(f"Size: {dimensions}")

            if file_size:
                tooltip_lines.append(f"File: {file_size}")

            if date_str:
                tooltip_lines.append(f"Date: {date_str}")

            if status and status != 'normal':
                status_label = self.STATUS_LABELS.get(status, status.title())
                tooltip_lines.append(f"Status: <span style='color: {self.STATUS_COLORS[status].name()}'>"
                                     f"{status_label}</span>")

            tooltip_html = "<br>".join(tooltip_lines)

            QToolTip.showText(event.globalPos(), tooltip_html, view)
            return True

        return super().helpEvent(event, view, option, index)
