"""
Archive Settings Tab for PyPhotoOrganizer GUI

Manages archive-related settings including:
- Archive Location (read-only display from database)
- Organization Settings (folder structure presets + custom templates with preview)
- File Type Organization (combined/subfolder/separate archive for videos)
- File Renaming settings (enable checkbox, template editor, preview)
"""

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                               QCheckBox, QLineEdit, QPushButton, QLabel,
                               QMessageBox, QScrollArea, QFormLayout, QComboBox,
                               QTextEdit, QRadioButton, QButtonGroup, QFileDialog)
from PySide6.QtCore import Qt
import os
from organization_template import OrganizationTemplate
import logging

logger = logging.getLogger(__name__)


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

        # Set the scroll area as the main layout
        main_layout = QVBoxLayout()
        main_layout.addWidget(scroll)
        self.setLayout(main_layout)

    # ========== Archive Location Methods ==========

    def on_browse_archive_clicked(self):
        """Handle browse button click for archive location."""
        archive_location = self.archive_path_edit.text()

        QMessageBox.information(
            self,
            "Archive Location Managed by Database",
            f"The archive location is controlled by the database you selected.\n\n"
            f"Current archive: {archive_location if archive_location else 'Not set'}\n"
            f"Database: {self.db_metadata.get_metadata().get('database_name', 'Unknown') if self.db_metadata else 'No database loaded'}\n\n"
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
