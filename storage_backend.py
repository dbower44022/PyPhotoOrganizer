"""
Storage Backend Abstraction Layer for PyPhotoOrganizer.

Provides a unified interface for file operations across different storage types
(local filesystem, S3, Azure Blob, etc.).

This module implements Phase 1 of the cloud storage integration plan.
"""

import hashlib
import logging
import os
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, BinaryIO, Dict, Iterator, Optional, Tuple

import constants

logger = logging.getLogger(__name__)


@dataclass
class FileInfo:
    """Metadata about a file in storage."""
    path: str
    size: int
    modified_time: datetime
    content_hash: Optional[str] = None  # SHA-256 or provider-specific hash
    storage_type: str = 'local'  # 'local', 's3', 'azure', 'gcs'

    def __repr__(self) -> str:
        return f"FileInfo(path='{self.path}', size={self.size}, storage='{self.storage_type}')"


class StorageBackend(ABC):
    """
    Abstract interface for storage operations.

    All file operations in the application should go through this interface
    to enable support for different storage backends (local, cloud, etc.).
    """

    @property
    @abstractmethod
    def storage_type(self) -> str:
        """Return the storage type identifier (e.g., 'local', 's3', 'azure')."""
        pass

    @property
    @abstractmethod
    def base_path(self) -> str:
        """Return the base path/bucket/container for this backend."""
        pass

    @abstractmethod
    def exists(self, path: str) -> bool:
        """
        Check if file exists at the given path.

        Args:
            path: Relative path within this storage backend

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    def get_size(self, path: str) -> int:
        """
        Get file size in bytes.

        Args:
            path: Relative path within this storage backend

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def get_file_info(self, path: str) -> Optional[FileInfo]:
        """
        Get file metadata.

        Args:
            path: Relative path within this storage backend

        Returns:
            FileInfo object with metadata, or None if file doesn't exist
        """
        pass

    @abstractmethod
    def read_file(self, path: str) -> bytes:
        """
        Read entire file into memory.

        Warning: Use only for small files. For large files, use read_file_stream().

        Args:
            path: Relative path within this storage backend

        Returns:
            File contents as bytes

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def read_file_stream(self, path: str) -> BinaryIO:
        """
        Get file as a readable binary stream.

        Args:
            path: Relative path within this storage backend

        Returns:
            Binary file-like object

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def write_file(self, path: str, data: bytes) -> bool:
        """
        Write data to file.

        Args:
            path: Relative path within this storage backend
            data: Bytes to write

        Returns:
            True if successful

        Raises:
            IOError: If write fails
        """
        pass

    @abstractmethod
    def write_file_stream(self, path: str, stream: BinaryIO, size: int) -> bool:
        """
        Write stream to file with known size.

        Args:
            path: Relative path within this storage backend
            stream: Binary file-like object to read from
            size: Expected size of the data

        Returns:
            True if successful

        Raises:
            IOError: If write fails
        """
        pass

    @abstractmethod
    def copy_from_local(self, local_path: str, remote_path: str,
                        preserve_metadata: bool = True) -> bool:
        """
        Upload/copy a local file to this storage backend.

        Args:
            local_path: Absolute path to local file
            remote_path: Relative path within this storage backend
            preserve_metadata: Whether to preserve file timestamps (local only)

        Returns:
            True if successful

        Raises:
            FileNotFoundError: If local file doesn't exist
            IOError: If copy fails
        """
        pass

    @abstractmethod
    def copy_to_local(self, remote_path: str, local_path: str) -> bool:
        """
        Download/copy a file from this storage backend to local filesystem.

        Args:
            remote_path: Relative path within this storage backend
            local_path: Absolute path for local destination

        Returns:
            True if successful

        Raises:
            FileNotFoundError: If remote file doesn't exist
            IOError: If copy fails
        """
        pass

    @abstractmethod
    def copy(self, source: str, dest: str) -> bool:
        """
        Copy file within the same storage backend.

        Args:
            source: Relative source path
            dest: Relative destination path

        Returns:
            True if successful

        Raises:
            FileNotFoundError: If source doesn't exist
            IOError: If copy fails
        """
        pass

    @abstractmethod
    def move(self, source: str, dest: str) -> bool:
        """
        Move file within the same storage backend.

        Args:
            source: Relative source path
            dest: Relative destination path

        Returns:
            True if successful

        Raises:
            FileNotFoundError: If source doesn't exist
            IOError: If move fails
        """
        pass

    @abstractmethod
    def delete(self, path: str) -> bool:
        """
        Delete file.

        Args:
            path: Relative path within this storage backend

        Returns:
            True if successful, False if file didn't exist

        Raises:
            IOError: If delete fails for reason other than non-existence
        """
        pass

    @abstractmethod
    def makedirs(self, path: str) -> bool:
        """
        Create directory structure.

        For object storage (S3, etc.), this is typically a no-op since
        directories don't exist as separate entities.

        Args:
            path: Relative directory path

        Returns:
            True if successful or already exists
        """
        pass

    @abstractmethod
    def list_files(self, prefix: str = '') -> Iterator[FileInfo]:
        """
        List files with the given prefix.

        Args:
            prefix: Path prefix to filter by (empty for all files)

        Yields:
            FileInfo objects for each matching file
        """
        pass

    @abstractmethod
    def compute_hash(self, path: str, algorithm: str = 'sha256') -> str:
        """
        Compute hash of file contents.

        Args:
            path: Relative path within this storage backend
            algorithm: Hash algorithm ('sha256', 'md5', etc.)

        Returns:
            Hex-encoded hash string

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        pass

    def compute_partial_hash(self, path: str, num_bytes: int = None) -> str:
        """
        Compute partial hash for quick duplicate detection.

        Reads first N bytes and last N bytes of file.

        Args:
            path: Relative path within this storage backend
            num_bytes: Bytes to read from start and end (default from constants)

        Returns:
            Hex-encoded SHA-256 hash of partial content

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        if num_bytes is None:
            num_bytes = constants.PARTIAL_HASH_BYTES

        file_info = self.get_file_info(path)
        if file_info is None:
            raise FileNotFoundError(f"File not found: {path}")

        if file_info.size <= num_bytes * 2:
            # File is small enough to hash entirely
            return self.compute_hash(path)

        # Read first and last chunks
        first_chunk = self.read_range(path, 0, num_bytes)
        last_chunk = self.read_range(path, file_info.size - num_bytes, num_bytes)

        hasher = hashlib.sha256()
        hasher.update(first_chunk)
        hasher.update(last_chunk)
        return hasher.hexdigest()

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        """
        Read a range of bytes from file.

        Default implementation reads full file (inefficient for large files).
        Cloud backends should override with range requests.

        Args:
            path: Relative path within this storage backend
            offset: Byte offset to start reading (negative for from end)
            length: Number of bytes to read

        Returns:
            Bytes from the specified range
        """
        data = self.read_file(path)
        if offset < 0:
            return data[offset:offset + length] if offset + length < 0 else data[offset:]
        return data[offset:offset + length]

    def resolve_path(self, relative_path: str) -> str:
        """
        Resolve a relative path to a full path for this backend.

        For local storage, returns absolute filesystem path.
        For cloud storage, returns full URI (s3://bucket/path).

        Args:
            relative_path: Relative path within this backend

        Returns:
            Full resolved path
        """
        return os.path.join(self.base_path, relative_path)

    def verify_integrity(self, path: str, expected_hash: str,
                        full_verify: bool = False) -> bool:
        """
        Verify file integrity by comparing hash.

        Args:
            path: Relative path within this storage backend
            expected_hash: Expected SHA-256 hash
            full_verify: If True, compute full hash; if False, use partial hash

        Returns:
            True if hash matches
        """
        try:
            if full_verify:
                actual_hash = self.compute_hash(path, 'sha256')
            else:
                actual_hash = self.compute_partial_hash(path)
            return actual_hash == expected_hash
        except FileNotFoundError:
            return False


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage backend.

    This is the default backend that wraps standard filesystem operations.
    """

    def __init__(self, base_path: str):
        """
        Initialize local storage backend.

        Args:
            base_path: Base directory for all operations
        """
        self._base_path = os.path.abspath(base_path)
        logger.debug(f"LocalStorageBackend initialized with base: {self._base_path}")

    @property
    def storage_type(self) -> str:
        return 'local'

    @property
    def base_path(self) -> str:
        return self._base_path

    def _full_path(self, path: str) -> str:
        """Convert relative path to absolute path."""
        # Normalize path separators
        path = path.replace('/', os.sep).replace('\\', os.sep)
        return os.path.join(self._base_path, path)

    def exists(self, path: str) -> bool:
        return os.path.exists(self._full_path(path))

    def get_size(self, path: str) -> int:
        full_path = self._full_path(path)
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")
        return os.path.getsize(full_path)

    def get_file_info(self, path: str) -> Optional[FileInfo]:
        full_path = self._full_path(path)
        if not os.path.exists(full_path):
            return None

        stat = os.stat(full_path)
        return FileInfo(
            path=path,
            size=stat.st_size,
            modified_time=datetime.fromtimestamp(stat.st_mtime),
            storage_type='local'
        )

    def read_file(self, path: str) -> bytes:
        full_path = self._full_path(path)
        with open(full_path, 'rb') as f:
            return f.read()

    def read_file_stream(self, path: str) -> BinaryIO:
        full_path = self._full_path(path)
        return open(full_path, 'rb')

    def read_range(self, path: str, offset: int, length: int) -> bytes:
        """Optimized range read for local files."""
        full_path = self._full_path(path)
        with open(full_path, 'rb') as f:
            if offset < 0:
                f.seek(offset, 2)  # Seek from end
            else:
                f.seek(offset)
            return f.read(length)

    def write_file(self, path: str, data: bytes) -> bool:
        full_path = self._full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(data)
        return True

    def write_file_stream(self, path: str, stream: BinaryIO, size: int) -> bool:
        full_path = self._full_path(path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        bytes_written = 0
        chunk_size = 1024 * 1024  # 1MB chunks

        with open(full_path, 'wb') as f:
            while bytes_written < size:
                chunk = stream.read(min(chunk_size, size - bytes_written))
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)

        return bytes_written == size

    def copy_from_local(self, local_path: str, remote_path: str,
                        preserve_metadata: bool = True) -> bool:
        dest_path = self._full_path(remote_path)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        if preserve_metadata:
            shutil.copy2(local_path, dest_path)
        else:
            shutil.copyfile(local_path, dest_path)

        logger.debug(f"Copied {local_path} -> {dest_path}")
        return True

    def copy_to_local(self, remote_path: str, local_path: str) -> bool:
        source_path = self._full_path(remote_path)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        shutil.copy2(source_path, local_path)
        logger.debug(f"Copied {source_path} -> {local_path}")
        return True

    def copy(self, source: str, dest: str) -> bool:
        source_path = self._full_path(source)
        dest_path = self._full_path(dest)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        shutil.copy2(source_path, dest_path)
        logger.debug(f"Copied {source_path} -> {dest_path}")
        return True

    def move(self, source: str, dest: str) -> bool:
        source_path = self._full_path(source)
        dest_path = self._full_path(dest)

        # Ensure destination directory exists
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        shutil.move(source_path, dest_path)
        logger.debug(f"Moved {source_path} -> {dest_path}")
        return True

    def delete(self, path: str) -> bool:
        full_path = self._full_path(path)
        if not os.path.exists(full_path):
            return False

        os.remove(full_path)
        logger.debug(f"Deleted {full_path}")
        return True

    def makedirs(self, path: str) -> bool:
        full_path = self._full_path(path)
        os.makedirs(full_path, exist_ok=True)
        return True

    def list_files(self, prefix: str = '') -> Iterator[FileInfo]:
        search_path = self._full_path(prefix) if prefix else self._base_path

        if os.path.isfile(search_path):
            # Single file
            info = self.get_file_info(prefix)
            if info:
                yield info
            return

        if not os.path.isdir(search_path):
            return

        for root, _, files in os.walk(search_path):
            for filename in files:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, self._base_path)
                # Normalize to forward slashes for consistency
                relative_path = relative_path.replace(os.sep, '/')

                info = self.get_file_info(relative_path)
                if info:
                    yield info

    def compute_hash(self, path: str, algorithm: str = 'sha256') -> str:
        full_path = self._full_path(path)

        hasher = hashlib.new(algorithm)
        with open(full_path, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)

        return hasher.hexdigest()


class StorageProviderRegistry:
    """
    Factory for creating storage backends from configuration.

    Usage:
        config = {'type': 'local', 'path': '/path/to/archive'}
        backend = StorageProviderRegistry.create(config)
    """

    _providers: Dict[str, type] = {
        'local': LocalStorageBackend,
    }

    @classmethod
    def register(cls, name: str, provider_class: type) -> None:
        """
        Register a new storage provider.

        Args:
            name: Provider identifier (e.g., 's3', 'azure')
            provider_class: Class that implements StorageBackend
        """
        cls._providers[name] = provider_class
        logger.info(f"Registered storage provider: {name}")

    @classmethod
    def create(cls, config: Dict[str, Any]) -> StorageBackend:
        """
        Create a storage backend from configuration.

        Args:
            config: Configuration dictionary with at least 'type' and 'path'/'bucket'

        Returns:
            StorageBackend instance

        Raises:
            ValueError: If storage type is unknown or config is invalid
        """
        storage_type = config.get('type', 'local')

        if storage_type not in cls._providers:
            available = ', '.join(cls._providers.keys())
            raise ValueError(
                f"Unknown storage type: {storage_type}. "
                f"Available types: {available}"
            )

        provider_class = cls._providers[storage_type]

        if storage_type == 'local':
            if 'path' not in config:
                raise ValueError("Local storage requires 'path' configuration")
            return provider_class(config['path'])

        # For cloud providers (to be implemented)
        return provider_class(**config)

    @classmethod
    def get_available_providers(cls) -> list:
        """Return list of registered provider names."""
        return list(cls._providers.keys())


class StorageManager:
    """
    Manages multiple storage backends for different vault types.

    This class provides a unified interface for accessing all configured
    storage backends (archive, video_archive, prior_revision, delete_vault).
    """

    VAULT_TYPES = ['archive', 'video_archive', 'prior_revision', 'delete_vault']

    def __init__(self, storage_config: Dict[str, Dict[str, Any]]):
        """
        Initialize storage manager with configuration.

        Args:
            storage_config: Dictionary mapping vault types to storage configs
                Example:
                {
                    'archive': {'type': 'local', 'path': '/archive'},
                    'video_archive': {'type': 's3', 'bucket': 'videos', ...}
                }
        """
        self._backends: Dict[str, StorageBackend] = {}

        for vault_type, config in storage_config.items():
            if vault_type in self.VAULT_TYPES:
                self._backends[vault_type] = StorageProviderRegistry.create(config)
                logger.info(f"Initialized {vault_type} backend: {config.get('type', 'local')}")

    def get_backend(self, vault_type: str) -> Optional[StorageBackend]:
        """
        Get the storage backend for a vault type.

        Args:
            vault_type: One of 'archive', 'video_archive', 'prior_revision', 'delete_vault'

        Returns:
            StorageBackend instance or None if not configured
        """
        return self._backends.get(vault_type)

    def get_archive_backend(self) -> Optional[StorageBackend]:
        """Get the main archive storage backend."""
        return self._backends.get('archive')

    def get_video_backend(self) -> Optional[StorageBackend]:
        """Get the video archive storage backend (falls back to archive)."""
        return self._backends.get('video_archive') or self._backends.get('archive')

    def get_prior_revision_backend(self) -> Optional[StorageBackend]:
        """Get the prior revision storage backend."""
        return self._backends.get('prior_revision')

    def get_delete_vault_backend(self) -> Optional[StorageBackend]:
        """Get the delete vault storage backend."""
        return self._backends.get('delete_vault')

    def resolve_path(self, relative_path: str, vault_type: str) -> Optional[str]:
        """
        Resolve a relative path to full path for the specified vault.

        Args:
            relative_path: Relative path within the vault
            vault_type: Vault type identifier

        Returns:
            Full resolved path or None if vault not configured
        """
        backend = self.get_backend(vault_type)
        if backend:
            return backend.resolve_path(relative_path)
        return None

    def copy_between_vaults(self, source_vault: str, source_path: str,
                           dest_vault: str, dest_path: str) -> bool:
        """
        Copy a file between two vaults.

        Handles the case where vaults may be on different storage backends.

        Args:
            source_vault: Source vault type
            source_path: Relative path in source vault
            dest_vault: Destination vault type
            dest_path: Relative path in destination vault

        Returns:
            True if successful

        Raises:
            ValueError: If either vault is not configured
            FileNotFoundError: If source file doesn't exist
        """
        source_backend = self.get_backend(source_vault)
        dest_backend = self.get_backend(dest_vault)

        if not source_backend:
            raise ValueError(f"Source vault not configured: {source_vault}")
        if not dest_backend:
            raise ValueError(f"Destination vault not configured: {dest_vault}")

        # Same backend type - use internal copy
        if source_backend.storage_type == dest_backend.storage_type:
            if source_backend.base_path == dest_backend.base_path:
                return source_backend.copy(source_path, dest_path)

        # Different backends - need intermediate transfer
        # For local-to-local with different bases, copy directly
        if (source_backend.storage_type == 'local' and
            dest_backend.storage_type == 'local'):
            source_full = source_backend.resolve_path(source_path)
            return dest_backend.copy_from_local(source_full, dest_path)

        # For cloud backends, would need to download then upload
        # This will be implemented when cloud backends are added
        raise NotImplementedError(
            f"Cross-backend copy between {source_backend.storage_type} and "
            f"{dest_backend.storage_type} not yet implemented"
        )

    @property
    def configured_vaults(self) -> list:
        """Return list of configured vault types."""
        return list(self._backends.keys())


def create_storage_config_from_legacy(destination_directory: str,
                                      video_archive_location: str = None,
                                      prior_revision_location: str = None,
                                      delete_vault_location: str = None) -> Dict[str, Dict[str, Any]]:
    """
    Create new storage configuration from legacy single-path settings.

    This provides backward compatibility with existing settings.json files.

    Args:
        destination_directory: Main archive path (required)
        video_archive_location: Separate video archive path (optional)
        prior_revision_location: Prior revision archive path (optional)
        delete_vault_location: Delete vault path (optional)

    Returns:
        Storage configuration dictionary for StorageManager
    """
    config = {
        'archive': {
            'type': 'local',
            'path': destination_directory
        }
    }

    if video_archive_location:
        config['video_archive'] = {
            'type': 'local',
            'path': video_archive_location
        }

    if prior_revision_location:
        config['prior_revision'] = {
            'type': 'local',
            'path': prior_revision_location
        }

    if delete_vault_location:
        config['delete_vault'] = {
            'type': 'local',
            'path': delete_vault_location
        }

    return config


if __name__ == '__main__':
    """Test the storage backend module."""
    import tempfile

    print("Testing storage_backend.py")
    print("=" * 50)

    # Create temp directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Test directory: {tmpdir}")

        # Test LocalStorageBackend
        backend = LocalStorageBackend(tmpdir)
        print(f"Created backend: {backend.storage_type} at {backend.base_path}")

        # Test write
        test_data = b"Hello, World! This is test data."
        backend.write_file("test/hello.txt", test_data)
        print("Wrote test/hello.txt")

        # Test exists
        assert backend.exists("test/hello.txt"), "File should exist"
        assert not backend.exists("test/nonexistent.txt"), "File should not exist"
        print("exists() works correctly")

        # Test get_size
        size = backend.get_size("test/hello.txt")
        assert size == len(test_data), f"Size mismatch: {size} vs {len(test_data)}"
        print(f"get_size() = {size} bytes")

        # Test get_file_info
        info = backend.get_file_info("test/hello.txt")
        assert info is not None
        assert info.size == len(test_data)
        print(f"get_file_info() = {info}")

        # Test read
        read_data = backend.read_file("test/hello.txt")
        assert read_data == test_data, "Read data mismatch"
        print("read_file() works correctly")

        # Test hash
        hash_value = backend.compute_hash("test/hello.txt")
        expected_hash = hashlib.sha256(test_data).hexdigest()
        assert hash_value == expected_hash, "Hash mismatch"
        print(f"compute_hash() = {hash_value[:16]}...")

        # Test copy
        backend.copy("test/hello.txt", "test/hello_copy.txt")
        assert backend.exists("test/hello_copy.txt"), "Copy failed"
        print("copy() works correctly")

        # Test move
        backend.move("test/hello_copy.txt", "test/hello_moved.txt")
        assert backend.exists("test/hello_moved.txt"), "Move failed"
        assert not backend.exists("test/hello_copy.txt"), "Move didn't remove source"
        print("move() works correctly")

        # Test delete
        backend.delete("test/hello_moved.txt")
        assert not backend.exists("test/hello_moved.txt"), "Delete failed"
        print("delete() works correctly")

        # Test list_files
        backend.write_file("subdir/file1.txt", b"file1")
        backend.write_file("subdir/file2.txt", b"file2")
        files = list(backend.list_files("subdir"))
        assert len(files) == 2, f"Expected 2 files, got {len(files)}"
        print(f"list_files() found {len(files)} files")

        # Test StorageProviderRegistry
        config = {'type': 'local', 'path': tmpdir}
        registered_backend = StorageProviderRegistry.create(config)
        assert registered_backend.storage_type == 'local'
        print("StorageProviderRegistry.create() works")

        # Test StorageManager
        storage_config = create_storage_config_from_legacy(
            destination_directory=tmpdir,
            prior_revision_location=os.path.join(tmpdir, 'prior')
        )
        manager = StorageManager(storage_config)
        assert manager.get_archive_backend() is not None
        assert manager.get_prior_revision_backend() is not None
        print(f"StorageManager configured vaults: {manager.configured_vaults}")

        print("=" * 50)
        print("All tests passed!")
