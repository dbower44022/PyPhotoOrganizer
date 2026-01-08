"""
Example test file demonstrating test patterns and fixtures.

This file shows how to write tests for PyPhotoOrganizer.
Use this as a template for creating new tests.
"""

import os
import pytest
from datetime import datetime

from DuplicateFileDetection import hash_file, get_creation_date
from tests.test_utils.image_generator import ImageGenerator


class TestExampleBasicUsage:
    """Examples of basic test patterns."""

    def test_simple_assertion(self):
        """Most basic test - simple assertion."""
        result = 2 + 2
        assert result == 4

    def test_with_temp_directory(self, temp_dir):
        """Example using temp_dir fixture."""
        # temp_dir is automatically created and cleaned up
        test_file = os.path.join(temp_dir, "test.txt")

        with open(test_file, 'w') as f:
            f.write("Hello, World!")

        assert os.path.exists(test_file)

        # No cleanup needed - fixture handles it

    def test_with_source_and_dest_dirs(self, source_dir, dest_dir):
        """Example using source and destination directory fixtures."""
        # Both directories are created and will be cleaned up automatically
        assert os.path.exists(source_dir)
        assert os.path.exists(dest_dir)
        assert source_dir != dest_dir


class TestExampleImageGeneration:
    """Examples of generating test images."""

    def test_create_simple_image(self, temp_dir):
        """Example: Create a simple test image."""
        img_path = os.path.join(temp_dir, "photo.jpg")

        ImageGenerator.create_test_image(
            path=img_path,
            width=1920,
            height=1080,
            format="JPEG"
        )

        assert os.path.exists(img_path)
        assert os.path.getsize(img_path) > 0

    def test_create_image_with_exif(self, temp_dir):
        """Example: Create image with specific EXIF date."""
        img_path = os.path.join(temp_dir, "vacation.jpg")
        test_date = datetime(2024, 7, 15, 14, 30, 0)

        ImageGenerator.create_test_image(
            path=img_path,
            text="Summer Vacation",
            exif_date=test_date,
            camera_make="Canon",
            camera_model="EOS R5"
        )

        # Verify EXIF was embedded
        year, month, day, date_source, is_reliable = get_creation_date(img_path)

        assert year == "2024"
        assert month == "07"
        assert day == "15"
        assert date_source == "exif"

    def test_create_photo_series(self, temp_dir):
        """Example: Create a series of photos."""
        start_date = datetime(2024, 6, 1)

        files = ImageGenerator.create_photo_series(
            base_path=temp_dir,
            count=10,
            start_date=start_date,
            prefix="PHOTO"
        )

        assert len(files) == 10

        for i, file_path in enumerate(files):
            assert os.path.exists(file_path)
            assert f"PHOTO_{i+1:04d}.jpg" in file_path


class TestExampleDatabaseOperations:
    """Examples of database testing."""

    def test_with_empty_database(self, empty_database):
        """Example: Using empty database fixture."""
        from database_metadata import DatabaseMetadata

        metadata = DatabaseMetadata(empty_database)

        # Database is initialized and ready to use
        assert os.path.exists(empty_database)

    def test_with_populated_database(self, populated_database):
        """Example: Using pre-populated database fixture."""
        from DuplicateFileDetection import PhotoDatabase

        with PhotoDatabase(populated_database) as db:
            hashes = db.get_all_hashes()

            # Fixture creates database with sample data
            assert len(hashes) > 0


class TestExampleTestScenarios:
    """Examples of using predefined test scenarios."""

    def test_simple_scenario(self, simple_scenario):
        """Example: Using simple scenario fixture."""
        # simple_scenario contains a few test files
        files = simple_scenario['files']

        assert len(files) == 5
        assert simple_scenario['expected_unique'] == 5
        assert simple_scenario['expected_duplicates'] == 0

    def test_duplicates_scenario(self, duplicates_scenario):
        """Example: Using duplicates scenario fixture."""
        # duplicates_scenario includes duplicate files
        original = duplicates_scenario['original']
        duplicates = duplicates_scenario['duplicates']

        # Hash them and verify they match
        original_hash = hash_file(original)

        for dup in duplicates:
            dup_hash = hash_file(dup)
            assert dup_hash == original_hash


