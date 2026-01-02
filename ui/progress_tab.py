"""
Progress Tab for PyPhotoOrganizer GUI

Displays real-time progress with time estimates.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QProgressBar, QLabel, QTextEdit)
from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
import time


class ProgressTab(QWidget):
    """Tab for displaying processing progress."""

    def __init__(self):
        super().__init__()
        self.start_time = None
        self.last_update_time = None
        self.processed_count = 0
        self.total_count = 0
        self.processing_rate_ema = None
        self.ema_alpha = 0.3
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout()

        # Overall progress group
        overall_group = QGroupBox("Overall Progress")
        overall_layout = QVBoxLayout()

        self.overall_progress = QProgressBar()
        self.overall_progress.setMinimum(0)
        self.overall_progress.setMaximum(100)
        overall_layout.addWidget(self.overall_progress)

        stats_layout = QHBoxLayout()
        self.files_label = QLabel("Files: 0 / 0")
        self.elapsed_label = QLabel("Elapsed: 00:00:00")
        self.remaining_label = QLabel("Remaining: Calculating...")
        stats_layout.addWidget(self.files_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self.elapsed_label)
        stats_layout.addStretch()
        stats_layout.addWidget(self.remaining_label)
        overall_layout.addLayout(stats_layout)

        overall_group.setLayout(overall_layout)
        layout.addWidget(overall_group, 0)  # Fixed size (stretch=0)

        # Current stage group
        stage_group = QGroupBox("Current Stage")
        stage_layout = QVBoxLayout()

        self.stage_label = QLabel("Idle")
        self.stage_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        stage_layout.addWidget(self.stage_label)

        self.stage_progress = QProgressBar()
        stage_layout.addWidget(self.stage_progress)

        self.current_file_label = QLabel("No file")
        stage_layout.addWidget(self.current_file_label)

        self.rate_label = QLabel("Rate: 0.0 files/sec")
        stage_layout.addWidget(self.rate_label)

        # Stage-specific stats
        self.stats_label = QLabel("")
        stage_layout.addWidget(self.stats_label)

        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group, 0)  # Fixed size (stretch=0)

        # Status log group
        log_group = QGroupBox("Status Log (Last 100 events)")
        log_layout = QVBoxLayout()

        self.status_log = QTextEdit()
        self.status_log.setReadOnly(True)
        self.status_log.setMinimumHeight(150)  # Minimum height instead of maximum
        log_layout.addWidget(self.status_log)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group, 1)  # Expandable (stretch=1)

        self.setLayout(layout)

    def reset(self):
        """Reset progress tracking."""
        self.start_time = None
        self.last_update_time = None
        self.processed_count = 0
        self.total_count = 0
        self.processing_rate_ema = None
        self.overall_progress.setValue(0)
        self.stage_progress.setValue(0)
        self.files_label.setText("Files: 0 / 0")
        self.elapsed_label.setText("Elapsed: 00:00:00")
        self.remaining_label.setText("Remaining: Calculating...")
        self.rate_label.setText("Rate: 0.0 files/sec")
        self.current_file_label.setText("No file")
        self.stats_label.setText("")
        self.status_log.clear()

    def update_stage(self, stage_name):
        """Update current processing stage."""
        self.stage_label.setText(stage_name)
        self.add_status_message("info", f"Stage: {stage_name}")

    def update_scanning_progress(self, dirs_scanned, total_dirs, current_dir):
        """Update scanning progress."""
        if total_dirs > 0:
            progress = int(100 * dirs_scanned / total_dirs)
            self.stage_progress.setValue(progress)

        # Truncate long directory paths
        if len(current_dir) > 60:
            current_dir = "..." + current_dir[-57:]
        self.current_file_label.setText(f"Scanning: {current_dir}")

        self.stats_label.setText(f"Directories scanned: {dirs_scanned} / {total_dirs}")

    def update_processing_progress(self, processed, total, current_file, stats):
        """Update processing progress with time estimates."""
        current_time = time.time()

        # Initialize on first update
        if self.start_time is None:
            self.start_time = current_time
            self.last_update_time = current_time
            self.processed_count = processed
            self.total_count = total

        # Update progress bar
        if total > 0:
            progress = int(100 * processed / total)
            self.stage_progress.setValue(progress)
            self.overall_progress.setValue(progress)

        # Update file count
        self.files_label.setText(f"Files: {processed} / {total}")

        # Truncate long filenames
        if len(current_file) > 60:
            current_file = "..." + current_file[-57:]
        self.current_file_label.setText(f"Processing: {current_file}")

        # Calculate processing rate and time estimates
        time_delta = current_time - self.last_update_time
        files_delta = processed - self.processed_count

        if time_delta > 0.5:  # Update every 0.5 seconds
            instant_rate = files_delta / time_delta

            # Update EMA
            if self.processing_rate_ema is None:
                self.processing_rate_ema = instant_rate
            else:
                self.processing_rate_ema = (self.ema_alpha * instant_rate +
                                           (1 - self.ema_alpha) * self.processing_rate_ema)

            # Calculate time remaining
            files_remaining = total - processed
            if self.processing_rate_ema and self.processing_rate_ema > 0:
                seconds_remaining = files_remaining / self.processing_rate_ema
                time_remaining_str = self._format_time(seconds_remaining)
            else:
                time_remaining_str = "Calculating..."

            # Calculate elapsed time
            elapsed_seconds = current_time - self.start_time
            elapsed_str = self._format_time(elapsed_seconds)

            # Update UI
            self.elapsed_label.setText(f"Elapsed: {elapsed_str}")
            self.remaining_label.setText(f"Remaining: {time_remaining_str}")
            self.rate_label.setText(f"Rate: {self.processing_rate_ema:.2f} files/sec")

            # Update state
            self.last_update_time = current_time
            self.processed_count = processed

        # Update stats
        unique = stats.get('unique', 0)
        duplicates = stats.get('duplicates', 0)
        filtered = stats.get('filtered', 0)
        self.stats_label.setText(
            f"Unique: {unique} | Duplicates: {duplicates} | Filtered: {filtered}")

    def update_organizing_progress(self, organized, total, current_file, bytes_copied, total_bytes):
        """Update organizing progress."""
        if total > 0:
            progress = int(100 * organized / total)
            self.stage_progress.setValue(progress)
            self.overall_progress.setValue(progress)

        # Update file count
        self.files_label.setText(f"Files: {organized} / {total}")

        # Truncate long filenames
        if len(current_file) > 60:
            current_file = "..." + current_file[-57:]
        self.current_file_label.setText(f"Organizing: {current_file}")

        # Format bytes
        bytes_str = self._format_bytes(bytes_copied)
        total_bytes_str = self._format_bytes(total_bytes)
        self.stats_label.setText(f"Copied: {bytes_str} / {total_bytes_str}")

    def add_status_message(self, level, message):
        """Add a status message to the log."""
        timestamp = time.strftime("%H:%M:%S")

        # Color code by level
        color = "black"
        if level.lower() == "warning":
            color = "orange"
        elif level.lower() == "error":
            color = "red"

        html = f'<span style="color: {color};">[{timestamp}] {message}</span><br>'
        self.status_log.insertHtml(html)

        # Auto-scroll to bottom
        cursor = self.status_log.textCursor()
        cursor.movePosition(QTextCursor.End)
        self.status_log.setTextCursor(cursor)

    def _format_time(self, seconds):
        """Format seconds as HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _format_bytes(self, bytes_count):
        """Format bytes as human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_count < 1024.0:
                return f"{bytes_count:.2f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.2f} PB"
