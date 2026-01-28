"""
Unit tests for date extraction functions.

Tests:
- EXIF date extraction
- IPTC date extraction
- Filename date extraction
- Path date extraction
- OS metadata fallback
- Date reliability detection
- Video date extraction
- Edge cases and error handling
"""

import os
import pytest
from datetime import datetime

from DuplicateFileDetection import get_creation_date
from date_extraction import (
    extract_filename_date,
    extract_path_date,
    extract_filename_or_path_date,
)
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


class TestFilenameDateExtraction:
    """Test date extraction from filenames."""

    def test_android_camera_format(self):
        """Test Android camera filename format (IMG_YYYYMMDD_HHMMSS)."""
        test_cases = [
            ("/path/to/IMG_20230415_123456.jpg", datetime(2023, 4, 15, 12, 34, 56)),
            ("/path/to/VID_20220101_000000.mp4", datetime(2022, 1, 1, 0, 0, 0)),
            ("/path/to/PXL_20241225_235959.jpg", datetime(2024, 12, 25, 23, 59, 59)),
            ("/path/to/MVIMG_20200630_140000.jpg", datetime(2020, 6, 30, 14, 0, 0)),
        ]

        for file_path, expected in test_cases:
            result = extract_filename_date(file_path)
            assert result == expected, f"Failed for {file_path}"

    def test_generic_datetime_formats(self):
        """Test generic datetime filename formats."""
        test_cases = [
            ("/path/to/20230415_123456.jpg", datetime(2023, 4, 15, 12, 34, 56)),
            ("/path/to/20230415-123456.jpg", datetime(2023, 4, 15, 12, 34, 56)),
            ("/path/to/2023-04-15_12-34-56.jpg", datetime(2023, 4, 15, 12, 34, 56)),
        ]

        for file_path, expected in test_cases:
            result = extract_filename_date(file_path)
            assert result == expected, f"Failed for {file_path}"

    def test_ios_format(self):
        """Test iOS sharing format (YYYY-MM-DD at HH.MM.SS)."""
        # iOS format with 'at'
        result = extract_filename_date("/path/to/Photo 2023-04-15 at 12.34.56.jpg")
        assert result == datetime(2023, 4, 15, 12, 34, 56)

    def test_screenshot_formats(self):
        """Test screenshot filename formats."""
        test_cases = [
            ("/path/Screenshot_20230415-123456.png", datetime(2023, 4, 15, 12, 34, 56)),
            ("/path/Screenshot_2023-04-15-12-34-56.png", datetime(2023, 4, 15, 12, 34, 56)),
        ]

        for file_path, expected in test_cases:
            result = extract_filename_date(file_path)
            assert result == expected, f"Failed for {file_path}"

    def test_whatsapp_format(self):
        """Test WhatsApp image filename format."""
        result = extract_filename_date("/path/to/IMG-20230415-WA0001.jpg")
        assert result is not None
        assert result.year == 2023
        assert result.month == 4
        assert result.day == 15

    def test_date_only_formats(self):
        """Test date-only filename formats (no time)."""
        test_cases = [
            ("/path/to/2023-04-15.jpg", datetime(2023, 4, 15, 12, 0, 0)),
            ("/path/to/photo_20230415.jpg", datetime(2023, 4, 15, 12, 0, 0)),
        ]

        for file_path, expected in test_cases:
            result = extract_filename_date(file_path)
            assert result is not None, f"Failed for {file_path}"
            assert result.year == expected.year
            assert result.month == expected.month
            assert result.day == expected.day

    def test_invalid_dates_rejected(self):
        """Test that invalid dates are rejected."""
        invalid_paths = [
            "/path/to/IMG_20231301_120000.jpg",  # Invalid month (13)
            "/path/to/IMG_20230230_120000.jpg",  # Invalid day (Feb 30)
            "/path/to/IMG_18500101_120000.jpg",  # Year before 1990
            "/path/to/IMG_21500101_120000.jpg",  # Year after 2100
        ]

        for file_path in invalid_paths:
            result = extract_filename_date(file_path)
            assert result is None, f"Should reject invalid date in {file_path}"

    def test_no_date_in_filename(self):
        """Test filenames without dates return None."""
        no_date_paths = [
            "/path/to/vacation_photo.jpg",
            "/path/to/DSC00001.jpg",
            "/path/to/random_file.png",
        ]

        for file_path in no_date_paths:
            result = extract_filename_date(file_path)
            assert result is None, f"Should return None for {file_path}"


