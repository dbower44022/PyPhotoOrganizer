"""
Progress Tab for PyPhotoOrganizer GUI

Displays real-time progress with time estimates, detailed statistics,
throughput metrics, and visual activity indicators.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QProgressBar, QLabel, QTextEdit, QGridLayout)
from PySide6.QtCore import Qt, QTimer
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

        # Byte throughput tracking
        self.bytes_processed = 0
        self.last_bytes = 0
        self.bytes_rate_ema = None

        # Activity indicator
        self.activity_timer = QTimer()
        self.activity_timer.timeout.connect(self._update_activity_indicator)
        self.activity_frame = 0
        self.activity_chars = ['●', '◐', '○', '◑']  # Rotating indicator

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

        # Stage label with activity indicator
        stage_header_layout = QHBoxLayout()
        self.activity_label = QLabel("●")
        self.activity_label.setStyleSheet("color: #4CAF50; font-size: 16px;")
        self.activity_label.setFixedWidth(20)
        self.activity_label.setVisible(False)  # Hidden when idle
        self.stage_label = QLabel("Idle")
        self.stage_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        stage_header_layout.addWidget(self.activity_label)
        stage_header_layout.addWidget(self.stage_label)
        stage_header_layout.addStretch()
        stage_layout.addLayout(stage_header_layout)

        self.stage_progress = QProgressBar()
        stage_layout.addWidget(self.stage_progress)

        self.current_file_label = QLabel("No file")
        stage_layout.addWidget(self.current_file_label)

        # Rate display with files/sec and MB/s
        rate_layout = QHBoxLayout()
        self.rate_label = QLabel("Rate: 0.0 files/sec")
        self.throughput_label = QLabel("0.0 MB/s")
        rate_layout.addWidget(self.rate_label)
        rate_layout.addWidget(QLabel("  |  "))
        rate_layout.addWidget(self.throughput_label)
        rate_layout.addStretch()
        stage_layout.addLayout(rate_layout)

        # Stage-specific stats (legacy, for organizing phase)
        self.stats_label = QLabel("")
        stage_layout.addWidget(self.stats_label)

        stage_group.setLayout(stage_layout)
        layout.addWidget(stage_group, 0)  # Fixed size (stretch=0)

        # Processing Breakdown group (collapsible)
        self.breakdown_group = QGroupBox("Processing Breakdown")
        self.breakdown_group.setCheckable(True)
        self.breakdown_group.setChecked(True)
        breakdown_layout = QGridLayout()
        breakdown_layout.setSpacing(10)

        # Row 0: Results
        breakdown_layout.addWidget(QLabel("Results:"), 0, 0)
        self.unique_label = QLabel("Unique: 0")
        self.unique_label.setStyleSheet("color: #4CAF50;")  # Green
        breakdown_layout.addWidget(self.unique_label, 0, 1)
        self.duplicates_label = QLabel("Duplicates: 0")
        self.duplicates_label.setStyleSheet("color: #2196F3;")  # Blue
        breakdown_layout.addWidget(self.duplicates_label, 0, 2)
        self.filtered_label = QLabel("Filtered: 0")
        self.filtered_label.setStyleSheet("color: #FF9800;")  # Orange
        breakdown_layout.addWidget(self.filtered_label, 0, 3)

        # Row 1: Content info
        breakdown_layout.addWidget(QLabel("Content:"), 1, 0)
        self.content_dups_label = QLabel("Content Dups: 0")
        self.content_dups_label.setStyleSheet("color: #9C27B0;")  # Purple
        breakdown_layout.addWidget(self.content_dups_label, 1, 1)
        self.unreliable_dates_label = QLabel("Unreliable Dates: 0")
        self.unreliable_dates_label.setStyleSheet("color: #F44336;")  # Red
        breakdown_layout.addWidget(self.unreliable_dates_label, 1, 2)
        # Empty cell at 1, 3

        # Row 2: File types
        breakdown_layout.addWidget(QLabel("Types:"), 2, 0)
        self.photos_label = QLabel("Photos: 0")
        breakdown_layout.addWidget(self.photos_label, 2, 1)
        self.videos_label = QLabel("Videos: 0")
        breakdown_layout.addWidget(self.videos_label, 2, 2)
        # Empty cell at 2, 3

        # Row 3: Date sources
        breakdown_layout.addWidget(QLabel("Dates:"), 3, 0)
        self.date_exif_label = QLabel("EXIF: 0")
        self.date_exif_label.setStyleSheet("color: #4CAF50;")  # Green - good
        breakdown_layout.addWidget(self.date_exif_label, 3, 1)
        self.date_os_label = QLabel("OS Metadata: 0")
        self.date_os_label.setStyleSheet("color: #FF9800;")  # Orange - not ideal
        breakdown_layout.addWidget(self.date_os_label, 3, 2)
        self.date_video_label = QLabel("Video: 0")
        self.date_video_label.setStyleSheet("color: #2196F3;")  # Blue
        breakdown_layout.addWidget(self.date_video_label, 3, 3)

        self.breakdown_group.setLayout(breakdown_layout)
        layout.addWidget(self.breakdown_group, 0)  # Fixed size (stretch=0)

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

        # Reset byte throughput tracking
        self.bytes_processed = 0
        self.last_bytes = 0
        self.bytes_rate_ema = None

        # Stop activity indicator
        self.activity_timer.stop()
        self.activity_frame = 0
        self.activity_label.setVisible(False)

        # Reset UI elements
        self.overall_progress.setValue(0)
        self.stage_progress.setValue(0)
        self.files_label.setText("Files: 0 / 0")
        self.elapsed_label.setText("Elapsed: 00:00:00")
        self.remaining_label.setText("Remaining: Calculating...")
        self.rate_label.setText("Rate: 0.0 files/sec")
        self.throughput_label.setText("0.0 MB/s")
        self.current_file_label.setText("No file")
        self.stats_label.setText("")
        self.stage_label.setText("Idle")

        # Reset breakdown labels
        self.unique_label.setText("Unique: 0")
        self.duplicates_label.setText("Duplicates: 0")
        self.filtered_label.setText("Filtered: 0")
        self.content_dups_label.setText("Content Dups: 0")
        self.unreliable_dates_label.setText("Unreliable Dates: 0")
        self.photos_label.setText("Photos: 0")
        self.videos_label.setText("Videos: 0")
        self.date_exif_label.setText("EXIF: 0")
        self.date_os_label.setText("OS Metadata: 0")
        self.date_video_label.setText("Video: 0")

        self.status_log.clear()

    def _start_activity_indicator(self):
        """Start the activity indicator animation."""
        if not self.activity_timer.isActive():
            self.activity_label.setVisible(True)
            self.activity_timer.start(250)  # Update every 250ms

    def _stop_activity_indicator(self):
        """Stop the activity indicator animation."""
        self.activity_timer.stop()
        self.activity_label.setVisible(False)

    def _update_activity_indicator(self):
        """Update the activity indicator animation frame."""
        self.activity_frame = (self.activity_frame + 1) % len(self.activity_chars)
        self.activity_label.setText(self.activity_chars[self.activity_frame])

    def update_stage(self, stage_name):
        """Update current processing stage."""
        self.stage_label.setText(stage_name)
        self.add_status_message("info", f"Stage: {stage_name}")

        # Start activity indicator when processing begins
        if "Idle" not in stage_name and "Complete" not in stage_name:
            self._start_activity_indicator()
        else:
            self._stop_activity_indicator()

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

        # Start activity indicator during scanning
        self._start_activity_indicator()

    def update_processing_progress(self, processed, total, current_file, stats):
        """Update processing progress with time estimates and detailed stats."""
        current_time = time.time()

        # Initialize on first update
        if self.start_time is None:
            self.start_time = current_time
            self.last_update_time = current_time
            self.processed_count = processed
            self.total_count = total

        # Start activity indicator
        self._start_activity_indicator()

        # Update progress bar
        if total > 0:
            progress = int(100 * processed / total)
            self.stage_progress.setValue(progress)
            self.overall_progress.setValue(progress)

        # Update file count
        self.files_label.setText(f"Files: {processed} / {total}")

        # Get file size for display
        current_file_size = stats.get('current_file_size', 0)
        file_size_str = self._format_bytes(current_file_size) if current_file_size > 0 else ""

        # Truncate long filenames and add file size
        display_file = current_file
        if len(display_file) > 50:
            display_file = "..." + display_file[-47:]
        if file_size_str:
            self.current_file_label.setText(f"Processing: {display_file} ({file_size_str})")
        else:
            self.current_file_label.setText(f"Processing: {display_file}")

        # Always update elapsed time
        elapsed_seconds = current_time - self.start_time
        elapsed_str = self._format_time(elapsed_seconds)
        self.elapsed_label.setText(f"Elapsed: {elapsed_str}")

        # Get bytes processed for throughput calculation
        bytes_processed = stats.get('bytes_processed', 0)

        # Calculate processing rate and throughput (throttled to avoid UI lag)
        time_delta = current_time - self.last_update_time
        files_delta = processed - self.processed_count
        bytes_delta = bytes_processed - self.last_bytes

        if time_delta >= 0.5 and files_delta > 0:
            # Calculate instant file rate
            instant_rate = files_delta / time_delta

            # Calculate instant byte rate
            instant_bytes_rate = bytes_delta / time_delta if time_delta > 0 else 0

            # Update file rate EMA
            if self.processing_rate_ema is None:
                self.processing_rate_ema = instant_rate
            else:
                self.processing_rate_ema = (self.ema_alpha * instant_rate +
                                           (1 - self.ema_alpha) * self.processing_rate_ema)

            # Update bytes rate EMA
            if self.bytes_rate_ema is None:
                self.bytes_rate_ema = instant_bytes_rate
            else:
                self.bytes_rate_ema = (self.ema_alpha * instant_bytes_rate +
                                      (1 - self.ema_alpha) * self.bytes_rate_ema)

            # Update state for next calculation
            self.last_update_time = current_time
            self.processed_count = processed
            self.last_bytes = bytes_processed

        # Calculate time remaining using current rate
        files_remaining = total - processed
        if self.processing_rate_ema and self.processing_rate_ema > 0.01:
            seconds_remaining = files_remaining / self.processing_rate_ema
            time_remaining_str = self._format_time(seconds_remaining)
            self.remaining_label.setText(f"Remaining: {time_remaining_str}")
            self.rate_label.setText(f"Rate: {self.processing_rate_ema:.1f} files/sec")
        elif elapsed_seconds > 2 and processed > 0:
            # Fallback: calculate rate from total elapsed time
            overall_rate = processed / elapsed_seconds
            if overall_rate > 0.01:
                seconds_remaining = files_remaining / overall_rate
                time_remaining_str = self._format_time(seconds_remaining)
                self.remaining_label.setText(f"Remaining: {time_remaining_str}")
                self.rate_label.setText(f"Rate: {overall_rate:.1f} files/sec")
                # Bootstrap the EMA with overall rate
                if self.processing_rate_ema is None:
                    self.processing_rate_ema = overall_rate

        # Update throughput display
        if self.bytes_rate_ema and self.bytes_rate_ema > 0:
            throughput_mb = self.bytes_rate_ema / (1024 * 1024)
            self.throughput_label.setText(f"{throughput_mb:.1f} MB/s")
        elif elapsed_seconds > 2 and bytes_processed > 0:
            # Fallback
            overall_bytes_rate = bytes_processed / elapsed_seconds
            throughput_mb = overall_bytes_rate / (1024 * 1024)
            self.throughput_label.setText(f"{throughput_mb:.1f} MB/s")
            if self.bytes_rate_ema is None:
                self.bytes_rate_ema = overall_bytes_rate

        # Update breakdown labels from stats
        self.unique_label.setText(f"Unique: {stats.get('unique', 0)}")
        self.duplicates_label.setText(f"Duplicates: {stats.get('duplicates', 0)}")
        self.filtered_label.setText(f"Filtered: {stats.get('filtered', 0)}")
        self.content_dups_label.setText(f"Content Dups: {stats.get('content_duplicates', 0)}")
        self.unreliable_dates_label.setText(f"Unreliable Dates: {stats.get('unreliable_dates', 0)}")
        self.photos_label.setText(f"Photos: {stats.get('photos_processed', 0)}")
        self.videos_label.setText(f"Videos: {stats.get('videos_processed', 0)}")
        self.date_exif_label.setText(f"EXIF: {stats.get('date_from_exif', 0)}")
        self.date_os_label.setText(f"OS Metadata: {stats.get('date_from_os', 0)}")
        self.date_video_label.setText(f"Video: {stats.get('date_from_video', 0)}")

        # Legacy stats label (show summary for organizing phase compatibility)
        unique = stats.get('unique', 0)
        duplicates = stats.get('duplicates', 0)
        filtered = stats.get('filtered', 0)
        self.stats_label.setText(
            f"Unique: {unique} | Duplicates: {duplicates} | Filtered: {filtered}")

    def update_organizing_progress(self, organized, total, current_file, bytes_copied, total_bytes):
        """Update organizing progress."""
        current_time = time.time()

        # Initialize on first update of organizing phase
        if self.start_time is None:
            self.start_time = current_time
            self.last_update_time = current_time
            self.processed_count = organized
            self.total_count = total
            self.processing_rate_ema = None
            self.bytes_rate_ema = None
            self.last_bytes = 0

        # Start activity indicator
        self._start_activity_indicator()

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

        # Always update elapsed time
        elapsed_seconds = current_time - self.start_time
        elapsed_str = self._format_time(elapsed_seconds)
        self.elapsed_label.setText(f"Elapsed: {elapsed_str}")

        # Calculate rate and remaining time
        time_delta = current_time - self.last_update_time
        files_delta = organized - self.processed_count
        bytes_delta = bytes_copied - self.last_bytes

        if time_delta >= 0.5 and files_delta > 0:
            instant_rate = files_delta / time_delta
            instant_bytes_rate = bytes_delta / time_delta if time_delta > 0 else 0

            if self.processing_rate_ema is None:
                self.processing_rate_ema = instant_rate
            else:
                self.processing_rate_ema = (self.ema_alpha * instant_rate +
                                           (1 - self.ema_alpha) * self.processing_rate_ema)

            if self.bytes_rate_ema is None:
                self.bytes_rate_ema = instant_bytes_rate
            else:
                self.bytes_rate_ema = (self.ema_alpha * instant_bytes_rate +
                                      (1 - self.ema_alpha) * self.bytes_rate_ema)

            self.last_update_time = current_time
            self.processed_count = organized
            self.last_bytes = bytes_copied

        # Update remaining time
        files_remaining = total - organized
        if self.processing_rate_ema and self.processing_rate_ema > 0.01:
            seconds_remaining = files_remaining / self.processing_rate_ema
            self.remaining_label.setText(f"Remaining: {self._format_time(seconds_remaining)}")
            self.rate_label.setText(f"Rate: {self.processing_rate_ema:.1f} files/sec")
        elif elapsed_seconds > 2 and organized > 0:
            overall_rate = organized / elapsed_seconds
            if overall_rate > 0.01:
                seconds_remaining = files_remaining / overall_rate
                self.remaining_label.setText(f"Remaining: {self._format_time(seconds_remaining)}")
                self.rate_label.setText(f"Rate: {overall_rate:.1f} files/sec")

        # Update throughput display
        if self.bytes_rate_ema and self.bytes_rate_ema > 0:
            throughput_mb = self.bytes_rate_ema / (1024 * 1024)
            self.throughput_label.setText(f"{throughput_mb:.1f} MB/s")
        elif elapsed_seconds > 2 and bytes_copied > 0:
            overall_bytes_rate = bytes_copied / elapsed_seconds
            throughput_mb = overall_bytes_rate / (1024 * 1024)
            self.throughput_label.setText(f"{throughput_mb:.1f} MB/s")

        # Format bytes for stats
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
                return f"{bytes_count:.1f} {unit}"
            bytes_count /= 1024.0
        return f"{bytes_count:.1f} PB"
