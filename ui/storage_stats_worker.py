"""
Storage Statistics Worker

Background worker for calculating storage statistics across all archive locations.
"""

from PySide6.QtCore import QThread, Signal
import os
import logging

logger = logging.getLogger(__name__)


class StorageStatsWorker(QThread):
    """
    Worker thread for calculating storage statistics.

    Scans multiple archive locations and calculates total size and file counts.
    Supports graceful cancellation.
    """

    # Signals
    progress_update = Signal(str)  # location being scanned
    completed = Signal(dict)  # results dictionary
    error_occurred = Signal(str)  # error message

    def __init__(self, locations_to_scan: dict):
        """
        Initialize the storage stats worker.

        Args:
            locations_to_scan: Dictionary of {name: path} or {name: {album_id: path}}
        """
        super().__init__()
        self.locations_to_scan = locations_to_scan
        self._should_stop = False

    def stop(self):
        """Request the worker to stop gracefully."""
        self._should_stop = True
        logger.info("Storage stats calculation stop requested")

    def run(self):
        """Main processing loop."""
        results = {}

        try:
            # Process main archive locations
            for location_name in ['main_archive', 'video_archive', 'prior_revision_archive', 'delete_vault']:
                if self._should_stop:
                    break

                path = self.locations_to_scan.get(location_name)
                if path and os.path.exists(path):
                    self.progress_update.emit(f"Scanning {location_name}...")
                    stats = self._scan_directory(path)
                    stats['path'] = path
                    results[location_name] = stats
                else:
                    results[location_name] = {
                        'path': path,
                        'size_bytes': 0,
                        'file_count': 0
                    }

            # Process database files
            if not self._should_stop:
                db_path = self.locations_to_scan.get('database')
                if db_path:
                    self.progress_update.emit("Calculating database size...")
                    results['database'] = self._get_database_stats(db_path)

            # Process albums
            if not self._should_stop:
                albums_data = self.locations_to_scan.get('albums', {})
                results['albums'] = {}

                for album_key, album_path in albums_data.items():
                    if self._should_stop:
                        break

                    if album_path and os.path.exists(album_path):
                        self.progress_update.emit(f"Scanning {album_key}...")
                        stats = self._scan_directory(album_path)
                        stats['path'] = album_path
                        results['albums'][album_key] = stats
                    else:
                        results['albums'][album_key] = {
                            'path': album_path,
                            'size_bytes': 0,
                            'file_count': 0
                        }

            self.completed.emit(results)

        except Exception as e:
            logger.error(f"Storage stats calculation failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))

    def _scan_directory(self, path: str) -> dict:
        """
        Scan a directory and calculate total size and file count.

        Args:
            path: Directory path to scan

        Returns:
            Dictionary with size_bytes and file_count
        """
        total_size = 0
        file_count = 0

        try:
            for root, dirs, files in os.walk(path):
                if self._should_stop:
                    break

                for filename in files:
                    if self._should_stop:
                        break

                    file_path = os.path.join(root, filename)
                    try:
                        if os.path.isfile(file_path):
                            total_size += os.path.getsize(file_path)
                            file_count += 1
                    except (OSError, IOError):
                        # Skip files we can't access
                        pass

        except Exception as e:
            logger.error(f"Error scanning directory {path}: {e}")

        return {
            'size_bytes': total_size,
            'file_count': file_count
        }

    def _get_database_stats(self, db_path: str) -> dict:
        """
        Get database file statistics.

        Args:
            db_path: Path to the database file

        Returns:
            Dictionary with size_bytes and file_count
        """
        total_size = 0
        file_count = 0

        # Main database file
        if os.path.exists(db_path):
            total_size += os.path.getsize(db_path)
            file_count += 1

        # WAL file
        wal_path = db_path + '-wal'
        if os.path.exists(wal_path):
            total_size += os.path.getsize(wal_path)
            file_count += 1

        # SHM file
        shm_path = db_path + '-shm'
        if os.path.exists(shm_path):
            total_size += os.path.getsize(shm_path)
            file_count += 1

        return {
            'path': db_path,
            'size_bytes': total_size,
            'file_count': file_count
        }
