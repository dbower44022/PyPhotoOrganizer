"""
Database Selector Dialog

Allows users to select an existing database or create a new one.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QListWidget, QListWidgetItem,
                               QMessageBox, QTextEdit, QApplication, QFileDialog,
                               QSplitter, QWidget, QFrame, QStyledItemDelegate,
                               QStyle)
from PySide6.QtCore import Qt, Signal, QSettings, QTimer, QSize
from PySide6.QtGui import QCloseEvent, QTextDocument, QPalette
from database_metadata import DatabaseMetadata
from datetime import datetime
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


class HtmlItemDelegate(QStyledItemDelegate):
    """Custom delegate to render HTML in QListWidget items."""

    def paint(self, painter, option, index):
        """Paint the item with HTML rendering."""
        options = option
        self.initStyleOption(options, index)

        painter.save()

        # Create text document for HTML rendering
        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width() - 10)

        # Draw background for selection
        style = option.widget.style() if option.widget else QApplication.style()
        style.drawPrimitive(QStyle.PE_PanelItemViewItem, options, painter, option.widget)

        # Translate painter to item position
        painter.translate(options.rect.left() + 5, options.rect.top() + 3)

        # Draw the HTML content
        doc.drawContents(painter)

        painter.restore()

    def sizeHint(self, option, index):
        """Calculate size hint based on HTML content."""
        options = option
        self.initStyleOption(options, index)

        doc = QTextDocument()
        doc.setHtml(options.text)
        doc.setTextWidth(options.rect.width() - 10 if options.rect.width() > 0 else 600)

        return QSize(int(doc.idealWidth()) + 10, int(doc.size().height()) + 6)


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

    @staticmethod
    def _diagnose_database(db_path: str) -> dict:
        """
        Diagnose why a database file might be invalid.

        Args:
            db_path: Path to the database file

        Returns:
            Dictionary with diagnosis:
                - is_valid: True if database is valid
                - is_sqlite: True if file is a valid SQLite database
                - has_metadata_table: True if DatabaseMetadata table exists
                - has_metadata_row: True if metadata row with id=1 exists
                - has_photos_table: True if UniquePhotos table exists
                - photo_count: Number of photos in database (if table exists)
                - error: Error message if any
                - can_repair: True if the issue is repairable
        """
        result = {
            'is_valid': False,
            'is_sqlite': False,
            'has_metadata_table': False,
            'has_metadata_row': False,
            'has_photos_table': False,
            'photo_count': 0,
            'error': None,
            'can_repair': False
        }

        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()

            # Check if it's a valid SQLite database by querying sqlite_master
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            result['is_sqlite'] = True

            # Check for DatabaseMetadata table
            if 'DatabaseMetadata' in tables:
                result['has_metadata_table'] = True

                # Check for metadata row
                cursor.execute("SELECT COUNT(*) FROM DatabaseMetadata WHERE id = 1")
                count = cursor.fetchone()[0]
                result['has_metadata_row'] = count > 0

            # Check for UniquePhotos table
            if 'UniquePhotos' in tables:
                result['has_photos_table'] = True
                cursor.execute("SELECT COUNT(*) FROM UniquePhotos")
                result['photo_count'] = cursor.fetchone()[0]

            conn.close()

            # Determine if valid
            result['is_valid'] = result['has_metadata_table'] and result['has_metadata_row']

            # Determine if repairable (has table structure but missing metadata row)
            if result['has_metadata_table'] and not result['has_metadata_row']:
                result['can_repair'] = True

        except sqlite3.DatabaseError as e:
            result['error'] = f"Not a valid SQLite database: {e}"
        except Exception as e:
            result['error'] = str(e)

        return result

    def _repair_database_metadata(self, db_path: str, diagnosis: dict) -> bool:
        """
        Repair a database by adding the missing metadata row.

        Args:
            db_path: Path to the database file
            diagnosis: Diagnosis dict from _diagnose_database

        Returns:
            True if repair was successful, False otherwise
        """
        # Derive database name from filename
        db_name = os.path.splitext(os.path.basename(db_path))[0]

        # Get archive location from user
        archive_location = QFileDialog.getExistingDirectory(
            self,
            "Select Archive Location",
            "",
            QFileDialog.ShowDirsOnly
        )

        if not archive_location:
            return False

        try:
            conn = sqlite3.connect(db_path, timeout=30)
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.cursor()

            now = datetime.now().isoformat()

            cursor.execute("""
                INSERT INTO DatabaseMetadata
                (id, database_name, description, archive_location, created_date, last_used_date, total_photos)
                VALUES (1, ?, '', ?, ?, ?, ?)
            """, (db_name, archive_location, now, now, diagnosis.get('photo_count', 0)))

            conn.commit()
            conn.close()

            logger.info(f"Repaired database metadata for {db_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to repair database {db_path}: {e}")
            QMessageBox.critical(
                self,
                "Repair Failed",
                f"Failed to repair database:\n\n{str(e)}"
            )
            return False

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

        # Create splitter for database list and info panel
        self.splitter = QSplitter(Qt.Vertical)
        self.splitter.setChildrenCollapsible(False)

        # Database list widget (top of splitter)
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        list_layout.setContentsMargins(0, 0, 0, 0)

        self.database_list = QListWidget()
        self.database_list.setAlternatingRowColors(True)
        self.database_list.setItemDelegate(HtmlItemDelegate(self.database_list))
        self.database_list.itemDoubleClicked.connect(self.on_database_double_clicked)
        self.database_list.itemSelectionChanged.connect(self.on_selection_changed)
        list_layout.addWidget(self.database_list)

        self.splitter.addWidget(list_widget)

        # Database info panel (bottom of splitter)
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 5, 0, 0)

        info_label = QLabel("Database Information:")
        info_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(info_label)

        self.info_panel = QTextEdit()
        self.info_panel.setReadOnly(True)
        self.info_panel.setStyleSheet("background-color: #f5f5f5; padding: 5px;")
        self.info_panel.setMinimumHeight(80)
        info_layout.addWidget(self.info_panel)

        self.splitter.addWidget(info_widget)

        layout.addWidget(self.splitter, 1)  # Splitter takes available space

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

            item_html = (
                f"<b>{name}</b><br>"
                f"&nbsp;&nbsp;<b>Archive:</b> {archive}<br>"
                f"&nbsp;&nbsp;<b>Photos:</b> {photos:,} &nbsp;|&nbsp; "
                f"<b>Last Activity:</b> {last_activity}"
            )
            item = QListWidgetItem(item_html)
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
        description = db_info.get('description', '') or 'None'
        info_html = f"""
