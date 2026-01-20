"""
Main Window for PyPhotoOrganizer GUI

Implements the main application window with tab-based interface.
"""

from PySide6.QtWidgets import (QMainWindow, QTabWidget, QMessageBox,
                               QApplication, QStatusBar)
from PySide6.QtCore import Qt, QSettings, QRect, QPoint, QTimer
from PySide6.QtGui import QAction, QScreen
import sys
from datetime import datetime

from ui.import_settings_tab import ImportSettingsTab
from ui.archive_settings_tab import ArchiveSettingsTab
from ui.system_settings_tab import SystemSettingsTab
from ui.progress_tab import ProgressTab
from ui.logs_tab import LogsTab
from ui.import_history_tab import ImportHistoryTab
from ui.database_selector_dialog import DatabaseSelectorDialog
from ui.worker import ProcessingWorker
from database_metadata import DatabaseMetadata


class MainWindow(QMainWindow):
    """Main application window with tab-based interface."""

    def __init__(self, splash_callback=None):
        super().__init__()
        self.worker = None
        self.current_database_path = None
        self.database_metadata = None
        self.settings = QSettings("PyPhotoOrganizer", "MainWindow")
        self.splash_callback = splash_callback

        if self.splash_callback:
            self.splash_callback("Creating tabs...")

        self.init_ui()

        if self.splash_callback:
            self.splash_callback("Restoring window position...")

        # Restore window geometry or center on screen
        self.restore_window_geometry()

        if self.splash_callback:
            self.splash_callback("Loading settings...")

        # Show database selector - deferred until after splash closes
        # Use QTimer to show it after the splash screen finishes
        QTimer.singleShot(100, self.select_database_on_startup)

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("PyPhotoOrganizer")
        # Set default size (will be overridden by restore_window_geometry if saved position exists)
        self.resize(1200, 800)

        # Create menu bar
        self._create_menu_bar()

        # Create status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create tabs
        self.import_settings_tab = ImportSettingsTab()
        self.archive_settings_tab = ArchiveSettingsTab()
        self.system_settings_tab = SystemSettingsTab()
        self.progress_tab = ProgressTab()
        self.logs_tab = LogsTab()
        self.import_history_tab = ImportHistoryTab()

        # Add tabs in workflow order
        # Tab 0: Import Settings (source folders, filtering, Start/Stop buttons)
        self.tabs.addTab(self.import_settings_tab, "📥 Import Settings")
        self.tabs.setTabToolTip(0, "Choose source folders, configure filtering, and start/stop processing")

        # Tab 1: Archive Settings (organization, file type, renaming)
        self.tabs.addTab(self.archive_settings_tab, "📦 Archive Settings")
        self.tabs.setTabToolTip(1, "Configure archive location, organization templates, and file renaming")

        # Tab 2: System Settings (database, operation mode, performance)
        self.tabs.addTab(self.system_settings_tab, "⚙️ System Settings")
        self.tabs.setTabToolTip(2, "Database information, operation mode, performance, and retention settings")

        # Tab 3: Progress (active during processing)
        self.tabs.addTab(self.progress_tab, "▶️ Progress")
        self.tabs.setTabToolTip(3, "View real-time processing status and statistics")

        # Tab 4: Import History (complete accounting of imports)
        self.tabs.addTab(self.import_history_tab, "📜 Import History")
        self.tabs.setTabToolTip(4, "Review past import sessions - new files, duplicates, filtered, and errors")

        # Tab 5: Logs (troubleshooting)
        self.tabs.addTab(self.logs_tab, "📋 Logs")
        self.tabs.setTabToolTip(5, "View detailed application logs for troubleshooting")

        # Connect signals
        self.import_settings_tab.start_clicked.connect(self.start_processing)
        self.import_settings_tab.stop_clicked.connect(self.stop_processing)

    def _create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(self, "About PyPhotoOrganizer",
                         "PyPhotoOrganizer v2.0\n\n"
                         "A tool for organizing and deduplicating photos.\n\n"
                         "Built with PySide6")

    def start_processing(self):
        """Start the photo processing."""
        try:
            # Ensure we have a database
            if not self.current_database_path:
                QMessageBox.warning(self, "Error", "No database selected")
                return

            # Get configuration from import settings tab
            config = self.import_settings_tab.get_config()

            # Get folder selections from import settings tab (only enabled ones)
            source_folders = self.import_settings_tab.get_enabled_source_folders()

            # Debug logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Enabled source folders from import settings tab: {source_folders}")

            # Get destination from database
            destination_folder = self.database_metadata.get_archive_location()
            logger.info(f"Destination folder from database: {destination_folder}")

            if not source_folders:
                QMessageBox.warning(self, "Error",
                                  "Please select at least one source folder.\n\n"
                                  "Go to Import Settings tab and add your source folders.\n"
                                  "Make sure the checkbox next to the source folder is checked!")
                return

            if not destination_folder:
                QMessageBox.warning(self, "Error",
                                  "No archive location configured for this database.\n\n"
                                  "This should not happen. Please check the System Settings tab.")
                return

            config['source_directory'] = source_folders
            config['destination_directory'] = destination_folder

            logger.info(f"=" * 80)
            logger.info(f"MAIN_WINDOW: Setting config database_path")
            logger.info(f"  self.current_database_path = '{self.current_database_path}'")
            config['database_path'] = self.current_database_path
            logger.info(f"  config['database_path'] = '{config['database_path']}'")
            logger.info(f"=" * 80)

            config['copy_files'] = self.system_settings_tab.is_copy_mode()
            config['move_files'] = self.system_settings_tab.is_move_mode()

            # Get ignored directories from database
            ignored_dirs = self.database_metadata.get_ignored_directories()
            config['ignored_directories'] = ignored_dirs
            logger.info(f"Ignored directories: {ignored_dirs}")

            # Add system performance settings
            perf_config = self.system_settings_tab.get_config()
            config.update(perf_config)

            # Save organization settings to database before processing
            if not self.archive_settings_tab.save_organization_to_database():
                return  # Error dialog already shown

            # Add organization template from database to config
            config['organization_template'] = self.database_metadata.get_organization_template()
            logger.info(f"Organization template from database: {config['organization_template']}")

            # Validate operation mode
            if not config['copy_files'] and not config['move_files']:
                QMessageBox.warning(self, "Error", "Please select Copy or Move mode in System Settings tab")
                return

            # Show warning for move mode
            if config['move_files']:
                response = QMessageBox.warning(self, "Warning: Move Mode",
                                              "Move mode will DELETE files from source folders!\n\n"
                                              "Are you sure you want to continue?",
                                              QMessageBox.Yes | QMessageBox.No,
                                              QMessageBox.No)
                if response == QMessageBox.No:
                    return

            # Create and start worker
            self.worker = ProcessingWorker(config)

            # Connect signals
            self.worker.scanning_progress.connect(self.progress_tab.update_scanning_progress)
            self.worker.processing_progress.connect(self.progress_tab.update_processing_progress)
            self.worker.organizing_progress.connect(self.progress_tab.update_organizing_progress)
            self.worker.stage_changed.connect(self.progress_tab.update_stage)
            self.worker.completed.connect(self.processing_completed)
            self.worker.error_occurred.connect(self.processing_error)
            self.worker.status_update.connect(self.progress_tab.add_status_message)

            # Switch to progress tab and start
            self.tabs.setCurrentWidget(self.progress_tab)
            self.progress_tab.reset()
            self.worker.start()

            # Update UI state
            self.import_settings_tab.set_controls_enabled(False)
            self.status_bar.showMessage("Processing...")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start processing:\n\n{str(e)}")

    def stop_processing(self):
        """Stop the photo processing."""
        if self.worker and self.worker.isRunning():
            response = QMessageBox.question(self, "Stop Processing",
                                           "Are you sure you want to stop processing?\n\n"
                                           "What will happen:\n"
                                           "• Current file processing will complete\n"
                                           "• All progress will be saved to the database\n"
                                           "• You can resume later (already-processed files will be skipped)\n\n"
                                           "Stop now?",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.No)
            if response == QMessageBox.Yes:
                self.worker.stop()
                self.status_bar.showMessage("Stopping... saving progress (please wait)")

    def processing_completed(self, results):
        """Handle processing completion."""
        # Re-enable controls
        self.import_settings_tab.set_controls_enabled(True)

        # Check if processing was cancelled
        was_cancelled = results.get('was_cancelled', False)

        if was_cancelled:
            self.status_bar.showMessage("Processing stopped - partial progress saved")
        else:
            self.status_bar.showMessage("Processing complete")

        # Refresh database photo count from UniquePhotos table
        if self.database_metadata:
            self.database_metadata.refresh_total_photos()
            # Refresh the system settings tab display to show updated count
            self.system_settings_tab.set_database(self.database_metadata)

            # Update last_scanned timestamp for all processed source directories
            # (even if cancelled, we've partially processed them)
            source_folders = self.import_settings_tab.get_enabled_source_folders()
            current_time = datetime.now().isoformat()
            for folder in source_folders:
                self.database_metadata.update_source_last_scanned(folder, current_time)

            # Refresh the import settings tab to show updated last_scanned times
            self.import_settings_tab.load_sources_from_database()

        # Switch to Import History tab to show results
        self.tabs.setCurrentWidget(self.import_history_tab)

        # Show completion message with summary
        total_examined = results.get('total_files_examined', 0)
        originals = results.get('total_new_original_files', 0)
        duplicates = results.get('total_duplicates', 0)
        filtered = results.get('total_filtered', 0)
        unreliable_dates = results.get('total_unreliable_dates', 0)

        if was_cancelled:
            # Show cancelled message with partial progress
            QMessageBox.information(self, "Processing Stopped",
                                  f"Processing was stopped by user.\n\n"
                                  f"Partial progress has been saved:\n\n"
                                  f"Files processed before stop: {total_examined}\n"
                                  f"New original photos saved: {originals}\n"
                                  f"Duplicates found: {duplicates}\n"
                                  f"Filtered files: {filtered}\n\n"
                                  f"You can resume processing at any time.\n"
                                  f"Files already in the database will be skipped.\n\n"
                                  f"View the Import History tab for details.")
        else:
            # Show normal completion message
            QMessageBox.information(self, "Processing Complete",
                                  f"Processing complete!\n\n"
                                  f"Total files examined: {total_examined}\n"
                                  f"New original photos: {originals}\n"
                                  f"Duplicates found: {duplicates}\n"
                                  f"Filtered files: {filtered}\n"
                                  f"Files with suspicious dates: {unreliable_dates}\n\n"
                                  f"View the Import History tab for full details.")

    def processing_error(self, error_msg):
        """Handle processing error."""
        # Re-enable controls
        self.import_settings_tab.set_controls_enabled(True)
        self.status_bar.showMessage("Error occurred")

        # Show error message
        QMessageBox.critical(self, "Processing Error",
                           f"An error occurred during processing:\n\n{error_msg}")

    def select_database_on_startup(self):
        """Show database selector on startup - user must select database."""
        dialog = DatabaseSelectorDialog(self)
        result = dialog.exec()

        if result:
            # User selected a database
            database_path = dialog.get_selected_database()
            if database_path:
                self.set_database(database_path)
        else:
            # User cancelled - cannot proceed without database
            QMessageBox.warning(
                self,
                "Database Required",
                "PyPhotoOrganizer requires a database to operate.\n\n"
                "You must either:\n"
                "• Select an existing database\n"
                "• Create a new database\n\n"
                "The application will now close."
            )
            QApplication.quit()

    def set_database(self, database_path):
        """
        Set the current database and update all tabs.

        Args:
            database_path: Path to the database file
        """
        self.current_database_path = database_path
        self.database_metadata = DatabaseMetadata(database_path)

        # Ensure all required tables exist (handles old databases)
        self.database_metadata.ensure_all_tables()

        # Update import settings tab with database (loads source directories)
        self.import_settings_tab.set_database(self.database_metadata)

        # Update archive settings tab with database (loads organization template, file renaming)
        self.archive_settings_tab.set_database(self.database_metadata)

        # Update system settings tab with database (loads database info, cache settings, retention)
        self.system_settings_tab.set_database(self.database_metadata)

        # Update import history tab with database
        self.import_history_tab.set_database(database_path)

        # Update window title
        metadata = self.database_metadata.get_metadata()
        if metadata:
            db_name = metadata.get('database_name', 'Unknown')
            self.setWindowTitle(f"PyPhotoOrganizer - {db_name}")

        # Update status bar
        self.status_bar.showMessage(f"Database loaded: {db_name}")

    def restore_window_geometry(self):
        """
        Restore window geometry from saved settings.
        If no saved geometry exists, center the window on screen.
        Ensures window title bar is always accessible.
        """
        # Try to restore saved geometry
        geometry = self.settings.value("geometry")

        if geometry:
            # Restore saved geometry
            self.restoreGeometry(geometry)

            # Ensure window is within screen bounds
            self.ensure_window_on_screen()
        else:
            # No saved geometry - center window on screen
            self.center_on_screen()

    def center_on_screen(self):
        """Center the window on the primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            window_geometry = self.frameGeometry()

            # Calculate center point
            center_point = screen_geometry.center()
            window_geometry.moveCenter(center_point)

            # Move window to centered position
            self.move(window_geometry.topLeft())

    def ensure_window_on_screen(self):
        """
        Ensure the window's title bar is accessible and on screen.
        Adjusts position if window is off-screen.
        """
        screen = QApplication.primaryScreen()
        if not screen:
            return

        screen_geometry = screen.availableGeometry()
        window_geometry = self.frameGeometry()

        # Minimum visible title bar height (50 pixels)
        min_title_bar_visible = 50

        # Adjust horizontal position
        if window_geometry.left() < screen_geometry.left():
            # Window is too far left
            self.move(screen_geometry.left(), window_geometry.top())
            window_geometry = self.frameGeometry()
        elif window_geometry.right() > screen_geometry.right():
            # Window is too far right
            self.move(screen_geometry.right() - window_geometry.width(), window_geometry.top())
            window_geometry = self.frameGeometry()

        # Adjust vertical position - ensure title bar is visible
        if window_geometry.top() < screen_geometry.top():
            # Window is too far up - title bar not accessible
            self.move(window_geometry.left(), screen_geometry.top())
        elif window_geometry.top() > screen_geometry.bottom() - min_title_bar_visible:
            # Window is too far down - move it up
            self.move(window_geometry.left(), screen_geometry.bottom() - min_title_bar_visible)

    def save_window_geometry(self):
        """Save current window geometry to settings."""
        self.settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event):
        """Handle window close event."""
        if self.worker and self.worker.isRunning():
            response = QMessageBox.question(self, "Quit",
                                           "Processing is still running. Quit anyway?\n\n"
                                           "What will happen:\n"
                                           "• Current file processing will complete\n"
                                           "• All progress will be saved to the database\n"
                                           "• You can resume later from where you left off\n\n"
                                           "Quit now?",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.No)
            if response == QMessageBox.Yes:
                self.status_bar.showMessage("Stopping and saving progress...")
                self.worker.stop()
                self.worker.wait()  # Wait for thread to finish
                self.save_window_geometry()  # Save position before closing
                event.accept()
            else:
                event.ignore()
        else:
            self.save_window_geometry()  # Save position before closing
            event.accept()
