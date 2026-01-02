"""
Database Selector Dialog

Allows users to select an existing database or create a new one.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QListWidgetItem,
                               QMessageBox, QTextEdit, QApplication)
from PySide6.QtCore import Qt, Signal
from database_metadata import DatabaseMetadata
import os


class DatabaseSelectorDialog(QDialog):
    """Dialog for selecting or creating a database."""

    database_selected = Signal(str)  # Emits database path

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_database = None
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
        self.databases = DatabaseMetadata.find_databases()

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

            item_text = f"{name}\n  Archive: {archive}\n  Photos: {photos:,}"
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
        info_text = f"""
Name: {db_info.get('database_name', 'N/A')}
Description: {db_info.get('description', 'None')}
Archive Location: {db_info.get('archive_location', 'N/A')}
Created: {db_info.get('created_date', 'N/A')[:10]}
Last Used: {db_info.get('last_used_date', 'Never')[:10] if db_info.get('last_used_date') else 'Never'}
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

    def get_selected_database(self):
        """Get the path of the selected database."""
        return self.selected_database
