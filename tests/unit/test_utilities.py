"""
Unit tests for utility functions.

Tests:
- unique filename generation
- directory creation
- file size formatting
- settings validation
- organization template parsing
- filename template parsing
"""

import os
import pytest

from utils import (
    ensure_directory_exists,
    get_unique_filename,
    format_file_size
)
from organization_template import OrganizationTemplate
from filename_template import FilenameTemplate
from datetime import datetime


class TestDirectoryOperations:
    """Test directory-related utility functions."""

    def test_ensure_directory_exists_creates_new(self, temp_dir):
        """Test creating a new directory."""
        new_dir = os.path.join(temp_dir, "new", "nested", "directory")

        assert not os.path.exists(new_dir)

        ensure_directory_exists(new_dir)

        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)

    def test_ensure_directory_exists_existing(self, temp_dir):
        """Test with existing directory."""
        existing_dir = os.path.join(temp_dir, "existing")
        os.makedirs(existing_dir)

        # Should not raise error
        ensure_directory_exists(existing_dir)

        assert os.path.exists(existing_dir)

    def test_ensure_directory_exists_nested(self, temp_dir):
        """Test creating deeply nested directories."""
        nested = os.path.join(temp_dir, "a", "b", "c", "d", "e")

        ensure_directory_exists(nested)

        assert os.path.exists(nested)
        assert os.path.isdir(nested)


class TestUniqueFilename:
    """Test unique filename generation."""

    def test_unique_filename_no_collision(self, temp_dir):
        """Test when no collision exists."""
        test_path = os.path.join(temp_dir, "test.jpg")

        unique_path = get_unique_filename(test_path)

        assert unique_path == test_path

    def test_unique_filename_single_collision(self, temp_dir):
        """Test with one existing file."""
        original = os.path.join(temp_dir, "photo.jpg")

        # Create the original file
        with open(original, 'w') as f:
            f.write("original")

        unique_path = get_unique_filename(original)

        expected = os.path.join(temp_dir, "photo_1.jpg")
        assert unique_path == expected
        assert not os.path.exists(unique_path)  # Should not create the file

    def test_unique_filename_multiple_collisions(self, temp_dir):
        """Test with multiple existing files."""
        base_path = os.path.join(temp_dir, "image.jpg")

        # Create multiple versions
        for i in range(5):
            if i == 0:
                path = base_path
            else:
                path = os.path.join(temp_dir, f"image_{i}.jpg")
            with open(path, 'w') as f:
                f.write(f"version {i}")

        unique_path = get_unique_filename(base_path)

        expected = os.path.join(temp_dir, "image_5.jpg")
        assert unique_path == expected

    def test_unique_filename_preserves_extension(self, temp_dir):
        """Test that file extension is preserved."""
        extensions = ['.jpg', '.png', '.JPEG', '.tif', '.mp4']

        for ext in extensions:
            file_path = os.path.join(temp_dir, f"file{ext}")
            with open(file_path, 'w') as f:
                f.write("test")

            unique_path = get_unique_filename(file_path)

            assert unique_path.endswith(ext)

    def test_unique_filename_no_extension(self, temp_dir):
        """Test with filename without extension."""
        file_path = os.path.join(temp_dir, "noextension")
        with open(file_path, 'w') as f:
            f.write("test")

        unique_path = get_unique_filename(file_path)

        expected = os.path.join(temp_dir, "noextension_1")
        assert unique_path == expected


class TestFileSizeFormatting:
    """Test file size formatting utility."""

    def test_format_bytes(self):
        """Test formatting bytes."""
        assert "500 B" in format_file_size(500)
        assert "1023 B" in format_file_size(1023)

    def test_format_kilobytes(self):
        """Test formatting kilobytes."""
        result = format_file_size(1024)
        assert "KB" in result or "KiB" in result

        result = format_file_size(50 * 1024)
        assert "50" in result
        assert "KB" in result or "KiB" in result

    def test_format_megabytes(self):
        """Test formatting megabytes."""
        result = format_file_size(5 * 1024 * 1024)
        assert "5" in result
        assert "MB" in result or "MiB" in result

    def test_format_gigabytes(self):
        """Test formatting gigabytes."""
        result = format_file_size(3 * 1024 * 1024 * 1024)
        assert "3" in result
        assert "GB" in result or "GiB" in result

    def test_format_zero(self):
        """Test formatting zero bytes."""
        result = format_file_size(0)
        assert "0" in result

    def test_format_large_number(self):
        """Test formatting very large sizes."""
        result = format_file_size(10 * 1024 * 1024 * 1024 * 1024)  # 10 TB
        # Should handle without error
        assert result is not None


