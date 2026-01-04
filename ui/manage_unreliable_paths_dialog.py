"""
Manage Unreliable Paths Dialog

Dialog for managing user-specified paths that should be
automatically flagged as having unreliable dates.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QFileDialog,
                               QMessageBox)
from PySide6.QtCore import Qt
import logging

logger = logging.getLogger(__name__)


class ManageUnreliablePathsDialog(QDialog):
    """Dialog for managing user-specified unreliable paths."""

    def __init__(self, parent, db_metadata):
        """
        Initialize dialog.

        Args:
            parent: Parent widget
            db_metadata: DatabaseMetadata instance
        """
        super().__init__(parent)
        self.db_metadata = db_metadata
        self.init_ui()
        self.load_paths()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Manage Unreliable Paths")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        layout = QVBoxLayout()

        # Header
        header = QLabel("Manage Unreliable Paths")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Description
        desc = QLabel(
            "Files from these paths will be automatically flagged as having unreliable dates.\n"
            "This is useful for folders containing scanned photos, imported archives, or\n"
            "files with known incorrect date information."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("padding: 5px; color: #666; margin-bottom: 10px;")
        layout.addWidget(desc)

        # List widget
        self.path_list = QListWidget()
        self.path_list.setAlternatingRowColors(True)
        layout.addWidget(self.path_list)

        # Buttons for list management
        list_button_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Path...")
        self.add_btn.clicked.connect(self.add_path)
        list_button_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self.remove_path)
        list_button_layout.addWidget(self.remove_btn)

        list_button_layout.addStretch()
        layout.addLayout(list_button_layout)

        # Dialog buttons
        button_layout = QHBoxLayout()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.close_btn)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self.save_changes)
        button_layout.addWidget(self.save_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Center on parent
        if self.parent():
            parent_geometry = self.parent().frameGeometry()
            dialog_geometry = self.frameGeometry()
            center_point = parent_geometry.center()
            dialog_geometry.moveCenter(center_point)
            self.move(dialog_geometry.topLeft())

    def load_paths(self):
        """Load paths from database and populate list."""
        try:
            paths = self.db_metadata.get_user_specified_paths()
            self.path_list.clear()

            for path in paths:
                self.path_list.addItem(path)

        except Exception as e:
            logger.error(f"Failed to load unreliable paths: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to load paths from database:\n\n{str(e)}"
            )

    def add_path(self):
        """Add a new path to the list."""
        # Open folder selection dialog
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Folder with Unreliable Dates",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if folder:
            # Check if path already exists
            existing_paths = [self.path_list.item(i).text()
                            for i in range(self.path_list.count())]

            if folder in existing_paths:
                QMessageBox.information(
                    self,
                    "Path Already Exists",
                    f"The path:\n\n{folder}\n\nis already in the list."
                )
                return

            # Add to list
            self.path_list.addItem(folder)
            logger.info(f"Added unreliable path: {folder}")

    def remove_path(self):
        """Remove selected path from list."""
        current_row = self.path_list.currentRow()

        if current_row < 0:
            QMessageBox.information(
                self,
                "No Selection",
                "Please select a path to remove."
            )
            return

        # Get selected path
        path = self.path_list.item(current_row).text()

        # Confirm removal
        response = QMessageBox.question(
            self,
            "Confirm Removal",
            f"Remove this path from unreliable paths?\n\n{path}\n\n"
            f"Note: This will not affect files already flagged.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if response == QMessageBox.Yes:
            self.path_list.takeItem(current_row)
            logger.info(f"Removed unreliable path: {path}")

    def save_changes(self):
        """Save changes to database."""
        try:
            # Get all paths from list
            paths = [self.path_list.item(i).text()
                    for i in range(self.path_list.count())]

            # Save to database
            success = self.db_metadata.set_user_specified_paths(paths)

            if success:
                QMessageBox.information(
                    self,
                    "Saved",
                    f"Successfully saved {len(paths)} unreliable path(s).\n\n"
                    f"Files from these paths will be automatically flagged\n"
                    f"during future processing runs."
                )
                self.accept()
            else:
                QMessageBox.critical(
                    self,
                    "Save Failed",
                    "Failed to save paths to database.\n\n"
                    "Check logs for details."
                )

        except Exception as e:
            logger.error(f"Failed to save unreliable paths: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save paths:\n\n{str(e)}"
            )
