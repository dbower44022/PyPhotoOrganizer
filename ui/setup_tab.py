"""
Setup Tab for PyPhotoOrganizer GUI

Allows users to configure source/destination folders and operation mode.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QListWidget, QPushButton, QLineEdit, QRadioButton,
                               QButtonGroup, QLabel, QFileDialog, QMessageBox)
from PySide6.QtCore import Signal
import os


class SetupTab(QWidget):
    """Tab for configuring folders and operation mode."""

    start_clicked = Signal()
    stop_clicked = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Source folders group
        source_group = QGroupBox("Source Folders")
        source_layout = QVBoxLayout()

        self.source_list = QListWidget()
        self.source_list.setMinimumHeight(150)
        source_layout.addWidget(self.source_list)

        source_buttons = QHBoxLayout()
        self.add_source_btn = QPushButton("Add Folder...")
        self.add_source_btn.clicked.connect(self.add_source_folder)
        self.remove_source_btn = QPushButton("Remove Selected")
        self.remove_source_btn.clicked.connect(self.remove_source_folder)
        source_buttons.addWidget(self.add_source_btn)
        source_buttons.addWidget(self.remove_source_btn)
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
            # Check if already in list
            items = [self.source_list.item(i).text() for i in range(self.source_list.count())]
            if folder not in items:
                self.source_list.addItem(folder)
            else:
                QMessageBox.information(self, "Folder Already Added",
                                       "This folder is already in the source list.")

    def remove_source_folder(self):
        """Remove selected source folder."""
        current_row = self.source_list.currentRow()
        if current_row >= 0:
            self.source_list.takeItem(current_row)

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
        """Get list of source folders."""
        return [self.source_list.item(i).text() for i in range(self.source_list.count())]

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
        # Note: browse_dest_btn always stays enabled (active UI principle)
        # It shows an informative dialog instead
        self.copy_radio.setEnabled(enabled)
        self.move_radio.setEnabled(enabled)
        self.start_btn.setEnabled(enabled)
        self.stop_btn.setEnabled(not enabled)
