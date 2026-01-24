"""
Album Management Module

Handles album CRUD operations, photo management within albums,
and sync logic for archive deletions.
"""

import os
import shutil
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class AlbumStorageError(Exception):
    """Exception raised when album storage is unavailable or inaccessible."""
    pass


class AlbumManager:
    """Manages photo albums and their contents."""

    def __init__(self, database_path: str):
        """
        Initialize album manager with database path.

        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection with WAL mode and timeout.

        Returns:
            sqlite3.Connection with proper settings for concurrency
        """
        conn = sqlite3.connect(self.database_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.row_factory = sqlite3.Row
        return conn

    # =========================================================================
    # Album CRUD Operations
    # =========================================================================

    def create_album(self, name: str, storage_location: str,
                     description: str = "", sync_deletions: bool = True) -> Optional[int]:
        """
        Create a new album.

        Args:
            name: Unique album name
            storage_location: Absolute path to album folder
            description: Optional description
            sync_deletions: Whether to auto-remove when archive files deleted

        Returns:
            Album ID if successful, None otherwise

        Raises:
            ValueError: If name is empty or storage_location is not absolute
            AlbumStorageError: If storage location cannot be created or is not writable
        """
        logger.info("=" * 60)
        logger.info(f"CREATING ALBUM: {name}")
        logger.info(f"  Storage location: {storage_location}")
        logger.info("-" * 40)

        # Validate inputs
        if not name or not name.strip():
            raise ValueError("Album name cannot be empty")

        if not os.path.isabs(storage_location):
            raise ValueError("Storage location must be an absolute path")

        # Create storage directory if it doesn't exist
        try:
            if not os.path.exists(storage_location):
                os.makedirs(storage_location, exist_ok=True)
                logger.info(f"  Created storage directory: {storage_location}")
        except OSError as e:
            raise AlbumStorageError(f"Cannot create storage directory: {e}")

        # Verify storage is writable
        if not os.access(storage_location, os.W_OK):
            raise AlbumStorageError(f"Storage location is not writable: {storage_location}")

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO Albums (
                        album_name, album_description, storage_location,
                        created_timestamp, sync_deletions
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    name.strip(),
                    description.strip() if description else "",
                    storage_location,
                    datetime.now().isoformat(),
                    1 if sync_deletions else 0
                ))

                album_id = cursor.lastrowid
                conn.commit()

                logger.info(f"  Album created with ID: {album_id}")
                logger.info("=" * 60)
                return album_id

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                logger.error(f"  Album name already exists: {name}")
                return None
            raise
        except Exception as e:
            logger.error(f"  Failed to create album: {e}")
            return None

    def get_album(self, album_id: int) -> Optional[Dict[str, Any]]:
        """
        Get album details by ID.

        Args:
            album_id: Album ID to retrieve

        Returns:
            Dict with album details, or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM Albums WHERE id = ?
                """, (album_id,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Failed to get album {album_id}: {e}")
            return None

    def get_album_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get album details by name.

        Args:
            name: Album name to retrieve

        Returns:
            Dict with album details, or None if not found
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM Albums WHERE album_name = ?
                """, (name,))
                row = cursor.fetchone()

                if row:
                    return dict(row)
                return None

        except Exception as e:
            logger.error(f"Failed to get album '{name}': {e}")
            return None

    def get_all_albums(self, include_inactive: bool = False) -> List[Dict[str, Any]]:
        """
        Get all albums.

        Args:
            include_inactive: Whether to include inactive albums

        Returns:
            List of album dicts
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                if include_inactive:
                    cursor.execute("""
                        SELECT * FROM Albums ORDER BY sort_order, album_name
                    """)
                else:
                    cursor.execute("""
                        SELECT * FROM Albums WHERE is_active = 1
                        ORDER BY sort_order, album_name
                    """)

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get albums: {e}")
            return []

    def update_album(self, album_id: int, name: str = None,
                     description: str = None, storage_location: str = None,
                     sync_deletions: bool = None) -> bool:
        """
        Update album properties.

        Args:
            album_id: Album ID to update
            name: New name (optional)
            description: New description (optional)
            storage_location: New storage location (optional)
            sync_deletions: New sync setting (optional)

        Returns:
            True if successful, False otherwise
        """
        updates = []
        params = []

        if name is not None:
            if not name.strip():
                logger.error("Album name cannot be empty")
                return False
            updates.append("album_name = ?")
            params.append(name.strip())

        if description is not None:
            updates.append("album_description = ?")
            params.append(description.strip())

        if storage_location is not None:
            if not os.path.isabs(storage_location):
                logger.error("Storage location must be absolute path")
                return False
            updates.append("storage_location = ?")
            params.append(storage_location)

        if sync_deletions is not None:
            updates.append("sync_deletions = ?")
            params.append(1 if sync_deletions else 0)

        if not updates:
            return True  # Nothing to update

        updates.append("updated_timestamp = ?")
        params.append(datetime.now().isoformat())
        params.append(album_id)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    UPDATE Albums SET {', '.join(updates)}
                    WHERE id = ?
                """, params)
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Album {album_id} updated successfully")
                    return True
                else:
                    logger.warning(f"Album {album_id} not found")
                    return False

        except sqlite3.IntegrityError as e:
            if "UNIQUE constraint" in str(e):
                logger.error(f"Album name already exists")
            return False
        except Exception as e:
            logger.error(f"Failed to update album {album_id}: {e}")
            return False

    def delete_album(self, album_id: int, delete_files: bool = True) -> bool:
        """
        Delete album and optionally its files.

        Args:
            album_id: Album to delete
            delete_files: If True, delete physical files from storage location

        Returns:
            True if successful, False otherwise
        """
        logger.info("=" * 60)
        logger.info(f"DELETING ALBUM: ID {album_id}")
        logger.info(f"  Delete files: {delete_files}")
        logger.info("-" * 40)

        try:
            album = self.get_album(album_id)
            if not album:
                logger.error(f"  Album {album_id} not found")
                return False

            storage_location = album['storage_location']

            if delete_files and os.path.exists(storage_location):
                # Get all album files first
                photos = self.get_album_photos(album_id)

                for photo in photos:
                    album_path = photo.get('album_file_path')
                    if album_path and os.path.exists(album_path):
                        try:
                            os.remove(album_path)
                            logger.info(f"  Deleted: {os.path.basename(album_path)}")
                        except OSError as e:
                            logger.warning(f"  Could not delete {album_path}: {e}")

                # Try to remove directory if empty
                try:
                    if os.path.exists(storage_location) and not os.listdir(storage_location):
                        os.rmdir(storage_location)
                        logger.info(f"  Removed empty directory: {storage_location}")
                except OSError:
                    pass  # Directory not empty or other error

            # Delete from database (CASCADE will delete AlbumPhotos)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM Albums WHERE id = ?", (album_id,))
                conn.commit()

                logger.info(f"  Album deleted from database")
                logger.info("=" * 60)
                return True

        except Exception as e:
            logger.error(f"  Failed to delete album: {e}")
            return False

    def rename_album(self, album_id: int, new_name: str) -> bool:
        """
        Rename an album (database name only, not folder).

        Args:
            album_id: Album ID to rename
            new_name: New album name

        Returns:
            True if successful, False otherwise
        """
        return self.update_album(album_id, name=new_name)

    # =========================================================================
    # Photo Management
    # =========================================================================

    def add_photo_to_album(self, album_id: int, file_hash: str,
                           archive_path: str) -> Optional[str]:
        """
        Add a single photo to an album (copies file to album storage).

        Args:
            album_id: Target album ID
            file_hash: SHA-256 hash of the file
            archive_path: Path to file in archive

        Returns:
            Album file path if successful, None otherwise
        """
        album = self.get_album(album_id)
        if not album:
            logger.error(f"Album {album_id} not found")
            return None

        storage_location = album['storage_location']

        # Verify storage is available
        if not os.path.exists(storage_location):
            try:
                os.makedirs(storage_location, exist_ok=True)
            except OSError as e:
                logger.error(f"Cannot create album storage: {e}")
                return None

        if not os.access(storage_location, os.W_OK):
            logger.error(f"Album storage not writable: {storage_location}")
            return None

        # Verify source file exists
        if not os.path.exists(archive_path):
            logger.error(f"Source file not found: {archive_path}")
            return None

        # Check if already in album
        if self.is_photo_in_album(album_id, file_hash):
            logger.debug(f"Photo already in album: {file_hash[:8]}...")
            return None

        # Generate unique filename for flat structure
        original_filename = os.path.basename(archive_path)
        album_file_path = self._generate_album_filename(
            storage_location, original_filename, file_hash
        )

        try:
            # Copy file with metadata preservation
            old_size = os.path.getsize(archive_path)
            try:
                shutil.copy2(archive_path, album_file_path)
            except OSError as e:
                # Handle SMB/network shares that don't support chmod (errno 95)
                if e.errno == 95:
                    logger.warning(f"copy2 failed (metadata not supported on destination), using copyfile: {e}")
                    shutil.copyfile(archive_path, album_file_path)
                else:
                    raise

            # Verify copy
            if not os.path.exists(album_file_path):
                raise IOError("Copy verification failed - file not found")

            new_size = os.path.getsize(album_file_path)
            if old_size != new_size:
                os.remove(album_file_path)
                raise IOError(f"Size mismatch: {old_size} vs {new_size}")

            # Insert database record
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Schema v6: Calculate relative path for portable storage
                relative_album_path = None
                try:
                    relative_album_path = os.path.relpath(album_file_path, storage_location)
                    # Normalize to forward slashes for cross-platform storage
                    relative_album_path = relative_album_path.replace(os.sep, '/')
                except ValueError:
                    # Different drives on Windows - just store None
                    pass

                cursor.execute("""
                    INSERT INTO AlbumPhotos (
                        album_id, file_hash, album_file_path, added_timestamp, relative_album_path
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    album_id,
                    file_hash,
                    album_file_path,
                    datetime.now().isoformat(),
                    relative_album_path
                ))
                conn.commit()

            # Update album stats
            self._update_album_stats(album_id)

            return album_file_path

        except Exception as e:
            logger.error(f"Failed to add photo to album: {e}")
            # Clean up partial copy
            if os.path.exists(album_file_path):
                try:
                    os.remove(album_file_path)
                except OSError:
                    pass
            return None

    def remove_photo_from_album(self, album_id: int, file_hash: str,
                                delete_file: bool = True) -> bool:
        """
        Remove a single photo from an album.

        Args:
            album_id: Album ID
            file_hash: Hash of file to remove
            delete_file: If True, delete physical file from album folder

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get album file path first
                cursor.execute("""
                    SELECT album_file_path FROM AlbumPhotos
                    WHERE album_id = ? AND file_hash = ?
                """, (album_id, file_hash))
                row = cursor.fetchone()

                if not row:
                    logger.warning(f"Photo not in album: {file_hash[:8]}...")
                    return False

                album_file_path = row['album_file_path']

                # Delete physical file if requested
                if delete_file and album_file_path and os.path.exists(album_file_path):
                    try:
                        os.remove(album_file_path)
                        logger.debug(f"Deleted album file: {album_file_path}")
                    except OSError as e:
                        logger.warning(f"Could not delete album file: {e}")

                # Delete database record
                cursor.execute("""
                    DELETE FROM AlbumPhotos
                    WHERE album_id = ? AND file_hash = ?
                """, (album_id, file_hash))
                conn.commit()

            # Update album stats
            self._update_album_stats(album_id)

            return True

        except Exception as e:
            logger.error(f"Failed to remove photo from album: {e}")
            return False

    def get_album_photos(self, album_id: int) -> List[Dict[str, Any]]:
        """
        Get all photos in an album with their details.

        Args:
            album_id: Album ID

        Returns:
            List of dicts with photo details including archive info
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT
                        ap.id,
                        ap.album_id,
                        ap.file_hash,
                        ap.album_file_path,
                        ap.added_timestamp,
                        ap.display_order,
                        up.file_name as archive_path,
                        up.source_path,
                        up.create_year,
                        up.create_month,
                        up.create_day,
                        up.file_size
                    FROM AlbumPhotos ap
                    LEFT JOIN UniquePhotos up ON ap.file_hash = up.file_hash
                    WHERE ap.album_id = ?
                    ORDER BY ap.display_order, ap.added_timestamp
                """, (album_id,))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get album photos: {e}")
            return []

    def is_photo_in_album(self, album_id: int, file_hash: str) -> bool:
        """
        Check if a photo is in a specific album.

        Args:
            album_id: Album ID
            file_hash: File hash to check

        Returns:
            True if photo is in album, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT COUNT(*) FROM AlbumPhotos
                    WHERE album_id = ? AND file_hash = ?
                """, (album_id, file_hash))
                return cursor.fetchone()[0] > 0

        except Exception as e:
            logger.error(f"Failed to check photo in album: {e}")
            return False

    def get_albums_containing_photo(self, file_hash: str) -> List[Dict[str, Any]]:
        """
        Get all albums that contain a specific photo.

        Args:
            file_hash: Hash of the file

        Returns:
            List of album dicts
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT a.* FROM Albums a
                    JOIN AlbumPhotos ap ON a.id = ap.album_id
                    WHERE ap.file_hash = ?
                    ORDER BY a.album_name
                """, (file_hash,))

                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get albums containing photo: {e}")
            return []

    # =========================================================================
    # Sync Operations
    # =========================================================================

    def sync_deletion_to_albums(self, file_hash: str) -> Dict[str, Any]:
        """
        Called when a photo is deleted from archive.
        Removes photo from all albums with sync_deletions=1.

        Args:
            file_hash: Hash of deleted file

        Returns:
            Dict with 'albums_updated': list of album names,
            'files_removed': count
        """
        result = {
            'albums_updated': [],
            'files_removed': 0
        }

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Find all albums containing this photo that have sync enabled
                cursor.execute("""
                    SELECT a.id, a.album_name, ap.album_file_path
                    FROM Albums a
                    JOIN AlbumPhotos ap ON a.id = ap.album_id
                    WHERE ap.file_hash = ? AND a.sync_deletions = 1
                """, (file_hash,))

                rows = cursor.fetchall()

                for row in rows:
                    album_id = row['id']
                    album_name = row['album_name']
                    album_file_path = row['album_file_path']

                    # Delete physical file
                    if album_file_path and os.path.exists(album_file_path):
                        try:
                            os.remove(album_file_path)
                            result['files_removed'] += 1
                        except OSError as e:
                            logger.warning(f"Could not delete {album_file_path}: {e}")

                    # Delete database record
                    cursor.execute("""
                        DELETE FROM AlbumPhotos
                        WHERE album_id = ? AND file_hash = ?
                    """, (album_id, file_hash))

                    result['albums_updated'].append(album_name)

                    # Update album stats
                    self._update_album_stats(album_id)

                conn.commit()

            if result['albums_updated']:
                logger.info(f"Synced deletion to albums: {', '.join(result['albums_updated'])}")

            return result

        except Exception as e:
            logger.error(f"Failed to sync deletion to albums: {e}")
            return result

    def verify_album_storage(self, album_id: int) -> Dict[str, Any]:
        """
        Verify album storage is accessible and consistent.

        Args:
            album_id: Album ID to verify

        Returns:
            Dict with 'status': 'ok'|'unavailable'|'inconsistent',
            'missing_files': list, 'orphan_files': list
        """
        result = {
            'status': 'ok',
            'missing_files': [],
            'orphan_files': [],
            'total_files': 0,
            'total_size': 0
        }

        album = self.get_album(album_id)
        if not album:
            result['status'] = 'not_found'
            return result

        storage_location = album['storage_location']

        # Check if storage exists
        if not os.path.exists(storage_location):
            result['status'] = 'unavailable'
            return result

        # Get database records
        photos = self.get_album_photos(album_id)
        db_files = {p['album_file_path'] for p in photos if p.get('album_file_path')}

        # Get actual files in storage
        try:
            actual_files = set()
            for f in os.listdir(storage_location):
                full_path = os.path.join(storage_location, f)
                if os.path.isfile(full_path):
                    actual_files.add(full_path)
                    result['total_files'] += 1
                    result['total_size'] += os.path.getsize(full_path)
        except OSError as e:
            result['status'] = 'unavailable'
            result['error'] = str(e)
            return result

        # Find missing files (in DB but not on disk)
        result['missing_files'] = list(db_files - actual_files)

        # Find orphan files (on disk but not in DB)
        result['orphan_files'] = list(actual_files - db_files)

        if result['missing_files'] or result['orphan_files']:
            result['status'] = 'inconsistent'

        return result

    def set_album_active(self, album_id: int, is_active: bool) -> bool:
        """
        Set album active status.

        Args:
            album_id: Album ID
            is_active: True for active, False for inactive

        Returns:
            True if successful, False otherwise
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Albums SET is_active = ?, updated_timestamp = ?
                    WHERE id = ?
                """, (1 if is_active else 0, datetime.now().isoformat(), album_id))
                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Failed to set album active status: {e}")
            return False

    # =========================================================================
    # Utility Methods
    # =========================================================================

    def _generate_album_filename(self, storage_location: str,
                                 original_filename: str, file_hash: str) -> str:
        """
        Generate unique filename for album storage (flat structure).

        Handles collisions by appending hash suffix and counter.

        Args:
            storage_location: Album storage folder
            original_filename: Original filename from archive
            file_hash: SHA-256 hash of the file

        Returns:
            Full path to unique filename in album storage
        """
        base, ext = os.path.splitext(original_filename)
        target_path = os.path.join(storage_location, original_filename)

        # If no collision, use original name
        if not os.path.exists(target_path):
            return target_path

        # Add hash suffix (first 8 chars)
        hash_suffix = file_hash[:8]
        new_filename = f"{base}_{hash_suffix}{ext}"
        target_path = os.path.join(storage_location, new_filename)

        if not os.path.exists(target_path):
            return target_path

        # Add counter if still collision
        counter = 1
        while os.path.exists(target_path):
            new_filename = f"{base}_{hash_suffix}_{counter}{ext}"
            target_path = os.path.join(storage_location, new_filename)
            counter += 1

        return target_path

    def _update_album_stats(self, album_id: int):
        """
        Update photo_count and total_size_bytes for album.

        Args:
            album_id: Album ID to update
        """
        try:
            photos = self.get_album_photos(album_id)

            photo_count = len(photos)
            total_size = 0

            for photo in photos:
                album_path = photo.get('album_file_path')
                if album_path and os.path.exists(album_path):
                    try:
                        total_size += os.path.getsize(album_path)
                    except OSError:
                        pass

            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE Albums
                    SET photo_count = ?, total_size_bytes = ?, updated_timestamp = ?
                    WHERE id = ?
                """, (photo_count, total_size, datetime.now().isoformat(), album_id))
                conn.commit()

        except Exception as e:
            logger.error(f"Failed to update album stats: {e}")
