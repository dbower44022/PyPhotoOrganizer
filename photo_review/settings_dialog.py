"""
Photo Review Settings Dialog

Settings dialog for the Photo Review application, providing cache configuration
and other application preferences.
"""

import logging
import os
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QFormLayout, QMessageBox, QFrame,
    QSizePolicy
)
from PySide6.QtCore import Qt, Signal

logger = logging.getLogger(__name__)


class PhotoReviewSettingsDialog(QDialog):
    """
    Settings dialog for Photo Review application.

    Provides UI for configuring:
    - Thumbnail cache memory size
    - Thumbnail generation worker threads
    - Cache statistics and management

    Signals:
        settings_changed: Emitted when settings are applied and cache needs reinitialization
    """

    settings_changed = Signal()

    def __init__(self, db_metadata, thumbnail_cache=None, is_dark_mode: bool = True, parent=None):
        """
        Initialize the settings dialog.

        Args:
            db_metadata: DatabaseMetadata instance for reading/writing settings
            thumbnail_cache: Optional ThumbnailCache instance for statistics
            is_dark_mode: Whether dark mode is active
            parent: Parent widget
        """
        super().__init__(parent)
        self.db_metadata = db_metadata
        self.thumbnail_cache = thumbnail_cache
        self._is_dark_mode = is_dark_mode

        self.setWindowTitle("Photo Review Settings")
        self.setMinimumWidth(450)
        self.setMinimumHeight(350)

        self._init_ui()
        self._load_current_settings()
        self._apply_theme()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(20, 20, 20, 20)

        # ---------------------------------------------------------------------
        # Thumbnail Cache Settings Group
        # ---------------------------------------------------------------------
        cache_group = QGroupBox("Thumbnail Cache Settings")
        cache_layout = QVBoxLayout(cache_group)
        cache_layout.setSpacing(12)

        # Memory cache size
        memory_layout = QHBoxLayout()
        memory_layout.setSpacing(8)

        memory_label = QLabel("Memory Cache Size:")
        memory_label.setMinimumWidth(140)
        memory_label.setMinimumHeight(28)
        memory_layout.addWidget(memory_label)

        self.memory_spinbox = QSpinBox()
        self.memory_spinbox.setRange(50, 2000)
        self.memory_spinbox.setSuffix(" MB")
        self.memory_spinbox.setValue(500)
        self.memory_spinbox.setMinimumWidth(120)
        self.memory_spinbox.setMinimumHeight(32)
        self.memory_spinbox.valueChanged.connect(self._update_memory_hint)
        memory_layout.addWidget(self.memory_spinbox)

        self.memory_hint_label = QLabel("(~3,333 thumbnails)")
        self.memory_hint_label.setMinimumHeight(28)
        self.memory_hint_label.setObjectName("hintLabel")
        memory_layout.addWidget(self.memory_hint_label)
        memory_layout.addStretch()

        cache_layout.addLayout(memory_layout)

        # Worker threads
        threads_layout = QHBoxLayout()
        threads_layout.setSpacing(8)

        threads_label = QLabel("Worker Threads:")
        threads_label.setMinimumWidth(140)
        threads_label.setMinimumHeight(28)
        threads_layout.addWidget(threads_label)

        self.threads_spinbox = QSpinBox()
        self.threads_spinbox.setRange(1, 16)
        self.threads_spinbox.setValue(8)
        self.threads_spinbox.setMinimumWidth(120)
        self.threads_spinbox.setMinimumHeight(32)
        threads_layout.addWidget(self.threads_spinbox)

        # Show CPU core count as hint
        try:
            cpu_count = os.cpu_count() or 4
            threads_hint = QLabel(f"(CPU has {cpu_count} cores)")
            threads_hint.setMinimumHeight(28)
            threads_hint.setObjectName("hintLabel")
            threads_layout.addWidget(threads_hint)
        except Exception:
            pass
        threads_layout.addStretch()

        cache_layout.addLayout(threads_layout)

        # Help text
        help_text = QLabel(
            "Higher memory cache keeps more thumbnails in RAM for faster access.\n"
            "More worker threads can speed up thumbnail generation on multi-core CPUs."
        )
        help_text.setObjectName("hintLabel")
        help_text.setWordWrap(True)
        help_text.setMinimumHeight(40)
        cache_layout.addWidget(help_text)

        layout.addWidget(cache_group)

        # ---------------------------------------------------------------------
        # Cache Statistics Group
        # ---------------------------------------------------------------------
        stats_group = QGroupBox("Cache Statistics")
        stats_layout = QFormLayout(stats_group)
        stats_layout.setSpacing(12)
        stats_layout.setContentsMargins(10, 10, 10, 10)

        self.stats_memory_label = QLabel("--")
        self.stats_memory_label.setMinimumHeight(24)
        stats_layout.addRow("In-Memory Cache:", self.stats_memory_label)

        self.stats_disk_label = QLabel("--")
        self.stats_disk_label.setMinimumHeight(24)
        stats_layout.addRow("Disk Cache:", self.stats_disk_label)

        self.stats_dir_label = QLabel("--")
        self.stats_dir_label.setWordWrap(True)
        self.stats_dir_label.setMinimumHeight(24)
        stats_layout.addRow("Cache Directory:", self.stats_dir_label)

        # Clear cache button
        clear_layout = QHBoxLayout()
        self.clear_cache_btn = QPushButton("Clear Thumbnail Cache")
        self.clear_cache_btn.clicked.connect(self._clear_cache)
        self.clear_cache_btn.setMaximumWidth(180)
        clear_layout.addWidget(self.clear_cache_btn)
        clear_layout.addStretch()
        stats_layout.addRow("", clear_layout)

        layout.addWidget(stats_group)

        # ---------------------------------------------------------------------
        # Spacer
        # ---------------------------------------------------------------------
        layout.addStretch()

        # ---------------------------------------------------------------------
        # Separator
        # ---------------------------------------------------------------------
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        layout.addWidget(separator)

        # ---------------------------------------------------------------------
        # Dialog Buttons
        # ---------------------------------------------------------------------
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)

        button_layout.addStretch()

        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_settings)
        self.apply_btn.setMinimumWidth(80)
        button_layout.addWidget(self.apply_btn)

        self.ok_btn = QPushButton("OK")
        self.ok_btn.clicked.connect(self._ok_clicked)
        self.ok_btn.setMinimumWidth(80)
        self.ok_btn.setDefault(True)
        button_layout.addWidget(self.ok_btn)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        self.cancel_btn.setMinimumWidth(80)
        button_layout.addWidget(self.cancel_btn)

        layout.addLayout(button_layout)

    def _apply_theme(self):
        """Apply theme-aware styling."""
        if self._is_dark_mode:
            self.setStyleSheet("""
                QDialog {
                    background-color: #1E1E1E;
                    color: #E0E0E0;
                    font-size: 13px;
                }
                QGroupBox {
                    background-color: #2A2A2A;
                    border: 1px solid #444444;
                    border-radius: 8px;
                    margin-top: 16px;
                    padding: 20px;
                    padding-top: 28px;
                    font-weight: 600;
                    font-size: 13px;
                    color: #FAFAFA;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 8px;
                    color: #FAFAFA;
                }
                QLabel {
                    color: #E0E0E0;
                    font-size: 13px;
                    min-height: 20px;
                }
                QLabel#hintLabel {
                    color: #888888;
                    font-size: 12px;
                }
                QSpinBox {
                    background-color: #333333;
                    border: 1px solid #444444;
                    border-radius: 4px;
                    padding: 6px 10px;
                    color: #FFFFFF;
                    font-size: 13px;
                    min-height: 28px;
                }
                QSpinBox:focus {
                    border-color: #0066FF;
                }
                QPushButton {
                    background-color: #333333;
                    border: 1px solid #444444;
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: #FFFFFF;
                    font-weight: 500;
                    font-size: 13px;
                    min-height: 32px;
                }
                QPushButton:hover {
                    background-color: #404040;
                    border-color: #0066FF;
                }
                QPushButton:pressed {
                    background-color: #0066FF;
                }
                QPushButton:default {
                    background-color: #0066FF;
                    border-color: #0066FF;
                }
                QPushButton:default:hover {
                    background-color: #0052CC;
                }
                QFrame[frameShape="4"] {
                    color: #444444;
                }
            """)
        else:
            self.setStyleSheet("""
                QDialog {
                    background-color: #FFFFFF;
                    color: #171717;
                    font-size: 13px;
                }
                QGroupBox {
                    background-color: #F5F5F5;
                    border: 1px solid #E0E0E0;
                    border-radius: 8px;
                    margin-top: 16px;
                    padding: 20px;
                    padding-top: 28px;
                    font-weight: 600;
                    font-size: 13px;
                    color: #171717;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    subcontrol-position: top left;
                    padding: 0 8px;
                    color: #171717;
                }
                QLabel {
                    color: #171717;
                    font-size: 13px;
                    min-height: 20px;
                }
                QLabel#hintLabel {
                    color: #666666;
                    font-size: 12px;
                }
                QSpinBox {
                    background-color: #FFFFFF;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    padding: 6px 10px;
                    color: #171717;
                    font-size: 13px;
                    min-height: 28px;
                }
                QSpinBox:focus {
                    border-color: #0066FF;
                }
                QPushButton {
                    background-color: #F5F5F5;
                    border: 1px solid #E0E0E0;
                    border-radius: 6px;
                    padding: 8px 16px;
                    color: #171717;
                    font-weight: 500;
                    font-size: 13px;
                    min-height: 32px;
                }
                QPushButton:hover {
                    background-color: #E5E5E5;
                    border-color: #0066FF;
                }
                QPushButton:pressed {
                    background-color: #0066FF;
                    color: #FFFFFF;
                }
                QPushButton:default {
                    background-color: #0066FF;
                    border-color: #0066FF;
                    color: #FFFFFF;
                }
                QPushButton:default:hover {
                    background-color: #0052CC;
                }
                QFrame[frameShape="4"] {
                    color: #E0E0E0;
                }
            """)

    def _load_current_settings(self):
        """Load current settings from database."""
        try:
            # Load cache memory setting
            memory_mb = self.db_metadata.get_cache_memory_mb()
            self.memory_spinbox.setValue(memory_mb)

            # Load worker threads setting
            threads = self.db_metadata.get_cache_worker_threads()
            self.threads_spinbox.setValue(threads)

            # Update hints
            self._update_memory_hint(memory_mb)

            # Update statistics
            self._update_statistics()

            logger.debug(f"Loaded settings: memory={memory_mb}MB, threads={threads}")

        except Exception as e:
            logger.error(f"Failed to load settings: {e}")

    def _update_memory_hint(self, memory_mb: int):
        """Update the thumbnail count hint based on memory size."""
        # Estimate ~150KB per thumbnail
        estimated_items = int((memory_mb * 1024 * 1024) / (150 * 1024))
        self.memory_hint_label.setText(f"(~{estimated_items:,} thumbnails)")

    def _update_statistics(self):
        """Update cache statistics display."""
        if self.thumbnail_cache:
            try:
                stats = self.thumbnail_cache.get_stats()

                # Memory cache stats
                memory_count = stats.get('memory_size', 0)
                memory_max = getattr(self.thumbnail_cache, 'memory_size', 0)
                self.stats_memory_label.setText(f"{memory_count:,} / {memory_max:,} items")

                # Disk cache stats - get from triage database
                try:
                    disk_info = self.thumbnail_cache.triage_db.get_cache_size_info()
                    disk_count = disk_info.get('count', 0)
                    disk_size_mb = disk_info.get('size_mb', 0)
                    self.stats_disk_label.setText(f"{disk_count:,} items ({disk_size_mb:.1f} MB)")
                except Exception:
                    self.stats_disk_label.setText(f"Hits: {stats.get('disk_hits', 0):,}")

                # Cache directory
                cache_dir = getattr(self.thumbnail_cache, 'cache_dir', 'Unknown')
                self.stats_dir_label.setText(str(cache_dir))

            except Exception as e:
                logger.error(f"Failed to get cache stats: {e}")
                self.stats_memory_label.setText("Error loading stats")
                self.stats_disk_label.setText("Error loading stats")
        else:
            self.stats_memory_label.setText("Cache not initialized")
            self.stats_disk_label.setText("Cache not initialized")
            self.stats_dir_label.setText("--")

    def _clear_cache(self):
        """Clear the thumbnail cache."""
        reply = QMessageBox.question(
            self,
            "Clear Cache",
            "This will clear thumbnails from memory.\n"
            "Thumbnails will be regenerated as needed.\n\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.thumbnail_cache:
                try:
                    # Clear memory cache
                    self.thumbnail_cache.clear_memory_cache()
                    self._update_statistics()
                    QMessageBox.information(
                        self,
                        "Cache Cleared",
                        "Memory cache has been cleared.\n"
                        "Thumbnails will be reloaded from disk cache as needed."
                    )
                except Exception as e:
                    logger.error(f"Failed to clear cache: {e}")
                    QMessageBox.warning(
                        self,
                        "Error",
                        f"Failed to clear cache: {e}"
                    )
            else:
                QMessageBox.information(
                    self,
                    "Cache Not Available",
                    "Thumbnail cache is not initialized."
                )

    def _apply_settings(self) -> bool:
        """
        Apply settings to database.

        Returns:
            True if settings were saved successfully
        """
        try:
            memory_mb = self.memory_spinbox.value()
            threads = self.threads_spinbox.value()

            # Save to database
            self.db_metadata.set_cache_memory_mb(memory_mb)
            self.db_metadata.set_cache_worker_threads(threads)

            logger.info(f"Saved cache settings: memory={memory_mb}MB, threads={threads}")

            # Emit signal so main window can reinitialize cache
            self.settings_changed.emit()

            return True

        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to save settings: {e}"
            )
            return False

    def _ok_clicked(self):
        """Handle OK button click."""
        if self._apply_settings():
            self.accept()

    def set_thumbnail_cache(self, cache):
        """
        Set or update the thumbnail cache reference.

        Args:
            cache: ThumbnailCache instance
        """
        self.thumbnail_cache = cache
        self._update_statistics()
