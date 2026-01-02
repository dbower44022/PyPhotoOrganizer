"""
Logs Tab for PyPhotoOrganizer GUI

View detailed application logs within UI.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QTableWidget, QTableWidgetItem, QComboBox,
                               QLineEdit, QPushButton, QLabel, QCheckBox,
                               QHeaderView)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
import os


class LogsTab(QWidget):
    """Tab for viewing application logs."""

    def __init__(self):
        super().__init__()
        self.log_file_path = "main_app_error.log"
        self.auto_scroll = True
        self.init_ui()

        # Set up auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_logs)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Controls group
        controls_layout = QHBoxLayout()

        # Log level filter
        controls_layout.addWidget(QLabel("Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["All", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.currentTextChanged.connect(self.filter_logs)
        controls_layout.addWidget(self.level_combo)

        # Search box
        controls_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by keyword...")
        self.search_box.textChanged.connect(self.filter_logs)
        controls_layout.addWidget(self.search_box)

        # Auto-scroll checkbox
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self.toggle_auto_scroll)
        controls_layout.addWidget(self.auto_scroll_check)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_logs)
        controls_layout.addWidget(self.refresh_btn)

        # Clear button
        self.clear_btn = QPushButton("Clear Display")
        self.clear_btn.clicked.connect(self.clear_display)
        controls_layout.addWidget(self.clear_btn)

        controls_layout.addStretch()

        layout.addLayout(controls_layout)

        # Log viewer group
        viewer_group = QGroupBox("Log Viewer")
        viewer_layout = QVBoxLayout()

        self.log_table = QTableWidget()
        self.log_table.setColumnCount(6)
        self.log_table.setHorizontalHeaderLabels(
            ["Timestamp", "Level", "Module", "Function", "Line", "Message"])

        # Set column widths
        header = self.log_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.Stretch)

        self.log_table.setAlternatingRowColors(True)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)

        viewer_layout.addWidget(self.log_table)

        viewer_group.setLayout(viewer_layout)
        layout.addWidget(viewer_group)

        self.setLayout(layout)

        # Initial load
        self.refresh_logs()

    def refresh_logs(self):
        """Refresh logs from file."""
        if not os.path.exists(self.log_file_path):
            return

        try:
            # Store current row count
            old_row_count = self.log_table.rowCount()

            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Parse log lines
            for line in lines[old_row_count:]:
                self._parse_and_add_log_line(line)

            # Auto-scroll to bottom if enabled
            if self.auto_scroll:
                self.log_table.scrollToBottom()

        except Exception as e:
            print(f"Error reading log file: {e}")

    def _parse_and_add_log_line(self, line):
        """Parse and add a log line to the table."""
        try:
            # Expected format: timestamp - module - level - function - line --- message
            parts = line.split(' - ')
            if len(parts) >= 5:
                timestamp = parts[0]
                module = parts[1]
                level = parts[2]
                function = parts[3]

                # Split line and message
                rest = ' - '.join(parts[4:])
                if ' --- ' in rest:
                    line_num, message = rest.split(' --- ', 1)
                else:
                    line_num = ""
                    message = rest

                # Add row
                row = self.log_table.rowCount()
                self.log_table.insertRow(row)

                # Set items
                self.log_table.setItem(row, 0, QTableWidgetItem(timestamp))
                self.log_table.setItem(row, 1, QTableWidgetItem(level))
                self.log_table.setItem(row, 2, QTableWidgetItem(module))
                self.log_table.setItem(row, 3, QTableWidgetItem(function))
                self.log_table.setItem(row, 4, QTableWidgetItem(line_num))
                self.log_table.setItem(row, 5, QTableWidgetItem(message.strip()))

                # Color code by level
                color = None
                if 'WARNING' in level:
                    color = QColor(255, 165, 0)  # Orange
                elif 'ERROR' in level or 'CRITICAL' in level:
                    color = QColor(255, 0, 0)  # Red

                if color:
                    for col in range(6):
                        item = self.log_table.item(row, col)
                        if item:
                            item.setBackground(color)

        except Exception as e:
            print(f"Error parsing log line: {e}")

    def filter_logs(self):
        """Filter logs by level and search text."""
        level_filter = self.level_combo.currentText()
        search_text = self.search_box.text().lower()

        for row in range(self.log_table.rowCount()):
            show_row = True

            # Level filter
            if level_filter != "All":
                level_item = self.log_table.item(row, 1)
                if level_item and level_filter not in level_item.text():
                    show_row = False

            # Search filter
            if show_row and search_text:
                row_text = ""
                for col in range(self.log_table.columnCount()):
                    item = self.log_table.item(row, col)
                    if item:
                        row_text += item.text().lower() + " "

                if search_text not in row_text:
                    show_row = False

            self.log_table.setRowHidden(row, not show_row)

    def toggle_auto_scroll(self, state):
        """Toggle auto-scroll."""
        self.auto_scroll = (state == Qt.Checked)

    def clear_display(self):
        """Clear the display (not the log file)."""
        self.log_table.setRowCount(0)