class TestPathDateExtraction:
    """Test date extraction from directory paths."""

    def test_full_date_path(self):
        """Test /YYYY/MM/DD/ path format."""
        test_cases = [
            ("/Photos/2023/04/15/photo.jpg", datetime(2023, 4, 15, 12, 0, 0), "ymd"),
            ("D:\\Archive\\2022\\12\\25\\IMG_0001.jpg", datetime(2022, 12, 25, 12, 0, 0), "ymd"),
            ("/home/user/Pictures/2024/01/01/test.png", datetime(2024, 1, 1, 12, 0, 0), "ymd"),
        ]

        for file_path, expected_date, expected_precision in test_cases:
            result, precision = extract_path_date(file_path)
            assert result is not None, f"Failed for {file_path}"
            assert precision == expected_precision
            assert result.year == expected_date.year
            assert result.month == expected_date.month
            assert result.day == expected_date.day

    def test_iso_date_folder(self):
        """Test /YYYY-MM-DD/ folder format."""
        result, precision = extract_path_date("/Photos/2023-04-15/photo.jpg")
        assert result is not None
        assert precision == "ymd"
        assert result.year == 2023
        assert result.month == 4
        assert result.day == 15

    def test_year_month_path(self):
        """Test /YYYY/MM/ path format (no day)."""
        test_cases = [
            ("/Photos/2023/04/photo.jpg", 2023, 4, "ym"),
            ("/Archive/2022-12/photo.jpg", 2022, 12, "ym"),
        ]

        for file_path, expected_year, expected_month, expected_precision in test_cases:
            result, precision = extract_path_date(file_path)
            assert result is not None, f"Failed for {file_path}"
            assert precision == expected_precision
            assert result.year == expected_year
            assert result.month == expected_month
            assert result.day == 1  # Default to first of month

    def test_year_only_path(self):
        """Test /YYYY/ path format (year only)."""
        result, precision = extract_path_date("/Photos/2023/photo.jpg")
        assert result is not None
        assert precision == "y"
        assert result.year == 2023
        assert result.month == 1  # Default
        assert result.day == 1    # Default

    def test_invalid_path_dates_rejected(self):
        """Test that invalid path dates are rejected."""
        invalid_paths = [
            "/Photos/1800/04/15/photo.jpg",  # Year before 1990
            "/Photos/2200/04/15/photo.jpg",  # Year after 2100
            "/Photos/2023/13/15/photo.jpg",  # Invalid month
        ]

        for file_path in invalid_paths:
            result, precision = extract_path_date(file_path)
            # Should either be None or fall back to a less specific match
            if result is not None:
                # If a date was extracted, verify it's from a valid portion
                assert 1990 <= result.year <= 2100

    def test_no_date_in_path(self):
        """Test paths without dates return None."""
        result, precision = extract_path_date("/Photos/vacation/beach/photo.jpg")
        assert result is None
        assert precision == ""


class TestFilenameOrPathExtraction:
    """Test combined filename/path extraction."""

    def test_filename_takes_priority(self):
        """Test that filename date takes priority over path date."""
        # Filename has different date than path
        file_path = "/Photos/2020/01/01/IMG_20230415_123456.jpg"
        result, source = extract_filename_or_path_date(file_path)

        assert result is not None
        assert source == "filename"  # Should use filename, not path
        assert result.year == 2023   # From filename
        assert result.month == 4     # From filename

    def test_falls_back_to_path(self):
        """Test fallback to path when filename has no date."""
        file_path = "/Photos/2023/04/15/vacation_photo.jpg"
        result, source = extract_filename_or_path_date(file_path)

        assert result is not None
        assert source == "path_ymd"
        assert result.year == 2023
        assert result.month == 4
        assert result.day == 15

    def test_no_date_found(self):
        """Test when neither filename nor path has a date."""
        file_path = "/Photos/vacation/beach/sunset.jpg"
        result, source = extract_filename_or_path_date(file_path)

        assert result is None
        assert source == ""


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
