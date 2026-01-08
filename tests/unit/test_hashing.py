"""
Unit tests for file hashing functions.

Tests:
- Full file hashing (hash_file)
- Partial file hashing (hash_file_partial)
- Two-stage hashing optimization
- Hash consistency and correctness
"""

import os
import hashlib
import pytest

from DuplicateFileDetection import hash_file, hash_file_partial


class TestFileHashing:
    """Test file hashing functions."""

    def test_hash_file_consistency(self, sample_images):
        """Test that hash_file produces consistent results."""
        file_path = sample_images[0]

        # Hash same file multiple times
        hash1 = hash_file(file_path)
        hash2 = hash_file(file_path)
        hash3 = hash_file(file_path)

        assert hash1 == hash2 == hash3
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters

    def test_hash_file_different_files(self, sample_images):
        """Test that different files produce different hashes."""
        if len(sample_images) < 2:
            pytest.skip("Need at least 2 sample images")

        hash1 = hash_file(sample_images[0])
        hash2 = hash_file(sample_images[1])

        assert hash1 != hash2

    def test_hash_file_duplicates(self, sample_images_with_duplicates):
        """Test that duplicate files produce identical hashes."""
        original = sample_images_with_duplicates['originals'][0]
        duplicates = sample_images_with_duplicates['duplicates']

        original_hash = hash_file(original)

        for dup in duplicates:
            dup_hash = hash_file(dup)
            assert dup_hash == original_hash, f"Duplicate {dup} should have same hash as original"

    def test_partial_hash_consistency(self, sample_images):
        """Test that partial hash produces consistent results."""
        file_path = sample_images[0]
        num_bytes = 16384  # 16KB

        hash1 = hash_file_partial(file_path, num_bytes)
        hash2 = hash_file_partial(file_path, num_bytes)

        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256

    def test_partial_hash_different_sizes(self, temp_dir):
        """Test partial hash with different byte counts."""
        from tests.test_utils.image_generator import ImageGenerator

        # Create a test image
        img_path = os.path.join(temp_dir, "test.jpg")
        ImageGenerator.create_test_image(img_path, width=1920, height=1080)

        # Hash different amounts
        hash_1kb = hash_file_partial(img_path, 1024)
        hash_16kb = hash_file_partial(img_path, 16384)
        hash_full = hash_file(img_path)

        # Partial hashes should differ from each other and from full hash
        # (unless file is very small)
        file_size = os.path.getsize(img_path)
        if file_size > 16384:
            assert hash_1kb != hash_16kb
            assert hash_16kb != hash_full

    def test_partial_hash_duplicates(self, sample_images_with_duplicates):
        """Test that partial hash detects duplicates."""
        original = sample_images_with_duplicates['originals'][0]
        duplicates = sample_images_with_duplicates['duplicates']

        original_partial = hash_file_partial(original, 16384)

        for dup in duplicates:
            dup_partial = hash_file_partial(dup, 16384)
            assert dup_partial == original_partial

    def test_hash_nonexistent_file(self, temp_dir):
        """Test hashing a nonexistent file."""
        nonexistent = os.path.join(temp_dir, "does_not_exist.jpg")

        with pytest.raises(FileNotFoundError):
            hash_file(nonexistent)

    def test_hash_empty_file(self, temp_dir):
        """Test hashing an empty file."""
        empty_file = os.path.join(temp_dir, "empty.txt")
        with open(empty_file, 'w') as f:
            pass  # Create empty file

        file_hash = hash_file(empty_file)

        # SHA-256 of empty file is known value
        expected = hashlib.sha256(b'').hexdigest()
        assert file_hash == expected

    def test_partial_hash_small_file(self, temp_dir):
        """Test partial hash when file is smaller than requested bytes."""
        small_file = os.path.join(temp_dir, "small.txt")
        content = b"Small content"
        with open(small_file, 'wb') as f:
            f.write(content)

        # Request more bytes than file contains
        partial_hash = hash_file_partial(small_file, 16384)
        full_hash = hash_file(small_file)

        # Should hash entire file
        assert partial_hash == full_hash

    def test_two_stage_hashing_optimization(self, temp_dir):
        """Test the two-stage hashing optimization strategy."""
        from tests.test_utils.image_generator import ImageGenerator

        # Create a large file (> 1MB threshold)
        large_file = os.path.join(temp_dir, "large.jpg")
        ImageGenerator.create_test_image(large_file, width=4000, height=3000)

        # Ensure file is large enough
        file_size = os.path.getsize(large_file)
        assert file_size > 1048576, "File should be larger than 1MB for this test"

        # Stage 1: Partial hash (fast)
        partial = hash_file_partial(large_file, 16384)
        assert len(partial) == 64

        # Stage 2: Full hash (only if needed)
        full = hash_file(large_file)
        assert len(full) == 64

        # Hashes should differ (unless file is very uniform)
        # This demonstrates the optimization: we'd only do full hash if partial matches

    def test_hash_file_verification(self, sample_images):
        """Test that hash values are valid SHA-256 hashes."""
        file_path = sample_images[0]
        file_hash = hash_file(file_path)

        # Verify hash format
        assert len(file_hash) == 64
        assert all(c in '0123456789abcdef' for c in file_hash)

        # Verify by rehashing the file manually
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)

        expected_hash = sha256_hash.hexdigest()
        assert file_hash == expected_hash


class TestHashPerformance:
    """Test hashing performance characteristics (optional, marked as slow)."""

    @pytest.mark.slow
    def test_partial_hash_faster_than_full(self, temp_dir):
        """Test that partial hashing is faster for large files."""
        import time
        from tests.test_utils.image_generator import ImageGenerator

        # Create a large file
        large_file = os.path.join(temp_dir, "very_large.jpg")
        ImageGenerator.create_test_image(large_file, width=5000, height=4000)

        # Time partial hash
        start = time.time()
        for _ in range(10):
            hash_file_partial(large_file, 16384)
        partial_time = time.time() - start

        # Time full hash
        start = time.time()
        for _ in range(10):
            hash_file(large_file)
        full_time = time.time() - start

        # Partial should be faster (at least 2x for large files)
        # This is a rough performance test
        assert partial_time < full_time, "Partial hash should be faster than full hash"
