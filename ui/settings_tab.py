"""
Settings Tab for PyPhotoOrganizer GUI

Advanced configuration management.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QCheckBox, QSpinBox, QLineEdit, QPushButton,
                               QLabel, QListWidget, QMessageBox, QScrollArea,
                               QFormLayout)
from PySide6.QtCore import Qt
import json
import os
import constants
from config import Config


class SettingsTab(QWidget):
    """Tab for managing application settings."""

    def __init__(self):
        super().__init__()
        self.settings_file = "settings.json"
        self.init_ui()
        self.load_from_file()

    def init_ui(self):
        """Initialize the user interface."""
        # Create scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        # Main widget for scroll area
        main_widget = QWidget()
        layout = QVBoxLayout()

        # File Processing Settings
        file_group = QGroupBox("File Processing Settings")
        file_layout = QFormLayout()

        self.include_subdirs_check = QCheckBox()
        self.include_subdirs_check.setChecked(True)
        file_layout.addRow("Include subdirectories:", self.include_subdirs_check)

        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(10, 1000)
        self.batch_size_spin.setValue(constants.DEFAULT_BATCH_SIZE)
        file_layout.addRow("Batch size:", self.batch_size_spin)

        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Organization Settings
        org_group = QGroupBox("Organization Settings")
        org_layout = QFormLayout()

        self.group_by_year_check = QCheckBox()
        self.group_by_year_check.setChecked(True)
        self.group_by_year_check.stateChanged.connect(self.update_folder_preview)
        org_layout.addRow("Group by year:", self.group_by_year_check)

        self.group_by_day_check = QCheckBox()
        self.group_by_day_check.setChecked(True)
        self.group_by_day_check.stateChanged.connect(self.update_folder_preview)
        org_layout.addRow("Group by day:", self.group_by_day_check)

        self.folder_preview_label = QLabel()
        self.folder_preview_label.setStyleSheet("font-style: italic; color: gray;")
        org_layout.addRow("Folder structure:", self.folder_preview_label)
        self.update_folder_preview()

        org_group.setLayout(org_layout)
        layout.addWidget(org_group)

        # Performance Settings
        perf_group = QGroupBox("Performance Settings")
        perf_layout = QFormLayout()

        self.partial_hash_check = QCheckBox()
        self.partial_hash_check.setChecked(True)
        perf_layout.addRow("Partial hash enabled:", self.partial_hash_check)

        self.partial_hash_bytes_spin = QSpinBox()
        self.partial_hash_bytes_spin.setRange(1024, 65536)
        self.partial_hash_bytes_spin.setValue(constants.PARTIAL_HASH_BYTES)
        perf_layout.addRow("Partial hash bytes:", self.partial_hash_bytes_spin)

        self.partial_hash_min_size_spin = QSpinBox()
        self.partial_hash_min_size_spin.setRange(100, 10000)
        self.partial_hash_min_size_spin.setValue(
            constants.PARTIAL_HASH_MIN_FILE_SIZE // 1024)  # Convert to KB
        self.partial_hash_min_size_spin.setSuffix(" KB")
        perf_layout.addRow("Partial hash min size:", self.partial_hash_min_size_spin)

        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # Photo Filtering Settings
        filter_group = QGroupBox("Photo Filtering Settings")
        filter_layout = QFormLayout()

        self.photo_filter_check = QCheckBox()
        self.photo_filter_check.setChecked(True)
        filter_layout.addRow("Enable photo filter:", self.photo_filter_check)

        self.min_file_size_spin = QSpinBox()
        self.min_file_size_spin.setRange(1, 1000)
        self.min_file_size_spin.setValue(constants.MIN_PHOTO_FILE_SIZE // 1024)
        self.min_file_size_spin.setSuffix(" KB")
        filter_layout.addRow("Min file size:", self.min_file_size_spin)

        self.min_width_spin = QSpinBox()
        self.min_width_spin.setRange(100, 10000)
        self.min_width_spin.setValue(constants.MIN_PHOTO_WIDTH)
        filter_layout.addRow("Min width:", self.min_width_spin)

        self.min_height_spin = QSpinBox()
        self.min_height_spin.setRange(100, 10000)
        self.min_height_spin.setValue(constants.MIN_PHOTO_HEIGHT)
        filter_layout.addRow("Min height:", self.min_height_spin)

        self.max_width_spin = QSpinBox()
        self.max_width_spin.setRange(1000, 100000)
        self.max_width_spin.setValue(constants.MAX_PHOTO_WIDTH)
        filter_layout.addRow("Max width:", self.max_width_spin)

        self.max_height_spin = QSpinBox()
        self.max_height_spin.setRange(1000, 100000)
        self.max_height_spin.setValue(constants.MAX_PHOTO_HEIGHT)
        filter_layout.addRow("Max height:", self.max_height_spin)

        self.exclude_square_spin = QSpinBox()
        self.exclude_square_spin.setRange(100, 1000)
        self.exclude_square_spin.setValue(constants.MIN_SQUARE_SIZE)
        filter_layout.addRow("Exclude squares smaller than:", self.exclude_square_spin)

        self.require_exif_check = QCheckBox()
        self.require_exif_check.setChecked(False)
        filter_layout.addRow("Require EXIF data:", self.require_exif_check)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Filename Pattern Filtering
        pattern_group = QGroupBox("Filename Pattern Filtering")
        pattern_layout = QVBoxLayout()

        # Description
        pattern_desc = QLabel(
            "Files containing these patterns in their filename will be filtered out.\n"
            "Common examples: favicon, icon, logo, thumbnail, etc."
        )
        pattern_desc.setWordWrap(True)
        pattern_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        pattern_layout.addWidget(pattern_desc)

        # Enable/disable checkbox
        self.filename_filter_check = QCheckBox("Enable filename pattern filtering")
        self.filename_filter_check.setChecked(True)
        self.filename_filter_check.stateChanged.connect(self.update_pattern_controls)
        pattern_layout.addWidget(self.filename_filter_check)

        # Pattern list
        pattern_list_layout = QHBoxLayout()

        # List widget
        list_container = QVBoxLayout()
        list_container.addWidget(QLabel("Excluded Patterns:"))
        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(150)
        list_container.addWidget(self.pattern_list)
        pattern_list_layout.addLayout(list_container)

        # Control buttons
        pattern_buttons = QVBoxLayout()

        self.add_pattern_input = QLineEdit()
        self.add_pattern_input.setPlaceholderText("Enter pattern to exclude...")
        pattern_buttons.addWidget(self.add_pattern_input)

        self.add_pattern_btn = QPushButton("Add Pattern")
        self.add_pattern_btn.clicked.connect(self.add_pattern)
        pattern_buttons.addWidget(self.add_pattern_btn)

        self.remove_pattern_btn = QPushButton("Remove Selected")
        self.remove_pattern_btn.clicked.connect(self.remove_pattern)
        pattern_buttons.addWidget(self.remove_pattern_btn)

        self.default_patterns_btn = QPushButton("Restore Default Patterns")
        self.default_patterns_btn.clicked.connect(self.restore_default_patterns)
        pattern_buttons.addWidget(self.default_patterns_btn)

        pattern_buttons.addStretch()
        pattern_list_layout.addLayout(pattern_buttons)

        pattern_layout.addLayout(pattern_list_layout)

        # Statistics label
        self.pattern_count_label = QLabel()
        self.pattern_count_label.setStyleSheet("font-style: italic; color: gray;")
        pattern_layout.addWidget(self.pattern_count_label)

        pattern_group.setLayout(pattern_layout)
        layout.addWidget(pattern_group)

        # Buttons
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

        layout.addLayout(button_layout)

        layout.addStretch()
        main_widget.setLayout(layout)
        scroll.setWidget(main_widget)

        # Set scroll area as main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

        # Initialize pattern count
        self.update_pattern_count()

    def update_pattern_controls(self):
        """Enable/disable pattern controls based on checkbox."""
        enabled = self.filename_filter_check.isChecked()
        self.pattern_list.setEnabled(enabled)
        self.add_pattern_input.setEnabled(enabled)
        self.add_pattern_btn.setEnabled(enabled)
        self.remove_pattern_btn.setEnabled(enabled)
        self.default_patterns_btn.setEnabled(enabled)

    def add_pattern(self):
        """Add a new pattern to the list."""
        pattern = self.add_pattern_input.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Empty Pattern",
                              "Please enter a pattern to add.")
            return

        # Check if already exists
        for i in range(self.pattern_list.count()):
            if self.pattern_list.item(i).text().lower() == pattern.lower():
                QMessageBox.information(self, "Pattern Exists",
                                      f"Pattern '{pattern}' already exists in the list.")
                return

        # Add to list
        self.pattern_list.addItem(pattern)
        self.add_pattern_input.clear()
        self.update_pattern_count()

    def remove_pattern(self):
        """Remove selected pattern from the list."""
        current_item = self.pattern_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection",
                                  "Please select a pattern to remove.")
            return

        # Remove the selected item
        row = self.pattern_list.row(current_item)
        self.pattern_list.takeItem(row)
        self.update_pattern_count()

    def restore_default_patterns(self):
        """Restore default filename patterns."""
        reply = QMessageBox.question(
            self,
            "Restore Defaults",
            "This will replace all current patterns with the default patterns.\n\n"
            "Are you sure?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self.pattern_list.clear()
            for pattern in constants.DEFAULT_EXCLUDED_PATTERNS:
                self.pattern_list.addItem(pattern)
            self.update_pattern_count()

    def update_pattern_count(self):
        """Update the pattern count label."""
        count = self.pattern_list.count()
        self.pattern_count_label.setText(f"Total patterns: {count}")

    def update_folder_preview(self):
        """Update folder structure preview."""
        group_by_year = self.group_by_year_check.isChecked()
        group_by_day = self.group_by_day_check.isChecked()

        if group_by_year and group_by_day:
            preview = "2024/11/25/photo.jpg"
        elif group_by_year and not group_by_day:
            preview = "2024/11/photo.jpg"
        elif not group_by_year and group_by_day:
            preview = "2024-11/25/photo.jpg"
        else:
            preview = "2024-11/photo.jpg"

        self.folder_preview_label.setText(preview)

    def get_config(self):
        """Get configuration as dictionary."""
        # Get excluded patterns from list widget
        excluded_patterns = []
        if self.filename_filter_check.isChecked():
            for i in range(self.pattern_list.count()):
                excluded_patterns.append(self.pattern_list.item(i).text())

        config = {
            'include_subdirectories': self.include_subdirs_check.isChecked(),
            'batch_size': self.batch_size_spin.value(),
            'group_by_year': self.group_by_year_check.isChecked(),
            'group_by_day': self.group_by_day_check.isChecked(),
            'partial_hash_enabled': self.partial_hash_check.isChecked(),
            'partial_hash_bytes': self.partial_hash_bytes_spin.value(),
            'partial_hash_min_file_size': self.partial_hash_min_size_spin.value() * 1024,
            'photo_filter_enabled': self.photo_filter_check.isChecked(),
            'min_file_size': self.min_file_size_spin.value() * 1024,
            'min_width': self.min_width_spin.value(),
            'min_height': self.min_height_spin.value(),
            'max_width': self.max_width_spin.value(),
            'max_height': self.max_height_spin.value(),
            'exclude_square_smaller_than': self.exclude_square_spin.value(),
            'require_exif': self.require_exif_check.isChecked(),
            'database_path': constants.DEFAULT_DATABASE_NAME,
            'file_endings': constants.DEFAULT_FILE_ENDINGS,
            'excluded_filename_patterns': excluded_patterns,
            'move_filtered_files': False,
            'filtered_files_folder': "filtered_non_photos"
        }
        return config

    def set_config(self, config):
        """Set configuration from dictionary."""
        self.include_subdirs_check.setChecked(config.get('include_subdirectories', True))
        self.batch_size_spin.setValue(config.get('batch_size', constants.DEFAULT_BATCH_SIZE))
        self.group_by_year_check.setChecked(config.get('group_by_year', True))
        self.group_by_day_check.setChecked(config.get('group_by_day', True))
        self.partial_hash_check.setChecked(config.get('partial_hash_enabled', True))
        self.partial_hash_bytes_spin.setValue(
            config.get('partial_hash_bytes', constants.PARTIAL_HASH_BYTES))
        self.partial_hash_min_size_spin.setValue(
            config.get('partial_hash_min_file_size', constants.PARTIAL_HASH_MIN_FILE_SIZE) // 1024)
        self.photo_filter_check.setChecked(config.get('photo_filter_enabled', True))
        self.min_file_size_spin.setValue(
            config.get('min_file_size', constants.MIN_PHOTO_FILE_SIZE) // 1024)
        self.min_width_spin.setValue(config.get('min_width', constants.MIN_PHOTO_WIDTH))
        self.min_height_spin.setValue(config.get('min_height', constants.MIN_PHOTO_HEIGHT))
        self.max_width_spin.setValue(config.get('max_width', constants.MAX_PHOTO_WIDTH))
        self.max_height_spin.setValue(config.get('max_height', constants.MAX_PHOTO_HEIGHT))
        self.exclude_square_spin.setValue(
            config.get('exclude_square_smaller_than', constants.MIN_SQUARE_SIZE))
        self.require_exif_check.setChecked(config.get('require_exif', False))

        # Load excluded patterns
        patterns = config.get('excluded_filename_patterns', constants.DEFAULT_EXCLUDED_PATTERNS)
        self.pattern_list.clear()
        for pattern in patterns:
            self.pattern_list.addItem(pattern)

        # Enable/disable filename filtering (default: True if patterns exist)
        has_patterns = len(patterns) > 0
        self.filename_filter_check.setChecked(has_patterns)
        self.update_pattern_controls()
        self.update_pattern_count()

        self.update_folder_preview()

    def load_from_file(self):
        """Load settings from file."""
        if not os.path.exists(self.settings_file):
            QMessageBox.information(self, "No Settings File",
                                   f"{self.settings_file} not found. Using defaults.")
            self.restore_defaults()
            return

        try:
            with open(self.settings_file, 'r') as f:
                config = json.load(f)
            self.set_config(config)
            QMessageBox.information(self, "Settings Loaded",
                                   "Settings loaded successfully from file.")
        except Exception as e:
            QMessageBox.critical(self, "Load Error",
                               f"Failed to load settings:\n\n{str(e)}")

    def save_to_file(self):
        """Save settings to file."""
        try:
            # Get current config
            config = self.get_config()

            # Load existing settings to preserve source/dest folders
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    existing = json.load(f)
                config['source_directory'] = existing.get('source_directory', [])
                config['destination_directory'] = existing.get('destination_directory', "")
                config['copy_files'] = existing.get('copy_files', True)
                config['move_files'] = existing.get('move_files', False)

            # Validate
            try:
                Config(config)
            except Exception as e:
                QMessageBox.critical(self, "Validation Error",
                                   f"Invalid settings:\n\n{str(e)}")
                return

            # Save
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
            'include_subdirectories': True,
            'batch_size': constants.DEFAULT_BATCH_SIZE,
            'group_by_year': True,
            'group_by_day': True,
            'partial_hash_enabled': True,
            'partial_hash_bytes': constants.PARTIAL_HASH_BYTES,
            'partial_hash_min_file_size': constants.PARTIAL_HASH_MIN_FILE_SIZE,
            'photo_filter_enabled': True,
            'min_file_size': constants.MIN_PHOTO_FILE_SIZE,
            'min_width': constants.MIN_PHOTO_WIDTH,
            'min_height': constants.MIN_PHOTO_HEIGHT,
            'max_width': constants.MAX_PHOTO_WIDTH,
            'max_height': constants.MAX_PHOTO_HEIGHT,
            'exclude_square_smaller_than': constants.MIN_SQUARE_SIZE,
            'require_exif': False,
            'excluded_filename_patterns': constants.DEFAULT_EXCLUDED_PATTERNS
        }
        self.set_config(config)
        QMessageBox.information(self, "Defaults Restored",
                               "Settings restored to default values.")

    def validate_settings(self):
        """Validate current settings."""
        try:
            config = self.get_config()
            # Add dummy source/dest for validation
            config['source_directory'] = ["/dummy/path"]
            config['destination_directory'] = "/dummy/path"
            config['copy_files'] = True
            config['move_files'] = False

            Config(config)
            QMessageBox.information(self, "Validation Successful",
                                   "All settings are valid.")
        except Exception as e:
            QMessageBox.critical(self, "Validation Failed",
                               f"Invalid settings:\n\n{str(e)}")