<b>Name:</b> {db_info.get('database_name', 'N/A')}<br>
<b>Description:</b> {description}<br>
<b>Archive Location:</b> {db_info.get('archive_location', 'N/A')}<br>
<b>Created:</b> {db_info.get('created_date', 'N/A')[:10]}<br>
<b>Last Activity:</b> {last_activity}<br>
<b>Total Photos:</b> {db_info.get('total_photos', 0):,}<br>
<b>Database File:</b> {db_info.get('filename', 'N/A')}
        """.strip()
        self.info_panel.setHtml(info_html)

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

        # Diagnose the database to understand any issues
        diagnosis = self._diagnose_database(file_path)

        # Handle various diagnosis outcomes
        if diagnosis['error']:
            QMessageBox.critical(
                self,
                "Invalid File",
                f"The selected file is not a valid database:\n\n"
                f"{file_path}\n\n"
                f"Error: {diagnosis['error']}"
            )
            return

        if not diagnosis['is_sqlite']:
            QMessageBox.warning(
                self,
                "Invalid File",
                f"The selected file is not a SQLite database:\n\n{file_path}"
            )
            return

        if not diagnosis['has_metadata_table']:
            QMessageBox.warning(
                self,
                "Invalid Database",
                f"The selected file does not appear to be a PyPhotoOrganizer database.\n\n"
                f"Missing required table: DatabaseMetadata\n\n"
                f"Please select a database created by this application."
            )
            return

        if not diagnosis['has_metadata_row']:
            # Database has structure but missing metadata - offer to repair
            photo_info = ""
            if diagnosis['has_photos_table'] and diagnosis['photo_count'] > 0:
                photo_info = f"\n\nThe database contains {diagnosis['photo_count']:,} photo records."

            response = QMessageBox.question(
                self,
                "Database Metadata Missing",
                f"The database file exists but is missing its configuration metadata.\n\n"
                f"File: {file_path}{photo_info}\n\n"
                f"This can happen if the database was partially created or the metadata "
                f"was accidentally deleted.\n\n"
                f"Would you like to repair this database by providing the required "
                f"configuration (database name and archive location)?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if response == QMessageBox.Yes:
                if self._repair_database_metadata(file_path, diagnosis):
                    QMessageBox.information(
                        self,
                        "Database Repaired",
                        "The database has been repaired successfully."
                    )
                    # Now try to open it
                else:
                    return  # Repair cancelled or failed
            else:
                return

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

    def _save_geometry(self):
        """Save window geometry to settings."""
        settings = QSettings("PyPhotoOrganizer", "DatabaseSelector")
        settings.setValue("geometry", self.saveGeometry())
        settings.setValue("splitter_state", self.splitter.saveState())
        settings.sync()  # Ensure settings are written to disk

    def accept(self):
        """Save geometry before accepting dialog."""
        self._save_geometry()
        super().accept()

    def reject(self):
        """Save geometry before rejecting dialog."""
        self._save_geometry()
        super().reject()

    def closeEvent(self, event: QCloseEvent):
        """Save geometry when dialog closes."""
        self._save_geometry()
        super().closeEvent(event)

    def _adjust_splitter_for_content(self):
        """
        Adjust splitter sizes to minimize blank space below database list
        and maximize the info panel.
        """
        # Calculate the height needed for the database list
        list_height = 0
        for i in range(self.database_list.count()):
            item = self.database_list.item(i)
            list_height += self.database_list.visualItemRect(item).height()

        # Add some padding for borders and scrollbar
        list_height += 10

        # Set minimum height for the list (at least 3 items or 100px)
        min_list_height = max(100, min(list_height, 200))

        # Get total available height for the splitter
        total_height = self.splitter.height()

        if total_height > 0:
            # Calculate optimal list height: use actual content height but cap it
            # to leave room for the info panel
            optimal_list_height = min(list_height, total_height - 150)
            optimal_list_height = max(optimal_list_height, min_list_height)

            # Set splitter sizes: list gets content height, info panel gets the rest
            info_height = total_height - optimal_list_height
            self.splitter.setSizes([optimal_list_height, info_height])

    def showEvent(self, event):
        """Handle show event to adjust layout after dialog is displayed."""
        super().showEvent(event)
        # Delay adjustment until layout is complete
        QTimer.singleShot(0, self._initial_layout_adjustment)

    def _initial_layout_adjustment(self):
        """Perform initial layout adjustment after dialog is shown."""
        settings = QSettings("PyPhotoOrganizer", "DatabaseSelector")

        if settings.contains("geometry"):
            # Restore saved geometry (includes size and position)
            self.restoreGeometry(settings.value("geometry"))
            if settings.contains("splitter_state"):
                self.splitter.restoreState(settings.value("splitter_state"))
        else:
            # No saved geometry - adjust splitter for content, then center
            self._adjust_splitter_for_content()
            self.center_on_parent()
