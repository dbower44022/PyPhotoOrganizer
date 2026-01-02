"""
Create Database Dialog

Wizard for creating a new photo archive database.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QLineEdit, QTextEdit, QFileDialog,
                               QMessageBox, QGroupBox, QFormLayout)
from PySide6.QtCore import Qt
from database_metadata import DatabaseMetadata
import os
from pathlib import Path


class CreateDatabaseDialog(QDialog):
    """Dialog for creating a new database."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.created_database_path = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Create New Database")
        self.setMinimumSize(600, 500)
        self.setModal(True)

        layout = QVBoxLayout()

        # Header
        header = QLabel("Create New Photo Archive Database")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        info = QLabel(
            "Set up a new photo archive by providing a name and selecting "
            "where your organized photos will be stored."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding: 5px; color: #666; margin-bottom: 10px;")
        layout.addWidget(info)

        # Database Info Group
        db_group = QGroupBox("Database Information")
        db_layout = QFormLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Family Photos 2020-2024")
        self.name_edit.textChanged.connect(self.update_database_filename)
        db_layout.addRow("Database Name:", self.name_edit)

        self.description_edit = QTextEdit()
        self.description_edit.setPlaceholderText(
            "Optional: Describe what photos this archive contains..."
        )
        self.description_edit.setMaximumHeight(80)
        db_layout.addRow("Description:", self.description_edit)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # Archive Location Group
        archive_group = QGroupBox("Archive Location")
        archive_layout = QVBoxLayout()

        archive_info = QLabel(
            "This is where your organized photos will be stored.\n"
            "Once created, this location will be linked to this database."
        )
        archive_info.setWordWrap(True)
        archive_info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        archive_layout.addWidget(archive_info)

        archive_select_layout = QHBoxLayout()
        self.archive_edit = QLineEdit()
        self.archive_edit.setPlaceholderText("Select archive location...")
        self.archive_edit.setReadOnly(True)
        archive_select_layout.addWidget(self.archive_edit)

        self.browse_archive_btn = QPushButton("Browse...")
        self.browse_archive_btn.clicked.connect(self.browse_archive_location)
        archive_select_layout.addWidget(self.browse_archive_btn)

        archive_layout.addLayout(archive_select_layout)
        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)

        # Database File Location Group
        file_group = QGroupBox("Database File Location")
        file_layout = QVBoxLayout()

        file_info = QLabel(
            "The database file (.db) will be saved in the application directory.\n"
            "Filename is automatically generated from the database name."
        )
        file_info.setWordWrap(True)
        file_info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        file_layout.addWidget(file_info)

        self.filename_label = QLabel("PhotoDB.db")
        self.filename_label.setStyleSheet(
            "background-color: #f5f5f5; padding: 8px; border: 1px solid #ddd;"
        )
        file_layout.addWidget(self.filename_label)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Spacer
        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()

        self.create_button = QPushButton("Create Database")
        self.create_button.setMinimumHeight(35)
        self.create_button.setStyleSheet("font-weight: bold;")
        self.create_button.clicked.connect(self.create_database)
        button_layout.addWidget(self.create_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(35)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def update_database_filename(self):
        """Update the database filename based on the name."""
        name = self.name_edit.text().strip()
        if name:
            # Create safe filename from name
            safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_'))
            safe_name = safe_name.replace(' ', '_')
            filename = f"PhotoDB_{safe_name}.db"
            self.filename_label.setText(filename)
        else:
            self.filename_label.setText("PhotoDB.db")

    def browse_archive_location(self):
        """Browse for archive (destination) location."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Archive Location (Where organized photos will be stored)",
            os.path.expanduser("~")
        )

        if folder:
            self.archive_edit.setText(folder)

    def validate_inputs(self):
        """Validate user inputs."""
        name = self.name_edit.text().strip()
        archive = self.archive_edit.text().strip()

        if not name:
            QMessageBox.warning(
                self,
                "Missing Information",
                "Please provide a name for this database.\n\n"
                "Example: 'Family Photos 2020-2024'"
            )
            self.name_edit.setFocus()
            return False

        if not archive:
            QMessageBox.warning(
                self,
                "Missing Archive Location",
                "Please select where your organized photos will be stored.\n\n"
                "Click the 'Browse...' button to select a folder."
            )
            return False

        if not os.path.isabs(archive):
            QMessageBox.warning(
                self,
                "Invalid Path",
                "Archive location must be an absolute path.\n\n"
                f"Current path: {archive}"
            )
            return False

        # Check if archive location exists, offer to create it
        if not os.path.exists(archive):
            response = QMessageBox.question(
                self,
                "Create Archive Folder?",
                f"The archive folder does not exist:\n\n{archive}\n\n"
                f"Would you like to create it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if response == QMessageBox.Yes:
                try:
                    os.makedirs(archive, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Failed to Create Folder",
                        f"Could not create archive folder:\n\n{str(e)}"
                    )
                    return False
            else:
                return False

        # Check if database file already exists
        db_filename = self.filename_label.text()
        db_path = os.path.join(os.getcwd(), db_filename)

        if os.path.exists(db_path):
            QMessageBox.warning(
                self,
                "Database Already Exists",
                f"A database with this name already exists:\n\n{db_path}\n\n"
                f"Please choose a different name."
            )
            self.name_edit.setFocus()
            return False

        return True

    def create_database(self):
        """Create the new database."""
        if not self.validate_inputs():
            return

        name = self.name_edit.text().strip()
        description = self.description_edit.toPlainText().strip()
        archive = self.archive_edit.text().strip()
        db_filename = self.filename_label.text()
        db_path = os.path.join(os.getcwd(), db_filename)

        try:
            # Create the database
            success = DatabaseMetadata.create_database(
                database_path=db_path,
                database_name=name,
                archive_location=archive,
                description=description
            )

            if success:
                self.created_database_path = db_path

                QMessageBox.information(
                    self,
                    "Database Created",
                    f"Successfully created new database:\n\n"
                    f"Name: {name}\n"
                    f"Archive: {archive}\n"
                    f"Database: {db_filename}\n\n"
                    f"You can now start organizing your photos!"
                )
                self.accept()
            else:
                QMessageBox.critical(
                    self,
                    "Creation Failed",
                    "Failed to create database. Please try again."
                )

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"An error occurred while creating the database:\n\n{str(e)}"
            )
