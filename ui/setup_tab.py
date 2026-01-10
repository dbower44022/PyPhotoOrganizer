"""
Setup Tab for PyPhotoOrganizer GUI

Allows users to configure source/destination folders and operation mode.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QRadioButton,
                               QButtonGroup, QLabel, QFileDialog, QMessageBox, QHeaderView,
                               QAbstractItemView, QCheckBox, QListWidget)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QColor
import os
import logging
from datetime import datetime
from database_metadata import DatabaseMetadata

logger = logging.getLogger(__name__)


class SetupTab(QWidget):
    """Tab for configuring folders and operation mode."""

    start_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.db_metadata = None  # Will be set when database is loaded
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Source folders group
        source_group = QGroupBox("Source Folders")
        source_layout = QVBoxLayout()

        # Create table with columns: Enable, Status Icon, Path, Last Scanned, Status
        self.source_table = QTableWidget()
        self.source_table.setColumnCount(5)
        self.source_table.setHorizontalHeaderLabels(["Enable", "Icon", "Source Path", "Last Scanned", "Status"])
        self.source_table.setMinimumHeight(150)
        self.source_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.source_table.setSelectionMode(QAbstractItemView.ExtendedSelection)  # Supports Shift/Ctrl selection
        self.source_table.verticalHeader().setVisible(False)

        # Track last clicked row for shift-selection
        self.last_clicked_row = -1

        # Connect signals for Shift/Ctrl selection on checkbox column and sync
        self.source_table.itemSelectionChanged.connect(self.sync_checkboxes_with_selection)
        self.source_table.itemClicked.connect(self.on_item_clicked)
        self.source_table.itemDoubleClicked.connect(self.on_item_double_clicked)

        # Set column widths
        header = self.source_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Enable checkbox
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # Icon
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Path
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Last Scanned
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Status
        self.source_table.setColumnWidth(0, 60)  # Enable checkbox column
        self.source_table.setColumnWidth(1, 50)  # Icon column

        # Enable tooltips
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

        # Ignored Directories group
        ignored_dirs_group = QGroupBox("Ignored Directories (Skip During Scan)")
        ignored_dirs_layout = QVBoxLayout()

        # Description
        ignored_dirs_desc = QLabel(
            "Directories matching these patterns will be skipped during scanning. "
            "This helps exclude system folders, thumbnails, and other non-photo directories."
        )
        ignored_dirs_desc.setWordWrap(True)
        ignored_dirs_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        ignored_dirs_layout.addWidget(ignored_dirs_desc)

        # Pattern list and controls in horizontal layout
        ignored_content_layout = QHBoxLayout()

        # Left side: List widget
        list_container = QVBoxLayout()
        list_label = QLabel("Ignored Patterns:")
        list_label.setStyleSheet("font-weight: bold;")
        list_container.addWidget(list_label)

        self.ignored_dirs_list = QListWidget()
        self.ignored_dirs_list.setMaximumHeight(120)
        self.ignored_dirs_list.setToolTip("Double-click to edit, select and click Remove to delete")
        list_container.addWidget(self.ignored_dirs_list)
        ignored_content_layout.addLayout(list_container)

        # Right side: Control buttons
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

        # Help text in expandable/collapsible format
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

        # Statistics label
        self.ignored_dirs_count_label = QLabel("Total patterns: 0")
        self.ignored_dirs_count_label.setStyleSheet("font-style: italic; color: gray; margin-top: 5px;")
        ignored_dirs_layout.addWidget(self.ignored_dirs_count_label)

        ignored_dirs_group.setLayout(ignored_dirs_layout)
        layout.addWidget(ignored_dirs_group)

        # Destination folder group
        dest_group = QGroupBox("Destination Folder (Archive Location)")
        dest_layout = QVBoxLayout()

        # Info label
        dest_info = QLabel(
            "The destination folder is controlled by your database.\n"
            "To change it, use the Database tab."
        )
        dest_info.setWordWrap(True)
        dest_info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        dest_layout.addWidget(dest_info)

        # Destination path with browse button
        dest_path_layout = QHBoxLayout()

        self.dest_edit = QLineEdit()
        self.dest_edit.setPlaceholderText("Archive location from database...")
        self.dest_edit.setReadOnly(True)
        self.dest_edit.setStyleSheet("background-color: #f5f5f5;")
        dest_path_layout.addWidget(self.dest_edit)

        self.browse_dest_btn = QPushButton("Browse...")
        self.browse_dest_btn.setToolTip("Destination is managed by the database")
        self.browse_dest_btn.clicked.connect(self.browse_destination)
        dest_path_layout.addWidget(self.browse_dest_btn)

        dest_layout.addLayout(dest_path_layout)

        dest_group.setLayout(dest_layout)
        layout.addWidget(dest_group)

        # Operation mode group
        mode_group = QGroupBox("Operation Mode")
        mode_layout = QVBoxLayout()

        self.copy_radio = QRadioButton("Copy Files (Safe - keeps originals)")
        self.copy_radio.setChecked(True)

        self.move_radio = QRadioButton("Move Files (Destructive - deletes originals)")

        self.mode_group = QButtonGroup()
        self.mode_group.addButton(self.copy_radio)
        self.mode_group.addButton(self.move_radio)

        mode_layout.addWidget(self.copy_radio)
        mode_layout.addWidget(self.move_radio)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Control buttons
        button_layout = QHBoxLayout()

        self.start_btn = QPushButton("Start Processing")
        self.start_btn.clicked.connect(self.start_clicked.emit)
        self.start_btn.setMinimumHeight(40)

        self.stop_btn = QPushButton("Stop Processing")
        self.stop_btn.clicked.connect(self.stop_clicked.emit)
        self.stop_btn.setEnabled(False)
        self.stop_btn.setMinimumHeight(40)

        button_layout.addWidget(self.start_btn)
        button_layout.addWidget(self.stop_btn)

        layout.addLayout(button_layout)

        layout.addStretch()
        self.setLayout(layout)

    def add_source_folder(self):
        """Add a source folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            # Check if already in table
            existing_paths = self.get_source_folders()
            if folder in existing_paths:
                msg_box = QMessageBox(QMessageBox.Information, "Folder Already Added",
                                     "This folder is already in the source list.", QMessageBox.Ok, self)
                self._center_dialog(msg_box)
                msg_box.exec()
                return

            # Add to database if available
            if self.db_metadata:
                success = self.db_metadata.add_source_directory(folder, enabled=True)
                if not success:
                    msg_box = QMessageBox(QMessageBox.Warning, "Failed to Add",
                                         "Could not add folder to database.", QMessageBox.Ok, self)
                    self._center_dialog(msg_box)
                    msg_box.exec()
                    return

            # Add to table
            self._add_source_to_table(folder, enabled=True, last_scanned=None)

    def remove_source_folder(self):
        """Remove source folders with checked checkboxes."""
        # Collect rows to remove (those with checked checkboxes)
        rows_to_remove = []
        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                # Find the QCheckBox within the widget
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    rows_to_remove.append(row)

        if not rows_to_remove:
            msg_box = QMessageBox(
                QMessageBox.Information,
                "No Selection",
                "Please check the checkboxes for the folders you want to remove.",
                QMessageBox.Ok,
                self
            )
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        # Confirm removal
        msg_box = QMessageBox(
            QMessageBox.Question,
            "Remove Source Folders",
            f"Remove {len(rows_to_remove)} source folder(s) from the list?\n\n"
            f"This will not delete any files, only remove them from the source list.",
            QMessageBox.Yes | QMessageBox.No,
            self
        )
        msg_box.setDefaultButton(QMessageBox.No)
        self._center_dialog(msg_box)
        if msg_box.exec() != QMessageBox.Yes:
            return

        # Remove rows in reverse order to avoid index shifting
        for row in sorted(rows_to_remove, reverse=True):
            # Get the path from the row
            path = self.source_table.item(row, 2).text()

            # Remove from database if available
            if self.db_metadata:
                self.db_metadata.remove_source_directory(path)

            # Remove from table
            self.source_table.removeRow(row)

    def clear_all_sources(self):
        """Clear all source folders."""
        if self.source_table.rowCount() == 0:
            msg_box = QMessageBox(
                QMessageBox.Information,
                "No Folders",
                "The source folder list is already empty.",
                QMessageBox.Ok,
                self
            )
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        msg_box = QMessageBox(
            QMessageBox.Question,
            "Clear All Source Folders?",
            f"Remove all {self.source_table.rowCount()} source folder(s) from the list?\n\n"
            f"This will not delete any files, only clear the list.",
            QMessageBox.Yes | QMessageBox.No,
            self
        )
        msg_box.setDefaultButton(QMessageBox.No)
        self._center_dialog(msg_box)
        response = msg_box.exec()

        if response == QMessageBox.Yes:
            # Clear from database if available
            if self.db_metadata:
                self.db_metadata.clear_all_source_directories()

            # Clear from table
            self.source_table.setRowCount(0)

    def _add_source_to_table(self, path: str, enabled: bool = True, last_scanned: str = None):
        """
        Add a source directory to the table.

        Args:
            path: Directory path
            enabled: Whether the source is enabled for scanning
            last_scanned: Last scanned timestamp (ISO format)
        """
        row_position = self.source_table.rowCount()
        self.source_table.insertRow(row_position)

        # Column 0: Enable checkbox
        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.stateChanged.connect(lambda state, p=path: self._on_checkbox_changed(p, state))

        # Debug logging
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Creating checkbox for {path}: enabled={enabled}, isChecked={checkbox.isChecked()}")

        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.source_table.setCellWidget(row_position, 0, checkbox_widget)

        # Validate path and get status
        is_available, status_text, status_detail = self._validate_path(path)

        # Column 1: Status icon
        icon_item = QTableWidgetItem()
        if is_available:
            icon_item.setText("✓")
            icon_item.setForeground(QColor(0, 150, 0))  # Green
        else:
            icon_item.setText("⚠")
            icon_item.setForeground(QColor(200, 0, 0))  # Red
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
                # Parse ISO format and display user-friendly
                dt = datetime.fromisoformat(last_scanned)
                scanned_text = dt.strftime("%Y-%m-%d %H:%M")
            except Exception as e:
                logger.warning(f"Failed to parse last_scanned timestamp '{last_scanned}': {e}")
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
            status_item.setForeground(QColor(200, 0, 0))  # Red text
        status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 4, status_item)

    def _validate_path(self, path: str) -> tuple:
        """
        Validate if a path exists and is accessible.

        Returns:
            Tuple of (is_available: bool, status_text: str, status_detail: str)
        """
        try:
            if not os.path.exists(path):
                # Check if it's a network path that might not be mounted
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

            # Path is valid and accessible
            return (True, "Available", f"Path is accessible: {path}")

        except Exception as e:
            return (False, "Error", f"Error checking path: {str(e)}")

    def _on_checkbox_changed(self, path: str, state: int):
        """Handle checkbox state change - update database."""
        if self.db_metadata:
            enabled = (state == Qt.Checked)
            self.db_metadata.update_source_enabled(path, enabled)

    def refresh_source_status(self):
        """Refresh the status of all source directories."""
        for row in range(self.source_table.rowCount()):
            path = self.source_table.item(row, 2).text()

            # Validate path and get status
            is_available, status_text, status_detail = self._validate_path(path)

            # Update icon (column 1)
            icon_item = self.source_table.item(row, 1)
            if is_available:
                icon_item.setText("✓")
                icon_item.setForeground(QColor(0, 150, 0))  # Green
            else:
                icon_item.setText("⚠")
                icon_item.setForeground(QColor(200, 0, 0))  # Red
            icon_item.setToolTip(status_detail)

            # Update status (column 4)
            status_item = self.source_table.item(row, 4)
            status_item.setText(status_text)
            status_item.setToolTip(status_detail)
            if not is_available:
                status_item.setForeground(QColor(200, 0, 0))  # Red text
            else:
                status_item.setForeground(QColor(0, 0, 0))  # Black text

    def load_sources_from_database(self):
        """Load source directories from the database."""
        if not self.db_metadata:
            return

        # Clear existing table
        self.source_table.setRowCount(0)

        # Load from database
        sources = self.db_metadata.get_all_source_directories()

        for source in sources:
            self._add_source_to_table(
                path=source['path'],
                enabled=source['enabled'],
                last_scanned=source['last_scanned']
            )

    def set_database(self, db_metadata: DatabaseMetadata):
        """
        Set the database metadata reference and load sources and ignored directories.

        Args:
            db_metadata: DatabaseMetadata instance
        """
        self.db_metadata = db_metadata
        self.load_sources_from_database()
        self.load_ignored_dirs_from_database()

    def browse_destination(self):
        """Show informative dialog - destination is managed by database."""
        current_dest = self.dest_edit.text()

        msg_box = QMessageBox(
            QMessageBox.Information,
            "Destination Managed by Database",
            f"The destination folder (archive location) is controlled by the database.\n\n"
            f"Current archive: {current_dest if current_dest else 'Not set'}\n\n"
            f"To change the archive location:\n"
            f"1. Go to the 'Database' tab\n"
            f"2. Use 'Change Archive Location' (coming soon)\n\n"
            f"This ensures your photo archive stays connected to the correct database.",
            QMessageBox.Ok,
            self
        )
        self._center_dialog(msg_box)
        msg_box.exec()

    def set_destination_folder(self, folder):
        """
        Set the destination folder (called by main window when database loads).

        Args:
            folder: Destination folder path
        """
        self.dest_edit.setText(folder)

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
            # Check if checkbox is checked
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    is_checked = checkbox.isChecked()
                    path_item = self.source_table.item(row, 2)
                    if path_item:
                        path = path_item.text()
                        # Debug logging
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.info(f"Source folder: {path}, Enabled: {is_checked}")
                        if is_checked:
                            enabled_folders.append(path)
                else:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Could not find checkbox for row {row}")

        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Total enabled folders: {len(enabled_folders)} out of {self.source_table.rowCount()}")
        return enabled_folders

    def get_destination_folder(self):
        """Get destination folder."""
        return self.dest_edit.text().strip()

    def is_copy_mode(self):
        """Check if copy mode is selected."""
        return self.copy_radio.isChecked()

    def is_move_mode(self):
        """Check if move mode is selected."""
        return self.move_radio.isChecked()

    def set_controls_enabled(self, enabled):
        """Enable or disable controls during processing."""
        self.add_source_btn.setEnabled(enabled)
        self.remove_source_btn.setEnabled(enabled)
        self.clear_all_btn.setEnabled(enabled)
        # Note: browse_dest_btn always stays enabled (active UI principle)
        # It shows an informative dialog instead
        self.copy_radio.setEnabled(enabled)
        self.move_radio.setEnabled(enabled)
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)

    def _center_dialog(self, dialog):
        """Center a dialog on the main application window."""
        parent = self.parent()
        if parent:
            # Get the top-level window
            main_window = parent.window()
            if main_window:
                # Force dialog to process geometry
                dialog.adjustSize()

                # Get geometries
                parent_geo = main_window.frameGeometry()
                dialog_geo = dialog.frameGeometry()

                # Calculate center position
                x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
                y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2

                # Move dialog to center
                dialog.move(x, y)

    def on_item_clicked(self, item):
        """Handle click on table item - support Shift/Ctrl selection on checkbox column."""
        if item is None:
            return

        row = item.row()
        column = item.column()

        # Only handle clicks on checkbox column (column 0)
        if column != 0:
            # For non-checkbox columns, just update last clicked row for future shift-clicks
            self.last_clicked_row = row
            return

        # Get the checkbox widget
        checkbox_widget = self.source_table.cellWidget(row, 0)
        if not checkbox_widget:
            return

        checkbox = checkbox_widget.findChild(QCheckBox)
        if not checkbox:
            return

        # Get keyboard modifiers
        from PySide6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()

        # Handle Shift-click: select range and check all checkboxes in range
        if modifiers & Qt.ShiftModifier and self.last_clicked_row >= 0:
            start_row = min(self.last_clicked_row, row)
            end_row = max(self.last_clicked_row, row)

            # Determine the target state based on the clicked checkbox
            target_state = checkbox.isChecked()

            # Block signals temporarily to avoid triggering state changes
            self.source_table.blockSignals(True)

            # Select all rows in range and set their checkboxes
            for r in range(start_row, end_row + 1):
                # Select the row
                self.source_table.selectRow(r)

                # Set checkbox state
                cb_widget = self.source_table.cellWidget(r, 0)
                if cb_widget:
                    cb = cb_widget.findChild(QCheckBox)
                    if cb:
                        cb.setChecked(target_state)

            self.source_table.blockSignals(False)

        # Handle Ctrl-click: toggle row selection and checkbox
        elif modifiers & Qt.ControlModifier:
            # The row selection is already handled by ExtendedSelection mode
            # Just update last_clicked_row
            self.last_clicked_row = row

        # Handle normal click: select single row
        else:
            # Qt already handles the checkbox toggle
            self.last_clicked_row = row

    def on_item_double_clicked(self, item):
        """Handle double-click on table item - toggle checkbox."""
        if item is None:
            return

        row = item.row()
        checkbox_widget = self.source_table.cellWidget(row, 0)

        if checkbox_widget:
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                # Toggle checkbox state
                checkbox.setChecked(not checkbox.isChecked())

    def sync_checkboxes_with_selection(self):
        """Sync checkbox states with row selection - checkboxes match selected rows."""
        # Get selected rows
        selected_rows = set(index.row() for index in self.source_table.selectedIndexes())

        # Block signals to avoid recursive calls
        self.source_table.blockSignals(True)

        # Update all checkboxes to match selection
        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    is_selected = row in selected_rows
                    if checkbox.isChecked() != is_selected:
                        checkbox.setChecked(is_selected)

        self.source_table.blockSignals(False)

    # ========== Ignored Directories Methods ==========

    def add_ignored_dir_pattern(self):
        """Add a new ignored directory pattern to the list."""
        pattern = self.add_ignored_dir_input.text().strip()
        if not pattern:
            msg_box = QMessageBox(QMessageBox.Warning, "Empty Pattern",
                                 "Please enter a pattern to add.", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        # Check if already exists
        for i in range(self.ignored_dirs_list.count()):
            if self.ignored_dirs_list.item(i).text().lower() == pattern.lower():
                msg_box = QMessageBox(QMessageBox.Information, "Pattern Exists",
                                     f"Pattern '{pattern}' already exists in the list.", QMessageBox.Ok, self)
                self._center_dialog(msg_box)
                msg_box.exec()
                return

        # Add to list
        self.ignored_dirs_list.addItem(pattern)
        self.add_ignored_dir_input.clear()
        self.update_ignored_dirs_count()

        # Save to database
        self.save_ignored_dirs_to_database()

    def remove_ignored_dir_pattern(self):
        """Remove selected ignored directory pattern from the list."""
        current_item = self.ignored_dirs_list.currentItem()
        if not current_item:
            msg_box = QMessageBox(QMessageBox.Information, "No Selection",
                                 "Please select a pattern to remove.", QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
            return

        # Remove the selected item
        row = self.ignored_dirs_list.row(current_item)
        self.ignored_dirs_list.takeItem(row)
        self.update_ignored_dirs_count()

        # Save to database
        self.save_ignored_dirs_to_database()

    def add_preset_ignored_dirs(self):
        """Add common preset patterns for ignored directories."""
        preset_patterns = [
            "@eaDir",           # Synology NAS thumbnails
            ".git",             # Git version control
            ".svn",             # SVN version control
            "node_modules",     # Node.js packages
            "venv",             # Python virtual environment
            ".venv",            # Python virtual environment (alternate)
            "__pycache__",      # Python cache
            "$RECYCLE.BIN",     # Windows recycle bin
            ".Trash-*",         # Linux trash
            "Thumbs.db",        # Windows thumbnail cache
            ".DS_Store",        # macOS metadata
            "__MACOSX",         # macOS metadata folder
            ".thumbnails",      # Linux thumbnail cache
            "*.tmp",            # Temporary folders
            ".cache",           # Cache folders
        ]

        added_count = 0
        for pattern in preset_patterns:
            # Check if already exists
            exists = False
            for i in range(self.ignored_dirs_list.count()):
                if self.ignored_dirs_list.item(i).text().lower() == pattern.lower():
                    exists = True
                    break

            if not exists:
                self.ignored_dirs_list.addItem(pattern)
                added_count += 1

        self.update_ignored_dirs_count()

        # Save to database
        if added_count > 0:
            self.save_ignored_dirs_to_database()
            msg_box = QMessageBox(QMessageBox.Information, "Presets Added",
                                 f"Added {added_count} preset patterns.\n"
                                 f"Total patterns: {self.ignored_dirs_list.count()}",
                                 QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()
        else:
            msg_box = QMessageBox(QMessageBox.Information, "No New Presets",
                                 "All preset patterns are already in the list.",
                                 QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()

    def update_ignored_dirs_count(self):
        """Update the ignored directories count label."""
        count = self.ignored_dirs_list.count()
        self.ignored_dirs_count_label.setText(f"Total patterns: {count}")

    def save_ignored_dirs_to_database(self):
        """Save ignored directories to database."""
        if self.db_metadata is None:
            return

        # Get all patterns from list
        patterns = []
        for i in range(self.ignored_dirs_list.count()):
            patterns.append(self.ignored_dirs_list.item(i).text())

        # Save to database
        try:
            self.db_metadata.set_ignored_directories(patterns)
            logger.info(f"Saved {len(patterns)} ignored directory patterns to database")
        except Exception as e:
            logger.error(f"Failed to save ignored directories: {e}")
            msg_box = QMessageBox(QMessageBox.Critical, "Error",
                                 f"Failed to save ignored directories to database:\n\n{str(e)}",
                                 QMessageBox.Ok, self)
            self._center_dialog(msg_box)
            msg_box.exec()

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
