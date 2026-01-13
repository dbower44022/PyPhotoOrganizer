"""
Settings Tab for PyPhotoOrganizer GUI

Reorganized settings management with three main tabs:
- Import Settings: Source configuration and filtering
- Archive Settings: Organization and file management
- System Settings: Database, performance, and global settings
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QCheckBox, QSpinBox, QLineEdit, QPushButton,
                               QLabel, QListWidget, QMessageBox, QScrollArea,
                               QFormLayout, QComboBox, QTextEdit, QRadioButton,
                               QButtonGroup, QTabWidget, QTableWidget, QTableWidgetItem,
                               QHeaderView, QAbstractItemView, QFileDialog)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
import json
import os
import constants
from config import Config
from organization_template import OrganizationTemplate
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SettingsTab(QWidget):
    """Tab for managing application settings with reorganized structure."""

    # Signals
    start_processing = Signal()
    stop_processing = Signal()

    def __init__(self):
        super().__init__()
        self.settings_file = "settings.json"
        self.db_metadata = None  # Will be set when database is loaded
        self.current_template = '{YYYY}/{MM}/{DD}'  # Default organization template
        self.current_filename_template = '{original_name}'  # Default filename template
        self.last_clicked_source_row = -1  # For Shift/Ctrl selection in source table
        self.init_ui()
        self.load_from_file(show_dialog=False)  # Suppress dialog during initialization

    def init_ui(self):
        """Initialize the user interface with three main tabs."""
        # Create tab widget for main tabs
        self.main_tabs = QTabWidget()

        # Stylesheet for bold GroupBox titles (used in all tabs)
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

        # Create individual tab pages
        import_tab = self._create_import_settings_tab()
        archive_tab = self._create_archive_settings_tab()
        system_tab = self._create_system_settings_tab()

        # Add tabs with icons
        self.main_tabs.addTab(import_tab, "📥 Import Settings")
        self.main_tabs.addTab(archive_tab, "📦 Archive Settings")
        self.main_tabs.addTab(system_tab, "⚙️ System Settings")

        # Set tooltips for tabs
        self.main_tabs.setTabToolTip(0, "Source folders, file processing, and filtering settings")
        self.main_tabs.setTabToolTip(1, "Archive location, organization, and file renaming")
        self.main_tabs.setTabToolTip(2, "Database info, operation mode, performance, and retention")

        # Set main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.main_tabs)
        self.setLayout(main_layout)

        # Initialize pattern count
        self.update_pattern_count()
        self.update_ignored_dirs_count()

    def _create_import_settings_tab(self):
        """Create the Import Settings tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        main_widget = QWidget()
        layout = QVBoxLayout()

        # Source Folders Group
        source_group = QGroupBox("Source Folders")
        source_group.setStyleSheet(self.groupbox_style)
        source_layout = QVBoxLayout()

        # Create table with columns: Enable, Status Icon, Path, Last Scanned, Status
        self.source_table = QTableWidget()
        self.source_table.setColumnCount(5)
        self.source_table.setHorizontalHeaderLabels(["Enable", "Icon", "Source Path", "Last Scanned", "Status"])
        self.source_table.setMinimumHeight(150)
        self.source_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.source_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.source_table.verticalHeader().setVisible(False)

        # Connect signals for Shift/Ctrl selection
        self.source_table.itemSelectionChanged.connect(self.sync_source_checkboxes_with_selection)
        self.source_table.itemClicked.connect(self.on_source_item_clicked)
        self.source_table.itemDoubleClicked.connect(self.on_source_item_double_clicked)

        # Set column widths
        header = self.source_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self.source_table.setColumnWidth(0, 60)
        self.source_table.setColumnWidth(1, 50)
        self.source_table.setMouseTracking(True)

        source_layout.addWidget(self.source_table)

        source_buttons = QHBoxLayout()
        self.add_source_btn = QPushButton("Add Folder...")
        self.add_source_btn.clicked.connect(self.add_source_folder)
        self.remove_source_btn = QPushButton("Remove Selected")
        self.remove_source_btn.clicked.connect(self.remove_source_folder)
        self.clear_all_btn = QPushButton("Clear All")
        self.clear_all_btn.clicked.connect(self.clear_all_sources)
        self.refresh_status_btn = QPushButton("Refresh Status")
        self.refresh_status_btn.clicked.connect(self.refresh_source_status)
        source_buttons.addWidget(self.add_source_btn)
        source_buttons.addWidget(self.remove_source_btn)
        source_buttons.addWidget(self.clear_all_btn)
        source_buttons.addWidget(self.refresh_status_btn)
        source_buttons.addStretch()
        source_layout.addLayout(source_buttons)

        source_group.setLayout(source_layout)
        layout.addWidget(source_group)

        # Ignored Directories Group
        ignored_dirs_group = QGroupBox("Ignored Directories (Skip During Scan)")
        ignored_dirs_group.setStyleSheet(self.groupbox_style)
        ignored_dirs_layout = QVBoxLayout()

        ignored_dirs_desc = QLabel(
            "Directories matching these patterns will be skipped during scanning. "
            "This helps exclude system folders, thumbnails, and other non-photo directories."
        )
        ignored_dirs_desc.setWordWrap(True)
        ignored_dirs_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        ignored_dirs_layout.addWidget(ignored_dirs_desc)

        ignored_content_layout = QHBoxLayout()

        list_container = QVBoxLayout()
        list_label = QLabel("Ignored Patterns:")
        list_label.setStyleSheet("font-weight: bold;")
        list_container.addWidget(list_label)

        self.ignored_dirs_list = QListWidget()
        self.ignored_dirs_list.setMaximumHeight(120)
        self.ignored_dirs_list.setToolTip("Double-click to edit, select and click Remove to delete")
        list_container.addWidget(self.ignored_dirs_list)
        ignored_content_layout.addLayout(list_container)

        ignored_buttons = QVBoxLayout()
        self.add_ignored_dir_input = QLineEdit()
        self.add_ignored_dir_input.setPlaceholderText("e.g., @eaDir, thumb*, .git, /path/to/skip")
        ignored_buttons.addWidget(self.add_ignored_dir_input)

        self.add_ignored_dir_btn = QPushButton("Add Pattern")
        self.add_ignored_dir_btn.clicked.connect(self.add_ignored_dir_pattern)
        ignored_buttons.addWidget(self.add_ignored_dir_btn)

        self.remove_ignored_dir_btn = QPushButton("Remove Selected")
        self.remove_ignored_dir_btn.clicked.connect(self.remove_ignored_dir_pattern)
        ignored_buttons.addWidget(self.remove_ignored_dir_btn)

        self.add_preset_dirs_btn = QPushButton("Add Common Presets")
        self.add_preset_dirs_btn.setToolTip("Add commonly ignored folders like @eaDir, .git, node_modules, etc.")
        self.add_preset_dirs_btn.clicked.connect(self.add_preset_ignored_dirs)
        ignored_buttons.addWidget(self.add_preset_dirs_btn)

        ignored_buttons.addStretch()
        ignored_content_layout.addLayout(ignored_buttons)
        ignored_dirs_layout.addLayout(ignored_content_layout)

        # Help text
        help_text_widget = QWidget()
        help_text_widget.setStyleSheet("background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 3px; padding: 8px;")
        help_text_layout = QVBoxLayout()
        help_text_layout.setContentsMargins(5, 5, 5, 5)

        help_title = QLabel("ℹ Wildcard Syntax:")
        help_title.setStyleSheet("font-weight: bold; font-size: 10pt;")
        help_text_layout.addWidget(help_title)

        help_examples = QLabel(
            "• <b>*</b> = Match any characters (e.g., <i>thumb*</i> matches thumbnail, thumbs, thumb_cache)<br>"
            "• <b>?</b> = Match single character (e.g., <i>temp?</i> matches temp1, temp2)<br>"
            "• <b>Examples:</b> @eaDir, .git, node_modules, thumb*, /mnt/backup/old"
        )
        help_examples.setWordWrap(True)
        help_examples.setStyleSheet("color: #555; font-size: 9pt;")
        help_text_layout.addWidget(help_examples)

        help_text_widget.setLayout(help_text_layout)
        ignored_dirs_layout.addWidget(help_text_widget)

        self.ignored_dirs_count_label = QLabel("Total patterns: 0")
        self.ignored_dirs_count_label.setStyleSheet("font-style: italic; color: gray; margin-top: 5px;")
        ignored_dirs_layout.addWidget(self.ignored_dirs_count_label)

        ignored_dirs_group.setLayout(ignored_dirs_layout)
        layout.addWidget(ignored_dirs_group)

        # File Processing Settings
        file_group = QGroupBox("File Processing Settings")
        file_group.setStyleSheet(self.groupbox_style)
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

        # Photo Filtering Settings
        filter_group = QGroupBox("Photo Filtering Settings")
        filter_group.setStyleSheet(self.groupbox_style)
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
        self.max_width_spin.setRange(1000, 50000)
        self.max_width_spin.setValue(constants.MAX_PHOTO_WIDTH)
        filter_layout.addRow("Max width:", self.max_width_spin)

        self.max_height_spin = QSpinBox()
        self.max_height_spin.setRange(1000, 50000)
        self.max_height_spin.setValue(constants.MAX_PHOTO_HEIGHT)
        filter_layout.addRow("Max height:", self.max_height_spin)

        self.exclude_square_spin = QSpinBox()
        self.exclude_square_spin.setRange(0, 1000)
        self.exclude_square_spin.setValue(constants.MIN_SQUARE_SIZE)
        filter_layout.addRow("Exclude square smaller than:", self.exclude_square_spin)

        self.require_exif_check = QCheckBox()
        self.require_exif_check.setChecked(False)
        filter_layout.addRow("Require EXIF data:", self.require_exif_check)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Filename Pattern Filtering
        pattern_group = QGroupBox("Filename Pattern Filtering")
        pattern_group.setStyleSheet(self.groupbox_style)
        pattern_layout = QVBoxLayout()

        pattern_desc = QLabel(
            "Files containing these patterns in their filename will be filtered out.\n"
            "Common examples: favicon, icon, logo, thumbnail, etc."
        )
        pattern_desc.setWordWrap(True)
        pattern_desc.setStyleSheet("font-style: italic; color: gray; padding: 5px;")
        pattern_layout.addWidget(pattern_desc)

        self.filename_filter_check = QCheckBox("Enable filename pattern filtering")
        self.filename_filter_check.setChecked(True)
        self.filename_filter_check.stateChanged.connect(self.update_pattern_controls)
        pattern_layout.addWidget(self.filename_filter_check)

        pattern_content_layout = QHBoxLayout()

        list_container = QVBoxLayout()
        list_label = QLabel("Excluded Patterns:")
        list_label.setStyleSheet("font-weight: bold;")
        list_container.addWidget(list_label)

        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(150)
        list_container.addWidget(self.pattern_list)
        pattern_content_layout.addLayout(list_container)

        pattern_buttons = QVBoxLayout()

        self.add_pattern_input = QLineEdit()
        self.add_pattern_input.setPlaceholderText("e.g., favicon, icon, thumb")
        pattern_buttons.addWidget(self.add_pattern_input)

        self.add_pattern_btn = QPushButton("Add Pattern")
        self.add_pattern_btn.clicked.connect(self.add_pattern)
        pattern_buttons.addWidget(self.add_pattern_btn)

        self.remove_pattern_btn = QPushButton("Remove Selected")
        self.remove_pattern_btn.clicked.connect(self.remove_pattern)
        pattern_buttons.addWidget(self.remove_pattern_btn)

        self.add_default_patterns_btn = QPushButton("Add Default Patterns")
        self.add_default_patterns_btn.clicked.connect(self.restore_default_patterns)
        pattern_buttons.addWidget(self.add_default_patterns_btn)

        pattern_buttons.addStretch()
        pattern_content_layout.addLayout(pattern_buttons)

        pattern_layout.addLayout(pattern_content_layout)

        self.pattern_count_label = QLabel()
        self.pattern_count_label.setStyleSheet("font-style: italic; color: gray;")
        pattern_layout.addWidget(self.pattern_count_label)

        pattern_group.setLayout(pattern_layout)
        layout.addWidget(pattern_group)

        layout.addStretch()
        main_widget.setLayout(layout)
        scroll.setWidget(main_widget)
        return scroll

    def _create_archive_settings_tab(self):
        """Create the Archive Settings tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)

        main_widget = QWidget()
        layout = QVBoxLayout()

        # Archive Location Group
        archive_group = QGroupBox("Archive Location")
        archive_group.setStyleSheet(self.groupbox_style)
        archive_layout = QVBoxLayout()

        archive_info = QLabel(
            "The archive location is where your organized photos are stored.\n"
            "This location is permanently bound to the database."
        )
        archive_info.setWordWrap(True)
        archive_info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        archive_layout.addWidget(archive_info)

        archive_path_layout = QHBoxLayout()
        self.archive_path_edit = QLineEdit()
        self.archive_path_edit.setReadOnly(True)
        self.archive_path_edit.setPlaceholderText("Archive location from database...")
        self.archive_path_edit.setStyleSheet("background-color: #f5f5f5;")
        archive_path_layout.addWidget(self.archive_path_edit)

        self.browse_archive_btn = QPushButton("Browse...")
        self.browse_archive_btn.setToolTip("Archive location is managed by the database")
        self.browse_archive_btn.clicked.connect(self.on_browse_archive_clicked)
        archive_path_layout.addWidget(self.browse_archive_btn)

        archive_layout.addLayout(archive_path_layout)

        self.archive_status_label = QLabel("")
        self.archive_status_label.setWordWrap(True)
        self.archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")
        archive_layout.addWidget(self.archive_status_label)

        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)

        # Organization Settings
        org_group = QGroupBox("Organization Settings")
        org_group.setStyleSheet(self.groupbox_style)
        org_layout = QVBoxLayout()

        preset_layout = QFormLayout()
        self.org_preset_combo = QComboBox()
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

        # Helper buttons
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

        self.template_validation_label = QLabel()
        self.template_validation_label.setWordWrap(True)
        custom_layout.addWidget(self.template_validation_label)

        self.custom_template_widget.setLayout(custom_layout)
        self.custom_template_widget.hide()
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

        # Lock warning
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
        file_type_group.setStyleSheet(self.groupbox_style)
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

        # Video archive location widget
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
        self.video_archive_widget.hide()
        file_type_layout.addWidget(self.video_archive_widget)

        self.file_type_combined_radio.setChecked(True)

        self.file_type_combined_radio.toggled.connect(self.on_file_type_changed)
        self.file_type_subfolder_radio.toggled.connect(self.on_file_type_changed)
        self.file_type_separate_radio.toggled.connect(self.on_file_type_changed)

        file_type_group.setLayout(file_type_layout)
        layout.addWidget(file_type_group)

        self.update_organization_preview()

        # File Renaming Settings
        rename_group = QGroupBox("File Renaming")
        rename_group.setStyleSheet(self.groupbox_style)
        rename_layout = QVBoxLayout()

        self.enable_rename_check = QCheckBox("Enable file renaming during processing")
        self.enable_rename_check.setToolTip("When enabled, files will be renamed according to the template below")
        self.enable_rename_check.stateChanged.connect(self.on_rename_enabled_changed)
        rename_layout.addWidget(self.enable_rename_check)

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

        restore_rename_btn = QPushButton("Restore Default: {original_name}")
        restore_rename_btn.clicked.connect(self.restore_default_filename_template)
        rename_layout.addWidget(restore_rename_btn)

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

        layout.addStretch()
        main_widget.setLayout(layout)
        scroll.setWidget(main_widget)
        return scroll

    def _create_system_settings_tab(self):
        """Create the System Settings tab."""
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
        return scroll

    # ========== Source Folders Methods ==========

    def add_source_folder(self):
        """Add a source folder."""
        folder = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if folder:
            existing_paths = self.get_source_folders()
            if folder in existing_paths:
                QMessageBox.information(self, "Folder Already Added",
                                       "This folder is already in the source list.")
                return

            if self.db_metadata:
                success = self.db_metadata.add_source_directory(folder, enabled=True)
                if not success:
                    QMessageBox.warning(self, "Failed to Add",
                                       "Could not add folder to database.")
                    return

            self._add_source_to_table(folder, enabled=True, last_scanned=None)

    def remove_source_folder(self):
        """Remove source folders with checked checkboxes."""
        rows_to_remove = []
        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    rows_to_remove.append(row)

        if not rows_to_remove:
            QMessageBox.information(self, "No Selection",
                                  "Please check the checkboxes for the folders you want to remove.")
            return

        reply = QMessageBox.question(
            self, "Remove Source Folders",
            f"Remove {len(rows_to_remove)} source folder(s) from the list?\n\n"
            f"This will not delete any files, only remove them from the source list.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        for row in sorted(rows_to_remove, reverse=True):
            path = self.source_table.item(row, 2).text()

            if self.db_metadata:
                self.db_metadata.remove_source_directory(path)

            self.source_table.removeRow(row)

    def clear_all_sources(self):
        """Clear all source folders."""
        if self.source_table.rowCount() == 0:
            QMessageBox.information(self, "No Folders",
                                  "The source folder list is already empty.")
            return

        reply = QMessageBox.question(
            self, "Clear All Source Folders?",
            f"Remove all {self.source_table.rowCount()} source folder(s) from the list?\n\n"
            f"This will not delete any files, only clear the list.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.db_metadata:
                self.db_metadata.clear_all_source_directories()

            self.source_table.setRowCount(0)

    def _add_source_to_table(self, path: str, enabled: bool = True, last_scanned: str = None):
        """Add a source directory to the table."""
        row_position = self.source_table.rowCount()
        self.source_table.insertRow(row_position)

        # Column 0: Enable checkbox
        checkbox = QCheckBox()
        checkbox.setChecked(enabled)
        checkbox.stateChanged.connect(lambda state, p=path: self._on_source_checkbox_changed(p, state))

        checkbox_widget = QWidget()
        checkbox_layout = QHBoxLayout(checkbox_widget)
        checkbox_layout.addWidget(checkbox)
        checkbox_layout.setAlignment(Qt.AlignCenter)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        self.source_table.setCellWidget(row_position, 0, checkbox_widget)

        # Validate path
        is_available, status_text, status_detail = self._validate_path(path)

        # Column 1: Status icon
        icon_item = QTableWidgetItem()
        if is_available:
            icon_item.setText("✓")
            icon_item.setForeground(QColor(0, 150, 0))
        else:
            icon_item.setText("⚠")
            icon_item.setForeground(QColor(200, 0, 0))
        icon_item.setTextAlignment(Qt.AlignCenter)
        icon_item.setToolTip(status_detail)
        icon_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 1, icon_item)

        # Column 2: Path
        path_item = QTableWidgetItem(path)
        path_item.setToolTip(status_detail)
        path_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 2, path_item)

        # Column 3: Last Scanned
        if last_scanned:
            try:
                dt = datetime.fromisoformat(last_scanned)
                scanned_text = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                scanned_text = "Unknown"
        else:
            scanned_text = "Never"
        scanned_item = QTableWidgetItem(scanned_text)
        scanned_item.setToolTip(f"Last scanned: {scanned_text}")
        scanned_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 3, scanned_item)

        # Column 4: Status
        status_item = QTableWidgetItem(status_text)
        status_item.setToolTip(status_detail)
        if not is_available:
            status_item.setForeground(QColor(200, 0, 0))
        status_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
        self.source_table.setItem(row_position, 4, status_item)

    def _validate_path(self, path: str) -> tuple:
        """Validate if a path exists and is accessible."""
        try:
            if not os.path.exists(path):
                if path.startswith('/run/user/') and '/gvfs/' in path:
                    return (False, "Not Mounted",
                           "Network share not mounted. Open the share in your file manager first.")
                else:
                    return (False, "Not Found",
                           f"Path does not exist: {path}")

            if not os.path.isdir(path):
                return (False, "Not a Directory",
                       f"Path exists but is not a directory: {path}")

            if not os.access(path, os.R_OK):
                return (False, "Permission Denied",
                       f"Cannot read directory (permission denied): {path}")

            return (True, "Available", f"Path is accessible: {path}")

        except Exception as e:
            return (False, "Error", f"Error checking path: {str(e)}")

    def _on_source_checkbox_changed(self, path: str, state: int):
        """Handle checkbox state change - update database."""
        if self.db_metadata:
            enabled = (state == Qt.Checked)
            self.db_metadata.update_source_enabled(path, enabled)

    def refresh_source_status(self):
        """Refresh the status of all source directories."""
        for row in range(self.source_table.rowCount()):
            path = self.source_table.item(row, 2).text()
            is_available, status_text, status_detail = self._validate_path(path)

            icon_item = self.source_table.item(row, 1)
            if is_available:
                icon_item.setText("✓")
                icon_item.setForeground(QColor(0, 150, 0))
            else:
                icon_item.setText("⚠")
                icon_item.setForeground(QColor(200, 0, 0))
            icon_item.setToolTip(status_detail)

            status_item = self.source_table.item(row, 4)
            status_item.setText(status_text)
            status_item.setToolTip(status_detail)
            if not is_available:
                status_item.setForeground(QColor(200, 0, 0))
            else:
                status_item.setForeground(QColor(0, 0, 0))

    def on_source_item_clicked(self, item):
        """Handle click on source table item - support Shift/Ctrl selection."""
        if item is None:
            return

        row = item.row()
        column = item.column()

        if column != 0:
            self.last_clicked_source_row = row
            return

        checkbox_widget = self.source_table.cellWidget(row, 0)
        if not checkbox_widget:
            return

        checkbox = checkbox_widget.findChild(QCheckBox)
        if not checkbox:
            return

        from PySide6.QtWidgets import QApplication
        modifiers = QApplication.keyboardModifiers()

        if modifiers & Qt.ShiftModifier and self.last_clicked_source_row >= 0:
            start_row = min(self.last_clicked_source_row, row)
            end_row = max(self.last_clicked_source_row, row)
            target_state = checkbox.isChecked()

            self.source_table.blockSignals(True)

            for r in range(start_row, end_row + 1):
                self.source_table.selectRow(r)
                cb_widget = self.source_table.cellWidget(r, 0)
                if cb_widget:
                    cb = cb_widget.findChild(QCheckBox)
                    if cb:
                        cb.setChecked(target_state)

            self.source_table.blockSignals(False)

        elif modifiers & Qt.ControlModifier:
            self.last_clicked_source_row = row

        else:
            self.last_clicked_source_row = row

    def on_source_item_double_clicked(self, item):
        """Handle double-click on source table item - toggle checkbox."""
        if item is None:
            return

        row = item.row()
        checkbox_widget = self.source_table.cellWidget(row, 0)

        if checkbox_widget:
            checkbox = checkbox_widget.findChild(QCheckBox)
            if checkbox:
                checkbox.setChecked(not checkbox.isChecked())

    def sync_source_checkboxes_with_selection(self):
        """Sync checkbox states with row selection."""
        selected_rows = set(index.row() for index in self.source_table.selectedIndexes())

        self.source_table.blockSignals(True)

        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox:
                    is_selected = row in selected_rows
                    if checkbox.isChecked() != is_selected:
                        checkbox.setChecked(is_selected)

        self.source_table.blockSignals(False)

    def load_sources_from_database(self):
        """Load source directories from the database."""
        if not self.db_metadata:
            return

        self.source_table.setRowCount(0)

        sources = self.db_metadata.get_all_source_directories()

        for source in sources:
            self._add_source_to_table(
                path=source['path'],
                enabled=source['enabled'],
                last_scanned=source['last_scanned']
            )

    def get_source_folders(self):
        """Get list of all source folders (regardless of enabled status)."""
        folders = []
        for row in range(self.source_table.rowCount()):
            path_item = self.source_table.item(row, 2)
            if path_item:
                folders.append(path_item.text())
        return folders

    def get_enabled_source_folders(self):
        """Get list of only enabled source folders."""
        enabled_folders = []
        for row in range(self.source_table.rowCount()):
            checkbox_widget = self.source_table.cellWidget(row, 0)
            if checkbox_widget:
                checkbox = checkbox_widget.findChild(QCheckBox)
                if checkbox and checkbox.isChecked():
                    path_item = self.source_table.item(row, 2)
                    if path_item:
                        enabled_folders.append(path_item.text())
        return enabled_folders

    # ========== Ignored Directories Methods ==========

    def add_ignored_dir_pattern(self):
        """Add a new ignored directory pattern to the list."""
        pattern = self.add_ignored_dir_input.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Empty Pattern",
                              "Please enter a pattern to add.")
            return

        for i in range(self.ignored_dirs_list.count()):
            if self.ignored_dirs_list.item(i).text().lower() == pattern.lower():
                QMessageBox.information(self, "Pattern Exists",
                                      f"Pattern '{pattern}' already exists in the list.")
                return

        self.ignored_dirs_list.addItem(pattern)
        self.add_ignored_dir_input.clear()
        self.update_ignored_dirs_count()

        self.save_ignored_dirs_to_database()

    def remove_ignored_dir_pattern(self):
        """Remove selected ignored directory pattern from the list."""
        current_item = self.ignored_dirs_list.currentItem()
        if not current_item:
            QMessageBox.information(self, "No Selection",
                                  "Please select a pattern to remove.")
            return

        row = self.ignored_dirs_list.row(current_item)
        self.ignored_dirs_list.takeItem(row)
        self.update_ignored_dirs_count()

        self.save_ignored_dirs_to_database()

    def add_preset_ignored_dirs(self):
        """Add common preset patterns for ignored directories."""
        preset_patterns = [
            "@eaDir", ".git", ".svn", "node_modules", "venv", ".venv",
            "__pycache__", "$RECYCLE.BIN", ".Trash-*", "Thumbs.db",
            ".DS_Store", "__MACOSX", ".thumbnails", "*.tmp", ".cache",
        ]

        added_count = 0
        for pattern in preset_patterns:
            exists = False
            for i in range(self.ignored_dirs_list.count()):
                if self.ignored_dirs_list.item(i).text().lower() == pattern.lower():
                    exists = True
                    break

            if not exists:
                self.ignored_dirs_list.addItem(pattern)
                added_count += 1

        self.update_ignored_dirs_count()

        if added_count > 0:
            self.save_ignored_dirs_to_database()
            QMessageBox.information(self, "Presets Added",
                                   f"Added {added_count} preset patterns.\n"
                                   f"Total patterns: {self.ignored_dirs_list.count()}")
        else:
            QMessageBox.information(self, "No New Presets",
                                   "All preset patterns are already in the list.")

    def update_ignored_dirs_count(self):
        """Update the ignored directories count label."""
        count = self.ignored_dirs_list.count()
        self.ignored_dirs_count_label.setText(f"Total patterns: {count}")

    def save_ignored_dirs_to_database(self):
        """Save ignored directories to database."""
        if self.db_metadata is None:
            return

        patterns = []
        for i in range(self.ignored_dirs_list.count()):
            patterns.append(self.ignored_dirs_list.item(i).text())

        try:
            self.db_metadata.set_ignored_directories(patterns)
            logger.info(f"Saved {len(patterns)} ignored directory patterns to database")
        except Exception as e:
            logger.error(f"Failed to save ignored directories: {e}")
            QMessageBox.critical(self, "Error",
                               f"Failed to save ignored directories to database:\n\n{str(e)}")

    def load_ignored_dirs_from_database(self):
        """Load ignored directories from database."""
        if self.db_metadata is None:
            return

        try:
            patterns = self.db_metadata.get_ignored_directories()
            self.ignored_dirs_list.clear()
            for pattern in patterns:
                self.ignored_dirs_list.addItem(pattern)
            self.update_ignored_dirs_count()
            logger.info(f"Loaded {len(patterns)} ignored directory patterns from database")
        except Exception as e:
            logger.error(f"Failed to load ignored directories from database: {e}")

    # ========== Filename Pattern Filtering Methods ==========

    def update_pattern_controls(self):
        """Enable/disable pattern controls based on checkbox."""
        enabled = self.filename_filter_check.isChecked()
        self.pattern_list.setEnabled(enabled)
        self.add_pattern_input.setEnabled(enabled)
        self.add_pattern_btn.setEnabled(enabled)
        self.remove_pattern_btn.setEnabled(enabled)
        self.add_default_patterns_btn.setEnabled(enabled)

    def add_pattern(self):
        """Add a new pattern to the list."""
        pattern = self.add_pattern_input.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Empty Pattern",
                              "Please enter a pattern to add.")
            return

        for i in range(self.pattern_list.count()):
            if self.pattern_list.item(i).text().lower() == pattern.lower():
                QMessageBox.information(self, "Pattern Exists",
                                      f"Pattern '{pattern}' already exists in the list.")
                return

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

    # ========== Archive Location Methods ==========

    def on_browse_archive_clicked(self):
        """Handle browse button click for archive location."""
        archive_location = self.archive_path_edit.text()

        QMessageBox.information(
            self,
            "Archive Location Managed by Database",
            f"The archive location is controlled by the database you selected.\n\n"
            f"Current archive: {archive_location if archive_location else 'Not set'}\n"
            f"Database: {self.db_name_label.text()}\n\n"
            f"To change the archive location, you would need to migrate your archive.\n"
            f"This feature will be available in a future update."
        )

    # ========== Organization Template Methods ==========

    def on_preset_changed(self, preset_name):
        """Handle preset selection change."""
        if preset_name == "Custom Template...":
            self.custom_template_widget.show()
            if not self.custom_template_edit.text():
                self.custom_template_edit.setText(self.current_template)
        else:
            self.custom_template_widget.hide()
            preset = OrganizationTemplate.get_preset_by_name(preset_name)
            if preset:
                self.current_template = preset['template']

        self.update_organization_preview()
        self.check_organization_lock()

    def on_custom_template_changed(self, text):
        """Validate and update preview for custom template."""
        if not text.strip():
            self.template_validation_label.setText("")
            return

        is_valid, error_msg = OrganizationTemplate.validate(text)

        if is_valid:
            self.template_validation_label.setText("✓ Valid template")
            self.template_validation_label.setStyleSheet("color: green; font-weight: bold;")
            self.current_template = text
            self.update_organization_preview()
        else:
            self.template_validation_label.setText(f"✗ {error_msg}")
            self.template_validation_label.setStyleSheet("color: red; font-weight: bold;")

        self.check_organization_lock()

    def insert_placeholder(self, placeholder):
        """Insert placeholder at cursor position in custom template."""
        cursor_pos = self.custom_template_edit.cursorPosition()
        current_text = self.custom_template_edit.text()
        new_text = current_text[:cursor_pos] + placeholder + current_text[cursor_pos:]
        self.custom_template_edit.setText(new_text)
        self.custom_template_edit.setCursorPosition(cursor_pos + len(placeholder))
        self.custom_template_edit.setFocus()

    def update_organization_preview(self):
        """Generate and display example paths."""
        is_valid, error_msg = OrganizationTemplate.validate(self.current_template)

        if not is_valid:
            self.org_description_label.setText(f"Invalid template: {error_msg}")
            self.org_preview_label.setText("")
            return

        description = OrganizationTemplate.format_description(self.current_template)
        self.org_description_label.setText(description)

        examples = OrganizationTemplate.generate_examples(self.current_template)
        example_text = "\n".join(examples)
        self.org_preview_label.setText(example_text)

    def check_organization_lock(self):
        """Check if organization settings are locked and show warning."""
        if self.db_metadata is None:
            self.org_lock_warning.hide()
            self.reorganize_btn.hide()
            return

        metadata = self.db_metadata.get_metadata()
        if not metadata:
            self.org_lock_warning.hide()
            self.reorganize_btn.hide()
            return

        total_photos = metadata.get('total_photos', 0)
        current_db_template = metadata.get('organization_template', '{YYYY}/{MM}/{DD}')
        current_db_file_type_mode = metadata.get('file_type_organization', 'combined')

        if self.file_type_combined_radio.isChecked():
            current_file_type_mode = 'combined'
        elif self.file_type_subfolder_radio.isChecked():
            current_file_type_mode = 'subfolder'
        else:
            current_file_type_mode = 'separate_archive'

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

        metadata = self.db_metadata.get_metadata()
        if not metadata:
            self.rename_lock_warning.hide()
            self.rename_reorganize_btn.hide()
            return

        total_photos = metadata.get('total_photos', 0)
        current_db_filename_template = metadata.get('filename_template', '{original_name}')

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
        if self.file_type_separate_radio.isChecked():
            self.video_archive_widget.show()
        else:
            self.video_archive_widget.hide()

        self.check_organization_lock()

    def on_browse_video_archive(self):
        """Browse for video archive location."""
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
            if self.file_type_combined_radio.isChecked():
                file_type_mode = 'combined'
            elif self.file_type_subfolder_radio.isChecked():
                file_type_mode = 'subfolder'
            else:
                file_type_mode = 'separate_archive'

            if file_type_mode == 'separate_archive':
                video_archive_location = self.video_archive_path_edit.text().strip()
                if not video_archive_location:
                    QMessageBox.warning(
                        self,
                        "Video Archive Location Required",
                        "Please specify a video archive location when using separate archive mode."
                    )
                    return False

                self.db_metadata.set_video_archive(video_archive_location, enabled=True)
            else:
                self.db_metadata.set_video_archive("", enabled=False)

            self.db_metadata.set_organization_template(self.current_template)
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
        """Show reorganization dialog."""
        QMessageBox.information(
            self,
            "Reorganization",
            "Reorganization feature will be implemented in a future update.\n\n"
            "This will allow you to migrate your entire archive to the new folder structure."
        )

    # ========== File Renaming Methods ==========

    def on_rename_enabled_changed(self, state):
        """Handle enable/disable file renaming checkbox change."""
        try:
            enabled = self.enable_rename_check.isChecked()

            if not self.db_metadata:
                QMessageBox.critical(self, "Error",
                                   "Database connection not initialized.\nPlease load or create a database first.")
                return

            success = self.db_metadata.set_file_rename_enabled(enabled)

            if success:
                status = "enabled" if enabled else "disabled"
                logger.info(f"✓ File renaming {status} successfully")
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
        try:
            from filename_template import FilenameTemplate

            self.rename_validation_label.clear()

            if not template:
                self.rename_example_label.setText("IMG_1234.jpg")
                self.rename_preview_label.setText("IMG_1234.jpg")
                return

            is_valid, error_msg = FilenameTemplate.validate(template)

            if not is_valid:
                logger.warning(f"⚠ Template validation failed: {error_msg}")
                self.rename_validation_label.setText(f"⚠ {error_msg}")
                self.rename_example_label.setStyleSheet("color: red; font-weight: bold;")
                self.rename_example_label.setText("Invalid template")
                self.rename_preview_label.setStyleSheet("color: red; font-weight: bold;")
                self.rename_preview_label.setText("Error")
                return

            example_output = FilenameTemplate.get_example_output(template)

            self.rename_example_label.setStyleSheet("color: green; font-weight: bold;")
            self.rename_example_label.setText(example_output)
            self.rename_preview_label.setStyleSheet("color: blue; font-weight: bold;")
            self.rename_preview_label.setText(example_output)

            self.current_filename_template = template

            if self.db_metadata:
                success = self.db_metadata.set_filename_template(template)
                if success:
                    logger.info(f"✓ Template saved to database: '{template}'")
                else:
                    logger.error(f"✗ Failed to save template to database")
                    self.rename_validation_label.setText(f"⚠ Failed to save template to database")
            else:
                logger.warning("⚠ db_metadata is None - template NOT saved to database")

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

    # ========== Database Info Methods ==========

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

    # ========== Settings File Management Methods ==========

    def get_config(self):
        """Get configuration as dictionary."""
        excluded_patterns = []
        if self.filename_filter_check.isChecked():
            for i in range(self.pattern_list.count()):
                excluded_patterns.append(self.pattern_list.item(i).text())

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

        if 'organization_template' in config:
            template = config['organization_template']
        else:
            group_by_year = config.get('group_by_year', True)
            group_by_day = config.get('group_by_day', True)
            if group_by_year and group_by_day:
                template = '{YYYY}/{MM}/{DD}'
            elif group_by_year:
                template = '{YYYY}/{MM}'
            else:
                template = '{YYYY}/{MM}/{DD}'

        self.current_template = template

        preset = OrganizationTemplate.get_preset_by_template(template)
        if preset:
            preset_name = preset['name']
            index = self.org_preset_combo.findText(preset_name)
            if index >= 0:
                self.org_preset_combo.setCurrentIndex(index)
        else:
            self.org_preset_combo.setCurrentText("Custom Template...")
            self.custom_template_edit.setText(template)

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

        patterns = config.get('excluded_filename_patterns', constants.DEFAULT_EXCLUDED_PATTERNS)
        self.pattern_list.clear()
        for pattern in patterns:
            self.pattern_list.addItem(pattern)

        has_patterns = len(patterns) > 0
        self.filename_filter_check.setChecked(has_patterns)
        self.update_pattern_controls()
        self.update_pattern_count()

        self.update_organization_preview()

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

            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r') as f:
                    existing = json.load(f)
                config['source_directory'] = existing.get('source_directory', [])
                config['destination_directory'] = existing.get('destination_directory', "")
                config['copy_files'] = existing.get('copy_files', True)
                config['move_files'] = existing.get('move_files', False)

            try:
                Config(config)
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

    # ========== Database Integration Methods ==========

    def set_database(self, db_metadata):
        """Load settings from database."""
        self.db_metadata = db_metadata

        if db_metadata is None:
            return

        # Load archive location
        archive_location = db_metadata.get_archive_location()
        if archive_location:
            self.archive_path_edit.setText(archive_location)
            if os.path.exists(archive_location):
                self.archive_status_label.setText("✓ Archive folder exists")
                self.archive_status_label.setStyleSheet("font-size: 10px; color: green; margin-top: 5px;")
            else:
                self.archive_status_label.setText("⚠ Warning: Archive folder does not exist!")
                self.archive_status_label.setStyleSheet("font-size: 10px; color: red; margin-top: 5px;")

        # Load organization template
        template = db_metadata.get_organization_template()
        self.current_template = template

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
        mode = db_metadata.get_file_type_organization()
        if mode == 'combined':
            self.file_type_combined_radio.setChecked(True)
        elif mode == 'subfolder':
            self.file_type_subfolder_radio.setChecked(True)
        elif mode == 'separate_archive':
            self.file_type_separate_radio.setChecked(True)

        if mode == 'separate_archive':
            video_archive_location = db_metadata.get_video_archive_location()
            if video_archive_location:
                self.video_archive_path_edit.setText(video_archive_location)

        self.update_organization_preview()
        self.check_organization_lock()

        # Load filename rename settings
        rename_enabled = db_metadata.is_file_rename_enabled()
        self.enable_rename_check.setChecked(rename_enabled)

        filename_template = db_metadata.get_filename_template()
        self.current_filename_template = filename_template
        self.filename_template_edit.setText(filename_template)

        self.on_filename_template_changed(filename_template)

        # Load retention settings
        self.load_retention_settings()

        # Load cache settings
        cache_memory_mb = db_metadata.get_cache_memory_mb()
        worker_threads = db_metadata.get_cache_worker_threads()

        self.cache_memory_spin.blockSignals(True)
        self.worker_threads_spin.blockSignals(True)

        self.cache_memory_spin.setValue(cache_memory_mb)
        self.worker_threads_spin.setValue(worker_threads)

        self.cache_memory_spin.blockSignals(False)
        self.worker_threads_spin.blockSignals(False)

        self.update_cache_items_label()

        # Load sources and ignored directories
        self.load_sources_from_database()
        self.load_ignored_dirs_from_database()

        # Load database info
        metadata = db_metadata.get_metadata()
        if metadata:
            self.db_name_label.setText(metadata.get('database_name', 'Unknown'))
            self.db_file_label.setText(os.path.basename(db_metadata.database_path))

            created_date = metadata.get('created_date', 'Unknown')
            if created_date and created_date != 'Unknown':
                self.db_created_label.setText(created_date[:10])
            else:
                self.db_created_label.setText('Unknown')

            last_used = metadata.get('last_used_date', 'Never')
            if last_used and last_used != 'Never':
                self.db_last_used_label.setText(last_used[:10])
            else:
                self.db_last_used_label.setText('Never')

            total_photos = metadata.get('total_photos', 0)
            self.total_photos_label.setText(f"{total_photos:,}")

            schema_version = metadata.get('schema_version', 1)
            self.schema_version_label.setText(str(schema_version))
