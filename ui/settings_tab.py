"""
Settings Tab for PyPhotoOrganizer GUI

Advanced configuration management.
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QCheckBox, QSpinBox, QLineEdit, QPushButton,
                               QLabel, QListWidget, QMessageBox, QScrollArea,
                               QFormLayout, QComboBox, QTextEdit, QRadioButton,
                               QButtonGroup)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import json
import os
import constants
from config import Config
from organization_template import OrganizationTemplate


class SettingsTab(QWidget):
    """Tab for managing application settings."""

    def __init__(self):
        super().__init__()
        self.settings_file = "settings.json"
        self.db_metadata = None  # Will be set when database is loaded
        self.current_template = '{YYYY}/{MM}/{DD}'  # Default organization template
        self.current_filename_template = '{original_name}'  # Default filename template
        self.init_ui()
        self.load_from_file(show_dialog=False)  # Suppress dialog during initialization

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
        org_layout = QVBoxLayout()

        # Preset dropdown
        preset_layout = QFormLayout()
        self.org_preset_combo = QComboBox()
        # Get preset names from OrganizationTemplate to ensure they match
        preset_names = OrganizationTemplate.get_preset_names()
        preset_names.append("Custom Template...")
        self.org_preset_combo.addItems(preset_names)
        self.org_preset_combo.currentTextChanged.connect(self.on_preset_changed)
        preset_layout.addRow("Folder Structure:", self.org_preset_combo)
        org_layout.addLayout(preset_layout)

        # Custom template editor (hidden by default)
        self.custom_template_widget = QWidget()
        custom_layout = QVBoxLayout()
        custom_layout.setContentsMargins(0, 0, 0, 0)

        custom_label = QLabel("Custom Template:")
        custom_label.setStyleSheet("font-weight: bold;")
        custom_layout.addWidget(custom_label)

        self.custom_template_edit = QLineEdit()
        self.custom_template_edit.setPlaceholderText("Example: {year}/{month}-{month_sname}/{day}-{day_sname}")
        self.custom_template_edit.textChanged.connect(self.on_custom_template_changed)
        custom_layout.addWidget(self.custom_template_edit)

        # Helper buttons for placeholders (updated to new naming convention)
        helper_layout = QHBoxLayout()
        helper_label = QLabel("Quick Insert:")
        helper_layout.addWidget(helper_label)

        placeholder_buttons = [
            ("year", "{year}"),
            ("month", "{month}"),
            ("day", "{day}"),
            ("month-name", "{month}-{month_sname}"),
            ("day-name", "{day}-{day_sname}"),
        ]

        for btn_label, placeholder in placeholder_buttons:
            btn = QPushButton(btn_label)
            btn.setMaximumWidth(90)
            btn.clicked.connect(lambda checked, p=placeholder: self.insert_placeholder(p))
            helper_layout.addWidget(btn)

        helper_layout.addStretch()
        custom_layout.addLayout(helper_layout)

        # Available Variables help text
        help_label = QLabel("Available Variables (case-insensitive):")
        help_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        custom_layout.addWidget(help_label)

        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(130)
        help_text.setHtml("""
            <table style='font-size: 9pt;'>
            <tr><td style='padding: 2px;'><b>{year}</b></td><td style='padding: 2px;'>- Four-digit year (e.g., 2025)</td></tr>
            <tr><td style='padding: 2px;'><b>{month}, {day}</b></td><td style='padding: 2px;'>- Zero-padded month/day (e.g., 02, 03)</td></tr>
            <tr><td style='padding: 2px;'><b>{month_name}, {day_name}</b></td><td style='padding: 2px;'>- Full names (e.g., February, Monday)</td></tr>
            <tr><td style='padding: 2px;'><b>{month_sname}, {day_sname}</b></td><td style='padding: 2px;'>- Short names (e.g., Feb, Mon)</td></tr>
            <tr><td style='padding: 2px;'><b>{month}-{month_sname}</b></td><td style='padding: 2px;'>- Combined format (e.g., 02-Feb)</td></tr>
            <tr><td style='padding: 2px;'><b>{day}-{day_sname}</b></td><td style='padding: 2px;'>- Combined format (e.g., 03-Mon)</td></tr>
            </table>
            <p style='font-size: 8pt; color: #666; margin-top: 5px;'>
            All variables are case-insensitive ({year}, {YEAR}, {Year} work the same).<br>
            Legacy placeholders ({YYYY}, {MM}, {DD}, etc.) still supported.
            </p>
        """)
        custom_layout.addWidget(help_text)

        # Validation message
        self.template_validation_label = QLabel()
        self.template_validation_label.setWordWrap(True)
        custom_layout.addWidget(self.template_validation_label)

        self.custom_template_widget.setLayout(custom_layout)
        self.custom_template_widget.hide()  # Hidden by default
        org_layout.addWidget(self.custom_template_widget)

        # Preview panel
        preview_widget = QWidget()
        preview_widget.setStyleSheet("background-color: #f5f5f5; border: 1px solid #ddd; border-radius: 3px;")
        preview_layout = QVBoxLayout()
        preview_layout.setContentsMargins(10, 10, 10, 10)

        preview_title = QLabel("Preview:")
        preview_title.setStyleSheet("font-weight: bold;")
        preview_layout.addWidget(preview_title)

        self.org_description_label = QLabel()
        self.org_description_label.setWordWrap(True)
        self.org_description_label.setStyleSheet("color: #555; margin-bottom: 5px;")
        preview_layout.addWidget(self.org_description_label)

        examples_label = QLabel("Example paths:")
        examples_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        preview_layout.addWidget(examples_label)

        self.org_preview_label = QLabel()
        self.org_preview_label.setWordWrap(True)
        self.org_preview_label.setStyleSheet("font-family: monospace; color: #333;")
        preview_layout.addWidget(self.org_preview_label)

        preview_widget.setLayout(preview_layout)
        org_layout.addWidget(preview_widget)

        # Lock warning (shown when archive has files)
        self.org_lock_warning = QLabel()
        self.org_lock_warning.setWordWrap(True)
        self.org_lock_warning.setStyleSheet("color: #d9534f; background-color: #f2dede; padding: 8px; border-radius: 3px;")
        self.org_lock_warning.hide()
        org_layout.addWidget(self.org_lock_warning)

        self.reorganize_btn = QPushButton("Reorganize Archive...")
        self.reorganize_btn.setStyleSheet("background-color: #f0ad4e; color: white; font-weight: bold;")
        self.reorganize_btn.hide()
        self.reorganize_btn.clicked.connect(self.on_reorganize_clicked)
        org_layout.addWidget(self.reorganize_btn)

        org_group.setLayout(org_layout)
        layout.addWidget(org_group)

        # File Type Organization Settings
        file_type_group = QGroupBox("File Type Organization")
        file_type_layout = QVBoxLayout()

        file_type_label = QLabel("How should videos be organized?")
        file_type_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        file_type_layout.addWidget(file_type_label)

        self.file_type_button_group = QButtonGroup()

        self.file_type_combined_radio = QRadioButton("Same folders as photos")
        self.file_type_combined_radio.setToolTip("Photos and videos in the same date folders")
        self.file_type_button_group.addButton(self.file_type_combined_radio, 0)
        file_type_layout.addWidget(self.file_type_combined_radio)

        combined_example = QLabel("  Example: 2025/02-Feb/03-Tue/photo.jpg\n"
                                  "           2025/02-Feb/03-Tue/video.mp4")
        combined_example.setStyleSheet("color: gray; font-size: 10px; margin-left: 20px; margin-bottom: 5px;")
        file_type_layout.addWidget(combined_example)

        self.file_type_subfolder_radio = QRadioButton("Separate subfolder under date folder")
        self.file_type_subfolder_radio.setToolTip("Videos in Videos/ subfolder, photos in Photos/ subfolder")
        self.file_type_button_group.addButton(self.file_type_subfolder_radio, 1)
        file_type_layout.addWidget(self.file_type_subfolder_radio)

        subfolder_example = QLabel("  Example: 2025/02-Feb/03-Tue/Photos/photo.jpg\n"
                                   "           2025/02-Feb/03-Tue/Videos/video.mp4")
        subfolder_example.setStyleSheet("color: gray; font-size: 10px; margin-left: 20px; margin-bottom: 5px;")
        file_type_layout.addWidget(subfolder_example)

        self.file_type_separate_radio = QRadioButton("Completely separate archive location")
        self.file_type_separate_radio.setToolTip("Videos stored in a different archive location")
        self.file_type_button_group.addButton(self.file_type_separate_radio, 2)
        file_type_layout.addWidget(self.file_type_separate_radio)

        separate_example = QLabel("  Photos: /archive/photos/2025/02-Feb/03-Tue/photo.jpg\n"
                                  "  Videos: /archive/videos/2025/02-Feb/03-Tue/video.mp4")
        separate_example.setStyleSheet("color: gray; font-size: 10px; margin-left: 20px; margin-bottom: 5px;")
        file_type_layout.addWidget(separate_example)

        # Video archive location widget (shown only when "Separate archive" is selected)
        self.video_archive_widget = QWidget()
        video_archive_layout = QHBoxLayout()
        video_archive_layout.setContentsMargins(20, 5, 0, 5)

        video_archive_label = QLabel("Video Archive Location:")
        video_archive_layout.addWidget(video_archive_label)

        self.video_archive_path_edit = QLineEdit()
        self.video_archive_path_edit.setPlaceholderText("Select folder for video archive...")
        self.video_archive_path_edit.setMinimumWidth(300)
        video_archive_layout.addWidget(self.video_archive_path_edit)

        self.video_archive_browse_btn = QPushButton("Browse...")
        self.video_archive_browse_btn.clicked.connect(self.on_browse_video_archive)
        video_archive_layout.addWidget(self.video_archive_browse_btn)

        video_archive_layout.addStretch()
        self.video_archive_widget.setLayout(video_archive_layout)
        self.video_archive_widget.hide()  # Hidden by default
        file_type_layout.addWidget(self.video_archive_widget)

        # Set default
        self.file_type_combined_radio.setChecked(True)

        # Connect radio buttons to check organization lock and update video archive visibility
        self.file_type_combined_radio.toggled.connect(self.on_file_type_changed)
        self.file_type_subfolder_radio.toggled.connect(self.on_file_type_changed)
        self.file_type_separate_radio.toggled.connect(self.on_file_type_changed)

        file_type_group.setLayout(file_type_layout)
        layout.addWidget(file_type_group)

        # Update preview with default preset
        self.update_organization_preview()

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

        # File Renaming Settings
        rename_group = QGroupBox("File Renaming")
        rename_layout = QVBoxLayout()

        # Enable/disable checkbox
        self.enable_rename_check = QCheckBox("Enable file renaming during processing")
        self.enable_rename_check.setToolTip("When enabled, files will be renamed according to the template below")
        self.enable_rename_check.stateChanged.connect(self.on_rename_enabled_changed)
        rename_layout.addWidget(self.enable_rename_check)

        # Template input
        template_label = QLabel("Filename Template:")
        template_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        rename_layout.addWidget(template_label)

        self.filename_template_edit = QLineEdit()
        self.filename_template_edit.setPlaceholderText("{year}{month}{day}_{original_name_no_ext}")
        self.filename_template_edit.textChanged.connect(self.on_filename_template_changed)
        rename_layout.addWidget(self.filename_template_edit)

        # Preview section
        preview_layout = QHBoxLayout()
        preview_layout.addWidget(QLabel("Preview:"))
        self.rename_preview_label = QLabel("IMG_1234.jpg")
        self.rename_preview_label.setStyleSheet("color: blue; font-weight: bold;")
        preview_layout.addWidget(self.rename_preview_label)
        preview_layout.addStretch()
        rename_layout.addLayout(preview_layout)

        # Example layout
        example_layout = QHBoxLayout()
        example_layout.addWidget(QLabel("Original:"))
        example_orig_label = QLabel("IMG_1234.jpg")
        example_orig_label.setStyleSheet("color: gray;")
        example_layout.addWidget(example_orig_label)
        example_layout.addWidget(QLabel(" → "))
        example_layout.addWidget(QLabel("Renamed:"))
        self.rename_example_label = QLabel("20250203_IMG_1234.jpg")
        self.rename_example_label.setStyleSheet("color: green; font-weight: bold;")
        example_layout.addWidget(self.rename_example_label)
        example_layout.addStretch()
        rename_layout.addLayout(example_layout)

        # Validation message
        self.rename_validation_label = QLabel()
        self.rename_validation_label.setStyleSheet("color: red; font-style: italic;")
        self.rename_validation_label.setWordWrap(True)
        rename_layout.addWidget(self.rename_validation_label)

        # Help text
        help_label = QLabel("Available Variables (case-insensitive):")
        help_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        rename_layout.addWidget(help_label)

        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setMaximumHeight(170)
        help_text.setHtml("""
            <table style='font-size: 9pt;'>
            <tr><td style='padding: 2px;'><b>{year}, {month}, {day}</b></td><td style='padding: 2px;'>- Date components (e.g., 2025, 02, 03)</td></tr>
            <tr><td style='padding: 2px;'><b>{month_name}, {day_name}</b></td><td style='padding: 2px;'>- Month/day full names (e.g., February, Monday)</td></tr>
            <tr><td style='padding: 2px;'><b>{month_sname}, {day_sname}</b></td><td style='padding: 2px;'>- Month/day short names (e.g., Feb, Mon)</td></tr>
            <tr><td style='padding: 2px;'><b>{hour}, {minute}, {second}</b></td><td style='padding: 2px;'>- Time components (e.g., 14, 30, 15)</td></tr>
            <tr><td style='padding: 2px;'><b>{original_name}</b></td><td style='padding: 2px;'>- Full original filename</td></tr>
            <tr><td style='padding: 2px;'><b>{original_name_no_ext}</b></td><td style='padding: 2px;'>- Filename without extension</td></tr>
            <tr><td style='padding: 2px;'><b>{ext}</b></td><td style='padding: 2px;'>- File extension (.jpg, .png, etc.)</td></tr>
            <tr><td style='padding: 2px;'><b>{folder_name}</b></td><td style='padding: 2px;'>- Immediate parent folder name</td></tr>
            <tr><td style='padding: 2px;'><b>{parent_folder_name}</b></td><td style='padding: 2px;'>- Grandparent folder name</td></tr>
            <tr><td style='padding: 2px;'><b>{counter}</b> or <b>{counter:04d}</b></td><td style='padding: 2px;'>- Sequential number (1, 2, 3 or 0001, 0002, 0003)</td></tr>
            </table>
            <p style='font-size: 8pt; color: #666; margin-top: 5px;'>All variables are case-insensitive ({year}, {YEAR}, {Year} work the same).</p>
        """)
        rename_layout.addWidget(help_text)

        # Restore default button
        restore_rename_btn = QPushButton("Restore Default: {original_name}")
        restore_rename_btn.clicked.connect(self.restore_default_filename_template)
        rename_layout.addWidget(restore_rename_btn)

        # Warning label for rename template changes (similar to organization template)
        self.rename_lock_warning = QLabel()
        self.rename_lock_warning.setWordWrap(True)
        self.rename_lock_warning.setStyleSheet("""
            QLabel {
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 4px;
                padding: 10px;
                color: #856404;
                margin-top: 10px;
            }
        """)
        self.rename_lock_warning.hide()
        rename_layout.addWidget(self.rename_lock_warning)

        # Reorganize button for rename template
        self.rename_reorganize_btn = QPushButton("Reorganize Files with New Template")
        self.rename_reorganize_btn.setStyleSheet("""
            QPushButton {
                background-color: #ffc107;
                color: #000;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #e0a800;
            }
        """)
        self.rename_reorganize_btn.clicked.connect(self.on_rename_reorganize_clicked)
        self.rename_reorganize_btn.hide()
        rename_layout.addWidget(self.rename_reorganize_btn)

        rename_group.setLayout(rename_layout)
        layout.addWidget(rename_group)

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

        # Audit Retention Settings
        retention_group = QGroupBox("Import History Retention")
        retention_layout = QVBoxLayout()

        # Description
        retention_desc = QLabel(
            "Configure how long import history records are kept. "
            "Older sessions and their file logs will be automatically cleaned up."
        )
        retention_desc.setWordWrap(True)
        retention_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        retention_layout.addWidget(retention_desc)

        # Retention mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Retention Mode:"))
        self.retention_mode_combo = QComboBox()
        self.retention_mode_combo.addItems(["Keep All", "Keep Last N Sessions", "Keep Last N Days"])
        self.retention_mode_combo.currentIndexChanged.connect(self.on_retention_mode_changed)
        mode_layout.addWidget(self.retention_mode_combo)
        mode_layout.addStretch()
        retention_layout.addLayout(mode_layout)

        # Session count/days input
        count_layout = QHBoxLayout()
        self.retention_count_label = QLabel("Sessions to keep:")
        count_layout.addWidget(self.retention_count_label)
        self.retention_count_spin = QSpinBox()
        self.retention_count_spin.setRange(1, 1000)
        self.retention_count_spin.setValue(50)
        count_layout.addWidget(self.retention_count_spin)
        count_layout.addStretch()
        retention_layout.addLayout(count_layout)

        # Auto-cleanup checkbox
        self.auto_cleanup_check = QCheckBox("Enable automatic cleanup on startup")
        self.auto_cleanup_check.setToolTip("When enabled, old sessions will be deleted automatically when the application starts")
        retention_layout.addWidget(self.auto_cleanup_check)

        # Manual cleanup button
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

    def on_preset_changed(self, preset_name):
        """Handle preset selection change."""
        # Show/hide custom template editor
        if preset_name == "Custom Template...":
            self.custom_template_widget.show()
            # Use current custom template or default
            if not self.custom_template_edit.text():
                self.custom_template_edit.setText(self.current_template)
        else:
            self.custom_template_widget.hide()
            # Load template from preset
            preset = OrganizationTemplate.get_preset_by_name(preset_name)
            if preset:
                self.current_template = preset['template']

        # Update preview
        self.update_organization_preview()

        # Check if organization is locked
        self.check_organization_lock()

    def on_custom_template_changed(self, text):
        """Validate and update preview for custom template."""
        if not text.strip():
            self.template_validation_label.setText("")
            return

        # Validate template
        is_valid, error_msg = OrganizationTemplate.validate(text)

        if is_valid:
            self.template_validation_label.setText("✓ Valid template")
            self.template_validation_label.setStyleSheet("color: green; font-weight: bold;")
            self.current_template = text
            self.update_organization_preview()
        else:
            self.template_validation_label.setText(f"✗ {error_msg}")
            self.template_validation_label.setStyleSheet("color: red; font-weight: bold;")

        # Check if organization is locked
        self.check_organization_lock()

    def insert_placeholder(self, placeholder):
        """Insert placeholder at cursor position in custom template."""
        cursor_pos = self.custom_template_edit.cursorPosition()
        current_text = self.custom_template_edit.text()
        new_text = current_text[:cursor_pos] + placeholder + current_text[cursor_pos:]
        self.custom_template_edit.setText(new_text)
        # Move cursor after inserted placeholder
        self.custom_template_edit.setCursorPosition(cursor_pos + len(placeholder))
        self.custom_template_edit.setFocus()

    def update_organization_preview(self):
        """Generate and display example paths."""
        # Validate current template
        is_valid, error_msg = OrganizationTemplate.validate(self.current_template)

        if not is_valid:
            self.org_description_label.setText(f"Invalid template: {error_msg}")
            self.org_preview_label.setText("")
            return

        # Get description
        description = OrganizationTemplate.format_description(self.current_template)
        self.org_description_label.setText(description)

        # Generate examples
        examples = OrganizationTemplate.generate_examples(self.current_template)
        example_text = "\n".join(examples)
        self.org_preview_label.setText(example_text)

    def check_organization_lock(self):
        """Check if organization settings are locked and show warning."""
        if self.db_metadata is None:
            self.org_lock_warning.hide()
            self.reorganize_btn.hide()
            return

        # Get metadata to check if database has files
        metadata = self.db_metadata.get_metadata()
        if not metadata:
            self.org_lock_warning.hide()
            self.reorganize_btn.hide()
            return

        total_photos = metadata.get('total_photos', 0)
        current_db_template = metadata.get('organization_template', '{YYYY}/{MM}/{DD}')
        current_db_file_type_mode = metadata.get('file_type_organization', 'combined')

        # Get current file type organization mode from UI
        if self.file_type_combined_radio.isChecked():
            current_file_type_mode = 'combined'
        elif self.file_type_subfolder_radio.isChecked():
            current_file_type_mode = 'subfolder'
        else:
            current_file_type_mode = 'separate_archive'

        # Check if template or file type organization has changed
        template_changed = (self.current_template != current_db_template)
        file_type_changed = (current_file_type_mode != current_db_file_type_mode)

        if total_photos > 0 and (template_changed or file_type_changed):
            self.org_lock_warning.setText(
                f"⚠ Warning: This archive contains {total_photos} files. "
                f"Changing the organization structure will require reorganizing all files. "
                f"This may take a significant amount of time."
            )
            self.org_lock_warning.show()
            self.reorganize_btn.show()
        else:
            self.org_lock_warning.hide()
            self.reorganize_btn.hide()

    def check_filename_rename_lock(self):
        """Check if filename rename template has changed and show warning."""
        if self.db_metadata is None:
            self.rename_lock_warning.hide()
            self.rename_reorganize_btn.hide()
            return

        # Get metadata to check if database has files
        metadata = self.db_metadata.get_metadata()
        if not metadata:
            self.rename_lock_warning.hide()
            self.rename_reorganize_btn.hide()
            return

        total_photos = metadata.get('total_photos', 0)
        current_db_filename_template = metadata.get('filename_template', '{original_name}')

        # Check if filename template has changed
        template_changed = (self.current_filename_template != current_db_filename_template)

        if total_photos > 0 and template_changed:
            self.rename_lock_warning.setText(
                f"⚠ Warning: This archive contains {total_photos} files. "
                f"Changing the filename template will require reorganizing all files to apply the new naming pattern. "
                f"This may take a significant amount of time."
            )
            self.rename_lock_warning.show()
            self.rename_reorganize_btn.show()
        else:
            self.rename_lock_warning.hide()
            self.rename_reorganize_btn.hide()

    def on_file_type_changed(self):
        """Handle file type organization mode change."""
        # Show/hide video archive location widget
        if self.file_type_separate_radio.isChecked():
            self.video_archive_widget.show()
        else:
            self.video_archive_widget.hide()

        # Check organization lock
        self.check_organization_lock()

    def on_browse_video_archive(self):
        """Browse for video archive location."""
        from PySide6.QtWidgets import QFileDialog

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Video Archive Location",
            self.video_archive_path_edit.text() or os.path.expanduser("~")
        )

        if folder:
            self.video_archive_path_edit.setText(folder)

    def save_organization_to_database(self):
        """Save organization settings to database."""
        if self.db_metadata is None:
            return False

        try:
            # Get current file type organization mode
            if self.file_type_combined_radio.isChecked():
                file_type_mode = 'combined'
            elif self.file_type_subfolder_radio.isChecked():
                file_type_mode = 'subfolder'
            else:
                file_type_mode = 'separate_archive'

            # Validate video archive location if separate archive mode
            if file_type_mode == 'separate_archive':
                video_archive_location = self.video_archive_path_edit.text().strip()
                if not video_archive_location:
                    QMessageBox.warning(
                        self,
                        "Video Archive Location Required",
                        "Please specify a video archive location when using separate archive mode."
                    )
                    return False

                # Save video archive location to database
                self.db_metadata.set_video_archive(video_archive_location, enabled=True)
            else:
                # Disable separate video archive
                self.db_metadata.set_video_archive("", enabled=False)

            # Save template to database
            self.db_metadata.set_organization_template(self.current_template)

            # Save file type organization mode to database
            self.db_metadata.set_file_type_organization(file_type_mode)

            return True
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Saving Settings",
                f"Failed to save organization settings to database:\n\n{str(e)}"
            )
            return False

    def on_reorganize_clicked(self):
        """Show reorganization dialog (placeholder for future implementation)."""
        QMessageBox.information(
            self,
            "Reorganization",
            "Reorganization feature will be implemented in a future update.\n\n"
            "This will allow you to migrate your entire archive to the new folder structure."
        )

    def set_database(self, db_metadata):
        """Load organization settings from database.

        Args:
            db_metadata: DatabaseMetadata instance
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"=" * 80)
        logger.info(f"SETTINGS TAB: set_database() called")
        if db_metadata:
            logger.info(f"  Database path: '{db_metadata.database_path}'")
        else:
            logger.info(f"  db_metadata is None!")
        logger.info(f"=" * 80)

        self.db_metadata = db_metadata

        if db_metadata is None:
            return

        # Load organization template
        template = db_metadata.get_organization_template()
        self.current_template = template

        # Find matching preset or use custom
        preset = OrganizationTemplate.get_preset_by_template(template)
        if preset:
            # Select the matching preset
            preset_name = preset['name']
            index = self.org_preset_combo.findText(preset_name)
            if index >= 0:
                self.org_preset_combo.setCurrentIndex(index)
        else:
            # Use custom template
            self.org_preset_combo.setCurrentText("Custom Template...")
            self.custom_template_edit.setText(template)

        # Load file type organization mode
        mode = db_metadata.get_file_type_organization()
        if mode == 'combined':
            self.file_type_combined_radio.setChecked(True)
        elif mode == 'subfolder':
            self.file_type_subfolder_radio.setChecked(True)
        elif mode == 'separate_archive':
            self.file_type_separate_radio.setChecked(True)

        # Load video archive location (if separate archive mode)
        if mode == 'separate_archive':
            video_archive_location = db_metadata.get_video_archive_location()
            if video_archive_location:
                self.video_archive_path_edit.setText(video_archive_location)

        # Update preview
        self.update_organization_preview()

        # Check lock status
        self.check_organization_lock()

        # Load filename rename settings
        rename_enabled = db_metadata.is_file_rename_enabled()
        self.enable_rename_check.setChecked(rename_enabled)

        filename_template = db_metadata.get_filename_template()
        self.current_filename_template = filename_template  # Store for comparison
        self.filename_template_edit.setText(filename_template)

        # Trigger preview update
        self.on_filename_template_changed(filename_template)

        # Load retention settings
        self.load_retention_settings()

    def get_config(self):
        """Get configuration as dictionary."""
        # Get excluded patterns from list widget
        excluded_patterns = []
        if self.filename_filter_check.isChecked():
            for i in range(self.pattern_list.count()):
                excluded_patterns.append(self.pattern_list.item(i).text())

        # Get file type organization mode
        if self.file_type_combined_radio.isChecked():
            file_type_mode = 'combined'
        elif self.file_type_subfolder_radio.isChecked():
            file_type_mode = 'subfolder'
        else:
            file_type_mode = 'separate_archive'

        config = {
            'include_subdirectories': self.include_subdirs_check.isChecked(),
            'batch_size': self.batch_size_spin.value(),
            'organization_template': self.current_template,
            'file_type_organization': file_type_mode,
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

        # Load organization template (with backward compatibility)
        if 'organization_template' in config:
            template = config['organization_template']
        else:
            # Legacy support: convert old group_by_year/group_by_day to template
            group_by_year = config.get('group_by_year', True)
            group_by_day = config.get('group_by_day', True)
            if group_by_year and group_by_day:
                template = '{YYYY}/{MM}/{DD}'
            elif group_by_year:
                template = '{YYYY}/{MM}'
            else:
                template = '{YYYY}/{MM}/{DD}'  # Default

        self.current_template = template

        # Find matching preset or use custom
        preset = OrganizationTemplate.get_preset_by_template(template)
        if preset:
            preset_name = preset['name']
            index = self.org_preset_combo.findText(preset_name)
            if index >= 0:
                self.org_preset_combo.setCurrentIndex(index)
        else:
            self.org_preset_combo.setCurrentText("Custom Template...")
            self.custom_template_edit.setText(template)

        # Load file type organization mode
        file_type_mode = config.get('file_type_organization', 'combined')
        if file_type_mode == 'combined':
            self.file_type_combined_radio.setChecked(True)
        elif file_type_mode == 'subfolder':
            self.file_type_subfolder_radio.setChecked(True)
        elif file_type_mode == 'separate_archive':
            self.file_type_separate_radio.setChecked(True)

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

        # Update organization preview
        self.update_organization_preview()

    def load_from_file(self, show_dialog=True):
        """Load settings from file.

        Args:
            show_dialog (bool): If True, show success/error dialogs. If False, load silently.
        """
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
            'organization_template': '{YYYY}/{MM}/{DD}',
            'file_type_organization': 'combined',
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

            # Debug: Check config types
            import logging
            logger = logging.getLogger(__name__)
            for key, value in config.items():
                logger.debug(f"Config[{key}] = {type(value)}: {value if not isinstance(value, (dict, list)) or len(str(value)) < 100 else str(value)[:100]+'...'}")

            # Add dummy source/dest for validation
            config['source_directory'] = ["/dummy/path"]
            config['destination_directory'] = "/dummy/path"
            config['copy_files'] = True
            config['move_files'] = False

            Config(settings_dict=config)
            QMessageBox.information(self, "Validation Successful",
                                   "All settings are valid.")
        except Exception as e:
            import traceback
            full_error = traceback.format_exc()
            logger.error(f"Validation failed:\n{full_error}")
            QMessageBox.critical(self, "Validation Failed",
                               f"Invalid settings:\n\n{str(e)}")

    # ========== File Renaming Methods ==========

    def on_rename_enabled_changed(self, state):
        """Handle enable/disable file renaming checkbox change."""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.info(f"→ on_rename_enabled_changed called - RAW state value: {state} (type: {type(state)})")
            logger.info(f"  Qt.Checked = {Qt.Checked}, Qt.Unchecked = {Qt.Unchecked}")

            # Use isChecked() instead of comparing state - more reliable
            enabled = self.enable_rename_check.isChecked()
            logger.info(f"  Checkbox.isChecked() = {enabled}")
            logger.info(f"  State comparison (state == Qt.Checked) = {state == Qt.Checked}")

            if not self.db_metadata:
                logger.error("✗ db_metadata is None - cannot save rename enabled state!")
                QMessageBox.critical(self, "Error",
                                   "Database connection not initialized.\nPlease load or create a database first.")
                return

            logger.debug(f"  Calling set_file_rename_enabled({enabled})...")
            success = self.db_metadata.set_file_rename_enabled(enabled)

            if success:
                status = "enabled" if enabled else "disabled"
                logger.info(f"✓ File renaming {status} successfully")
                print(f"File renaming {status}")
            else:
                logger.error(f"✗ set_file_rename_enabled() returned False")
                QMessageBox.warning(self, "Warning",
                                  f"Failed to update rename setting.\nCheck the log file for details.")

        except Exception as e:
            logger.error(f"✗ Exception in on_rename_enabled_changed: {e}", exc_info=True)
            QMessageBox.critical(self, "Error",
                               f"Failed to update rename setting:\n\n{str(e)}")

    def on_filename_template_changed(self, template):
        """Handle filename template text change with validation and preview."""
        import logging
        logger = logging.getLogger(__name__)

        try:
            logger.debug(f"→ on_filename_template_changed('{template}')")

            # Import here to avoid circular dependency
            from filename_template import FilenameTemplate

            # Clear previous validation message
            self.rename_validation_label.clear()

            if not template:
                # Empty template - show placeholder preview
                logger.debug("  Empty template - showing placeholder")
                self.rename_example_label.setText("IMG_1234.jpg")
                self.rename_preview_label.setText("IMG_1234.jpg")
                return

            # Validate template
            logger.debug(f"  Validating template...")
            is_valid, error_msg = FilenameTemplate.validate(template)

            if not is_valid:
                # Show validation error
                logger.warning(f"⚠ Template validation failed: {error_msg}")
                self.rename_validation_label.setText(f"⚠ {error_msg}")
                self.rename_example_label.setStyleSheet("color: red; font-weight: bold;")
                self.rename_example_label.setText("Invalid template")
                self.rename_preview_label.setStyleSheet("color: red; font-weight: bold;")
                self.rename_preview_label.setText("Error")
                return

            logger.debug(f"  ✓ Template validation passed")

            # Template is valid - generate preview
            example_output = FilenameTemplate.get_example_output(template)
            logger.debug(f"  Preview generated: '{example_output}'")

            self.rename_example_label.setStyleSheet("color: green; font-weight: bold;")
            self.rename_example_label.setText(example_output)
            self.rename_preview_label.setStyleSheet("color: blue; font-weight: bold;")
            self.rename_preview_label.setText(example_output)

            # Store current template for comparison
            self.current_filename_template = template
            logger.debug(f"  Stored current_filename_template = '{template}'")

            # Save to database if valid
            if self.db_metadata:
                logger.debug(f"  Saving template to database...")
                success = self.db_metadata.set_filename_template(template)
                if success:
                    logger.info(f"✓ Template saved to database: '{template}'")
                else:
                    logger.error(f"✗ Failed to save template to database")
                    self.rename_validation_label.setText(f"⚠ Failed to save template to database")
            else:
                logger.warning("⚠ db_metadata is None - template NOT saved to database")

            # Check if reorganization is needed
            logger.debug(f"  Checking if reorganization needed...")
            self.check_filename_rename_lock()

        except Exception as e:
            logger.error(f"✗ Exception in on_filename_template_changed: {e}", exc_info=True)
            self.rename_validation_label.setText(f"⚠ Error: {str(e)}")
            self.rename_example_label.setText("Error")

    def restore_default_filename_template(self):
        """Restore default filename template."""
        default_template = "{original_name}"
        self.filename_template_edit.setText(default_template)

        if self.db_metadata:
            try:
                self.db_metadata.set_filename_template(default_template)
                QMessageBox.information(self, "Template Restored",
                                       "Filename template restored to default:\n{original_name}")
            except Exception as e:
                QMessageBox.critical(self, "Error",
                                   f"Failed to restore default template:\n\n{str(e)}")

    def on_rename_reorganize_clicked(self):
        """Show reorganization dialog for filename template changes."""
        QMessageBox.information(
            self,
            "Reorganization",
            "Reorganization feature will be implemented in a future update.\n\n"
            "This will allow you to rename all files in the archive using the new template."
        )

    # ==================== Retention Settings Methods ====================

    def on_retention_mode_changed(self, index):
        """Handle retention mode dropdown change."""
        mode_labels = ["", "Sessions to keep:", "Days to keep:"]
        if index == 0:  # Keep All
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

            # Trigger visibility update
            self.on_retention_mode_changed(self.retention_mode_combo.currentIndex())

        except Exception as e:
            # Silently fail - retention settings are optional
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
            QMessageBox.critical(self, "Error",
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
                    self, "Cleanup Complete",
                    "No sessions needed to be cleaned up based on current retention settings."
                )

        except Exception as e:
            QMessageBox.critical(self, "Cleanup Failed",
                               f"Failed to run cleanup:\n\n{str(e)}")
