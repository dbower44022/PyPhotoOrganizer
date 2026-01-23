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
from album_manager import AlbumManager

logger = logging.getLogger(__name__)


class ProcessingWorker(QThread):
    """Worker thread for background photo processing."""

    # Progress signals
    scanning_progress = Signal(int, int, str)  # dirs_scanned, total_dirs, current_dir
    processing_progress = Signal(int, int, str, dict)  # processed, total, current_file, stats
    organizing_progress = Signal(int, int, str, object, object)  # organized, total, current_file, bytes_copied, total_bytes (object to handle >2GB)

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
        # Track partial progress for graceful shutdown
        self._partial_results = {
            'total_files_examined': 0,
            'total_new_original_files': 0,
            'total_duplicates': 0,
            'total_filtered': 0,
            'total_unreliable_dates': 0,
            'total_errors': 0
        }

    def run(self):
        """Main processing loop (runs in background thread)."""
        error_summary = None
        final_status = 'completed'
        was_cancelled = False

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
                was_cancelled = True
                self.status_update.emit("warning", "Cancelled during startup")
                return

            self.stage_changed.emit("Scanning Directories")
            self.status_update.emit("info", "Starting directory scan...")

            files = self._scan_directories()

            # Check for cancellation after scanning
            if self._should_stop:
                final_status = 'cancelled'
                was_cancelled = True
                self.status_update.emit("warning", "Cancelled after directory scan")
                return

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
                was_cancelled = True
                self.status_update.emit("warning", "Cancelled before processing")
                return

            self.stage_changed.emit("Processing and Organizing Files")
            self.status_update.emit("info", "Processing files and organizing...")

            # Pass the should_stop callable to enable graceful cancellation
            final_results = self._organize_files(files)

            # Check if processing was cancelled mid-way
            if final_results.get('was_cancelled', False):
                final_status = 'cancelled'
                was_cancelled = True
                self.status_update.emit("warning", "Processing cancelled by user")

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
                'session_id': self.session_id,
                'was_cancelled': was_cancelled
            }

            # Store partial results for potential later use
            self._partial_results = complete_results.copy()

            # End audit session with final results
            if self.audit_manager and self.session_id:
                self.audit_manager.end_session(
                    self.session_id,
                    status=final_status,
                    stats={
                        'total_files_processed': complete_results['total_files_examined'],
                        'total_unique_files': complete_results['total_new_original_files'],
                        'total_duplicates': complete_results['total_duplicates'],
                        'total_filtered': complete_results['total_filtered'],
                        'total_errors': complete_results['total_errors']
                    }
                )

            if was_cancelled:
                self.status_update.emit("warning", "Processing stopped - partial progress saved")
            else:
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
            if self.audit_manager and self.session_id and final_status not in ('completed', 'cancelled'):
                try:
                    # Use partial results if available
                    stats = {
                        'total_files_processed': self._partial_results.get('total_files_examined', 0),
                        'total_unique_files': self._partial_results.get('total_new_original_files', 0),
                        'total_duplicates': self._partial_results.get('total_duplicates', 0),
                        'total_filtered': self._partial_results.get('total_filtered', 0),
                        'total_errors': self._partial_results.get('total_errors', 0)
                    }
                    self.audit_manager.end_session(
                        self.session_id,
                        status=final_status,
                        stats=stats,
                        error_summary=error_summary
                    )
                except Exception as cleanup_error:
                    # Log but don't let audit cleanup errors mask the original error
                    logger.error(f"Failed to end audit session during cleanup: {cleanup_error}", exc_info=True)

    def _scan_directories(self):
        """Scan directories for files."""
        try:
            # Get ignored directories from config (if available)
            ignored_dirs = self.config.get('ignored_directories', [])
            logger.info(f"Using ignored directories: {ignored_dirs}")

            files = DuplicateFileDetection.get_file_list(
                sources=self.config.source_directory,
                recursive=self.config.include_subdirectories,
                file_endings=self.config.file_endings,
                progress_callback=self._scanning_callback,
                ignored_directories=ignored_dirs
            )
            return files
        except Exception as e:
            logger.error(f"Directory scan failed: {e}", exc_info=True)
            self.status_update.emit("error", f"Scan error: {str(e)}")
            raise

    def _scanning_callback(self, dirs_scanned, total_dirs, current_dir):
        """Callback for scanning progress. Returns True if should stop."""
        # Emit signal to UI (thread-safe)
        self.scanning_progress.emit(dirs_scanned, total_dirs, current_dir)

        # Return True to signal stop, False to continue
        return self._should_stop

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
        """Callback for processing progress. Returns True if should stop."""
        # Update partial results for graceful shutdown tracking
        self._partial_results['total_duplicates'] = stats.get('duplicates', 0)
        self._partial_results['total_filtered'] = stats.get('filtered', 0)
        self._partial_results['total_new_original_files'] = stats.get('unique', 0)

        # Emit signal to UI (thread-safe)
        self.processing_progress.emit(processed, total, current_file, stats)

        # Return True to signal stop, False to continue
        return self._should_stop

    def _organize_files(self, files):
        """Organize files into destination."""
        try:
            # Create album manager if there's a source-album mapping
            album_manager = None
            source_album_mapping = self.config.get('source_album_mapping', {})
            if source_album_mapping:
                album_manager = AlbumManager(self.config.database_path)
                self.status_update.emit("info", f"Album integration enabled for {len(source_album_mapping)} source(s)")

            results = main_module.organize_files(
                config=self.config,
                files=files,
                database_path=self.config.database_path,
                batch_size=self.config.batch_size,
                progress_callback=self._organizing_callback,
                audit_manager=self.audit_manager,
                session_id=self.session_id,
                should_stop=self._check_should_stop,  # Pass stop check callable
                album_manager=album_manager,
                source_album_mapping=source_album_mapping
            )

            return results

        except Exception as e:
            logger.error(f"File organization failed: {e}", exc_info=True)
            self.status_update.emit("error", f"Organization error: {str(e)}")
            raise

    def _check_should_stop(self):
        """Check if processing should stop. Returns True if stop was requested."""
        return self._should_stop

    def _organizing_callback(self, organized, total, current_file, bytes_copied, total_bytes):
        """Callback for organizing progress. Returns True if should stop."""
        # Update partial results for graceful shutdown tracking
        self._partial_results['total_files_examined'] = organized

        # Emit signal to UI (thread-safe)
        self.organizing_progress.emit(organized, total, current_file,
                                      bytes_copied, total_bytes)

        # Return True to signal stop, False to continue
        return self._should_stop

    def stop(self):
        """Request worker to stop gracefully."""
        self._should_stop = True
        self.status_update.emit("warning", "Stop requested - saving progress and stopping...")

    def pause(self):
        """Pause processing."""
        self._is_paused = True
        self.status_update.emit("info", "Processing paused")

    def resume(self):
        """Resume processing."""
        self._is_paused = False
        self.status_update.emit("info", "Processing resumed")
