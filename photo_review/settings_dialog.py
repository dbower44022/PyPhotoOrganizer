"""
Photo Review Settings Dialog

Modern settings dialog for the Photo Review application with intuitive
card-based layout, visual sliders, and performance presets.
"""

import logging
import os
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QFormLayout, QMessageBox, QFrame,
    QSizePolicy, QSlider, QWidget, QProgressBar, QToolButton,
    QStackedWidget, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QFont

logger = logging.getLogger(__name__)


class SettingsCard(QFrame):
    """
    Modern card widget for grouping related settings.
    """

    def __init__(self, title: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.setObjectName("settingsCard")
        self._title = title
        self._icon = icon

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(20, 16, 20, 20)
        self._layout.setSpacing(16)

        # Header
        header = QHBoxLayout()
        header.setSpacing(10)

        if icon:
            icon_label = QLabel(icon)
            icon_label.setObjectName("cardIcon")
            header.addWidget(icon_label)

        title_label = QLabel(title)
        title_label.setObjectName("cardTitle")
        header.addWidget(title_label)
        header.addStretch()

        self._layout.addLayout(header)

        # Content area
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self._layout.addWidget(self._content)

    def add_widget(self, widget: QWidget):
        """Add a widget to the card content."""
        self._content_layout.addWidget(widget)

    def add_layout(self, layout):
        """Add a layout to the card content."""
        self._content_layout.addLayout(layout)


class PresetButton(QPushButton):
    """Styled preset button for quick configuration."""

    def __init__(self, text: str, description: str = "", parent=None):
        super().__init__(text, parent)
        self.setObjectName("presetButton")
        self.description = description
        self.setToolTip(description)
        self.setCheckable(True)
        self.setMinimumHeight(60)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


class PhotoReviewSettingsDialog(QDialog):
    """
    Modern settings dialog for Photo Review application.

    Features:
    - Card-based layout for visual clarity
    - Performance presets (Low/Balanced/High)
    - Visual sliders with real-time feedback
    - Cache usage visualization
    - Clean, intuitive design

    Signals:
        settings_changed: Emitted when settings are applied
    """

    settings_changed = Signal()

    def __init__(self, db_metadata, thumbnail_cache=None, is_dark_mode: bool = True, parent=None):
        super().__init__(parent)
        self.db_metadata = db_metadata
        self.thumbnail_cache = thumbnail_cache
        self._is_dark_mode = is_dark_mode

        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.setMinimumHeight(580)

        self._init_ui()
        self._load_current_settings()
        self._apply_theme()

    def _init_ui(self):
        """Initialize the modern user interface."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QWidget()
        header.setObjectName("dialogHeader")
        header.setFixedHeight(64)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(24, 0, 24, 0)

        header_icon = QLabel("\u2699")  # Gear icon
        header_icon.setObjectName("headerIcon")
        header_layout.addWidget(header_icon)

        header_title = QLabel("Photo Review Settings")
        header_title.setObjectName("headerTitle")
        header_layout.addWidget(header_title)
        header_layout.addStretch()

        main_layout.addWidget(header)

        # Scrollable content area
        scroll = QScrollArea()
        scroll.setObjectName("settingsScroll")
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(16)
        content_layout.setContentsMargins(24, 20, 24, 20)

        # ---------------------------------------------------------------------
        # Performance Presets Card
        # ---------------------------------------------------------------------
        presets_card = SettingsCard("Quick Setup", "\u26A1")

        presets_desc = QLabel(
            "Choose a performance profile based on your computer's capabilities."
        )
        presets_desc.setObjectName("cardDescription")
        presets_desc.setWordWrap(True)
        presets_card.add_widget(presets_desc)

        # Preset buttons row
        presets_row = QHBoxLayout()
        presets_row.setSpacing(12)

        self.preset_low = PresetButton(
            "Light",
            "Lower memory usage\nGood for older computers"
        )
        self.preset_low.clicked.connect(lambda: self._apply_preset('low'))
        presets_row.addWidget(self.preset_low)

        self.preset_balanced = PresetButton(
            "Balanced",
            "Recommended for most computers"
        )
        self.preset_balanced.clicked.connect(lambda: self._apply_preset('balanced'))
        presets_row.addWidget(self.preset_balanced)

        self.preset_high = PresetButton(
            "Performance",
            "Maximum speed\nUses more memory"
        )
        self.preset_high.clicked.connect(lambda: self._apply_preset('high'))
        presets_row.addWidget(self.preset_high)

        presets_card.add_layout(presets_row)
        content_layout.addWidget(presets_card)

        # ---------------------------------------------------------------------
        # Cache Settings Card
        # ---------------------------------------------------------------------
        cache_card = SettingsCard("Thumbnail Cache", "\U0001F5BC")  # Frame picture icon

        # Memory slider with labels
        memory_container = QWidget()
        memory_layout = QVBoxLayout(memory_container)
        memory_layout.setContentsMargins(0, 0, 0, 0)
        memory_layout.setSpacing(8)

        # Memory header row
        memory_header = QHBoxLayout()
        memory_label = QLabel("Memory Cache Size")
        memory_label.setObjectName("settingLabel")
        memory_header.addWidget(memory_label)
        memory_header.addStretch()

        self.memory_value_label = QLabel("500 MB")
        self.memory_value_label.setObjectName("settingValue")
        memory_header.addWidget(self.memory_value_label)

        memory_layout.addLayout(memory_header)

        # Memory slider
        self.memory_slider = QSlider(Qt.Horizontal)
        self.memory_slider.setObjectName("settingSlider")
        self.memory_slider.setRange(50, 2000)
        self.memory_slider.setValue(500)
        self.memory_slider.setTickPosition(QSlider.NoTicks)
        self.memory_slider.valueChanged.connect(self._on_memory_changed)
        memory_layout.addWidget(self.memory_slider)

        # Memory hint row
        memory_hint_row = QHBoxLayout()
        memory_min = QLabel("50 MB")
        memory_min.setObjectName("sliderHint")
        memory_hint_row.addWidget(memory_min)
        memory_hint_row.addStretch()

        self.memory_items_hint = QLabel("~3,333 thumbnails")
        self.memory_items_hint.setObjectName("sliderHint")
        memory_hint_row.addWidget(self.memory_items_hint)
        memory_hint_row.addStretch()

        memory_max = QLabel("2000 MB")
        memory_max.setObjectName("sliderHint")
        memory_hint_row.addWidget(memory_max)
        memory_layout.addLayout(memory_hint_row)

        cache_card.add_widget(memory_container)

        # Separator
        sep1 = QFrame()
        sep1.setObjectName("cardSeparator")
        sep1.setFrameShape(QFrame.HLine)
        cache_card.add_widget(sep1)

        # Worker threads
        threads_container = QWidget()
        threads_layout = QVBoxLayout(threads_container)
        threads_layout.setContentsMargins(0, 0, 0, 0)
        threads_layout.setSpacing(8)

        threads_header = QHBoxLayout()
        threads_label = QLabel("Processing Threads")
        threads_label.setObjectName("settingLabel")
        threads_header.addWidget(threads_label)
        threads_header.addStretch()

        self.threads_value_label = QLabel("8")
        self.threads_value_label.setObjectName("settingValue")
        threads_header.addWidget(self.threads_value_label)
        threads_layout.addLayout(threads_header)

        self.threads_slider = QSlider(Qt.Horizontal)
        self.threads_slider.setObjectName("settingSlider")
        self.threads_slider.setRange(1, 16)
        self.threads_slider.setValue(8)
        self.threads_slider.valueChanged.connect(self._on_threads_changed)
        threads_layout.addWidget(self.threads_slider)

        # Threads hint
        threads_hint_row = QHBoxLayout()
        threads_min = QLabel("1 thread")
        threads_min.setObjectName("sliderHint")
        threads_hint_row.addWidget(threads_min)
        threads_hint_row.addStretch()

        try:
            cpu_count = os.cpu_count() or 4
            cpu_hint = QLabel(f"Your CPU: {cpu_count} cores")
            cpu_hint.setObjectName("sliderHint")
            threads_hint_row.addWidget(cpu_hint)
            threads_hint_row.addStretch()
        except Exception:
            pass

        threads_max = QLabel("16 threads")
        threads_max.setObjectName("sliderHint")
        threads_hint_row.addWidget(threads_max)
        threads_layout.addLayout(threads_hint_row)

        cache_card.add_widget(threads_container)

        content_layout.addWidget(cache_card)

        # ---------------------------------------------------------------------
        # Cache Status Card
        # ---------------------------------------------------------------------
        status_card = SettingsCard("Cache Status", "\U0001F4CA")  # Chart icon

        # Memory usage bar
        mem_status = QWidget()
        mem_status_layout = QVBoxLayout(mem_status)
        mem_status_layout.setContentsMargins(0, 0, 0, 0)
        mem_status_layout.setSpacing(6)

        mem_header = QHBoxLayout()
        mem_label = QLabel("Memory Cache")
        mem_label.setObjectName("statusLabel")
        mem_header.addWidget(mem_label)
        mem_header.addStretch()

        self.mem_usage_label = QLabel("0 / 0 items")
        self.mem_usage_label.setObjectName("statusValue")
        mem_header.addWidget(self.mem_usage_label)
        mem_status_layout.addLayout(mem_header)

        self.mem_progress = QProgressBar()
        self.mem_progress.setObjectName("usageBar")
        self.mem_progress.setFixedHeight(8)
        self.mem_progress.setTextVisible(False)
        self.mem_progress.setRange(0, 100)
        self.mem_progress.setValue(0)
        mem_status_layout.addWidget(self.mem_progress)

        status_card.add_widget(mem_status)

        # Disk usage
        disk_status = QWidget()
        disk_status_layout = QVBoxLayout(disk_status)
        disk_status_layout.setContentsMargins(0, 0, 0, 0)
        disk_status_layout.setSpacing(6)

        disk_header = QHBoxLayout()
        disk_label = QLabel("Disk Cache")
        disk_label.setObjectName("statusLabel")
        disk_header.addWidget(disk_label)
        disk_header.addStretch()

        self.disk_usage_label = QLabel("-- items (-- MB)")
        self.disk_usage_label.setObjectName("statusValue")
        disk_header.addWidget(self.disk_usage_label)
        disk_status_layout.addLayout(disk_header)

        status_card.add_widget(disk_status)

        # Cache directory
        dir_row = QHBoxLayout()
        dir_row.setSpacing(8)

        dir_label = QLabel("Location:")
        dir_label.setObjectName("statusLabel")
        dir_row.addWidget(dir_label)

        self.cache_dir_label = QLabel("--")
        self.cache_dir_label.setObjectName("pathLabel")
        self.cache_dir_label.setWordWrap(True)
        dir_row.addWidget(self.cache_dir_label, 1)

        status_card.add_layout(dir_row)

        # Clear cache button
        clear_row = QHBoxLayout()
        clear_row.addStretch()

        self.clear_btn = QPushButton("\U0001F5D1  Clear Memory Cache")
        self.clear_btn.setObjectName("secondaryButton")
        self.clear_btn.clicked.connect(self._clear_cache)
        clear_row.addWidget(self.clear_btn)

        status_card.add_layout(clear_row)
        content_layout.addWidget(status_card)

        # Add stretch to push cards to top
        content_layout.addStretch()

        scroll.setWidget(content)
        main_layout.addWidget(scroll, 1)

        # ---------------------------------------------------------------------
        # Footer with action buttons
        # ---------------------------------------------------------------------
        footer = QWidget()
        footer.setObjectName("dialogFooter")
        footer.setFixedHeight(72)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(24, 16, 24, 16)
        footer_layout.setSpacing(12)

        # Settings changed indicator
        self.changes_label = QLabel("")
        self.changes_label.setObjectName("changesLabel")
        footer_layout.addWidget(self.changes_label)

        footer_layout.addStretch()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setObjectName("secondaryButton")
        self.cancel_btn.setMinimumWidth(100)
        self.cancel_btn.clicked.connect(self.reject)
        footer_layout.addWidget(self.cancel_btn)

        self.save_btn = QPushButton("Save Changes")
        self.save_btn.setObjectName("primaryButton")
        self.save_btn.setMinimumWidth(120)
        self.save_btn.clicked.connect(self._save_and_close)
        self.save_btn.setDefault(True)
        footer_layout.addWidget(self.save_btn)

        main_layout.addWidget(footer)

    def _apply_theme(self):
        """Apply modern theme styling."""
        if self._is_dark_mode:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1A1A1A;
                    color: #E0E0E0;
                }

                /* Header */
                QWidget#dialogHeader {
                    background-color: #262626;
                    border-bottom: 1px solid #333333;
                }
                QLabel#headerIcon {
                    font-size: 24px;
                    color: #888888;
                }
                QLabel#headerTitle {
                    font-size: 18px;
                    font-weight: 600;
                    color: #FFFFFF;
                }

                /* Scroll area */
                QScrollArea#settingsScroll {
                    background-color: #1A1A1A;
                }

                /* Cards */
                QFrame#settingsCard {
                    background-color: #262626;
                    border: 1px solid #333333;
                    border-radius: 12px;
                }
                QLabel#cardIcon {
                    font-size: 20px;
                }
                QLabel#cardTitle {
                    font-size: 15px;
                    font-weight: 600;
                    color: #FFFFFF;
                }
                QLabel#cardDescription {
                    font-size: 13px;
                    color: #888888;
                    line-height: 1.4;
                }
                QFrame#cardSeparator {
                    background-color: #333333;
                    border: none;
                    max-height: 1px;
                }

                /* Preset buttons */
                QPushButton#presetButton {
                    background-color: #333333;
                    border: 2px solid #404040;
                    border-radius: 10px;
                    padding: 12px 16px;
                    font-size: 14px;
                    font-weight: 600;
                    color: #E0E0E0;
                }
                QPushButton#presetButton:hover {
                    background-color: #404040;
                    border-color: #0066FF;
                }
                QPushButton#presetButton:checked {
                    background-color: #0066FF;
                    border-color: #0066FF;
                    color: #FFFFFF;
                }

                /* Setting controls */
                QLabel#settingLabel {
                    font-size: 14px;
                    font-weight: 500;
                    color: #E0E0E0;
                }
                QLabel#settingValue {
                    font-size: 14px;
                    font-weight: 600;
                    color: #0066FF;
                    min-width: 80px;
                    text-align: right;
                }
                QLabel#sliderHint {
                    font-size: 11px;
                    color: #666666;
                }

                /* Sliders */
                QSlider#settingSlider {
                    height: 24px;
                }
                QSlider#settingSlider::groove:horizontal {
                    background: #404040;
                    height: 6px;
                    border-radius: 3px;
                }
                QSlider#settingSlider::handle:horizontal {
                    background: #0066FF;
                    width: 18px;
                    height: 18px;
                    margin: -6px 0;
                    border-radius: 9px;
                }
                QSlider#settingSlider::handle:horizontal:hover {
                    background: #0052CC;
                }
                QSlider#settingSlider::sub-page:horizontal {
                    background: #0066FF;
                    border-radius: 3px;
                }

                /* Status section */
                QLabel#statusLabel {
                    font-size: 13px;
                    color: #888888;
                }
                QLabel#statusValue {
                    font-size: 13px;
                    font-weight: 500;
                    color: #E0E0E0;
                }
                QLabel#pathLabel {
                    font-size: 12px;
                    color: #666666;
                }

                /* Progress bar */
                QProgressBar#usageBar {
                    background-color: #404040;
                    border: none;
                    border-radius: 4px;
                }
                QProgressBar#usageBar::chunk {
                    background-color: #0066FF;
                    border-radius: 4px;
                }

                /* Footer */
                QWidget#dialogFooter {
                    background-color: #262626;
                    border-top: 1px solid #333333;
                }
                QLabel#changesLabel {
                    font-size: 12px;
                    color: #888888;
                    font-style: italic;
                }

                /* Buttons */
                QPushButton#primaryButton {
                    background-color: #0066FF;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    color: #FFFFFF;
                }
                QPushButton#primaryButton:hover {
                    background-color: #0052CC;
                }
                QPushButton#primaryButton:pressed {
                    background-color: #004299;
                }

                QPushButton#secondaryButton {
                    background-color: transparent;
                    border: 1px solid #444444;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                    color: #E0E0E0;
                }
                QPushButton#secondaryButton:hover {
                    background-color: #333333;
                    border-color: #666666;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #F5F5F5;
                    color: #171717;
                }

                /* Header */
                QWidget#dialogHeader {
                    background-color: #FFFFFF;
                    border-bottom: 1px solid #E5E5E5;
                }
                QLabel#headerIcon {
                    font-size: 24px;
                    color: #666666;
                }
                QLabel#headerTitle {
                    font-size: 18px;
                    font-weight: 600;
                    color: #171717;
                }

                /* Scroll area */
                QScrollArea#settingsScroll {
                    background-color: #F5F5F5;
                }

                /* Cards */
                QFrame#settingsCard {
                    background-color: #FFFFFF;
                    border: 1px solid #E5E5E5;
                    border-radius: 12px;
                }
                QLabel#cardIcon {
                    font-size: 20px;
                }
                QLabel#cardTitle {
                    font-size: 15px;
                    font-weight: 600;
                    color: #171717;
                }
                QLabel#cardDescription {
                    font-size: 13px;
                    color: #666666;
                    line-height: 1.4;
                }
                QFrame#cardSeparator {
                    background-color: #E5E5E5;
                    border: none;
                    max-height: 1px;
                }

                /* Preset buttons */
                QPushButton#presetButton {
                    background-color: #F5F5F5;
                    border: 2px solid #E5E5E5;
                    border-radius: 10px;
                    padding: 12px 16px;
                    font-size: 14px;
                    font-weight: 600;
                    color: #333333;
                }
                QPushButton#presetButton:hover {
                    background-color: #EBEBEB;
                    border-color: #0066FF;
                }
                QPushButton#presetButton:checked {
                    background-color: #0066FF;
                    border-color: #0066FF;
                    color: #FFFFFF;
                }

                /* Setting controls */
                QLabel#settingLabel {
                    font-size: 14px;
                    font-weight: 500;
                    color: #333333;
                }
                QLabel#settingValue {
                    font-size: 14px;
                    font-weight: 600;
                    color: #0066FF;
                    min-width: 80px;
                    text-align: right;
                }
                QLabel#sliderHint {
                    font-size: 11px;
                    color: #888888;
                }

                /* Sliders */
                QSlider#settingSlider {
                    height: 24px;
                }
                QSlider#settingSlider::groove:horizontal {
                    background: #E5E5E5;
                    height: 6px;
                    border-radius: 3px;
                }
                QSlider#settingSlider::handle:horizontal {
                    background: #0066FF;
                    width: 18px;
                    height: 18px;
                    margin: -6px 0;
                    border-radius: 9px;
                }
                QSlider#settingSlider::handle:horizontal:hover {
                    background: #0052CC;
                }
                QSlider#settingSlider::sub-page:horizontal {
                    background: #0066FF;
                    border-radius: 3px;
                }

                /* Status section */
                QLabel#statusLabel {
                    font-size: 13px;
                    color: #666666;
                }
                QLabel#statusValue {
                    font-size: 13px;
                    font-weight: 500;
                    color: #333333;
                }
                QLabel#pathLabel {
                    font-size: 12px;
                    color: #888888;
                }

                /* Progress bar */
                QProgressBar#usageBar {
                    background-color: #E5E5E5;
                    border: none;
                    border-radius: 4px;
                }
                QProgressBar#usageBar::chunk {
                    background-color: #0066FF;
                    border-radius: 4px;
                }

                /* Footer */
                QWidget#dialogFooter {
                    background-color: #FFFFFF;
                    border-top: 1px solid #E5E5E5;
                }
                QLabel#changesLabel {
                    font-size: 12px;
                    color: #888888;
                    font-style: italic;
                }

                /* Buttons */
                QPushButton#primaryButton {
                    background-color: #0066FF;
                    border: none;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    color: #FFFFFF;
                }
                QPushButton#primaryButton:hover {
                    background-color: #0052CC;
                }
                QPushButton#primaryButton:pressed {
                    background-color: #004299;
                }

                QPushButton#secondaryButton {
                    background-color: transparent;
                    border: 1px solid #E5E5E5;
                    border-radius: 8px;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 500;
                    color: #333333;
                }
                QPushButton#secondaryButton:hover {
                    background-color: #F5F5F5;
                    border-color: #CCCCCC;
                }
            """)

    def _load_current_settings(self):
        """Load current settings from database."""
        try:
            # Load cache memory setting
            memory_mb = self.db_metadata.get_cache_memory_mb()
            self.memory_slider.setValue(memory_mb)
            self._on_memory_changed(memory_mb)

            # Load worker threads setting
            threads = self.db_metadata.get_cache_worker_threads()
            self.threads_slider.setValue(threads)
            self._on_threads_changed(threads)

            # Update preset selection
            self._update_preset_selection(memory_mb, threads)

            # Update statistics
            self._update_statistics()

            logger.debug(f"Loaded settings: memory={memory_mb}MB, threads={threads}")

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _on_memory_changed(self, value: int):
        """Handle memory slider change."""
        self.memory_value_label.setText(f"{value} MB")
        estimated_items = int((value * 1024 * 1024) / (150 * 1024))
        self.memory_items_hint.setText(f"~{estimated_items:,} thumbnails")
        self._update_preset_selection(value, self.threads_slider.value())
        self._mark_changes()

    def _on_threads_changed(self, value: int):
        """Handle threads slider change."""
        self.threads_value_label.setText(str(value))
        self._update_preset_selection(self.memory_slider.value(), value)
        self._mark_changes()

    def _apply_preset(self, preset: str):
        """Apply a performance preset."""
        presets = {
            'low': {'memory': 200, 'threads': 2},
            'balanced': {'memory': 500, 'threads': 4},
            'high': {'memory': 1000, 'threads': 8}
        }

        if preset in presets:
            config = presets[preset]
            self.memory_slider.setValue(config['memory'])
            self.threads_slider.setValue(config['threads'])

    def _update_preset_selection(self, memory: int, threads: int):
        """Update which preset button appears selected."""
        # Clear all
        self.preset_low.setChecked(False)
        self.preset_balanced.setChecked(False)
        self.preset_high.setChecked(False)

        # Check if current values match a preset
        if memory <= 250 and threads <= 3:
            self.preset_low.setChecked(True)
        elif 400 <= memory <= 600 and 3 <= threads <= 6:
            self.preset_balanced.setChecked(True)
        elif memory >= 800 and threads >= 6:
            self.preset_high.setChecked(True)

    def _mark_changes(self):
        """Mark that settings have been changed."""
        self.changes_label.setText("You have unsaved changes")

    def _update_statistics(self):
        """Update cache statistics display."""
        if self.thumbnail_cache:
            try:
                stats = self.thumbnail_cache.get_stats()

                # Memory cache stats
                memory_count = stats.get('memory_size', 0)
                memory_max = getattr(self.thumbnail_cache, 'memory_size', 1)
                self.mem_usage_label.setText(f"{memory_count:,} / {memory_max:,} items")

                # Update progress bar
                if memory_max > 0:
                    percent = int((memory_count / memory_max) * 100)
                    self.mem_progress.setValue(percent)
                else:
                    self.mem_progress.setValue(0)

                # Disk cache stats
                try:
                    disk_info = self.thumbnail_cache.triage_db.get_cache_size_info()
                    disk_count = disk_info.get('count', 0)
                    disk_size_mb = disk_info.get('size_mb', 0)
                    self.disk_usage_label.setText(f"{disk_count:,} items ({disk_size_mb:.1f} MB)")
                except Exception:
                    self.disk_usage_label.setText(f"Hits: {stats.get('disk_hits', 0):,}")

                # Cache directory
                cache_dir = getattr(self.thumbnail_cache, 'cache_dir', 'Unknown')
                self.cache_dir_label.setText(str(cache_dir))

            except Exception as e:
                logger.error(f"Failed to get cache stats: {e}")
                self.mem_usage_label.setText("Error")
                self.mem_progress.setValue(0)
        else:
            self.mem_usage_label.setText("Not initialized")
            self.mem_progress.setValue(0)
            self.disk_usage_label.setText("Not initialized")
            self.cache_dir_label.setText("--")

    def _clear_cache(self):
        """Clear the thumbnail cache."""
        reply = QMessageBox.question(
            self,
            "Clear Memory Cache",
            "This will clear all thumbnails from memory.\n"
            "They will be reloaded from disk as needed.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.thumbnail_cache:
                try:
                    self.thumbnail_cache.clear_memory_cache()
                    self._update_statistics()
                    QMessageBox.information(
                        self,
                        "Cache Cleared",
                        "Memory cache has been cleared successfully."
                    )
                except Exception as e:
                    logger.error(f"Failed to clear cache: {e}")
                    QMessageBox.warning(self, "Error", f"Failed to clear cache: {e}")
            else:
                QMessageBox.information(
                    self,
                    "Cache Not Available",
                    "Thumbnail cache is not initialized."
                )

    def _save_and_close(self):
        """Save settings and close dialog."""
        if self._apply_settings():
            self.accept()

    def _apply_settings(self) -> bool:
        """Apply settings to database."""
        try:
            memory_mb = self.memory_slider.value()
            threads = self.threads_slider.value()

            self.db_metadata.set_cache_memory_mb(memory_mb)
            self.db_metadata.set_cache_worker_threads(threads)

            logger.info(f"Saved settings: memory={memory_mb}MB, threads={threads}")

            self.settings_changed.emit()
            self.changes_label.setText("")

            return True

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.warning(self, "Error", f"Failed to save settings: {e}")
            return False

    def set_thumbnail_cache(self, cache):
        """Set or update the thumbnail cache reference."""
        self.thumbnail_cache = cache
        self._update_statistics()
