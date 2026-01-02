"""
Logs Tab for PyPhotoOrganizer GUI

View detailed application logs within UI with advanced filtering and analysis.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QTableWidget, QTableWidgetItem, QComboBox,
                               QLineEdit, QPushButton, QLabel, QCheckBox,
                               QHeaderView, QTextEdit, QFileDialog, QMessageBox,
                               QApplication, QSplitter)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor, QFont
import os
import glob
from datetime import datetime, timedelta


class ClickableLabel(QLabel):
    """Label that emits a signal when clicked."""
    clicked = Signal()

    def mousePressEvent(self, event):
        """Emit clicked signal when label is clicked."""
        self.clicked.emit()
        super().mousePressEvent(event)


class LogsTab(QWidget):
    """Tab for viewing application logs with advanced features."""

    def __init__(self):
        super().__init__()
        self.current_log_file = None
        self.available_log_files = []
        self.auto_scroll = True
        self.all_log_entries = []  # Store all parsed entries
        self.init_ui()

        # Discover log files
        self.discover_log_files()

        # Set up auto-refresh timer
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_logs)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds

    def init_ui(self):
        """Initialize the user interface."""
        main_layout = QVBoxLayout()

        # Statistics bar
        stats_layout = QHBoxLayout()
        stats_layout.addWidget(QLabel("Log Statistics:"))

        # Create clickable stat labels
        self.stats_debug = ClickableLabel("DEBUG: 0")
        self.stats_info = ClickableLabel("INFO: 0")
        self.stats_warning = ClickableLabel("WARNING: 0")
        self.stats_error = ClickableLabel("ERROR: 0")
        self.stats_critical = ClickableLabel("CRITICAL: 0")

        # Connect click signals
        self.stats_debug.clicked.connect(lambda: self.filter_by_stat("DEBUG"))
        self.stats_info.clicked.connect(lambda: self.filter_by_stat("INFO"))
        self.stats_warning.clicked.connect(lambda: self.filter_by_stat("WARNING"))
        self.stats_error.clicked.connect(lambda: self.filter_by_stat("ERROR"))
        self.stats_critical.clicked.connect(lambda: self.filter_by_stat("CRITICAL"))

        # Style the stat labels
        from PySide6.QtCore import Qt
        for stat_label in [self.stats_debug, self.stats_info, self.stats_warning,
                           self.stats_error, self.stats_critical]:
            stat_label.setStyleSheet("padding: 5px; border: 1px solid #ccc;")
            stat_label.setCursor(Qt.PointingHandCursor)  # Set hand cursor properly

        self.stats_warning.setStyleSheet("padding: 5px; border: 1px solid #ccc; background-color: #fff3cd;")
        self.stats_error.setStyleSheet("padding: 5px; border: 1px solid #ccc; background-color: #f8d7da;")
        self.stats_critical.setStyleSheet("padding: 5px; border: 1px solid #ccc; background-color: #dc3545; color: white;")

        stats_layout.addWidget(self.stats_debug)
        stats_layout.addWidget(self.stats_info)
        stats_layout.addWidget(self.stats_warning)
        stats_layout.addWidget(self.stats_error)
        stats_layout.addWidget(self.stats_critical)
        stats_layout.addStretch()

        main_layout.addLayout(stats_layout)

        # Controls group - Row 1
        controls_layout1 = QHBoxLayout()

        # Log file selector
        controls_layout1.addWidget(QLabel("Log File:"))
        self.log_file_combo = QComboBox()
        self.log_file_combo.currentTextChanged.connect(self.on_log_file_changed)
        controls_layout1.addWidget(self.log_file_combo)

        # Log level filter
        controls_layout1.addWidget(QLabel("Level:"))
        self.level_combo = QComboBox()
        self.level_combo.addItems(["All", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.level_combo.currentTextChanged.connect(self.filter_logs)
        controls_layout1.addWidget(self.level_combo)

        # Search box
        controls_layout1.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Filter by keyword...")
        self.search_box.textChanged.connect(self.filter_logs)
        controls_layout1.addWidget(self.search_box)

        # Auto-scroll checkbox
        self.auto_scroll_check = QCheckBox("Auto-scroll")
        self.auto_scroll_check.setChecked(True)
        self.auto_scroll_check.stateChanged.connect(self.toggle_auto_scroll)
        controls_layout1.addWidget(self.auto_scroll_check)

        controls_layout1.addStretch()
        main_layout.addLayout(controls_layout1)

        # Controls group - Row 2
        controls_layout2 = QHBoxLayout()

        # Time range filter
        controls_layout2.addWidget(QLabel("Time Range:"))
        self.time_range_combo = QComboBox()
        self.time_range_combo.addItems([
            "All Time",
            "Last 5 Minutes",
            "Last 15 Minutes",
            "Last Hour",
            "Last 6 Hours",
            "Today",
            "Yesterday"
        ])
        self.time_range_combo.currentTextChanged.connect(self.filter_logs)
        controls_layout2.addWidget(self.time_range_combo)

        # Buttons
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_logs)
        controls_layout2.addWidget(self.refresh_btn)

        self.copy_btn = QPushButton("Copy Selected")
        self.copy_btn.clicked.connect(self.copy_selected_rows)
        controls_layout2.addWidget(self.copy_btn)

        self.export_btn = QPushButton("Export Filtered...")
        self.export_btn.clicked.connect(self.export_logs)
        controls_layout2.addWidget(self.export_btn)

        self.clear_display_btn = QPushButton("Clear Display")
        self.clear_display_btn.clicked.connect(self.clear_display)
        controls_layout2.addWidget(self.clear_display_btn)

        self.clear_file_btn = QPushButton("Clear Log File")
        self.clear_file_btn.clicked.connect(self.clear_log_file)
        self.clear_file_btn.setStyleSheet("background-color: #dc3545; color: white;")
        controls_layout2.addWidget(self.clear_file_btn)

        controls_layout2.addStretch()
        main_layout.addLayout(controls_layout2)

        # Splitter for table and details panel
        splitter = QSplitter(Qt.Vertical)

        # Log viewer table
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
        self.log_table.itemSelectionChanged.connect(self.on_selection_changed)

        splitter.addWidget(self.log_table)

        # Details panel
        details_group = QGroupBox("Details")
        details_layout = QVBoxLayout()

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        # Remove maximum height to allow resizing with splitter
        font = QFont("Courier New", 10)
        self.details_text.setFont(font)
        self.details_text.setPlaceholderText("Select a log entry to view full details...")

        details_layout.addWidget(self.details_text)
        details_group.setLayout(details_layout)

        splitter.addWidget(details_group)

        # Set initial splitter sizes (table larger than details)
        splitter.setSizes([400, 150])

        main_layout.addWidget(splitter)

        self.setLayout(main_layout)

    def discover_log_files(self):
        """Discover all available log files."""
        try:
            # Look for all .log files in current directory
            log_files = glob.glob("*.log")

            if log_files:
                self.available_log_files = sorted(log_files)
                self.log_file_combo.clear()
                self.log_file_combo.addItems(self.available_log_files)

                # Default to main app log if available
                if "main_app_error.log" in self.available_log_files:
                    self.log_file_combo.setCurrentText("main_app_error.log")
                else:
                    self.log_file_combo.setCurrentIndex(0)
            else:
                self.log_file_combo.clear()
                self.log_file_combo.addItem("No log files found")

        except Exception as e:
            print(f"Error discovering log files: {e}")

    def on_log_file_changed(self, log_file):
        """Handle log file selection change."""
        if log_file and log_file != "No log files found":
            self.current_log_file = log_file
            self.clear_display()
            self.refresh_logs()

    def refresh_logs(self):
        """Refresh logs from file."""
        if not self.current_log_file or not os.path.exists(self.current_log_file):
            return

        try:
            with open(self.current_log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()

            # Clear and reload all entries
            self.all_log_entries = []

            # Parse all log lines
            for line in lines:
                entry = self._parse_log_line(line)
                if entry:
                    self.all_log_entries.append(entry)

            # Update statistics
            self.update_statistics()

            # Apply filters and display
            self.filter_logs()

        except Exception as e:
            print(f"Error reading log file: {e}")

    def _parse_log_line(self, line):
        """
        Parse a log line and return a dictionary.

        Handles variable log formats by finding the log level in the parts.
        Expected levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
        """
        try:
            # First, check if this line contains ' --- ' which separates metadata from message
            if ' --- ' not in line:
                return None

            # Split into metadata and message parts
            metadata_part, message = line.split(' --- ', 1)

            # Now split metadata by ' - '
            parts = [p.strip() for p in metadata_part.split(' - ')]

            # We need at least: timestamp - module - level - function - line
            if len(parts) < 5:
                return None

            # Find the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            level_index = -1
            level = None
            valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']

            for i, part in enumerate(parts):
                if part in valid_levels:
                    level_index = i
                    level = part
                    break

            # If we didn't find a valid level, skip this line
            if level_index == -1:
                return None

            # Parse based on where we found the level
            # Format appears to be: timestamp - module - [extra?] - level - function - line
            timestamp = parts[0]

            # Module is before the level (could be parts[1] or parts[1:level_index] joined)
            if level_index > 1:
                module = parts[1]
            else:
                module = "unknown"

            # Function should be after level
            if level_index + 1 < len(parts):
                function = parts[level_index + 1]
            else:
                function = "unknown"

            # Line number should be after function
            if level_index + 2 < len(parts):
                line_num = parts[level_index + 2]
            else:
                line_num = ""

            return {
                'timestamp': timestamp,
                'level': level,
                'module': module,
                'function': function,
                'line': line_num,
                'message': message.strip(),
                'raw': line.strip()
            }

        except Exception as e:
            # If parsing fails, silently skip (don't spam console)
            return None

    def filter_logs(self):
        """Filter logs by level, search text, and time range."""
        level_filter = self.level_combo.currentText()
        search_text = self.search_box.text().lower()
        time_range = self.time_range_combo.currentText()

        # Save current selection (by raw log line)
        selected_entry = None
        selected_items = self.log_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            first_item = self.log_table.item(row, 0)
            if first_item:
                selected_entry = first_item.data(Qt.UserRole)

        # Calculate time threshold
        time_threshold = None
        now = datetime.now()

        if time_range == "Last 5 Minutes":
            time_threshold = now - timedelta(minutes=5)
        elif time_range == "Last 15 Minutes":
            time_threshold = now - timedelta(minutes=15)
        elif time_range == "Last Hour":
            time_threshold = now - timedelta(hours=1)
        elif time_range == "Last 6 Hours":
            time_threshold = now - timedelta(hours=6)
        elif time_range == "Today":
            time_threshold = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif time_range == "Yesterday":
            yesterday = now - timedelta(days=1)
            time_threshold = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)

        # Clear table
        self.log_table.setRowCount(0)

        # Filter and display entries
        for entry in self.all_log_entries:
            show_entry = True

            # Level filter
            if level_filter != "All" and entry['level'] != level_filter:
                show_entry = False

            # Search filter
            if show_entry and search_text:
                entry_text = f"{entry['timestamp']} {entry['level']} {entry['module']} {entry['function']} {entry['message']}".lower()
                if search_text not in entry_text:
                    show_entry = False

            # Time range filter
            if show_entry and time_threshold:
                try:
                    # Parse timestamp (format: 2024-01-02 15:30:45,123)
                    timestamp_str = entry['timestamp'].split(',')[0]  # Remove milliseconds
                    entry_time = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

                    if entry_time < time_threshold:
                        show_entry = False
                except:
                    # If timestamp parsing fails, show the entry
                    pass

            if show_entry:
                self._add_entry_to_table(entry)

        # Restore selection if we had one
        if selected_entry:
            for row in range(self.log_table.rowCount()):
                first_item = self.log_table.item(row, 0)
                if first_item:
                    entry = first_item.data(Qt.UserRole)
                    if entry and entry['raw'] == selected_entry['raw']:
                        # Found the same entry, restore selection
                        self.log_table.selectRow(row)
                        # Don't auto-scroll if we're restoring a selection
                        break
        else:
            # Only auto-scroll if no selection (user isn't reading something)
            if self.auto_scroll:
                self.log_table.scrollToBottom()

    def _add_entry_to_table(self, entry):
        """Add a log entry to the table."""
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)

        # Set items
        self.log_table.setItem(row, 0, QTableWidgetItem(entry['timestamp']))
        self.log_table.setItem(row, 1, QTableWidgetItem(entry['level']))
        self.log_table.setItem(row, 2, QTableWidgetItem(entry['module']))
        self.log_table.setItem(row, 3, QTableWidgetItem(entry['function']))
        self.log_table.setItem(row, 4, QTableWidgetItem(entry['line']))
        self.log_table.setItem(row, 5, QTableWidgetItem(entry['message']))

        # Store full entry in first column's data
        self.log_table.item(row, 0).setData(Qt.UserRole, entry)

        # Color code by level
        color = None
        if entry['level'] == 'WARNING':
            color = QColor(255, 243, 205)  # Light yellow
        elif entry['level'] == 'ERROR':
            color = QColor(248, 215, 218)  # Light red
        elif entry['level'] == 'CRITICAL':
            color = QColor(220, 53, 69)  # Red
            # Make text white for critical
            for col in range(6):
                item = self.log_table.item(row, col)
                if item:
                    item.setForeground(QColor(255, 255, 255))

        if color:
            for col in range(6):
                item = self.log_table.item(row, col)
                if item:
                    item.setBackground(color)

    def update_statistics(self):
        """Update log statistics display."""
        counts = {
            'DEBUG': 0,
            'INFO': 0,
            'WARNING': 0,
            'ERROR': 0,
            'CRITICAL': 0
        }

        for entry in self.all_log_entries:
            level = entry['level']
            if level in counts:
                counts[level] += 1

        self.stats_debug.setText(f"DEBUG: {counts['DEBUG']}")
        self.stats_info.setText(f"INFO: {counts['INFO']}")
        self.stats_warning.setText(f"WARNING: {counts['WARNING']}")
        self.stats_error.setText(f"ERROR: {counts['ERROR']}")
        self.stats_critical.setText(f"CRITICAL: {counts['CRITICAL']}")

    def filter_by_stat(self, level):
        """Filter logs by clicking a statistic."""
        # Set the level combo box to the clicked level
        self.level_combo.setCurrentText(level)

    def on_selection_changed(self):
        """Handle log entry selection to show details."""
        selected_items = self.log_table.selectedItems()

        if not selected_items:
            self.details_text.clear()
            return

        # Get the first column of the selected row to retrieve full entry
        row = selected_items[0].row()
        first_item = self.log_table.item(row, 0)

        if first_item:
            entry = first_item.data(Qt.UserRole)
            if entry:
                # Build detailed view
                details = []
                details.append("=" * 80)
                details.append(f"TIMESTAMP:  {entry['timestamp']}")
                details.append(f"LEVEL:      {entry['level']}")
                details.append(f"MODULE:     {entry['module']}")
                details.append(f"FUNCTION:   {entry['function']}")
                details.append(f"LINE:       {entry['line']}")
                details.append("=" * 80)
                details.append("MESSAGE:")
                details.append(entry['message'])
                details.append("=" * 80)
                details.append("RAW LOG LINE:")
                details.append(entry['raw'])
                details.append("=" * 80)

                self.details_text.setPlainText("\n".join(details))

    def copy_selected_rows(self):
        """Copy selected rows to clipboard."""
        selected_rows = set()
        for item in self.log_table.selectedItems():
            selected_rows.add(item.row())

        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select rows to copy.")
            return

        # Build text to copy
        lines = []
        for row in sorted(selected_rows):
            row_data = []
            for col in range(self.log_table.columnCount()):
                item = self.log_table.item(row, col)
                if item:
                    row_data.append(item.text())
            lines.append("\t".join(row_data))

        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))

        QMessageBox.information(self, "Copied",
                               f"Copied {len(selected_rows)} row(s) to clipboard!")

    def export_logs(self):
        """Export filtered logs to file."""
        if self.log_table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "No logs to export.")
            return

        # Ask user for file path
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Logs",
            f"exported_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;CSV Files (*.csv);;All Files (*)"
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                # Write header
                headers = []
                for col in range(self.log_table.columnCount()):
                    headers.append(self.log_table.horizontalHeaderItem(col).text())

                if file_path.endswith('.csv'):
                    f.write(",".join(f'"{h}"' for h in headers) + "\n")
                else:
                    f.write("\t".join(headers) + "\n")

                # Write rows
                for row in range(self.log_table.rowCount()):
                    row_data = []
                    for col in range(self.log_table.columnCount()):
                        item = self.log_table.item(row, col)
                        if item:
                            text = item.text()
                            if file_path.endswith('.csv'):
                                # Escape quotes and wrap in quotes for CSV
                                text = f'"{text.replace(chr(34), chr(34)+chr(34))}"'
                            row_data.append(text)

                    if file_path.endswith('.csv'):
                        f.write(",".join(row_data) + "\n")
                    else:
                        f.write("\t".join(row_data) + "\n")

            QMessageBox.information(self, "Export Successful",
                                   f"Exported {self.log_table.rowCount()} log entries to:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Failed",
                               f"Failed to export logs:\n\n{str(e)}")

    def clear_display(self):
        """Clear the display (not the log file)."""
        self.log_table.setRowCount(0)
        self.all_log_entries = []
        self.details_text.clear()
        self.update_statistics()

    def clear_log_file(self):
        """Clear the actual log file (with confirmation)."""
        if not self.current_log_file:
            return

        response = QMessageBox.warning(
            self,
            "Clear Log File?",
            f"Are you sure you want to clear the log file?\n\n"
            f"File: {self.current_log_file}\n\n"
            f"This will permanently delete all log entries!\n"
            f"This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if response == QMessageBox.Yes:
            try:
                # Truncate the file
                with open(self.current_log_file, 'w') as f:
                    f.write('')

                # Clear display
                self.clear_display()

                QMessageBox.information(self, "Log File Cleared",
                                       f"Log file cleared successfully:\n{self.current_log_file}")

            except Exception as e:
                QMessageBox.critical(self, "Failed to Clear",
                                   f"Failed to clear log file:\n\n{str(e)}")

    def toggle_auto_scroll(self, state):
        """Toggle auto-scroll."""
        self.auto_scroll = (state == Qt.Checked)
