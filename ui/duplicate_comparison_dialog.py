"""
Duplicate Comparison Dialog

Side-by-side comparison view for verifying duplicate files.
Shows the source file and the existing archive file with synchronized
zoom capabilities to verify they are indeed duplicates.
"""

import logging
import os
from typing import Optional, Dict, Any

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSplitter, QFrame, QGroupBox, QApplication, QCheckBox
)
from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QCloseEvent

from ui.preview import ZoomableImageViewer
from ui.theme import get_theme

logger = logging.getLogger(__name__)


class SynchronizedImageViewer(ZoomableImageViewer):
    """
    ZoomableImageViewer with signals for synchronized zoom operations.

    Emits signals when the user performs zoom actions so that a paired
    viewer can mirror the zoom behavior.
    """

    # Signal emitted when user completes a rubber band zoom
    # Parameters: x, y, width, height (normalized 0-1 relative to image size)
    zoom_region_changed = Signal(float, float, float, float)

    # Signal emitted when user double-clicks to reset zoom
    zoom_reset = Signal()

    def __init__(self, parent=None, dark_mode: bool = False):
        super().__init__(parent, dark_mode)
        self._syncing = False  # Prevent recursive sync

    def mouseReleaseEvent(self, event):
        """Override to emit zoom signal after rubber band zoom."""
        if event.button() == Qt.LeftButton and self._is_rubber_banding:
            if self._rubber_band_origin:
                current_pos = self.mapToScene(event.pos())

                # Calculate zoom rectangle in scene coordinates
                x = min(self._rubber_band_origin.x(), current_pos.x())
                y = min(self._rubber_band_origin.y(), current_pos.y())
                width = abs(current_pos.x() - self._rubber_band_origin.x())
                height = abs(current_pos.y() - self._rubber_band_origin.y())

                # Only emit if rectangle is large enough (> 10 pixels)
                if width > 10 and height > 10 and self._pixmap_item and not self._syncing:
                    # Normalize to image dimensions for cross-viewer sync
                    img_rect = self._pixmap_item.boundingRect()
                    if img_rect.width() > 0 and img_rect.height() > 0:
                        norm_x = x / img_rect.width()
                        norm_y = y / img_rect.height()
                        norm_w = width / img_rect.width()
                        norm_h = height / img_rect.height()
                        # Emit after parent handles the zoom
                        super().mouseReleaseEvent(event)
                        self.zoom_region_changed.emit(norm_x, norm_y, norm_w, norm_h)
                        return

        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        """Override to emit reset signal after double-click zoom reset."""
        if event.button() == Qt.LeftButton and not self._syncing:
            super().mouseDoubleClickEvent(event)
            self.zoom_reset.emit()
        else:
            super().mouseDoubleClickEvent(event)

    def apply_normalized_zoom(self, norm_x: float, norm_y: float,
                               norm_w: float, norm_h: float):
        """
        Apply a zoom region using normalized coordinates.

        Args:
            norm_x, norm_y: Top-left corner (0-1 relative to image)
            norm_w, norm_h: Width and height (0-1 relative to image)
        """
        if not self._pixmap_item or self._syncing:
            return

        self._syncing = True
        try:
            img_rect = self._pixmap_item.boundingRect()
            if img_rect.width() > 0 and img_rect.height() > 0:
                # Convert normalized coords to scene coords
                x = norm_x * img_rect.width()
                y = norm_y * img_rect.height()
                w = norm_w * img_rect.width()
                h = norm_h * img_rect.height()

                zoom_rect = QRectF(x, y, w, h)
                self.fitInView(zoom_rect, Qt.KeepAspectRatio)
                self._is_custom_zoom = True
                self.viewport().update()
        finally:
            self._syncing = False

    def sync_zoom_to_fit(self):
        """Reset zoom without emitting signal (for sync purposes)."""
        self._syncing = True
        try:
            self._zoom_to_fit()
        finally:
            self._syncing = False


