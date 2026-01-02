"""
Filtered Files Tab

Review files that were filtered out during processing, see why they were filtered,
and view their attributes and preview.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QTableWidget, QTableWidgetItem, QPushButton,
                               QLabel, QTextEdit, QSplitter, QHeaderView,
                               QFileDialog, QMessageBox, QApplication, QComboBox)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
import os
from pathlib import Path
from PIL import Image
import subprocess


class FilteredFilesTab(QWidget):
    """Tab for reviewing filtered files with details and preview."""

    def __init__(self):
        super().__init__()
        self.filtered_files = []
        self.filter_statistics = {}
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout()

        # Header with statistics
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Filtered Files"))

        self.total_filtered_label = QLabel("Total Filtered: 0")
        self.total_filtered_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(self.total_filtered_label)

        header_layout.addStretch()

        # Filter reason dropdown
        header_layout.addWidget(QLabel("Filter by Reason:"))
        self.reason_combo = QComboBox()
        self.reason_combo.addItem("All Reasons")
        self.reason_combo.currentTextChanged.connect(self.filter_by_reason)
        header_layout.addWidget(self.reason_combo)

        # Export button
        self.export_btn = QPushButton("Export List...")
        self.export_btn.clicked.connect(self.export_filtered_files)
        header_layout.addWidget(self.export_btn)

        main_layout.addLayout(header_layout)

        # Statistics summary
        stats_group = QGroupBox("Filter Statistics")
        stats_layout = QVBoxLayout()
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMinimumHeight(80)  # Minimum instead of maximum
        self.stats_text.setPlaceholderText("No filtering statistics available yet. Run processing to see results.")
        stats_layout.addWidget(self.stats_text)
        stats_group.setLayout(stats_layout)
        main_layout.addWidget(stats_group, 0)  # Fixed size (stretch=0)

        # Create splitter for table and details/preview
        splitter = QSplitter(Qt.Horizontal)

        # Left side - Filtered files table
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)

        self.files_table = QTableWidget()
        self.files_table.setColumnCount(5)
        self.files_table.setHorizontalHeaderLabels([
            "Filename", "Filter Reason", "Size", "Dimensions", "Path"
        ])

        # Set column widths - all columns are user-resizable (Interactive mode)
        header = self.files_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)  # Allow user resizing

        # Set initial column widths
        self.files_table.setColumnWidth(0, 200)  # Filename
        self.files_table.setColumnWidth(1, 200)  # Filter Reason - wider for readability
        self.files_table.setColumnWidth(2, 100)  # Size
        self.files_table.setColumnWidth(3, 120)  # Dimensions
        self.files_table.setColumnWidth(4, 300)  # Path

        # Make the last column (Path) stretch to fill remaining space
        header.setStretchLastSection(True)

        self.files_table.setAlternatingRowColors(True)
        self.files_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.files_table.itemSelectionChanged.connect(self.on_file_selected)

        left_layout.addWidget(self.files_table)

        splitter.addWidget(left_widget)

        # Right side - Details and Preview with vertical splitter
        right_widget = QWidget()
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins for cleaner look
        right_widget.setLayout(right_layout)

        # Create vertical splitter for details and preview
        right_splitter = QSplitter(Qt.Vertical)

        # File details
        details_group = QGroupBox("File Details")
        details_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumHeight(150)  # Minimum instead of maximum
        self.details_text.setPlaceholderText("Select a file to view its details...")
        details_layout.addWidget(self.details_text)

        details_group.setLayout(details_layout)
        right_splitter.addWidget(details_group)

        # Image preview
        preview_group = QGroupBox("Image Preview")
        preview_layout = QVBoxLayout()

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumSize(400, 300)
        self.preview_label.setStyleSheet("border: 1px solid #ccc; background-color: #f5f5f5;")
        self.preview_label.setText("No preview available")
        preview_layout.addWidget(self.preview_label)

        # Preview controls
        preview_controls = QHBoxLayout()

        self.open_file_btn = QPushButton("Open File")
        self.open_file_btn.clicked.connect(self.open_selected_file)
        self.open_file_btn.setEnabled(False)
        preview_controls.addWidget(self.open_file_btn)

        self.open_folder_btn = QPushButton("Open Folder")
        self.open_folder_btn.clicked.connect(self.open_file_folder)
        self.open_folder_btn.setEnabled(False)
        preview_controls.addWidget(self.open_folder_btn)

        self.copy_path_btn = QPushButton("Copy Path")
        self.copy_path_btn.clicked.connect(self.copy_file_path)
        self.copy_path_btn.setEnabled(False)
        preview_controls.addWidget(self.copy_path_btn)

        preview_controls.addStretch()
        preview_layout.addLayout(preview_controls)

        preview_group.setLayout(preview_layout)
        right_splitter.addWidget(preview_group)

        # Set initial sizes for vertical splitter (40% details, 60% preview)
        right_splitter.setSizes([300, 450])

        # Add vertical splitter to right layout
        right_layout.addWidget(right_splitter)

        splitter.addWidget(right_widget)

        # Set initial splitter sizes (60% table, 40% preview)
        splitter.setSizes([600, 400])

        main_layout.addWidget(splitter, 1)  # Expandable (stretch=1) - takes all available space

        self.setLayout(main_layout)

    def display_filtered_files(self, filtered_files, filter_statistics):
        """
        Display filtered files from processing results.

        Args:
            filtered_files: List of dictionaries with file info and filter reason
            filter_statistics: Dictionary with statistics by filter reason
        """
        self.filtered_files = filtered_files or []
        self.filter_statistics = filter_statistics or {}

        # Update header
        self.total_filtered_label.setText(f"Total Filtered: {len(self.filtered_files)}")

        # Update statistics
        self.update_statistics_display()

        # Update reason dropdown
        self.update_reason_combo()

        # Populate table
        self.populate_table()

    def update_statistics_display(self):
        """Update the statistics summary."""
        if not self.filter_statistics:
            self.stats_text.setPlainText("No filtering statistics available.")
            return

        lines = []
        lines.append("Files were filtered for the following reasons:\n")

        stats_items = [
            ("By file size", self.filter_statistics.get('filtered_by_size', 0)),
            ("By dimensions", self.filter_statistics.get('filtered_by_dimensions', 0)),
            ("By square icon detection", self.filter_statistics.get('filtered_by_square', 0)),
            ("By filename pattern", self.filter_statistics.get('filtered_by_filename', 0)),
            ("By missing EXIF", self.filter_statistics.get('filtered_by_exif', 0)),
            ("By aspect ratio", self.filter_statistics.get('filtered_by_aspect_ratio', 0)),
        ]

        for reason, count in stats_items:
            if count > 0:
                lines.append(f"  • {reason}: {count} files")

        lines.append(f"\nTotal filtered: {self.filter_statistics.get('total_filtered', 0)} files")

        self.stats_text.setPlainText("\n".join(lines))

    def update_reason_combo(self):
        """Update the filter reason dropdown."""
        current_text = self.reason_combo.currentText()
        self.reason_combo.clear()
        self.reason_combo.addItem("All Reasons")

        # Add unique reasons from filtered files
        reasons = set()
        for file_info in self.filtered_files:
            reason = file_info.get('filter_reason', 'Unknown')
            if reason:
                reasons.add(reason)

        for reason in sorted(reasons):
            self.reason_combo.addItem(reason)

        # Restore previous selection if possible
        index = self.reason_combo.findText(current_text)
        if index >= 0:
            self.reason_combo.setCurrentIndex(index)

    def filter_by_reason(self):
        """Filter the table by selected reason."""
        self.populate_table()

    def populate_table(self):
        """Populate the filtered files table."""
        self.files_table.setRowCount(0)

        selected_reason = self.reason_combo.currentText()

        for file_info in self.filtered_files:
            # Apply reason filter
            reason = file_info.get('filter_reason', 'Unknown')
            if selected_reason != "All Reasons" and reason != selected_reason:
                continue

            row = self.files_table.rowCount()
            self.files_table.insertRow(row)

            # Filename
            file_path = file_info.get('file_path', '')
            filename = os.path.basename(file_path)
            self.files_table.setItem(row, 0, QTableWidgetItem(filename))

            # Filter Reason
            self.files_table.setItem(row, 1, QTableWidgetItem(reason))

            # Size
            size = file_info.get('file_size', 0)
            size_str = self.format_file_size(size)
            self.files_table.setItem(row, 2, QTableWidgetItem(size_str))

            # Dimensions
            width = file_info.get('width', 0)
            height = file_info.get('height', 0)
            if width and height:
                dimensions = f"{width} x {height}"
            else:
                dimensions = "N/A"
            self.files_table.setItem(row, 3, QTableWidgetItem(dimensions))

            # Path
            self.files_table.setItem(row, 4, QTableWidgetItem(file_path))

            # Store full file info in first column
            self.files_table.item(row, 0).setData(Qt.UserRole, file_info)

    def on_file_selected(self):
        """Handle file selection to show details and preview."""
        selected_items = self.files_table.selectedItems()

        if not selected_items:
            self.details_text.clear()
            self.preview_label.clear()
            self.preview_label.setText("No preview available")
            self.open_file_btn.setEnabled(False)
            self.open_folder_btn.setEnabled(False)
            self.copy_path_btn.setEnabled(False)
            return

        # Get file info
        row = selected_items[0].row()
        first_item = self.files_table.item(row, 0)
        if not first_item:
            return

        file_info = first_item.data(Qt.UserRole)
        if not file_info:
            return

        # Enable buttons
        self.open_file_btn.setEnabled(True)
        self.open_folder_btn.setEnabled(True)
        self.copy_path_btn.setEnabled(True)

        # Display details
        self.display_file_details(file_info)

        # Display preview
        self.display_file_preview(file_info)

    def display_file_details(self, file_info):
        """Display detailed file information."""
        details = []
        details.append("=" * 80)
        details.append("FILE INFORMATION")
        details.append("=" * 80)
        details.append(f"Filename:       {os.path.basename(file_info.get('file_path', ''))}")
        details.append(f"Path:           {file_info.get('file_path', 'N/A')}")
        details.append(f"Filter Reason:  {file_info.get('filter_reason', 'Unknown')}")
        details.append("")
        details.append("FILE ATTRIBUTES")
        details.append("=" * 80)
        details.append(f"File Size:      {self.format_file_size(file_info.get('file_size', 0))}")
        details.append(f"Dimensions:     {file_info.get('width', 'N/A')} x {file_info.get('height', 'N/A')} pixels")

        # Aspect ratio
        width = file_info.get('width', 0)
        height = file_info.get('height', 0)
        if width and height:
            aspect_ratio = width / height
            details.append(f"Aspect Ratio:   {aspect_ratio:.2f}:1")

        details.append(f"Format:         {file_info.get('format', 'Unknown')}")
        details.append(f"Mode:           {file_info.get('mode', 'Unknown')}")

        # EXIF data
        has_exif = file_info.get('has_exif', False)
        details.append(f"Has EXIF:       {'Yes' if has_exif else 'No'}")

        details.append("")
        details.append("FILTER CRITERIA")
        details.append("=" * 80)
        details.append(f"Meets size requirement:       {file_info.get('passes_size', 'N/A')}")
        details.append(f"Meets dimension requirement:  {file_info.get('passes_dimensions', 'N/A')}")
        details.append(f"Is not small square icon:     {file_info.get('passes_square_check', 'N/A')}")
        details.append(f"Filename pattern OK:          {file_info.get('passes_filename_check', 'N/A')}")

        details.append("=" * 80)

        self.details_text.setPlainText("\n".join(details))

    def display_file_preview(self, file_info):
        """Display image preview if possible."""
        file_path = file_info.get('file_path', '')

        if not os.path.exists(file_path):
            self.preview_label.clear()
            self.preview_label.setText("File not found")
            return

        try:
            # Try to load image with PIL
            img = Image.open(file_path)

            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')

            # Resize to fit preview area (max 400x300)
            img.thumbnail((400, 300), Image.Resampling.LANCZOS)

            # Convert PIL Image to QPixmap
            img_data = img.tobytes("raw", "RGB")
            qimage = QImage(img_data, img.width, img.height, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(qimage)

            self.preview_label.setPixmap(pixmap)

        except Exception as e:
            self.preview_label.clear()
            self.preview_label.setText(f"Preview not available\n{str(e)}")

    def open_selected_file(self):
        """Open the selected file with default application."""
        selected_items = self.files_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        file_path = self.files_table.item(row, 4).text()

        if not os.path.exists(file_path):
            QMessageBox.warning(self, "File Not Found",
                              f"File does not exist:\n{file_path}")
            return

        try:
            # Open file with default application (platform-independent)
            if os.name == 'nt':  # Windows
                os.startfile(file_path)
            elif os.name == 'posix':  # Linux/Mac
                subprocess.run(['xdg-open', file_path], check=False)

        except Exception as e:
            QMessageBox.critical(self, "Error Opening File",
                               f"Failed to open file:\n{str(e)}")

    def open_file_folder(self):
        """Open the folder containing the selected file."""
        selected_items = self.files_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        file_path = self.files_table.item(row, 4).text()

        folder_path = os.path.dirname(file_path)

        if not os.path.exists(folder_path):
            QMessageBox.warning(self, "Folder Not Found",
                              f"Folder does not exist:\n{folder_path}")
            return

        try:
            # Open folder with file manager (platform-independent)
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            elif os.name == 'posix':  # Linux/Mac
                subprocess.run(['xdg-open', folder_path], check=False)

        except Exception as e:
            QMessageBox.critical(self, "Error Opening Folder",
                               f"Failed to open folder:\n{str(e)}")

    def copy_file_path(self):
        """Copy the selected file path to clipboard."""
        selected_items = self.files_table.selectedItems()
        if not selected_items:
            return

        row = selected_items[0].row()
        file_path = self.files_table.item(row, 4).text()

        clipboard = QApplication.clipboard()
        clipboard.setText(file_path)

        QMessageBox.information(self, "Copied",
                               "File path copied to clipboard!")

    def export_filtered_files(self):
        """Export the filtered files list to a file."""
        if not self.filtered_files:
            QMessageBox.warning(self, "No Data",
                              "No filtered files to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Filtered Files",
            "filtered_files.csv",
            "CSV Files (*.csv);;Text Files (*.txt);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Write header
                if file_path.endswith('.csv'):
                    f.write('"Filename","Filter Reason","Size","Dimensions","Path"\n')
                else:
                    f.write("Filename\tFilter Reason\tSize\tDimensions\tPath\n")

                # Write data
                for file_info in self.filtered_files:
                    filename = os.path.basename(file_info.get('file_path', ''))
                    reason = file_info.get('filter_reason', 'Unknown')
                    size = self.format_file_size(file_info.get('file_size', 0))
                    width = file_info.get('width', 0)
                    height = file_info.get('height', 0)
                    dimensions = f"{width}x{height}" if width and height else "N/A"
                    path = file_info.get('file_path', '')

                    if file_path.endswith('.csv'):
                        f.write(f'"{filename}","{reason}","{size}","{dimensions}","{path}"\n')
                    else:
                        f.write(f"{filename}\t{reason}\t{size}\t{dimensions}\t{path}\n")

            QMessageBox.information(self, "Export Successful",
                                   f"Exported {len(self.filtered_files)} filtered files to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export:\n{str(e)}")

    def format_file_size(self, size_bytes):
        """Format file size in human-readable format."""
        if size_bytes == 0:
            return "0 B"

        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"
