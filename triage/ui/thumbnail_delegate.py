"""
Thumbnail Delegate

Custom delegate for rendering thumbnail grid items.

Renders:
- Thumbnail image (from model's Qt.DecorationRole)
- Filename below thumbnail
- Overlay icons for marks (delete/favorite/date correction)
- Selection border
"""

import logging
from typing import Optional

from PySide6.QtWidgets import QStyledItemDelegate, QStyle
from PySide6.QtCore import Qt, QSize, QRect, QPoint
from PySide6.QtGui import QPainter, QPixmap, QColor, QPen, QFont

logger = logging.getLogger(__name__)


class ThumbnailDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering thumbnail grid items.

    Each item shows:
    - Thumbnail image (centered, scaled to fit)
    - Filename below (truncated if too long)
    - Overlay icons in top-right corner (delete/favorite/date correction)
    - Blue border when selected
    """

    def __init__(self, parent=None):
        """
        Initialize delegate.

        Args:
            parent: Parent QObject
        """
        super().__init__(parent)
        self.thumbnail_size = 256  # Default: medium

        # Load overlay icons (create simple colored rectangles for now)
        # TODO: Replace with actual icon images
        self.icon_delete = self._create_icon('❌', QColor(200, 50, 50))
        self.icon_favorite = self._create_icon('⭐', QColor(255, 200, 50))
        self.icon_date = self._create_icon('📅', QColor(50, 150, 255))

    def _create_icon(self, text: str, color: QColor, size: int = 32) -> QPixmap:
        """
        Create simple icon pixmap with text and background color.

        Args:
            text: Emoji or text to display
            color: Background color
            size: Icon size in pixels

        Returns:
            QPixmap icon
        """
        pixmap = QPixmap(size, size)
        pixmap.fill(color)

        painter = QPainter(pixmap)
        painter.setPen(QColor(255, 255, 255))  # White text
        font = QFont()
        font.setPointSize(size // 3)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, text)
        painter.end()

        return pixmap

    def paint(self, painter: QPainter, option, index):
        """
        Render thumbnail item.

        Args:
            painter: QPainter for drawing
            option: Style option
            index: Model index
        """
        try:
            logger.debug(f"paint() ENTRY - row {index.row() if index and index.isValid() else '?'}")

            # Validate painter is active
            if not painter or not painter.isActive():
                logger.warning("Paint called with inactive painter")
                return

            # Validate index
            if not index or not index.isValid():
                logger.warning("Paint called with invalid index")
                return

            logger.debug(f"paint() validated - starting to paint row {index.row()}")

            painter.save()

            # Get data from model
            logger.debug(f"paint() getting data for row {index.row()}")
            thumbnail = index.data(Qt.DecorationRole)  # QPixmap
            logger.debug(f"paint() got thumbnail: {type(thumbnail)}, isNull={thumbnail.isNull() if isinstance(thumbnail, QPixmap) else 'N/A'}")
            filename = index.data(Qt.DisplayRole)  # str
            logger.debug(f"paint() got filename: {filename}")
            marks = index.data(Qt.UserRole + 1)  # dict
            logger.debug(f"paint() got marks: {marks}")

            # Calculate rectangles
            item_rect = option.rect
            margin = 10

            # Thumbnail area (square, centered)
            thumb_rect = QRect(
                item_rect.x() + margin,
                item_rect.y() + margin,
                self.thumbnail_size,
                self.thumbnail_size
            )

            # Filename area (below thumbnail)
            text_rect = QRect(
                item_rect.x() + margin,
                thumb_rect.bottom() + 5,
                self.thumbnail_size,
                40  # Height for 2 lines of text
            )

            # Draw thumbnail
            if thumbnail and isinstance(thumbnail, QPixmap) and not thumbnail.isNull():
                try:
                    logger.debug(f"Drawing thumbnail pixmap for row {index.row()}")
                    # Scale to fit while maintaining aspect ratio
                    scaled = thumbnail.scaled(
                        thumb_rect.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )

                    # Validate scaled pixmap
                    if scaled and not scaled.isNull():
                        # Center in rectangle
                        x = thumb_rect.x() + (thumb_rect.width() - scaled.width()) // 2
                        y = thumb_rect.y() + (thumb_rect.height() - scaled.height()) // 2
                        painter.drawPixmap(x, y, scaled)
                        logger.debug(f"Drew thumbnail successfully for row {index.row()}")
                    else:
                        logger.warning("Scaled pixmap is null")
                except Exception as draw_error:
                    logger.error(f"Error drawing thumbnail pixmap: {draw_error}", exc_info=True)
            else:
                # Placeholder - DRAW NOTHING (all painting operations crash)
                # CRITICAL: Don't draw rectangles, text, or anything else
                # Even painter.fillRect() causes Qt crashes
                # Just skip drawing entirely - thumbnail not ready yet
                logger.debug(f"Skipping placeholder drawing for row {index.row()} - thumbnail not ready")

            # Draw filename - DISABLED (QPainter.drawText causes Qt crashes)
            # TODO: Re-enable text rendering once Qt text crash is resolved
            # try:
            #     if text_rect.isValid() and text_rect.width() > 0:
            #         painter.setPen(QColor(220, 220, 220))
            #         font = QFont()
            #         font.setPointSize(9)
            #         painter.setFont(font)
            #         display_name = filename or ""
            #         if len(display_name) > 30:
            #             display_name = display_name[:27] + "..."
            #         painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, display_name)
            # except Exception as filename_error:
            #     logger.error(f"Error drawing filename: {filename_error}", exc_info=True)
            logger.debug(f"Skipping filename rendering for stability (filename={filename})")

            # Draw overlay icons - DISABLED (icons created with QPainter.drawText)
            # TODO: Replace with simple colored rectangles or disable entirely
            # try:
            #     if marks and isinstance(marks, dict):
            #         icon_size = 32
            #         icon_x = thumb_rect.right() - icon_size - 5
            #         icon_y = thumb_rect.top() + 5
            #
            #         if marks.get('delete'):
            #             painter.drawPixmap(icon_x, icon_y, icon_size, icon_size, self.icon_delete)
            #             icon_y += icon_size + 5
            #
            #         if marks.get('favorite'):
            #             painter.drawPixmap(icon_x, icon_y, icon_size, icon_size, self.icon_favorite)
            #             icon_y += icon_size + 5
            #
            #         if marks.get('date_correction'):
            #             painter.drawPixmap(icon_x, icon_y, icon_size, icon_size, self.icon_date)
            # except Exception as marks_error:
            #     logger.error(f"Error drawing overlay marks: {marks_error}", exc_info=True)
            logger.debug(f"Skipping overlay icon rendering for stability (marks={marks})")

            # Draw selection border
            try:
                if option.state & QStyle.State_Selected:
                    painter.setPen(QPen(QColor(66, 133, 244), 3))  # Blue, 3px
                    painter.drawRect(thumb_rect.adjusted(-2, -2, 2, 2))
            except Exception as selection_error:
                logger.error(f"Error drawing selection border: {selection_error}", exc_info=True)

            painter.restore()

        except Exception as e:
            logger.error(f"Error in paint method: {e}", exc_info=True)
            # Try to restore painter state
            try:
                if painter and painter.isActive():
                    painter.restore()
            except:
                pass

    def sizeHint(self, option, index):
        """
        Return size hint for grid item.

        Args:
            option: Style option
            index: Model index

        Returns:
            QSize for item
        """
        try:
            logger.debug(f"sizeHint() called for row {index.row() if index and index.isValid() else '?'}")

            # Width and height include thumbnail + margins + text area
            margin = 10
            text_height = 40
            total_size = self.thumbnail_size + (2 * margin) + text_height

            size = QSize(total_size, total_size)
            logger.debug(f"sizeHint() returning: {size.width()}x{size.height()}")
            return size

        except Exception as e:
            logger.error(f"Error in sizeHint(): {e}", exc_info=True)
            # Return safe default
            return QSize(276, 276)  # 256 + 20 + 40

    def set_thumbnail_size(self, size: int):
        """
        Change thumbnail size.

        Args:
            size: Size in pixels (128, 256, 512, or 1024)
        """
        self.thumbnail_size = size
        logger.debug(f"Delegate thumbnail size changed to {size}px")


if __name__ == '__main__':
    # Test delegate rendering
    import sys
    from PySide6.QtWidgets import QApplication, QListView
    from PySide6.QtCore import QAbstractListModel
    from PySide6.QtGui import QPixmap

    logging.basicConfig(level=logging.DEBUG)

    class TestModel(QAbstractListModel):
        """Simple test model."""

        def rowCount(self, parent=None):
            return 10

        def data(self, index, role):
            if role == Qt.DisplayRole:
                return f"test_image_{index.row():03d}.jpg"
            elif role == Qt.DecorationRole:
                # Create colored pixmap
                pixmap = QPixmap(256, 256)
                colors = [
                    QColor(200, 100, 100),
                    QColor(100, 200, 100),
                    QColor(100, 100, 200),
                ]
                pixmap.fill(colors[index.row() % 3])
                return pixmap
            elif role == Qt.UserRole + 1:
                # Some items marked
                return {
                    'delete': index.row() % 3 == 0,
                    'favorite': index.row() % 3 == 1,
                    'date_correction': index.row() % 3 == 2
                }
            return None

    app = QApplication(sys.argv)

    # Create view with custom delegate
    view = QListView()
    view.setViewMode(QListView.IconMode)
    view.setResizeMode(QListView.Adjust)
    view.setSpacing(10)
    view.setUniformItemSizes(True)

    # Set background
    view.setStyleSheet("""
        QListView {
            background-color: #2d2d2d;
            border: none;
        }
        QListView::item:selected {
            background-color: rgba(66, 133, 244, 0.3);
        }
    """)

    # Set model and delegate
    model = TestModel()
    view.setModel(model)

    delegate = ThumbnailDelegate()
    view.setItemDelegate(delegate)

    # Show
    view.setWindowTitle("Thumbnail Delegate Test")
    view.resize(800, 600)
    view.show()

    print("✓ Delegate test window displayed")
    print("  Click items to see selection border")
    print("  Icons show different marks (delete/favorite/date correction)")

    sys.exit(app.exec())
