"""
Worker Thread for PyPhotoOrganizer GUI

Background processing without blocking the UI.
"""

from PySide6.QtCore import QThread, Signal
import time
import traceback

from config import Config
import DuplicateFileDetection
import main as main_module


class ProcessingWorker(QThread):
    """Worker thread for background photo processing."""

    # Progress signals
    scanning_progress = Signal(int, int, str)  # dirs_scanned, total_dirs, current_dir
    processing_progress = Signal(int, int, str, dict)  # processed, total, current_file, stats
    organizing_progress = Signal(int, int, str, int, int)  # organized, total, current_file, bytes_copied, total_bytes

    # Status signals
    status_update = Signal(str, str)  # level, message
    stage_changed = Signal(str)  # stage_name
    completed = Signal(dict)  # final_results
    error_occurred = Signal(str)  # error_message

    def __init__(self, config_dict):
        super().__init__()
        self.config_dict = config_dict
        self.config = None
        self._should_stop = False
        self._is_paused = False
        self.start_time = None

    def run(self):
        """Main processing loop (runs in background thread)."""
        try:
            self.start_time = time.time()

            # Create Config object from dictionary
            self.config = Config(settings_dict=self.config_dict)

            # Stage 1: Scanning
            if self._should_stop:
                return

            self.stage_changed.emit("Scanning Directories")
            self.status_update.emit("info", "Starting directory scan...")

            files = self._scan_directories()

            if not files:
                self.status_update.emit("warning", "No files found to process")
                self.completed.emit({
                    'total_files_examined': 0,
                    'total_new_original_files': 0,
                    'total_duplicates': 0,
                    'total_filtered': 0,
                    'processing_time': 0
                })
                return

            self.status_update.emit("info", f"Found {len(files)} files to process")

            # Stage 2 & 3: Processing (Duplicate Detection) and Organizing
            # Note: organize_files handles both duplicate detection AND organization
            if self._should_stop:
                return

            self.stage_changed.emit("Processing and Organizing Files")
            self.status_update.emit("info", "Processing files and organizing...")

            final_results = self._organize_files(files)

            # Compile final results
            processing_time = time.time() - self.start_time

            complete_results = {
                'total_files_examined': final_results.get('total_files_processed', len(files)),
                'total_new_original_files': final_results.get('total_new_original_files', 0),
                'total_duplicates': final_results.get('total_duplicates', 0),
                'total_filtered': final_results.get('total_filtered', 0),
                'processing_time': processing_time,
                'filter_statistics': final_results.get('filter_statistics', {})
            }

            self.status_update.emit("info", "Processing complete!")
            self.completed.emit(complete_results)

        except Exception as e:
            error_msg = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            self.status_update.emit("error", f"Error: {str(e)}")
            self.error_occurred.emit(error_msg)

    def _scan_directories(self):
        """Scan directories for files."""
        try:
            files = DuplicateFileDetection.get_file_list(
                sources=self.config.source_directory,
                recursive=self.config.include_subdirectories,
                file_endings=self.config.file_endings,
                progress_callback=self._scanning_callback
            )
            return files
        except Exception as e:
            self.status_update.emit("error", f"Scan error: {str(e)}")
            raise

    def _scanning_callback(self, dirs_scanned, total_dirs, current_dir):
        """Callback for scanning progress."""
        if self._should_stop:
            return

        # Emit signal to UI (thread-safe)
        self.scanning_progress.emit(dirs_scanned, total_dirs, current_dir)

    def _process_files(self, files):
        """Process files for duplicates."""
        try:
            # Load existing hashes from database
            hashes = DuplicateFileDetection.load_photo_hashes(self.config.database_path)

            # Find duplicates
            results = DuplicateFileDetection.find_duplicates(
                files=files,
                hashes=hashes,
                database_path=self.config.database_path,
                batch_size=self.config.batch_size,
                partial_hash_enabled=self.config.partial_hash_enabled,
                partial_hash_bytes=self.config.partial_hash_bytes,
                partial_hash_min_file_size=self.config.partial_hash_min_file_size,
                config=self.config_dict,
                progress_callback=self._processing_callback
            )

            return results

        except Exception as e:
            self.status_update.emit("error", f"Processing error: {str(e)}")
            raise

    def _processing_callback(self, processed, total, current_file, stats):
        """Callback for processing progress."""
        if self._should_stop:
            return

        # Emit signal to UI (thread-safe)
        self.processing_progress.emit(processed, total, current_file, stats)

    def _organize_files(self, files):
        """Organize files into destination."""
        try:
            results = main_module.organize_files(
                config=self.config,
                files=files,
                database_path=self.config.database_path,
                batch_size=self.config.batch_size,
                progress_callback=self._organizing_callback
            )

            return results

        except Exception as e:
            self.status_update.emit("error", f"Organization error: {str(e)}")
            raise

    def _organizing_callback(self, organized, total, current_file, bytes_copied, total_bytes):
        """Callback for organizing progress."""
        if self._should_stop:
            return

        # Emit signal to UI (thread-safe)
        self.organizing_progress.emit(organized, total, current_file,
                                      bytes_copied, total_bytes)

    def stop(self):
        """Request worker to stop gracefully."""
        self._should_stop = True
        self.status_update.emit("warning", "Stop requested - finishing current batch...")

    def pause(self):
        """Pause processing."""
        self._is_paused = True
        self.status_update.emit("info", "Processing paused")

    def resume(self):
        """Resume processing."""
        self._is_paused = False
        self.status_update.emit("info", "Processing resumed")
