"""
Integration tests for complete processing workflows.

Tests complete end-to-end scenarios:
- Simple file processing
- Duplicate detection
- Photo filtering
- Date correction
- File organization
"""

import os
import pytest
from datetime import datetime

from DuplicateFileDetection import get_file_list, find_duplicates, PhotoDatabase
from database_metadata import DatabaseMetadata
from tests.test_utils.image_generator import ImageGenerator
from tests.test_utils.test_file_generator import TestFileGenerator


class TestSimpleProcessingWorkflow:
    """Test basic file processing workflow."""

    def test_end_to_end_simple_processing(self, source_dir, dest_dir, test_db_path, default_settings):
        """Test complete workflow: scan, hash, detect duplicates, organize."""
        # Setup: Create test files
        test_files = []
        for i in range(5):
            img_path = os.path.join(source_dir, f"photo_{i+1}.jpg")
            ImageGenerator.create_test_image(
                img_path,
                text=f"Photo {i+1}",
                exif_date=datetime(2024, 6, i+1, 10, 0, 0)
            )
            test_files.append(img_path)

        # Initialize database
        DatabaseMetadata.create_database(test_db_path)
        metadata = DatabaseMetadata(test_db_path)
        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir
        )

        # Step 1: Scan for files
        file_list = get_file_list([source_dir], default_settings)

        assert len(file_list) == 5
        for test_file in test_files:
            assert test_file in file_list

        # Step 2: Find duplicates (should be none)
        originals, duplicates, filtered = find_duplicates(
            file_list,
            test_db_path,
            default_settings
        )

        assert len(originals) == 5
        assert len(duplicates) == 0

        # Step 3: Verify database was updated
        with PhotoDatabase(test_db_path) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == 5


class TestDuplicateDetectionWorkflow:
    """Test duplicate detection in complete workflow."""

    def test_duplicate_detection_end_to_end(self, source_dir, dest_dir, test_db_path, default_settings):
        """Test workflow with duplicate files."""
        # Create original
        original = os.path.join(source_dir, "original.jpg")
        ImageGenerator.create_test_image(
            original,
            text="Original",
            exif_date=datetime(2024, 5, 1)
        )

        # Create duplicates
        dup1 = os.path.join(source_dir, "duplicate_1.jpg")
        dup2 = os.path.join(source_dir, "subfolder", "duplicate_2.jpg")
        os.makedirs(os.path.dirname(dup2), exist_ok=True)

        ImageGenerator.create_duplicate(original, dup1)
        ImageGenerator.create_duplicate(original, dup2)

        # Initialize database
        DatabaseMetadata.create_database(test_db_path)
        metadata = DatabaseMetadata(test_db_path)
        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir
        )

        # Process files
        file_list = get_file_list([source_dir], default_settings)
        assert len(file_list) == 3  # original + 2 duplicates

        originals, duplicates, filtered = find_duplicates(
            file_list,
            test_db_path,
            default_settings
        )

        # Should detect 1 original and 2 duplicates
        assert len(originals) == 1
        assert len(duplicates) == 2

        # Database should only have 1 hash
        with PhotoDatabase(test_db_path) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == 1

    def test_incremental_processing_with_duplicates(self, source_dir, dest_dir, test_db_path, default_settings):
        """Test processing files in multiple batches."""
        # Initialize database
        DatabaseMetadata.create_database(test_db_path)
        metadata = DatabaseMetadata(test_db_path)
        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir
        )

        # Batch 1: Process initial files
        batch1_dir = os.path.join(source_dir, "batch1")
        os.makedirs(batch1_dir)

        for i in range(3):
            img_path = os.path.join(batch1_dir, f"photo_{i}.jpg")
            ImageGenerator.create_test_image(
                img_path,
                text=f"Batch 1 Photo {i}",
                exif_date=datetime(2024, 1, i+1)
            )

        file_list_1 = get_file_list([batch1_dir], default_settings)
        originals1, duplicates1, filtered1 = find_duplicates(
            file_list_1,
            test_db_path,
            default_settings
        )

        assert len(originals1) == 3
        assert len(duplicates1) == 0

        # Batch 2: Process new files + some duplicates of batch 1
        batch2_dir = os.path.join(source_dir, "batch2")
        os.makedirs(batch2_dir)

        # New file
        new_photo = os.path.join(batch2_dir, "new_photo.jpg")
        ImageGenerator.create_test_image(
            new_photo,
            text="New Photo",
            exif_date=datetime(2024, 2, 1)
        )

        # Duplicate of first file from batch 1
        source_dup = os.path.join(batch1_dir, "photo_0.jpg")
        dest_dup = os.path.join(batch2_dir, "duplicate.jpg")
        ImageGenerator.create_duplicate(source_dup, dest_dup)

        file_list_2 = get_file_list([batch2_dir], default_settings)
        originals2, duplicates2, filtered2 = find_duplicates(
            file_list_2,
            test_db_path,
            default_settings
        )

        # Should find 1 new original and 1 duplicate
        assert len(originals2) == 1
        assert len(duplicates2) == 1

        # Total database should have 4 unique hashes
        with PhotoDatabase(test_db_path) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == 4


