"""
Unit tests for S3 storage backend.

Tests the S3StorageBackend implementation using moto for AWS mocking.
If moto is not available, tests are skipped.

To run tests with moto:
    pip install moto boto3
    python -m pytest tests/unit/test_storage_backend_s3.py -v
"""

import hashlib
import io
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

# Check if boto3 and moto are available
try:
    import boto3
    from moto import mock_aws
    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False

    # Dummy decorator that just returns the function unchanged
    def mock_aws(f=None):
        if f is None:
            return lambda fn: fn
        return f

from storage_backend_s3 import (
    BOTO3_AVAILABLE,
    S3StorageBackend,
    S3Config,
    STORAGE_CLASS_STANDARD,
    STORAGE_CLASS_INTELLIGENT_TIERING,
)
from storage_backend import StorageProviderRegistry


@unittest.skipUnless(BOTO3_AVAILABLE and MOTO_AVAILABLE,
                     "boto3 and moto required for S3 tests")
class TestS3StorageBackend(unittest.TestCase):
    """Tests for S3StorageBackend using moto mock."""

    @mock_aws
    def setUp(self):
        """Create mock S3 bucket for each test."""
        self.bucket_name = 'test-photo-archive'
        self.region = 'us-east-1'

        # Create S3 client and bucket
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        # Create backend
        self.backend = S3StorageBackend(
            bucket=self.bucket_name,
            prefix='photos',
            region=self.region
        )

    @mock_aws
    def test_storage_type(self):
        """Test storage_type property."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)
        self.assertEqual(backend.storage_type, 's3')

    @mock_aws
    def test_base_path(self):
        """Test base_path property."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name, prefix='photos')
        self.assertEqual(backend.base_path, f's3://{self.bucket_name}/photos')

        backend_no_prefix = S3StorageBackend(bucket=self.bucket_name)
        self.assertEqual(backend_no_prefix.base_path, f's3://{self.bucket_name}')

    @mock_aws
    def test_write_and_read_file(self):
        """Test writing and reading a file."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name, prefix='test')

        test_data = b"Hello, S3 World!"
        backend.write_file("test.txt", test_data)

        read_data = backend.read_file("test.txt")
        self.assertEqual(read_data, test_data)

    @mock_aws
    def test_exists(self):
        """Test exists method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        self.assertFalse(backend.exists("nonexistent.txt"))

        backend.write_file("exists.txt", b"data")
        self.assertTrue(backend.exists("exists.txt"))

    @mock_aws
    def test_get_size(self):
        """Test get_size method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        test_data = b"1234567890"  # 10 bytes
        backend.write_file("sized.txt", test_data)

        self.assertEqual(backend.get_size("sized.txt"), 10)

    @mock_aws
    def test_get_file_info(self):
        """Test get_file_info method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        test_data = b"File info test"
        backend.write_file("info.txt", test_data)

        info = backend.get_file_info("info.txt")
        self.assertIsNotNone(info)
        self.assertEqual(info.path, "info.txt")
        self.assertEqual(info.size, len(test_data))
        self.assertEqual(info.storage_type, 's3')

    @mock_aws
    def test_delete(self):
        """Test delete method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        backend.write_file("to_delete.txt", b"data")
        self.assertTrue(backend.exists("to_delete.txt"))

        result = backend.delete("to_delete.txt")
        self.assertTrue(result)
        self.assertFalse(backend.exists("to_delete.txt"))

    @mock_aws
    def test_copy(self):
        """Test copy method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        test_data = b"Copy test"
        backend.write_file("original.txt", test_data)

        result = backend.copy("original.txt", "copied.txt")
        self.assertTrue(result)
        self.assertTrue(backend.exists("original.txt"))
        self.assertTrue(backend.exists("copied.txt"))
        self.assertEqual(backend.read_file("copied.txt"), test_data)

    @mock_aws
    def test_move(self):
        """Test move method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        test_data = b"Move test"
        backend.write_file("source.txt", test_data)

        result = backend.move("source.txt", "dest.txt")
        self.assertTrue(result)
        self.assertFalse(backend.exists("source.txt"))
        self.assertTrue(backend.exists("dest.txt"))
        self.assertEqual(backend.read_file("dest.txt"), test_data)

    @mock_aws
    def test_list_files(self):
        """Test list_files method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name, prefix='list_test')

        # Create several files
        backend.write_file("file1.txt", b"1")
        backend.write_file("file2.txt", b"2")
        backend.write_file("subdir/file3.txt", b"3")

        files = list(backend.list_files())
        self.assertEqual(len(files), 3)

        paths = [f.path for f in files]
        self.assertIn("file1.txt", paths)
        self.assertIn("file2.txt", paths)
        self.assertIn("subdir/file3.txt", paths)

    @mock_aws
    def test_copy_from_local(self):
        """Test copy_from_local method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        # Create a local temp file
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"Local file content")
            local_path = f.name

        try:
            result = backend.copy_from_local(local_path, "uploaded.txt")
            self.assertTrue(result)
            self.assertEqual(backend.read_file("uploaded.txt"), b"Local file content")
        finally:
            os.unlink(local_path)

    @mock_aws
    def test_copy_to_local(self):
        """Test copy_to_local method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        backend.write_file("download.txt", b"Download content")

        with tempfile.TemporaryDirectory() as tmpdir:
            local_path = os.path.join(tmpdir, "downloaded.txt")
            result = backend.copy_to_local("download.txt", local_path)

            self.assertTrue(result)
            with open(local_path, 'rb') as f:
                self.assertEqual(f.read(), b"Download content")

    @mock_aws
    def test_compute_hash(self):
        """Test compute_hash method."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        test_data = b"Hash test data"
        backend.write_file("hash.txt", test_data)

        hash_value = backend.compute_hash("hash.txt", "sha256")
        expected = hashlib.sha256(test_data).hexdigest()
        self.assertEqual(hash_value, expected)

    @mock_aws
    def test_makedirs_noop(self):
        """Test that makedirs is a no-op for S3."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name)

        # Should succeed without creating anything
        result = backend.makedirs("some/nested/path")
        self.assertTrue(result)

    @mock_aws
    def test_prefix_handling(self):
        """Test that prefix is correctly applied to all operations."""
        self.s3_client = boto3.client('s3', region_name=self.region)
        self.s3_client.create_bucket(Bucket=self.bucket_name)

        backend = S3StorageBackend(bucket=self.bucket_name, prefix='my/prefix')

        backend.write_file("test.txt", b"data")

        # Verify the actual key in S3 includes the prefix
        response = self.s3_client.list_objects_v2(
            Bucket=self.bucket_name,
            Prefix='my/prefix'
        )

        keys = [obj['Key'] for obj in response.get('Contents', [])]
        self.assertIn('my/prefix/test.txt', keys)


