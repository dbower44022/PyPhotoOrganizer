"""
Deleted Files Dialog

Dialog for viewing and restoring files from the Delete Vault.
"""

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QTableWidget, QTableWidgetItem,
                               QHeaderView, QMessageBox, QProgressDialog,
                               QCheckBox, QGroupBox, QAbstractItemView)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class DeletedFilesDialog(QDialog):
    """Dialog for viewing and restoring deleted files."""

    def __init__(self, parent, db_metadata, dialog_logger):
        """
        Initialize deleted files dialog.

        Args:
            parent: Parent widget
            db_metadata: DatabaseMetadata instance
            dialog_logger: Logger instance
        """
        super().__init__(parent)
        self.parent_widget = parent
        self.db_metadata = db_metadata
        self.dialog_logger = dialog_logger
        self.deleted_files = []
        self.restore_worker = None
        self.init_ui()
        self.load_deleted_files()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Deleted Files")
        self.setMinimumSize(900, 600)
        self.setModal(True)

        layout = QVBoxLayout()

        # Header
        header = QLabel("Files in Delete Vault")
        header.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        layout.addWidget(header)

        # Filter options
        filter_group = QGroupBox("Filter")
        filter_layout = QHBoxLayout()

        self.show_restored_check = QCheckBox("Show Restored Files")
        self.show_restored_check.stateChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.show_restored_check)

        filter_layout.addStretch()
        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Select", "Filename", "Original Path", "Deletion Date",
            "Size", "Creation Date", "Status"
        ])

        # Set column widths
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Select
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Filename
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Original Path
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Deletion Date
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Size
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Creation Date
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Status

        self.table.setColumnWidth(0, 50)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)

        layout.addWidget(self.table)

        # Statistics
        self.stats_label = QLabel("Total: 0 files")
        self.stats_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self.stats_label)

        # Buttons
        button_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(self.deselect_all_btn)

        button_layout.addStretch()

        self.restore_btn = QPushButton("Restore Selected")
        self.restore_btn.clicked.connect(self.on_restore_selected)
        self.restore_btn.setEnabled(False)
        button_layout.addWidget(self.restore_btn)

        self.permanently_delete_btn = QPushButton("Permanently Delete Selected")
        self.permanently_delete_btn.clicked.connect(self.on_permanently_delete)
        self.permanently_delete_btn.setEnabled(False)
        self.permanently_delete_btn.setStyleSheet("background-color: #d32f2f; color: white;")
        button_layout.addWidget(self.permanently_delete_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Connect table selection changed
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

    def load_deleted_files(self):
        """Load deleted files from database."""
        include_restored = self.show_restored_check.isChecked()
        self.deleted_files = self.db_metadata.get_deleted_files(include_restored=include_restored)

        self.populate_table()
        self.update_stats()

    def on_filter_changed(self):
        """Handle filter change."""
        self.load_deleted_files()

    def populate_table(self):
        """Populate table with deleted files."""
        self.table.setRowCount(0)

        for record in self.deleted_files:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Checkbox
            checkbox = QTableWidgetItem()
            checkbox.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
            checkbox.setCheckState(Qt.Unchecked)
            self.table.setItem(row, 0, checkbox)

            # Filename
            filename = os.path.basename(record.get('original_archive_path', 'Unknown'))
            filename_item = QTableWidgetItem(filename)
            filename_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 1, filename_item)

            # Original path
            orig_path = record.get('original_archive_path', '-')
            orig_item = QTableWidgetItem(orig_path)
            orig_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 2, orig_item)

            # Deletion date
            deletion_date = record.get('deletion_timestamp', '-')
            if deletion_date != '-':
                try:
                    dt = datetime.fromisoformat(deletion_date)
                    deletion_date = dt.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            date_item = QTableWidgetItem(deletion_date)
            date_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 3, date_item)

            # File size
            size = record.get('file_size', 0)
            size_str = self._format_size(size) if size else '-'
            size_item = QTableWidgetItem(size_str)
            size_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 4, size_item)

            # Creation date
            creation_date = record.get('creation_date', '-')
            creation_item = QTableWidgetItem(creation_date)
            creation_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.table.setItem(row, 5, creation_item)

            # Status
            is_restored = record.get('is_restored', 0)
            status = "Restored" if is_restored else "In Vault"
            status_item = QTableWidgetItem(status)
            status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if is_restored:
                status_item.setForeground(Qt.blue)
            self.table.setItem(row, 6, status_item)

    def update_stats(self):
        """Update statistics label."""
        total = len(self.deleted_files)
        restored = sum(1 for r in self.deleted_files if r.get('is_restored'))
        in_vault = total - restored

        self.stats_label.setText(f"Total: {total} files | In Vault: {in_vault} | Restored: {restored}")

    def on_selection_changed(self):
        """Handle selection change - enable/disable buttons."""
        selected_rows = self.get_selected_rows()
        has_selection = len(selected_rows) > 0

        self.restore_btn.setEnabled(has_selection)
        self.permanently_delete_btn.setEnabled(has_selection)

    def get_selected_rows(self):
        """Get list of selected row indices."""
        selected = []
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox and checkbox.checkState() == Qt.Checked:
                selected.append(row)
        return selected

    def get_selected_records(self):
        """Get list of selected file records."""
        selected_rows = self.get_selected_rows()
        return [self.deleted_files[row] for row in selected_rows if row < len(self.deleted_files)]

    def select_all(self):
        """Select all files."""
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox:
                checkbox.setCheckState(Qt.Checked)

    def deselect_all(self):
        """Deselect all files."""
        for row in range(self.table.rowCount()):
            checkbox = self.table.item(row, 0)
            if checkbox:
                checkbox.setCheckState(Qt.Unchecked)

    def on_restore_selected(self):
        """Restore selected files from Delete Vault to archive."""
        selected_records = self.get_selected_records()

        if not selected_records:
            QMessageBox.warning(self, "No Selection",
                              "Please select files to restore.")
            return

        # Filter out already restored files
        to_restore = [r for r in selected_records if not r.get('is_restored')]

        if not to_restore:
            QMessageBox.information(self, "Already Restored",
                                  "All selected files have already been restored.")
            return

        # Confirm
        count = len(to_restore)
        reply = QMessageBox.question(
            self, "Confirm Restore",
            f"Restore {count} file(s) from Delete Vault to archive?\n\n"
            f"Files will be moved back to their original archive locations.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Create and start restore worker
        from ui.restore_worker import RestoreWorker

        self.restore_worker = RestoreWorker(
            to_restore,
            self.db_metadata,
            self.dialog_logger
        )

        # Show progress dialog
        progress_dialog = QProgressDialog(
            "Restoring files...", "Cancel", 0, count, self
        )
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.setMinimumDuration(0)

        self.restore_worker.progress.connect(
            lambda cur, total, fname: progress_dialog.setValue(cur)
        )
        self.restore_worker.finished.connect(
            lambda results: self._on_restore_finished(results, progress_dialog)
        )

        self.restore_worker.start()

    def _on_restore_finished(self, results, progress_dialog):
        """Handle restore completion."""
        progress_dialog.close()

        success_count = results.get('success', 0)
        errors = results.get('errors', [])

        if errors:
            error_msg = "\n".join([f"- {e}" for e in errors[:10]])
            QMessageBox.warning(
                self, "Restore Complete with Errors",
                f"Successfully restored: {success_count}\n"
                f"Failed: {len(errors)}\n\n"
                f"First errors:\n{error_msg}"
            )

        # Reload data
        self.load_deleted_files()

    def on_permanently_delete(self):
        """Permanently delete selected files from Delete Vault."""
        selected_records = self.get_selected_records()

        if not selected_records:
            QMessageBox.warning(self, "No Selection",
                              "Please select files to permanently delete.")
            return

        # Confirm with strong warning
        count = len(selected_records)
        reply = QMessageBox.critical(
            self, "PERMANENT DELETION",
            f"⚠️ PERMANENTLY DELETE {count} file(s) from Delete Vault?\n\n"
            f"THIS ACTION CANNOT BE UNDONE!\n"
            f"Files will be erased from disk and cannot be recovered.\n\n"
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
            f"Delete {count} file(s) permanently?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply2 != QMessageBox.Yes:
            return

        # Perform permanent deletion
        success_count = 0
        errors = []

        for record in selected_records:
            vault_path = record.get('delete_vault_path')
            file_hash = record.get('file_hash')
            filename = os.path.basename(vault_path) if vault_path else 'Unknown'

            try:
                # Delete file from vault
                if vault_path and os.path.exists(vault_path):
                    os.remove(vault_path)
                    self.dialog_logger.info(f"✓ Permanently deleted: {vault_path}")

                # Delete database record
                self.db_metadata.delete_deleted_file_record(file_hash)

                success_count += 1

            except Exception as e:
                error_msg = f"{filename}: {str(e)}"
                self.dialog_logger.error(f"✗ Failed to permanently delete: {e}", exc_info=True)
                errors.append(error_msg)

        # Show results
        if errors:
            error_msg = "\n".join([f"- {e}" for e in errors[:10]])
            QMessageBox.warning(
                self, "Deletion Complete with Errors",
                f"Successfully deleted: {success_count}\n"
                f"Failed: {len(errors)}\n\n"
                f"First errors:\n{error_msg}"
            )
        else:
            QMessageBox.information(
                self, "Deletion Complete",
                f"Successfully deleted {success_count} file(s) permanently."
            )

        # Reload data
        self.load_deleted_files()

    def _format_size(self, bytes):
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close - ensure worker thread is properly stopped."""
        if self.restore_worker and self.restore_worker.isRunning():
            self.dialog_logger.info("Stopping restore worker before dialog close...")
            self.restore_worker.cancel()
            self.restore_worker.wait()  # Wait for thread to finish
            self.dialog_logger.info("Restore worker stopped")
        event.accept()
