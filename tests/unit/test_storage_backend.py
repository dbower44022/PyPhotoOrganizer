"""
Unit tests for storage_backend.py

Tests the StorageBackend abstraction layer including:
- LocalStorageBackend operations
- StorageProviderRegistry factory
- StorageManager multi-vault management
- Backward compatibility helpers
"""

import hashlib
import os
import tempfile
import unittest
from datetime import datetime

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from storage_backend import (
    FileInfo,
    LocalStorageBackend,
    StorageBackend,
    StorageManager,
    StorageProviderRegistry,
    create_storage_config_from_legacy,
)


class TestFileInfo(unittest.TestCase):
    """Tests for FileInfo dataclass."""

    def test_creation(self):
        """Test FileInfo creation with all fields."""
        info = FileInfo(
            path='test/file.txt',
            size=1024,
            modified_time=datetime.now(),
            content_hash='abc123',
            storage_type='local'
        )
        self.assertEqual(info.path, 'test/file.txt')
        self.assertEqual(info.size, 1024)
        self.assertEqual(info.content_hash, 'abc123')
        self.assertEqual(info.storage_type, 'local')

    def test_default_values(self):
        """Test FileInfo with default values."""
        info = FileInfo(
            path='test.txt',
            size=100,
            modified_time=datetime.now()
        )
        self.assertIsNone(info.content_hash)
        self.assertEqual(info.storage_type, 'local')

    def test_repr(self):
        """Test string representation."""
        info = FileInfo('file.txt', 100, datetime.now())
        repr_str = repr(info)
        self.assertIn('file.txt', repr_str)
        self.assertIn('100', repr_str)


