"""
Database Selector Dialog

Allows users to select an existing database or create a new one.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QListWidgetItem,
                               QMessageBox, QTextEdit, QApplication, QFileDialog)
from PySide6.QtCore import Qt, Signal
from database_metadata import DatabaseMetadata
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


class DatabaseSelectorDialog(QDialog):
    """Dialog for selecting or creating a database."""

    database_selected = Signal(str)  # Emits database path

    @staticmethod
    def _get_last_activity_date(db_path: str) -> str:
        """
        Get the last activity date from the ImportSession table.

        Args:
            db_path: Path to the database file

        Returns:
            Last activity date string or 'Never' if no sessions
        """
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()

            # Check if ImportSession table exists
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='ImportSession'
            """)
            if not cursor.fetchone():
                conn.close()
                return 'Never'

            # Get the most recent session end_timestamp or start_timestamp
            cursor.execute("""
                SELECT MAX(COALESCE(end_timestamp, start_timestamp))
                FROM ImportSession
            """)
            result = cursor.fetchone()
            conn.close()

            if result and result[0]:
                # Return date portion only (first 10 chars: YYYY-MM-DD)
                return result[0][:10]
            return 'Never'

        except Exception as e:
            logger.debug(f"Could not get last activity for {db_path}: {e}")
            return 'Unknown'

    def __init__(self, parent=None, search_paths=None):
        """
        Initialize database selector dialog.

        Args:
            parent: Parent widget
            search_paths: List of directories to search for databases.
                         If None, searches current directory only.
        """
        super().__init__(parent)
        self.selected_database = None
        self.search_paths = search_paths if search_paths else ["."]
        self.init_ui()
        self.load_databases()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Select Database")
        self.setMinimumSize(700, 500)
        self.setModal(True)

        layout = QVBoxLayout()

        # Header
        header = QLabel("Select a Photo Archive Database")
        header.setStyleSheet("font-size: 16px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        info = QLabel(
            "Each database is linked to a specific photo archive location.\n"
            "Select an existing database or create a new one to get started."
        )
        info.setWordWrap(True)
        info.setStyleSheet("padding: 5px; color: #666;")
        layout.addWidget(info)

        # Database list
        self.database_list = QListWidget()
        self.database_list.setAlternatingRowColors(True)
        self.database_list.itemDoubleClicked.connect(self.on_database_double_clicked)
        self.database_list.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.database_list)

        # Database info panel
        info_label = QLabel("Database Information:")
        info_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(info_label)

        self.info_panel = QTextEdit()
        self.info_panel.setReadOnly(True)
        self.info_panel.setMaximumHeight(100)
        self.info_panel.setStyleSheet("background-color: #f5f5f5; padding: 5px;")
        layout.addWidget(self.info_panel)

        # Buttons
        button_layout = QHBoxLayout()

        self.open_button = QPushButton("Open Selected")
        self.open_button.setMinimumHeight(35)
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.on_open_clicked)
        button_layout.addWidget(self.open_button)

        self.browse_button = QPushButton("Browse...")
        self.browse_button.setMinimumHeight(35)
        self.browse_button.setToolTip("Browse for a database file")
        self.browse_button.clicked.connect(self.on_browse_clicked)
        button_layout.addWidget(self.browse_button)

        self.create_button = QPushButton("Create New Database")
        self.create_button.setMinimumHeight(35)
        self.create_button.clicked.connect(self.on_create_clicked)
        button_layout.addWidget(self.create_button)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setMinimumHeight(35)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Center dialog on parent or screen
        self.center_on_parent()

    def center_on_parent(self):
        """Center the dialog on its parent window or screen."""
        if self.parent():
            # Center on parent window
            parent_geometry = self.parent().frameGeometry()
            dialog_geometry = self.frameGeometry()
            center_point = parent_geometry.center()
            dialog_geometry.moveCenter(center_point)
            self.move(dialog_geometry.topLeft())
        else:
            # Center on screen if no parent
            screen = QApplication.primaryScreen()
            if screen:
                screen_geometry = screen.availableGeometry()
                dialog_geometry = self.frameGeometry()
                center_point = screen_geometry.center()
                dialog_geometry.moveCenter(center_point)
                self.move(dialog_geometry.topLeft())

    def load_databases(self):
        """Load and display available databases."""
        self.database_list.clear()

        # Search all configured paths for databases
        all_databases = []
        seen_paths = set()  # Avoid duplicates

        for search_path in self.search_paths:
            databases = DatabaseMetadata.find_databases(search_path)
            for db in databases:
                # Avoid duplicates (same database in multiple search paths)
                db_path = db.get('path')
                if db_path and db_path not in seen_paths:
                    all_databases.append(db)
                    seen_paths.add(db_path)

        # Sort databases by name (case-insensitive)
        all_databases.sort(key=lambda db: db.get('database_name', '').lower())
        self.databases = all_databases

        if not self.databases:
            item = QListWidgetItem("No databases found. Click 'Create New Database' to get started.")
            item.setFlags(Qt.ItemIsEnabled)  # Not selectable
            item.setForeground(Qt.gray)
            self.database_list.addItem(item)
            self.info_panel.setPlainText("No databases available.")
            return

        for db in self.databases:
            name = db.get('database_name', 'Unnamed Database')
            archive = db.get('archive_location', 'Unknown')
            photos = db.get('total_photos', 0)

            # Get last activity date from ImportSession table
            db_path = db.get('path', '')
            last_activity = self._get_last_activity_date(db_path)
            db['last_activity'] = last_activity  # Store for info panel

            item_text = f"{name}\n  Archive: {archive}\n  Photos: {photos:,}  |  Last Activity: {last_activity}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, db)  # Store database info
            self.database_list.addItem(item)

    def on_selection_changed(self):
        """Handle database selection change."""
        items = self.database_list.selectedItems()
        if items:
            item = items[0]
            db_info = item.data(Qt.UserRole)

            if db_info:
                self.open_button.setEnabled(True)
                self.display_database_info(db_info)
            else:
                self.open_button.setEnabled(False)
                self.info_panel.clear()
        else:
            self.open_button.setEnabled(False)
            self.info_panel.clear()

    def display_database_info(self, db_info):
        """Display detailed database information."""
        last_activity = db_info.get('last_activity', 'Unknown')
        info_text = f"""
Name: {db_info.get('database_name', 'N/A')}
Description: {db_info.get('description', 'None')}
Archive Location: {db_info.get('archive_location', 'N/A')}
Created: {db_info.get('created_date', 'N/A')[:10]}
Last Activity: {last_activity}
Total Photos: {db_info.get('total_photos', 0):,}
Database File: {db_info.get('filename', 'N/A')}
        """.strip()
        self.info_panel.setPlainText(info_text)

    def on_database_double_clicked(self, item):
        """Handle double-click on database."""
        db_info = item.data(Qt.UserRole)
        if db_info:
            self.open_database(db_info)

    def on_open_clicked(self):
        """Handle Open button click."""
        items = self.database_list.selectedItems()
        if items:
            db_info = items[0].data(Qt.UserRole)
            if db_info:
                self.open_database(db_info)

    def open_database(self, db_info):
        """Open the selected database."""
        database_path = db_info.get('path')
        archive_location = db_info.get('archive_location')

        # Validate archive location exists
        if not os.path.exists(archive_location):
            response = QMessageBox.warning(
                self,
                "Archive Location Not Found",
                f"The archive location for this database does not exist:\n\n"
                f"{archive_location}\n\n"
                f"The archive folder may have been moved or deleted.\n\n"
                f"Do you want to open this database anyway?\n"
                f"(You will need to update the archive location in the Database tab)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if response == QMessageBox.No:
                return

        self.selected_database = database_path
        self.database_selected.emit(database_path)
        self.accept()

    def on_create_clicked(self):
        """Handle Create New Database button click."""
        from ui.create_database_dialog import CreateDatabaseDialog

        dialog = CreateDatabaseDialog(self)
        if dialog.exec():
            # Reload databases to show the new one
            self.load_databases()

            # Auto-select the newly created database
            new_db_path = dialog.created_database_path
            if new_db_path:
                # Find and select the new database
                for i in range(self.database_list.count()):
                    item = self.database_list.item(i)
                    db_info = item.data(Qt.UserRole)
                    if db_info and db_info.get('path') == new_db_path:
                        self.database_list.setCurrentItem(item)
                        self.open_database(db_info)
                        break

    def on_browse_clicked(self):
        """Handle Browse button click - open file dialog to find a database."""
        # Determine starting directory
        start_dir = ""
        if self.search_paths:
            for path in self.search_paths:
                if os.path.isdir(path):
                    start_dir = path
                    break

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Database File",
            start_dir,
            "Database Files (*.db);;All Files (*)"
        )

        if not file_path:
            return  # User cancelled

        # Validate the selected file is a PyPhotoOrganizer database
        try:
            db_meta = DatabaseMetadata(file_path)
            metadata = db_meta.get_metadata()

            if not metadata:
                QMessageBox.warning(
                    self,
                    "Invalid Database",
                    f"The selected file does not appear to be a valid "
                    f"PyPhotoOrganizer database:\n\n{file_path}\n\n"
                    f"Please select a database created by this application."
                )
                return

            # Build db_info dict matching the format from find_databases
            db_info = {
                'path': os.path.abspath(file_path),
                'filename': os.path.basename(file_path),
                **metadata
            }

            # Get last activity date
            db_info['last_activity'] = self._get_last_activity_date(file_path)

            # Open the database directly
            self.open_database(db_info)

        except Exception as e:
            logger.error(f"Failed to open database {file_path}: {e}")
            QMessageBox.critical(
                self,
                "Error Opening Database",
                f"Failed to open the database file:\n\n{file_path}\n\nError: {str(e)}"
            )

    def get_selected_database(self):
        """Get the path of the selected database."""
        return self.selected_database
