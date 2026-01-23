"""
Bulk Delete Preview Dialog

Preview dialog showing scan results before bulk deletion.
Displays matched files (to be deleted) and not found files in separate tabs.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGroupBox, QGridLayout, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QCloseEvent
import os
import logging

logger = logging.getLogger(__name__)


class BulkDeletePreviewDialog(QDialog):
    """
    Preview dialog showing scan results before deletion.

    Displays:
    - Summary stats (matches, not found, total size)
    - Tab 1: "To Delete" table (Reference File, Archive Path, Size, Hash)
    - Tab 2: "Not in Archive" table (Reference File, Size, Reason)
    """

    delete_confirmed = Signal(list)  # Emits list of files to delete

    def __init__(self, parent=None, reference_folder="", scan_results=None):
        """
        Initialize preview dialog.

        Args:
            parent: Parent widget
            reference_folder: Path to reference folder
            scan_results: Results from scan phase
        """
        super().__init__(parent)
        self.reference_folder = reference_folder
        self.scan_results = scan_results or {}
        self.worker = None

        self.setWindowTitle("Bulk Delete Preview")
        self.setMinimumSize(900, 600)
        self.resize(1000, 700)

        self._init_ui()
        self._populate_data()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Header with reference folder
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Reference Folder:"))
        folder_label = QLabel(self.reference_folder)
        folder_label.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(folder_label, stretch=1)
        layout.addLayout(header_layout)

        # Summary stats group
        stats_group = QGroupBox("Summary")
        stats_layout = QGridLayout()

        stats_layout.addWidget(QLabel("Files in reference folder:"), 0, 0)
        self._total_label = QLabel("-")
        self._total_label.setStyleSheet("font-weight: bold;")
        stats_layout.addWidget(self._total_label, 0, 1)

        stats_layout.addWidget(QLabel("Matched in archive:"), 0, 2)
        self._matched_label = QLabel("-")
        self._matched_label.setStyleSheet("font-weight: bold; color: green;")
        stats_layout.addWidget(self._matched_label, 0, 3)

        stats_layout.addWidget(QLabel("Not in archive:"), 1, 0)
        self._not_found_label = QLabel("-")
        self._not_found_label.setStyleSheet("font-weight: bold; color: gray;")
        stats_layout.addWidget(self._not_found_label, 1, 1)

        stats_layout.addWidget(QLabel("Total size to delete:"), 1, 2)
        self._size_label = QLabel("-")
        self._size_label.setStyleSheet("font-weight: bold; color: red;")
        stats_layout.addWidget(self._size_label, 1, 3)

        stats_layout.setColumnStretch(4, 1)
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Tab widget for tables
        self._tabs = QTabWidget()

        # To Delete tab
        self._delete_table = QTableWidget()
        self._delete_table.setColumnCount(4)
        self._delete_table.setHorizontalHeaderLabels([
            "Reference File", "Archive Path", "Size", "Hash"
        ])
        self._delete_table.setAlternatingRowColors(True)
        self._delete_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._delete_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header = self._delete_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self._tabs.addTab(self._delete_table, "To Delete (0)")

        # Not Found tab
        self._not_found_table = QTableWidget()
        self._not_found_table.setColumnCount(3)
        self._not_found_table.setHorizontalHeaderLabels([
            "Reference File", "Size", "Reason"
        ])
        self._not_found_table.setAlternatingRowColors(True)
        self._not_found_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._not_found_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        header2 = self._not_found_table.horizontalHeader()
        header2.setSectionResizeMode(0, QHeaderView.Stretch)
        header2.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header2.setSectionResizeMode(2, QHeaderView.Stretch)
        self._tabs.addTab(self._not_found_table, "Not in Archive (0)")

        layout.addWidget(self._tabs, stretch=1)

        # Button row
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)

        self._delete_btn = QPushButton("Delete Matched Files")
        self._delete_btn.setStyleSheet(
            "background-color: #d32f2f; color: white; font-weight: bold; padding: 8px 16px;"
        )
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        button_layout.addWidget(self._delete_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _populate_data(self):
        """Populate tables with scan results."""
        matched_files = self.scan_results.get('matched_files', [])
        not_found_files = self.scan_results.get('not_found_files', [])
        total_reference = self.scan_results.get('total_reference', 0)
        total_matched = self.scan_results.get('total_matched', 0)
        total_not_found = self.scan_results.get('total_not_found', 0)
        total_matched_size = self.scan_results.get('total_matched_size', 0)

        # Update labels
        self._total_label.setText(f"{total_reference:,}")
        self._matched_label.setText(f"{total_matched:,}")
        self._not_found_label.setText(f"{total_not_found:,}")
        self._size_label.setText(self._format_size(total_matched_size))

        # Update tab titles
        self._tabs.setTabText(0, f"To Delete ({total_matched:,})")
        self._tabs.setTabText(1, f"Not in Archive ({total_not_found:,})")

        # Populate To Delete table
        self._delete_table.setRowCount(len(matched_files))
        for row, file_info in enumerate(matched_files):
            ref_path = file_info.get('reference_path', '')
            archive_path = file_info.get('archive_path', '')
            file_size = file_info.get('file_size', 0)
            file_hash = file_info.get('file_hash', '')

            self._delete_table.setItem(row, 0, QTableWidgetItem(os.path.basename(ref_path)))
            self._delete_table.item(row, 0).setToolTip(ref_path)

            self._delete_table.setItem(row, 1, QTableWidgetItem(archive_path))
            self._delete_table.item(row, 1).setToolTip(archive_path)

            self._delete_table.setItem(row, 2, QTableWidgetItem(self._format_size(file_size)))

            hash_display = file_hash[:12] + "..." if len(file_hash) > 12 else file_hash
            self._delete_table.setItem(row, 3, QTableWidgetItem(hash_display))
            self._delete_table.item(row, 3).setToolTip(file_hash)

        # Populate Not Found table
        self._not_found_table.setRowCount(len(not_found_files))
        for row, file_info in enumerate(not_found_files):
            ref_path = file_info.get('reference_path', '')
            file_size = file_info.get('file_size', 0)
            reason = file_info.get('reason', 'Not in archive')

            self._not_found_table.setItem(row, 0, QTableWidgetItem(os.path.basename(ref_path)))
            self._not_found_table.item(row, 0).setToolTip(ref_path)

            size_str = self._format_size(file_size) if file_size else "-"
            self._not_found_table.setItem(row, 1, QTableWidgetItem(size_str))

            self._not_found_table.setItem(row, 2, QTableWidgetItem(reason))

        # Disable delete button if no matches
        if total_matched == 0:
            self._delete_btn.setEnabled(False)
            self._delete_btn.setText("No Files to Delete")
            self._delete_btn.setStyleSheet(
                "background-color: #cccccc; color: #666666; padding: 8px 16px;"
            )

    def _on_delete_clicked(self):
        """Handle delete button click - show confirmation."""
        matched_files = self.scan_results.get('matched_files', [])
        total_matched = len(matched_files)
        total_size = self.scan_results.get('total_matched_size', 0)

        # Confirmation dialog
        reply = QMessageBox.warning(
            self,
            "Confirm Deletion",
            f"Delete {total_matched:,} files from the archive?\n\n"
            f"Total size: {self._format_size(total_size)}\n\n"
            f"Files will be moved to the Delete Vault and can be restored if needed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.delete_confirmed.emit(matched_files)
            self.accept()

    def _format_size(self, bytes_val):
        """Format file size in human-readable format."""
        if bytes_val is None:
            return "-"
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_val < 1024.0:
                return f"{bytes_val:.1f} {unit}"
            bytes_val /= 1024.0
        return f"{bytes_val:.1f} PB"

    def closeEvent(self, event: QCloseEvent):
        """Handle dialog close - ensure worker thread is properly stopped."""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        event.accept()
