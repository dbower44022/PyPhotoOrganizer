"""
Detachable Preview Window

Separate window for large image viewing with zoom capabilities.
Can be moved to second monitor for dual-screen workflows.
Enhanced with Source/Archive file actions and revision history.
"""

import logging
import os
import json
import subprocess
import platform
from typing import Optional, Dict, Any, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QGroupBox, QApplication, QSplitter,
    QListWidget, QListWidgetItem, QFrame, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent, QFont

from ui.theme import ThemeManager, get_theme

logger = logging.getLogger(__name__)


class StyledLabel(QLabel):
    """Label with consistent styling for file details, theme-aware."""

    def __init__(self, text: str = "", is_value: bool = False, parent=None):
        super().__init__(text, parent)
        self.is_value = is_value
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._apply_style()

    def _apply_style(self):
        """Apply theme-aware styling."""
        theme = get_theme()
        c = theme.colors

        if self.is_value:
            # Value labels - normal weight, primary text color
            self.setStyleSheet(f"color: {c.text_primary}; font-size: 10pt;")
        else:
            # Label/header labels - bold and primary color
            self.setStyleSheet(f"color: {c.primary}; font-weight: bold; font-size: 10pt;")

    def update_theme(self):
        """Update styling when theme changes."""
        self._apply_style()


