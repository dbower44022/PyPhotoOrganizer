#!/usr/bin/env python3
"""
Content Hash Test GUI

A graphical interface for testing content hash calculation and duplicate detection.
Allows easy folder selection, displays results in a table, and highlights duplicates.

Usage:
    python tests/content_hash_test_gui.py
"""

import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from collections import defaultdict

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTableWidget, QTableWidgetItem,
    QProgressBar, QGroupBox, QCheckBox, QMessageBox, QHeaderView,
    QSplitter, QTextEdit, QStatusBar
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor, QBrush, QFont

from DuplicateFileDetection import hash_image_content

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Supported image extensions
IMAGE_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif',
    '.webp', '.heic', '.heif', '.raw', '.cr2', '.nef', '.arw'
}

# Video extensions to skip
VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.avi', '.mkv', '.m4v', '.mpg', '.mpeg', '.wmv'
}

# Colors for duplicate groups (cycling through these)
DUPLICATE_COLORS = [
    QColor('#FFE4E1'),  # Misty Rose
    QColor('#E0FFFF'),  # Light Cyan
    QColor('#FFFACD'),  # Lemon Chiffon
    QColor('#E6E6FA'),  # Lavender
    QColor('#F0FFF0'),  # Honeydew
    QColor('#FFF0F5'),  # Lavender Blush
    QColor('#F5FFFA'),  # Mint Cream
    QColor('#FFEFD5'),  # Papaya Whip
]


class ContentHashWorker(QThread):
    """Worker thread for calculating content hashes."""

    progress = Signal(int, int, str)  # current, total, filename
    file_processed = Signal(str, str, int)  # path, hash, size
    completed = Signal(dict)  # results
    error = Signal(str)

    def __init__(self, folder_path: str, recursive: bool = False):
        super().__init__()
        self.folder_path = folder_path
        self.recursive = recursive
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            # Scan for images
            image_files = self._scan_folder()

            if not image_files:
                self.completed.emit({
                    'files': [],
                    'duplicates': {},
                    'total': 0,
                    'successful': 0,
                    'failed': 0
                })
                return

            # Calculate hashes
            results = []
            hash_to_files = defaultdict(list)
            successful = 0
            failed = 0

            for idx, file_path in enumerate(image_files):
                if self._should_stop:
                    break

                filename = os.path.basename(file_path)
                self.progress.emit(idx + 1, len(image_files), filename)

                try:
                    file_size = os.path.getsize(file_path)
                    content_hash = hash_image_content(file_path)

                    result = {
                        'path': file_path,
                        'filename': filename,
                        'size': file_size,
                        'hash': content_hash
                    }
                    results.append(result)

                    if content_hash:
                        hash_to_files[content_hash].append(file_path)
                        successful += 1
                    else:
                        failed += 1

                    self.file_processed.emit(file_path, content_hash or '', file_size)

                except Exception as e:
                    logger.error(f"Error processing {file_path}: {e}")
                    results.append({
                        'path': file_path,
                        'filename': filename,
                        'size': 0,
                        'hash': None,
                        'error': str(e)
                    })
                    failed += 1

            # Find duplicates
            duplicates = {
                h: files for h, files in hash_to_files.items()
                if len(files) > 1
            }

            self.completed.emit({
                'files': results,
                'duplicates': duplicates,
                'total': len(image_files),
                'successful': successful,
                'failed': failed
            })

        except Exception as e:
            logger.error(f"Worker error: {e}", exc_info=True)
            self.error.emit(str(e))

    def _scan_folder(self) -> List[str]:
        """Scan folder for image files."""
        image_files = []
        folder = Path(self.folder_path)

        if self.recursive:
            pattern = '**/*'
        else:
            pattern = '*'

        for file_path in folder.glob(pattern):
            if self._should_stop:
                break
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext in IMAGE_EXTENSIONS:
                    image_files.append(str(file_path))

        return sorted(image_files)


