"""
Main Window for PyPhotoOrganizer GUI

Implements the main application window with tab-based interface.
"""

from PySide6.QtWidgets import (QMainWindow, QTabWidget, QMessageBox,
                               QApplication, QStatusBar)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
import sys

from ui.setup_tab import SetupTab
from ui.progress_tab import ProgressTab
from ui.results_tab import ResultsTab
from ui.logs_tab import LogsTab
from ui.settings_tab import SettingsTab
from ui.database_tab import DatabaseTab
from ui.database_selector_dialog import DatabaseSelectorDialog
from ui.worker import ProcessingWorker
from database_metadata import DatabaseMetadata


class MainWindow(QMainWindow):
    """Main application window with tab-based interface."""

    def __init__(self):
        super().__init__()
        self.worker = None
        self.current_database_path = None
        self.database_metadata = None
        self.init_ui()

        # Show database selector - user must select database before proceeding
        self.select_database_on_startup()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("PyPhotoOrganizer")
        self.setGeometry(100, 100, 1200, 800)

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
        self.setup_tab = SetupTab()
        self.progress_tab = ProgressTab()
        self.results_tab = ResultsTab()
        self.logs_tab = LogsTab()
        self.settings_tab = SettingsTab()
        self.database_tab = DatabaseTab()

        # Add tabs
        self.tabs.addTab(self.setup_tab, "Setup")
        self.tabs.addTab(self.progress_tab, "Progress")
        self.tabs.addTab(self.results_tab, "Results")
        self.tabs.addTab(self.logs_tab, "Logs")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.tabs.addTab(self.database_tab, "Database")

        # Connect signals
        self.setup_tab.start_clicked.connect(self.start_processing)
        self.setup_tab.stop_clicked.connect(self.stop_processing)
        self.database_tab.database_changed.connect(self.on_database_changed)

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

            # Get configuration from settings tab
            config = self.settings_tab.get_config()

            # Update config with folder selections from setup tab
            source_folders = self.setup_tab.get_source_folders()

            # Get destination from database
            destination_folder = self.database_metadata.get_archive_location()

            if not source_folders:
                QMessageBox.warning(self, "Error", "Please select at least one source folder")
                return

            if not destination_folder:
                QMessageBox.warning(self, "Error",
                                  "No archive location configured for this database.\n\n"
                                  "This should not happen. Please check the Database tab.")
                return

            config['source_directory'] = source_folders
            config['destination_directory'] = destination_folder
            config['database_path'] = self.current_database_path
            config['copy_files'] = self.setup_tab.is_copy_mode()
            config['move_files'] = self.setup_tab.is_move_mode()

            # Validate operation mode
            if not config['copy_files'] and not config['move_files']:
                QMessageBox.warning(self, "Error", "Please select Copy or Move mode")
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
            self.setup_tab.set_controls_enabled(False)
            self.status_bar.showMessage("Processing...")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start processing:\n\n{str(e)}")

    def stop_processing(self):
        """Stop the photo processing."""
        if self.worker and self.worker.isRunning():
            response = QMessageBox.question(self, "Stop Processing",
                                           "Are you sure you want to stop processing?\n\n"
                                           "Progress will be saved to the database.",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.No)
            if response == QMessageBox.Yes:
                self.worker.stop()
                self.status_bar.showMessage("Stopping...")

    def processing_completed(self, results):
        """Handle processing completion."""
        # Re-enable controls
        self.setup_tab.set_controls_enabled(True)
        self.status_bar.showMessage("Processing complete")

        # Update results tab
        self.results_tab.display_results(results)

        # Switch to results tab
        self.tabs.setCurrentWidget(self.results_tab)

        # Show completion message
        total_examined = results.get('total_files_examined', 0)
        originals = results.get('total_new_original_files', 0)
        duplicates = results.get('total_duplicates', 0)
        filtered = results.get('total_filtered', 0)

        QMessageBox.information(self, "Processing Complete",
                              f"Processing complete!\n\n"
                              f"Total files examined: {total_examined}\n"
                              f"New original photos: {originals}\n"
                              f"Duplicates found: {duplicates}\n"
                              f"Filtered files: {filtered}")

    def processing_error(self, error_msg):
        """Handle processing error."""
        # Re-enable controls
        self.setup_tab.set_controls_enabled(True)
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

        # Update database tab
        self.database_tab.set_database(database_path)

        # Get archive location from database
        archive_location = self.database_metadata.get_archive_location()

        # Update setup tab with archive location
        if archive_location:
            self.setup_tab.set_destination_folder(archive_location)

        # Update window title
        metadata = self.database_metadata.get_metadata()
        if metadata:
            db_name = metadata.get('database_name', 'Unknown')
            self.setWindowTitle(f"PyPhotoOrganizer - {db_name}")

        # Update status bar
        self.status_bar.showMessage(f"Database loaded: {db_name}")

    def on_database_changed(self, new_database_path):
        """Handle database change from Database tab."""
        self.set_database(new_database_path)

    def closeEvent(self, event):
        """Handle window close event."""
        if self.worker and self.worker.isRunning():
            response = QMessageBox.question(self, "Quit",
                                           "Processing is still running. Quit anyway?\n\n"
                                           "Progress will be saved to the database.",
                                           QMessageBox.Yes | QMessageBox.No,
                                           QMessageBox.No)
            if response == QMessageBox.Yes:
                self.worker.stop()
                self.worker.wait()  # Wait for thread to finish
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
