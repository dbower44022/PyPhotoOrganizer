"""
Archive Backup Worker

Background worker for creating full backups of the database and all archive locations.
"""

from PySide6.QtCore import QThread, Signal
import os
import shutil
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ArchiveBackupWorker(QThread):
    """
    Worker thread for full archive backup.

    Creates a timestamped backup folder containing:
    - Database file (+ WAL and SHM)
    - Main archive directory
    - Video archive directory (if configured)
    - Prior revisions archive (if configured)
    - Delete vault (if configured)
    - All album storage locations

    Supports graceful cancellation.
    """

    # Signals
    progress_update = Signal(int, int, str)  # current, total, filename
    stage_update = Signal(str)  # current backup stage
    status_update = Signal(str)  # status message
    completed = Signal(dict)  # results dictionary
    error_occurred = Signal(str)  # error message

    def __init__(self, database_path: str, backup_destination: str,
                 archives_to_backup: dict, albums: list):
        """
        Initialize the backup worker.

        Args:
            database_path: Path to the SQLite database
            backup_destination: Root folder for backups
            archives_to_backup: Dictionary with main_archive, video_archive, etc.
            albums: List of album dictionaries with storage_location
        """
        super().__init__()
        self.database_path = database_path
        self.backup_destination = backup_destination
        self.archives_to_backup = archives_to_backup
        self.albums = albums
        self._should_stop = False

    def stop(self):
        """Request the worker to stop gracefully."""
        self._should_stop = True
        logger.info("Backup stop requested")

    def run(self):
        """Main backup process."""
        files_copied = 0
        bytes_copied = 0
        errors = []
        backup_folder = None

        try:
            # Create timestamped backup folder
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_folder = os.path.join(self.backup_destination, f"backup_{timestamp}")
            os.makedirs(backup_folder, exist_ok=True)

            self.status_update.emit(f"Created backup folder: {backup_folder}")
            logger.info(f"Starting backup to: {backup_folder}")

            # Initialize manifest
            manifest = {
                'backup_timestamp': datetime.now().isoformat(),
                'database_path': self.database_path,
                'archives': {},
                'albums': [],
                'stats': {
                    'total_files': 0,
                    'total_bytes': 0
                }
            }

            # 1. Backup database files
            if not self._should_stop:
                self.stage_update.emit("Backing up database...")
                db_result = self._backup_database(backup_folder)
                files_copied += db_result['files']
                bytes_copied += db_result['bytes']
                manifest['database_backup'] = db_result

            # 2. Backup main archive
            if not self._should_stop:
                main_archive = self.archives_to_backup.get('main_archive')
                if main_archive and os.path.exists(main_archive):
                    self.stage_update.emit("Backing up main archive...")
                    result = self._backup_directory(
                        main_archive,
                        os.path.join(backup_folder, "main_archive"),
                        "Main Archive"
                    )
                    files_copied += result['files']
                    bytes_copied += result['bytes']
                    errors.extend(result.get('errors', []))
                    manifest['archives']['main_archive'] = result

            # 3. Backup video archive
            if not self._should_stop:
                video_archive = self.archives_to_backup.get('video_archive')
                if video_archive and os.path.exists(video_archive):
                    self.stage_update.emit("Backing up video archive...")
                    result = self._backup_directory(
                        video_archive,
                        os.path.join(backup_folder, "video_archive"),
                        "Video Archive"
                    )
                    files_copied += result['files']
                    bytes_copied += result['bytes']
                    errors.extend(result.get('errors', []))
                    manifest['archives']['video_archive'] = result

            # 4. Backup prior revisions archive
            if not self._should_stop:
                prior_revision = self.archives_to_backup.get('prior_revision_archive')
                if prior_revision and os.path.exists(prior_revision):
                    self.stage_update.emit("Backing up prior revisions archive...")
                    result = self._backup_directory(
                        prior_revision,
                        os.path.join(backup_folder, "prior_revisions"),
                        "Prior Revisions"
                    )
                    files_copied += result['files']
                    bytes_copied += result['bytes']
                    errors.extend(result.get('errors', []))
                    manifest['archives']['prior_revisions'] = result

            # 5. Backup delete vault
            if not self._should_stop:
                delete_vault = self.archives_to_backup.get('delete_vault')
                if delete_vault and os.path.exists(delete_vault):
                    self.stage_update.emit("Backing up delete vault...")
                    result = self._backup_directory(
                        delete_vault,
                        os.path.join(backup_folder, "delete_vault"),
                        "Delete Vault"
                    )
                    files_copied += result['files']
                    bytes_copied += result['bytes']
                    errors.extend(result.get('errors', []))
                    manifest['archives']['delete_vault'] = result

            # 6. Backup albums
            if not self._should_stop and self.albums:
                albums_folder = os.path.join(backup_folder, "albums")
                os.makedirs(albums_folder, exist_ok=True)

                for album in self.albums:
                    if self._should_stop:
                        break

                    album_name = album.get('album_name', 'unknown')
                    album_location = album.get('storage_location')

                    if album_location and os.path.exists(album_location):
                        self.stage_update.emit(f"Backing up album: {album_name}...")

                        # Sanitize album name for folder
                        safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in album_name)
                        result = self._backup_directory(
                            album_location,
                            os.path.join(albums_folder, safe_name),
                            f"Album: {album_name}"
                        )
                        files_copied += result['files']
                        bytes_copied += result['bytes']
                        errors.extend(result.get('errors', []))
                        manifest['albums'].append({
                            'name': album_name,
                            'original_path': album_location,
                            **result
                        })

            # Update manifest stats
            manifest['stats']['total_files'] = files_copied
            manifest['stats']['total_bytes'] = bytes_copied

            # Write manifest
            if not self._should_stop:
                manifest_path = os.path.join(backup_folder, "manifest.json")
                with open(manifest_path, 'w') as f:
                    json.dump(manifest, f, indent=2)
                logger.info(f"Wrote backup manifest: {manifest_path}")

            # Determine status
            if self._should_stop:
                status = 'cancelled'
            elif errors:
                status = 'completed_with_errors'
            else:
                status = 'completed'

            logger.info(f"Backup {status}: {files_copied} files, {bytes_copied} bytes")

            self.completed.emit({
                'status': status,
                'files_copied': files_copied,
                'bytes_copied': bytes_copied,
                'backup_folder': backup_folder,
                'errors': errors
            })

        except Exception as e:
            logger.error(f"Backup failed: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
            self.completed.emit({
                'status': 'failed',
                'files_copied': files_copied,
                'bytes_copied': bytes_copied,
                'backup_folder': backup_folder,
                'errors': [str(e)]
            })

    def _backup_database(self, backup_folder: str) -> dict:
        """
        Backup database files (db, WAL, SHM).

        Args:
            backup_folder: Destination folder

        Returns:
            Dictionary with files copied and bytes
        """
        files = 0
        bytes_copied = 0

        db_backup_folder = os.path.join(backup_folder, "database")
        os.makedirs(db_backup_folder, exist_ok=True)

        def _copy_with_fallback(src, dst):
            """Copy file, falling back to copyfile() if copy2() fails on network shares."""
            try:
                shutil.copy2(src, dst)
            except OSError as e:
                if e.errno == 95:  # Operation not supported (SMB/network shares)
                    logger.warning(f"copy2 failed (metadata not supported), using copyfile: {e}")
                    shutil.copyfile(src, dst)
                else:
                    raise

        # Main database file
        if os.path.exists(self.database_path):
            dest = os.path.join(db_backup_folder, os.path.basename(self.database_path))
            _copy_with_fallback(self.database_path, dest)
            files += 1
            bytes_copied += os.path.getsize(dest)
            self.progress_update.emit(files, files, os.path.basename(self.database_path))

        # WAL file
        wal_path = self.database_path + '-wal'
        if os.path.exists(wal_path):
            dest = os.path.join(db_backup_folder, os.path.basename(wal_path))
            _copy_with_fallback(wal_path, dest)
            files += 1
            bytes_copied += os.path.getsize(dest)

        # SHM file
        shm_path = self.database_path + '-shm'
        if os.path.exists(shm_path):
            dest = os.path.join(db_backup_folder, os.path.basename(shm_path))
            _copy_with_fallback(shm_path, dest)
            files += 1
            bytes_copied += os.path.getsize(dest)

        return {
            'path': db_backup_folder,
            'files': files,
            'bytes': bytes_copied
        }

    def _backup_directory(self, source_dir: str, dest_dir: str, label: str) -> dict:
        """
        Backup a directory with progress reporting.

        Args:
            source_dir: Source directory path
            dest_dir: Destination directory path
            label: Label for progress messages

        Returns:
            Dictionary with files copied, bytes, and errors
        """
        files = 0
        bytes_copied = 0
        errors = []

        try:
            # Count total files first for progress
            total_files = sum(len(files_list) for _, _, files_list in os.walk(source_dir))
            self.status_update.emit(f"{label}: {total_files:,} files to copy")

            for root, dirs, filenames in os.walk(source_dir):
                if self._should_stop:
                    break

                # Calculate relative path
                rel_path = os.path.relpath(root, source_dir)
                target_dir = os.path.join(dest_dir, rel_path) if rel_path != '.' else dest_dir

                # Create target directory
                os.makedirs(target_dir, exist_ok=True)

                for filename in filenames:
                    if self._should_stop:
                        break

                    source_path = os.path.join(root, filename)
                    dest_path = os.path.join(target_dir, filename)

                    try:
                        try:
                            shutil.copy2(source_path, dest_path)
                        except OSError as e:
                            # Handle SMB/network shares that don't support chmod (errno 95)
                            if e.errno == 95:
                                logger.warning(f"copy2 failed (metadata not supported), using copyfile: {e}")
                                shutil.copyfile(source_path, dest_path)
                            else:
                                raise
                        file_size = os.path.getsize(dest_path)
                        files += 1
                        bytes_copied += file_size

                        # Report progress
                        if files % 100 == 0 or files == total_files:
                            self.progress_update.emit(files, total_files, filename)

                    except Exception as e:
                        error_msg = f"{source_path}: {str(e)}"
                        errors.append(error_msg)
                        logger.warning(f"Failed to copy: {error_msg}")

        except Exception as e:
            error_msg = f"Error walking directory {source_dir}: {str(e)}"
            errors.append(error_msg)
            logger.error(error_msg)

        return {
            'source_path': source_dir,
            'dest_path': dest_dir,
            'files': files,
            'bytes': bytes_copied,
            'errors': errors
        }
