"""
Album Management Dialog

Full-featured dialog for creating, editing, and managing albums.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QTextEdit, QCheckBox,
    QFileDialog, QMessageBox, QGroupBox, QSplitter, QFrame,
    QFormLayout, QWidget
)
from PySide6.QtCore import Qt, Signal
import os
import logging

from ui.theme import ThemeManager, get_theme
from album_manager import AlbumManager
from ui.add_to_album_dialog import CreateAlbumDialog

logger = logging.getLogger(__name__)


def format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


class AlbumManagementDialog(QDialog):
    """Dialog for managing all albums."""

    album_selected = Signal(int)  # Emitted when user selects album to view

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.album_manager = AlbumManager(db_path)
        self.current_album_id = None

        self.setWindowTitle("Album Management")
        self.setModal(True)
        self.resize(900, 600)

        self._init_ui()
        self._apply_theme()
        self._load_albums()

    def _init_ui(self):
        """Initialize the user interface."""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)

        # Left panel - Album list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 8, 16)

        list_label = QLabel("Albums")
        list_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        left_layout.addWidget(list_label)

        self.album_list = QListWidget()
        self.album_list.currentItemChanged.connect(self._on_album_selected)
        left_layout.addWidget(self.album_list)

        # Album list buttons
        list_btn_layout = QHBoxLayout()
        list_btn_layout.setSpacing(8)

        self.new_btn = QPushButton("+ New")
        self.new_btn.clicked.connect(self._create_new_album)
        list_btn_layout.addWidget(self.new_btn)

        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self._delete_album)
        list_btn_layout.addWidget(self.delete_btn)

        left_layout.addLayout(list_btn_layout)

        splitter.addWidget(left_panel)

        # Right panel - Album details
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 16, 16, 16)

        details_label = QLabel("Album Details")
        details_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        right_layout.addWidget(details_label)

        # Details form
        details_group = QGroupBox()
        form_layout = QFormLayout(details_group)
        form_layout.setSpacing(12)

        # Name field
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Album name")
        form_layout.addRow("Name:", self.name_edit)

        # Description field
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional description")
        form_layout.addRow("Description:", self.desc_edit)

        # Storage location (read-only display)
        self.location_label = QLabel("")
        self.location_label.setWordWrap(True)
        self.location_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        form_layout.addRow("Storage:", self.location_label)

        # Sync deletions checkbox
        self.sync_checkbox = QCheckBox("Sync deletions from archive")
        self.sync_checkbox.setToolTip(
            "When enabled, photos deleted from the archive\n"
            "will also be removed from this album."
        )
        form_layout.addRow("", self.sync_checkbox)

        right_layout.addWidget(details_group)

        # Statistics group
        stats_group = QGroupBox("Statistics")
        stats_layout = QFormLayout(stats_group)
        stats_layout.setSpacing(8)

        self.photo_count_label = QLabel("-")
        stats_layout.addRow("Photos:", self.photo_count_label)

        self.size_label = QLabel("-")
        stats_layout.addRow("Total Size:", self.size_label)

        self.created_label = QLabel("-")
        stats_layout.addRow("Created:", self.created_label)

        self.updated_label = QLabel("-")
        stats_layout.addRow("Last Updated:", self.updated_label)

        self.status_label = QLabel("-")
        stats_layout.addRow("Status:", self.status_label)

        right_layout.addWidget(stats_group)

        right_layout.addStretch()

        # Action buttons
        action_layout = QHBoxLayout()
        action_layout.setSpacing(8)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self._open_album_folder)
        action_layout.addWidget(self.open_folder_btn)

        self.verify_btn = QPushButton("Verify")
        self.verify_btn.clicked.connect(self._verify_album)
        self.verify_btn.setToolTip("Check for missing or orphan files")
        action_layout.addWidget(self.verify_btn)

        action_layout.addStretch()

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.clicked.connect(self._save_changes)
        action_layout.addWidget(self.save_btn)

        right_layout.addLayout(action_layout)

        splitter.addWidget(right_panel)

        # Set initial splitter sizes (1:2 ratio)
        splitter.setSizes([300, 600])

        main_layout.addWidget(splitter)

        # Initially disable details panel
        self._set_details_enabled(False)

    def _apply_theme(self):
        """Apply theme styling."""
        theme = get_theme()
        c = theme.colors

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg_primary};
                color: {c.text_primary};
            }}
            QListWidget {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_light};
                border-radius: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-bottom: 1px solid {c.border_light};
            }}
            QListWidget::item:selected {{
                background-color: {c.primary};
                color: white;
            }}
            QListWidget::item:hover:!selected {{
                background-color: {c.hover_bg};
            }}
            QGroupBox {{
                font-weight: bold;
                border: 1px solid {c.border_light};
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 12px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
            QLabel {{
                color: {c.text_primary};
            }}
            QLineEdit {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: 4px;
                padding: 8px;
            }}
            QLineEdit:focus {{
                border-color: {c.primary};
            }}
            QLineEdit:disabled {{
                background-color: {c.bg_tertiary};
                color: {c.text_disabled};
            }}
            QCheckBox {{
                color: {c.text_primary};
            }}
            QCheckBox:disabled {{
                color: {c.text_disabled};
            }}
            QPushButton {{
                background-color: {c.bg_tertiary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: 4px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {c.primary};
                color: white;
                border-color: {c.primary};
            }}
            QPushButton:disabled {{
                background-color: {c.bg_secondary};
                color: {c.text_disabled};
                border-color: {c.border_light};
            }}
        """)

        # Style save button as primary
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {c.primary};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {c.primary_hover};
            }}
            QPushButton:disabled {{
                background-color: {c.gray_400};
            }}
        """)

    def _set_details_enabled(self, enabled: bool):
        """Enable/disable details panel widgets."""
        self.name_edit.setEnabled(enabled)
        self.desc_edit.setEnabled(enabled)
        self.sync_checkbox.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        self.open_folder_btn.setEnabled(enabled)
        self.verify_btn.setEnabled(enabled)

        if not enabled:
            self.name_edit.clear()
            self.desc_edit.clear()
            self.location_label.setText("-")
            self.sync_checkbox.setChecked(False)
            self.photo_count_label.setText("-")
            self.size_label.setText("-")
            self.created_label.setText("-")
            self.updated_label.setText("-")
            self.status_label.setText("-")

    def _load_albums(self):
        """Load all albums into the list."""
        self.album_list.clear()
        self.current_album_id = None
        self._set_details_enabled(False)

        albums = self.album_manager.get_all_albums(include_inactive=True)

        for album in albums:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, album['id'])

            # Format display text
            name = album['album_name']
            count = album['photo_count']
            status = "" if album['is_active'] else " (inactive)"

            item.setText(f"{name} ({count}){status}")
            self.album_list.addItem(item)

    def _on_album_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        """Handle album selection - show details."""
        if not current:
            self._set_details_enabled(False)
            self.current_album_id = None
            return

        album_id = current.data(Qt.UserRole)
        self.current_album_id = album_id

        album = self.album_manager.get_album(album_id)
        if not album:
            self._set_details_enabled(False)
            return

        self._set_details_enabled(True)

        # Populate fields
        self.name_edit.setText(album['album_name'])
        self.desc_edit.setText(album['album_description'] or "")
        self.location_label.setText(album['storage_location'])
        self.sync_checkbox.setChecked(album['sync_deletions'] == 1)

        # Statistics
        self.photo_count_label.setText(str(album['photo_count']))
        self.size_label.setText(format_size(album['total_size_bytes']))

        created = album.get('created_timestamp', '-')
        if created and created != '-':
            created = created[:19].replace('T', ' ')
        self.created_label.setText(created)

        updated = album.get('updated_timestamp', '-')
        if updated and updated != '-':
            updated = updated[:19].replace('T', ' ')
        self.updated_label.setText(updated or "Never")

        # Status
        if album['is_active']:
            if os.path.exists(album['storage_location']):
                self.status_label.setText("Active")
                self.status_label.setStyleSheet("color: #10B981;")  # Green
            else:
                self.status_label.setText("Storage unavailable")
                self.status_label.setStyleSheet("color: #EF4444;")  # Red
        else:
            self.status_label.setText("Inactive")
            self.status_label.setStyleSheet("color: #F59E0B;")  # Amber

    def _create_new_album(self):
        """Open dialog to create new album."""
        dialog = CreateAlbumDialog(self.db_path, self)
        if dialog.exec() == QDialog.Accepted:
            self._load_albums()

            # Select the new album
            if dialog.created_album_id:
                for i in range(self.album_list.count()):
                    item = self.album_list.item(i)
                    if item.data(Qt.UserRole) == dialog.created_album_id:
                        self.album_list.setCurrentItem(item)
                        break

    def _delete_album(self):
        """Delete the selected album with confirmation."""
        if not self.current_album_id:
            QMessageBox.information(
                self, "No Selection",
                "Please select an album to delete."
            )
            return

        album = self.album_manager.get_album(self.current_album_id)
        if not album:
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Delete album '{album['album_name']}'?\n\n"
            f"This will also delete {album['photo_count']} photo(s) from the album folder.\n"
            f"(Original archive files will not be affected)",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Delete album
        if self.album_manager.delete_album(self.current_album_id, delete_files=True):
            QMessageBox.information(
                self, "Album Deleted",
                f"Album '{album['album_name']}' has been deleted."
            )
            self._load_albums()
        else:
            QMessageBox.warning(
                self, "Delete Failed",
                "Failed to delete album. Check logs for details."
            )

    def _save_changes(self):
        """Save changes to selected album."""
        if not self.current_album_id:
            return

        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Invalid Name", "Album name cannot be empty.")
            return

        description = self.desc_edit.text().strip()
        sync_deletions = self.sync_checkbox.isChecked()

        if self.album_manager.update_album(
            self.current_album_id,
            name=name,
            description=description,
            sync_deletions=sync_deletions
        ):
            QMessageBox.information(self, "Saved", "Album changes saved.")
            self._load_albums()

            # Re-select the album
            for i in range(self.album_list.count()):
                item = self.album_list.item(i)
                if item.data(Qt.UserRole) == self.current_album_id:
                    self.album_list.setCurrentItem(item)
                    break
        else:
            QMessageBox.warning(
                self, "Save Failed",
                "Failed to save changes. The name may already be in use."
            )

    def _open_album_folder(self):
        """Open album folder in file manager."""
        if not self.current_album_id:
            return

        album = self.album_manager.get_album(self.current_album_id)
        if not album:
            return

        storage_path = album['storage_location']
        if not os.path.exists(storage_path):
            QMessageBox.warning(
                self, "Folder Not Found",
                f"Album storage folder does not exist:\n{storage_path}"
            )
            return

        # Open in file manager (cross-platform)
        import subprocess
        import sys

        try:
            if sys.platform == 'win32':
                os.startfile(storage_path)
            elif sys.platform == 'darwin':
                subprocess.run(['open', storage_path])
            else:
                subprocess.run(['xdg-open', storage_path])
        except Exception as e:
            QMessageBox.warning(
                self, "Error",
                f"Could not open folder:\n{e}"
            )

    def _verify_album(self):
        """Verify album storage consistency."""
        if not self.current_album_id:
            return

        album = self.album_manager.get_album(self.current_album_id)
        if not album:
            return

        result = self.album_manager.verify_album_storage(self.current_album_id)

        status = result.get('status', 'unknown')

        if status == 'ok':
            QMessageBox.information(
                self, "Verification Complete",
                f"Album '{album['album_name']}' is consistent.\n\n"
                f"Files: {result.get('total_files', 0)}\n"
                f"Size: {format_size(result.get('total_size', 0))}"
            )
        elif status == 'unavailable':
            QMessageBox.warning(
                self, "Storage Unavailable",
                f"Cannot access album storage:\n{album['storage_location']}"
            )
        elif status == 'inconsistent':
            missing = result.get('missing_files', [])
            orphans = result.get('orphan_files', [])

            message = f"Album has inconsistencies:\n\n"
            if missing:
                message += f"Missing files (in DB but not on disk): {len(missing)}\n"
            if orphans:
                message += f"Orphan files (on disk but not in DB): {len(orphans)}\n"

            QMessageBox.warning(self, "Inconsistencies Found", message)
        else:
            QMessageBox.information(
                self, "Verification Result",
                f"Status: {status}"
            )
