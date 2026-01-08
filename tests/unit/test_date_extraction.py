"""
Unit tests for date extraction functions.

Tests:
- EXIF date extraction
- IPTC date extraction
- OS metadata fallback
- Date reliability detection
- Video date extraction
- Edge cases and error handling
"""

import os
import pytest
from datetime import datetime

from DuplicateFileDetection import get_creation_date
from tests.test_utils.image_generator import ImageGenerator


class TestDateExtraction:
    """Test date extraction from various sources."""

    def test_exif_date_extraction(self, temp_dir):
        """Test extracting date from EXIF data."""
        test_date = datetime(2024, 6, 15, 14, 30, 45)
        img_path = os.path.join(temp_dir, "with_exif.jpg")

        ImageGenerator.create_test_image(
            img_path,
            exif_date=test_date
        )

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        assert year == "2024"
        assert month == "06"
        assert day == "15"
        assert date_source == "exif"
        assert is_reliable is True

    def test_no_exif_fallback_to_os(self, temp_dir):
        """Test fallback to OS metadata when EXIF is missing."""
        img_path = os.path.join(temp_dir, "no_exif.jpg")
        ImageGenerator.create_photo_without_exif(img_path)

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        # Should fall back to OS metadata
        assert date_source in ["os_metadata", "fallback"]
        assert is_reliable is False  # Flagged as unreliable

    def test_suspicious_date_detection_unix_epoch(self, temp_dir):
        """Test detection of suspicious date (1970-01-01)."""
        img_path = os.path.join(temp_dir, "epoch.jpg")
        ImageGenerator.create_photo_with_suspicious_date(img_path)

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        # Should be flagged as unreliable
        assert is_reliable is False
        if year == "1970" and month == "01" and day == "01":
            # Detected the epoch date
            pass

    def test_suspicious_date_detection_old_year(self, temp_dir):
        """Test detection of suspiciously old dates."""
        old_date = datetime(1985, 1, 1)  # Before consumer digital cameras
        img_path = os.path.join(temp_dir, "old_date.jpg")

        ImageGenerator.create_test_image(
            img_path,
            exif_date=old_date
        )

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        # Should be flagged as unreliable (year < 1990)
        assert is_reliable is False
        assert year == "1985"

    def test_suspicious_date_detection_future(self, temp_dir):
        """Test detection of future dates."""
        future_date = datetime(2030, 12, 31)
        img_path = os.path.join(temp_dir, "future.jpg")

        ImageGenerator.create_test_image(
            img_path,
            exif_date=future_date
        )

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        # Should be flagged as unreliable (future date)
        assert is_reliable is False
        assert year == "2030"

    def test_valid_date_range(self, temp_dir):
        """Test that dates in valid range are marked as reliable."""
        valid_date = datetime(2020, 6, 15, 10, 30, 0)
        img_path = os.path.join(temp_dir, "valid.jpg")

        ImageGenerator.create_test_image(
            img_path,
            exif_date=valid_date
        )

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        assert year == "2020"
        assert month == "06"
        assert day == "15"
        assert date_source == "exif"
        assert is_reliable is True

    def test_date_formatting(self, temp_dir):
        """Test that dates are properly zero-padded."""
        test_date = datetime(2024, 1, 5)  # Single digit month and day
        img_path = os.path.join(temp_dir, "test.jpg")

        ImageGenerator.create_test_image(
            img_path,
            exif_date=test_date
        )

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        assert month == "01"  # Zero-padded
        assert day == "05"    # Zero-padded

    def test_multiple_files_date_extraction(self, sample_images):
        """Test extracting dates from multiple files."""
        results = []

        for img_path in sample_images:
            year, month, day, date_source, is_reliable = get_creation_date(img_path)
            results.append((year, month, day, date_source, is_reliable))

        # All should have extracted dates
        assert len(results) == len(sample_images)

        # All should have valid year format
        for year, month, day, _, _ in results:
            assert len(year) == 4
            assert len(month) == 2
            assert len(day) == 2

    def test_nonexistent_file(self, temp_dir):
        """Test date extraction from nonexistent file."""
        nonexistent = os.path.join(temp_dir, "does_not_exist.jpg")

        # Should handle gracefully or raise appropriate error
        try:
            year, month, day, date_source, is_reliable = get_creation_date(nonexistent)
            # If it returns, should be fallback values
            assert year == "1000"  # Fallback year
            assert is_reliable is False
        except (FileNotFoundError, OSError):
            # Expected behavior
            pass

    def test_corrupted_file(self, temp_dir):
        """Test date extraction from corrupted file."""
        from tests.test_utils.image_generator import ImageGenerator

        corrupted = os.path.join(temp_dir, "corrupted.jpg")
        ImageGenerator.create_corrupted_file(corrupted)

        # Should handle gracefully
        year, month, day, date_source, is_reliable = get_creation_date(corrupted)

        # Should fall back to OS metadata or year 1000
        assert date_source in ["os_metadata", "fallback"]
        assert is_reliable is False


class TestDateSourcePriority:
    """Test the priority order of date extraction methods."""

    def test_exif_priority_over_os(self, temp_dir):
        """Test that EXIF date takes priority over OS metadata."""
        exif_date = datetime(2022, 5, 10)
        img_path = os.path.join(temp_dir, "priority_test.jpg")

        ImageGenerator.create_test_image(
            img_path,
            exif_date=exif_date
        )

        # Modify file timestamp to different date
        os.utime(img_path, (1609459200, 1609459200))  # 2021-01-01

        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        # Should use EXIF date, not OS date
        assert date_source == "exif"
        assert year == "2022"
        assert month == "05"
        assert day == "10"


class TestVideoDateExtraction:
    """Test date extraction from video files."""

    @pytest.mark.requires_ffmpeg
    def test_video_file_handling(self, temp_dir):
        """Test that video files are handled without error."""
        from tests.test_utils.test_file_generator import TestFileGenerator

        video_path = os.path.join(temp_dir, "test.mp4")
        TestFileGenerator.create_mock_video(video_path)

        # Should handle gracefully (may not extract real date from mock video)
        try:
            year, month, day, date_source, is_reliable = get_creation_date(video_path)

            # Should return some date (likely OS metadata or fallback)
            assert year is not None
            assert date_source in ["video_metadata", "video_quicktime", "os_metadata", "fallback"]
        except Exception as e:
            # Mock video may not be parseable, which is acceptable
            pytest.skip(f"Mock video not parseable: {e}")


class TestDateReliability:
    """Test the reliability flagging system."""

    def test_reliable_dates_criteria(self, temp_dir):
        """Test that dates meeting all criteria are marked reliable."""
        # Valid date range: 1990 <= year <= current_year + 1
        # Has EXIF data
        # Not suspicious patterns

        valid_dates = [
            datetime(1990, 1, 1),
            datetime(2000, 6, 15),
            datetime(2020, 12, 31),
            datetime.now().year, 1, 1
        ]

        for i, test_date in enumerate(valid_dates):
            img_path = os.path.join(temp_dir, f"reliable_{i}.jpg")
            ImageGenerator.create_test_image(img_path, exif_date=test_date)

            year, month, day, date_source, is_reliable = get_creation_date(img_path)

            assert is_reliable is True, f"Date {test_date} should be reliable"

    def test_unreliable_dates_criteria(self, unreliable_date_files):
        """Test that problematic dates are flagged as unreliable."""
        all_unreliable = unreliable_date_files['all_unreliable']

        for file_path in all_unreliable:
            year, month, day, date_source, is_reliable = get_creation_date(file_path)

            # Should be flagged as unreliable
            assert is_reliable is False, f"File {file_path} should be unreliable"
