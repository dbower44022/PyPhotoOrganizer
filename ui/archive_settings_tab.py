"""
Archive Settings Tab for PyPhotoOrganizer GUI

Manages archive-related settings including:
- Archive Location (with file verification when changing locations)
- Prior Revision Archive location
- Organization Settings (folder structure presets + custom templates with preview)
- File Type Organization (combined/subfolder/separate archive for videos)
- File Renaming settings (enable checkbox, template editor, preview)
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QCheckBox, QLineEdit, QPushButton, QLabel,
                               QMessageBox, QScrollArea, QFormLayout, QComboBox,
                               QTextEdit, QRadioButton, QButtonGroup, QFileDialog,
                               QFrame, QProgressBar)
from PySide6.QtCore import Qt, Signal
import os
import json
from organization_template import OrganizationTemplate
import logging

logger = logging.getLogger(__name__)

# Import cloud settings widget and sync worker
try:
    from ui.cloud_settings_widget import CloudSettingsWidget
    CLOUD_SETTINGS_AVAILABLE = True
except ImportError:
    CLOUD_SETTINGS_AVAILABLE = False
    logger.warning("CloudSettingsWidget not available")

try:
    from ui.cloud_sync_worker import CloudSyncWorker, SyncStatusPoller
    CLOUD_SYNC_AVAILABLE = True
except ImportError:
    CLOUD_SYNC_AVAILABLE = False
    logger.warning("CloudSyncWorker not available")


class ArchiveSettingsTab(QWidget):
    """Tab for managing archive organization and file renaming settings."""

    def __init__(self):
        super().__init__()
        self.db_metadata = None  # Will be set when database is loaded
        self.current_template = '{YYYY}/{MM}/{DD}'  # Default organization template
        self.current_filename_template = '{original_name}'  # Default filename template

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
            "You can change this if you've moved your archive to a new location."
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
        self.browse_archive_btn.setToolTip("Select or change the archive location")
        self.browse_archive_btn.clicked.connect(self.on_browse_archive_clicked)
        archive_path_layout.addWidget(self.browse_archive_btn)

        archive_layout.addLayout(archive_path_layout)

        self.archive_status_label = QLabel("")
        self.archive_status_label.setWordWrap(True)
        self.archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")
        archive_layout.addWidget(self.archive_status_label)

        archive_group.setLayout(archive_layout)
        layout.addWidget(archive_group)

        # Prior Revision Archive Group
        prior_archive_group = QGroupBox("Prior Revision Archive")
        prior_archive_group.setStyleSheet(self.groupbox_style)
        prior_archive_layout = QVBoxLayout()

        prior_archive_info = QLabel(
            "Prior Revision Archive stores historical versions of rotated images.\n"
            "When you rotate an image, the original is moved here automatically,\n"
            "keeping your main archive clean with only current revisions."
        )
        prior_archive_info.setWordWrap(True)
        prior_archive_info.setStyleSheet("color: #666; font-size: 11px; margin-bottom: 5px;")
        prior_archive_layout.addWidget(prior_archive_info)

        prior_archive_path_layout = QHBoxLayout()
        self.prior_archive_path_edit = QLineEdit()
        self.prior_archive_path_edit.setReadOnly(True)
        self.prior_archive_path_edit.setPlaceholderText("Not configured (rotation disabled)")
        self.prior_archive_path_edit.setStyleSheet("background-color: #f5f5f5;")
        prior_archive_path_layout.addWidget(self.prior_archive_path_edit)

        self.browse_prior_archive_btn = QPushButton("Browse...")
        self.browse_prior_archive_btn.setToolTip("Select a directory for prior revision storage (auto-saves)")
        self.browse_prior_archive_btn.clicked.connect(self.on_browse_prior_archive)
        prior_archive_path_layout.addWidget(self.browse_prior_archive_btn)

        self.clear_prior_archive_btn = QPushButton("Clear")
        self.clear_prior_archive_btn.setToolTip("Clear Prior Revision Archive location (disables rotation)")
        self.clear_prior_archive_btn.clicked.connect(self.on_clear_prior_archive)
        prior_archive_path_layout.addWidget(self.clear_prior_archive_btn)

        prior_archive_layout.addLayout(prior_archive_path_layout)

        self.prior_archive_status_label = QLabel("")
        self.prior_archive_status_label.setWordWrap(True)
        self.prior_archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")
        prior_archive_layout.addWidget(self.prior_archive_status_label)

        # Help text
        help_label = QLabel(
            "<b>Important:</b> Prior Revision Archive must be:\n"
            "• Different from main archive\n"
            "• Not inside main archive\n"
            "• Writable with sufficient disk space"
        )
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-size: 10px; color: #444; margin-top: 10px; padding: 5px; background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 3px;")
        prior_archive_layout.addWidget(help_label)

        prior_archive_group.setLayout(prior_archive_layout)
        layout.addWidget(prior_archive_group)

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

        # Cloud Storage Settings (Beta)
        if CLOUD_SETTINGS_AVAILABLE:
            cloud_group = QGroupBox("Cloud Storage (Beta)")
            cloud_group.setStyleSheet(self.groupbox_style)
            cloud_layout = QVBoxLayout()

            # Beta notice
            beta_notice = QLabel(
                "Configure cloud storage backends for your archive. "
                "This feature is in beta - local storage is recommended for most users."
            )
            beta_notice.setWordWrap(True)
            beta_notice.setStyleSheet("color: #856404; background-color: #fff3cd; padding: 8px; border-radius: 4px; margin-bottom: 10px;")
            cloud_layout.addWidget(beta_notice)

            # Cloud settings widget
            self.cloud_settings_widget = CloudSettingsWidget()
            self.cloud_settings_widget.config_changed.connect(self._on_cloud_config_changed)
            cloud_layout.addWidget(self.cloud_settings_widget)

            # Sync controls section
            sync_frame = QFrame()
            sync_frame.setStyleSheet("QFrame { border: 1px solid #ddd; border-radius: 4px; padding: 10px; margin-top: 10px; }")
            sync_layout = QVBoxLayout(sync_frame)
            sync_layout.setContentsMargins(10, 10, 10, 10)

            sync_header = QLabel("Cloud Sync")
            sync_header.setStyleSheet("font-weight: bold; font-size: 12px;")
            sync_layout.addWidget(sync_header)

            # Sync status
            self.sync_status_label = QLabel("Not syncing")
            self.sync_status_label.setStyleSheet("color: #666;")
            sync_layout.addWidget(self.sync_status_label)

            # Progress bar
            self.sync_progress_bar = QProgressBar()
            self.sync_progress_bar.setVisible(False)
            self.sync_progress_bar.setTextVisible(True)
            sync_layout.addWidget(self.sync_progress_bar)

            # Sync buttons
            sync_btn_layout = QHBoxLayout()

            self.sync_now_btn = QPushButton("Sync Now")
            self.sync_now_btn.setToolTip("Upload all un-synced files to cloud storage")
            self.sync_now_btn.clicked.connect(self._on_sync_now_clicked)
            sync_btn_layout.addWidget(self.sync_now_btn)

            self.stop_sync_btn = QPushButton("Stop")
            self.stop_sync_btn.setToolTip("Stop the current sync operation")
            self.stop_sync_btn.clicked.connect(self._on_stop_sync_clicked)
            self.stop_sync_btn.setVisible(False)
            sync_btn_layout.addWidget(self.stop_sync_btn)

            self.check_status_btn = QPushButton("Check Status")
            self.check_status_btn.setToolTip("Check sync status for all vaults")
            self.check_status_btn.clicked.connect(self._on_check_status_clicked)
            sync_btn_layout.addWidget(self.check_status_btn)

            sync_btn_layout.addStretch()
            sync_layout.addLayout(sync_btn_layout)

            cloud_layout.addWidget(sync_frame)

            # Initialize sync worker reference
            self.sync_worker = None
            self.status_poller = None

            cloud_group.setLayout(cloud_layout)
            layout.addWidget(cloud_group)
        else:
            self.cloud_settings_widget = None
            self.sync_worker = None
            self.status_poller = None

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

        # Set the scroll area as the main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ========== Archive Location Methods ==========

    def on_browse_archive_clicked(self):
        """Handle browse button click for archive location."""
        if self.db_metadata is None:
            QMessageBox.information(
                self,
                "No Database Loaded",
                "Please load or create a database first before setting an archive location."
            )
            return

        current_location = self.archive_path_edit.text()
        metadata = self.db_metadata.get_metadata()
        total_photos = metadata.get('total_photos', 0) if metadata else 0

        # Show dialog explaining what changing archive location does
        if total_photos > 0:
            reply = QMessageBox.question(
                self,
                "Change Archive Location",
                f"This archive contains {total_photos} files.\n\n"
                "Changing the archive location updates where the database expects to find files. "
                "This is useful when:\n"
                "• You've moved your archive to a new drive\n"
                "• You want to point to a different existing archive\n\n"
                "Note: This does NOT move files automatically. If you've moved files, "
                "select the new location where they now reside.\n\n"
                "Would you like to select a new archive location?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        else:
            # No files yet, simpler message
            reply = QMessageBox.question(
                self,
                "Set Archive Location",
                "This will set where your organized photos will be stored.\n\n"
                "Select the folder you want to use as your photo archive.\n\n"
                "Continue?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply != QMessageBox.Yes:
                return

        # Get starting directory for file dialog
        start_dir = current_location if current_location and os.path.exists(current_location) else os.path.expanduser("~")

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Archive Location",
            start_dir
        )

        # User cancelled
        if not folder:
            return

        # Validate the selected path
        if not os.path.exists(folder):
            QMessageBox.warning(
                self,
                "Invalid Path",
                f"The specified path does not exist:\n\n{folder}\n\nPlease create the directory first or select an existing one."
            )
            return

        if not os.path.isdir(folder):
            QMessageBox.warning(
                self,
                "Invalid Path",
                f"The specified path is not a directory:\n\n{folder}"
            )
            return

        if not os.access(folder, os.W_OK):
            QMessageBox.warning(
                self,
                "Permission Error",
                f"The specified path is not writable:\n\n{folder}\n\nPlease check permissions."
            )
            return

        # Check for conflicts with Prior Revision Archive
        prior_archive = self.db_metadata.get_prior_revision_archive_location()
        if prior_archive:
            prior_real = os.path.realpath(prior_archive)
            folder_real = os.path.realpath(folder)

            if folder_real == prior_real:
                QMessageBox.warning(
                    self,
                    "Invalid Configuration",
                    "Archive location cannot be the same as the Prior Revision Archive.\n\n"
                    "Please select a different location."
                )
                return

            if prior_real.startswith(folder_real + os.sep):
                QMessageBox.warning(
                    self,
                    "Invalid Configuration",
                    "The Prior Revision Archive is inside this folder.\n\n"
                    "This could cause issues. Please select a different location or "
                    "change the Prior Revision Archive first."
                )
                return

        # Check for conflicts with Video Archive
        video_archive = self.db_metadata.get_video_archive_location()
        if video_archive:
            video_real = os.path.realpath(video_archive)
            folder_real = os.path.realpath(folder)

            if folder_real == video_real:
                QMessageBox.warning(
                    self,
                    "Invalid Configuration",
                    "Archive location cannot be the same as the Video Archive.\n\n"
                    "Please select a different location."
                )
                return

        # Verify files exist at new location if there are files in the database
        if total_photos > 0:
            verification_result = self._verify_archive_files_at_location(
                current_location, folder, sample_size=min(100, total_photos)
            )

            if verification_result['checked'] > 0:
                found = verification_result['found']
                missing = verification_result['missing']
                checked = verification_result['checked']

                if missing > 0:
                    # Some files are missing - warn user
                    percentage_found = (found / checked) * 100

                    if found == 0:
                        # No files found at new location
                        reply = QMessageBox.warning(
                            self,
                            "No Files Found",
                            f"None of the {checked} sampled files were found at the new location.\n\n"
                            f"This suggests the files have not been moved to:\n{folder}\n\n"
                            "Are you sure you want to change the archive location?\n"
                            "This may make your existing photos inaccessible.",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if reply != QMessageBox.Yes:
                            return
                    else:
                        # Partial files found
                        reply = QMessageBox.warning(
                            self,
                            "Some Files Missing",
                            f"Verification Results:\n"
                            f"• Checked: {checked} files (sample)\n"
                            f"• Found: {found} ({percentage_found:.1f}%)\n"
                            f"• Missing: {missing}\n\n"
                            f"Some files were not found at the new location.\n"
                            f"Missing files will not be accessible until they are moved.\n\n"
                            "Do you want to proceed anyway?",
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if reply != QMessageBox.Yes:
                            return
                else:
                    # All sampled files found - show confirmation
                    logger.info(f"Archive verification: {found}/{checked} sampled files found at {folder}")

        # All validation passed - save to database
        success = self.db_metadata.update_archive_location(folder)

        if success:
            # Update UI
            self.archive_path_edit.setText(folder)
            if os.path.exists(folder):
                self.archive_status_label.setText("✓ Archive folder exists")
                self.archive_status_label.setStyleSheet("font-size: 10px; color: green; margin-top: 5px;")
            else:
                self.archive_status_label.setText("⚠ Warning: Archive folder does not exist!")
                self.archive_status_label.setStyleSheet("font-size: 10px; color: red; margin-top: 5px;")

            if total_photos > 0:
                QMessageBox.information(
                    self,
                    "Archive Location Updated",
                    f"Archive location has been updated to:\n\n{folder}\n\n"
                    "If you moved your files to this location, they should now be accessible.\n"
                    "If files are missing, use Photo Review to verify the archive contents."
                )
            else:
                QMessageBox.information(
                    self,
                    "Archive Location Set",
                    f"Archive location has been set to:\n\n{folder}\n\n"
                    "New photos will be organized into this folder during import."
                )
            logger.info(f"Archive location updated: {folder}")
        else:
            self.archive_status_label.setText("✗ Failed to save configuration")
            self.archive_status_label.setStyleSheet("font-size: 10px; color: red; margin-top: 5px;")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save archive location.\n\nCheck the log for details."
            )

    def _verify_archive_files_at_location(self, old_location: str, new_location: str,
                                          sample_size: int = 100) -> dict:
        """
        Verify that archive files exist at the new location.

        Gets a sample of files from the database and checks if they exist
        at the corresponding paths in the new location.

        Args:
            old_location: Current archive location stored in database
            new_location: New location to verify files at
            sample_size: Number of files to sample for verification

        Returns:
            dict with keys:
                - checked: Number of files checked
                - found: Number of files found at new location
                - missing: Number of files not found
                - missing_files: List of missing file paths (up to 10)
        """
        result = {
            'checked': 0,
            'found': 0,
            'missing': 0,
            'missing_files': []
        }

        if not old_location or not new_location:
            return result

        try:
            from DuplicateFileDetection import PhotoDatabase

            # Get sample of files from database
            db = PhotoDatabase(self.db_metadata.db_path)

            # Query for a sample of files
            db.cursor.execute(
                """SELECT file_name FROM UniquePhotos
                   WHERE file_name LIKE ? || '%'
                   AND revised_photo IS NULL
                   LIMIT ?""",
                (old_location + os.sep if not old_location.endswith(os.sep) else old_location,
                 sample_size)
            )
            files = db.cursor.fetchall()
            db.close()

            # Normalize paths for comparison
            old_location_normalized = os.path.normpath(old_location)
            new_location_normalized = os.path.normpath(new_location)

            for (file_path,) in files:
                result['checked'] += 1

                # Calculate expected path at new location
                file_path_normalized = os.path.normpath(file_path)

                if file_path_normalized.startswith(old_location_normalized):
                    # Get relative path from old archive
                    relative_path = file_path_normalized[len(old_location_normalized):].lstrip(os.sep)
                    # Build expected path at new location
                    expected_path = os.path.join(new_location_normalized, relative_path)

                    if os.path.exists(expected_path):
                        result['found'] += 1
                    else:
                        result['missing'] += 1
                        if len(result['missing_files']) < 10:
                            result['missing_files'].append(relative_path)
                else:
                    # File path doesn't match old location - skip it
                    result['checked'] -= 1
                    logger.warning(f"File path doesn't match old location: {file_path}")

        except Exception as e:
            logger.error(f"Error verifying archive files: {e}")
            # Return empty result on error - don't block the operation
            return result

        return result

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

    def on_reorganize_clicked(self):
        """Show reorganization dialog."""
        QMessageBox.information(
            self,
            "Reorganization",
            "Reorganization feature will be implemented in a future update.\n\n"
            "This will allow you to migrate your entire archive to the new folder structure."
        )

    # ========== File Type Organization Methods ==========

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

    # ========== Prior Revision Archive Methods ==========

    def on_browse_prior_archive(self):
        """Browse for Prior Revision Archive location and auto-save."""
        if self.db_metadata is None:
            QMessageBox.critical(
                self,
                "Error",
                "Database connection not initialized.\nPlease load or create a database first."
            )
            return

        # Get current path or default to home directory
        current_path = self.prior_archive_path_edit.text() or os.path.expanduser("~")

        folder = QFileDialog.getExistingDirectory(
            self,
            "Select Prior Revision Archive Location",
            current_path
        )

        # User cancelled
        if not folder:
            return

        # Validate path exists
        if not os.path.exists(folder):
            QMessageBox.warning(
                self,
                "Invalid Path",
                f"The specified path does not exist:\n\n{folder}\n\nPlease create the directory first."
            )
            return

        # Validate is directory
        if not os.path.isdir(folder):
            QMessageBox.warning(
                self,
                "Invalid Path",
                f"The specified path is not a directory:\n\n{folder}"
            )
            return

        # Validate writable
        if not os.access(folder, os.W_OK):
            QMessageBox.warning(
                self,
                "Permission Error",
                f"The specified path is not writable:\n\n{folder}\n\nPlease check permissions."
            )
            return

        # Get main archive location for validation
        archive_base = self.db_metadata.get_archive_location()

        # Check if same as main archive
        if archive_base and os.path.realpath(folder) == os.path.realpath(archive_base):
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "Prior Revision Archive cannot be the same as the main archive.\n\n"
                "Please select a different location."
            )
            return

        # Check if inside main archive
        if archive_base and os.path.realpath(folder).startswith(os.path.realpath(archive_base) + os.sep):
            QMessageBox.warning(
                self,
                "Invalid Configuration",
                "Prior Revision Archive cannot be inside the main archive.\n\n"
                "Please select a location outside the main archive."
            )
            return

        # All validation passed - save to database
        success = self.db_metadata.set_prior_revision_archive_location(folder)

        if success:
            # Update UI
            self.prior_archive_path_edit.setText(folder)
            self.prior_archive_status_label.setText(f"✓ Configured: {folder}")
            self.prior_archive_status_label.setStyleSheet("font-size: 10px; color: #28a745; margin-top: 5px;")

            # Show success message
            QMessageBox.information(
                self,
                "Success",
                f"Prior Revision Archive location saved successfully.\n\nLocation: {folder}\n\n"
                "Image rotation is now enabled.\n"
                "When you rotate images, originals will be moved to this location automatically."
            )
            logger.info(f"Prior Revision Archive configured: {folder}")
        else:
            # Save failed
            self.prior_archive_status_label.setText("✗ Failed to save configuration")
            self.prior_archive_status_label.setStyleSheet("font-size: 10px; color: #dc3545; margin-top: 5px;")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to save Prior Revision Archive location.\n\nCheck the log for details."
            )

    def on_clear_prior_archive(self):
        """Clear Prior Revision Archive location (disables rotation)."""
        if self.db_metadata is None:
            QMessageBox.critical(
                self,
                "Error",
                "Database connection not initialized.\nPlease load or create a database first."
            )
            return

        # Check if already empty
        current_path = self.prior_archive_path_edit.text().strip()
        if not current_path:
            QMessageBox.information(
                self,
                "Already Clear",
                "Prior Revision Archive is not configured."
            )
            return

        # Confirm clearing
        reply = QMessageBox.question(
            self,
            "Clear Prior Revision Archive",
            "This will disable the Prior Revision Archive.\n"
            "You will not be able to rotate images until you configure a new location.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply != QMessageBox.Yes:
            return

        # Clear from database
        success = self.db_metadata.set_prior_revision_archive_location("")

        if success:
            # Update UI
            self.prior_archive_path_edit.setText("")
            self.prior_archive_status_label.setText("ℹ Prior Revision Archive cleared (rotation disabled)")
            self.prior_archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")

            QMessageBox.information(
                self,
                "Success",
                "Prior Revision Archive has been cleared.\nImage rotation is now disabled."
            )
            logger.info("Prior Revision Archive cleared")
        else:
            QMessageBox.critical(
                self,
                "Error",
                "Failed to clear Prior Revision Archive location."
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

    def on_rename_reorganize_clicked(self):
        """Show reorganization dialog for filename template changes."""
        QMessageBox.information(
            self,
            "Reorganization",
            "Reorganization feature will be implemented in a future update.\n\n"
            "This will allow you to rename all files in the archive using the new template."
        )

    # ========== Cloud Storage Methods ==========

    def _on_cloud_config_changed(self, config: dict):
        """Handle cloud configuration changes."""
        if self.db_metadata is None:
            return

        try:
            # Save cloud config to database metadata
            # The database methods handle JSON serialization internally
            storage_config = config.get('storage', {})
            cloud_defaults = config.get('cloud_defaults', {})

            # Update database metadata
            self.db_metadata.set_storage_config(storage_config)
            self.db_metadata.set_cloud_defaults(cloud_defaults)

            logger.info("Cloud storage configuration saved")

        except Exception as e:
            logger.error(f"Failed to save cloud config: {e}", exc_info=True)

    def get_cloud_storage_config(self) -> dict:
        """Get the current cloud storage configuration."""
        if self.cloud_settings_widget:
            return self.cloud_settings_widget.get_storage_config()
        return {'storage': {}, 'cloud_defaults': {}}

    # ========== Cloud Sync Methods ==========

    def _on_sync_now_clicked(self):
        """Start cloud sync operation."""
        if not CLOUD_SYNC_AVAILABLE:
            QMessageBox.warning(
                self,
                "Cloud Sync Unavailable",
                "Cloud sync functionality is not available.\n"
                "Please check that all dependencies are installed."
            )
            return

        if not self.db_metadata:
            QMessageBox.information(
                self,
                "No Database",
                "Please open a database first before syncing."
            )
            return

        # Check if any vault has cloud storage configured
        storage_config = self.db_metadata.get_storage_config()
        if not storage_config:
            QMessageBox.information(
                self,
                "No Cloud Storage Configured",
                "No cloud storage has been configured.\n\n"
                "Please configure a cloud storage provider for at least one vault "
                "before syncing."
            )
            return

        # Check for cloud vaults
        has_cloud = False
        for vault, config in storage_config.items():
            if isinstance(config, dict) and config.get('provider', 'local') != 'local':
                has_cloud = True
                break

        if not has_cloud:
            QMessageBox.information(
                self,
                "No Cloud Storage",
                "All vaults are configured for local storage.\n\n"
                "Configure a cloud provider (e.g., S3) for a vault to enable sync."
            )
            return

        # Start sync
        self._start_sync()

    def _start_sync(self):
        """Initialize and start the sync worker."""
        try:
            from storage_backend import StorageManager

            # Create storage manager from config
            storage_config = self.db_metadata.get_storage_config()
            storage_manager = StorageManager(storage_config)

            # Create and configure worker
            self.sync_worker = CloudSyncWorker(
                self.db_metadata.database_path,
                storage_manager,
                parent=self
            )
            self.sync_worker.configure(
                vault_type='archive',
                operation='sync_to_cloud'
            )

            # Connect signals
            self.sync_worker.progress.connect(self._on_sync_progress)
            self.sync_worker.sync_completed.connect(self._on_sync_completed)
            self.sync_worker.error.connect(self._on_sync_error)

            # Update UI
            self.sync_now_btn.setVisible(False)
            self.stop_sync_btn.setVisible(True)
            self.check_status_btn.setEnabled(False)
            self.sync_progress_bar.setVisible(True)
            self.sync_progress_bar.setValue(0)
            self.sync_status_label.setText("Starting sync...")
            self.sync_status_label.setStyleSheet("color: #0066cc;")

            # Start worker
            self.sync_worker.start()

            logger.info("Cloud sync started")

        except Exception as e:
            logger.error(f"Failed to start sync: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Sync Error",
                f"Failed to start sync:\n{str(e)}"
            )

    def _on_stop_sync_clicked(self):
        """Stop the current sync operation."""
        if self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.request_stop()
            self.sync_status_label.setText("Stopping sync...")
            self.stop_sync_btn.setEnabled(False)

    def _on_sync_progress(self, progress):
        """Handle sync progress updates."""
        if progress.total_files > 0:
            percent = int((progress.current_file / progress.total_files) * 100)
            self.sync_progress_bar.setValue(percent)
            self.sync_progress_bar.setFormat(f"{progress.current_file}/{progress.total_files} files")

        self.sync_status_label.setText(progress.message)

    def _on_sync_completed(self, stats: dict):
        """Handle sync completion."""
        # Update UI
        self.sync_now_btn.setVisible(True)
        self.stop_sync_btn.setVisible(False)
        self.check_status_btn.setEnabled(True)
        self.sync_progress_bar.setVisible(False)

        # Show completion message
        uploaded = stats.get('files_uploaded', 0)
        failed = stats.get('files_failed', 0)
        duration = stats.get('duration_seconds', 0)

        if failed > 0:
            self.sync_status_label.setText(
                f"Sync completed: {uploaded} uploaded, {failed} failed"
            )
            self.sync_status_label.setStyleSheet("color: #cc6600;")
        else:
            self.sync_status_label.setText(
                f"Sync completed: {uploaded} files uploaded in {duration:.1f}s"
            )
            self.sync_status_label.setStyleSheet("color: #28a745;")

        # Update last sync time
        if self.db_metadata:
            self.db_metadata.set_cloud_last_sync()

        logger.info(f"Cloud sync completed: {stats}")

        # Clean up worker
        if self.sync_worker:
            self.sync_worker.deleteLater()
            self.sync_worker = None

    def _on_sync_error(self, error_message: str):
        """Handle sync error."""
        # Update UI
        self.sync_now_btn.setVisible(True)
        self.stop_sync_btn.setVisible(False)
        self.check_status_btn.setEnabled(True)
        self.sync_progress_bar.setVisible(False)

        self.sync_status_label.setText(f"Sync error: {error_message}")
        self.sync_status_label.setStyleSheet("color: #dc3545;")

        logger.error(f"Cloud sync error: {error_message}")

        # Clean up worker
        if self.sync_worker:
            self.sync_worker.deleteLater()
            self.sync_worker = None

    def _on_check_status_clicked(self):
        """Check sync status for all vaults."""
        if not self.db_metadata:
            QMessageBox.information(
                self,
                "No Database",
                "Please open a database first."
            )
            return

        storage_config = self.db_metadata.get_storage_config()
        if not storage_config:
            QMessageBox.information(
                self,
                "No Cloud Storage",
                "No cloud storage has been configured."
            )
            return

        try:
            from storage_backend import StorageManager
            from cloud_sync_manager import CloudSyncManager
            from cloud_sync import CloudSync

            storage_manager = StorageManager(storage_config)
            sync_manager = CloudSyncManager(self.db_metadata.database_path, storage_manager)
            cloud_sync = CloudSync(self.db_metadata.database_path, sync_manager)

            # Get status for each cloud vault
            status_lines = []
            for vault_type in ['archive', 'video_archive', 'prior_revision', 'delete_vault']:
                backend = storage_manager.get_backend(vault_type)
                if backend and backend.storage_type != 'local':
                    summary = cloud_sync.get_sync_status_summary(vault_type)
                    status_lines.append(
                        f"{vault_type.replace('_', ' ').title()}:\n"
                        f"  Total files: {summary['total_files']}\n"
                        f"  Synced: {summary['synced_files']} ({summary['sync_percentage']:.1f}%)\n"
                        f"  Pending: {summary['pending_uploads']}\n"
                        f"  Failed: {summary['failed_uploads']}\n"
                        f"  Needs sync: {summary['needs_sync']}"
                    )

            if status_lines:
                QMessageBox.information(
                    self,
                    "Cloud Sync Status",
                    "\n\n".join(status_lines)
                )
            else:
                QMessageBox.information(
                    self,
                    "Cloud Sync Status",
                    "No cloud storage configured for any vault."
                )

        except Exception as e:
            logger.error(f"Failed to check sync status: {e}", exc_info=True)
            QMessageBox.warning(
                self,
                "Status Error",
                f"Failed to check sync status:\n{str(e)}"
            )

    def closeEvent(self, event):
        """Clean up workers on close."""
        if self.sync_worker and self.sync_worker.isRunning():
            self.sync_worker.request_stop()
            self.sync_worker.wait(5000)  # Wait up to 5 seconds

        if self.status_poller and self.status_poller.isRunning():
            self.status_poller.request_stop()
            self.status_poller.wait(2000)

        super().closeEvent(event) if hasattr(super(), 'closeEvent') else None

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

        # Load Prior Revision Archive location
        prior_archive_location = db_metadata.get_prior_revision_archive_location()
        if prior_archive_location:
            self.prior_archive_path_edit.setText(prior_archive_location)
            self.clear_prior_archive_btn.setEnabled(True)
            if os.path.exists(prior_archive_location):
                self.prior_archive_status_label.setText(f"✓ Configured: {prior_archive_location}")
                self.prior_archive_status_label.setStyleSheet("font-size: 10px; color: #28a745; margin-top: 5px;")
            else:
                self.prior_archive_status_label.setText("⚠ Warning: Prior archive folder does not exist!")
                self.prior_archive_status_label.setStyleSheet("font-size: 10px; color: #dc3545; margin-top: 5px;")
        else:
            self.prior_archive_path_edit.setText("")
            self.prior_archive_status_label.setText("ℹ Not configured (image rotation disabled)")
            self.prior_archive_status_label.setStyleSheet("font-size: 10px; color: #666; margin-top: 5px;")
            self.clear_prior_archive_btn.setEnabled(False)

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

        # Load cloud storage settings
        if self.cloud_settings_widget and hasattr(db_metadata, 'get_storage_config'):
            try:
                # Database methods return dicts directly (handle JSON internally)
                storage_config = db_metadata.get_storage_config()
                cloud_defaults = db_metadata.get_cloud_defaults()

                config = {
                    'storage': storage_config if storage_config else {},
                    'cloud_defaults': cloud_defaults if cloud_defaults else {}
                }

                # If no storage config, create from archive location
                if not config['storage'] and archive_location:
                    config['storage'] = {
                        'archive': {'type': 'local', 'path': archive_location}
                    }

                self.cloud_settings_widget.set_storage_config(config)
                logger.info("Cloud storage configuration loaded")

            except Exception as e:
                logger.error(f"Failed to load cloud config: {e}", exc_info=True)
