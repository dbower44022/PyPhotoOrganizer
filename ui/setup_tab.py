"""
Setup Tab for PyPhotoOrganizer GUI

Allows users to configure source/destination folders and operation mode.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QRadioButton,
                               QButtonGroup, QLabel, QFileDialog, QMessageBox, QHeaderView,
                               QAbstractItemView, QCheckBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QIcon, QColor
import os
from datetime import datetime
from database_metadata import DatabaseMetadata


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
        self.source_table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.source_table.verticalHeader().setVisible(False)

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
                QMessageBox.information(self, "Folder Already Added",
                                       "This folder is already in the source list.")
                return

            # Add to database if available
            if self.db_metadata:
                success = self.db_metadata.add_source_directory(folder, enabled=True)
                if not success:
                    QMessageBox.warning(self, "Failed to Add",
                                       "Could not add folder to database.")
                    return

            # Add to table
            self._add_source_to_table(folder, enabled=True, last_scanned=None)

    def remove_source_folder(self):
        """Remove selected source folder."""
        current_row = self.source_table.currentRow()
        if current_row >= 0:
            # Get the path from the selected row
            path = self.source_table.item(current_row, 2).text()

            # Remove from database if available
            if self.db_metadata:
                self.db_metadata.remove_source_directory(path)

            # Remove from table
            self.source_table.removeRow(current_row)

    def clear_all_sources(self):
        """Clear all source folders."""
        if self.source_table.rowCount() == 0:
            QMessageBox.information(
                self,
                "No Folders",
                "The source folder list is already empty."
            )
            return

        response = QMessageBox.question(
            self,
            "Clear All Source Folders?",
            f"Remove all {self.source_table.rowCount()} source folder(s) from the list?\n\n"
            f"This will not delete any files, only clear the list.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

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
        self.source_table.setItem(row_position, 1, icon_item)

        # Column 2: Path
        path_item = QTableWidgetItem(path)
        path_item.setToolTip(status_detail)
        self.source_table.setItem(row_position, 2, path_item)

        # Column 3: Last Scanned
        if last_scanned:
            try:
                # Parse ISO format and display user-friendly
                dt = datetime.fromisoformat(last_scanned)
                scanned_text = dt.strftime("%Y-%m-%d %H:%M")
            except:
                scanned_text = "Unknown"
        else:
            scanned_text = "Never"
        scanned_item = QTableWidgetItem(scanned_text)
        scanned_item.setToolTip(f"Last scanned: {scanned_text}")
        self.source_table.setItem(row_position, 3, scanned_item)

        # Column 4: Status
        status_item = QTableWidgetItem(status_text)
        status_item.setToolTip(status_detail)
        if not is_available:
            status_item.setForeground(QColor(200, 0, 0))  # Red text
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
        Set the database metadata reference and load sources.

        Args:
            db_metadata: DatabaseMetadata instance
        """
        self.db_metadata = db_metadata
        self.load_sources_from_database()

    def browse_destination(self):
        """Show informative dialog - destination is managed by database."""
        current_dest = self.dest_edit.text()

        QMessageBox.information(
            self,
            "Destination Managed by Database",
            f"The destination folder (archive location) is controlled by the database.\n\n"
            f"Current archive: {current_dest if current_dest else 'Not set'}\n\n"
            f"To change the archive location:\n"
            f"1. Go to the 'Database' tab\n"
            f"2. Use 'Change Archive Location' (coming soon)\n\n"
            f"This ensures your photo archive stays connected to the correct database."
        )

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
                if checkbox and checkbox.isChecked():
                    path_item = self.source_table.item(row, 2)
                    if path_item:
                        enabled_folders.append(path_item.text())
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
