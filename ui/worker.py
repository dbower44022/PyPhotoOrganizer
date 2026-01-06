"""
Worker Thread for PyPhotoOrganizer GUI

Background processing without blocking the UI.
"""

from PySide6.QtCore import QThread, Signal
import time
import traceback
import logging

from config import Config
import DuplicateFileDetection
import main as main_module
from audit_manager import AuditManager

logger = logging.getLogger(__name__)


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
        self.audit_manager = None
        self.session_id = None

    def run(self):
        """Main processing loop (runs in background thread)."""
        error_summary = None
        final_status = 'completed'

        try:
            self.start_time = time.time()

            # Create Config object from dictionary
            self.config = Config(settings_dict=self.config_dict)

            # Initialize audit manager and start session
            try:
                self.audit_manager = AuditManager(self.config.database_path)
                operation_mode = 'copy' if self.config.copy_files else 'move'
                organization_template = self.config.get('organization_template', '{YYYY}/{MM}/{DD}')

                self.session_id = self.audit_manager.start_session(
                    source_directories=self.config.source_directory,
                    destination_directory=self.config.destination_directory,
                    organization_template=organization_template,
                    operation_mode=operation_mode
                )
                self.status_update.emit("info", f"Audit session started: {self.session_id}")
            except Exception as e:
                # Non-fatal: continue without audit logging
                logger.error(f"Failed to initialize audit session: {e}", exc_info=True)
                self.status_update.emit("warning", f"Audit logging unavailable: {str(e)}")
                self.audit_manager = None
                self.session_id = None

            # Stage 1: Scanning
            if self._should_stop:
                final_status = 'cancelled'
                return

            self.stage_changed.emit("Scanning Directories")
            self.status_update.emit("info", "Starting directory scan...")

            files = self._scan_directories()

            if not files:
                self.status_update.emit("warning", "No files found to process")
                complete_results = {
                    'total_files_examined': 0,
                    'total_new_original_files': 0,
                    'total_duplicates': 0,
                    'total_filtered': 0,
                    'processing_time': 0,
                    'session_id': self.session_id
                }
                # End audit session with empty results
                if self.audit_manager and self.session_id:
                    self.audit_manager.end_session(
                        self.session_id,
                        status='completed',
                        stats=complete_results
                    )
                self.completed.emit(complete_results)
                return

            self.status_update.emit("info", f"Found {len(files)} files to process")

            # Update audit session with total files scanned
            if self.audit_manager and self.session_id:
                self.audit_manager.update_session_stats(
                    self.session_id,
                    total_files_scanned=len(files)
                )

            # Stage 2 & 3: Processing (Duplicate Detection) and Organizing
            # Note: organize_files handles both duplicate detection AND organization
            if self._should_stop:
                final_status = 'cancelled'
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
                'total_unreliable_dates': final_results.get('total_unreliable_dates', 0),
                'total_errors': final_results.get('total_errors', 0),
                'processing_time': processing_time,
                'filter_statistics': final_results.get('filter_statistics', {}),
                'filtered_files': final_results.get('filtered_files', []),
                'session_id': self.session_id
            }

            # End audit session with final results
            if self.audit_manager and self.session_id:
                self.audit_manager.end_session(
                    self.session_id,
                    status='completed',
                    stats={
                        'total_files_processed': complete_results['total_files_examined'],
                        'total_unique_files': complete_results['total_new_original_files'],
                        'total_duplicates': complete_results['total_duplicates'],
                        'total_filtered': complete_results['total_filtered'],
                        'total_errors': complete_results['total_errors']
                    }
                )

            self.status_update.emit("info", "Processing complete!")
            self.completed.emit(complete_results)

        except Exception as e:
            final_status = 'failed'
            logger.error(f"Processing failed: {e}", exc_info=True)
            error_msg = f"{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            error_summary = {'exception': str(e), 'traceback': traceback.format_exc()}
            self.status_update.emit("error", f"Error: {str(e)}")
            self.error_occurred.emit(error_msg)

        finally:
            # Ensure audit session is ended even on error/cancellation
            if self.audit_manager and self.session_id and final_status != 'completed':
                try:
                    self.audit_manager.end_session(
                        self.session_id,
                        status=final_status,
                        stats={},
                        error_summary=error_summary
                    )
                except Exception as cleanup_error:
                    # Log but don't let audit cleanup errors mask the original error
                    logger.error(f"Failed to end audit session during cleanup: {cleanup_error}", exc_info=True)

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
            logger.error(f"Directory scan failed: {e}", exc_info=True)
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
            logger.error(f"File processing failed: {e}", exc_info=True)
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
                progress_callback=self._organizing_callback,
                audit_manager=self.audit_manager,
                session_id=self.session_id
            )

            return results

        except Exception as e:
            logger.error(f"File organization failed: {e}", exc_info=True)
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