class TestLocalStorageBackend(unittest.TestCase):
    """Tests for LocalStorageBackend."""

    def setUp(self):
        """Create temp directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.backend = LocalStorageBackend(self.temp_dir)

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_storage_type(self):
        """Test storage_type property."""
        self.assertEqual(self.backend.storage_type, 'local')

    def test_base_path(self):
        """Test base_path property."""
        self.assertEqual(self.backend.base_path, self.temp_dir)

    def test_write_and_read_file(self):
        """Test writing and reading a file."""
        test_data = b"Hello, World!"
        self.backend.write_file("test.txt", test_data)

        read_data = self.backend.read_file("test.txt")
        self.assertEqual(read_data, test_data)

    def test_write_creates_directories(self):
        """Test that write_file creates parent directories."""
        test_data = b"Nested file content"
        self.backend.write_file("deep/nested/path/file.txt", test_data)

        self.assertTrue(self.backend.exists("deep/nested/path/file.txt"))
        self.assertEqual(self.backend.read_file("deep/nested/path/file.txt"), test_data)

    def test_exists(self):
        """Test exists method."""
        self.assertFalse(self.backend.exists("nonexistent.txt"))

        self.backend.write_file("exists.txt", b"data")
        self.assertTrue(self.backend.exists("exists.txt"))

    def test_get_size(self):
        """Test get_size method."""
        test_data = b"1234567890"  # 10 bytes
        self.backend.write_file("sized.txt", test_data)

        self.assertEqual(self.backend.get_size("sized.txt"), 10)

    def test_get_size_nonexistent(self):
        """Test get_size raises FileNotFoundError for missing file."""
        with self.assertRaises(FileNotFoundError):
            self.backend.get_size("nonexistent.txt")

    def test_get_file_info(self):
        """Test get_file_info method."""
        test_data = b"File info test data"
        self.backend.write_file("info.txt", test_data)

        info = self.backend.get_file_info("info.txt")
        self.assertIsNotNone(info)
        self.assertEqual(info.path, "info.txt")
        self.assertEqual(info.size, len(test_data))
        self.assertEqual(info.storage_type, 'local')
        self.assertIsInstance(info.modified_time, datetime)

    def test_get_file_info_nonexistent(self):
        """Test get_file_info returns None for missing file."""
        info = self.backend.get_file_info("nonexistent.txt")
        self.assertIsNone(info)

    def test_read_file_stream(self):
        """Test read_file_stream method."""
        test_data = b"Stream test data"
        self.backend.write_file("stream.txt", test_data)

        with self.backend.read_file_stream("stream.txt") as f:
            read_data = f.read()
        self.assertEqual(read_data, test_data)

    def test_write_file_stream(self):
        """Test write_file_stream method."""
        test_data = b"Stream write test"
        import io
        stream = io.BytesIO(test_data)

        result = self.backend.write_file_stream("stream_out.txt", stream, len(test_data))
        self.assertTrue(result)
        self.assertEqual(self.backend.read_file("stream_out.txt"), test_data)

    def test_copy(self):
        """Test copy method."""
        test_data = b"Copy test data"
        self.backend.write_file("original.txt", test_data)

        result = self.backend.copy("original.txt", "copied.txt")
        self.assertTrue(result)
        self.assertTrue(self.backend.exists("original.txt"))
        self.assertTrue(self.backend.exists("copied.txt"))
        self.assertEqual(self.backend.read_file("copied.txt"), test_data)

    def test_copy_to_subdirectory(self):
        """Test copying to a new subdirectory."""
        test_data = b"Copy to subdir"
        self.backend.write_file("file.txt", test_data)

        self.backend.copy("file.txt", "subdir/file.txt")
        self.assertTrue(self.backend.exists("subdir/file.txt"))

    def test_move(self):
        """Test move method."""
        test_data = b"Move test data"
        self.backend.write_file("source.txt", test_data)

        result = self.backend.move("source.txt", "destination.txt")
        self.assertTrue(result)
        self.assertFalse(self.backend.exists("source.txt"))
        self.assertTrue(self.backend.exists("destination.txt"))
        self.assertEqual(self.backend.read_file("destination.txt"), test_data)

    def test_delete(self):
        """Test delete method."""
        self.backend.write_file("to_delete.txt", b"data")
        self.assertTrue(self.backend.exists("to_delete.txt"))

        result = self.backend.delete("to_delete.txt")
        self.assertTrue(result)
        self.assertFalse(self.backend.exists("to_delete.txt"))

    def test_delete_nonexistent(self):
        """Test delete returns False for missing file."""
        result = self.backend.delete("nonexistent.txt")
        self.assertFalse(result)

    def test_makedirs(self):
        """Test makedirs method."""
        result = self.backend.makedirs("new/nested/directory")
        self.assertTrue(result)
        self.assertTrue(os.path.isdir(os.path.join(self.temp_dir, "new/nested/directory")))

    def test_list_files(self):
        """Test list_files method."""
        # Create several files
        self.backend.write_file("file1.txt", b"1")
        self.backend.write_file("file2.txt", b"2")
        self.backend.write_file("subdir/file3.txt", b"3")

        files = list(self.backend.list_files())
        self.assertEqual(len(files), 3)

        paths = [f.path for f in files]
        self.assertIn("file1.txt", paths)
        self.assertIn("file2.txt", paths)
        self.assertIn("subdir/file3.txt", paths)

    def test_list_files_with_prefix(self):
        """Test list_files with prefix filter."""
        self.backend.write_file("dir1/a.txt", b"a")
        self.backend.write_file("dir1/b.txt", b"b")
        self.backend.write_file("dir2/c.txt", b"c")

        files = list(self.backend.list_files("dir1"))
        self.assertEqual(len(files), 2)

    def test_compute_hash(self):
        """Test compute_hash method."""
        test_data = b"Hash test data"
        self.backend.write_file("hash.txt", test_data)

        hash_value = self.backend.compute_hash("hash.txt", "sha256")
        expected = hashlib.sha256(test_data).hexdigest()
        self.assertEqual(hash_value, expected)

    def test_compute_hash_md5(self):
        """Test compute_hash with MD5."""
        test_data = b"MD5 test"
        self.backend.write_file("md5.txt", test_data)

        hash_value = self.backend.compute_hash("md5.txt", "md5")
        expected = hashlib.md5(test_data).hexdigest()
        self.assertEqual(hash_value, expected)

    def test_compute_partial_hash_small_file(self):
        """Test compute_partial_hash returns full hash for small files."""
        test_data = b"Small file"
        self.backend.write_file("small.txt", test_data)

        partial_hash = self.backend.compute_partial_hash("small.txt")
        full_hash = self.backend.compute_hash("small.txt")
        self.assertEqual(partial_hash, full_hash)

    def test_read_range(self):
        """Test read_range method."""
        test_data = b"0123456789"
        self.backend.write_file("range.txt", test_data)

        # Read from start
        chunk = self.backend.read_range("range.txt", 0, 5)
        self.assertEqual(chunk, b"01234")

        # Read from middle
        chunk = self.backend.read_range("range.txt", 3, 4)
        self.assertEqual(chunk, b"3456")

        # Read from end (negative offset)
        chunk = self.backend.read_range("range.txt", -3, 3)
        self.assertEqual(chunk, b"789")

    def test_copy_from_local(self):
        """Test copy_from_local method."""
        # Create a file outside the backend
        external_file = os.path.join(self.temp_dir, "_external.txt")
        with open(external_file, 'wb') as f:
            f.write(b"External file content")

        # Copy it into the backend
        result = self.backend.copy_from_local(external_file, "imported.txt")
        self.assertTrue(result)
        self.assertEqual(self.backend.read_file("imported.txt"), b"External file content")

    def test_copy_to_local(self):
        """Test copy_to_local method."""
        self.backend.write_file("export.txt", b"Export content")

        external_dest = os.path.join(self.temp_dir, "_exported.txt")
        result = self.backend.copy_to_local("export.txt", external_dest)

        self.assertTrue(result)
        with open(external_dest, 'rb') as f:
            self.assertEqual(f.read(), b"Export content")

    def test_resolve_path(self):
        """Test resolve_path method."""
        full_path = self.backend.resolve_path("subdir/file.txt")
        expected = os.path.join(self.temp_dir, "subdir/file.txt")
        self.assertEqual(full_path, expected)

    def test_verify_integrity(self):
        """Test verify_integrity method."""
        test_data = b"Verify this"
        self.backend.write_file("verify.txt", test_data)

        correct_hash = hashlib.sha256(test_data).hexdigest()
        wrong_hash = "0" * 64

        self.assertTrue(self.backend.verify_integrity("verify.txt", correct_hash, full_verify=True))
        self.assertFalse(self.backend.verify_integrity("verify.txt", wrong_hash, full_verify=True))

    def test_verify_integrity_missing_file(self):
        """Test verify_integrity returns False for missing file."""
        result = self.backend.verify_integrity("missing.txt", "anyhash")
        self.assertFalse(result)

    def test_path_separator_normalization(self):
        """Test that forward slashes work on all platforms."""
        test_data = b"Path test"
        self.backend.write_file("a/b/c.txt", test_data)

        # Should work with either separator
        self.assertTrue(self.backend.exists("a/b/c.txt"))
        if os.sep == '\\':
            self.assertTrue(self.backend.exists("a\\b\\c.txt"))


class TestStorageProviderRegistry(unittest.TestCase):
    """Tests for StorageProviderRegistry."""

    def test_create_local_backend(self):
        """Test creating local storage backend."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {'type': 'local', 'path': tmpdir}
            backend = StorageProviderRegistry.create(config)

            self.assertIsInstance(backend, LocalStorageBackend)
            self.assertEqual(backend.storage_type, 'local')
            self.assertEqual(backend.base_path, tmpdir)

    def test_create_default_type(self):
        """Test that missing type defaults to local."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = {'path': tmpdir}  # No 'type' key
            backend = StorageProviderRegistry.create(config)

            self.assertIsInstance(backend, LocalStorageBackend)

    def test_create_unknown_type(self):
        """Test error for unknown storage type."""
        config = {'type': 'unknown_provider', 'path': '/tmp'}

        with self.assertRaises(ValueError) as context:
            StorageProviderRegistry.create(config)

        self.assertIn('Unknown storage type', str(context.exception))

    def test_create_missing_path(self):
        """Test error when path is missing for local storage."""
        config = {'type': 'local'}

        with self.assertRaises(ValueError) as context:
            StorageProviderRegistry.create(config)

        self.assertIn('path', str(context.exception))

    def test_get_available_providers(self):
        """Test get_available_providers returns local at minimum."""
        providers = StorageProviderRegistry.get_available_providers()

        self.assertIsInstance(providers, list)
        self.assertIn('local', providers)

    def test_register_custom_provider(self):
        """Test registering a custom storage provider."""
        # Create a dummy provider class
        class DummyBackend(LocalStorageBackend):
            @property
            def storage_type(self):
                return 'dummy'

        # Register it
        StorageProviderRegistry.register('dummy', DummyBackend)

        self.assertIn('dummy', StorageProviderRegistry.get_available_providers())

        # Clean up
        del StorageProviderRegistry._providers['dummy']


class TestStorageManager(unittest.TestCase):
    """Tests for StorageManager."""

    def setUp(self):
        """Create temp directories for testing."""
        self.archive_dir = tempfile.mkdtemp()
        self.video_dir = tempfile.mkdtemp()
        self.prior_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temp directories."""
        import shutil
        shutil.rmtree(self.archive_dir, ignore_errors=True)
        shutil.rmtree(self.video_dir, ignore_errors=True)
        shutil.rmtree(self.prior_dir, ignore_errors=True)

    def test_create_with_all_vaults(self):
        """Test creating StorageManager with all vault types."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir},
            'video_archive': {'type': 'local', 'path': self.video_dir},
            'prior_revision': {'type': 'local', 'path': self.prior_dir},
        }

        manager = StorageManager(config)

        self.assertIsNotNone(manager.get_archive_backend())
        self.assertIsNotNone(manager.get_video_backend())
        self.assertIsNotNone(manager.get_prior_revision_backend())

    def test_get_archive_backend(self):
        """Test get_archive_backend method."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir}
        }
        manager = StorageManager(config)

        backend = manager.get_archive_backend()
        self.assertIsNotNone(backend)
        self.assertEqual(backend.base_path, self.archive_dir)

    def test_get_video_backend_fallback(self):
        """Test that get_video_backend falls back to archive."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir}
            # No video_archive configured
        }
        manager = StorageManager(config)

        video_backend = manager.get_video_backend()
        archive_backend = manager.get_archive_backend()

        # Should fall back to archive
        self.assertEqual(video_backend.base_path, archive_backend.base_path)

    def test_get_backend_by_type(self):
        """Test get_backend method with vault type."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir},
            'prior_revision': {'type': 'local', 'path': self.prior_dir},
        }
        manager = StorageManager(config)

        archive = manager.get_backend('archive')
        prior = manager.get_backend('prior_revision')
        missing = manager.get_backend('delete_vault')

        self.assertIsNotNone(archive)
        self.assertIsNotNone(prior)
        self.assertIsNone(missing)

    def test_configured_vaults(self):
        """Test configured_vaults property."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir},
            'video_archive': {'type': 'local', 'path': self.video_dir},
        }
        manager = StorageManager(config)

        configured = manager.configured_vaults
        self.assertIn('archive', configured)
        self.assertIn('video_archive', configured)
        self.assertNotIn('prior_revision', configured)

    def test_resolve_path(self):
        """Test resolve_path method."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir}
        }
        manager = StorageManager(config)

        resolved = manager.resolve_path("2024/01/photo.jpg", "archive")
        expected = os.path.join(self.archive_dir, "2024/01/photo.jpg")
        self.assertEqual(resolved, expected)

    def test_resolve_path_unconfigured_vault(self):
        """Test resolve_path returns None for unconfigured vault."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir}
        }
        manager = StorageManager(config)

        resolved = manager.resolve_path("file.txt", "delete_vault")
        self.assertIsNone(resolved)

    def test_copy_between_vaults_same_backend(self):
        """Test copying between local vaults."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir},
            'prior_revision': {'type': 'local', 'path': self.prior_dir},
        }
        manager = StorageManager(config)

        # Write file to archive
        archive_backend = manager.get_archive_backend()
        archive_backend.write_file("test.jpg", b"photo data")

        # Copy to prior_revision
        result = manager.copy_between_vaults(
            'archive', 'test.jpg',
            'prior_revision', 'test_backup.jpg'
        )

        self.assertTrue(result)
        prior_backend = manager.get_prior_revision_backend()
        self.assertTrue(prior_backend.exists('test_backup.jpg'))

    def test_copy_between_vaults_missing_source(self):
        """Test copy_between_vaults raises error for missing vault."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir}
        }
        manager = StorageManager(config)

        with self.assertRaises(ValueError) as context:
            manager.copy_between_vaults('nonexistent', 'a.txt', 'archive', 'b.txt')

        self.assertIn('Source vault not configured', str(context.exception))

    def test_ignores_invalid_vault_types(self):
        """Test that invalid vault types in config are ignored."""
        config = {
            'archive': {'type': 'local', 'path': self.archive_dir},
            'invalid_vault': {'type': 'local', 'path': '/tmp'},
        }
        manager = StorageManager(config)

        self.assertIn('archive', manager.configured_vaults)
        self.assertNotIn('invalid_vault', manager.configured_vaults)


class TestBackwardCompatibility(unittest.TestCase):
    """Tests for backward compatibility helpers."""

    def test_create_storage_config_from_legacy_minimal(self):
        """Test legacy config with only destination_directory."""
        config = create_storage_config_from_legacy('/archive')

        self.assertIn('archive', config)
        self.assertEqual(config['archive']['type'], 'local')
        self.assertEqual(config['archive']['path'], '/archive')
        self.assertNotIn('video_archive', config)
        self.assertNotIn('prior_revision', config)

    def test_create_storage_config_from_legacy_full(self):
        """Test legacy config with all paths."""
        config = create_storage_config_from_legacy(
            destination_directory='/archive',
            video_archive_location='/videos',
            prior_revision_location='/prior',
            delete_vault_location='/deleted'
        )

        self.assertEqual(config['archive']['path'], '/archive')
        self.assertEqual(config['video_archive']['path'], '/videos')
        self.assertEqual(config['prior_revision']['path'], '/prior')
        self.assertEqual(config['delete_vault']['path'], '/deleted')

        # All should be local type
        for vault_config in config.values():
            self.assertEqual(vault_config['type'], 'local')


if __name__ == '__main__':
    unittest.main()
