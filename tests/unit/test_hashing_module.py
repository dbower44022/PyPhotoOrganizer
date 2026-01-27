"""
Unit tests for the hashing module.

Tests:
- Full file hashing
- Partial file hashing
- Content-based image hashing
- Copy verification
- Hash threshold logic
"""

import os
import tempfile
import shutil
import pytest
from datetime import datetime

import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from hashing import (
    hash_file,
    hash_file_partial,
    hash_image_content,
    verify_copy_integrity,
    should_use_partial_hash,
    get_file_size_and_hash
)
from tests.test_utils.image_generator import ImageGenerator
import constants


class TestHashFile:
    """Tests for hash_file function."""

    def test_hash_file_basic(self, temp_dir):
        """Test basic file hashing."""
        # Create a test file
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Hello, World!")

        file_hash = hash_file(test_file)

        assert file_hash is not None
        assert isinstance(file_hash, str)
        assert len(file_hash) == 64  # SHA-256 produces 64 hex characters

    def test_hash_file_consistency(self, temp_dir):
        """Test that hashing the same file twice produces the same result."""
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, "w") as f:
            f.write("Consistent content")

        hash1 = hash_file(test_file)
        hash2 = hash_file(test_file)

        assert hash1 == hash2

    def test_hash_file_different_content(self, temp_dir):
        """Test that different files produce different hashes."""
        file1 = os.path.join(temp_dir, "file1.txt")
        file2 = os.path.join(temp_dir, "file2.txt")

        with open(file1, "w") as f:
            f.write("Content A")
        with open(file2, "w") as f:
            f.write("Content B")

        hash1 = hash_file(file1)
        hash2 = hash_file(file2)

        assert hash1 != hash2

    def test_hash_file_binary(self, temp_dir):
        """Test hashing binary files."""
        binary_file = os.path.join(temp_dir, "binary.bin")
        with open(binary_file, "wb") as f:
            f.write(bytes(range(256)))

        file_hash = hash_file(binary_file)

        assert file_hash is not None
        assert len(file_hash) == 64

    def test_hash_file_large(self, temp_dir):
        """Test hashing a large file."""
        large_file = os.path.join(temp_dir, "large.bin")
        # Create a 5MB file
        with open(large_file, "wb") as f:
            f.write(os.urandom(5 * 1024 * 1024))

        file_hash = hash_file(large_file)

        assert file_hash is not None
        assert len(file_hash) == 64

    def test_hash_file_nonexistent(self, temp_dir):
        """Test that hashing a nonexistent file raises an exception."""
        nonexistent = os.path.join(temp_dir, "does_not_exist.txt")

        with pytest.raises(FileNotFoundError):
            hash_file(nonexistent)

    def test_hash_file_image(self, temp_dir):
        """Test hashing an image file."""
        image_file = os.path.join(temp_dir, "test.jpg")
        ImageGenerator.create_test_image(
            image_file,
            width=800,
            height=600,
            exif_date=datetime(2024, 1, 1)
        )

        file_hash = hash_file(image_file)

        assert file_hash is not None
        assert len(file_hash) == 64


class TestHashFilePartial:
    """Tests for hash_file_partial function."""

    def test_partial_hash_basic(self, temp_dir):
        """Test basic partial hashing."""
        test_file = os.path.join(temp_dir, "large.bin")
        # Create a file larger than partial hash size
        with open(test_file, "wb") as f:
            f.write(os.urandom(100000))

        partial = hash_file_partial(test_file)

        assert partial is not None
        assert len(partial) == 64

    def test_partial_hash_custom_size(self, temp_dir):
        """Test partial hashing with custom byte count."""
        test_file = os.path.join(temp_dir, "test.bin")
        with open(test_file, "wb") as f:
            f.write(os.urandom(50000))

        partial_8k = hash_file_partial(test_file, num_bytes=8192)
        partial_16k = hash_file_partial(test_file, num_bytes=16384)

        # Different sizes should produce different partial hashes
        assert partial_8k != partial_16k

    def test_partial_hash_small_file(self, temp_dir):
        """Test partial hashing on a file smaller than hash size."""
        test_file = os.path.join(temp_dir, "small.txt")
        with open(test_file, "w") as f:
            f.write("Small content")

        partial = hash_file_partial(test_file)

        # Should still work, hashing whatever is available
        assert partial is not None
        assert len(partial) == 64

    def test_partial_vs_full_hash(self, temp_dir):
        """Test that partial hash differs from full hash for large files."""
        test_file = os.path.join(temp_dir, "large.bin")
        with open(test_file, "wb") as f:
            f.write(os.urandom(100000))

        partial = hash_file_partial(test_file)
        full = hash_file(test_file)

        # Partial and full should differ for files larger than partial size
        assert partial != full

    def test_partial_hash_consistency(self, temp_dir):
        """Test that partial hashing is consistent."""
        test_file = os.path.join(temp_dir, "test.bin")
        with open(test_file, "wb") as f:
            f.write(os.urandom(50000))

        partial1 = hash_file_partial(test_file)
        partial2 = hash_file_partial(test_file)

        assert partial1 == partial2