class ContentHashTestGUI(QMainWindow):
    """Main GUI window for content hash testing."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.results = None

        self.setWindowTitle("Content Hash Test Tool")
        self.resize(1000, 700)

        self._create_ui()
        self._create_status_bar()

    def _create_ui(self):
        """Create the user interface."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Folder selection group
        folder_group = QGroupBox("Test Folder")
        folder_layout = QHBoxLayout(folder_group)

        self.folder_label = QLabel("No folder selected")
        self.folder_label.setMinimumWidth(400)
        folder_layout.addWidget(self.folder_label)

        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self._browse_folder)
        folder_layout.addWidget(self.browse_btn)

        self.recursive_check = QCheckBox("Include subfolders")
        folder_layout.addWidget(self.recursive_check)

        folder_layout.addStretch()
        layout.addWidget(folder_group)

        # Action buttons
        action_layout = QHBoxLayout()

        self.run_btn = QPushButton("Run Test")
        self.run_btn.setEnabled(False)
        self.run_btn.clicked.connect(self._run_test)
        self.run_btn.setMinimumWidth(120)
        action_layout.addWidget(self.run_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_test)
        action_layout.addWidget(self.cancel_btn)

        action_layout.addSpacing(20)

        self.export_btn = QPushButton("Export Results...")
        self.export_btn.setEnabled(False)
        self.export_btn.clicked.connect(self._export_results)
        action_layout.addWidget(self.export_btn)

        action_layout.addStretch()
        layout.addLayout(action_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.progress_label = QLabel("")
        self.progress_label.setVisible(False)
        layout.addWidget(self.progress_label)

        # Results splitter
        splitter = QSplitter(Qt.Vertical)

        # Results table
        table_group = QGroupBox("Results")
        table_layout = QVBoxLayout(table_group)

        self.results_table = QTableWidget()
        self.results_table.setColumnCount(4)
        self.results_table.setHorizontalHeaderLabels([
            "Filename", "Content Hash", "File Size", "Status"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.results_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.results_table.setSortingEnabled(True)
        self.results_table.itemSelectionChanged.connect(self._on_selection_changed)
        table_layout.addWidget(self.results_table)

        splitter.addWidget(table_group)

        # Summary and details
        bottom_widget = QWidget()
        bottom_layout = QHBoxLayout(bottom_widget)

        # Summary group
        summary_group = QGroupBox("Summary")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_label = QLabel("No test run yet")
        self.summary_label.setAlignment(Qt.AlignTop)
        summary_layout.addWidget(self.summary_label)

        bottom_layout.addWidget(summary_group)

        # Duplicates group
        dup_group = QGroupBox("Duplicate Groups")
        dup_layout = QVBoxLayout(dup_group)

        self.duplicates_text = QTextEdit()
        self.duplicates_text.setReadOnly(True)
        self.duplicates_text.setMinimumHeight(100)
        dup_layout.addWidget(self.duplicates_text)

        bottom_layout.addWidget(dup_group)

        splitter.addWidget(bottom_widget)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        layout.addWidget(splitter)

    def _create_status_bar(self):
        """Create status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready - Select a folder to test")

    def _browse_folder(self):
        """Open folder browser dialog."""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Test Folder",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly
        )

        if folder:
            self.folder_label.setText(folder)
            self.run_btn.setEnabled(True)
            self.status_bar.showMessage(f"Selected: {folder}")

    def _run_test(self):
        """Start the content hash test."""
        folder = self.folder_label.text()
        if folder == "No folder selected":
            QMessageBox.warning(self, "No Folder", "Please select a folder first.")
            return

        # Clear previous results
        self.results_table.setRowCount(0)
        self.summary_label.setText("Running test...")
        self.duplicates_text.clear()
        self.results = None

        # Update UI state
        self.run_btn.setEnabled(False)
        self.browse_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.progress_label.setVisible(True)

        # Create and start worker
        self.worker = ContentHashWorker(
            folder,
            recursive=self.recursive_check.isChecked()
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.file_processed.connect(self._on_file_processed)
        self.worker.completed.connect(self._on_completed)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        self.status_bar.showMessage("Scanning folder...")

    def _cancel_test(self):
        """Cancel the running test."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.status_bar.showMessage("Cancelling...")

    def _on_progress(self, current: int, total: int, filename: str):
        """Handle progress update."""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(f"Processing {current}/{total}: {filename}")

    def _on_file_processed(self, path: str, hash_val: str, size: int):
        """Handle file processed - add to table."""
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)

        filename = os.path.basename(path)

        # Filename
        item = QTableWidgetItem(filename)
        item.setData(Qt.UserRole, path)  # Store full path
        item.setToolTip(path)
        self.results_table.setItem(row, 0, item)

        # Hash
        if hash_val:
            hash_item = QTableWidgetItem(hash_val[:16] + "...")
            hash_item.setToolTip(hash_val)
            hash_item.setData(Qt.UserRole, hash_val)
        else:
            hash_item = QTableWidgetItem("FAILED")
            hash_item.setForeground(QBrush(QColor('red')))
        self.results_table.setItem(row, 1, hash_item)

        # Size
        size_str = self._format_size(size)
        size_item = QTableWidgetItem(size_str)
        size_item.setData(Qt.UserRole, size)  # For sorting
        self.results_table.setItem(row, 2, size_item)

        # Status (will be updated when duplicates are found)
        status_item = QTableWidgetItem("OK" if hash_val else "Failed")
        if not hash_val:
            status_item.setForeground(QBrush(QColor('red')))
        self.results_table.setItem(row, 3, status_item)

    def _on_completed(self, results: dict):
        """Handle test completion."""
        self.results = results

        # Update UI state
        self.run_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.export_btn.setEnabled(True)

        # Update summary
        total = results['total']
        successful = results['successful']
        failed = results['failed']
        duplicates = results['duplicates']
        dup_count = len(duplicates)
        dup_files = sum(len(files) for files in duplicates.values())

        summary = f"""Files scanned: {total}
Successfully hashed: {successful}
Failed to hash: {failed}

Duplicate groups: {dup_count}
Total duplicate files: {dup_files}"""

        self.summary_label.setText(summary)

        # Highlight duplicates in table
        self._highlight_duplicates(duplicates)

        # Update duplicates text
        if duplicates:
            dup_text = ""
            for idx, (hash_val, files) in enumerate(duplicates.items(), 1):
                dup_text += f"Group {idx} (hash: {hash_val[:16]}...):\n"
                for f in files:
                    dup_text += f"  - {os.path.basename(f)}\n"
                dup_text += "\n"
            self.duplicates_text.setText(dup_text)
        else:
            self.duplicates_text.setText("No duplicates found.")

        # Status message
        if dup_count > 0:
            self.status_bar.showMessage(
                f"Test complete: {total} files, {dup_count} duplicate groups found"
            )
        else:
            self.status_bar.showMessage(
                f"Test complete: {total} files, no duplicates found"
            )

        self.worker = None

    def _highlight_duplicates(self, duplicates: Dict[str, List[str]]):
        """Highlight duplicate rows in table with colors."""
        if not duplicates:
            return

        # Build hash -> color mapping
        hash_colors = {}
        for idx, hash_val in enumerate(duplicates.keys()):
            hash_colors[hash_val] = DUPLICATE_COLORS[idx % len(DUPLICATE_COLORS)]

        # Update table rows
        for row in range(self.results_table.rowCount()):
            hash_item = self.results_table.item(row, 1)
            if hash_item:
                full_hash = hash_item.data(Qt.UserRole)
                if full_hash in hash_colors:
                    color = hash_colors[full_hash]
                    for col in range(self.results_table.columnCount()):
                        item = self.results_table.item(row, col)
                        if item:
                            item.setBackground(QBrush(color))

                    # Update status
                    status_item = self.results_table.item(row, 3)
                    if status_item:
                        status_item.setText("DUPLICATE")
                        status_item.setForeground(QBrush(QColor('#9966CC')))
                        font = status_item.font()
                        font.setBold(True)
                        status_item.setFont(font)

    def _on_error(self, error_msg: str):
        """Handle worker error."""
        self.run_btn.setEnabled(True)
        self.browse_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)

        QMessageBox.critical(self, "Error", f"Test failed:\n{error_msg}")
        self.status_bar.showMessage(f"Error: {error_msg}")

        self.worker = None

    def _on_selection_changed(self):
        """Handle table selection change."""
        selected = self.results_table.selectedItems()
        if selected:
            row = selected[0].row()
            path_item = self.results_table.item(row, 0)
            if path_item:
                path = path_item.data(Qt.UserRole)
                self.status_bar.showMessage(f"Selected: {path}")

    def _export_results(self):
        """Export results to file."""
        if not self.results:
            QMessageBox.information(self, "No Results", "No results to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Results",
            "content_hash_results.txt",
            "Text Files (*.txt);;CSV Files (*.csv);;JSON Files (*.json)"
        )

        if not file_path:
            return

        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.json':
                self._export_json(file_path)
            elif ext == '.csv':
                self._export_csv(file_path)
            else:
                self._export_text(file_path)

            QMessageBox.information(
                self, "Export Complete",
                f"Results exported to:\n{file_path}"
            )

        except Exception as e:
            QMessageBox.critical(
                self, "Export Error",
                f"Failed to export results:\n{e}"
            )

    def _export_text(self, file_path: str):
        """Export results as text."""
        with open(file_path, 'w') as f:
            f.write("CONTENT HASH TEST RESULTS\n")
            f.write("=" * 70 + "\n\n")

            f.write(f"Folder: {self.folder_label.text()}\n")
            f.write(f"Files scanned: {self.results['total']}\n")
            f.write(f"Successful: {self.results['successful']}\n")
            f.write(f"Failed: {self.results['failed']}\n")
            f.write(f"Duplicate groups: {len(self.results['duplicates'])}\n\n")

            f.write("-" * 70 + "\n")
            f.write("ALL FILES\n")
            f.write("-" * 70 + "\n\n")

            for file_info in self.results['files']:
                f.write(f"File: {file_info['filename']}\n")
                f.write(f"  Path: {file_info['path']}\n")
                f.write(f"  Size: {self._format_size(file_info['size'])}\n")
                f.write(f"  Hash: {file_info['hash'] or 'FAILED'}\n\n")

            if self.results['duplicates']:
                f.write("-" * 70 + "\n")
                f.write("DUPLICATE GROUPS\n")
                f.write("-" * 70 + "\n\n")

                for idx, (hash_val, files) in enumerate(self.results['duplicates'].items(), 1):
                    f.write(f"Group {idx} (hash: {hash_val}):\n")
                    for fp in files:
                        f.write(f"  - {fp}\n")
                    f.write("\n")

    def _export_csv(self, file_path: str):
        """Export results as CSV."""
        import csv

        with open(file_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Filename', 'Path', 'Size', 'Content Hash', 'Is Duplicate'])

            dup_hashes = set(self.results['duplicates'].keys())

            for file_info in self.results['files']:
                is_dup = file_info['hash'] in dup_hashes if file_info['hash'] else False
                writer.writerow([
                    file_info['filename'],
                    file_info['path'],
                    file_info['size'],
                    file_info['hash'] or '',
                    'Yes' if is_dup else 'No'
                ])

    def _export_json(self, file_path: str):
        """Export results as JSON."""
        import json

        output = {
            'folder': self.folder_label.text(),
            'summary': {
                'total': self.results['total'],
                'successful': self.results['successful'],
                'failed': self.results['failed'],
                'duplicate_groups': len(self.results['duplicates'])
            },
            'files': self.results['files'],
            'duplicates': [
                {'hash': h, 'files': files}
                for h, files in self.results['duplicates'].items()
            ]
        }

        with open(file_path, 'w') as f:
            json.dump(output, f, indent=2)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def closeEvent(self, event):
        """Handle window close."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = ContentHashTestGUI()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()
