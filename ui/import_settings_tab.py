"""
Import Settings Tab for PyPhotoOrganizer GUI

Contains source folder management, ignored directories, file processing settings,
photo filtering settings, and filename pattern filtering.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QCheckBox, QSpinBox, QLineEdit, QPushButton,
                               QLabel, QListWidget, QMessageBox, QScrollArea,
                               QFormLayout, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QFileDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import os
import constants
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ImportSettingsTab(QWidget):
    """Tab for managing import settings: sources, filtering, and processing."""

    # Signals
    start_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.db_metadata = None  # Will be set when database is loaded
        self.last_clicked_source_row = -1  # For Shift/Ctrl selection in source table
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        main_widget = QWidget()
        layout = QVBoxLayout()

        # Stylesheet for bold GroupBox titles
        groupbox_style = """
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
        """

        # Source Folders Group
        source_group = QGroupBox("Source Folders")
        source_group.setStyleSheet(groupbox_style)
        source_layout = QVBoxLayout()

        # Create table with columns: Enable, Status Icon, Path, Last Scanned, Status
        self.source_table = QTableWidget()
        self.source_table.setColumnCount(5)
        self.source_table.setHorizontalHeaderLabels(["Enable", "Icon", "Source Path", "Last Scanned", "Status"])
        self.source_table.setMinimumHeight(150)
        self.source_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.source_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_table.verticalHeader().setVisible(False)

        # Connect signals for Shift/Ctrl selection
        self.source_table.itemSelectionChanged.connect(self.sync_source_checkboxes_with_selection)
        self.source_table.itemClicked.connect(self.on_source_item_clicked)
        self.source_table.itemDoubleClicked.connect(self.on_source_item_double_clicked)

        # Set column widths
        header = self.source_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.source_table.setColumnWidth(0, 60)
        self.source_table.setColumnWidth(1, 50)
        self.source_table.setMouseTracking(True)

        source_layout.addWidget(self.source_table)

        source_buttons = QHBoxLayout()
        self.add_source_btn = QPushButton("Add Folder...")
        self.add_source_btn.clicked.connect(self.add_source_folder)
        self.remove_source_btn = QPushButton("Remove Selected")
        self.remove_source_btn.clicked.connect(self.remove_source_folder)
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_sources)
        self.refresh_status_btn = QPushButton("Refresh Status")
        self.refresh_status_btn.clicked.connect(self.refresh_source_status)
        source_buttons.addWidget(self.add_source_btn)
        source_buttons.addWidget(self.remove_source_btn)
        source_buttons.addWidget(self.clear_all_btn)
        source_buttons.addWidget(self.refresh_status_btn)
        source_buttons.addStretch()
        source_layout.addLayout(source_buttons)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Ignored Directories Group
        ignored_dirs_group = QGroupBox("Ignored Directories (Skip During Scan)")
        ignored_dirs_group.setStyleSheet(groupbox_style)
        ignored_dirs_layout = QVBoxLayout()

        ignored_dirs_desc = QLabel(
            "Directories matching these patterns will be skipped during scanning. "
            "This helps exclude system folders, thumbnails, and other non-photo directories."
        )
        ignored_dirs_desc.setWordWrap(True)
        ignored_dirs_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        ignored_dirs_layout.addWidget(ignored_dirs_desc)

        ignored_content_layout = QHBoxLayout()

        list_container = QVBoxLayout()
        list_label = QLabel("Ignored Patterns:")
        list_label.setStyleSheet("font-weight: bold;")
        list_container.addWidget(list_label)

        self.ignored_dirs_list = QListWidget()
        self.ignored_dirs_list.setMaximumHeight(120)
        self.ignored_dirs_list.setToolTip("Double-click to edit, select and click Remove to delete")
        list_container.addWidget(self.ignored_dirs_list)
        ignored_content_layout.addLayout(list_container)

        ignored_buttons = QVBoxLayout()
        self.add_ignored_dir_input = QLineEdit()
        self.add_ignored_dir_input.setPlaceholderText("e.g., @eaDir, thumb*, .git, /path/to/skip")
        ignored_buttons.addWidget(self.add_ignored_dir_input)

        self.add_ignored_dir_btn = QPushButton("Add Pattern")
        self.add_ignored_dir_btn.clicked.connect(self.add_ignored_dir_pattern)
        ignored_buttons.addWidget(self.add_ignored_dir_btn)

        self.remove_ignored_dir_btn = QPushButton("Remove Selected")
        self.remove_ignored_dir_btn.clicked.connect(self.remove_ignored_dir_pattern)
        ignored_buttons.addWidget(self.remove_ignored_dir_btn)

        self.add_preset_dirs_btn = QPushButton("Add Common Presets")
        self.add_preset_dirs_btn.setToolTip("Add commonly ignored folders like @eaDir, .git, node_modules, etc.")
        self.add_preset_dirs_btn.clicked.connect(self.add_preset_ignored_dirs)
        ignored_buttons.addWidget(self.add_preset_dirs_btn)

        ignored_buttons.addStretch()
        ignored_content_layout.addLayout(ignored_buttons)
        ignored_dirs_layout.addLayout(ignored_content_layout)

        # Help text
        help_text_widget = QWidget()
        help_text_widget.setStyleSheet("background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; padding: 8px;")
        help_text_layout = QVBoxLayout()
        help_text_layout.setContentsMargins(5, 5, 5, 5)

        help_title = QLabel("ℹ Wildcard Syntax:")
        help_title.setStyleSheet("font-weight: bold; font-size: 10pt;")
        help_text_layout.addWidget(help_title)

        help_examples = QLabel(
            "• <b>*</b> = Match any characters (e.g., <i>thumb*</i> matches thumbnail, thumbs, thumb_cache)<br>"
            "• <b>?</b> = Match single character (e.g., <i>temp?</i> matches temp1, temp2)<br>"
            "• <b>Examples:</b> @eaDir, .git, node_modules, thumb*, /mnt/backup/old"
        )
        help_examples.setWordWrap(True)
        help_examples.setStyleSheet("color: #555; font-size: 9pt;")
        help_text_layout.addWidget(help_examples)

        help_text_widget.setLayout(help_text_layout)
        ignored_dirs_layout.addWidget(help_text_widget)

        self.ignored_dirs_count_label = QLabel("Total patterns: 0")
        self.ignored_dirs_count_label.setStyleSheet("font-style: italic; color: gray; margin-top: 5px;")
        ignored_dirs_layout.addWidget(self.ignored_dirs_count_label)

        ignored_dirs_group.setLayout(ignored_dirs_layout)
        layout.addWidget(ignored_dirs_group)

        # File Processing Settings
        file_group = QGroupBox("File Processing Settings")
        file_group.setStyleSheet(groupbox_style)
        file_layout = QFormLayout()

        self.include_subdirs_check = QCheckBox()
        self.include_subdirs_check.setChecked(True)
        file_layout.addRow("Include subdirectories:", self.include_subdirs_check)

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(10, 1000)
        self.batch_size_spin.setValue(constants.DEFAULT_BATCH_SIZE)
        file_layout.addRow("Batch size:", self.batch_size_spin)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Photo Filtering Settings
        filter_group = QGroupBox("Photo Filtering Settings")
        filter_group.setStyleSheet(groupbox_style)
        filter_layout = QFormLayout()

        self.photo_filter_check = QCheckBox()
        self.photo_filter_check.setChecked(True)
        filter_layout.addRow("Enable photo filter:", self.photo_filter_check)

        self.min_file_size_spin = QSpinBox()
        self.min_file_size_spin.setRange(1, 1000)
        self.min_file_size_spin.setValue(constants.MIN_PHOTO_FILE_SIZE // 1024)
        self.min_file_size_spin.setSuffix(" KB")
        filter_layout.addRow("Min file size:", self.min_file_size_spin)

        self.min_width_spin = QSpinBox()
        self.min_width_spin.setRange(100, 10000)
        self.min_width_spin.setValue(constants.MIN_PHOTO_WIDTH)
        filter_layout.addRow("Min width:", self.min_width_spin)

        self.min_height_spin = QSpinBox()
        self.min_height_spin.setRange(100, 10000)
        self.min_height_spin.setValue(constants.MIN_PHOTO_HEIGHT)
        filter_layout.addRow("Min height:", self.min_height_spin)

        self.max_width_spin = QSpinBox()
        self.max_width_spin.setRange(1000, 50000)
        self.max_width_spin.setValue(constants.MAX_PHOTO_WIDTH)
        filter_layout.addRow("Max width:", self.max_width_spin)

        self.max_height_spin = QSpinBox()
        self.max_height_spin.setRange(1000, 50000)
        self.max_height_spin.setValue(constants.MAX_PHOTO_HEIGHT)
        filter_layout.addRow("Max height:", self.max_height_spin)

        self.exclude_square_spin = QSpinBox()
        self.exclude_square_spin.setRange(0, 1000)
        self.exclude_square_spin.setValue(constants.MIN_SQUARE_SIZE)
        filter_layout.addRow("Exclude square smaller than:", self.exclude_square_spin)

        self.require_exif_check = QCheckBox()
        self.require_exif_check.setChecked(False)
        filter_layout.addRow("Require EXIF data:", self.require_exif_check)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Filename Pattern Filtering
        pattern_group = QGroupBox("Filename Pattern Filtering")
        pattern_group.setStyleSheet(groupbox_style)
        pattern_layout = QVBoxLayout()

        pattern_desc = QLabel(
            "Files containing these patterns in their filename will be filtered out.\n"
            "Common examples: favicon, icon, logo, thumbnail, etc."
        )
        pattern_desc.setWordWrap(True)
        pattern_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        pattern_layout.addWidget(pattern_desc)

        self.filename_filter_check = QCheckBox("Enable filename pattern filtering")
        self.filename_filter_check.setChecked(True)
        self.filename_filter_check.stateChanged.connect(self.update_pattern_controls)
        pattern_layout.addWidget(self.filename_filter_check)

        pattern_content_layout = QHBoxLayout()

        list_container = QVBoxLayout()
        list_label = QLabel("Excluded Patterns:")
        list_label.setStyleSheet("font-weight: bold;")
        list_container.addWidget(list_label)

        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(150)
        list_container.addWidget(self.pattern_list)
        pattern_content_layout.addLayout(list_container)

        pattern_buttons = QVBoxLayout()

        self.add_pattern_input = QLineEdit()
        self.add_pattern_input.setPlaceholderText("e.g., favicon, icon, thumb")
        pattern_buttons.addWidget(self.add_pattern_input)

        self.add_pattern_btn = QPushButton("Add Pattern")
        self.add_pattern_btn.clicked.connect(self.add_pattern)
        pattern_buttons.addWidget(self.add_pattern_btn)

        self.remove_pattern_btn = QPushButton("Remove Selected")
        self.remove_pattern_btn.clicked.connect(self.remove_pattern)
        pattern_buttons.addWidget(self.remove_pattern_btn)

        self.add_default_patterns_btn = QPushButton("Add Default Patterns")
        self.add_default_patterns_btn.clicked.connect(self.restore_default_patterns)
        pattern_buttons.addWidget(self.add_default_patterns_btn)

        pattern_buttons.addStretch()
        pattern_content_layout.addLayout(pattern_buttons)

        pattern_layout.addLayout(pattern_content_layout)

        self.pattern_count_label = QLabel()
        self.pattern_count_label.setStyleSheet("font-style: italic; color: gray;")
        pattern_layout.addWidget(self.pattern_count_label)

        pattern_group.setLayout(pattern_layout)
        layout.addWidget(pattern_group)

        layout.addStretch()

        # Start and Stop buttons at the bottom
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()

        self.start_btn = QPushButton("▶ Start Processing")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 12pt;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_btn.clicked.connect(self.start_clicked.emit)
        buttons_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■ Stop Processing")
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                font-size: 12pt;
                padding: 10px 20px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.stop_btn.setEnabled(False)  # Initially disabled
        buttons_layout.addWidget(self.stop_btn)

        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)

        main_widget.setLayout(layout)
        scroll.setWidget(main_widget)

        # Set main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

        # Initialize pattern count
        self.update_pattern_count()
        self.update_ignored_dirs_count()

    # ========== Source Folder Management Methods ==========

    def add_source_folder(self):
        """Add a source folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            existing_paths = self.get_source_folders()
            if folder in existing_paths:
                QMessageBox.information(self, "Folder Already Added",
                                       "This folder is already in the source list.")
                return

            if self.db_metadata:
                success = self.db_metadata.add_source_directory(folder, enabled=True)
                if not success:
                    QMessageBox.warning(self, "Failed to Add",
                                       "Could not add folder to database.")
                    return

            self._add_source_to_table(folder, enabled=True, last_scanned=None)

    def remove_source_folder(self):
        """Remove source folders with checked checkboxes."""
        rows_to_remove = []
        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    rows_to_remove.append(row)

        if not rows_to_remove:
            QMessageBox.information(self, "No Selection",
                                  "Please check the checkboxes for the folders you want to remove.")
            return

        reply = QMessageBox.question(
            self, "Remove Source Folders",
            f"Remove {len(rows_to_remove)} source folder(s) from the list?\n\n"
            f"This will not delete any files, only remove them from the source list.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        for row in sorted(rows_to_remove, reverse=True):
            path = self.source_table.item(row, 2).text()

            if self.db_metadata:
                self.db_metadata.remove_source_directory(path)

            self.source_table.removeRow(row)

    def clear_all_sources(self):
        """Clear all source folders."""
        if self.source_table.rowCount() == 0:
            QMessageBox.information(self, "No Folders",
                                  "The source folder list is already empty.")
            return

        reply = QMessageBox.question(
            self, "Clear All Source Folders?",
            f"Remove all {self.source_table.rowCount()} source folder(s) from the list?\n\n"
            f"This will not delete any files, only clear the list.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.db_metadata:
                self.db_metadata.clear_all_source_directories()

            self.source_table.setRowCount(0)

    def _add_source_to_table(self, path: str, enabled: bool = True, last_scanned: str = None):
        """Add a source directory to the table."""
        row_position = self.source_table.rowCount()
        self.source_table.insertRow(row_position)

        # Column 0: Enable checkbox
        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.stateChanged.connect(lambda state, p=path: self._on_source_checkbox_changed(p, state))

        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.source_table.setCellWidget(row_position, 0, checkbox_widget)

        # Validate path
        is_available, status_text, status_detail = self._validate_path(path)

        # Column 1: Status icon
        icon_item = QTableWidgetItem()
        if is_available:
            icon_item.setText("✓")
            icon_item.setForeground(QColor(0, 150, 0))
        else:
            icon_item.setText("⚠")
            icon_item.setForeground(QColor(200, 0, 0))
        icon_item.setTextAlignment(Qt.AlignCenter)
        icon_item.setToolTip(status_detail)
        icon_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 1, icon_item)

        # Column 2: Path
        path_item = QTableWidgetItem(path)
        path_item.setToolTip(status_detail)
        path_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 2, path_item)

        # Column 3: Last Scanned
        if last_scanned:
            try:
                dt = datetime.fromisoformat(last_scanned)
                scanned_text = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                scanned_text = "Unknown"
        else:
            scanned_text = "Never"
        scanned_item = QTableWidgetItem(scanned_text)
        scanned_item.setToolTip(f"Last scanned: {scanned_text}")
        scanned_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 3, scanned_item)

        # Column 4: Status
        status_item = QTableWidgetItem(status_text)
        status_item.setToolTip(status_detail)
        if not is_available:
            status_item.setForeground(QColor(200, 0, 0))
        status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 4, status_item)

    def _validate_path(self, path: str) -> tuple:
        """Validate if a path exists and is accessible."""
        try:
            if not os.path.exists(path):
                if path.startswith('/run/user/') and '/gvfs/' in path:
                    return (False, "Not Mounted",
                           "Network share not mounted. Open the share in your file manager first.")
                else:
                    return (False, "Not Found",
                           f"Path does not exist: {path}")

            if not os.path.isdir(path):
                return (False, "Not a Directory",
                       f"Path exists but is not a directory: {path}")

            if not os.access(path, os.R_OK):
                return (False, "Permission Denied",
                       f"Cannot read directory (permission denied): {path}")

            return (True, "Available", f"Path is accessible: {path}")

        except Exception as e:
            return (False, "Error", f"Error checking path: {str(e)}")

    def _on_source_checkbox_changed(self, path: str, state: int):
        """Handle checkbox state change - update database."""
        if self.db_metadata:
            enabled = (state == Qt.Checked)
            self.db_metadata.update_source_enabled(path, enabled)

    def refresh_source_status(self):
        """Refresh the status of all source directories."""
        for row in range(self.source_table.rowCount()):
            path = self.source_table.item(row, 2).text()
            is_available, status_text, status_detail = self._validate_path(path)

            icon_item = self.source_table.item(row, 1)
            if is_available:
                icon_item.setText("✓")
                icon_item.setForeground(QColor(0, 150, 0))
            else:
                icon_item.setText("⚠")
                icon_item.setForeground(QColor(200, 0, 0))
            icon_item.setToolTip(status_detail)

            status_item = self.source_table.item(row, 4)
            status_item.setText(status_text)
            status_item.setToolTip(status_detail)
            if not is_available:
                status_item.setForeground(QColor(200, 0, 0))
            else:
                status_item.setForeground(QColor(0, 0, 0))

    def on_source_item_clicked(self, item):
        """Handle click on source table item - support Shift/Ctrl selection."""
        if item is None:
            return

        row = item.row()
        column = item.column()

        if column != 0:
            self.last_clicked_source_row = row
            return

        checkbox_widget = self.source_table.cellWidget(row, 0)
        if not checkbox_widget:
            return

        checkbox = checkbox_widget.findChild(QCheckBox)
        if not checkbox:
            return

        from PySide6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()

        if modifiers & Qt.ShiftModifier and self.last_clicked_source_row >= 0:
            start_row = min(self.last_clicked_source_row, row)
            end_row = max(self.last_clicked_source_row, row)
            target_state = checkbox.isChecked()

            self.source_table.blockSignals(True)

            for r in range(start_row, end_row + 1):
                self.source_table.selectRow(r)
                cb_widget = self.source_table.cellWidget(r, 0)
                if cb_widget:
                    cb = cb_widget.findChild(QCheckBox)
                    if cb:
                        cb.setChecked(target_state)

            self.source_table.blockSignals(False)

        elif modifiers & Qt.ControlModifier:
            self.last_clicked_source_row = row

        else:
            self.last_clicked_source_row = row

    def on_source_item_double_clicked(self, item):
        """Handle double-click on source table item - toggle checkbox."""
        if item is None:
            return

        row = item.row()
        checkbox_widget = self.source_table.cellWidget(row, 0)

        if checkbox_widget:
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(not checkbox.isChecked())

    def sync_source_checkboxes_with_selection(self):
        """Sync checkbox states with row selection."""
        selected_rows = set(index.row() for index in self.source_table.selectedIndexes())

        self.source_table.blockSignals(True)

        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    is_selected = row in selected_rows
                    if checkbox.isChecked() != is_selected:
                        checkbox.setChecked(is_selected)

        self.source_table.blockSignals(False)

    def load_sources_from_database(self):
        """Load source directories from the database."""
        if not self.db_metadata:
            return

        self.source_table.setRowCount(0)

        sources = self.db_metadata.get_all_source_directories()

        for source in sources:
            self._add_source_to_table(
                path=source['path'],
                enabled=source['enabled'],
                last_scanned=source['last_scanned']
            )

    def get_source_folders(self):
        """Get list of all source folders (regardless of enabled status)."""
        folders = []
        for row in range(self.source_table.rowCount()):
            path_item = self.source_table.item(row, 2)
            if path_item:
                folders.append(path_item.text())
        return folders

    def get_enabled_source_folders(self):
        """Get list of only enabled source folders."""
        enabled_folders = []
        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    path_item = self.source_table.item(row, 2)
                    if path_item:
                        enabled_folders.append(path_item.text())
        return enabled_folders

    # ========== Ignored Directories Methods ==========

    def add_ignored_dir_pattern(self):
        """Add a new ignored directory pattern to the list."""
        pattern = self.add_ignored_dir_input.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Empty Pattern",
                              "Please enter a pattern to add.")
            return

        for i in range(self.ignored_dirs_list.count()):
            if self.ignored_dirs_list.item(i).text().lower() == pattern.lower():
                QMessageBox.information(self, "Pattern Exists",
                                      f"Pattern '{pattern}' already exists in the list.")
                return

        self.ignored_dirs_list.addItem(pattern)
        self.add_ignored_dir_input.clear()
        self.update_ignored_dirs_count()

        self.save_ignored_dirs_to_database()

    def remove_ignored_dir_pattern(self):
        """Remove selected ignored directory pattern from the list."""
        current_item = self.ignored_dirs_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection",
                                  "Please select a pattern to remove.")
            return

        row = self.ignored_dirs_list.row(current_item)
        self.ignored_dirs_list.takeItem(row)
        self.update_ignored_dirs_count()

        self.save_ignored_dirs_to_database()

    def add_preset_ignored_dirs(self):
        """Add common preset patterns for ignored directories."""
        preset_patterns = [
            "@eaDir", ".git", ".svn", "node_modules", "venv", ".venv",
            "__pycache__", "$RECYCLE.BIN", ".Trash-*", "Thumbs.db",
            ".DS_Store", "__MACOSX", ".thumbnails", "*.tmp", ".cache",
        ]

        added_count = 0
        for pattern in preset_patterns:
            exists = False
            for i in range(self.ignored_dirs_list.count()):
                if self.ignored_dirs_list.item(i).text().lower() == pattern.lower():
                    exists = True
                    break

            if not exists:
                self.ignored_dirs_list.addItem(pattern)
                added_count += 1

        self.update_ignored_dirs_count()

        if added_count > 0:
            self.save_ignored_dirs_to_database()
            QMessageBox.information(self, "Presets Added",
                                   f"Added {added_count} preset patterns.\n"
                                   f"Total patterns: {self.ignored_dirs_list.count()}")
        else:
            QMessageBox.information(self, "No New Presets",
                                   "All preset patterns are already in the list.")

    def update_ignored_dirs_count(self):
        """Update the ignored directories count label."""
        count = self.ignored_dirs_list.count()
        self.ignored_dirs_count_label.setText(f"Total patterns: {count}")

    def save_ignored_dirs_to_database(self):
        """Save ignored directories to database."""
        if self.db_metadata is None:
            return

        patterns = []
        for i in range(self.ignored_dirs_list.count()):
            patterns.append(self.ignored_dirs_list.item(i).text())

        try:
            self.db_metadata.set_ignored_directories(patterns)
            logger.info(f"Saved {len(patterns)} ignored directory patterns to database")
        except Exception as e:
            logger.error(f"Failed to save ignored directories: {e}")
            QMessageBox.critical(self, "Error",
                               f"Failed to save ignored directories to database:\n\n{str(e)}")

    def load_ignored_dirs_from_database(self):
        """Load ignored directories from database."""
        if self.db_metadata is None:
            return

        try:
            patterns = self.db_metadata.get_ignored_directories()
            self.ignored_dirs_list.clear()
            for pattern in patterns:
                self.ignored_dirs_list.addItem(pattern)
            self.update_ignored_dirs_count()
            logger.info(f"Loaded {len(patterns)} ignored directory patterns from database")
        except Exception as e:
            logger.error(f"Failed to load ignored directories from database: {e}")

    # ========== Filename Pattern Filtering Methods ==========

    def update_pattern_controls(self):
        """Enable/disable pattern controls based on checkbox."""
        enabled = self.filename_filter_check.isChecked()
        self.pattern_list.setEnabled(enabled)
        self.add_pattern_input.setEnabled(enabled)
        self.add_pattern_btn.setEnabled(enabled)
        self.remove_pattern_btn.setEnabled(enabled)
        self.add_default_patterns_btn.setEnabled(enabled)

    def add_pattern(self):
        """Add a new pattern to the list."""
        pattern = self.add_pattern_input.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Empty Pattern",
                              "Please enter a pattern to add.")
            return

        for i in range(self.pattern_list.count()):
            if self.pattern_list.item(i).text().lower() == pattern.lower():
                QMessageBox.information(self, "Pattern Exists",
                                      f"Pattern '{pattern}' already exists in the list.")
                return

        self.pattern_list.addItem(pattern)
        self.add_pattern_input.clear()
        self.update_pattern_count()

    def remove_pattern(self):
        """Remove selected pattern from the list."""
        current_item = self.pattern_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection",
                                  "Please select a pattern to remove.")
            return

        row = self.pattern_list.row(current_item)
        self.pattern_list.takeItem(row)
        self.update_pattern_count()

    def restore_default_patterns(self):
        """Restore default filename patterns."""
        reply = QMessageBox.question(
            self,
            "Restore Defaults",
            "This will replace all current patterns with the default patterns.\n\n"
            "Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.pattern_list.clear()
            for pattern in constants.DEFAULT_EXCLUDED_PATTERNS:
                self.pattern_list.addItem(pattern)
            self.update_pattern_count()

    def update_pattern_count(self):
        """Update the pattern count label."""
        count = self.pattern_list.count()
        self.pattern_count_label.setText(f"Total patterns: {count}")

    # ========== Configuration Methods ==========

    def get_config(self):
        """Get configuration as dictionary."""
        excluded_patterns = []
        if self.filename_filter_check.isChecked():
            for i in range(self.pattern_list.count()):
                excluded_patterns.append(self.pattern_list.item(i).text())

        config = {
            'include_subdirectories': self.include_subdirs_check.isChecked(),
            'batch_size': self.batch_size_spin.value(),
            'photo_filter_enabled': self.photo_filter_check.isChecked(),
            'min_file_size': self.min_file_size_spin.value() * 1024,
            'min_width': self.min_width_spin.value(),
            'min_height': self.min_height_spin.value(),
            'max_width': self.max_width_spin.value(),
            'max_height': self.max_height_spin.value(),
            'exclude_square_smaller_than': self.exclude_square_spin.value(),
            'require_exif': self.require_exif_check.isChecked(),
            'excluded_filename_patterns': excluded_patterns,
            'move_filtered_files': False,
            'filtered_files_folder': "filtered_non_photos"
        }
        return config

    # ========== Database Integration Methods ==========

    def set_database(self, db_metadata):
        """Set database and load settings."""
        self.db_metadata = db_metadata

        if db_metadata is None:
            return

        # Load sources and ignored directories
        self.load_sources_from_database()
        self.load_ignored_dirs_from_database()

    def set_controls_enabled(self, enabled: bool):
        """Enable or disable controls during processing."""
        # Source folder controls
        self.add_source_btn.setEnabled(enabled)
        self.remove_source_btn.setEnabled(enabled)
        self.clear_all_btn.setEnabled(enabled)
        self.refresh_status_btn.setEnabled(enabled)
        self.source_table.setEnabled(enabled)

        # Ignored directories controls
        self.add_ignored_dir_input.setEnabled(enabled)
        self.add_ignored_dir_btn.setEnabled(enabled)
        self.remove_ignored_dir_btn.setEnabled(enabled)
        self.add_preset_dirs_btn.setEnabled(enabled)
        self.ignored_dirs_list.setEnabled(enabled)

        # File processing controls
        self.include_subdirs_check.setEnabled(enabled)
        self.batch_size_spin.setEnabled(enabled)

        # Photo filter controls
        self.photo_filter_check.setEnabled(enabled)
        self.min_file_size_spin.setEnabled(enabled)
        self.min_width_spin.setEnabled(enabled)
        self.min_height_spin.setEnabled(enabled)
        self.max_width_spin.setEnabled(enabled)
        self.max_height_spin.setEnabled(enabled)
        self.exclude_square_spin.setEnabled(enabled)
        self.require_exif_check.setEnabled(enabled)

        # Pattern filtering controls
        self.filename_filter_check.setEnabled(enabled)
        pattern_enabled = enabled and self.filename_filter_check.isChecked()
        self.pattern_list.setEnabled(pattern_enabled)
        self.add_pattern_input.setEnabled(pattern_enabled)
        self.add_pattern_btn.setEnabled(pattern_enabled)
        self.remove_pattern_btn.setEnabled(pattern_enabled)
        self.add_default_patterns_btn.setEnabled(pattern_enabled)

        # Start/Stop buttons
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)