class DuplicateComparisonDialog(QDialog):
    """
    Dialog for comparing a source file with its duplicate in the archive.

    Shows two SynchronizedImageViewer widgets side-by-side with file details
    for each. Zoom actions are synchronized between viewers.

    Features:
        - Side-by-side comparison with synchronized zoom
        - Rubber band zoom mirrors to other viewer
        - Double-click reset mirrors to other viewer
        - File details (path, size, dimensions) for each file
        - Theme-aware styling
    """

    def __init__(self, parent=None):
        """
        Initialize the comparison dialog.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.setWindowTitle("Duplicate Comparison")
        self.setModal(False)  # Allow interaction with main window
        self.resize(1400, 800)

        self._source_path: Optional[str] = None
        self._archive_path: Optional[str] = None
        self._sync_enabled = True  # Zoom synchronization enabled by default

        self._init_ui()
        self._connect_sync_signals()
        self._apply_theme()

        logger.info("DuplicateComparisonDialog initialized")

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)

        # Header
        self.header_label = QLabel("Compare duplicate files - zoom is synchronized between panels")
        self.header_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.header_label)

        # Main splitter for side-by-side view
        self.splitter = QSplitter(Qt.Horizontal)

        # Left side: Source file
        self.source_group = QGroupBox("Source File (Import Candidate)")
        source_layout = QVBoxLayout(self.source_group)

        self.source_path_label = QLabel("Path: Not loaded")
        self.source_path_label.setWordWrap(True)
        self.source_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        source_layout.addWidget(self.source_path_label)

        self.source_info_label = QLabel("Size: - | Dimensions: -")
        source_layout.addWidget(self.source_info_label)

        self.source_viewer = SynchronizedImageViewer()
        self.source_viewer.setMinimumSize(400, 400)
        source_layout.addWidget(self.source_viewer, 1)

        # Source action buttons
        source_actions = QHBoxLayout()
        self.source_open_btn = QPushButton("Open File")
        self.source_open_btn.clicked.connect(self._open_source_file)
        source_actions.addWidget(self.source_open_btn)

        self.source_folder_btn = QPushButton("Open Folder")
        self.source_folder_btn.clicked.connect(self._open_source_folder)
        source_actions.addWidget(self.source_folder_btn)

        self.source_copy_btn = QPushButton("Copy Path")
        self.source_copy_btn.clicked.connect(self._copy_source_path)
        source_actions.addWidget(self.source_copy_btn)

        source_actions.addStretch()
        source_layout.addLayout(source_actions)

        self.splitter.addWidget(self.source_group)

        # Right side: Archive file
        self.archive_group = QGroupBox("Archive File (Existing)")
        archive_layout = QVBoxLayout(self.archive_group)

        self.archive_path_label = QLabel("Path: Not loaded")
        self.archive_path_label.setWordWrap(True)
        self.archive_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        archive_layout.addWidget(self.archive_path_label)

        self.archive_info_label = QLabel("Size: - | Dimensions: -")
        archive_layout.addWidget(self.archive_info_label)

        self.archive_viewer = SynchronizedImageViewer()
        self.archive_viewer.setMinimumSize(400, 400)
        archive_layout.addWidget(self.archive_viewer, 1)

        # Archive action buttons
        archive_actions = QHBoxLayout()
        self.archive_open_btn = QPushButton("Open File")
        self.archive_open_btn.clicked.connect(self._open_archive_file)
        archive_actions.addWidget(self.archive_open_btn)

        self.archive_folder_btn = QPushButton("Open Folder")
        self.archive_folder_btn.clicked.connect(self._open_archive_folder)
        archive_actions.addWidget(self.archive_folder_btn)

        self.archive_copy_btn = QPushButton("Copy Path")
        self.archive_copy_btn.clicked.connect(self._copy_archive_path)
        archive_actions.addWidget(self.archive_copy_btn)

        archive_actions.addStretch()
        archive_layout.addLayout(archive_actions)

        self.splitter.addWidget(self.archive_group)

        # Set equal sizes for splitter
        self.splitter.setSizes([700, 700])

        main_layout.addWidget(self.splitter, 1)

        # Bottom buttons
        bottom_layout = QHBoxLayout()

        # Sync checkbox
        self.sync_checkbox = QCheckBox("Synchronize Zoom")
        self.sync_checkbox.setChecked(True)
        self.sync_checkbox.setToolTip("When enabled, zoom actions in one panel are mirrored to the other")
        self.sync_checkbox.stateChanged.connect(self._on_sync_changed)
        bottom_layout.addWidget(self.sync_checkbox)

        bottom_layout.addSpacing(20)

        # Reset zoom buttons
        self.reset_both_zoom_btn = QPushButton("Reset Zoom")
        self.reset_both_zoom_btn.clicked.connect(self._reset_both_zoom)
        self.reset_both_zoom_btn.setToolTip("Reset zoom on both panels (or double-click either image)")
        bottom_layout.addWidget(self.reset_both_zoom_btn)

        bottom_layout.addStretch()

        # Close button
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumWidth(100)
        self.close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(self.close_btn)

        main_layout.addLayout(bottom_layout)

    def _connect_sync_signals(self):
        """Connect synchronization signals between viewers."""
        # Source viewer zoom -> archive viewer
        self.source_viewer.zoom_region_changed.connect(self._on_source_zoom)
        self.source_viewer.zoom_reset.connect(self._on_source_reset)

        # Archive viewer zoom -> source viewer
        self.archive_viewer.zoom_region_changed.connect(self._on_archive_zoom)
        self.archive_viewer.zoom_reset.connect(self._on_archive_reset)

    def _on_sync_changed(self, state):
        """Handle sync checkbox state change."""
        self._sync_enabled = (state == Qt.Checked)
        logger.debug(f"Zoom sync {'enabled' if self._sync_enabled else 'disabled'}")

    def _on_source_zoom(self, norm_x, norm_y, norm_w, norm_h):
        """Handle zoom from source viewer - apply to archive viewer."""
        if self._sync_enabled:
            self.archive_viewer.apply_normalized_zoom(norm_x, norm_y, norm_w, norm_h)

    def _on_archive_zoom(self, norm_x, norm_y, norm_w, norm_h):
        """Handle zoom from archive viewer - apply to source viewer."""
        if self._sync_enabled:
            self.source_viewer.apply_normalized_zoom(norm_x, norm_y, norm_w, norm_h)

    def _on_source_reset(self):
        """Handle zoom reset from source viewer - apply to archive viewer."""
        if self._sync_enabled:
            self.archive_viewer.sync_zoom_to_fit()

    def _on_archive_reset(self):
        """Handle zoom reset from archive viewer - apply to source viewer."""
        if self._sync_enabled:
            self.source_viewer.sync_zoom_to_fit()

    def _apply_theme(self):
        """Apply theme-aware styling."""
        theme = get_theme()
        c = theme.colors

        self.setStyleSheet(theme.get_global_stylesheet())

        # Header - use bright color for visibility
        self.header_label.setStyleSheet(f"""
            font-size: 13pt;
            font-weight: bold;
            color: white;
            padding: 10px;
            background-color: {c.primary};
            border-radius: 4px;
        """)

        # Group boxes
        group_style = f"""
            QGroupBox {{
                font-size: 11pt;
                font-weight: bold;
                color: {c.primary};
                border: 2px solid {c.border_light};
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 8px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 6px;
                background-color: {c.bg_primary};
            }}
        """
        self.source_group.setStyleSheet(group_style)
        self.archive_group.setStyleSheet(group_style)

        # Path labels
        path_style = f"color: {c.text_muted}; font-size: 10pt; padding: 4px;"
        self.source_path_label.setStyleSheet(path_style)
        self.archive_path_label.setStyleSheet(path_style)

        # Info labels
        info_style = f"color: {c.text_primary}; font-size: 10pt; padding: 4px;"
        self.source_info_label.setStyleSheet(info_style)
        self.archive_info_label.setStyleSheet(info_style)

        # Action buttons (secondary style)
        action_btn_style = f"""
            QPushButton {{
                background-color: {c.bg_tertiary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10pt;
            }}
            QPushButton:hover {{
                background-color: {c.primary};
                color: white;
                border-color: {c.primary};
            }}
        """
        for btn in [self.source_open_btn, self.source_folder_btn, self.source_copy_btn,
                    self.archive_open_btn, self.archive_folder_btn, self.archive_copy_btn,
                    self.reset_both_zoom_btn]:
            btn.setStyleSheet(action_btn_style)

        # Sync checkbox - make it clearly visible
        self.sync_checkbox.setStyleSheet(f"""
            QCheckBox {{
                color: white;
                font-size: 11pt;
                font-weight: bold;
                padding: 6px 12px;
                background-color: {c.bg_tertiary};
                border: 1px solid {c.border_light};
                border-radius: 4px;
            }}
            QCheckBox::indicator {{
                width: 20px;
                height: 20px;
            }}
            QCheckBox::indicator:unchecked {{
                background-color: {c.bg_primary};
                border: 2px solid {c.border_light};
                border-radius: 3px;
            }}
            QCheckBox::indicator:checked {{
                background-color: {c.primary};
                border: 2px solid {c.primary};
                border-radius: 3px;
            }}
            QCheckBox:hover {{
                background-color: {c.hover_bg};
            }}
        """)

        # Close button (primary style)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 8px 16px;
                font-size: 11pt;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
        """)

    def set_files(self, source_path: str, archive_path: str,
                  source_info: Optional[Dict[str, Any]] = None,
                  archive_info: Optional[Dict[str, Any]] = None):
        """
        Set the files to compare.

        Args:
            source_path: Path to the source file (import candidate)
            archive_path: Path to the existing archive file
            source_info: Optional dict with source file info (size, etc.)
            archive_info: Optional dict with archive file info
        """
        self._source_path = source_path
        self._archive_path = archive_path

        # Load source file
        self.source_path_label.setText(f"Path: {source_path}")
        if source_path and os.path.exists(source_path):
            self.source_viewer.load_image(source_path)
            source_size = self._format_file_size(os.path.getsize(source_path))
            source_dims = self.source_viewer.image_dimensions
            dims_str = f"{source_dims[0]}x{source_dims[1]}" if source_dims else "N/A"
            self.source_info_label.setText(f"Size: {source_size} | Dimensions: {dims_str}")
        else:
            self.source_viewer.clear()
            self.source_info_label.setText("Size: - | Dimensions: - (File not found)")

        # Load archive file
        self.archive_path_label.setText(f"Path: {archive_path}")
        if archive_path and os.path.exists(archive_path):
            self.archive_viewer.load_image(archive_path)
            archive_size = self._format_file_size(os.path.getsize(archive_path))
            archive_dims = self.archive_viewer.image_dimensions
            dims_str = f"{archive_dims[0]}x{archive_dims[1]}" if archive_dims else "N/A"
            self.archive_info_label.setText(f"Size: {archive_size} | Dimensions: {dims_str}")
        else:
            self.archive_viewer.clear()
            self.archive_info_label.setText("Size: - | Dimensions: - (File not found)")

        # Update window title
        source_name = os.path.basename(source_path) if source_path else "Unknown"
        self.setWindowTitle(f"Duplicate Comparison - {source_name}")

        logger.info(f"Comparing: {source_path} vs {archive_path}")

    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable format."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

    def _reset_both_zoom(self):
        """Reset zoom on both viewers."""
        self.source_viewer.zoom_to_fit()
        self.archive_viewer.zoom_to_fit()

    def _open_source_file(self):
        """Open source file with system default application."""
        if self._source_path and os.path.exists(self._source_path):
            self._open_file_external(self._source_path)

    def _open_source_folder(self):
        """Open folder containing the source file."""
        if self._source_path and os.path.exists(self._source_path):
            self._open_folder(self._source_path)

    def _copy_source_path(self):
        """Copy source file path to clipboard."""
        if self._source_path:
            QApplication.clipboard().setText(self._source_path)
            logger.info(f"Copied source path: {self._source_path}")

    def _open_archive_file(self):
        """Open archive file with system default application."""
        if self._archive_path and os.path.exists(self._archive_path):
            self._open_file_external(self._archive_path)

    def _open_archive_folder(self):
        """Open folder containing the archive file."""
        if self._archive_path and os.path.exists(self._archive_path):
            self._open_folder(self._archive_path)

    def _copy_archive_path(self):
        """Copy archive file path to clipboard."""
        if self._archive_path:
            QApplication.clipboard().setText(self._archive_path)
            logger.info(f"Copied archive path: {self._archive_path}")

    def _open_file_external(self, file_path: str):
        """Open file with system default application."""
        import platform
        import subprocess

        try:
            system = platform.system()
            if system == 'Windows':
                os.startfile(file_path)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', file_path], check=True)
            else:  # Linux and others
                subprocess.run(['xdg-open', file_path], check=True)
            logger.info(f"Opened file externally: {file_path}")
        except Exception as e:
            logger.error(f"Failed to open file: {e}", exc_info=True)

    def _open_folder(self, file_path: str):
        """Open folder containing the file."""
        import platform
        import subprocess

        try:
            folder_path = os.path.dirname(file_path)
            system = platform.system()
            if system == 'Windows':
                subprocess.run(['explorer', '/select,', file_path], check=True)
            elif system == 'Darwin':  # macOS
                subprocess.run(['open', '-R', file_path], check=True)
            else:  # Linux and others
                subprocess.run(['xdg-open', folder_path], check=True)
            logger.info(f"Opened folder: {folder_path}")
        except Exception as e:
            logger.error(f"Failed to open folder: {e}", exc_info=True)

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close."""
        logger.debug("DuplicateComparisonDialog closed")
        event.accept()
