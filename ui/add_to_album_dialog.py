"""
Add to Album Dialog

Quick dialog for adding selected photos to an existing or new album.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QLabel, QProgressDialog, QMessageBox,
    QLineEdit, QFileDialog, QCheckBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
import os
import logging

from ui.theme import ThemeManager, get_theme
from album_manager import AlbumManager
from ui.album_worker import AddToAlbumWorker

logger = logging.getLogger(__name__)


class AddToAlbumDialog(QDialog):
    """Dialog for adding photos to an album."""

    def __init__(self, selected_records: list, db_path: str, parent=None):
        """
        Initialize dialog.

        Args:
            selected_records: List of selected photo records
            db_path: Database path
        """
        super().__init__(parent)
        self.selected_records = selected_records
        self.db_path = db_path
        self.album_manager = AlbumManager(db_path)
        self.worker = None
        self.progress_dialog = None

        self.setWindowTitle(f"Add {len(selected_records)} Photo(s) to Album")
        self.setModal(True)
        self.resize(450, 250)

        self._init_ui()
        self._apply_theme()
        self._load_albums()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        header_label = QLabel(f"Add {len(self.selected_records)} photo(s) to album:")
        header_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(header_label)

        # Album selection combo
        album_layout = QHBoxLayout()

        self.album_combo = QComboBox()
        self.album_combo.setMinimumWidth(300)
        self.album_combo.currentIndexChanged.connect(self._on_album_changed)
        album_layout.addWidget(self.album_combo, 1)

        layout.addLayout(album_layout)

        # Create new album button
        self.new_album_btn = QPushButton("+ Create New Album...")
        self.new_album_btn.clicked.connect(self._create_new_album)
        layout.addWidget(self.new_album_btn)

        # Album info label
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(self.info_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)

        self.add_btn = QPushButton("Add to Album")
        self.add_btn.clicked.connect(self._add_to_album)
        self.add_btn.setDefault(True)
        button_layout.addWidget(self.add_btn)

        layout.addLayout(button_layout)

    def _apply_theme(self):
        """Apply theme styling."""
        theme = get_theme()
        c = theme.colors

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg_primary};
                color: {c.text_primary};
            }}
            QLabel {{
                color: {c.text_primary};
            }}
            QComboBox {{
                background-color: {c.bg_secondary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: 4px;
                padding: 8px 12px;
                min-height: 20px;
            }}
            QComboBox:hover {{
                border-color: {c.primary};
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {c.bg_primary};
                color: {c.text_primary};
                selection-background-color: {c.primary};
                selection-color: white;
            }}
            QPushButton {{
                background-color: {c.bg_tertiary};
                color: {c.text_primary};
                border: 1px solid {c.border_medium};
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c.primary};
                color: white;
                border-color: {c.primary};
            }}
            QPushButton:pressed {{
                background-color: {c.primary_hover};
            }}
        """)

        # Style the Add button to be primary
        self.add_btn.setStyleSheet(f"""
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
        """)

    def _load_albums(self):
        """Populate album dropdown."""
        self.album_combo.clear()

        albums = self.album_manager.get_all_albums()

        if not albums:
            self.album_combo.addItem("No albums - create one first", None)
            self.add_btn.setEnabled(False)
        else:
            for album in albums:
                display_text = f"{album['album_name']} ({album['photo_count']} photos)"
                self.album_combo.addItem(display_text, album['id'])
            self.add_btn.setEnabled(True)

        self._on_album_changed()

    def _on_album_changed(self):
        """Handle album selection change."""
        album_id = self.album_combo.currentData()
        if album_id:
            album = self.album_manager.get_album(album_id)
            if album:
                size_mb = album['total_size_bytes'] / (1024 * 1024)
                self.info_label.setText(
                    f"Location: {album['storage_location']}\n"
                    f"Size: {size_mb:.1f} MB"
                )
            else:
                self.info_label.setText("")
        else:
            self.info_label.setText("")

    def _create_new_album(self):
        """Open dialog to create a new album."""
        dialog = CreateAlbumDialog(self.db_path, self)
        if dialog.exec() == QDialog.Accepted:
            # Refresh album list and select the new album
            self._load_albums()
            new_album_id = dialog.created_album_id
            if new_album_id:
                # Find and select the new album
                for i in range(self.album_combo.count()):
                    if self.album_combo.itemData(i) == new_album_id:
                        self.album_combo.setCurrentIndex(i)
                        break

    def _add_to_album(self):
        """Execute add operation with progress dialog."""
        album_id = self.album_combo.currentData()
        if not album_id:
            QMessageBox.information(
                self, "No Album Selected",
                "Please select an album or create a new one."
            )
            return

        album = self.album_manager.get_album(album_id)
        if not album:
            QMessageBox.warning(self, "Error", "Selected album not found.")
            return

        # Verify storage is available
        storage_path = album['storage_location']
        if not os.path.exists(storage_path):
            try:
                os.makedirs(storage_path, exist_ok=True)
            except OSError as e:
                QMessageBox.warning(
                    self, "Storage Error",
                    f"Cannot access album storage:\n{storage_path}\n\nError: {e}"
                )
                return

        # Create progress dialog
        self.progress_dialog = QProgressDialog(
            "Adding photos to album...", "Cancel",
            0, len(self.selected_records), self
        )
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.setAutoReset(False)

        # Create and start worker
        self.worker = AddToAlbumWorker(
            album_id=album_id,
            records=self.selected_records,
            db_path=self.db_path,
            album_storage_path=storage_path,
            worker_logger=logger
        )

        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.progress_dialog.canceled.connect(self._on_cancel)

        self.worker.start()

    def _on_progress(self, current: int, total: int, filename: str):
        """Handle progress updates."""
        if self.progress_dialog:
            self.progress_dialog.setValue(current)
            self.progress_dialog.setLabelText(f"Adding: {filename}")

    def _on_cancel(self):
        """Handle cancel button."""
        if self.worker:
            self.worker.cancel()

    def _on_finished(self, result: dict):
        """Handle worker completion."""
        if self.progress_dialog:
            self.progress_dialog.close()
            self.progress_dialog = None

        added = result.get('added', 0)
        skipped = result.get('skipped', 0)
        errors = result.get('errors', [])

        # Show result message
        if errors:
            message = f"Added: {added}\nSkipped: {skipped}\nErrors: {len(errors)}"
            if len(errors) <= 5:
                message += "\n\nErrors:\n" + "\n".join(errors)
            QMessageBox.warning(self, "Completed with Errors", message)
        elif added > 0:
            QMessageBox.information(
                self, "Success",
                f"Added {added} photo(s) to album.\n"
                f"Skipped {skipped} (already in album)."
            )
        else:
            QMessageBox.information(
                self, "No Changes",
                f"All {skipped} photo(s) were already in the album."
            )

        self.accept()

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close - ensure worker thread is properly stopped."""
        if self.worker and self.worker.isRunning():
            logger.info("Stopping album worker before dialog close...")
            self.worker.cancel()
            self.worker.wait()  # Wait for thread to finish
            logger.info("Album worker stopped")
        event.accept()


class CreateAlbumDialog(QDialog):
    """Dialog for creating a new album."""

    def __init__(self, db_path: str, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.album_manager = AlbumManager(db_path)
        self.created_album_id = None

        self.setWindowTitle("Create New Album")
        self.setModal(True)
        self.resize(500, 350)

        self._init_ui()
        self._apply_theme()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # Form layout
        form_group = QGroupBox("Album Details")
        form_layout = QFormLayout(form_group)
        form_layout.setSpacing(12)

        # Album name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., Living Room Photo Frame")
        form_layout.addRow("Album Name:", self.name_edit)

        # Description
        self.desc_edit = QLineEdit()
        self.desc_edit.setPlaceholderText("Optional description")
        form_layout.addRow("Description:", self.desc_edit)

        # Storage location
        location_layout = QHBoxLayout()
        self.location_edit = QLineEdit()
        self.location_edit.setPlaceholderText("Select folder for album files...")
        self.location_edit.setReadOnly(True)
        location_layout.addWidget(self.location_edit, 1)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_location)
        location_layout.addWidget(browse_btn)

        form_layout.addRow("Storage Location:", location_layout)

        # Sync deletions checkbox
        self.sync_checkbox = QCheckBox("Sync deletions from archive")
        self.sync_checkbox.setChecked(True)
        self.sync_checkbox.setToolTip(
            "When enabled, photos deleted from the archive\n"
            "will also be removed from this album."
        )
        form_layout.addRow("", self.sync_checkbox)

        layout.addWidget(form_group)

        # Info text
        info_label = QLabel(
            "The album will store copies of your photos in the specified location.\n"
            "This is ideal for photo frames that read from a specific folder."
        )
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        layout.addStretch()

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self.create_btn = QPushButton("Create Album")
        self.create_btn.clicked.connect(self._create_album)
        self.create_btn.setDefault(True)
        button_layout.addWidget(self.create_btn)

        layout.addLayout(button_layout)

    def _apply_theme(self):
        """Apply theme styling."""
        theme = get_theme()
        c = theme.colors

        self.setStyleSheet(f"""
            QDialog {{
                background-color: {c.bg_primary};
                color: {c.text_primary};
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
            QLineEdit:read-only {{
                background-color: {c.bg_tertiary};
            }}
            QCheckBox {{
                color: {c.text_primary};
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
        """)

        # Style create button as primary
        self.create_btn.setStyleSheet(f"""
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
        """)

    def _browse_location(self):
        """Open folder browser for storage location."""
        folder = QFileDialog.getExistingDirectory(
            self, "Select Album Storage Location",
            os.path.expanduser("~")
        )
        if folder:
            self.location_edit.setText(folder)

    def _create_album(self):
        """Create the album."""
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing Name", "Please enter an album name.")
            self.name_edit.setFocus()
            return

        location = self.location_edit.text().strip()
        if not location:
            QMessageBox.warning(
                self, "Missing Location",
                "Please select a storage location for the album."
            )
            return

        description = self.desc_edit.text().strip()
        sync_deletions = self.sync_checkbox.isChecked()

        try:
            album_id = self.album_manager.create_album(
                name=name,
                storage_location=location,
                description=description,
                sync_deletions=sync_deletions
            )

            if album_id:
                self.created_album_id = album_id
                QMessageBox.information(
                    self, "Album Created",
                    f"Album '{name}' created successfully."
                )
                self.accept()
            else:
                QMessageBox.warning(
                    self, "Creation Failed",
                    "Album name may already exist. Please choose a different name."
                )

        except ValueError as e:
            QMessageBox.warning(self, "Invalid Input", str(e))
        except Exception as e:
            logger.error(f"Failed to create album: {e}", exc_info=True)
            QMessageBox.critical(
                self, "Error",
                f"Failed to create album:\n{str(e)}"
            )