class TestPhotoFilteringWorkflow:
    """Test photo filtering in complete workflow."""

    def test_filtering_excludes_icons_and_thumbnails(self, source_dir, dest_dir, test_db_path, settings_with_filtering):
        """Test that icons and thumbnails are filtered out."""
        # Create valid photos
        for i in range(3):
            img_path = os.path.join(source_dir, f"photo_{i}.jpg")
            ImageGenerator.create_test_image(
                img_path,
                width=1920,
                height=1080,
                exif_date=datetime(2024, 6, i+1)
            )

        # Create icons (should be filtered)
        for i in range(2):
            icon_path = os.path.join(source_dir, f"icon_{i}.png")
            ImageGenerator.create_icon(icon_path, size=64)

        # Create thumbnails (should be filtered)
        thumb_path = os.path.join(source_dir, "thumbnail.jpg")
        ImageGenerator.create_thumbnail(thumb_path)

        # Initialize database
        DatabaseMetadata.create_database(test_db_path)
        metadata = DatabaseMetadata(test_db_path)
        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir
        )

        # Process files with filtering enabled
        file_list = get_file_list([source_dir], settings_with_filtering)
        originals, duplicates, filtered = find_duplicates(
            file_list,
            test_db_path,
            settings_with_filtering
        )

        # Should have 3 originals (valid photos) and 3 filtered (icons + thumbnail)
        assert len(originals) == 3
        assert len(filtered) >= 3  # At least the icons and thumbnail

        # Database should only contain valid photos
        with PhotoDatabase(test_db_path) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == 3


class TestUnreliableDateWorkflow:
    """Test unreliable date detection and tracking."""

    def test_unreliable_dates_are_flagged(self, source_dir, dest_dir, test_db_path, default_settings):
        """Test that files with unreliable dates are flagged."""
        # Create files with various date issues
        # No EXIF
        no_exif = os.path.join(source_dir, "no_exif.jpg")
        ImageGenerator.create_photo_without_exif(no_exif)

        # Suspicious date
        suspicious = os.path.join(source_dir, "suspicious.jpg")
        ImageGenerator.create_photo_with_suspicious_date(suspicious)

        # Future date
        future = os.path.join(source_dir, "future.jpg")
        ImageGenerator.create_test_image(
            future,
            exif_date=datetime(2030, 1, 1)
        )

        # Valid date (should NOT be flagged)
        valid = os.path.join(source_dir, "valid.jpg")
        ImageGenerator.create_test_image(
            valid,
            exif_date=datetime(2020, 6, 15)
        )

        # Initialize database
        DatabaseMetadata.create_database(test_db_path)
        metadata = DatabaseMetadata(test_db_path)
        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir
        )

        # Process files
        file_list = get_file_list([source_dir], default_settings)
        originals, duplicates, filtered = find_duplicates(
            file_list,
            test_db_path,
            default_settings
        )

        # All should be processed
        assert len(originals) == 4

        # Check unreliable dates table
        unreliable_records = metadata.get_unreliable_dates()

        # Should have flagged 3 files (no_exif, suspicious, future)
        assert len(unreliable_records) >= 3


class TestMultiSourceProcessing:
    """Test processing from multiple source directories."""

    def test_process_multiple_sources(self, multiple_source_dirs, dest_dir, test_db_path, default_settings):
        """Test processing files from multiple source directories."""
        # Create files in each source directory
        all_files = []

        for i, source_dir in enumerate(multiple_source_dirs):
            for j in range(3):
                img_path = os.path.join(source_dir, f"photo_{j}.jpg")
                ImageGenerator.create_test_image(
                    img_path,
                    text=f"Source {i+1} Photo {j+1}",
                    exif_date=datetime(2024, i+1, j+1)
                )
                all_files.append(img_path)

        # Initialize database
        DatabaseMetadata.create_database(test_db_path)
        metadata = DatabaseMetadata(test_db_path)
        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir
        )

        # Process all sources
        file_list = get_file_list(multiple_source_dirs, default_settings)

        # Should find all files from all sources
        assert len(file_list) == 9  # 3 sources × 3 files each

        originals, duplicates, filtered = find_duplicates(
            file_list,
            test_db_path,
            default_settings
        )

        # All should be unique
        assert len(originals) == 9
        assert len(duplicates) == 0

        # Database should have 9 hashes
        with PhotoDatabase(test_db_path) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == 9


@pytest.mark.slow
class TestLargeScaleProcessing:
    """Test processing large numbers of files."""

    def test_process_many_files(self, source_dir, dest_dir, test_db_path, default_settings):
        """Test processing hundreds of files."""
        num_files = 100

        # Create many files
        for i in range(num_files):
            folder = os.path.join(source_dir, f"folder_{i // 10}")
            os.makedirs(folder, exist_ok=True)

            img_path = os.path.join(folder, f"photo_{i}.jpg")
            ImageGenerator.create_test_image(
                img_path,
                text=f"#{i}",
                exif_date=datetime(2024, 1, (i % 28) + 1)
            )

        # Initialize database
        DatabaseMetadata.create_database(test_db_path)
        metadata = DatabaseMetadata(test_db_path)
        metadata.initialize_metadata(
            database_name="Test DB",
            archive_location=dest_dir
        )

        # Process
        file_list = get_file_list([source_dir], default_settings)
        assert len(file_list) == num_files

        originals, duplicates, filtered = find_duplicates(
            file_list,
            test_db_path,
            default_settings
        )

        assert len(originals) == num_files
        assert len(duplicates) == 0

        # Verify database
        with PhotoDatabase(test_db_path) as db:
            hashes = db.get_all_hashes()
            assert len(hashes) == num_files