@unittest.skipUnless(BOTO3_AVAILABLE, "boto3 required for config tests")
class TestS3Config(unittest.TestCase):
    """Tests for S3Config dataclass."""

    def test_default_values(self):
        """Test S3Config default values."""
        config = S3Config(bucket='test-bucket')

        self.assertEqual(config.bucket, 'test-bucket')
        self.assertEqual(config.prefix, '')
        self.assertEqual(config.region, 'us-east-1')
        self.assertEqual(config.storage_class, STORAGE_CLASS_INTELLIGENT_TIERING)

    def test_custom_values(self):
        """Test S3Config with custom values."""
        config = S3Config(
            bucket='my-bucket',
            prefix='photos',
            region='eu-west-1',
            storage_class=STORAGE_CLASS_STANDARD
        )

        self.assertEqual(config.bucket, 'my-bucket')
        self.assertEqual(config.prefix, 'photos')
        self.assertEqual(config.region, 'eu-west-1')
        self.assertEqual(config.storage_class, STORAGE_CLASS_STANDARD)


class TestS3ProviderRegistration(unittest.TestCase):
    """Tests for S3 provider registration."""

    def test_s3_registered_when_boto3_available(self):
        """Test that S3 is registered when boto3 is available."""
        providers = StorageProviderRegistry.get_available_providers()

        if BOTO3_AVAILABLE:
            self.assertIn('s3', providers)
        else:
            self.assertNotIn('s3', providers)


class TestS3BackendWithoutBoto3(unittest.TestCase):
    """Tests for S3 backend behavior when boto3 is not available."""

    def test_import_error_without_boto3(self):
        """Test that appropriate error is raised without boto3."""
        if BOTO3_AVAILABLE:
            self.skipTest("boto3 is available")

        with self.assertRaises(ImportError):
            S3StorageBackend(bucket='test')


if __name__ == '__main__':
    if not BOTO3_AVAILABLE:
        print("boto3 not installed - skipping most S3 tests")
        print("Install with: pip install boto3")
    if not MOTO_AVAILABLE:
        print("moto not installed - skipping mock S3 tests")
        print("Install with: pip install moto")

    unittest.main()
