"""
Path Resolver Module

Resolves relative paths to absolute paths using base locations from DatabaseMetadata.
This enables portable databases that work across different mount points and archive locations.

Schema v6 stores relative paths (e.g., '2024/01/15/photo.jpg') instead of absolute paths.
The PathResolver reconstructs full paths at runtime by joining base locations with relative paths.
"""

import os
import logging
from typing import Optional, Tuple, Dict, Any

logger = logging.getLogger(__name__)


class PathResolver:
    """
    Resolves relative paths to absolute using base locations from DatabaseMetadata.

    Supports multiple storage types:
    - 'archive': Main photo archive
    - 'video_archive': Separate video archive (if enabled)
    - 'prior_revision': Prior revision archive for edited/rotated originals

    Usage:
        from path_resolver import PathResolver
        from database_metadata import DatabaseMetadata

        db_metadata = DatabaseMetadata(database_path)
        resolver = PathResolver(db_metadata)

        # Convert relative to absolute
        abs_path = resolver.resolve('2024/01/15/photo.jpg', 'archive')

        # Convert absolute to relative
        rel_path, storage_type = resolver.make_relative('/mnt/photos/2024/01/15/photo.jpg')
    """

    # Storage type constants
    STORAGE_ARCHIVE = 'archive'
    STORAGE_VIDEO_ARCHIVE = 'video_archive'
    STORAGE_PRIOR_REVISION = 'prior_revision'
    STORAGE_UNKNOWN = 'unknown'

    # Valid storage types
    VALID_STORAGE_TYPES = {STORAGE_ARCHIVE, STORAGE_VIDEO_ARCHIVE, STORAGE_PRIOR_REVISION}

    def __init__(self, db_metadata: 'DatabaseMetadata'):
        """
        Initialize PathResolver with DatabaseMetadata instance.

        Args:
            db_metadata: DatabaseMetadata instance for accessing base locations
        """
        self.db_metadata = db_metadata
        self._cache: Dict[str, Optional[str]] = {}
        self._album_cache: Dict[int, Optional[str]] = {}

    def _get_base(self, storage_type: str) -> Optional[str]:
        """
        Get the base location for a storage type.

        Caches results to avoid repeated database queries.

        Args:
            storage_type: One of 'archive', 'video_archive', 'prior_revision'

        Returns:
            Base path for the storage type, or None if not configured
        """
        if storage_type in self._cache:
            return self._cache[storage_type]

        base = None
        if storage_type == self.STORAGE_ARCHIVE:
            base = self.db_metadata.get_archive_location()
        elif storage_type == self.STORAGE_VIDEO_ARCHIVE:
            base = self.db_metadata.get_video_archive_location()
        elif storage_type == self.STORAGE_PRIOR_REVISION:
            base = self.db_metadata.get_prior_revision_archive_location()

        self._cache[storage_type] = base
        return base

    def _get_album_storage(self, album_id: int) -> Optional[str]:
        """
        Get the storage location for an album.

        Args:
            album_id: Album ID

        Returns:
            Album storage location, or None if not found
        """
        if album_id in self._album_cache:
            return self._album_cache[album_id]

        # Import here to avoid circular imports
        from album_manager import AlbumManager
        album_manager = AlbumManager(self.db_metadata.database_path)
        album = album_manager.get_album(album_id)

        storage = album.get('storage_location') if album else None
        self._album_cache[album_id] = storage
        return storage

    def _get_delete_vault(self) -> Optional[str]:
        """
        Get the delete vault location.

        Returns:
            Delete vault path, or None if not configured
        """
        if 'delete_vault' in self._cache:
            return self._cache['delete_vault']

        vault = self.db_metadata.get_delete_vault_location()
        self._cache['delete_vault'] = vault
        return vault

    def invalidate_cache(self):
        """
        Clear the cached base locations.

        Call this after archive locations are changed.
        """
        self._cache.clear()
        self._album_cache.clear()
        logger.debug("PathResolver cache invalidated")

    def resolve(self, relative_path: str, storage_type: str) -> Optional[str]:
        """
        Convert relative path to absolute using appropriate base.

        Args:
            relative_path: Path relative to storage base (e.g., '2024/01/15/photo.jpg')
            storage_type: One of 'archive', 'video_archive', 'prior_revision'

        Returns:
            Absolute path, or None if base is not configured
        """
        if not relative_path:
            return None

        if storage_type not in self.VALID_STORAGE_TYPES:
            logger.warning(f"Unknown storage type: {storage_type}")
            return None

        base = self._get_base(storage_type)
        if not base:
            logger.debug(f"No base configured for storage type: {storage_type}")
            return None

        # Normalize the relative path (handle platform differences)
        normalized_rel = relative_path.replace('/', os.sep).replace('\\', os.sep)

        return os.path.join(base, normalized_rel)

    def make_relative(self, absolute_path: str) -> Tuple[Optional[str], str]:
        """
        Convert absolute path to (relative_path, storage_type) tuple.

        Checks bases in priority order:
        1. prior_revision (may be subdirectory of archive)
        2. video_archive
        3. archive

        Args:
            absolute_path: Full path to file

        Returns:
            Tuple of (relative_path, storage_type).
            Returns (None, 'unknown') if no matching base found.
        """
        if not absolute_path:
            return None, self.STORAGE_UNKNOWN

        # Normalize the input path
        norm_path = os.path.normpath(absolute_path)

        # Check bases in priority order (most specific first)
        # Prior revision may be a subdirectory, so check it first
        check_order = [
            self.STORAGE_PRIOR_REVISION,
            self.STORAGE_VIDEO_ARCHIVE,
            self.STORAGE_ARCHIVE
        ]

        for storage_type in check_order:
            base = self._get_base(storage_type)
            if not base:
                continue

            norm_base = os.path.normpath(base)

            # Check if path starts with this base
            if norm_path.startswith(norm_base + os.sep) or norm_path == norm_base:
                try:
                    relative = os.path.relpath(norm_path, norm_base)
                    # Normalize to forward slashes for storage (cross-platform)
                    relative = relative.replace(os.sep, '/')
                    return relative, storage_type
                except ValueError:
                    # Can happen on Windows with different drives
                    continue

        logger.debug(f"No matching base for path: {absolute_path}")
        return None, self.STORAGE_UNKNOWN

    def resolve_album(self, relative_path: str, album_id: int) -> Optional[str]:
        """
        Resolve relative path using album's storage_location.

        Args:
            relative_path: Path relative to album storage
            album_id: Album ID

        Returns:
            Absolute path, or None if album not found
        """
        if not relative_path:
            return None

        storage = self._get_album_storage(album_id)
        if not storage:
            logger.debug(f"No storage found for album: {album_id}")
            return None

        # Normalize the relative path
        normalized_rel = relative_path.replace('/', os.sep).replace('\\', os.sep)

        return os.path.join(storage, normalized_rel)

    def make_album_relative(self, absolute_path: str, album_id: int) -> Optional[str]:
        """
        Convert absolute album path to relative.

        Args:
            absolute_path: Full path in album storage
            album_id: Album ID

        Returns:
            Relative path, or None if not in album storage
        """
        if not absolute_path:
            return None

        storage = self._get_album_storage(album_id)
        if not storage:
            return None

        norm_path = os.path.normpath(absolute_path)
        norm_storage = os.path.normpath(storage)

        if norm_path.startswith(norm_storage + os.sep):
            try:
                relative = os.path.relpath(norm_path, norm_storage)
                # Normalize to forward slashes for storage
                return relative.replace(os.sep, '/')
            except ValueError:
                return None

        return None

    def resolve_vault(self, relative_path: str) -> Optional[str]:
        """
        Resolve relative path using delete vault location.

        Args:
            relative_path: Path relative to delete vault

        Returns:
            Absolute path, or None if vault not configured
        """
        if not relative_path:
            return None

        vault = self._get_delete_vault()
        if not vault:
            logger.debug("Delete vault not configured")
            return None

        # Normalize the relative path
        normalized_rel = relative_path.replace('/', os.sep).replace('\\', os.sep)

        return os.path.join(vault, normalized_rel)

    def make_vault_relative(self, absolute_path: str) -> Optional[str]:
        """
        Convert absolute vault path to relative.

        Args:
            absolute_path: Full path in delete vault

        Returns:
            Relative path, or None if not in vault
        """
        if not absolute_path:
            return None

        vault = self._get_delete_vault()
        if not vault:
            return None

        norm_path = os.path.normpath(absolute_path)
        norm_vault = os.path.normpath(vault)

        if norm_path.startswith(norm_vault + os.sep):
            try:
                relative = os.path.relpath(norm_path, norm_vault)
                # Normalize to forward slashes for storage
                return relative.replace(os.sep, '/')
            except ValueError:
                return None

        return None

    def get_storage_type_for_path(self, absolute_path: str) -> str:
        """
        Determine the storage type for an absolute path.

        Convenience method that returns just the storage type.

        Args:
            absolute_path: Full path to file

        Returns:
            Storage type string ('archive', 'video_archive', 'prior_revision', or 'unknown')
        """
        _, storage_type = self.make_relative(absolute_path)
        return storage_type

    def is_path_in_archive(self, absolute_path: str) -> bool:
        """
        Check if a path is within any of the managed archive locations.

        Args:
            absolute_path: Path to check

        Returns:
            True if path is in archive, video_archive, or prior_revision
        """
        storage_type = self.get_storage_type_for_path(absolute_path)
        return storage_type != self.STORAGE_UNKNOWN
