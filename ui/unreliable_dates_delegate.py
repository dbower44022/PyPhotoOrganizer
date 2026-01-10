"""
Unreliable Dates Delegate

Custom delegate for rendering thumbnail grid items with status overlays.
Based on triage ThumbnailDelegate but adapted for date correction status.
"""

import logging
from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtCore import Qt, QRect, QSize
from PySide6.QtGui import QPainter, QPixmap, QPen, QColor, QBrush

logger = logging.getLogger(__name__)


class UnreliableDatesDelegate(QStyledItemDelegate):
    """
    Delegate for rendering unreliable dates thumbnails.

    Features:
    - Draws thumbnail centered in cell
    - Selection border (blue, 3px)
    - Status overlay (green=corrected, blue=reorganized)
    - Handles null pixmaps gracefully
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.thumbnail_size = 100  # Default size
        logger.debug("UnreliableDatesDelegate initialized")

    def paint(self, painter: QPainter, option, index):
        """
        Render thumbnail with status overlay and selection border.

        Args:
            painter: QPainter for drawing
            option: Style options
            index: Model index
        """
        try:
            # Get data from model
            pixmap = index.data(Qt.DecorationRole)
            filename = index.data(Qt.DisplayRole)
            status = index.data(Qt.UserRole + 1)

            # Calculate rects
            rect = option.rect
            thumb_rect = QRect(
                rect.x() + 5,
                rect.y() + 5,
                self.thumbnail_size,
                self.thumbnail_size
            )

            # Draw background (darker for selected items)
            if option.state & QStyle.State_Selected:
                painter.fillRect(rect, QColor(66, 133, 244, 50))  # Light blue background
            else:
                painter.fillRect(rect, QColor(45, 45, 45))  # Dark background

            # Draw thumbnail (centered, scaled to fit)
            if pixmap and isinstance(pixmap, QPixmap) and not pixmap.isNull():
                # Scale pixmap to fit thumb_rect while maintaining aspect ratio
                scaled = pixmap.scaled(
                    thumb_rect.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

                # Center the scaled pixmap
                x = thumb_rect.x() + (thumb_rect.width() - scaled.width()) // 2
                y = thumb_rect.y() + (thumb_rect.height() - scaled.height()) // 2

                painter.drawPixmap(x, y, scaled)
            else:
                # Draw placeholder rectangle for loading/missing thumbnails
                painter.fillRect(thumb_rect, QColor(60, 60, 60))
                painter.setPen(QPen(QColor(100, 100, 100), 1))
                painter.drawRect(thumb_rect)

                # Draw "Loading..." text
                painter.setPen(QColor(150, 150, 150))
                painter.drawText(thumb_rect, Qt.AlignCenter, "Loading...")

            # Draw selection border (blue, 3px, outside thumbnail)
            if option.state & QStyle.State_Selected:
                painter.setPen(QPen(QColor(66, 133, 244), 3))
                painter.setBrush(Qt.NoBrush)
                painter.drawRect(thumb_rect.adjusted(-2, -2, 2, 2))

            # Draw status overlay (top-right corner of thumbnail)
            if status in ('corrected', 'reorganized'):
                overlay_size = 20
                overlay_rect = QRect(
                    thumb_rect.right() - overlay_size,
                    thumb_rect.top(),
                    overlay_size,
                    overlay_size
                )

                if status == 'corrected':
                    # Green overlay for corrected (needs reorganization)
                    overlay_color = QColor(0, 150, 0, 220)
                else:
                    # Blue overlay for reorganized (complete)
                    overlay_color = QColor(50, 150, 255, 220)

                painter.fillRect(overlay_rect, overlay_color)

                # Draw checkmark or symbol (optional)
                painter.setPen(QColor(255, 255, 255))
                if status == 'corrected':
                    # Draw "!" for pending reorganization
                    painter.drawText(overlay_rect, Qt.AlignCenter, "!")
                else:
                    # Draw checkmark for complete
                    painter.drawText(overlay_rect, Qt.AlignCenter, "✓")

        except Exception as e:
            logger.error(f"Error in paint(): {e}", exc_info=True)
            # Draw error indicator
            try:
                painter.fillRect(option.rect, QColor(100, 0, 0, 50))
            except:
                pass

    def sizeHint(self, option, index):
        """
        Return item size (thumbnail + minimal margins).

        Args:
            option: Style options
            index: Model index

        Returns:
            QSize for the item
        """
        # Minimal margins to maximize thumbnails on screen
        size = self.thumbnail_size + 10  # Small margins for selection border
        return QSize(size, size)

    def set_thumbnail_size(self, size: int):
        """
        Change thumbnail size.

        Args:
            size: New thumbnail size in pixels
        """
        self.thumbnail_size = size
        logger.debug(f"Delegate thumbnail size changed to {size}px")