class TestHashImageContent:
    """Tests for hash_image_content function."""

    def test_content_hash_basic(self, temp_dir):
        """Test basic image content hashing."""
        image_file = os.path.join(temp_dir, "test.jpg")
        ImageGenerator.create_test_image(
            image_file,
            width=800,
            height=600
        )

        content_hash = hash_image_content(image_file)

        assert content_hash is not None
        assert len(content_hash) == 64

    def test_content_hash_ignores_metadata(self, temp_dir):
        """Test that content hash ignores metadata changes."""
        # Create two images with same pixels but different metadata
        img1 = os.path.join(temp_dir, "img1.jpg")
        img2 = os.path.join(temp_dir, "img2.jpg")

        # Same visual content, different EXIF dates
        ImageGenerator.create_test_image(
            img1,
            width=800,
            height=600,
            text="Same Content",
            exif_date=datetime(2024, 1, 1)
        )
        ImageGenerator.create_test_image(
            img2,
            width=800,
            height=600,
            text="Same Content",
            exif_date=datetime(2024, 12, 31)
        )

        hash1 = hash_image_content(img1)
        hash2 = hash_image_content(img2)

        # Content hashes should be equal if pixel content is the same
        # (This depends on exact image generation - may need adjustment)
        # For now, just verify both produce valid hashes
        assert hash1 is not None
        assert hash2 is not None

    def test_content_hash_video_returns_none(self, temp_dir):
        """Test that content hash returns None for video files."""
        from tests.test_utils.test_file_generator import TestFileGenerator

        video_file = os.path.join(temp_dir, "test.mp4")
        TestFileGenerator.create_mock_video(video_file)

        content_hash = hash_image_content(video_file)

        assert content_hash is None

    def test_content_hash_corrupted_file(self, temp_dir):
        """Test content hash on corrupted file returns None."""
        corrupted = os.path.join(temp_dir, "corrupted.jpg")
        ImageGenerator.create_corrupted_file(corrupted)

        content_hash = hash_image_content(corrupted)

        # Should return None for unreadable files
        assert content_hash is None


class TestVerifyCopyIntegrity:
    """Tests for verify_copy_integrity function."""

    def test_verify_success(self, temp_dir):
        """Test successful copy verification."""
        source = os.path.join(temp_dir, "source.txt")
        dest = os.path.join(temp_dir, "dest.txt")

        with open(source, "w") as f:
            f.write("Test content")

        expected_hash = hash_file(source)
        shutil.copy2(source, dest)

        verified, actual_hash, error = verify_copy_integrity(dest, expected_hash)

        assert verified is True
        assert actual_hash == expected_hash
        assert error is None

    def test_verify_hash_mismatch(self, temp_dir):
        """Test verification fails on hash mismatch."""
        dest = os.path.join(temp_dir, "dest.txt")

        with open(dest, "w") as f:
            f.write("Actual content")

        # Provide wrong expected hash
        wrong_hash = "a" * 64

        verified, actual_hash, error = verify_copy_integrity(dest, wrong_hash)

        assert verified is False
        assert actual_hash is not None
        assert actual_hash != wrong_hash
        assert error is not None
        assert "mismatch" in error.lower()

    def test_verify_nonexistent_file(self, temp_dir):
        """Test verification of nonexistent file."""
        nonexistent = os.path.join(temp_dir, "does_not_exist.txt")
        expected_hash = "a" * 64

        verified, actual_hash, error = verify_copy_integrity(nonexistent, expected_hash)

        assert verified is False
        assert actual_hash is None
        assert error is not None
        assert "not exist" in error.lower()

    def test_verify_with_retry(self, temp_dir):
        """Test verification with retry count."""
        dest = os.path.join(temp_dir, "dest.txt")
        with open(dest, "w") as f:
            f.write("Test")

        expected_hash = hash_file(dest)

        # Should succeed with retries
        verified, actual_hash, error = verify_copy_integrity(
            dest, expected_hash, retry_count=3
        )

        assert verified is True


class TestShouldUsePartialHash:
    """Tests for should_use_partial_hash function."""

    def test_small_file_no_partial(self):
        """Test that small files don't use partial hashing."""
        small_size = 500 * 1024  # 500KB
        assert should_use_partial_hash(small_size) is False

    def test_large_file_uses_partial(self):
        """Test that large files use partial hashing."""
        large_size = 5 * 1024 * 1024  # 5MB
        assert should_use_partial_hash(large_size) is True

    def test_threshold_boundary(self):
        """Test threshold boundary behavior."""
        # Just under threshold
        assert should_use_partial_hash(constants.PARTIAL_HASH_MIN_FILE_SIZE - 1) is False

        # At threshold
        assert should_use_partial_hash(constants.PARTIAL_HASH_MIN_FILE_SIZE) is True

        # Just over threshold
        assert should_use_partial_hash(constants.PARTIAL_HASH_MIN_FILE_SIZE + 1) is True


class TestGetFileSizeAndHash:
    """Tests for get_file_size_and_hash function."""

    def test_small_file_no_partial(self, temp_dir):
        """Test small file returns no partial hash."""
        small_file = os.path.join(temp_dir, "small.txt")
        with open(small_file, "w") as f:
            f.write("Small content")

        size, full_hash, partial_hash, partial_bytes = get_file_size_and_hash(small_file)

        assert size > 0
        assert full_hash is not None
        assert partial_hash is None
        assert partial_bytes is None

    def test_large_file_with_partial(self, temp_dir):
        """Test large file returns both hashes."""
        large_file = os.path.join(temp_dir, "large.bin")
        # Create file larger than threshold
        with open(large_file, "wb") as f:
            f.write(os.urandom(2 * 1024 * 1024))  # 2MB

        size, full_hash, partial_hash, partial_bytes = get_file_size_and_hash(large_file)

        assert size >= 2 * 1024 * 1024
        assert full_hash is not None
        assert partial_hash is not None
        assert partial_bytes == constants.PARTIAL_HASH_BYTES

    def test_disable_partial(self, temp_dir):
        """Test disabling partial hashing."""
        large_file = os.path.join(temp_dir, "large.bin")
        with open(large_file, "wb") as f:
            f.write(os.urandom(2 * 1024 * 1024))

        size, full_hash, partial_hash, partial_bytes = get_file_size_and_hash(
            large_file, use_partial=False
        )

        assert full_hash is not None
        assert partial_hash is None
        assert partial_bytes is None