class TestOrganizationTemplate:
    """Test organization template parsing."""

    def test_by_day_template(self):
        """Test year/month/day organization."""
        template = "{year}/{month}/{day}"
        test_date = datetime(2024, 6, 15)

        result = OrganizationTemplate.parse(template, test_date)

        assert result == "2024/06/15"

    def test_by_month_template(self):
        """Test year/month organization."""
        template = "{year}/{month}"
        test_date = datetime(2024, 6, 15)

        result = OrganizationTemplate.parse(template, test_date)

        assert result == "2024/06"

    def test_by_year_template(self):
        """Test year-only organization."""
        template = "{year}"
        test_date = datetime(2024, 6, 15)

        result = OrganizationTemplate.parse(template, test_date)

        assert result == "2024"

    def test_month_name_template(self):
        """Test month name in template."""
        template = "{year}/{month_name}"
        test_date = datetime(2024, 6, 15)

        result = OrganizationTemplate.parse(template, test_date)

        assert "2024" in result
        assert "June" in result

    def test_month_short_name_template(self):
        """Test short month name."""
        template = "{year}/{month_sname}"
        test_date = datetime(2024, 6, 15)

        result = OrganizationTemplate.parse(template, test_date)

        assert "2024" in result
        assert "Jun" in result

    def test_template_validation(self):
        """Test template validation."""
        # Valid templates
        valid = [
            "{year}/{month}/{day}",
            "{year}/{month}",
            "{year}",
            "{year}/{month_name}",
            "{year}/{month_sname}/{day_sname}"
        ]

        for template in valid:
            errors = OrganizationTemplate.validate(template)
            assert len(errors) == 0, f"Template {template} should be valid"

    def test_invalid_template(self):
        """Test invalid template detection."""
        # Templates with path traversal
        invalid = [
            "../{year}",
            "{year}/../../etc",
            "/absolute/path/{year}"
        ]

        for template in invalid:
            errors = OrganizationTemplate.validate(template)
            assert len(errors) > 0, f"Template {template} should be invalid"

    def test_case_insensitive_placeholders(self):
        """Test that placeholders are case-insensitive."""
        templates = [
            "{year}/{month}/{day}",
            "{YEAR}/{MONTH}/{DAY}",
            "{Year}/{Month}/{Day}",
            "{YeAr}/{MoNtH}/{DaY}"
        ]

        test_date = datetime(2024, 6, 15)

        for template in templates:
            result = OrganizationTemplate.parse(template, test_date)
            assert result == "2024/06/15", f"Template {template} should produce same result"


class TestFilenameTemplate:
    """Test filename template parsing."""

    def test_original_name_template(self):
        """Test preserving original filename."""
        template = "{original_name}"

        result = FilenameTemplate.parse(
            template,
            file_date=datetime(2024, 1, 1),
            original_filename="vacation_beach.jpg",
            counter=1
        )

        assert result == "vacation_beach.jpg"

    def test_date_based_template(self):
        """Test date-based filename."""
        template = "{year}{month}{day}_{hour}{minute}{second}"
        test_date = datetime(2024, 6, 15, 14, 30, 45)

        result = FilenameTemplate.parse(
            template,
            file_date=test_date,
            original_filename="photo.jpg",
            counter=1
        )

        assert "20240615_143045" in result

    def test_counter_template(self):
        """Test sequential counter."""
        template = "photo_{counter:04d}"

        result = FilenameTemplate.parse(
            template,
            file_date=datetime(2024, 1, 1),
            original_filename="IMG_001.jpg",
            counter=42
        )

        assert "photo_0042" in result

    def test_template_validation(self):
        """Test filename template validation."""
        # Valid templates
        valid = [
            "{original_name}",
            "{year}-{month}-{day}_{counter:03d}",
            "{year}_{month_name}_{day_name}"
        ]

        for template in valid:
            errors = FilenameTemplate.validate(template)
            assert len(errors) == 0, f"Template {template} should be valid"

    def test_dangerous_characters_blocked(self):
        """Test that dangerous characters are blocked."""
        invalid = [
            "{year}/../file",
            "file<test>",
            "file:name",
            "file|name",
            "file?name"
        ]

        for template in invalid:
            errors = FilenameTemplate.validate(template)
            assert len(errors) > 0, f"Template {template} should be invalid"

    def test_case_insensitive_placeholders(self):
        """Test case-insensitive placeholders."""
        templates = [
            "{year}_{month}_{day}",
            "{YEAR}_{MONTH}_{DAY}",
            "{Year}_{Month}_{Day}"
        ]

        test_date = datetime(2024, 6, 15)

        for template in templates:
            result = FilenameTemplate.parse(
                template,
                file_date=test_date,
                original_filename="test.jpg",
                counter=1
            )
            assert "2024_06_15" in result
