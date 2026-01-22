"""
Archive Maintenance Tab for PyPhotoOrganizer GUI

This tab contains archive maintenance features:
- Archive Backup - Full backup of database + all archives + albums
- Database Maintenance - Integrity check, vacuum, statistics
- Archive Verification - Hash verification, orphan detection, missing file detection
- Storage Statistics - Size breakdown by archive type
- Delete Vault Management - View/purge soft-deleted files
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QPushButton, QLabel, QMessageBox, QScrollArea,
                               QFormLayout, QLineEdit, QFileDialog, QProgressBar,
                               QGridLayout, QTextEdit)
from PySide6.QtCore import Qt
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ArchiveMaintenanceTab(QWidget):
    """Tab for archive maintenance and backup operations."""

    def __init__(self):
        super().__init__()
        self.db_metadata = None
        self.album_manager = None

        # Worker references for cleanup
        self._backup_worker = None
        self._verification_worker = None
        self._storage_stats_worker = None

        # Stylesheet for bold GroupBox titles
        self.groupbox_style = """
            QGroupBox {
                font-weight: bold;
                font-size: 11pt;
                border: 2px solid #c0c0c0;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                left: 10px;
                padding: 0 5px;
            }
        """

        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        main_widget = QWidget()
        layout = QVBoxLayout()

        # ========== Archive Backup Group ==========
        backup_group = QGroupBox("Archive Backup")
        backup_group.setStyleSheet(self.groupbox_style)
        backup_layout = QVBoxLayout()

        backup_desc = QLabel(
            "Create a complete backup of your database and all archive locations. "
            "Includes main archive, video archive, prior revisions, delete vault, and albums."
        )
        backup_desc.setWordWrap(True)
        backup_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        backup_layout.addWidget(backup_desc)

        # Backup location row
        location_layout = QHBoxLayout()
        location_layout.addWidget(QLabel("Backup Location:"))
        self.backup_location_edit = QLineEdit()
        self.backup_location_edit.setReadOnly(True)
        self.backup_location_edit.setPlaceholderText("Not configured - click Browse to set")
        location_layout.addWidget(self.backup_location_edit, stretch=1)

        self.backup_browse_btn = QPushButton("Browse...")
        self.backup_browse_btn.clicked.connect(self.on_browse_backup_location)
        location_layout.addWidget(self.backup_browse_btn)

        self.backup_clear_btn = QPushButton("Clear")
        self.backup_clear_btn.clicked.connect(self.on_clear_backup_location)
        location_layout.addWidget(self.backup_clear_btn)

        backup_layout.addLayout(location_layout)

        # Last backup info row
        info_layout = QHBoxLayout()
        self.last_backup_label = QLabel("Last Backup: Never")
        self.last_backup_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.last_backup_label)

        self.backup_status_label = QLabel("")
        info_layout.addWidget(self.backup_status_label)
        info_layout.addStretch()
        backup_layout.addLayout(info_layout)

        # Backup buttons row
        backup_btn_layout = QHBoxLayout()
        self.run_backup_btn = QPushButton("Run Full Backup Now")
        self.run_backup_btn.clicked.connect(self.on_run_backup)
        backup_btn_layout.addWidget(self.run_backup_btn)

        self.cancel_backup_btn = QPushButton("Cancel Backup")
        self.cancel_backup_btn.clicked.connect(self.on_cancel_backup)
        self.cancel_backup_btn.hide()
        backup_btn_layout.addWidget(self.cancel_backup_btn)

        backup_btn_layout.addStretch()
        backup_layout.addLayout(backup_btn_layout)

        # Progress bar (hidden by default)
        self.backup_progress = QProgressBar()
        self.backup_progress.setRange(0, 100)
        self.backup_progress.setValue(0)
        self.backup_progress.hide()
        backup_layout.addWidget(self.backup_progress)

        self.backup_progress_label = QLabel("")
        self.backup_progress_label.setStyleSheet("color: #666;")
        self.backup_progress_label.hide()
        backup_layout.addWidget(self.backup_progress_label)

        backup_group.setLayout(backup_layout)
        layout.addWidget(backup_group)

        # ========== Database Maintenance Group ==========
        db_group = QGroupBox("Database Maintenance")
        db_group.setStyleSheet(self.groupbox_style)
        db_layout = QVBoxLayout()

        db_desc = QLabel(
            "Check database integrity, optimize storage, and view statistics."
        )
        db_desc.setWordWrap(True)
        db_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        db_layout.addWidget(db_desc)

        # Buttons row
        db_btn_layout = QHBoxLayout()
        self.check_integrity_btn = QPushButton("Check Integrity")
        self.check_integrity_btn.setToolTip("Run SQLite integrity check on the database")
        self.check_integrity_btn.clicked.connect(self.on_check_integrity)
        db_btn_layout.addWidget(self.check_integrity_btn)

        self.vacuum_btn = QPushButton("Vacuum Database")
        self.vacuum_btn.setToolTip("Reclaim unused space and optimize database file")
        self.vacuum_btn.clicked.connect(self.on_vacuum_database)
        db_btn_layout.addWidget(self.vacuum_btn)

        self.refresh_db_stats_btn = QPushButton("Refresh Statistics")
        self.refresh_db_stats_btn.clicked.connect(self.refresh_database_stats)
        db_btn_layout.addWidget(self.refresh_db_stats_btn)

        db_btn_layout.addStretch()
        db_layout.addLayout(db_btn_layout)

        # Stats grid
        stats_grid = QGridLayout()
        stats_grid.addWidget(QLabel("Database Size:"), 0, 0)
        self.db_size_label = QLabel("-")
        self.db_size_label.setStyleSheet("font-weight: bold;")
        stats_grid.addWidget(self.db_size_label, 0, 1)

        stats_grid.addWidget(QLabel("WAL Size:"), 0, 2)
        self.wal_size_label = QLabel("-")
        stats_grid.addWidget(self.wal_size_label, 0, 3)

        stats_grid.addWidget(QLabel("Total Records:"), 1, 0)
        self.total_records_label = QLabel("-")
        self.total_records_label.setStyleSheet("font-weight: bold;")
        stats_grid.addWidget(self.total_records_label, 1, 1)

        stats_grid.addWidget(QLabel("Schema Version:"), 1, 2)
        self.schema_version_label = QLabel("-")
        stats_grid.addWidget(self.schema_version_label, 1, 3)

        stats_grid.setColumnStretch(4, 1)
        db_layout.addLayout(stats_grid)

        # Integrity result label
        self.db_result_label = QLabel("")
        self.db_result_label.setWordWrap(True)
        db_layout.addWidget(self.db_result_label)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # ========== Archive Verification Group ==========
        verify_group = QGroupBox("Archive Verification")
        verify_group.setStyleSheet(self.groupbox_style)
        verify_layout = QVBoxLayout()

        verify_desc = QLabel(
            "Verify archive integrity by checking file hashes, finding orphaned files "
            "(files in archive not in database), and detecting missing files "
            "(database records without files on disk)."
        )
        verify_desc.setWordWrap(True)
        verify_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        verify_layout.addWidget(verify_desc)

        # Buttons row
        verify_btn_layout = QHBoxLayout()
        self.verify_hashes_btn = QPushButton("Verify File Hashes")
        self.verify_hashes_btn.setToolTip("Recalculate and verify hashes for all archive files")
        self.verify_hashes_btn.clicked.connect(self.on_verify_hashes)
        verify_btn_layout.addWidget(self.verify_hashes_btn)

        self.find_orphaned_btn = QPushButton("Find Orphaned Files")
        self.find_orphaned_btn.setToolTip("Find files in archive that are not tracked in database")
        self.find_orphaned_btn.clicked.connect(self.on_find_orphaned)
        verify_btn_layout.addWidget(self.find_orphaned_btn)

        self.find_missing_btn = QPushButton("Find Missing Files")
        self.find_missing_btn.setToolTip("Find database records where files are missing from disk")
        self.find_missing_btn.clicked.connect(self.on_find_missing)
        verify_btn_layout.addWidget(self.find_missing_btn)

        self.cancel_verify_btn = QPushButton("Cancel")
        self.cancel_verify_btn.clicked.connect(self.on_cancel_verification)
        self.cancel_verify_btn.hide()
        verify_btn_layout.addWidget(self.cancel_verify_btn)

        verify_btn_layout.addStretch()
        verify_layout.addLayout(verify_btn_layout)

        # Progress bar (hidden by default)
        self.verify_progress = QProgressBar()
        self.verify_progress.setRange(0, 100)
        self.verify_progress.setValue(0)
        self.verify_progress.hide()
        verify_layout.addWidget(self.verify_progress)

        self.verify_progress_label = QLabel("")
        self.verify_progress_label.setStyleSheet("color: #666;")
        self.verify_progress_label.hide()
        verify_layout.addWidget(self.verify_progress_label)

        # Results text area (hidden by default)
        self.verify_results_text = QTextEdit()
        self.verify_results_text.setReadOnly(True)
        self.verify_results_text.setMaximumHeight(150)
        self.verify_results_text.hide()
        verify_layout.addWidget(self.verify_results_text)

        verify_group.setLayout(verify_layout)
        layout.addWidget(verify_group)

        # ========== Storage Statistics Group ==========
        storage_group = QGroupBox("Storage Statistics")
        storage_group.setStyleSheet(self.groupbox_style)
        storage_layout = QVBoxLayout()

        storage_desc = QLabel(
            "View storage usage breakdown by archive type."
        )
        storage_desc.setWordWrap(True)
        storage_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        storage_layout.addWidget(storage_desc)

        # Refresh button
        refresh_storage_layout = QHBoxLayout()
        self.refresh_storage_btn = QPushButton("Refresh Statistics")
        self.refresh_storage_btn.clicked.connect(self.on_refresh_storage_stats)
        refresh_storage_layout.addWidget(self.refresh_storage_btn)

        self.cancel_storage_btn = QPushButton("Cancel")
        self.cancel_storage_btn.clicked.connect(self.on_cancel_storage_stats)
        self.cancel_storage_btn.hide()
        refresh_storage_layout.addWidget(self.cancel_storage_btn)

        refresh_storage_layout.addStretch()
        storage_layout.addLayout(refresh_storage_layout)

        # Storage grid
        storage_grid = QGridLayout()

        # Headers
        storage_grid.addWidget(QLabel("Location"), 0, 0)
        header_size = QLabel("Size")
        header_size.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(header_size, 0, 1)
        header_files = QLabel("Files")
        header_files.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(header_files, 0, 2)

        # Main Archive
        storage_grid.addWidget(QLabel("Main Archive:"), 1, 0)
        self.main_archive_size_label = QLabel("-")
        self.main_archive_size_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.main_archive_size_label, 1, 1)
        self.main_archive_files_label = QLabel("-")
        self.main_archive_files_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.main_archive_files_label, 1, 2)

        # Video Archive
        storage_grid.addWidget(QLabel("Video Archive:"), 2, 0)
        self.video_archive_size_label = QLabel("-")
        self.video_archive_size_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.video_archive_size_label, 2, 1)
        self.video_archive_files_label = QLabel("-")
        self.video_archive_files_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.video_archive_files_label, 2, 2)

        # Prior Revisions
        storage_grid.addWidget(QLabel("Prior Revisions:"), 3, 0)
        self.prior_rev_size_label = QLabel("-")
        self.prior_rev_size_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.prior_rev_size_label, 3, 1)
        self.prior_rev_files_label = QLabel("-")
        self.prior_rev_files_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.prior_rev_files_label, 3, 2)

        # Delete Vault
        storage_grid.addWidget(QLabel("Delete Vault:"), 4, 0)
        self.delete_vault_size_label = QLabel("-")
        self.delete_vault_size_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.delete_vault_size_label, 4, 1)
        self.delete_vault_files_label = QLabel("-")
        self.delete_vault_files_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.delete_vault_files_label, 4, 2)

        # Albums
        storage_grid.addWidget(QLabel("Albums:"), 5, 0)
        self.albums_size_label = QLabel("-")
        self.albums_size_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.albums_size_label, 5, 1)
        self.albums_files_label = QLabel("-")
        self.albums_files_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.albums_files_label, 5, 2)

        # Database Files
        storage_grid.addWidget(QLabel("Database Files:"), 6, 0)
        self.database_files_size_label = QLabel("-")
        self.database_files_size_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.database_files_size_label, 6, 1)
        self.database_files_count_label = QLabel("-")
        self.database_files_count_label.setAlignment(Qt.AlignRight)
        storage_grid.addWidget(self.database_files_count_label, 6, 2)

        # Separator line
        separator = QLabel("─" * 40)
        separator.setStyleSheet("color: #c0c0c0;")
        storage_grid.addWidget(separator, 7, 0, 1, 3)

        # Total
        total_label = QLabel("Total:")
        total_label.setStyleSheet("font-weight: bold;")
        storage_grid.addWidget(total_label, 8, 0)
        self.total_size_label = QLabel("-")
        self.total_size_label.setAlignment(Qt.AlignRight)
        self.total_size_label.setStyleSheet("font-weight: bold;")
        storage_grid.addWidget(self.total_size_label, 8, 1)
        self.total_files_label = QLabel("-")
        self.total_files_label.setAlignment(Qt.AlignRight)
        self.total_files_label.setStyleSheet("font-weight: bold;")
        storage_grid.addWidget(self.total_files_label, 8, 2)

        storage_grid.setColumnStretch(3, 1)
        storage_layout.addLayout(storage_grid)

        # Progress label for scanning
        self.storage_progress_label = QLabel("")
        self.storage_progress_label.setStyleSheet("color: #666; font-style: italic;")
        self.storage_progress_label.hide()
        storage_layout.addWidget(self.storage_progress_label)

        storage_group.setLayout(storage_layout)
        layout.addWidget(storage_group)

        # ========== Delete Vault Management Group ==========
        vault_group = QGroupBox("Delete Vault Management")
        vault_group.setStyleSheet(self.groupbox_style)
        vault_layout = QVBoxLayout()

        vault_desc = QLabel(
            "Manage files in the Delete Vault. These are files that have been soft-deleted "
            "from the archive and can be restored or permanently purged."
        )
        vault_desc.setWordWrap(True)
        vault_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        vault_layout.addWidget(vault_desc)

        # Stats row
        vault_stats_layout = QHBoxLayout()
        self.vault_files_label = QLabel("Files in vault: -")
        self.vault_files_label.setStyleSheet("font-weight: bold;")
        vault_stats_layout.addWidget(self.vault_files_label)

        self.vault_size_label = QLabel("Size: -")
        vault_stats_layout.addWidget(self.vault_size_label)

        vault_stats_layout.addStretch()
        vault_layout.addLayout(vault_stats_layout)

        # Buttons row
        vault_btn_layout = QHBoxLayout()
        self.view_vault_btn = QPushButton("View Vault Contents")
        self.view_vault_btn.setToolTip("Open dialog to view and manage deleted files")
        self.view_vault_btn.clicked.connect(self.on_view_vault_contents)
        vault_btn_layout.addWidget(self.view_vault_btn)

        self.purge_vault_btn = QPushButton("Permanently Purge Vault")
        self.purge_vault_btn.setToolTip("Permanently delete ALL files in the Delete Vault")
        self.purge_vault_btn.clicked.connect(self.on_purge_vault)
        self.purge_vault_btn.setStyleSheet("background-color: #d32f2f; color: white;")
        vault_btn_layout.addWidget(self.purge_vault_btn)

        self.refresh_vault_btn = QPushButton("Refresh")
        self.refresh_vault_btn.clicked.connect(self.refresh_vault_stats)
        vault_btn_layout.addWidget(self.refresh_vault_btn)

        vault_btn_layout.addStretch()
        vault_layout.addLayout(vault_btn_layout)

        vault_group.setLayout(vault_layout)
        layout.addWidget(vault_group)

        # Add stretch at bottom
        layout.addStretch()

        main_widget.setLayout(layout)
        scroll.setWidget(main_widget)

        # Set the scroll area as the main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ========== Database Connection ==========

    def set_database(self, db_metadata, album_manager=None):
        """
        Set the database metadata and album manager.

        Args:
            db_metadata: DatabaseMetadata instance
            album_manager: AlbumManager instance (optional)
        """
        self.db_metadata = db_metadata
        self.album_manager = album_manager

        if db_metadata:
            self.load_backup_info()
            self.refresh_database_stats()
            self.refresh_vault_stats()

    # ========== Archive Backup Methods ==========

    def load_backup_info(self):
        """Load backup location and last backup info from database."""
        if not self.db_metadata:
            return

        # Load backup location
        backup_location = self.db_metadata.get_backup_location()
        if backup_location:
            self.backup_location_edit.setText(backup_location)
        else:
            self.backup_location_edit.clear()
            self.backup_location_edit.setPlaceholderText("Not configured - click Browse to set")

        # Load last backup info
        backup_info = self.db_metadata.get_last_backup_info()
        if backup_info and backup_info.get('timestamp'):
            timestamp = backup_info['timestamp']
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted = dt.strftime("%B %d, %Y at %I:%M %p").replace(" 0", " ")
                self.last_backup_label.setText(f"Last Backup: {formatted}")
            except:
                self.last_backup_label.setText(f"Last Backup: {timestamp}")

            status = backup_info.get('status', 'unknown')
            if status == 'success':
                self.backup_status_label.setText("| Status: Success")
                self.backup_status_label.setStyleSheet("color: green;")
            elif status == 'failed':
                self.backup_status_label.setText("| Status: Failed")
                self.backup_status_label.setStyleSheet("color: red;")
            elif status == 'cancelled':
                self.backup_status_label.setText("| Status: Cancelled")
                self.backup_status_label.setStyleSheet("color: orange;")
            else:
                self.backup_status_label.setText("")
        else:
            self.last_backup_label.setText("Last Backup: Never")
            self.backup_status_label.setText("")

    def on_browse_backup_location(self):
        """Browse for backup location."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        current_path = self.backup_location_edit.text()
        if not current_path:
            current_path = os.path.expanduser("~")

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Backup Directory",
            current_path,
            QFileDialog.ShowDirsOnly
        )

        if directory:
            # Validate and save
            if not os.access(directory, os.W_OK):
                QMessageBox.critical(
                    self, "Permission Denied",
                    f"The selected directory is not writable:\n{directory}"
                )
                return

            success = self.db_metadata.set_backup_location(directory)
            if success:
                self.backup_location_edit.setText(directory)
                logger.info(f"Backup location set: {directory}")

                # Ask if user wants to run backup now
                reply = QMessageBox.question(
                    self, "Run Backup Now?",
                    "Backup location has been set.\n\nWould you like to run a full backup now?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    self.on_run_backup()
            else:
                QMessageBox.critical(
                    self, "Error",
                    "Failed to save backup location. Check logs for details."
                )

    def on_clear_backup_location(self):
        """Clear the backup location."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        if not self.backup_location_edit.text():
            QMessageBox.information(
                self, "No Location Set",
                "No backup location is currently configured."
            )
            return

        reply = QMessageBox.question(
            self, "Clear Backup Location?",
            "Are you sure you want to clear the backup location?\n\n"
            "This will not delete any existing backups.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.db_metadata.set_backup_location(None)
            self.backup_location_edit.clear()
            self.backup_location_edit.setPlaceholderText("Not configured - click Browse to set")
            logger.info("Backup location cleared")

    def on_run_backup(self):
        """Run full backup."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        backup_location = self.backup_location_edit.text()
        if not backup_location:
            QMessageBox.information(
                self, "No Backup Location",
                "Please set a backup location first by clicking 'Browse...'."
            )
            return

        # Check if already running
        if self._backup_worker is not None and self._backup_worker.isRunning():
            QMessageBox.information(
                self, "Backup Running",
                "A backup is already in progress."
            )
            return

        # Confirm backup
        reply = QMessageBox.question(
            self, "Run Full Backup?",
            f"This will create a complete backup of:\n"
            f"• Database file\n"
            f"• Main archive\n"
            f"• Video archive (if configured)\n"
            f"• Prior revisions archive (if configured)\n"
            f"• Delete vault (if configured)\n"
            f"• All album storage locations\n\n"
            f"Backup destination: {backup_location}\n\n"
            f"This may take a while for large archives.\n\n"
            f"Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            return

        # Start backup worker
        self._start_backup()

    def _start_backup(self):
        """Start the backup worker."""
        from ui.archive_backup_worker import ArchiveBackupWorker

        # Gather all locations to backup
        backup_location = self.backup_location_edit.text()
        database_path = self.db_metadata.database_path

        archives_to_backup = self.db_metadata.get_all_archive_locations()

        # Get album storage locations
        albums = []
        if self.album_manager:
            albums = self.album_manager.get_all_albums()

        # Create worker
        self._backup_worker = ArchiveBackupWorker(
            database_path=database_path,
            backup_destination=backup_location,
            archives_to_backup=archives_to_backup,
            albums=albums
        )

        # Connect signals
        self._backup_worker.progress_update.connect(self._on_backup_progress)
        self._backup_worker.stage_update.connect(self._on_backup_stage)
        self._backup_worker.status_update.connect(self._on_backup_status)
        self._backup_worker.completed.connect(self._on_backup_completed)
        self._backup_worker.error_occurred.connect(self._on_backup_error)

        # Update UI
        self.run_backup_btn.setEnabled(False)
        self.cancel_backup_btn.show()
        self.backup_progress.show()
        self.backup_progress.setValue(0)
        self.backup_progress_label.show()
        self.backup_progress_label.setText("Starting backup...")

        # Start worker
        self._backup_worker.start()

    def on_cancel_backup(self):
        """Cancel running backup."""
        if self._backup_worker and self._backup_worker.isRunning():
            self._backup_worker.stop()
            self.backup_progress_label.setText("Cancelling...")

    def _on_backup_progress(self, current, total, filename):
        """Handle backup progress update."""
        if total > 0:
            percent = int((current / total) * 100)
            self.backup_progress.setValue(percent)
            self.backup_progress_label.setText(f"Copying {current}/{total}: {filename}")

    def _on_backup_stage(self, stage):
        """Handle backup stage change."""
        self.backup_progress_label.setText(stage)

    def _on_backup_status(self, message):
        """Handle backup status update."""
        self.backup_progress_label.setText(message)

    def _on_backup_completed(self, results):
        """Handle backup completion."""
        # Reset UI
        self.run_backup_btn.setEnabled(True)
        self.cancel_backup_btn.hide()
        self.backup_progress.hide()
        self.backup_progress_label.hide()

        status = results.get('status', 'unknown')
        files_copied = results.get('files_copied', 0)
        bytes_copied = results.get('bytes_copied', 0)
        errors = results.get('errors', [])

        # Update database with backup status
        if self.db_metadata:
            timestamp = datetime.now().isoformat()
            self.db_metadata.update_last_backup(timestamp, status)
            self.load_backup_info()

        if status == 'completed':
            size_str = self._format_size(bytes_copied)
            QMessageBox.information(
                self, "Backup Complete",
                f"Backup completed successfully!\n\n"
                f"Files copied: {files_copied:,}\n"
                f"Total size: {size_str}\n"
                f"Location: {results.get('backup_folder', 'N/A')}"
            )
        elif status == 'cancelled':
            QMessageBox.information(
                self, "Backup Cancelled",
                f"Backup was cancelled.\n\n"
                f"Files copied before cancellation: {files_copied:,}"
            )
        else:
            error_summary = "\n".join(errors[:5]) if errors else "Unknown error"
            QMessageBox.critical(
                self, "Backup Failed",
                f"Backup failed.\n\n"
                f"Files copied: {files_copied:,}\n"
                f"Errors:\n{error_summary}"
            )

        self._backup_worker = None

    def _on_backup_error(self, error_msg):
        """Handle backup error."""
        self.run_backup_btn.setEnabled(True)
        self.cancel_backup_btn.hide()
        self.backup_progress.hide()
        self.backup_progress_label.setText(f"Error: {error_msg}")

        QMessageBox.critical(
            self, "Backup Error",
            f"Backup failed:\n\n{error_msg}"
        )

        self._backup_worker = None

    # ========== Database Maintenance Methods ==========

    def refresh_database_stats(self):
        """Refresh database statistics display."""
        if not self.db_metadata:
            return

        stats = self.db_metadata.get_database_stats()
        if stats:
            self.db_size_label.setText(self._format_size(stats.get('database_size', 0)))
            self.wal_size_label.setText(self._format_size(stats.get('wal_size', 0)))
            self.total_records_label.setText(f"{stats.get('total_records', 0):,}")
            self.schema_version_label.setText(str(stats.get('schema_version', 'N/A')))

    def on_check_integrity(self):
        """Run database integrity check."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        self.db_result_label.setText("Running integrity check...")
        self.db_result_label.setStyleSheet("color: #666;")

        # Run integrity check (this is quick, no need for worker)
        passed, message = self.db_metadata.run_integrity_check()

        if passed:
            self.db_result_label.setText(f"Integrity check passed: {message}")
            self.db_result_label.setStyleSheet("color: green;")
            QMessageBox.information(
                self, "Integrity Check Passed",
                f"Database integrity check passed.\n\nResult: {message}"
            )
        else:
            self.db_result_label.setText(f"Integrity check FAILED: {message}")
            self.db_result_label.setStyleSheet("color: red;")
            QMessageBox.critical(
                self, "Integrity Check Failed",
                f"Database integrity check FAILED!\n\nResult: {message}\n\n"
                f"Consider restoring from a backup."
            )

    def on_vacuum_database(self):
        """Run database vacuum."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        reply = QMessageBox.question(
            self, "Vacuum Database?",
            "This will optimize the database file and reclaim unused space.\n\n"
            "The database will be briefly locked during this operation.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            return

        self.db_result_label.setText("Running vacuum...")
        self.db_result_label.setStyleSheet("color: #666;")

        # Get size before
        stats_before = self.db_metadata.get_database_stats()
        size_before = stats_before.get('database_size', 0) if stats_before else 0

        # Run vacuum
        success, bytes_reclaimed = self.db_metadata.vacuum_database()

        if success:
            # Get size after
            stats_after = self.db_metadata.get_database_stats()
            size_after = stats_after.get('database_size', 0) if stats_after else 0
            actual_reclaimed = size_before - size_after

            self.db_result_label.setText(
                f"Vacuum complete. Space reclaimed: {self._format_size(actual_reclaimed)}"
            )
            self.db_result_label.setStyleSheet("color: green;")
            self.refresh_database_stats()

            QMessageBox.information(
                self, "Vacuum Complete",
                f"Database vacuum completed successfully.\n\n"
                f"Size before: {self._format_size(size_before)}\n"
                f"Size after: {self._format_size(size_after)}\n"
                f"Space reclaimed: {self._format_size(actual_reclaimed)}"
            )
        else:
            self.db_result_label.setText("Vacuum failed")
            self.db_result_label.setStyleSheet("color: red;")
            QMessageBox.critical(
                self, "Vacuum Failed",
                "Failed to vacuum database. Check logs for details."
            )

    # ========== Archive Verification Methods ==========

    def on_verify_hashes(self):
        """Start hash verification."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        if self._verification_worker and self._verification_worker.isRunning():
            QMessageBox.information(
                self, "Verification Running",
                "A verification operation is already in progress."
            )
            return

        reply = QMessageBox.question(
            self, "Verify File Hashes?",
            "This will recalculate the hash of every file in the archive and compare "
            "it to the stored hash in the database.\n\n"
            "This can take a long time for large archives.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._start_verification('verify_hashes')

    def on_find_orphaned(self):
        """Start orphan detection."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        if self._verification_worker and self._verification_worker.isRunning():
            QMessageBox.information(
                self, "Verification Running",
                "A verification operation is already in progress."
            )
            return

        reply = QMessageBox.question(
            self, "Find Orphaned Files?",
            "This will scan the archive directories for files that are not tracked "
            "in the database.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            self._start_verification('find_orphaned')

    def on_find_missing(self):
        """Start missing file detection."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        if self._verification_worker and self._verification_worker.isRunning():
            QMessageBox.information(
                self, "Verification Running",
                "A verification operation is already in progress."
            )
            return

        reply = QMessageBox.question(
            self, "Find Missing Files?",
            "This will check every database record to verify the file exists on disk.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply == QMessageBox.Yes:
            self._start_verification('find_missing')

    def _start_verification(self, mode):
        """Start verification worker."""
        from ui.archive_verification_worker import ArchiveVerificationWorker

        archive_location = self.db_metadata.get_archive_location()

        self._verification_worker = ArchiveVerificationWorker(
            database_path=self.db_metadata.database_path,
            archive_location=archive_location,
            verification_mode=mode
        )

        # Connect signals
        self._verification_worker.progress_update.connect(self._on_verification_progress)
        self._verification_worker.status_update.connect(self._on_verification_status)
        self._verification_worker.completed.connect(self._on_verification_completed)
        self._verification_worker.error_occurred.connect(self._on_verification_error)

        # Update UI
        self.verify_hashes_btn.setEnabled(False)
        self.find_orphaned_btn.setEnabled(False)
        self.find_missing_btn.setEnabled(False)
        self.cancel_verify_btn.show()
        self.verify_progress.show()
        self.verify_progress.setValue(0)
        self.verify_progress_label.show()
        self.verify_progress_label.setText("Starting verification...")
        self.verify_results_text.hide()

        self._verification_worker.start()

    def on_cancel_verification(self):
        """Cancel running verification."""
        if self._verification_worker and self._verification_worker.isRunning():
            self._verification_worker.stop()
            self.verify_progress_label.setText("Cancelling...")

    def _on_verification_progress(self, current, total, filename):
        """Handle verification progress."""
        if total > 0:
            percent = int((current / total) * 100)
            self.verify_progress.setValue(percent)
            self.verify_progress_label.setText(f"Checking {current}/{total}: {filename}")

    def _on_verification_status(self, message):
        """Handle verification status update."""
        self.verify_progress_label.setText(message)

    def _on_verification_completed(self, results):
        """Handle verification completion."""
        # Reset UI
        self.verify_hashes_btn.setEnabled(True)
        self.find_orphaned_btn.setEnabled(True)
        self.find_missing_btn.setEnabled(True)
        self.cancel_verify_btn.hide()
        self.verify_progress.hide()

        mode = results.get('mode', 'unknown')
        status = results.get('status', 'unknown')

        if mode == 'verify_hashes':
            verified = results.get('verified', 0)
            mismatches = results.get('mismatches', [])
            missing = results.get('missing', [])

            summary = f"Hash Verification Results:\n"
            summary += f"Files verified: {verified:,}\n"
            summary += f"Hash mismatches: {len(mismatches)}\n"
            summary += f"Missing files: {len(missing)}\n"

            if mismatches:
                summary += f"\nMismatched files:\n"
                for path in mismatches[:10]:
                    summary += f"  - {path}\n"
                if len(mismatches) > 10:
                    summary += f"  ... and {len(mismatches) - 10} more\n"

            if len(mismatches) == 0 and len(missing) == 0:
                self.verify_progress_label.setText("Verification passed - all hashes match!")
                self.verify_progress_label.setStyleSheet("color: green;")
            else:
                self.verify_progress_label.setText(f"Issues found: {len(mismatches)} mismatches, {len(missing)} missing")
                self.verify_progress_label.setStyleSheet("color: red;")

        elif mode == 'find_orphaned':
            orphaned = results.get('orphaned', [])

            summary = f"Orphaned File Detection Results:\n"
            summary += f"Orphaned files found: {len(orphaned)}\n"

            if orphaned:
                summary += f"\nOrphaned files:\n"
                for path in orphaned[:20]:
                    summary += f"  - {path}\n"
                if len(orphaned) > 20:
                    summary += f"  ... and {len(orphaned) - 20} more\n"

            if len(orphaned) == 0:
                self.verify_progress_label.setText("No orphaned files found")
                self.verify_progress_label.setStyleSheet("color: green;")
            else:
                self.verify_progress_label.setText(f"Found {len(orphaned)} orphaned files")
                self.verify_progress_label.setStyleSheet("color: orange;")

        elif mode == 'find_missing':
            missing = results.get('missing', [])

            summary = f"Missing File Detection Results:\n"
            summary += f"Missing files found: {len(missing)}\n"

            if missing:
                summary += f"\nMissing files:\n"
                for path in missing[:20]:
                    summary += f"  - {path}\n"
                if len(missing) > 20:
                    summary += f"  ... and {len(missing) - 20} more\n"

            if len(missing) == 0:
                self.verify_progress_label.setText("No missing files - all records have files on disk")
                self.verify_progress_label.setStyleSheet("color: green;")
            else:
                self.verify_progress_label.setText(f"Found {len(missing)} missing files")
                self.verify_progress_label.setStyleSheet("color: red;")
        else:
            summary = f"Verification completed with status: {status}"

        self.verify_results_text.setText(summary)
        self.verify_results_text.show()
        self._verification_worker = None

    def _on_verification_error(self, error_msg):
        """Handle verification error."""
        self.verify_hashes_btn.setEnabled(True)
        self.find_orphaned_btn.setEnabled(True)
        self.find_missing_btn.setEnabled(True)
        self.cancel_verify_btn.hide()
        self.verify_progress.hide()
        self.verify_progress_label.setText(f"Error: {error_msg}")
        self.verify_progress_label.setStyleSheet("color: red;")

        QMessageBox.critical(
            self, "Verification Error",
            f"Verification failed:\n\n{error_msg}"
        )

        self._verification_worker = None

    # ========== Storage Statistics Methods ==========

    def on_refresh_storage_stats(self):
        """Refresh storage statistics."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        if self._storage_stats_worker and self._storage_stats_worker.isRunning():
            QMessageBox.information(
                self, "Calculation Running",
                "Storage statistics calculation is already in progress."
            )
            return

        self._start_storage_stats()

    def _start_storage_stats(self):
        """Start storage stats worker."""
        from ui.storage_stats_worker import StorageStatsWorker

        # Gather all locations to scan
        locations = self.db_metadata.get_all_archive_locations()
        locations['database'] = self.db_metadata.database_path

        # Add album storage locations
        if self.album_manager:
            albums = self.album_manager.get_all_albums()
            album_locations = {}
            for album in albums:
                loc = album.get('storage_location')
                if loc:
                    album_locations[f"album_{album['id']}"] = loc
            locations['albums'] = album_locations

        self._storage_stats_worker = StorageStatsWorker(locations)

        # Connect signals
        self._storage_stats_worker.progress_update.connect(self._on_storage_progress)
        self._storage_stats_worker.completed.connect(self._on_storage_stats_completed)
        self._storage_stats_worker.error_occurred.connect(self._on_storage_stats_error)

        # Update UI
        self.refresh_storage_btn.setEnabled(False)
        self.cancel_storage_btn.show()
        self.storage_progress_label.show()
        self.storage_progress_label.setText("Calculating storage statistics...")

        self._storage_stats_worker.start()

    def on_cancel_storage_stats(self):
        """Cancel storage stats calculation."""
        if self._storage_stats_worker and self._storage_stats_worker.isRunning():
            self._storage_stats_worker.stop()
            self.storage_progress_label.setText("Cancelling...")

    def _on_storage_progress(self, location):
        """Handle storage stats progress."""
        self.storage_progress_label.setText(f"Scanning: {location}")

    def _on_storage_stats_completed(self, results):
        """Handle storage stats completion."""
        self.refresh_storage_btn.setEnabled(True)
        self.cancel_storage_btn.hide()
        self.storage_progress_label.hide()

        total_size = 0
        total_files = 0

        # Main archive
        main = results.get('main_archive', {})
        self.main_archive_size_label.setText(self._format_size(main.get('size_bytes', 0)))
        self.main_archive_files_label.setText(f"{main.get('file_count', 0):,}")
        total_size += main.get('size_bytes', 0)
        total_files += main.get('file_count', 0)

        # Video archive
        video = results.get('video_archive', {})
        if video.get('path'):
            self.video_archive_size_label.setText(self._format_size(video.get('size_bytes', 0)))
            self.video_archive_files_label.setText(f"{video.get('file_count', 0):,}")
            total_size += video.get('size_bytes', 0)
            total_files += video.get('file_count', 0)
        else:
            self.video_archive_size_label.setText("(not configured)")
            self.video_archive_files_label.setText("-")

        # Prior revisions
        prior = results.get('prior_revision_archive', {})
        if prior.get('path'):
            self.prior_rev_size_label.setText(self._format_size(prior.get('size_bytes', 0)))
            self.prior_rev_files_label.setText(f"{prior.get('file_count', 0):,}")
            total_size += prior.get('size_bytes', 0)
            total_files += prior.get('file_count', 0)
        else:
            self.prior_rev_size_label.setText("(not configured)")
            self.prior_rev_files_label.setText("-")

        # Delete vault
        vault = results.get('delete_vault', {})
        if vault.get('path'):
            self.delete_vault_size_label.setText(self._format_size(vault.get('size_bytes', 0)))
            self.delete_vault_files_label.setText(f"{vault.get('file_count', 0):,}")
            total_size += vault.get('size_bytes', 0)
            total_files += vault.get('file_count', 0)
        else:
            self.delete_vault_size_label.setText("(not configured)")
            self.delete_vault_files_label.setText("-")

        # Albums (aggregated)
        albums = results.get('albums', {})
        album_size = sum(a.get('size_bytes', 0) for a in albums.values())
        album_files = sum(a.get('file_count', 0) for a in albums.values())
        self.albums_size_label.setText(self._format_size(album_size))
        self.albums_files_label.setText(f"{album_files:,}")
        total_size += album_size
        total_files += album_files

        # Database files
        db = results.get('database', {})
        db_size = db.get('size_bytes', 0)
        db_files = db.get('file_count', 0)  # db, wal, shm
        self.database_files_size_label.setText(self._format_size(db_size))
        self.database_files_count_label.setText(f"{db_files}")
        total_size += db_size

        # Totals
        self.total_size_label.setText(self._format_size(total_size))
        self.total_files_label.setText(f"{total_files:,}")

        self._storage_stats_worker = None

    def _on_storage_stats_error(self, error_msg):
        """Handle storage stats error."""
        self.refresh_storage_btn.setEnabled(True)
        self.cancel_storage_btn.hide()
        self.storage_progress_label.setText(f"Error: {error_msg}")
        self.storage_progress_label.setStyleSheet("color: red;")

        self._storage_stats_worker = None

    # ========== Delete Vault Management Methods ==========

    def refresh_vault_stats(self):
        """Refresh delete vault statistics."""
        if not self.db_metadata:
            return

        stats = self.db_metadata.get_delete_vault_stats()
        if stats:
            file_count = stats.get('file_count', 0)
            total_size = stats.get('total_size', 0)

            self.vault_files_label.setText(f"Files in vault: {file_count:,}")
            self.vault_size_label.setText(f"Size: {self._format_size(total_size)}")
        else:
            self.vault_files_label.setText("Files in vault: -")
            self.vault_size_label.setText("Size: -")

    def on_view_vault_contents(self):
        """Open the deleted files dialog."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        # Check if delete vault is configured
        vault_location = self.db_metadata.get_delete_vault_location()
        if not vault_location:
            QMessageBox.information(
                self, "Delete Vault Not Configured",
                "No Delete Vault location is configured.\n\n"
                "You can configure one in the System Settings tab."
            )
            return

        # Import and show the existing dialog
        from ui.deleted_files_dialog import DeletedFilesDialog

        dialog = DeletedFilesDialog(
            parent=self,
            db_metadata=self.db_metadata,
            dialog_logger=logger
        )
        dialog.exec()

        # Refresh stats after dialog closes
        self.refresh_vault_stats()

    def on_purge_vault(self):
        """Permanently purge all files in the delete vault."""
        if not self.db_metadata:
            QMessageBox.information(
                self, "No Database",
                "Please select a database first."
            )
            return

        # Get current stats
        stats = self.db_metadata.get_delete_vault_stats()
        if not stats or stats.get('file_count', 0) == 0:
            QMessageBox.information(
                self, "Vault Empty",
                "The Delete Vault is empty. Nothing to purge."
            )
            return

        file_count = stats.get('file_count', 0)
        total_size = stats.get('total_size', 0)

        # Confirm with strong warning
        reply = QMessageBox.critical(
            self, "PERMANENT DELETION",
            f"⚠️ PERMANENTLY DELETE ALL {file_count:,} files from Delete Vault?\n\n"
            f"Total size: {self._format_size(total_size)}\n\n"
            f"THIS ACTION CANNOT BE UNDONE!\n"
            f"All files will be permanently erased and cannot be recovered.\n\n"
            f"Are you absolutely sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Double confirmation
        reply2 = QMessageBox.warning(
            self, "Final Confirmation",
            f"This is your last chance!\n\n"
            f"Permanently delete all {file_count:,} files?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply2 != QMessageBox.Yes:
            return

        # Perform purge
        files_deleted, bytes_freed = self.db_metadata.purge_delete_vault()

        QMessageBox.information(
            self, "Purge Complete",
            f"Delete Vault purged.\n\n"
            f"Files deleted: {files_deleted:,}\n"
            f"Space freed: {self._format_size(bytes_freed)}"
        )

        # Refresh stats
        self.refresh_vault_stats()

    # ========== Utility Methods ==========

    def _format_size(self, bytes):
        """Format file size in human-readable format."""
        if bytes is None:
            return "-"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} PB"

    def cleanup_workers(self):
        """
        Stop and wait for any running worker threads.

        Called by main window before closing to prevent
        'QThread destroyed while thread is still running' errors.
        """
        if self._backup_worker and self._backup_worker.isRunning():
            logger.info("Stopping backup worker before close...")
            self._backup_worker.stop()
            self._backup_worker.wait()
            logger.info("Backup worker stopped")

        if self._verification_worker and self._verification_worker.isRunning():
            logger.info("Stopping verification worker before close...")
            self._verification_worker.stop()
            self._verification_worker.wait()
            logger.info("Verification worker stopped")

        if self._storage_stats_worker and self._storage_stats_worker.isRunning():
            logger.info("Stopping storage stats worker before close...")
            self._storage_stats_worker.stop()
            self._storage_stats_worker.wait()
            logger.info("Storage stats worker stopped")
