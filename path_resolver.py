"""
Path Resolver Module

Resolves relative paths to absolute paths using base locations from DatabaseMetadata.
This enables portable databases that work across different mount points and archive locations.

Schema v6 stores relative paths (e.g., '2024/01/15/photo.jpg') instead of absolute paths.
The PathResolver reconstructs full paths at runtime by joining base locations with relative paths.

Also provides path sanitization and validation utilities to handle special characters
and prevent path traversal attacks.

Supports both direct filesystem access (via DatabaseMetadata) and cloud storage
(via StorageBackend) for flexible storage configurations.
"""

import os
import logging
import re
import unicodedata
from typing import Optional, Tuple, Dict, Any, List, TYPE_CHECKING

if TYPE_CHECKING:
    from storage_backend import StorageManager, StorageBackend

logger = logging.getLogger(__name__)


# ============================================================================
# Path Sanitization and Validation Utilities
# ============================================================================

# Characters that are problematic in file paths across platforms
DANGEROUS_CHARS = ['..', '\x00']  # Directory traversal and null byte

# Characters that may cause issues on specific platforms
WINDOWS_RESERVED = ['<', '>', ':', '"', '|', '?', '*']
WINDOWS_RESERVED_NAMES = [
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
]


class PathValidationError(Exception):
    """Raised when path validation fails."""
    pass


def validate_path(path: str, allow_absolute: bool = True) -> Tuple[bool, Optional[str]]:
    """
    Validate a file path for safety and correctness.

    Checks for:
    - Directory traversal attempts (..)
    - Null byte injection
    - Empty paths
    - Excessively long paths

    Parameters:
        path (str): The path to validate
        allow_absolute (bool): Whether absolute paths are allowed (default: True)

    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
            - is_valid: True if path is safe, False otherwise
            - error_message: Description of issue if invalid, None if valid
    """
    if not path:
        return (False, "Path is empty")

    if path.strip() != path:
        return (False, "Path contains leading or trailing whitespace")

    # Check for null bytes (common injection attack)
    if '\x00' in path:
        return (False, "Path contains null byte (potential injection attack)")

    # Check for directory traversal
    # Normalize and check for .. components
    normalized = os.path.normpath(path)
    if '..' in normalized.split(os.sep):
        return (False, "Path contains directory traversal (..) which is not allowed")

    # Check path length (Windows max is 260, but extended-length paths can be longer)
    if len(path) > 32767:  # Windows extended-length path limit
        return (False, f"Path exceeds maximum length of 32767 characters")

    # Check for absolute path if not allowed
    if not allow_absolute and os.path.isabs(path):
        return (False, "Absolute paths are not allowed")

    return (True, None)


def sanitize_path_for_database(path: str) -> str:
    """
    Sanitize a path for safe storage and retrieval from database.

    This handles special characters like apostrophes that can cause SQL issues
    if parameterized queries are not used properly (defense in depth).

    Note: This function does NOT escape SQL - always use parameterized queries!
    This is a defense-in-depth measure for path normalization.

    Parameters:
        path (str): The path to sanitize

    Returns:
        str: Normalized path safe for storage
    """
    if not path:
        return path

    # Normalize Unicode characters (decompose and recompose)
    # This ensures consistent representation of accented characters
    normalized = unicodedata.normalize('NFC', path)

    # Replace backslashes with forward slashes for consistent storage
    # (will be converted back to platform-specific separator on retrieval)
    normalized = normalized.replace('\\', '/')

    # Remove duplicate slashes
    while '//' in normalized:
        normalized = normalized.replace('//', '/')

    # Strip trailing slashes (except for root)
    if len(normalized) > 1:
        normalized = normalized.rstrip('/')

    return normalized


def sanitize_filename(filename: str, replacement: str = '_') -> str:
    """
    Sanitize a filename by replacing or removing problematic characters.

    Handles:
    - Windows reserved characters (< > : " | ? *)
    - Control characters
    - Leading/trailing spaces and dots
    - Reserved Windows names (CON, PRN, etc.)

    Parameters:
        filename (str): The filename to sanitize
        replacement (str): Character to replace invalid chars with (default: '_')

    Returns:
        str: Sanitized filename safe for all platforms
    """
    if not filename:
        return filename

    # Normalize Unicode
    result = unicodedata.normalize('NFC', filename)

    # Replace Windows reserved characters
    for char in WINDOWS_RESERVED:
        result = result.replace(char, replacement)

    # Remove control characters (0x00-0x1F and 0x7F)
    result = ''.join(char for char in result if ord(char) >= 32 and ord(char) != 127)

    # Remove leading/trailing dots and spaces
    result = result.strip('. ')

    # Check for Windows reserved names
    name_without_ext = result.split('.')[0].upper()
    if name_without_ext in WINDOWS_RESERVED_NAMES:
        result = replacement + result

    # Ensure filename is not empty after sanitization
    if not result:
        result = 'unnamed'

    return result


