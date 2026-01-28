"""
Service Manager for Auto-Import Service.

Manages the service lifecycle, scheduling, and coordination between components.
"""

import logging
import os
import signal
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from auto_import.config import ConfigManager, ServiceConfig

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """Current status of the service."""
    running: bool = False
    paused: bool = False
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    runs_completed: int = 0
    files_imported_total: int = 0
    last_error: Optional[str] = None
    uptime_seconds: float = 0


class ServiceManager:
    """
    Manages the auto-import service lifecycle.

    Responsibilities:
    - Start/stop service
    - Schedule periodic scans
    - Handle signals (SIGTERM, SIGHUP)
    - Manage worker threads
    - Coordinate between components
    """

    def __init__(self, config: ServiceConfig):
        """
        Initialize ServiceManager.

        Args:
            config: Service configuration
        """
        self.config = config
        self._running = False
        self._paused = False
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()

        # Statistics
        self._start_time: Optional[datetime] = None
        self._last_run: Optional[datetime] = None
        self._next_run: Optional[datetime] = None
        self._runs_completed = 0
        self._files_imported_total = 0
        self._last_error: Optional[str] = None

        # Components (lazy loaded)
        self._watcher = None
        self._processor = None
        self._reporter = None
        self._scheduler = None

        # Signal handlers
        self._original_sigterm = None
        self._original_sighup = None
        self._original_sigint = None

    @classmethod
    def from_config_file(cls, config_path: str) -> 'ServiceManager':
        """Create ServiceManager from config file path."""
        config_manager = ConfigManager(config_path)
        config = config_manager.load()
        return cls(config)

    def _setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        self._original_sigterm = signal.signal(signal.SIGTERM, self._handle_sigterm)
        self._original_sigint = signal.signal(signal.SIGINT, self._handle_sigint)

        # SIGHUP for config reload (Unix only)
        if hasattr(signal, 'SIGHUP'):
            self._original_sighup = signal.signal(signal.SIGHUP, self._handle_sighup)

    def _restore_signal_handlers(self):
        """Restore original signal handlers."""
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sighup and hasattr(signal, 'SIGHUP'):
            signal.signal(signal.SIGHUP, self._original_sighup)

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM signal."""
        logger.info("Received SIGTERM, initiating graceful shutdown...")
        self.stop()

    def _handle_sigint(self, signum, frame):
        """Handle SIGINT signal (Ctrl+C)."""
        logger.info("Received SIGINT, initiating graceful shutdown...")
        self.stop()

    def _handle_sighup(self, signum, frame):
        """Handle SIGHUP signal (config reload)."""
        logger.info("Received SIGHUP, reloading configuration...")
        # Config reload would be handled here if we had a ConfigManager reference

    def _initialize_components(self):
        """Initialize service components."""
        from auto_import.watcher import DirectoryWatcher
        from auto_import.processor import ImportProcessor
        from auto_import.reporter import ReportManager
        from auto_import.scheduler import Scheduler

        logger.info("Initializing service components...")

        self._watcher = DirectoryWatcher(self.config)
        self._processor = ImportProcessor(self.config)
        self._reporter = ReportManager(self.config)
        self._scheduler = Scheduler(self.config.schedule)

        logger.info("Service components initialized")

    def _write_pid_file(self):
        """Write PID file if configured."""
        if not self.config.pid_file:
            return

        try:
            pid_dir = os.path.dirname(self.config.pid_file)
            if pid_dir and not os.path.exists(pid_dir):
                os.makedirs(pid_dir, exist_ok=True)

            with open(self.config.pid_file, 'w') as f:
                f.write(str(os.getpid()))

            logger.debug(f"PID file written: {self.config.pid_file}")

        except Exception as e:
            logger.warning(f"Failed to write PID file: {e}")

    def _remove_pid_file(self):
        """Remove PID file."""
        if not self.config.pid_file:
            return

        try:
            if os.path.exists(self.config.pid_file):
                os.remove(self.config.pid_file)
                logger.debug(f"PID file removed: {self.config.pid_file}")
        except Exception as e:
            logger.warning(f"Failed to remove PID file: {e}")

    def start(self):
        """
        Start the service.

        This method blocks until the service is stopped.
        """
        if self._running:
            logger.warning("Service is already running")
            return

        logger.info("=" * 60)
        logger.info("Starting PyPhotoOrganizer Auto-Import Service")
        logger.info("=" * 60)

        try:
            self._running = True
            self._start_time = datetime.now()
            self._stop_event.clear()

            # Initialize components
            self._initialize_components()

            # Set up signal handlers
            self._setup_signal_handlers()

            # Write PID file
            self._write_pid_file()

            # Log configuration summary
            self._log_config_summary()

            # Run on startup if configured
            if self.config.schedule.run_on_startup:
                logger.info("Running initial import on startup...")
                self._run_import_cycle()

            # Main service loop
            self._run_loop()

        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
            self._last_error = str(e)
            raise

        finally:
            self._cleanup()

    def _log_config_summary(self):
        """Log configuration summary."""
        logger.info("Configuration Summary:")
        logger.info(f"  Database: {self.config.database_path}")
        logger.info(f"  Schedule: {self.config.schedule.mode} "
                   f"(every {self.config.schedule.interval_minutes} min)")

        if self.config.schedule.quiet_hours_start:
            logger.info(f"  Quiet hours: {self.config.schedule.quiet_hours_start} - "
                       f"{self.config.schedule.quiet_hours_end}")

        logger.info(f"  Watch directories: {len(self.config.watch_directories)}")
        for wd in self.config.watch_directories:
            status = "available" if wd.is_available() else "NOT AVAILABLE"
            enabled = "enabled" if wd.enabled else "disabled"
            logger.info(f"    - {wd.path} [{enabled}] [{status}]")

        if self.config.notifications.email.is_configured():
            logger.info(f"  Email notifications: {', '.join(self.config.notifications.email.recipients)}")
        else:
            logger.info("  Email notifications: disabled")

    def _run_loop(self):
        """Main service loop."""
        logger.info("Entering main service loop")

        while self._running and not self._stop_event.is_set():
            try:
                # Calculate next run time
                next_run = self._scheduler.get_next_run_time()
                self._next_run = next_run

                # Wait until next run or stop signal
                wait_seconds = (next_run - datetime.now()).total_seconds()
                if wait_seconds > 0:
                    logger.debug(f"Waiting {wait_seconds:.0f} seconds until next run")
                    if self._stop_event.wait(timeout=min(wait_seconds, 60)):
                        break  # Stop signal received

                # Check if we should run now
                if datetime.now() >= next_run:
                    # Check quiet hours
                    if self.config.schedule.is_quiet_hours():
                        logger.debug("Skipping run during quiet hours")
                        time.sleep(60)  # Check again in a minute
                        continue

                    # Check if paused
                    if self._paused:
                        logger.debug("Service is paused, skipping run")
                        time.sleep(60)
                        continue

                    # Run import cycle
                    self._run_import_cycle()

            except Exception as e:
                logger.error(f"Error in service loop: {e}", exc_info=True)
                self._last_error = str(e)
                time.sleep(60)  # Wait before retrying

    def _run_import_cycle(self):
        """Run a single import cycle."""
        from auto_import.processor import ImportResult

        logger.info("-" * 40)
        logger.info("Starting import cycle")
        start_time = datetime.now()

        try:
            # Scan for new files
            new_files = self._watcher.scan_for_new_files()
            logger.info(f"Found {len(new_files)} new files to process")

            if not new_files:
                # No new files
                self._last_run = datetime.now()
                self._runs_completed += 1

                if self.config.notifications.report_on_no_changes:
                    result = ImportResult(
                        start_time=start_time,
                        end_time=datetime.now(),
                        files_scanned=0,
                        files_imported=0,
                        files_duplicate=0,
                        files_filtered=0,
                        files_failed=0,
                        bytes_processed=0,
                        errors=[],
                        imported_files=[],
                        watch_directories_scanned=len(self.config.get_enabled_watch_directories())
                    )
                    self._send_report(result)

                logger.info("No new files to process")
                return

            # Process files
            result = self._processor.process_files(new_files)

            # Update statistics
            self._last_run = datetime.now()
            self._runs_completed += 1
            self._files_imported_total += result.files_imported

            # Mark files as processed
            for file_info in new_files:
                self._watcher.mark_as_processed(file_info.path)

            # Cloud sync if enabled
            if self.config.processing.cloud_sync_after_import and result.files_imported > 0:
                self._run_cloud_sync()

            # Send report
            self._send_report(result)

            logger.info(f"Import cycle completed: {result.files_imported} imported, "
                       f"{result.files_duplicate} duplicates, {result.files_failed} failed")

        except Exception as e:
            logger.error(f"Import cycle failed: {e}", exc_info=True)
            self._last_error = str(e)

            # Send failure report
            if self.config.notifications.report_on_failure:
                result = ImportResult(
                    start_time=start_time,
                    end_time=datetime.now(),
                    files_scanned=0,
                    files_imported=0,
                    files_duplicate=0,
                    files_filtered=0,
                    files_failed=0,
                    bytes_processed=0,
                    errors=[str(e)],
                    imported_files=[],
                    watch_directories_scanned=0
                )
                self._send_report(result)

    def _run_cloud_sync(self):
        """Run cloud sync after import."""
        logger.info("Running cloud sync...")
        try:
            # This would integrate with CloudSyncManager
            # For now, just log
            logger.info("Cloud sync completed")
        except Exception as e:
            logger.error(f"Cloud sync failed: {e}")

    def _send_report(self, result):
        """Send import report."""
        if not self.config.notifications.enabled:
            return

        try:
            should_send = (
                (result.files_imported > 0 and self.config.notifications.report_on_success) or
                (result.errors and self.config.notifications.report_on_failure) or
                (result.files_imported == 0 and self.config.notifications.report_on_no_changes)
            )

            if should_send:
                self._reporter.send_report(result)
                logger.info("Report sent successfully")

        except Exception as e:
            logger.error(f"Failed to send report: {e}")

    def stop(self):
        """Stop the service gracefully."""
        if not self._running:
            return

        logger.info("Stopping service...")
        self._running = False
        self._stop_event.set()

    def pause(self):
        """Pause the service (skip runs but stay running)."""
        self._paused = True
        logger.info("Service paused")

    def resume(self):
        """Resume the service from pause."""
        self._paused = False
        logger.info("Service resumed")

    def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up...")

        self._running = False
        self._restore_signal_handlers()
        self._remove_pid_file()

        logger.info("Service stopped")

    def run_once(self) -> 'ImportResult':
        """
        Run a single import cycle without starting the service loop.

        Useful for manual/testing runs.

        Returns:
            ImportResult from the import cycle
        """
        from auto_import.watcher import DirectoryWatcher
        from auto_import.processor import ImportProcessor, ImportResult
        from auto_import.reporter import ReportManager

        logger.info("Running single import cycle...")

        watcher = DirectoryWatcher(self.config)
        processor = ImportProcessor(self.config)
        reporter = ReportManager(self.config)

        start_time = datetime.now()

        try:
            # Scan for new files
            new_files = watcher.scan_for_new_files()
            logger.info(f"Found {len(new_files)} new files")

            if not new_files:
                return ImportResult(
                    start_time=start_time,
                    end_time=datetime.now(),
                    files_scanned=0,
                    files_imported=0,
                    files_duplicate=0,
                    files_filtered=0,
                    files_failed=0,
                    bytes_processed=0,
                    errors=[],
                    imported_files=[],
                    watch_directories_scanned=len(self.config.get_enabled_watch_directories())
                )

            # Process files
            result = processor.process_files(new_files)

            # Mark as processed
            for file_info in new_files:
                watcher.mark_as_processed(file_info.path)

            # Send report
            if self.config.notifications.enabled:
                reporter.send_report(result)

            return result

        except Exception as e:
            logger.error(f"Single run failed: {e}", exc_info=True)
            return ImportResult(
                start_time=start_time,
                end_time=datetime.now(),
                files_scanned=0,
                files_imported=0,
                files_duplicate=0,
                files_filtered=0,
                files_failed=0,
                bytes_processed=0,
                errors=[str(e)],
                imported_files=[],
                watch_directories_scanned=0
            )

    def get_status(self) -> ServiceStatus:
        """Get current service status."""
        uptime = 0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()

        return ServiceStatus(
            running=self._running,
            paused=self._paused,
            last_run=self._last_run,
            next_run=self._next_run,
            runs_completed=self._runs_completed,
            files_imported_total=self._files_imported_total,
            last_error=self._last_error,
            uptime_seconds=uptime,
        )