class TestExampleParametrization:
    """Examples of parameterized tests."""

    @pytest.mark.parametrize("width,height,should_pass", [
        (1920, 1080, True),   # Valid photo size
        (800, 600, True),     # Minimum valid size
        (100, 100, False),    # Too small
        (64, 64, False),      # Icon size
    ])
    def test_dimension_filtering(self, temp_dir, width, height, should_pass):
        """Example: Parameterized test for dimension filtering."""
        img_path = os.path.join(temp_dir, f"test_{width}x{height}.jpg")

        ImageGenerator.create_test_image(
            img_path,
            width=width,
            height=height
        )

        # Test filtering logic here
        assert os.path.exists(img_path)

    @pytest.mark.parametrize("year,is_suspicious", [
        (2024, False),   # Current year - valid
        (2020, False),   # Recent year - valid
        (1985, True),    # Before digital cameras - suspicious
        (2030, True),    # Future year - suspicious
        (1970, True),    # Unix epoch - suspicious
    ])
    def test_date_reliability(self, temp_dir, year, is_suspicious):
        """Example: Parameterized test for date reliability."""
        img_path = os.path.join(temp_dir, f"photo_{year}.jpg")
        test_date = datetime(year, 6, 15)

        ImageGenerator.create_test_image(
            img_path,
            exif_date=test_date
        )

        _, _, _, _, is_reliable = get_creation_date(img_path)

        # Suspicious dates should be marked unreliable
        assert is_reliable != is_suspicious


class TestExampleErrorHandling:
    """Examples of testing error conditions."""

    def test_nonexistent_file(self):
        """Example: Test handling of nonexistent file."""
        with pytest.raises(FileNotFoundError):
            hash_file("/path/that/does/not/exist.jpg")

    def test_corrupted_file(self, temp_dir):
        """Example: Test handling of corrupted file."""
        corrupted_path = os.path.join(temp_dir, "corrupted.jpg")

        ImageGenerator.create_corrupted_file(corrupted_path)

        # Function should handle gracefully
        year, month, day, date_source, is_reliable = get_creation_date(corrupted_path)

        # Should fall back to OS metadata or year 1000
        assert date_source in ["os_metadata", "fallback"]
        assert is_reliable is False


class TestExampleMarkers:
    """Examples of using test markers."""

    @pytest.mark.slow
    def test_large_dataset(self, source_dir):
        """Example: Mark slow test."""
        # Create many files (takes time)
        for i in range(100):
            img_path = os.path.join(source_dir, f"photo_{i}.jpg")
            ImageGenerator.create_test_image(img_path)

        # Test processing large dataset...

    @pytest.mark.requires_ffmpeg
    def test_video_processing(self, temp_dir):
        """Example: Mark test requiring external dependency."""
        from tests.test_utils.test_file_generator import TestFileGenerator

        video_path = os.path.join(temp_dir, "test.mp4")
        TestFileGenerator.create_mock_video(video_path)

        # Test video processing...


class TestExampleFixtureCombinations:
    """Examples of combining multiple fixtures."""

    def test_with_multiple_fixtures(
        self,
        source_dir,
        dest_dir,
        test_db_path,
        default_settings,
        image_generator
    ):
        """Example: Using multiple fixtures together."""
        # Create test images in source
        for i in range(3):
            img_path = os.path.join(source_dir, f"photo_{i}.jpg")
            image_generator.create_test_image(
                img_path,
                exif_date=datetime(2024, 6, i+1)
            )

        # Initialize database
        from database_metadata import DatabaseMetadata
        DatabaseMetadata.create_database(test_db_path)

        # Process files using settings
        from DuplicateFileDetection import get_file_list

        file_list = get_file_list([source_dir], default_settings)

        assert len(file_list) == 3


# To run just this example file:
# pytest tests/test_example.py -v

# To run a specific test class:
# pytest tests/test_example.py::TestExampleBasicUsage -v

# To run a specific test:
# pytest tests/test_example.py::TestExampleBasicUsage::test_simple_assertion -v

# To run with coverage:
# pytest tests/test_example.py --cov=. --cov-report=html
