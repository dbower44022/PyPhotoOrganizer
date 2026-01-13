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
                               QButtonGroup)
from PySide6.QtCore import Qt
import json
import os
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

    def set_database(self, db_metadata):
        """Set the database metadata and update UI."""
        self.db_metadata = db_metadata

        if db_metadata is None:
            self.db_name_label.setText("No database loaded")
            self.db_file_label.setText("-")
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

            created = metadata.get('created_date', '-')
            if created and created != '-':
                self.db_created_label.setText(created)
            else:
                self.db_created_label.setText("-")

            last_used = metadata.get('last_used_date', '-')
            if last_used and last_used != '-':
                self.db_last_used_label.setText(last_used)
            else:
                self.db_last_used_label.setText("-")

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

        # Load retention settings
        self.load_retention_settings()

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