class DetachablePreviewWindow(QMainWindow):
    """
    Detachable preview window for large image viewing.

    Features:
    - ZoomableImageViewer (rubber band zoom, double-click reset)
    - File details panel with styled labels (paths, dates, status)
    - Source file actions (Open, Open Folder, Copy Path)
    - Archive file actions (Open, Open Folder, Copy Path)
    - Revision history panel showing all versions
    - Double-click revision to preview or launch externally
    - Geometry persistence across sessions
    - Independent window (can move to second monitor)
    """

    # Signal when window is closed
    window_closed = Signal()

    # Signal when correct date button is clicked
    correct_date_clicked = Signal(dict)  # Emits current record

    def __init__(self, db_metadata, parent=None):
        """
        Initialize preview window.

        Args:
            db_metadata: DatabaseMetadata instance for settings
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_metadata = db_metadata
        self.current_record: Optional[Dict[str, Any]] = None
        self.revisions: List[Dict] = []
        self.revision_preview_window = None  # Secondary preview window

        self.setWindowTitle("Image Preview - Date Corrections")
        self.setWindowFlags(Qt.Window)  # Independent window

        self._init_ui()
        self._restore_geometry()

        logger.info("DetachablePreviewWindow initialized")

    def _init_ui(self):
        """Initialize user interface."""
        # Central widget
        central = QWidget()
        main_layout = QVBoxLayout(central)
        main_layout.setSpacing(8)

        # Header: filename (styling applied in _apply_theme)
        self.filename_label = QLabel("No file selected")
        main_layout.addWidget(self.filename_label)

        # Image viewer (from unified preview module)
        try:
            from ui.preview import ZoomableImageViewer
            self.viewer = ZoomableImageViewer()
            main_layout.addWidget(self.viewer, 1)  # Stretch factor 1
        except ImportError:
            logger.error("Failed to import ZoomableImageViewer from ui.preview")
            self.viewer = QLabel("Image viewer not available")
            main_layout.addWidget(self.viewer, 1)

        # Details and Revisions area (horizontal splitter)
        details_splitter = QSplitter(Qt.Horizontal)

        # Left side: File Details
        details_group = QGroupBox("File Details")
        details_layout = QGridLayout()
        details_layout.setSpacing(6)
        details_layout.setColumnStretch(1, 1)  # Value column stretches

        row = 0

        # Source path
        details_layout.addWidget(StyledLabel("Source:"), row, 0, Qt.AlignTop)
        self.detail_source = StyledLabel("-", is_value=True)
        details_layout.addWidget(self.detail_source, row, 1)
        row += 1

        # Archive path
        details_layout.addWidget(StyledLabel("Archive:"), row, 0, Qt.AlignTop)
        self.detail_archive = StyledLabel("-", is_value=True)
        details_layout.addWidget(self.detail_archive, row, 1)
        row += 1

        # Detected Date
        details_layout.addWidget(StyledLabel("Detected Date:"), row, 0, Qt.AlignTop)
        self.detail_detected_date = StyledLabel("-", is_value=True)
        details_layout.addWidget(self.detail_detected_date, row, 1)
        row += 1

        # Corrected Date
        details_layout.addWidget(StyledLabel("Corrected Date:"), row, 0, Qt.AlignTop)
        self.detail_corrected_date = StyledLabel("-", is_value=True)
        details_layout.addWidget(self.detail_corrected_date, row, 1)
        row += 1

        # Flag Reason
        details_layout.addWidget(StyledLabel("Flag Reason:"), row, 0, Qt.AlignTop)
        self.detail_reason = StyledLabel("-", is_value=True)
        details_layout.addWidget(self.detail_reason, row, 1)
        row += 1

        # Status
        details_layout.addWidget(StyledLabel("Status:"), row, 0, Qt.AlignTop)
        self.detail_status = StyledLabel("-", is_value=True)
        details_layout.addWidget(self.detail_status, row, 1)
        row += 1

        # Hash (styling applied in _apply_theme)
        details_layout.addWidget(StyledLabel("Hash:"), row, 0, Qt.AlignTop)
        self.detail_hash = StyledLabel("-", is_value=True)
        details_layout.addWidget(self.detail_hash, row, 1)

        details_group.setLayout(details_layout)
        details_splitter.addWidget(details_group)

        # Right side: Revisions panel
        revisions_group = QGroupBox("Revisions (Double-click to preview)")
        revisions_layout = QVBoxLayout()

        self.revisions_list = QListWidget()
        self.revisions_list.setAlternatingRowColors(True)
        # Styling applied in _apply_theme
        self.revisions_list.itemDoubleClicked.connect(self._on_revision_double_clicked)
        revisions_layout.addWidget(self.revisions_list)

        # Revision info label (styling applied in _apply_theme)
        self.revision_info_label = QLabel("No revisions found")
        revisions_layout.addWidget(self.revision_info_label)

        revisions_group.setLayout(revisions_layout)
        details_splitter.addWidget(revisions_group)

        # Set initial splitter sizes (60% details, 40% revisions)
        details_splitter.setSizes([350, 250])

        main_layout.addWidget(details_splitter)

        # Source file buttons
        source_buttons_group = QGroupBox("Source File Actions")
        source_buttons_layout = QHBoxLayout()
        source_buttons_layout.setSpacing(8)

        self.open_source_file_btn = QPushButton("Open Source File")
        self.open_source_file_btn.setMinimumHeight(36)
        self.open_source_file_btn.clicked.connect(self._on_open_source_file)
        self.open_source_file_btn.setEnabled(False)
        source_buttons_layout.addWidget(self.open_source_file_btn)

        self.open_source_folder_btn = QPushButton("Open Source Folder")
        self.open_source_folder_btn.setMinimumHeight(36)
        self.open_source_folder_btn.clicked.connect(self._on_open_source_folder)
        self.open_source_folder_btn.setEnabled(False)
        source_buttons_layout.addWidget(self.open_source_folder_btn)

        self.copy_source_path_btn = QPushButton("Copy Source Path")
        self.copy_source_path_btn.setMinimumHeight(36)
        self.copy_source_path_btn.clicked.connect(self._on_copy_source_path)
        self.copy_source_path_btn.setEnabled(False)
        source_buttons_layout.addWidget(self.copy_source_path_btn)

        source_buttons_group.setLayout(source_buttons_layout)
        main_layout.addWidget(source_buttons_group)

        # Archive file buttons
        archive_buttons_group = QGroupBox("Archive File Actions")
        archive_buttons_layout = QHBoxLayout()
        archive_buttons_layout.setSpacing(8)

        self.open_archive_file_btn = QPushButton("Open Archive File")
        self.open_archive_file_btn.setMinimumHeight(36)
        self.open_archive_file_btn.clicked.connect(self._on_open_archive_file)
        self.open_archive_file_btn.setEnabled(False)
        archive_buttons_layout.addWidget(self.open_archive_file_btn)

        self.open_archive_folder_btn = QPushButton("Open Archive Folder")
        self.open_archive_folder_btn.setMinimumHeight(36)
        self.open_archive_folder_btn.clicked.connect(self._on_open_archive_folder)
        self.open_archive_folder_btn.setEnabled(False)
        archive_buttons_layout.addWidget(self.open_archive_folder_btn)

        self.copy_archive_path_btn = QPushButton("Copy Archive Path")
        self.copy_archive_path_btn.setMinimumHeight(36)
        self.copy_archive_path_btn.clicked.connect(self._on_copy_archive_path)
        self.copy_archive_path_btn.setEnabled(False)
        archive_buttons_layout.addWidget(self.copy_archive_path_btn)

        archive_buttons_group.setLayout(archive_buttons_layout)
        main_layout.addWidget(archive_buttons_group)

        # Action buttons row
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        # Correct date button (styling applied in _apply_theme)
        self.correct_btn = QPushButton("Correct Date...")
        self.correct_btn.setMinimumHeight(40)
        self.correct_btn.clicked.connect(self.on_correct_date)
        self.correct_btn.setEnabled(False)
        action_layout.addWidget(self.correct_btn)

        action_layout.addStretch()

        # Close button (red, positioned on right)
        self.close_btn = QPushButton("Close")
        self.close_btn.setMinimumHeight(40)
        self.close_btn.setMinimumWidth(100)
        self.close_btn.clicked.connect(self.close)
        action_layout.addWidget(self.close_btn)

        main_layout.addLayout(action_layout)

        self.setCentralWidget(central)

        # Apply theme-aware styling
        self._apply_theme()

    def _apply_theme(self):
        """Apply theme-aware styling to all components."""
        theme = get_theme()
        c = theme.colors

        # Apply global theme stylesheet to window
        self.setStyleSheet(theme.get_global_stylesheet())

        # Filename header
        self.filename_label.setStyleSheet(f"""
            font-size: 14pt;
            font-weight: bold;
            padding: 10px;
            background-color: {c.bg_secondary};
            border-radius: 4px;
            color: {c.text_primary};
        """)

        # Revisions list
        self.revisions_list.setStyleSheet(f"""
            QListWidget {{
                background-color: {c.bg_primary};
                border: 1px solid {c.border_light};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 6px;
                border-bottom: 1px solid {c.border_light};
                color: {c.text_primary};
            }}
            QListWidget::item:selected {{
                background-color: {c.primary};
                color: white;
            }}
            QListWidget::item:hover {{
                background-color: {c.hover_bg};
            }}
            QListWidget::item:alternate {{
                background-color: {c.bg_secondary};
            }}
        """)

        # Revision info label
        self.revision_info_label.setStyleSheet(f"color: {c.text_muted}; font-style: italic;")

        # Hash label - monospace font
        self.detail_hash.setStyleSheet(f"color: {c.text_primary}; font-family: monospace; font-size: 9pt;")

        # Correct date button (primary action)
        self.correct_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
            QPushButton:disabled {{
                background-color: {c.gray_400};
                color: {c.text_disabled};
            }}
        """)

        # Close button (red for visibility)
        self.close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.error};
                color: white;
                font-weight: bold;
                border-radius: 4px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: #DC2626;
            }}
        """)

        # Update all StyledLabels
        for label in self.findChildren(StyledLabel):
            label.update_theme()

        # Update the viewer theme if it has that capability
        if hasattr(self.viewer, 'update_theme'):
            self.viewer.update_theme()
        elif hasattr(self.viewer, 'setStyleSheet'):
            self.viewer.setStyleSheet(f"background-color: {c.bg_tertiary};")

    def update_preview(self, record: Dict[str, Any]):
        """
        Update preview from selected record.

        Args:
            record: UnreliableDates record dict or UniquePhotos record
        """
        try:
            self.current_record = record

            # Update image
            # CRITICAL: Prefer archive_path over source_path because:
            # 1. Rotations/modifications happen on archive files (never modify source files)
            # 2. Archive file reflects current state after any rotations/corrections
            # 3. Source files remain pristine and unmodified
            archive_path = record.get('archive_path') or record.get('file_name', '')
            source_path = record.get('source_path', '')

            # Prefer archive if available, fallback to source
            preview_path = archive_path if (archive_path and os.path.exists(archive_path)) else source_path

            if preview_path and os.path.exists(preview_path):
                if hasattr(self.viewer, 'load_image'):
                    self.viewer.load_image(preview_path)
            else:
                if hasattr(self.viewer, 'clear'):
                    self.viewer.clear()

            # Update filename header
            filename = os.path.basename(source_path) if source_path else os.path.basename(archive_path)
            self.filename_label.setText(filename or "Unknown")

            # Update details
            self.detail_source.setText(source_path or "N/A")
            self.detail_archive.setText(archive_path or "Not organized")

            # Dates
            detected_date = record.get('original_date') or record.get('create_datetime', '-')
            date_source = record.get('date_source', '')
            if date_source:
                self.detail_detected_date.setText(f"{detected_date} (from {date_source})")
            else:
                self.detail_detected_date.setText(detected_date)

            corrected_date = record.get('corrected_date')
            self.detail_corrected_date.setText(corrected_date or "Not corrected")

            # Reason
            reason = record.get('flag_reason') or '-'
            reason = reason.replace('_', ' ').title()
            self.detail_reason.setText(reason)

            # Status (use theme colors)
            theme = get_theme()
            c = theme.colors
            if corrected_date:
                if record.get('needs_reorganization'):
                    status_text = "Corrected (Needs reorganization)"
                    self.detail_status.setStyleSheet(f"color: {c.status_corrected}; font-weight: bold; font-size: 10pt;")
                else:
                    status_text = "Reorganized"
                    self.detail_status.setStyleSheet(f"color: {c.status_reorganized}; font-weight: bold; font-size: 10pt;")
            else:
                status_text = "Pending correction"
                self.detail_status.setStyleSheet(f"color: {c.text_muted}; font-size: 10pt;")
            self.detail_status.setText(status_text)

            # Hash
            file_hash = record.get('file_hash', 'N/A')
            self.detail_hash.setText(file_hash)
            logger.debug(f"update_preview: file_hash={file_hash[:16] if file_hash and file_hash != 'N/A' else file_hash}...")

            # Enable buttons based on path existence
            has_source = bool(source_path and os.path.exists(source_path))
            self.open_source_file_btn.setEnabled(has_source)
            self.open_source_folder_btn.setEnabled(has_source)
            self.copy_source_path_btn.setEnabled(bool(source_path))

            has_archive = bool(archive_path and os.path.exists(archive_path))
            self.open_archive_file_btn.setEnabled(has_archive)
            self.open_archive_folder_btn.setEnabled(has_archive)
            self.copy_archive_path_btn.setEnabled(bool(archive_path))

            self.correct_btn.setEnabled(True)

            # Load revisions
            self._load_revisions(file_hash)

        except Exception as e:
            logger.error(f"Error updating preview: {e}", exc_info=True)

    def _load_revisions(self, file_hash: str):
        """Load and display revision history for the current file."""
        self.revisions_list.clear()
        self.revisions = []

        if not file_hash or file_hash == 'N/A':
            self.revision_info_label.setText("No hash available")
            return

        try:
            # Use PhotoDatabase to get revision chain
            from DuplicateFileDetection import PhotoDatabase

            db_path = self.db_metadata.database_path
            logger.debug(f"Loading revisions for hash {file_hash[:16]}... from database: {db_path}")

            with PhotoDatabase(db_path) as db:
                # Get the full revision chain (original to current)
                chain = db.get_revision_chain(file_hash)
                logger.debug(f"get_revision_chain returned {len(chain) if chain else 0} entries")

                if not chain:
                    logger.debug(f"No revision chain found for hash {file_hash[:16]}...")
                    self.revision_info_label.setText("No revisions found")
                    return

                self.revisions = chain
                logger.info(f"Revision chain for {file_hash[:16]}...: {len(chain)} entries")

                # Populate the list
                for i, rev in enumerate(chain):
                    rev_hash = rev.get('file_hash', '')
                    rev_path = rev.get('file_name', '')
                    rev_reason = rev.get('revision_reason')
                    rev_timestamp = rev.get('revision_timestamp', '')
                    is_current = (rev_hash == file_hash)
                    logger.debug(f"  [{i}] hash={rev_hash[:16]}..., reason={rev_reason}, is_current={is_current}")

                    # Format display text
                    if rev_reason:
                        label = f"v{i}: {rev_reason.title()}"
                    else:
                        label = f"v{i}: Original"

                    if rev_timestamp:
                        # Just show date portion
                        label += f" ({rev_timestamp[:10]})"

                    if is_current:
                        label += " [CURRENT]"

                    # Check if file exists
                    exists = os.path.exists(rev_path) if rev_path else False
                    if not exists:
                        label += " (missing)"

                    item = QListWidgetItem(label)
                    item.setData(Qt.UserRole, rev)  # Store full revision data

                    # Style current item
                    if is_current:
                        font = item.font()
                        font.setBold(True)
                        item.setFont(font)

                    # Gray out missing files
                    if not exists:
                        item.setForeground(Qt.gray)

                    self.revisions_list.addItem(item)

                count = len(chain)
                if count == 1:
                    self.revision_info_label.setText("Original file (no revisions)")
                else:
                    self.revision_info_label.setText(f"{count} versions in chain")

        except Exception as e:
            logger.error(f"Failed to load revisions: {e}", exc_info=True)
            self.revision_info_label.setText(f"Error loading revisions")

    def _on_revision_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on a revision item."""
        rev_data = item.data(Qt.UserRole)
        if not rev_data:
            return

        rev_path = rev_data.get('file_name', '')
        if not rev_path or not os.path.exists(rev_path):
            QMessageBox.warning(
                self, "File Not Found",
                f"Revision file not found:\n{rev_path}"
            )
            return

        # Ask user what to do
        from PySide6.QtWidgets import QInputDialog

        choice, ok = QInputDialog.getItem(
            self, "Open Revision",
            "How would you like to view this revision?",
            ["Preview in new window", "Open with system viewer"],
            0, False
        )

        if not ok:
            return

        if choice == "Preview in new window":
            self._show_revision_preview(rev_data)
        else:
            self._open_file_external(rev_path)

    def _show_revision_preview(self, rev_data: Dict):
        """Show a revision in a secondary preview window."""
        rev_path = rev_data.get('file_name', '')
        theme = get_theme()
        c = theme.colors

        # Create or reuse secondary preview window
        if not self.revision_preview_window:
            from ui.preview import ZoomableImageViewer

            self.revision_preview_window = QMainWindow(self)
            self.revision_preview_window.setWindowTitle("Revision Preview")
            self.revision_preview_window.setWindowFlags(Qt.Window)
            self.revision_preview_window.resize(800, 600)

            central = QWidget()
            layout = QVBoxLayout(central)

            # Header
            self._revision_header = QLabel()
            layout.addWidget(self._revision_header)

            # Viewer
            self._revision_viewer = ZoomableImageViewer()
            layout.addWidget(self._revision_viewer, 1)

            # Info
            self._revision_info = QLabel()
            self._revision_info.setWordWrap(True)
            layout.addWidget(self._revision_info)

            # Close button
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.revision_preview_window.hide)
            layout.addWidget(close_btn)

            self.revision_preview_window.setCentralWidget(central)

        # Apply global and specific theme styling to secondary window
        self.revision_preview_window.setStyleSheet(theme.get_global_stylesheet())
        self._revision_header.setStyleSheet(f"""
            font-size: 12pt;
            font-weight: bold;
            padding: 8px;
            background-color: {c.bg_secondary};
            color: {c.text_primary};
            border-radius: 4px;
        """)
        self._revision_info.setStyleSheet(f"padding: 8px; color: {c.text_muted};")
        if hasattr(self._revision_viewer, 'update_theme'):
            self._revision_viewer.update_theme()
        else:
            self._revision_viewer.setStyleSheet(f"background-color: {c.bg_tertiary};")

        # Update content
        rev_reason = rev_data.get('revision_reason', 'Original')
        rev_timestamp = rev_data.get('revision_timestamp', 'Unknown')
        rev_hash = rev_data.get('file_hash', 'N/A')

        self._revision_header.setText(
            f"Revision: {rev_reason.title() if rev_reason else 'Original'}"
        )

        self._revision_info.setText(
            f"Path: {rev_path}\n"
            f"Timestamp: {rev_timestamp}\n"
            f"Hash: {rev_hash}"
        )

        self._revision_viewer.load_image(rev_path)

        # Show window
        self.revision_preview_window.show()
        self.revision_preview_window.raise_()
        self.revision_preview_window.activateWindow()

    def _open_file_external(self, file_path: str):
        """Open file with system default application."""
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
            QMessageBox.warning(
                self, "Error",
                f"Failed to open file:\n{str(e)}"
            )

    def _open_folder(self, file_path: str):
        """Open folder containing the file."""
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
            QMessageBox.warning(
                self, "Error",
                f"Failed to open folder:\n{str(e)}"
            )

    # Source file actions
    def _on_open_source_file(self):
        """Open source file with default application."""
        if not self.current_record:
            return
        source_path = self.current_record.get('source_path', '')
        if source_path and os.path.exists(source_path):
            self._open_file_external(source_path)

    def _on_open_source_folder(self):
        """Open folder containing the source file."""
        if not self.current_record:
            return
        source_path = self.current_record.get('source_path', '')
        if source_path and os.path.exists(source_path):
            self._open_folder(source_path)

    def _on_copy_source_path(self):
        """Copy source file path to clipboard."""
        if not self.current_record:
            return
        source_path = self.current_record.get('source_path', '')
        if source_path:
            QApplication.clipboard().setText(source_path)
            logger.info(f"Copied source path to clipboard: {source_path}")

    # Archive file actions
    def _on_open_archive_file(self):
        """Open archive file with default application."""
        if not self.current_record:
            return
        archive_path = self.current_record.get('archive_path') or self.current_record.get('file_name', '')
        if archive_path and os.path.exists(archive_path):
            self._open_file_external(archive_path)

    def _on_open_archive_folder(self):
        """Open folder containing the archive file."""
        if not self.current_record:
            return
        archive_path = self.current_record.get('archive_path') or self.current_record.get('file_name', '')
        if archive_path and os.path.exists(archive_path):
            self._open_folder(archive_path)

    def _on_copy_archive_path(self):
        """Copy archive file path to clipboard."""
        if not self.current_record:
            return
        archive_path = self.current_record.get('archive_path') or self.current_record.get('file_name', '')
        if archive_path:
            QApplication.clipboard().setText(archive_path)
            logger.info(f"Copied archive path to clipboard: {archive_path}")

    # Legacy method aliases for backward compatibility
    def on_open_file(self):
        """Open source file (legacy method)."""
        self._on_open_source_file()

    def on_open_folder(self):
        """Open source folder (legacy method)."""
        self._on_open_source_folder()

    def on_copy_path(self):
        """Copy source path (legacy method)."""
        self._on_copy_source_path()

    def on_correct_date(self):
        """Handle correct date button click."""
        if not self.current_record:
            return
        # Emit signal for parent to handle (opens dialog)
        self.correct_date_clicked.emit(self.current_record)

    def closeEvent(self, event: QCloseEvent):
        """Handle window close event - save geometry."""
        self._save_geometry()

        # Close secondary preview if open
        if self.revision_preview_window:
            self.revision_preview_window.close()

        self.window_closed.emit()
        super().closeEvent(event)

    def _save_geometry(self):
        """Save window geometry to database."""
        try:
            geo = self.geometry()
            geometry_dict = {
                'x': geo.x(),
                'y': geo.y(),
                'width': geo.width(),
                'height': geo.height()
            }
            self.db_metadata.set_preview_window_geometry(json.dumps(geometry_dict))
            logger.debug(f"Saved preview window geometry: {geometry_dict}")
        except Exception as e:
            logger.error(f"Failed to save preview window geometry: {e}")

    def _restore_geometry(self):
        """Restore window geometry from database."""
        try:
            geo_json = self.db_metadata.get_preview_window_geometry()
            if geo_json:
                geo = json.loads(geo_json)
                self.setGeometry(geo['x'], geo['y'], geo['width'], geo['height'])
                logger.debug(f"Restored preview window geometry: {geo}")
                return
        except Exception as e:
            logger.debug(f"Could not restore preview window geometry: {e}")

        # Default: 1100x900 centered on parent
        self.resize(1100, 900)
        if self.parent():
            try:
                parent_geo = self.parent().window().frameGeometry()
                x = parent_geo.x() + (parent_geo.width() - 1100) // 2
                y = parent_geo.y() + (parent_geo.height() - 900) // 2
                self.move(x, y)
            except:
                pass  # Use default position if centering fails

        logger.debug("Using default preview window geometry (1100x900)")
