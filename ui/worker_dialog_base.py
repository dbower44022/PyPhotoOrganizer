"""
Worker Dialog Base Class

Provides a reusable base class for dialogs that use QThread workers.
Handles the common pattern of stopping and waiting for workers on close.

Usage:
    class MyDialog(WorkerDialogBase):
        def __init__(self, parent=None):
            super().__init__(parent)
            # Create your worker
            self.my_worker = MyWorker()
            # Register it for automatic cleanup
            self.register_worker(self.my_worker)

        def start_operation(self):
            self.my_worker.start()

The base class handles:
- Stopping workers when dialog closes
- Waiting for workers to finish
- Preventing dialog close while workers are running (optional)
- Tracking multiple workers per dialog
"""

from typing import List, Optional, Union
from PySide6.QtWidgets import QDialog, QMessageBox
from PySide6.QtCore import QThread
from PySide6.QtGui import QCloseEvent

import constants


class WorkerDialogBase(QDialog):
    """
    Base class for dialogs that use QThread workers.

    Provides automatic worker cleanup when the dialog is closed.
    Workers are stopped and waited on in closeEvent to prevent
    crashes from thread destruction while running.

    Attributes:
        _workers: List of registered workers to manage
        _block_close_while_running: If True, shows warning instead of closing
                                    while workers are running
        _worker_shutdown_timeout: Timeout in seconds for waiting on workers
    """

    def __init__(self, parent=None, block_close_while_running: bool = False):
        """
        Initialize the worker dialog base.

        Args:
            parent: Parent widget
            block_close_while_running: If True, prevents closing while
                                       workers are active (shows warning)
        """
        super().__init__(parent)
        self._workers: List[QThread] = []
        self._block_close_while_running = block_close_while_running
        self._worker_shutdown_timeout = constants.WORKER_SHUTDOWN_TIMEOUT_SECONDS

    def register_worker(self, worker: QThread) -> None:
        """
        Register a worker for automatic cleanup on dialog close.

        Args:
            worker: QThread worker to register
        """
        if worker not in self._workers:
            self._workers.append(worker)

    def unregister_worker(self, worker: QThread) -> None:
        """
        Unregister a worker from automatic cleanup.

        Args:
            worker: QThread worker to unregister
        """
        if worker in self._workers:
            self._workers.remove(worker)

    def has_running_workers(self) -> bool:
        """
        Check if any registered workers are currently running.

        Returns:
            True if any worker is running, False otherwise
        """
        return any(
            worker is not None and worker.isRunning()
            for worker in self._workers
        )

    def get_running_workers(self) -> List[QThread]:
        """
        Get list of currently running workers.

        Returns:
            List of running QThread workers
        """
        return [
            worker for worker in self._workers
            if worker is not None and worker.isRunning()
        ]

    def stop_all_workers(self, wait: bool = True) -> None:
        """
        Stop all registered workers.

        Args:
            wait: If True, wait for workers to finish after stopping
        """
        for worker in self._workers:
            if worker is not None and worker.isRunning():
                # Try to call stop() if the worker has it
                if hasattr(worker, 'stop'):
                    worker.stop()
                elif hasattr(worker, 'cancel'):
                    worker.cancel()
                elif hasattr(worker, 'requestInterruption'):
                    worker.requestInterruption()

                if wait:
                    # Wait with timeout
                    timeout_ms = self._worker_shutdown_timeout * 1000
                    if not worker.wait(timeout_ms):
                        # Worker didn't stop in time, try terminate as last resort
                        worker.terminate()
                        worker.wait(1000)  # Brief wait after terminate

    def wait_for_workers(self, timeout_ms: Optional[int] = None) -> bool:
        """
        Wait for all workers to finish.

        Args:
            timeout_ms: Timeout in milliseconds per worker (None for default)

        Returns:
            True if all workers finished, False if timeout
        """
        if timeout_ms is None:
            timeout_ms = self._worker_shutdown_timeout * 1000

        all_finished = True
        for worker in self._workers:
            if worker is not None and worker.isRunning():
                if not worker.wait(timeout_ms):
                    all_finished = False

        return all_finished

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        Handle dialog close event.

        Stops all running workers and waits for them to finish.
        If block_close_while_running is True, shows a warning instead.

        Args:
            event: The close event
        """
        if self.has_running_workers():
            if self._block_close_while_running:
                # Show warning and reject close
                QMessageBox.warning(
                    self,
                    "Operation in Progress",
                    "Please wait for the current operation to complete, "
                    "or cancel it before closing this dialog."
                )
                event.ignore()
                return

            # Stop all workers and wait
            self.stop_all_workers(wait=True)

        event.accept()

    def set_worker_shutdown_timeout(self, seconds: int) -> None:
        """
        Set the timeout for waiting on workers during shutdown.

        Args:
            seconds: Timeout in seconds
        """
        self._worker_shutdown_timeout = seconds

    def set_block_close_while_running(self, block: bool) -> None:
        """
        Set whether to block dialog close while workers are running.

        Args:
            block: If True, shows warning instead of closing
        """
        self._block_close_while_running = block


class SingleWorkerDialogBase(WorkerDialogBase):
    """
    Convenience base class for dialogs with a single worker.

    Provides a simpler interface when only one worker is needed.

    Usage:
        class MyDialog(SingleWorkerDialogBase):
            def __init__(self, parent=None):
                super().__init__(parent)
                self._worker = MyWorker()  # Use _worker attribute

            def start_operation(self):
                self.start_worker()  # Convenience method
    """

    def __init__(self, parent=None, block_close_while_running: bool = False):
        """
        Initialize the single worker dialog base.

        Args:
            parent: Parent widget
            block_close_while_running: If True, prevents closing while
                                       worker is active
        """
        super().__init__(parent, block_close_while_running)
        self._worker: Optional[QThread] = None

    @property
    def worker(self) -> Optional[QThread]:
        """Get the worker instance."""
        return self._worker

    @worker.setter
    def worker(self, value: QThread) -> None:
        """
        Set the worker instance.

        Automatically registers the worker for cleanup.
        """
        # Unregister old worker if exists
        if self._worker is not None:
            self.unregister_worker(self._worker)

        self._worker = value

        # Register new worker
        if self._worker is not None:
            self.register_worker(self._worker)

    def is_worker_running(self) -> bool:
        """
        Check if the worker is currently running.

        Returns:
            True if worker is running, False otherwise
        """
        return self._worker is not None and self._worker.isRunning()

    def start_worker(self) -> bool:
        """
        Start the worker if not already running.

        Returns:
            True if worker started, False if already running or no worker
        """
        if self._worker is None:
            return False

        if self._worker.isRunning():
            return False

        self._worker.start()
        return True

    def stop_worker(self, wait: bool = True) -> None:
        """
        Stop the worker.

        Args:
            wait: If True, wait for worker to finish
        """
        if self._worker is None:
            return

        if self._worker.isRunning():
            if hasattr(self._worker, 'stop'):
                self._worker.stop()
            elif hasattr(self._worker, 'cancel'):
                self._worker.cancel()

            if wait:
                timeout_ms = self._worker_shutdown_timeout * 1000
                self._worker.wait(timeout_ms)
