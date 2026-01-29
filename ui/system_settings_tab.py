"""
System Settings Tab for PyPhotoOrganizer GUI

This tab contains system-level settings:
- Current Database Information (name, file, dates)
- Current Database Statistics (total photos, schema version)
- Operation Mode (Copy vs Move)
- Performance Settings (partial hash configuration)
- Thumbnail Cache Settings (memory size, worker threads)
- Import History Retention (mode, count, cleanup)
- Settings Management (Load/Save/Restore/Validate)
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QCheckBox, QSpinBox, QPushButton,
                               QLabel, QMessageBox, QScrollArea,
                               QFormLayout, QComboBox, QRadioButton,
                               QButtonGroup, QLineEdit, QFileDialog)
from PySide6.QtCore import Qt
import json
import os
from datetime import datetime
import constants
from config import Config
import logging

logger = logging.getLogger(__name__)


class SystemSettingsTab(QWidget):
    """Tab for managing system-level settings."""

    def __init__(self):
        super().__init__()
        self.settings_file = "settings.json"
        self.db_metadata = None  # Will be set when database is loaded

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

        # Current Database Group
        db_group = QGroupBox("Current Database Information")
        db_group.setStyleSheet(self.groupbox_style)
        db_layout = QFormLayout()

        self.db_name_label = QLabel("No database loaded")
        self.db_name_label.setStyleSheet("font-weight: bold;")
        db_layout.addRow("Database Name:", self.db_name_label)

        self.db_file_label = QLabel("-")
        db_layout.addRow("Database File:", self.db_file_label)

        self.db_path_label = QLabel("-")
        self.db_path_label.setWordWrap(True)
        self.db_path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        db_layout.addRow("Database Path:", self.db_path_label)

        self.db_created_label = QLabel("-")
        db_layout.addRow("Created:", self.db_created_label)

        self.db_last_used_label = QLabel("-")
        db_layout.addRow("Last Used:", self.db_last_used_label)

        db_group.setLayout(db_layout)
        layout.addWidget(db_group)

        # Statistics Group
        stats_group = QGroupBox("Current Database Statistics")
        stats_group.setStyleSheet(self.groupbox_style)
        stats_layout = QFormLayout()

        self.total_photos_label = QLabel("0")
        self.total_photos_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        stats_layout.addRow("Total Photos:", self.total_photos_label)

        self.schema_version_label = QLabel("-")
        stats_layout.addRow("Schema Version:", self.schema_version_label)

        # Refresh button
        self.refresh_db_stats_btn = QPushButton("Refresh Statistics")
        self.refresh_db_stats_btn.clicked.connect(self.refresh_database_statistics)
        stats_layout.addRow("", self.refresh_db_stats_btn)

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        # Operation Mode Group
        mode_group = QGroupBox("Operation Mode")
        mode_group.setStyleSheet(self.groupbox_style)
        mode_layout = QVBoxLayout()

        self.copy_radio = QRadioButton("Copy Files (Safe - keeps originals)")
        self.copy_radio.setChecked(True)

        self.move_radio = QRadioButton("Move Files (Destructive - deletes originals)")

        self.mode_button_group = QButtonGroup()
        self.mode_button_group.addButton(self.copy_radio)
        self.mode_button_group.addButton(self.move_radio)

        mode_layout.addWidget(self.copy_radio)
        mode_layout.addWidget(self.move_radio)

        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # Performance Settings
        perf_group = QGroupBox("Performance Settings")
        perf_group.setStyleSheet(self.groupbox_style)
        perf_layout = QFormLayout()

        self.partial_hash_check = QCheckBox()
        self.partial_hash_check.setChecked(True)
        perf_layout.addRow("Partial hash enabled:", self.partial_hash_check)

        self.partial_hash_bytes_spin = QSpinBox()
        self.partial_hash_bytes_spin.setRange(1024, 1048576)
        self.partial_hash_bytes_spin.setValue(constants.PARTIAL_HASH_BYTES)
        perf_layout.addRow("Partial hash bytes:", self.partial_hash_bytes_spin)

        self.partial_hash_min_size_spin = QSpinBox()
        self.partial_hash_min_size_spin.setRange(0, 10485760)
        self.partial_hash_min_size_spin.setValue(constants.PARTIAL_HASH_MIN_FILE_SIZE)
        perf_layout.addRow("Min file size for partial hash:", self.partial_hash_min_size_spin)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # Content-Based Duplicate Detection Settings
        content_hash_group = QGroupBox("Content-Based Duplicate Detection")
        content_hash_group.setStyleSheet(self.groupbox_style)
        content_hash_layout = QVBoxLayout()

        content_hash_desc = QLabel(
            "Content hashing detects visually identical images even when file bytes differ "
            "(e.g., after re-encoding or EXIF modification). Uses pixel data to find duplicates."
        )
        content_hash_desc.setWordWrap(True)
        content_hash_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        content_hash_layout.addWidget(content_hash_desc)

        self.content_hash_enabled_check = QCheckBox("Enable content-based duplicate detection during import")
        self.content_hash_enabled_check.setChecked(True)
        self.content_hash_enabled_check.stateChanged.connect(self.on_content_hash_enabled_changed)
        content_hash_layout.addWidget(self.content_hash_enabled_check)

        # Backfill section
        backfill_layout = QHBoxLayout()
        self.backfill_btn = QPushButton("Calculate Content Hashes for Existing Files")
        self.backfill_btn.setToolTip("Calculate content hashes for archive files that don't have them yet")
        self.backfill_btn.clicked.connect(self.start_content_hash_backfill)
        backfill_layout.addWidget(self.backfill_btn)

        self.cancel_backfill_btn = QPushButton("Cancel")
        self.cancel_backfill_btn.setToolTip("Cancel the content hash calculation")
        self.cancel_backfill_btn.clicked.connect(self.cancel_content_hash_backfill)
        self.cancel_backfill_btn.hide()
        backfill_layout.addWidget(self.cancel_backfill_btn)

        backfill_layout.addStretch()
        content_hash_layout.addLayout(backfill_layout)

        # Progress bar (hidden by default)
        from PySide6.QtWidgets import QProgressBar
        self.backfill_progress = QProgressBar()
        self.backfill_progress.setRange(0, 100)
        self.backfill_progress.setValue(0)
        self.backfill_progress.hide()
        content_hash_layout.addWidget(self.backfill_progress)

        # Status label
        self.backfill_status_label = QLabel("")
        self.backfill_status_label.setStyleSheet("color: #666;")
        self.backfill_status_label.hide()
        content_hash_layout.addWidget(self.backfill_status_label)

        content_hash_group.setLayout(content_hash_layout)
        layout.addWidget(content_hash_group)

        # Initialize backfill worker reference
        self._backfill_worker = None

        # Video Content-Based Duplicate Detection Settings
        video_content_hash_group = QGroupBox("Video Content-Based Duplicate Detection")
        video_content_hash_group.setStyleSheet(self.groupbox_style)
        video_content_hash_layout = QVBoxLayout()

        video_content_hash_desc = QLabel(
            "Video content hashing detects visually identical videos even when re-encoded, "
            "transcoded, or with different metadata. Uses perceptual hashing of key frames."
        )
        video_content_hash_desc.setWordWrap(True)
        video_content_hash_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        video_content_hash_layout.addWidget(video_content_hash_desc)

        self.video_content_hash_enabled_check = QCheckBox("Enable video content duplicate detection during import")
        self.video_content_hash_enabled_check.setChecked(True)
        self.video_content_hash_enabled_check.stateChanged.connect(self.on_video_content_hash_enabled_changed)
        video_content_hash_layout.addWidget(self.video_content_hash_enabled_check)

        # Video backfill section
        video_backfill_layout = QHBoxLayout()
        self.video_backfill_btn = QPushButton("Calculate Video Content Hashes for Existing Files")
        self.video_backfill_btn.setToolTip("Calculate video content hashes for archive videos that don't have them yet")
        self.video_backfill_btn.clicked.connect(self.start_video_content_hash_backfill)
        video_backfill_layout.addWidget(self.video_backfill_btn)

        self.cancel_video_backfill_btn = QPushButton("Cancel")
        self.cancel_video_backfill_btn.setToolTip("Cancel the video content hash calculation")
        self.cancel_video_backfill_btn.clicked.connect(self.cancel_video_content_hash_backfill)
        self.cancel_video_backfill_btn.hide()
        video_backfill_layout.addWidget(self.cancel_video_backfill_btn)

        video_backfill_layout.addStretch()
        video_content_hash_layout.addLayout(video_backfill_layout)

        # Video progress bar (hidden by default)
        from PySide6.QtWidgets import QProgressBar
        self.video_backfill_progress = QProgressBar()
        self.video_backfill_progress.setRange(0, 100)
        self.video_backfill_progress.setValue(0)
        self.video_backfill_progress.hide()
        video_content_hash_layout.addWidget(self.video_backfill_progress)

        # Video status label
        self.video_backfill_status_label = QLabel("")
        self.video_backfill_status_label.setStyleSheet("color: #666;")
        self.video_backfill_status_label.hide()
        video_content_hash_layout.addWidget(self.video_backfill_status_label)

        video_content_hash_group.setLayout(video_content_hash_layout)
        layout.addWidget(video_content_hash_group)

        # Initialize video backfill worker reference
        self._video_backfill_worker = None

        # Metadata-Based Archive Upgrade Settings
        metadata_upgrade_group = QGroupBox("Metadata-Based Archive Upgrades")
        metadata_upgrade_group.setStyleSheet(self.groupbox_style)
        metadata_upgrade_layout = QVBoxLayout()

        metadata_upgrade_desc = QLabel(
            "When importing a duplicate file with better metadata (e.g., EXIF date vs OS date), "
            "automatically replace the archive file with the incoming file. The original is "
            "preserved in the Prior Revision Archive. User-corrected files are never replaced."
        )
        metadata_upgrade_desc.setWordWrap(True)
        metadata_upgrade_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        metadata_upgrade_layout.addWidget(metadata_upgrade_desc)

        self.metadata_upgrade_enabled_check = QCheckBox("Enable automatic metadata upgrades during import")
        self.metadata_upgrade_enabled_check.setChecked(True)
        self.metadata_upgrade_enabled_check.setToolTip(
            "When enabled, duplicates with better metadata will replace inferior archive files.\n"
            "For example: A file with EXIF date will replace a file that only has OS file date.\n"
            "Files you have manually corrected are protected and will never be replaced."
        )
        self.metadata_upgrade_enabled_check.stateChanged.connect(self.on_metadata_upgrade_enabled_changed)
        metadata_upgrade_layout.addWidget(self.metadata_upgrade_enabled_check)

        # Priority explanation
        priority_label = QLabel(
            "<b>Metadata quality priority:</b> EXIF DateTimeOriginal > EXIF DateTimeDigitized > "
            "GPS Date > Video metadata > IPTC > EXIF DateTime > OS file date"
        )
        priority_label.setWordWrap(True)
        priority_label.setStyleSheet("font-size: 10px; color: #444; margin-top: 10px; padding: 5px; "
                                     "background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 3px;")
        metadata_upgrade_layout.addWidget(priority_label)

        metadata_upgrade_group.setLayout(metadata_upgrade_layout)
        layout.addWidget(metadata_upgrade_group)

        # Thumbnail Cache Settings
        cache_group = QGroupBox("Thumbnail Cache Settings (Date Corrections Tab)")
        cache_group.setStyleSheet(self.groupbox_style)
        cache_layout = QFormLayout()

        cache_memory_layout = QHBoxLayout()
        self.cache_memory_spin = QSpinBox()
        self.cache_memory_spin.setRange(50, 2000)
        self.cache_memory_spin.setValue(500)
        self.cache_memory_spin.setSuffix(" MB")
        self.cache_memory_spin.valueChanged.connect(self.on_cache_settings_changed)
        cache_memory_layout.addWidget(self.cache_memory_spin)

        self.cache_items_label = QLabel()
        self.cache_items_label.setStyleSheet("color: #666; font-style: italic;")
        cache_memory_layout.addWidget(self.cache_items_label)
        cache_memory_layout.addStretch()

        cache_layout.addRow("Cache memory size:", cache_memory_layout)

        worker_layout = QHBoxLayout()
        self.worker_threads_spin = QSpinBox()
        self.worker_threads_spin.setRange(1, 16)
        self.worker_threads_spin.setValue(8)
        self.worker_threads_spin.setSuffix(" threads")
        self.worker_threads_spin.valueChanged.connect(self.on_cache_settings_changed)
        worker_layout.addWidget(self.worker_threads_spin)

        import multiprocessing
        cpu_count = multiprocessing.cpu_count()
        cpu_hint = QLabel(f"(System has {cpu_count} CPU cores)")
        cpu_hint.setStyleSheet("color: #666; font-style: italic;")
        worker_layout.addWidget(cpu_hint)
        worker_layout.addStretch()

        cache_layout.addRow("Worker threads:", worker_layout)

        cache_help = QLabel(
            "Cache memory determines how many thumbnails are kept in RAM for instant access.\n"
            "Higher values = faster scrolling but more memory usage.\n"
            "Worker threads control parallel thumbnail generation. Match your CPU cores for best performance."
        )
        cache_help.setWordWrap(True)
        cache_help.setStyleSheet("color: #666; font-size: 9pt; padding: 5px;")
        cache_layout.addRow("", cache_help)

        cache_group.setLayout(cache_layout)
        layout.addWidget(cache_group)

        self.update_cache_items_label()

        # Delete Vault Configuration
        vault_group = QGroupBox("Delete Vault Configuration")
        vault_group.setStyleSheet(self.groupbox_style)
        vault_layout = QFormLayout()

        vault_desc = QLabel(
            "Configure a location where deleted files will be moved before permanent deletion.\n"
            "Deleted files can be restored from the Delete Vault through the Date Corrections tab."
        )
        vault_desc.setWordWrap(True)
        vault_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        vault_layout.addRow("", vault_desc)

        vault_path_layout = QHBoxLayout()
        self.vault_path_edit = QLineEdit()
        self.vault_path_edit.setReadOnly(True)
        self.vault_path_edit.setPlaceholderText("Not configured")
        vault_path_layout.addWidget(self.vault_path_edit)

        self.vault_browse_btn = QPushButton("Browse...")
        self.vault_browse_btn.clicked.connect(self.on_browse_delete_vault)
        vault_path_layout.addWidget(self.vault_browse_btn)

        vault_layout.addRow("Delete Vault Location:", vault_path_layout)

        vault_group.setLayout(vault_layout)
        layout.addWidget(vault_group)

        # Import History Retention Settings
        retention_group = QGroupBox("Import History Retention")
        retention_group.setStyleSheet(self.groupbox_style)
        retention_layout = QVBoxLayout()

        retention_desc = QLabel(
            "Configure how long import history records are kept. "
            "Older sessions and their file logs will be automatically cleaned up."
        )
        retention_desc.setWordWrap(True)
        retention_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        retention_layout.addWidget(retention_desc)

        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Retention Mode:"))
        self.retention_mode_combo = QComboBox()
        self.retention_mode_combo.addItems(["Keep All", "Keep Last N Sessions", "Keep Last N Days"])
        self.retention_mode_combo.currentIndexChanged.connect(self.on_retention_mode_changed)
        mode_layout.addWidget(self.retention_mode_combo)
        mode_layout.addStretch()
        retention_layout.addLayout(mode_layout)

        count_layout = QHBoxLayout()
        self.retention_count_label = QLabel("Sessions to keep:")
        count_layout.addWidget(self.retention_count_label)
        self.retention_count_spin = QSpinBox()
        self.retention_count_spin.setRange(1, 1000)
        self.retention_count_spin.setValue(50)
        count_layout.addWidget(self.retention_count_spin)
        count_layout.addStretch()
        retention_layout.addLayout(count_layout)

        self.auto_cleanup_check = QCheckBox("Enable automatic cleanup on startup")
        self.auto_cleanup_check.setToolTip("When enabled, old sessions will be deleted automatically when the application starts")
        retention_layout.addWidget(self.auto_cleanup_check)

        cleanup_btn_layout = QHBoxLayout()
        self.cleanup_now_btn = QPushButton("Clean Up Now")
        self.cleanup_now_btn.clicked.connect(self.run_retention_cleanup)
        self.cleanup_now_btn.setToolTip("Delete old sessions according to retention settings")
        cleanup_btn_layout.addWidget(self.cleanup_now_btn)

        self.save_retention_btn = QPushButton("Save Retention Settings")
        self.save_retention_btn.clicked.connect(self.save_retention_settings)
        cleanup_btn_layout.addWidget(self.save_retention_btn)

        cleanup_btn_layout.addStretch()
        retention_layout.addLayout(cleanup_btn_layout)

        retention_group.setLayout(retention_layout)
        layout.addWidget(retention_group)

        # Global Settings Buttons
        button_group = QGroupBox("Settings Management (Load and Save Files)")
        button_group.setStyleSheet(self.groupbox_style)
        button_layout = QHBoxLayout()

        self.load_btn = QPushButton("Load from File")
        self.load_btn.clicked.connect(self.load_from_file)
        button_layout.addWidget(self.load_btn)

        self.save_btn = QPushButton("Save to File")
        self.save_btn.clicked.connect(self.save_to_file)
        button_layout.addWidget(self.save_btn)

        self.defaults_btn = QPushButton("Restore Defaults")
        self.defaults_btn.clicked.connect(self.restore_defaults)
        button_layout.addWidget(self.defaults_btn)

        self.validate_btn = QPushButton("Validate Settings")
        self.validate_btn.clicked.connect(self.validate_settings)
        button_layout.addWidget(self.validate_btn)

        button_layout.addStretch()
        button_group.setLayout(button_layout)
        layout.addWidget(button_group)

        layout.addStretch()
        main_widget.setLayout(layout)
        scroll.setWidget(main_widget)

        # Set the scroll area as the main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ========== Database Methods ==========

    def _format_date(self, date_str: str) -> str:
        """Format a date string into a user-friendly format.

        Args:
            date_str: Date string in various formats (ISO format, etc.)

        Returns:
            Formatted date string like "January 15, 2025 at 3:45 PM"
        """
        if not date_str or date_str == '-':
            return '-'

        try:
            # Try ISO format first (e.g., "2025-01-15T14:30:00" or "2025-01-15 14:30:00")
            if 'T' in date_str:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            elif ' ' in date_str and ':' in date_str:
                # Try "YYYY-MM-DD HH:MM:SS" format
                dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            elif '-' in date_str and len(date_str) == 10:
                # Try "YYYY-MM-DD" format
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                return dt.strftime("%B %d, %Y")
            else:
                # Unknown format, return as-is
                return date_str

            # Format with time
            return dt.strftime("%B %d, %Y at %I:%M %p").replace(" 0", " ")
        except (ValueError, AttributeError) as e:
            logger.debug(f"Could not parse date '{date_str}': {e}")
            return date_str

    def set_database(self, db_metadata):
        """Set the database metadata and update UI."""
        self.db_metadata = db_metadata

        if db_metadata is None:
            self.db_name_label.setText("No database loaded")
            self.db_file_label.setText("-")
            self.db_path_label.setText("-")
            self.db_created_label.setText("-")
            self.db_last_used_label.setText("-")
            self.total_photos_label.setText("0")
            self.schema_version_label.setText("-")
            return

        # Load database information
        metadata = db_metadata.get_metadata()
        if metadata:
            self.db_name_label.setText(metadata.get('database_name', 'Unknown'))
            self.db_file_label.setText(os.path.basename(db_metadata.database_path))
            self.db_path_label.setText(db_metadata.database_path)

            created = metadata.get('created_date', '-')
            self.db_created_label.setText(self._format_date(created))

            last_used = metadata.get('last_used_date', '-')
            self.db_last_used_label.setText(self._format_date(last_used))

            self.total_photos_label.setText(f"{metadata.get('total_photos', 0):,}")
            self.schema_version_label.setText(str(metadata.get('schema_version', 1)))

        # Load cache settings
        cache_memory_mb = db_metadata.get_cache_memory_mb()
        if cache_memory_mb:
            self.cache_memory_spin.setValue(cache_memory_mb)

        worker_threads = db_metadata.get_cache_worker_threads()
        if worker_threads:
            self.worker_threads_spin.setValue(worker_threads)

        self.update_cache_items_label()

        # Load Delete Vault location
        vault_path = db_metadata.get_delete_vault_location()
        if vault_path:
            self.vault_path_edit.setText(vault_path)
        else:
            self.vault_path_edit.clear()
            self.vault_path_edit.setPlaceholderText("Not configured")

        # Load retention settings
        self.load_retention_settings()

        # Load content hash settings
        content_hash_enabled = db_metadata.is_content_hash_enabled()
        self.content_hash_enabled_check.blockSignals(True)
        self.content_hash_enabled_check.setChecked(content_hash_enabled)
        self.content_hash_enabled_check.blockSignals(False)

        # Load metadata upgrade settings
        metadata_upgrade_enabled = db_metadata.is_metadata_upgrade_enabled()
        self.metadata_upgrade_enabled_check.blockSignals(True)
        self.metadata_upgrade_enabled_check.setChecked(metadata_upgrade_enabled)
        self.metadata_upgrade_enabled_check.blockSignals(False)

        # Load video content hash settings
        video_content_hash_enabled = db_metadata.is_video_content_hash_enabled()
        self.video_content_hash_enabled_check.blockSignals(True)
        self.video_content_hash_enabled_check.setChecked(video_content_hash_enabled)
        self.video_content_hash_enabled_check.blockSignals(False)

    def refresh_database_statistics(self):
        """Refresh the database statistics display."""
        if not self.db_metadata:
            return

        self.db_metadata.refresh_total_photos()
        metadata = self.db_metadata.get_metadata()

        if not metadata:
            return

        self.total_photos_label.setText(f"{metadata.get('total_photos', 0):,}")
        self.schema_version_label.setText(str(metadata.get('schema_version', 1)))
        self.db_metadata.update_last_used()

    # ========== Operation Mode Methods ==========

    def is_copy_mode(self):
        """Check if copy mode is selected."""
        return self.copy_radio.isChecked()

    def is_move_mode(self):
        """Check if move mode is selected."""
        return self.move_radio.isChecked()

    # ========== Performance Settings Methods ==========

    def update_cache_items_label(self):
        """Update the label showing calculated item count from MB."""
        cache_memory_mb = self.cache_memory_spin.value()
        items = int((cache_memory_mb * 1024 * 1024) / (150 * 1024))
        self.cache_items_label.setText(f"(~{items:,} thumbnails)")

    def on_cache_settings_changed(self):
        """Handle cache settings change - update label and save to database."""
        self.update_cache_items_label()

        if self.db_metadata:
            cache_memory_mb = self.cache_memory_spin.value()
            worker_threads = self.worker_threads_spin.value()

            self.db_metadata.set_cache_memory_mb(cache_memory_mb)
            self.db_metadata.set_cache_worker_threads(worker_threads)

            logger.info(f"Updated cache settings: {cache_memory_mb}MB memory, {worker_threads} worker threads")
            logger.info("Note: Changes will take effect when Date Corrections tab is reopened")

    # ========== Delete Vault Configuration Methods ==========

    def on_browse_delete_vault(self):
        """Open directory browser for Delete Vault location and auto-save."""
        from PySide6.QtWidgets import QFileDialog

        logger.info(f"{'='*80}")
        logger.info(f"DELETE VAULT LOCATION SELECTION STARTED")
        logger.info(f"{'-'*60}")

        if not self.db_metadata:
            logger.error(f"✗ No database loaded")
            logger.error(f"  Cannot configure Delete Vault without active database")
            QMessageBox.warning(
                self,
                "No Database",
                "No database is currently loaded."
            )
            return

        current_path = self.vault_path_edit.text()
        if not current_path or current_path == "Not configured":
            current_path = os.path.expanduser("~")

        logger.info(f"  Opening directory browser...")
        logger.info(f"  Starting path: {current_path}")

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Delete Vault Directory",
            current_path,
            QFileDialog.ShowDirsOnly
        )

        if directory:
            logger.info(f"  User selected directory: {directory}")

            # Validate path
            if not os.path.exists(directory):
                logger.error(f"✗ Selected directory does not exist: {directory}")
                logger.error(f"  Validation failed: Directory not found")
                QMessageBox.critical(
                    self,
                    "Invalid Path",
                    f"The selected directory does not exist:\n{directory}"
                )
                logger.info(f"{'='*80}")
                return

            if not os.path.isdir(directory):
                logger.error(f"✗ Selected path is not a directory: {directory}")
                logger.error(f"  Validation failed: Not a directory")
                QMessageBox.critical(
                    self,
                    "Invalid Path",
                    f"The selected path is not a directory:\n{directory}"
                )
                logger.info(f"{'='*80}")
                return

            if not os.access(directory, os.W_OK):
                logger.error(f"✗ Selected directory is not writable: {directory}")
                logger.error(f"  Validation failed: Permission denied")
                QMessageBox.critical(
                    self,
                    "Permission Denied",
                    f"The selected directory is not writable:\n{directory}"
                )
                logger.info(f"{'='*80}")
                return

            logger.info(f"  ✓ Directory validation passed")
            logger.info(f"  Saving to database...")

            # Auto-save to database
            success = self.db_metadata.set_delete_vault_location(directory)

            if success:
                self.vault_path_edit.setText(directory)
                logger.info(f"✓ Delete Vault location saved and UI updated successfully")
                logger.info(f"  Location: {directory}")
                logger.info(f"{'='*80}")
            else:
                logger.error(f"✗ Failed to save Delete Vault location to database")
                logger.error(f"  Directory: {directory}")
                logger.error(f"  Check detailed logs above for specific error")
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to save Delete Vault location. Check logs for details."
                )
                logger.info(f"{'='*80}")
        else:
            logger.info(f"  User cancelled directory selection")
            logger.info(f"{'='*80}")

    # ========== Retention Settings Methods ==========

    def on_retention_mode_changed(self, index):
        """Handle retention mode dropdown change."""
        mode_labels = ["", "Sessions to keep:", "Days to keep:"]
        if index == 0:
            self.retention_count_label.hide()
            self.retention_count_spin.hide()
        else:
            self.retention_count_label.setText(mode_labels[index])
            self.retention_count_label.show()
            self.retention_count_spin.show()

    def load_retention_settings(self):
        """Load retention settings from database."""
        if not self.db_metadata:
            return

        try:
            from audit_manager import AuditManager
            audit_manager = AuditManager(self.db_metadata.database_path)
            settings = audit_manager.get_retention_settings()

            if settings:
                mode = settings.get('retention_mode', 'none')
                if mode == 'none':
                    self.retention_mode_combo.setCurrentIndex(0)
                elif mode == 'sessions':
                    self.retention_mode_combo.setCurrentIndex(1)
                    self.retention_count_spin.setValue(settings.get('retain_session_count', 50))
                elif mode == 'days':
                    self.retention_mode_combo.setCurrentIndex(2)
                    self.retention_count_spin.setValue(settings.get('retain_days', 365))

                self.auto_cleanup_check.setChecked(settings.get('auto_cleanup_enabled', False))

            self.on_retention_mode_changed(self.retention_mode_combo.currentIndex())

        except Exception:
            pass

    def save_retention_settings(self):
        """Save retention settings to database."""
        if not self.db_metadata:
            QMessageBox.warning(self, "No Database", "Please select a database first.")
            return

        try:
            from audit_manager import AuditManager
            audit_manager = AuditManager(self.db_metadata.database_path)

            index = self.retention_mode_combo.currentIndex()
            if index == 0:
                mode = 'none'
            elif index == 1:
                mode = 'sessions'
            else:
                mode = 'days'

            count = self.retention_count_spin.value()
            auto_cleanup = self.auto_cleanup_check.isChecked()

            audit_manager.set_retention_settings(
                mode=mode,
                count=count if mode == 'sessions' else 50,
                days=count if mode == 'days' else 365,
                auto_cleanup=auto_cleanup
            )

            QMessageBox.information(self, "Settings Saved",
                                   "Retention settings saved successfully.")

        except Exception as e:
            QMessageBox.critical(self, "Save Error",
                               f"Failed to save retention settings:\n\n{str(e)}")

    def run_retention_cleanup(self):
        """Run retention policy cleanup manually."""
        if not self.db_metadata:
            QMessageBox.warning(self, "No Database", "Please select a database first.")
            return

        reply = QMessageBox.question(
            self, "Confirm Cleanup",
            "This will delete old import sessions according to your retention settings.\n\n"
            "This action cannot be undone. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        try:
            from audit_manager import AuditManager
            audit_manager = AuditManager(self.db_metadata.database_path)

            sessions_deleted, logs_deleted = audit_manager.apply_retention_policy()

            if sessions_deleted > 0 or logs_deleted > 0:
                QMessageBox.information(
                    self, "Cleanup Complete",
                    f"Cleanup complete:\n\n"
                    f"Sessions deleted: {sessions_deleted}\n"
                    f"File logs deleted: {logs_deleted}"
                )
            else:
                QMessageBox.information(
                    self, "No Cleanup Needed",
                    "No sessions need to be deleted according to current retention settings."
                )

        except Exception as e:
            QMessageBox.critical(self, "Cleanup Error",
                               f"Failed to run cleanup:\n\n{str(e)}")

    # ========== Settings File Management Methods ==========

    def get_config(self):
        """Get configuration as dictionary (partial hash settings only)."""
        config = {
            'partial_hash_enabled': self.partial_hash_check.isChecked(),
            'partial_hash_bytes': self.partial_hash_bytes_spin.value(),
            'partial_hash_min_file_size': self.partial_hash_min_size_spin.value(),
        }
        return config

    def set_config(self, config):
        """Set configuration from dictionary (partial hash settings only)."""
        self.partial_hash_check.setChecked(config.get('partial_hash_enabled', True))
        self.partial_hash_bytes_spin.setValue(
            config.get('partial_hash_bytes', constants.PARTIAL_HASH_BYTES))
        self.partial_hash_min_size_spin.setValue(
            config.get('partial_hash_min_file_size', constants.PARTIAL_HASH_MIN_FILE_SIZE))

    def load_from_file(self, show_dialog=True):
        """Load settings from file."""
        if not os.path.exists(self.settings_file):
            if show_dialog:
                QMessageBox.information(self, "No Settings File",
                                       f"{self.settings_file} not found. Using defaults.")
            self.restore_defaults()
            return

        try:
            with open(self.settings_file, 'r') as f:
                config = json.load(f)
            self.set_config(config)
            if show_dialog:
                QMessageBox.information(self, "Settings Loaded",
                                       "Settings loaded successfully from file.")
        except Exception as e:
            if show_dialog:
                QMessageBox.critical(self, "Load Error",
                                   f"Failed to load settings:\n\n{str(e)}")

    def save_to_file(self):
        """Save settings to file."""
        try:
            config = self.get_config()

            # Preserve other settings from existing file if it exists
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    existing = json.load(f)
                # Merge - keep existing settings, only update what we manage
                existing.update(config)
                config = existing

            # Validate before saving
            try:
                # Create a complete config for validation
                test_config = config.copy()
                test_config['source_directory'] = ["/dummy/path"]
                test_config['destination_directory'] = "/dummy/path"
                test_config['copy_files'] = True
                test_config['move_files'] = False
                Config(test_config)
            except Exception as e:
                QMessageBox.critical(self, "Validation Error",
                                   f"Invalid settings:\n\n{str(e)}")
                return

            with open(self.settings_file, 'w') as f:
                json.dump(config, f, indent=2)

            QMessageBox.information(self, "Settings Saved",
                                   "Settings saved successfully to file.")

        except Exception as e:
            QMessageBox.critical(self, "Save Error",
                               f"Failed to save settings:\n\n{str(e)}")

    def restore_defaults(self):
        """Restore default settings."""
        config = {
            'partial_hash_enabled': True,
            'partial_hash_bytes': constants.PARTIAL_HASH_BYTES,
            'partial_hash_min_file_size': constants.PARTIAL_HASH_MIN_FILE_SIZE,
        }
        self.set_config(config)
        QMessageBox.information(self, "Defaults Restored",
                               "Settings restored to default values.")

    def validate_settings(self):
        """Validate current settings."""
        try:
            config = self.get_config()

            # Create complete config for validation
            config['source_directory'] = ["/dummy/path"]
            config['destination_directory'] = "/dummy/path"
            config['copy_files'] = True
            config['move_files'] = False
            config['batch_size'] = constants.DEFAULT_BATCH_SIZE
            config['include_subdirectories'] = True
            config['organization_template'] = '{YYYY}/{MM}/{DD}'
            config['file_type_organization'] = 'combined'
            config['photo_filter_enabled'] = True
            config['min_file_size'] = constants.MIN_PHOTO_FILE_SIZE
            config['min_width'] = constants.MIN_PHOTO_WIDTH
            config['min_height'] = constants.MIN_PHOTO_HEIGHT
            config['max_width'] = constants.MAX_PHOTO_WIDTH
            config['max_height'] = constants.MAX_PHOTO_HEIGHT
            config['exclude_square_smaller_than'] = constants.MIN_SQUARE_SIZE
            config['require_exif'] = False
            config['database_path'] = constants.DEFAULT_DATABASE_NAME
            config['file_endings'] = constants.DEFAULT_FILE_ENDINGS
            config['excluded_filename_patterns'] = constants.DEFAULT_EXCLUDED_PATTERNS

            Config(settings_dict=config)
            QMessageBox.information(self, "Validation Successful",
                                   "All settings are valid.")
        except Exception as e:
            import traceback
            full_error = traceback.format_exc()
            logger.error(f"Validation failed:\n{full_error}")
            QMessageBox.critical(self, "Validation Failed",
                               f"Invalid settings:\n\n{str(e)}")

    # ========== Content Hash Methods ==========

    def on_content_hash_enabled_changed(self, state):
        """Handle content hash enabled checkbox change."""
        if not self.db_metadata:
            return

        enabled = state == Qt.Checked
        success = self.db_metadata.set_content_hash_enabled(enabled)
        if success:
            logger.info(f"Content hashing {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning("Failed to save content hash setting")
            # Revert checkbox
            self.content_hash_enabled_check.blockSignals(True)
            self.content_hash_enabled_check.setChecked(not enabled)
            self.content_hash_enabled_check.blockSignals(False)

    def on_metadata_upgrade_enabled_changed(self, state):
        """Handle metadata upgrade enabled checkbox change."""
        if not self.db_metadata:
            return

        enabled = state == Qt.Checked
        success = self.db_metadata.set_metadata_upgrade_enabled(enabled)
        if success:
            logger.info(f"Metadata upgrades {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning("Failed to save metadata upgrade setting")
            # Revert checkbox
            self.metadata_upgrade_enabled_check.blockSignals(True)
            self.metadata_upgrade_enabled_check.setChecked(not enabled)
            self.metadata_upgrade_enabled_check.blockSignals(False)

    def start_content_hash_backfill(self):
        """Start the content hash backfill process."""
        if not self.db_metadata:
            QMessageBox.warning(self, "No Database", "Please select a database first.")
            return

        # Check if already running
        if self._backfill_worker is not None and self._backfill_worker.isRunning():
            QMessageBox.information(self, "Already Running",
                                   "Content hash calculation is already in progress.")
            return

        # Confirm with user
        reply = QMessageBox.question(
            self, "Calculate Content Hashes",
            "This will calculate content hashes for all archive files that don't have them yet.\n\n"
            "This may take a while for large archives.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            return

        # Import worker
        from ui.content_hash_worker import ContentHashBackfillWorker

        # Create and start worker
        self._backfill_worker = ContentHashBackfillWorker(
            database_path=self.db_metadata.database_path,
            batch_size=100
        )

        # Connect signals
        self._backfill_worker.progress_update.connect(self._on_backfill_progress)
        self._backfill_worker.status_update.connect(self._on_backfill_status)
        self._backfill_worker.completed.connect(self._on_backfill_completed)
        self._backfill_worker.error_occurred.connect(self._on_backfill_error)

        # Update UI
        self.backfill_btn.setEnabled(False)
        self.cancel_backfill_btn.show()
        self.backfill_progress.show()
        self.backfill_progress.setValue(0)
        self.backfill_status_label.setText("Starting...")
        self.backfill_status_label.show()

        # Start worker
        self._backfill_worker.start()

    def cancel_content_hash_backfill(self):
        """Cancel the content hash backfill process."""
        if self._backfill_worker and self._backfill_worker.isRunning():
            self._backfill_worker.stop()
            self.backfill_status_label.setText("Cancelling...")

    def _on_backfill_progress(self, current, total, filename):
        """Handle backfill progress update."""
        if total > 0:
            percent = int((current / total) * 100)
            self.backfill_progress.setValue(percent)
            self.backfill_status_label.setText(f"Processing {current}/{total}: {filename}")

    def _on_backfill_status(self, message):
        """Handle backfill status update."""
        self.backfill_status_label.setText(message)

    def _on_backfill_completed(self, results):
        """Handle backfill completion."""
        # Reset UI
        self.backfill_btn.setEnabled(True)
        self.cancel_backfill_btn.hide()
        self.backfill_progress.hide()

        status = results.get('status', 'unknown')
        files_updated = results.get('files_updated', 0)
        files_skipped = results.get('files_skipped', 0)
        files_failed = results.get('files_failed', 0)
        discovered_duplicates = results.get('discovered_duplicates', [])
        dup_count = len(discovered_duplicates)

        if status == 'completed':
            status_text = f"Complete: {files_updated} updated, {files_skipped} skipped, {files_failed} failed"
            if dup_count > 0:
                status_text += f", {dup_count} duplicates discovered"
            self.backfill_status_label.setText(status_text)

            if files_updated > 0 or dup_count > 0:
                message = (
                    f"Content hash calculation complete!\n\n"
                    f"Files updated: {files_updated}\n"
                    f"Files skipped (videos/missing): {files_skipped}\n"
                    f"Files failed: {files_failed}"
                )

                if dup_count > 0:
                    message += f"\n\nDiscovered {dup_count} content duplicate(s)!\n"
                    message += "These are files with identical pixel content but different file hashes.\n\n"

                    # Show up to 5 examples
                    examples = discovered_duplicates[:5]
                    for dup in examples:
                        file_name = os.path.basename(dup['file_path'])
                        dup_of_name = os.path.basename(dup['duplicate_of_path'])
                        message += f"  - {file_name} matches {dup_of_name}\n"

                    if dup_count > 5:
                        message += f"  ... and {dup_count - 5} more\n"

                    message += "\nYou can find these in the database by querying files with the same content_hash."

                QMessageBox.information(self, "Backfill Complete", message)

        elif status == 'cancelled':
            status_text = f"Cancelled: {files_updated} files updated before cancellation"
            if dup_count > 0:
                status_text += f", {dup_count} duplicates discovered"
            self.backfill_status_label.setText(status_text)
        else:
            self.backfill_status_label.setText(f"Failed: {results.get('error', 'Unknown error')}")

        self._backfill_worker = None

    def _on_backfill_error(self, error_msg):
        """Handle backfill error."""
        self.backfill_btn.setEnabled(True)
        self.cancel_backfill_btn.hide()
        self.backfill_progress.hide()
        self.backfill_status_label.setText(f"Error: {error_msg}")

        QMessageBox.critical(
            self, "Backfill Error",
            f"Content hash calculation failed:\n\n{error_msg}"
        )

        self._backfill_worker = None

    # ========== Video Content Hash Methods ==========

    def on_video_content_hash_enabled_changed(self, state):
        """Handle video content hash enabled checkbox change."""
        if not self.db_metadata:
            return

        enabled = state == Qt.Checked
        success = self.db_metadata.set_video_content_hash_enabled(enabled)
        if success:
            logger.info(f"Video content hashing {'enabled' if enabled else 'disabled'}")
        else:
            logger.warning("Failed to save video content hash setting")
            # Revert checkbox
            self.video_content_hash_enabled_check.blockSignals(True)
            self.video_content_hash_enabled_check.setChecked(not enabled)
            self.video_content_hash_enabled_check.blockSignals(False)

    def start_video_content_hash_backfill(self):
        """Start the video content hash backfill process."""
        if not self.db_metadata:
            QMessageBox.warning(self, "No Database", "Please select a database first.")
            return

        # Check if already running
        if self._video_backfill_worker is not None and self._video_backfill_worker.isRunning():
            QMessageBox.information(self, "Already Running",
                                   "Video content hash calculation is already in progress.")
            return

        # Confirm with user
        reply = QMessageBox.question(
            self, "Calculate Video Content Hashes",
            "This will calculate video content hashes for all archive videos that don't have them yet.\n\n"
            "This extracts key frames from each video and may take significantly longer than image hashing.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            return

        # Import worker
        from ui.video_content_hash_worker import VideoContentHashBackfillWorker

        # Create and start worker
        self._video_backfill_worker = VideoContentHashBackfillWorker(
            database_path=self.db_metadata.database_path,
            batch_size=50  # Lower batch size for videos due to higher processing cost
        )

        # Connect signals
        self._video_backfill_worker.progress_update.connect(self._on_video_backfill_progress)
        self._video_backfill_worker.status_update.connect(self._on_video_backfill_status)
        self._video_backfill_worker.completed.connect(self._on_video_backfill_completed)
        self._video_backfill_worker.error_occurred.connect(self._on_video_backfill_error)

        # Update UI
        self.video_backfill_btn.setEnabled(False)
        self.cancel_video_backfill_btn.show()
        self.video_backfill_progress.show()
        self.video_backfill_progress.setValue(0)
        self.video_backfill_status_label.setText("Starting...")
        self.video_backfill_status_label.show()

        # Start worker
        self._video_backfill_worker.start()

    def cancel_video_content_hash_backfill(self):
        """Cancel the video content hash backfill process."""
        if self._video_backfill_worker and self._video_backfill_worker.isRunning():
            self._video_backfill_worker.stop()
            self.video_backfill_status_label.setText("Cancelling...")

    def _on_video_backfill_progress(self, current, total, filename):
        """Handle video backfill progress update."""
        if total > 0:
            percent = int((current / total) * 100)
            self.video_backfill_progress.setValue(percent)
            self.video_backfill_status_label.setText(f"Processing {current}/{total}: {filename}")

    def _on_video_backfill_status(self, message):
        """Handle video backfill status update."""
        self.video_backfill_status_label.setText(message)

    def _on_video_backfill_completed(self, results):
        """Handle video backfill completion."""
        # Reset UI
        self.video_backfill_btn.setEnabled(True)
        self.cancel_video_backfill_btn.hide()
        self.video_backfill_progress.hide()

        status = results.get('status', 'unknown')
        files_updated = results.get('files_updated', 0)
        files_skipped = results.get('files_skipped', 0)
        files_failed = results.get('files_failed', 0)
        discovered_duplicates = results.get('discovered_duplicates', [])
        dup_count = len(discovered_duplicates)

        if status == 'completed':
            status_text = f"Complete: {files_updated} updated, {files_skipped} skipped, {files_failed} failed"
            if dup_count > 0:
                status_text += f", {dup_count} duplicates discovered"
            self.video_backfill_status_label.setText(status_text)

            if files_updated > 0 or dup_count > 0:
                message = (
                    f"Video content hash calculation complete!\n\n"
                    f"Videos updated: {files_updated}\n"
                    f"Videos skipped (missing/failed): {files_skipped}\n"
                    f"Videos failed: {files_failed}"
                )

                if dup_count > 0:
                    message += f"\n\nDiscovered {dup_count} video content duplicate(s)!\n"
                    message += "These are videos with identical visual content but different file hashes.\n\n"

                    # Show up to 5 examples
                    examples = discovered_duplicates[:5]
                    for dup in examples:
                        file_name = os.path.basename(dup['file_path'])
                        dup_of_name = os.path.basename(dup['duplicate_of_path'])
                        message += f"  - {file_name} matches {dup_of_name}\n"

                    if dup_count > 5:
                        message += f"  ... and {dup_count - 5} more\n"

                    message += "\nYou can find these in the database by querying files with the same video_content_hash."

                QMessageBox.information(self, "Video Backfill Complete", message)

        elif status == 'cancelled':
            status_text = f"Cancelled: {files_updated} videos updated before cancellation"
            if dup_count > 0:
                status_text += f", {dup_count} duplicates discovered"
            self.video_backfill_status_label.setText(status_text)
        else:
            self.video_backfill_status_label.setText(f"Failed: {results.get('error', 'Unknown error')}")

        self._video_backfill_worker = None

    def _on_video_backfill_error(self, error_msg):
        """Handle video backfill error."""
        self.video_backfill_btn.setEnabled(True)
        self.cancel_video_backfill_btn.hide()
        self.video_backfill_progress.hide()
        self.video_backfill_status_label.setText(f"Error: {error_msg}")

        QMessageBox.critical(
            self, "Video Backfill Error",
            f"Video content hash calculation failed:\n\n{error_msg}"
        )

        self._video_backfill_worker = None

    def cleanup_workers(self):
        """
        Stop and wait for any running worker threads.

        Called by main window before closing to prevent
        'QThread destroyed while thread is still running' errors.
        """
        if self._backfill_worker and self._backfill_worker.isRunning():
            logger.info("Stopping content hash backfill worker before close...")
            self._backfill_worker.stop()
            self._backfill_worker.wait()
            logger.info("Content hash backfill worker stopped")

        if self._video_backfill_worker and self._video_backfill_worker.isRunning():
            logger.info("Stopping video content hash backfill worker before close...")
            self._video_backfill_worker.stop()
            self._video_backfill_worker.wait()
            logger.info("Video content hash backfill worker stopped")
