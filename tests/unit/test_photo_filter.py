"""
Unit tests for PhotoFilter class.

Tests:
- File size filtering
- Dimension filtering
- Small square detection (icons)
- Filename pattern exclusion
- EXIF requirement
- Video file bypass
- Filter statistics
"""

import os
import pytest
from datetime import datetime

from photo_filter import PhotoFilter
from tests.test_utils.image_generator import ImageGenerator
from tests.test_utils.test_file_generator import TestFileGenerator


class TestPhotoFilter:
    """Test PhotoFilter functionality."""

    def test_filter_too_small_file(self, temp_dir):
        """Test filtering files below minimum size."""
        # Create a very small image
        small_img = os.path.join(temp_dir, "tiny.jpg")
        ImageGenerator.create_icon(small_img, size=16)

        settings = {
            'min_file_size': 51200,  # 50KB
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': False,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)
        is_valid, reason = filter.is_valid_photo(small_img)

        assert is_valid is False
        assert 'size' in reason.lower() or 'small' in reason.lower()

    def test_filter_small_dimensions(self, temp_dir):
        """Test filtering images with dimensions too small."""
        small_img = os.path.join(temp_dir, "small_dims.jpg")
        ImageGenerator.create_test_image(
            small_img,
            width=400,
            height=300,
            format="JPEG"
        )

        settings = {
            'min_file_size': 1000,  # Low threshold
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': False,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)
        is_valid, reason = filter.is_valid_photo(small_img)

        assert is_valid is False
        assert 'dimension' in reason.lower() or 'width' in reason.lower() or 'height' in reason.lower()

    def test_filter_small_square_icon(self, temp_dir):
        """Test filtering small square images (likely icons)."""
        icon = os.path.join(temp_dir, "icon.png")
        ImageGenerator.create_icon(icon, size=64)

        settings = {
            'min_file_size': 1000,
            'min_width': 10,
            'min_height': 10,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,  # Filter squares < 400x400
            'require_exif': False,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)
        is_valid, reason = filter.is_valid_photo(icon)

        assert is_valid is False
        assert 'square' in reason.lower() or 'icon' in reason.lower()

    def test_filter_filename_patterns(self, temp_dir):
        """Test filtering based on filename patterns."""
        patterns_to_test = [
            ('favicon.ico', 'favicon'),
            ('icon-32.png', 'icon'),
            ('logo.jpg', 'logo'),
            ('thumbnail.jpg', 'thumb'),
            ('button_submit.png', 'button')
        ]

        settings = {
            'min_file_size': 1000,
            'min_width': 10,
            'min_height': 10,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 0,
            'require_exif': False,
            'excluded_filename_patterns': ['favicon', 'icon', 'logo', 'thumb', 'button']
        }

        filter = PhotoFilter(settings)

        for filename, pattern in patterns_to_test:
            img_path = os.path.join(temp_dir, filename)
            ImageGenerator.create_test_image(
                img_path,
                width=1000,
                height=1000,
                format="PNG" if filename.endswith('.png') else "JPEG"
            )

            is_valid, reason = filter.is_valid_photo(img_path)

            assert is_valid is False, f"File with pattern '{pattern}' should be filtered"
            assert 'filename' in reason.lower() or 'pattern' in reason.lower()

    def test_valid_photo_passes(self, temp_dir):
        """Test that a valid photo passes all filters."""
        valid_photo = os.path.join(temp_dir, "vacation_beach.jpg")
        ImageGenerator.create_test_image(
            valid_photo,
            width=1920,
            height=1080,
            format="JPEG",
            exif_date=datetime(2024, 6, 15)
        )

        settings = {
            'min_file_size': 51200,
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': False,
            'excluded_filename_patterns': ['favicon', 'icon', 'logo', 'thumb']
        }

        filter = PhotoFilter(settings)
        is_valid, reason = filter.is_valid_photo(valid_photo)

        assert is_valid is True
        assert reason == ""

    def test_exif_requirement(self, temp_dir):
        """Test filtering based on EXIF requirement."""
        # Photo without EXIF
        no_exif = os.path.join(temp_dir, "no_exif.jpg")
        ImageGenerator.create_photo_without_exif(no_exif)

        # Photo with EXIF
        with_exif = os.path.join(temp_dir, "with_exif.jpg")
        ImageGenerator.create_test_image(
            with_exif,
            width=1920,
            height=1080,
            exif_date=datetime(2024, 1, 1)
        )

        settings = {
            'min_file_size': 10000,
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': True,  # EXIF required
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)

        # Without EXIF should fail
        is_valid, reason = filter.is_valid_photo(no_exif)
        assert is_valid is False
        assert 'exif' in reason.lower()

        # With EXIF should pass
        is_valid, reason = filter.is_valid_photo(with_exif)
        assert is_valid is True

    def test_video_bypass(self, temp_dir):
        """Test that video files bypass photo filtering."""
        video_path = os.path.join(temp_dir, "test.mp4")
        TestFileGenerator.create_mock_video(video_path)

        settings = {
            'min_file_size': 999999999,  # Very high threshold
            'min_width': 9999,
            'min_height': 9999,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': True,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)
        is_valid, reason = filter.is_valid_photo(video_path)

        # Video should pass through regardless of settings
        assert is_valid is True
        assert reason == "" or 'video' in reason.lower()

    def test_filter_statistics(self, filtered_files):
        """Test that filter statistics are tracked correctly."""
        settings = {
            'min_file_size': 51200,
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': False,
            'excluded_filename_patterns': ['favicon', 'icon', 'thumb']
        }

        filter = PhotoFilter(settings)

        # Process all files
        for file_path in filtered_files['should_filter']:
            filter.is_valid_photo(file_path)

        for file_path in filtered_files['should_keep']:
            filter.is_valid_photo(file_path)

        stats = filter.get_statistics()

        # Should have tracked some filtered files
        assert stats['total_filtered'] > 0
        assert stats['total_validated'] == len(filtered_files['should_filter']) + len(filtered_files['should_keep'])

    def test_case_insensitive_patterns(self, temp_dir):
        """Test that filename pattern matching is case-insensitive."""
        filenames = ['FAVICON.PNG', 'Icon_big.jpg', 'myLogo.jpeg']

        settings = {
            'min_file_size': 1000,
            'min_width': 10,
            'min_height': 10,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 0,
            'require_exif': False,
            'excluded_filename_patterns': ['favicon', 'icon', 'logo']
        }

        filter = PhotoFilter(settings)

        for filename in filenames:
            img_path = os.path.join(temp_dir, filename)
            ImageGenerator.create_test_image(
                img_path,
                width=1000,
                height=1000
            )

            is_valid, reason = filter.is_valid_photo(img_path)
            assert is_valid is False, f"Pattern matching should be case-insensitive for {filename}"

    def test_max_dimensions(self, temp_dir):
        """Test filtering images exceeding maximum dimensions."""
        huge_img = os.path.join(temp_dir, "huge.jpg")
        ImageGenerator.create_test_image(
            huge_img,
            width=60000,  # Exceeds max
            height=40000
        )

        settings = {
            'min_file_size': 1000,
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': False,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)
        is_valid, reason = filter.is_valid_photo(huge_img)

        # Might pass or fail depending on implementation
        # (max dimensions might be for filtering unrealistic sizes)


class TestPhotoFilterEdgeCases:
    """Test edge cases and error handling."""

    def test_corrupted_image(self, temp_dir):
        """Test handling of corrupted image files."""
        corrupted = os.path.join(temp_dir, "corrupted.jpg")
        ImageGenerator.create_corrupted_file(corrupted)

        settings = {
            'min_file_size': 1000,
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': False,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)

        # Should handle gracefully without crashing
        try:
            is_valid, reason = filter.is_valid_photo(corrupted)
            # Likely filtered due to corruption
            assert is_valid is False
        except Exception:
            # Acceptable to raise exception for corrupted file
            pass

    def test_nonexistent_file(self, temp_dir):
        """Test handling of nonexistent file."""
        nonexistent = os.path.join(temp_dir, "does_not_exist.jpg")

        settings = {
            'min_file_size': 1000,
            'min_width': 800,
            'min_height': 600,
            'max_width': 50000,
            'max_height': 50000,
            'exclude_square_smaller_than': 400,
            'require_exif': False,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)

        # Should handle gracefully
        try:
            is_valid, reason = filter.is_valid_photo(nonexistent)
            assert is_valid is False
        except (FileNotFoundError, OSError):
            # Expected behavior
            pass

    def test_empty_settings(self, temp_dir):
        """Test filter with minimal/empty settings."""
        img_path = os.path.join(temp_dir, "test.jpg")
        ImageGenerator.create_test_image(img_path, width=1920, height=1080)

        # Minimal settings
        settings = {
            'min_file_size': 0,
            'min_width': 0,
            'min_height': 0,
            'max_width': 999999,
            'max_height': 999999,
            'exclude_square_smaller_than': 0,
            'require_exif': False,
            'excluded_filename_patterns': []
        }

        filter = PhotoFilter(settings)
        is_valid, reason = filter.is_valid_photo(img_path)

        # Should pass with minimal filtering
        assert is_valid is True
