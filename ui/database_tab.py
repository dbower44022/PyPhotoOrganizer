"""
Database Tab

Displays database information and allows database management.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QGroupBox, QFormLayout, QLineEdit,
                               QTextEdit, QMessageBox, QFileDialog, QCheckBox)
from PySide6.QtCore import Qt, Signal
from database_metadata import DatabaseMetadata
import os


class DatabaseTab(QWidget):
    """Tab for displaying and managing database information."""

    database_changed = Signal(str)  # Emits new database path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_database_path = None
        self.database_metadata = None
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Header
        header = QLabel("Database Management")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Current Database Group
        db_group = QGroupBox("Current Database")
        db_layout = QFormLayout()

        self.db_name_label = QLabel("No database loaded")
        self.db_name_label.setStyleSheet("font-weight: bold;")
        db_layout.addRow("Database Name:", self.db_name_label)

        self.db_file_label = QLabel("-")
        db_layout.addRow("Database File:", self.db_file_label)

        self.db_created_label = QLabel("-")
        db_layout.addRow("Created:", self.db_created_label)

        self.db_last_used_label = QLabel("-")
        db_layout.addRow("Last Used:", self.db_last_used_label)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # Description Group
        desc_group = QGroupBox("Description")
        desc_layout = QVBoxLayout()

        self.description_display = QTextEdit()
        self.description_display.setReadOnly(True)
        self.description_display.setMaximumHeight(80)
        self.description_display.setPlaceholderText("No description")
        self.description_display.setStyleSheet("background-color: #f5f5f5; padding: 5px;")
        desc_layout.addWidget(self.description_display)

        desc_group.setLayout(desc_layout)
        layout.addWidget(desc_group)

        # Archive Location Group
        archive_group = QGroupBox("Archive Location")
        archive_layout = QVBoxLayout()

        archive_info = QLabel(
            "The archive location is where your organized photos are stored.\n"
            "This location is managed by the database and cannot be changed here."
        )
        archive_info.setWordWrap(True)
        archive_info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        archive_layout.addWidget(archive_info)

        archive_path_layout = QHBoxLayout()
        self.archive_path_edit = QLineEdit()
        self.archive_path_edit.setReadOnly(True)
        self.archive_path_edit.setPlaceholderText("No archive location set")
        self.archive_path_edit.setStyleSheet("background-color: #f5f5f5;")
        archive_path_layout.addWidget(self.archive_path_edit)

        self.browse_archive_btn = QPushButton("Browse...")
        self.browse_archive_btn.setToolTip("Archive location is managed by the database")
        self.browse_archive_btn.clicked.connect(self.on_browse_archive_clicked)
        archive_path_layout.addWidget(self.browse_archive_btn)

        archive_layout.addLayout(archive_path_layout)

        # Archive status
        self.archive_status_label = QLabel("")
        self.archive_status_label.setWordWrap(True)
        self.archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")
        archive_layout.addWidget(self.archive_status_label)

        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)

        # Video Archive Location Group
        video_archive_group = QGroupBox("Video Archive Location (Optional)")
        video_archive_layout = QVBoxLayout()

        # Enable/disable checkbox
        self.separate_video_archive_check = QCheckBox("Store videos in separate location")
        self.separate_video_archive_check.setToolTip(
            "When enabled, video files will be organized to a different location than photos"
        )
        self.separate_video_archive_check.stateChanged.connect(self.on_separate_video_changed)
        video_archive_layout.addWidget(self.separate_video_archive_check)

        video_archive_info = QLabel(
            "Videos can be stored separately from photos. Useful for NAS storage or\n"
            "when you want photos and videos in different locations."
        )
        video_archive_info.setWordWrap(True)
        video_archive_info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        video_archive_layout.addWidget(video_archive_info)

        video_archive_path_layout = QHBoxLayout()
        self.video_archive_path_edit = QLineEdit()
        self.video_archive_path_edit.setReadOnly(True)
        self.video_archive_path_edit.setPlaceholderText("No video archive location set")
        self.video_archive_path_edit.setStyleSheet("background-color: #f5f5f5;")
        video_archive_path_layout.addWidget(self.video_archive_path_edit)

        self.browse_video_archive_btn = QPushButton("Browse...")
        self.browse_video_archive_btn.setEnabled(False)
        self.browse_video_archive_btn.clicked.connect(self.on_browse_video_archive_clicked)
        video_archive_path_layout.addWidget(self.browse_video_archive_btn)

        self.set_video_archive_btn = QPushButton("Set")
        self.set_video_archive_btn.setEnabled(False)
        self.set_video_archive_btn.setToolTip("Apply the selected video archive location")
        self.set_video_archive_btn.clicked.connect(self.on_set_video_archive_clicked)
        video_archive_path_layout.addWidget(self.set_video_archive_btn)

        video_archive_layout.addLayout(video_archive_path_layout)

        # Video archive status
        self.video_archive_status_label = QLabel("")
        self.video_archive_status_label.setWordWrap(True)
        self.video_archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")
        video_archive_layout.addWidget(self.video_archive_status_label)

        video_archive_group.setLayout(video_archive_layout)
        layout.addWidget(video_archive_group)

        # Statistics Group
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout()

        self.total_photos_label = QLabel("0")
        self.total_photos_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        stats_layout.addRow("Total Photos:", self.total_photos_label)

        self.schema_version_label = QLabel("-")
        stats_layout.addRow("Schema Version:", self.schema_version_label)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Management Buttons
        button_layout = QHBoxLayout()

        self.change_archive_btn = QPushButton("Change Archive Location")
        self.change_archive_btn.setMinimumHeight(35)
        self.change_archive_btn.setToolTip("Change where organized photos are stored (Coming Soon)")
        self.change_archive_btn.clicked.connect(self.on_change_archive_clicked)
        button_layout.addWidget(self.change_archive_btn)

        self.change_database_btn = QPushButton("Select Different Database")
        self.change_database_btn.setMinimumHeight(35)
        self.change_database_btn.clicked.connect(self.on_change_database_clicked)
        button_layout.addWidget(self.change_database_btn)

        self.refresh_btn = QPushButton("Refresh Statistics")
        self.refresh_btn.setMinimumHeight(35)
        self.refresh_btn.clicked.connect(self.refresh_database_info)
        button_layout.addWidget(self.refresh_btn)

        layout.addLayout(button_layout)

        # Spacer
        layout.addStretch()

        self.setLayout(layout)

    def set_database(self, database_path):
        """
        Set the current database and load its information.

        Args:
            database_path: Path to the database file
        """
        if not os.path.exists(database_path):
            QMessageBox.warning(
                self,
                "Database Not Found",
                f"The database file does not exist:\n\n{database_path}"
            )
            return

        self.current_database_path = database_path
        self.database_metadata = DatabaseMetadata(database_path)
        self.refresh_database_info()

    def refresh_database_info(self):
        """Refresh the database information display."""
        if not self.current_database_path or not self.database_metadata:
            self.clear_display()
            return

        # Refresh the total photos count from UniquePhotos table
        self.database_metadata.refresh_total_photos()

        metadata = self.database_metadata.get_metadata()

        if not metadata:
            QMessageBox.warning(
                self,
                "Metadata Not Found",
                "Could not load metadata for this database.\n"
                "This may be an older database format."
            )
            self.clear_display()
            return

        # Update database info
        self.db_name_label.setText(metadata.get('database_name', 'Unknown'))
        self.db_file_label.setText(os.path.basename(self.current_database_path))

        created_date = metadata.get('created_date', 'Unknown')
        if created_date and created_date != 'Unknown':
            self.db_created_label.setText(created_date[:10])  # Just the date part
        else:
            self.db_created_label.setText('Unknown')

        last_used = metadata.get('last_used_date', 'Never')
        if last_used and last_used != 'Never':
            self.db_last_used_label.setText(last_used[:10])
        else:
            self.db_last_used_label.setText('Never')

        # Update description
        description = metadata.get('description', '')
        if description:
            self.description_display.setPlainText(description)
        else:
            self.description_display.setPlainText("No description provided")

        # Update archive location
        archive_location = metadata.get('archive_location', '')
        self.archive_path_edit.setText(archive_location)

        # Check if archive exists
        if archive_location and os.path.exists(archive_location):
            self.archive_status_label.setText("✓ Archive folder exists")
            self.archive_status_label.setStyleSheet("font-size: 10px; color: green; margin-top: 5px;")
        elif archive_location:
            self.archive_status_label.setText("⚠ Warning: Archive folder does not exist!")
            self.archive_status_label.setStyleSheet("font-size: 10px; color: red; margin-top: 5px;")
        else:
            self.archive_status_label.setText("No archive location set")
            self.archive_status_label.setStyleSheet("font-size: 10px; color: orange; margin-top: 5px;")

        # Update statistics
        total_photos = metadata.get('total_photos', 0)
        self.total_photos_label.setText(f"{total_photos:,}")

        schema_version = metadata.get('schema_version', 1)
        self.schema_version_label.setText(str(schema_version))

        # Update video archive information
        video_archive_location = metadata.get('video_archive_location', '')
        separate_video_archive = metadata.get('separate_video_archive', False)

        self.separate_video_archive_check.setChecked(separate_video_archive)
        self.video_archive_path_edit.setText(video_archive_location if video_archive_location else "")

        # Update video archive status
        if separate_video_archive and video_archive_location:
            if os.path.exists(video_archive_location):
                self.video_archive_status_label.setText("✓ Video archive folder exists")
                self.video_archive_status_label.setStyleSheet("font-size: 10px; color: green; margin-top: 5px;")
            else:
                self.video_archive_status_label.setText("⚠ Warning: Video archive folder does not exist!")
                self.video_archive_status_label.setStyleSheet("font-size: 10px; color: red; margin-top: 5px;")
        elif separate_video_archive:
            self.video_archive_status_label.setText("⚠ Separate video archive enabled but no location set")
            self.video_archive_status_label.setStyleSheet("font-size: 10px; color: orange; margin-top: 5px;")
        else:
            self.video_archive_status_label.setText("Videos will be stored in the same location as photos")
            self.video_archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")

        # Update last used timestamp
        self.database_metadata.update_last_used()

    def clear_display(self):
        """Clear all displayed information."""
        self.db_name_label.setText("No database loaded")
        self.db_file_label.setText("-")
        self.db_created_label.setText("-")
        self.db_last_used_label.setText("-")
        self.description_display.clear()
        self.archive_path_edit.clear()
        self.archive_status_label.clear()
        self.video_archive_path_edit.clear()
        self.video_archive_status_label.clear()
        self.separate_video_archive_check.setChecked(False)
        self.total_photos_label.setText("0")
        self.schema_version_label.setText("-")

    def on_browse_archive_clicked(self):
        """Handle browse button click - show informative dialog."""
        archive_location = self.archive_path_edit.text()

        QMessageBox.information(
            self,
            "Archive Location Managed by Database",
            f"The destination folder is controlled by the database you selected.\n\n"
            f"Current archive: {archive_location if archive_location else 'Not set'}\n"
            f"Database: {self.db_name_label.text()}\n\n"
            f"To change the archive location, use:\n"
            f"'Change Archive Location' button below.\n\n"
            f"This ensures your photo archive stays connected to the correct database."
        )

    def on_change_archive_clicked(self):
        """Handle change archive location button click."""
        QMessageBox.information(
            self,
            "Feature Coming Soon",
            "Archive location migration will be available in a future update.\n\n"
            "This feature will allow you to:\n"
            "• Move your photo archive to a new location\n"
            "• Update the database to reference the new location\n"
            "• Verify all photos have been moved correctly\n\n"
            "For now, the archive location is set when you create the database."
        )

    def on_change_database_clicked(self):
        """Handle change database button click."""
        from ui.database_selector_dialog import DatabaseSelectorDialog

        dialog = DatabaseSelectorDialog(self)
        if dialog.exec():
            new_db_path = dialog.get_selected_database()
            if new_db_path:
                self.set_database(new_db_path)
                self.database_changed.emit(new_db_path)

    def get_current_database_path(self):
        """Get the current database path."""
        return self.current_database_path

    def get_archive_location(self):
        """Get the archive location for the current database."""
        if self.database_metadata:
            return self.database_metadata.get_archive_location()
        return None

    def on_separate_video_changed(self, state):
        """Handle separate video archive checkbox state change."""
        enabled = (state == Qt.CheckState.Checked.value)
        self.browse_video_archive_btn.setEnabled(enabled)

        if not enabled:
            # Disable separate video archive in database
            if self.database_metadata:
                try:
                    self.database_metadata.set_video_archive("", enabled=False)
                    self.refresh_database_info()
                    QMessageBox.information(
                        self,
                        "Video Archive Disabled",
                        "Videos will now be stored in the same location as photos."
                    )
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Error",
                        f"Failed to disable video archive:\n\n{str(e)}"
                    )
                    # Revert checkbox
                    self.separate_video_archive_check.setChecked(True)

    def on_browse_video_archive_clicked(self):
        """Handle browse video archive button click."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Video Archive Location",
            os.path.expanduser("~")
        )

        if folder:
            self.video_archive_path_edit.setText(folder)
            self.set_video_archive_btn.setEnabled(True)

    def on_set_video_archive_clicked(self):
        """Handle set video archive button click."""
        video_archive_location = self.video_archive_path_edit.text().strip()

        if not video_archive_location:
            QMessageBox.warning(
                self,
                "No Location Selected",
                "Please select a video archive location first."
            )
            return

        # Validate path is absolute
        if not os.path.isabs(video_archive_location):
            QMessageBox.warning(
                self,
                "Invalid Path",
                f"Video archive location must be an absolute path.\n\n"
                f"Current path: {video_archive_location}"
            )
            return

        # Check if folder exists, offer to create
        if not os.path.exists(video_archive_location):
            response = QMessageBox.question(
                self,
                "Create Video Archive Folder?",
                f"The video archive folder does not exist:\n\n{video_archive_location}\n\n"
                f"Would you like to create it now?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if response == QMessageBox.Yes:
                try:
                    os.makedirs(video_archive_location, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Failed to Create Folder",
                        f"Could not create video archive folder:\n\n{str(e)}"
                    )
                    return
            else:
                return

        # Set video archive in database
        try:
            self.database_metadata.set_video_archive(video_archive_location, enabled=True)
            self.refresh_database_info()
            self.set_video_archive_btn.setEnabled(False)

            QMessageBox.information(
                self,
                "Video Archive Set",
                f"Video archive location has been set:\n\n{video_archive_location}\n\n"
                f"Videos will now be organized to this location."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to set video archive location:\n\n{str(e)}"
            )