def is_path_safe_for_sql(path: str) -> bool:
    """
    Check if a path is safe for use in SQL queries.

    Note: Always use parameterized queries! This is a defense-in-depth check.

    Parameters:
        path (str): The path to check

    Returns:
        bool: True if path appears safe, False if it contains suspicious patterns
    """
    if not path:
        return True

    # Check for SQL injection patterns (this is defense-in-depth)
    suspicious_patterns = [
        "';", '";',  # Statement termination
        '--',        # SQL comment
        '/*',        # Multi-line comment start
        'UNION',     # UNION injection
        'SELECT',    # SELECT injection
        'DROP',      # DROP injection
        'DELETE',    # DELETE injection
        'INSERT',    # INSERT injection
        'UPDATE',    # UPDATE injection
    ]

    upper_path = path.upper()
    for pattern in suspicious_patterns:
        if pattern in upper_path:
            logger.warning(f"Suspicious pattern '{pattern}' found in path: {path}")
            return False

    return True


def normalize_path_separators(path: str) -> str:
    """
    Normalize path separators to the current platform's separator.

    Parameters:
        path (str): Path with mixed separators

    Returns:
        str: Path with consistent separators for current platform
    """
    if not path:
        return path

    # Replace all separators with current platform separator
    normalized = path.replace('/', os.sep).replace('\\', os.sep)

    # Remove duplicate separators
    while os.sep + os.sep in normalized:
        normalized = normalized.replace(os.sep + os.sep, os.sep)

    return normalized


def escape_path_for_glob(path: str) -> str:
    """
    Escape special glob characters in a path for literal matching.

    Parameters:
        path (str): Path that may contain glob special characters

    Returns:
        str: Path with glob special characters escaped
    """
    # Glob special characters: * ? [ ]
    special_chars = ['*', '?', '[', ']']
    result = path
    for char in special_chars:
        result = result.replace(char, f'[{char}]')
    return result


def get_safe_path_for_display(path: str, max_length: int = 100) -> str:
    """
    Get a safe, truncated version of a path for display purposes.

    Truncates from the middle to preserve both the beginning (drive/root)
    and the end (filename).

    Parameters:
        path (str): The full path
        max_length (int): Maximum display length (default: 100)

    Returns:
        str: Truncated path safe for display
    """
    if not path or len(path) <= max_length:
        return path

    # Keep the first part and the last part, replace middle with ...
    ellipsis = '...'
    available = max_length - len(ellipsis)
    front = available // 2
    back = available - front

    return path[:front] + ellipsis + path[-back:]


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


class StorageBackendResolver:
    """
    Cloud-aware path resolver using StorageManager backends.

    This class provides the same interface as PathResolver but uses
    StorageBackend instances for file operations, enabling cloud storage support.

    Usage:
        from path_resolver import StorageBackendResolver
        from storage_backend import StorageManager

        storage_config = {
            'archive': {'type': 'local', 'path': '/archive'},
            'video_archive': {'type': 's3', 'bucket': 'videos', ...}
        }
        manager = StorageManager(storage_config)
        resolver = StorageBackendResolver(manager)

        # Get backend for a storage type
        backend = resolver.get_backend('archive')
        if backend.exists('2024/01/photo.jpg'):
            data = backend.read_file('2024/01/photo.jpg')
    """

    # Storage type constants (mirror PathResolver)
    STORAGE_ARCHIVE = 'archive'
    STORAGE_VIDEO_ARCHIVE = 'video_archive'
    STORAGE_PRIOR_REVISION = 'prior_revision'
    STORAGE_DELETE_VAULT = 'delete_vault'
    STORAGE_UNKNOWN = 'unknown'

    VALID_STORAGE_TYPES = {
        STORAGE_ARCHIVE, STORAGE_VIDEO_ARCHIVE,
        STORAGE_PRIOR_REVISION, STORAGE_DELETE_VAULT
    }

    def __init__(self, storage_manager: 'StorageManager'):
        """
        Initialize with a StorageManager instance.

        Args:
            storage_manager: StorageManager with configured backends
        """
        self.storage_manager = storage_manager

    def get_backend(self, storage_type: str) -> Optional['StorageBackend']:
        """
        Get the storage backend for a given storage type.

        Args:
            storage_type: One of 'archive', 'video_archive', 'prior_revision', 'delete_vault'

        Returns:
            StorageBackend instance or None if not configured
        """
        return self.storage_manager.get_backend(storage_type)

    def resolve(self, relative_path: str, storage_type: str) -> Optional[str]:
        """
        Convert relative path to full path for the storage backend.

        For local storage, returns absolute filesystem path.
        For cloud storage, returns the full URI (e.g., s3://bucket/path).

        Args:
            relative_path: Path relative to storage base
            storage_type: Storage type identifier

        Returns:
            Full resolved path, or None if backend not configured
        """
        backend = self.get_backend(storage_type)
        if not backend:
            return None

        return backend.resolve_path(relative_path)

    def exists(self, relative_path: str, storage_type: str) -> bool:
        """
        Check if a file exists in the specified storage.

        Args:
            relative_path: Path relative to storage base
            storage_type: Storage type identifier

        Returns:
            True if file exists
        """
        backend = self.get_backend(storage_type)
        if not backend:
            return False

        return backend.exists(relative_path)

    def get_storage_type(self, storage_type: str) -> str:
        """
        Get the backend type (local, s3, azure, etc.) for a storage type.

        Args:
            storage_type: Storage type identifier (archive, video_archive, etc.)

        Returns:
            Backend type string or 'unknown' if not configured
        """
        backend = self.get_backend(storage_type)
        if not backend:
            return self.STORAGE_UNKNOWN

        return backend.storage_type

    def is_cloud_storage(self, storage_type: str) -> bool:
        """
        Check if a storage type uses cloud backend.

        Args:
            storage_type: Storage type identifier

        Returns:
            True if storage uses cloud backend (s3, azure, gcs, etc.)
        """
        backend_type = self.get_storage_type(storage_type)
        return backend_type not in ('local', self.STORAGE_UNKNOWN)

    def get_configured_vaults(self) -> List[str]:
        """
        Get list of configured vault types.

        Returns:
            List of storage type strings that are configured
        """
        return self.storage_manager.configured_vaults

    def copy_to_storage(self, local_path: str, relative_path: str,
                        storage_type: str, verify: bool = True) -> bool:
        """
        Copy a local file to storage.

        Args:
            local_path: Absolute path to local source file
            relative_path: Destination path relative to storage base
            storage_type: Target storage type
            verify: If True, verify integrity after copy

        Returns:
            True if copy successful
        """
        backend = self.get_backend(storage_type)
        if not backend:
            logger.error(f"No backend configured for storage type: {storage_type}")
            return False

        try:
            result = backend.copy_from_local(local_path, relative_path)

            if result and verify:
                # Verify file exists and has content
                if not backend.exists(relative_path):
                    logger.error(f"Verification failed: file not found after copy: {relative_path}")
                    return False

            return result

        except Exception as e:
            logger.error(f"Failed to copy to storage: {e}")
            return False

    def copy_from_storage(self, relative_path: str, local_path: str,
                          storage_type: str) -> bool:
        """
        Copy a file from storage to local filesystem.

        Args:
            relative_path: Source path relative to storage base
            local_path: Absolute destination path on local filesystem
            storage_type: Source storage type

        Returns:
            True if copy successful
        """
        backend = self.get_backend(storage_type)
        if not backend:
            logger.error(f"No backend configured for storage type: {storage_type}")
            return False

        try:
            return backend.copy_to_local(relative_path, local_path)
        except Exception as e:
            logger.error(f"Failed to copy from storage: {e}")
            return False

    def delete_from_storage(self, relative_path: str, storage_type: str) -> bool:
        """
        Delete a file from storage.

        Args:
            relative_path: Path relative to storage base
            storage_type: Storage type identifier

        Returns:
            True if deleted (or didn't exist), False on error
        """
        backend = self.get_backend(storage_type)
        if not backend:
            logger.error(f"No backend configured for storage type: {storage_type}")
            return False

        try:
            return backend.delete(relative_path)
        except Exception as e:
            logger.error(f"Failed to delete from storage: {e}")
            return False

    def verify_integrity(self, relative_path: str, expected_hash: str,
                        storage_type: str, full_verify: bool = False) -> bool:
        """
        Verify file integrity in storage.

        Args:
            relative_path: Path relative to storage base
            expected_hash: Expected SHA-256 hash
            storage_type: Storage type identifier
            full_verify: If True, compute full hash; if False, use partial

        Returns:
            True if hash matches
        """
        backend = self.get_backend(storage_type)
        if not backend:
            return False

        return backend.verify_integrity(relative_path, expected_hash, full_verify)


def create_resolver_from_config(config: 'Config') -> StorageBackendResolver:
    """
    Create a StorageBackendResolver from a Config instance.

    This is a convenience function for creating a cloud-aware resolver
    from application configuration.

    Args:
        config: Config instance with storage configuration

    Returns:
        StorageBackendResolver ready for use
    """
    storage_manager = config.create_storage_manager()
    return StorageBackendResolver(storage_manager)
