"""
Pytest Configuration and Shared Fixtures

This file contains fixtures that are available to all tests without needing explicit imports.
"""

import os
import sys
import tempfile
import shutil
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Generator, Dict

import pytest

# Add parent directory to path so tests can import application modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from tests.test_utils.image_generator import ImageGenerator
from tests.test_utils.test_file_generator import TestFileGenerator
from tests.test_utils.mock_data import MockDataFactory


# ============================================================================
# Directory and File System Fixtures
# ============================================================================

@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """
    Create a temporary directory for test files.
    Automatically cleaned up after test completes.
    """
    temp_path = tempfile.mkdtemp(prefix="pyphotoorgtst_")
    yield temp_path
    if os.path.exists(temp_path):
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def source_dir(temp_dir: str) -> str:
    """Create a temporary source directory."""
    source_path = os.path.join(temp_dir, "source")
    os.makedirs(source_path, exist_ok=True)
    return source_path


@pytest.fixture
def dest_dir(temp_dir: str) -> str:
    """Create a temporary destination directory."""
    dest_path = os.path.join(temp_dir, "archive")
    os.makedirs(dest_path, exist_ok=True)
    return dest_path


@pytest.fixture
def multiple_source_dirs(temp_dir: str) -> list:
    """Create multiple source directories for multi-source testing."""
    sources = []
    for i in range(3):
        source_path = os.path.join(temp_dir, f"source_{i+1}")
        os.makedirs(source_path, exist_ok=True)
        sources.append(source_path)
    return sources


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
def test_db_path(temp_dir: str) -> str:
    """Create path for test database file."""
    return os.path.join(temp_dir, "test.db")


@pytest.fixture
def empty_database(test_db_path: str) -> Generator[str, None, None]:
    """
    Create an empty initialized database with all required tables.
    Returns path to database file.
    """
    from database_metadata import DatabaseMetadata

    # Create database with all tables
    DatabaseMetadata.create_database(test_db_path)

    yield test_db_path

    # Cleanup
    if os.path.exists(test_db_path):
        os.remove(test_db_path)


@pytest.fixture
def populated_database(empty_database: str, dest_dir: str) -> str:
    """
    Create a database populated with test data.
    Returns path to database file.
    """
    from database_metadata import DatabaseMetadata
    from DuplicateFileDetection import PhotoDatabase

    # Set up metadata
    metadata = DatabaseMetadata(empty_database)
    metadata.initialize_metadata(
        database_name="Test Database",
        archive_location=dest_dir,
        description="Populated test database"
    )

    # Add some sample photo records
    with PhotoDatabase(empty_database) as db:
        test_records = [
            ("hash1", "/archive/2024/01/01/photo1.jpg", "2024", "01", "01", "2024-01-01 10:00:00", "exif", None, 1024000),
            ("hash2", "/archive/2024/01/02/photo2.jpg", "2024", "01", "02", "2024-01-02 11:00:00", "exif", None, 2048000),
            ("hash3", "/archive/2024/02/15/photo3.jpg", "2024", "02", "15", "2024-02-15 14:30:00", "os_metadata", None, 512000),
        ]

        for record in test_records:
            db.insert_unique_photo(*record)

    return empty_database


@pytest.fixture
def in_memory_database() -> Generator[str, None, None]:
    """
    Create an in-memory SQLite database for fast testing.
    Returns connection string.
    """
    from database_metadata import DatabaseMetadata

    db_path = ":memory:"
    DatabaseMetadata.create_database(db_path)

    yield db_path

    # No cleanup needed for in-memory database


# ============================================================================
# Settings and Configuration Fixtures
# ============================================================================

@pytest.fixture
def default_settings(source_dir: str, dest_dir: str, test_db_path: str) -> Dict:
    """Create default settings configuration."""
    return MockDataFactory.create_settings(
        source_directories=[source_dir],
        destination_directory=dest_dir,
        database_path=test_db_path
    )


@pytest.fixture
def settings_with_filtering(default_settings: Dict) -> Dict:
    """Create settings with photo filtering enabled."""
    settings = default_settings.copy()
    settings.update({
        "photo_filter_enabled": True,
        "min_file_size": 51200,
        "min_width": 800,
        "min_height": 600,
        "exclude_square_smaller_than": 400
    })
    return settings


@pytest.fixture
def settings_without_filtering(default_settings: Dict) -> Dict:
    """Create settings with photo filtering disabled."""
    settings = default_settings.copy()
    settings["photo_filter_enabled"] = False
    return settings


@pytest.fixture
def settings_file(temp_dir: str, default_settings: Dict) -> str:
    """Create a temporary settings.json file."""
    settings_path = os.path.join(temp_dir, "settings.json")
    MockDataFactory.save_settings_to_file(default_settings, settings_path)
    return settings_path


# ============================================================================
# Test Data Generation Fixtures
# ============================================================================

@pytest.fixture
def image_generator() -> ImageGenerator:
    """Provide ImageGenerator instance."""
    return ImageGenerator()


@pytest.fixture
def file_generator() -> TestFileGenerator:
    """Provide TestFileGenerator instance."""
    return TestFileGenerator()


@pytest.fixture
def mock_factory() -> MockDataFactory:
    """Provide MockDataFactory instance."""
    return MockDataFactory()


@pytest.fixture
def sample_images(source_dir: str) -> list:
    """
    Create a collection of sample images with various properties.
    Returns list of file paths.
    """
    files = []

    # Valid photos with EXIF
    for i in range(5):
        path = os.path.join(source_dir, f"photo_{i+1}.jpg")
        ImageGenerator.create_test_image(
            path=path,
            width=1920,
            height=1080,
            text=f"Photo {i+1}",
            exif_date=datetime(2024, 1, i+1, 10, 0, 0)
        )
        files.append(path)

    return files


@pytest.fixture
def sample_images_with_duplicates(source_dir: str) -> Dict:
    """
    Create a collection with duplicates.
    Returns dict with 'originals' and 'duplicates' lists.
    """
    original = os.path.join(source_dir, "original.jpg")
    ImageGenerator.create_test_image(
        path=original,
        text="Original",
        exif_date=datetime(2024, 5, 1)
    )

    # Create duplicates
    dup1 = os.path.join(source_dir, "duplicate_1.jpg")
    dup2 = os.path.join(source_dir, "subfolder", "duplicate_2.jpg")
    os.makedirs(os.path.dirname(dup2), exist_ok=True)

    ImageGenerator.create_duplicate(original, dup1)
    ImageGenerator.create_duplicate(original, dup2)

    return {
        'originals': [original],
        'duplicates': [dup1, dup2],
        'all_files': [original, dup1, dup2]
    }


@pytest.fixture
def filtered_files(source_dir: str) -> Dict:
    """
    Create files that should be filtered (icons, thumbnails).
    Returns dict categorizing files.
    """
    icons = []
    thumbnails = []
    valid_photos = []

    # Icons
    for size in [16, 32, 64]:
        icon_path = os.path.join(source_dir, f"icon_{size}.png")
        ImageGenerator.create_icon(icon_path, size=size)
        icons.append(icon_path)

    # Thumbnails
    for i in range(3):
        thumb_path = os.path.join(source_dir, f"thumb_{i}.jpg")
        ImageGenerator.create_thumbnail(thumb_path)
        thumbnails.append(thumb_path)

    # Valid photos
    for i in range(2):
        photo_path = os.path.join(source_dir, f"valid_{i}.jpg")
        ImageGenerator.create_test_image(
            photo_path,
            width=1920,
            height=1080,
            exif_date=datetime(2024, 6, 1)
        )
        valid_photos.append(photo_path)

    return {
        'icons': icons,
        'thumbnails': thumbnails,
        'valid_photos': valid_photos,
        'should_filter': icons + thumbnails,
        'should_keep': valid_photos
    }


@pytest.fixture
def unreliable_date_files(source_dir: str) -> Dict:
    """
    Create files with various date reliability issues.
    Returns dict categorizing files by issue type.
    """
    no_exif = []
    suspicious_dates = []
    future_dates = []
    valid_dates = []

    # No EXIF
    for i in range(2):
        path = os.path.join(source_dir, f"no_exif_{i}.jpg")
        ImageGenerator.create_photo_without_exif(path)
        no_exif.append(path)

    # Suspicious (1970)
    for i in range(2):
        path = os.path.join(source_dir, f"suspicious_{i}.jpg")
        ImageGenerator.create_photo_with_suspicious_date(path)
        suspicious_dates.append(path)

    # Future dates
    future_path = os.path.join(source_dir, "future.jpg")
    ImageGenerator.create_test_image(
        future_path,
        exif_date=datetime(2030, 1, 1)
    )
    future_dates.append(future_path)

    # Valid dates
    valid_path = os.path.join(source_dir, "valid.jpg")
    ImageGenerator.create_test_image(
        valid_path,
        exif_date=datetime(2020, 6, 15)
    )
    valid_dates.append(valid_path)

    return {
        'no_exif': no_exif,
        'suspicious': suspicious_dates,
        'future': future_dates,
        'valid': valid_dates,
        'all_unreliable': no_exif + suspicious_dates + future_dates,
        'all_reliable': valid_dates
    }


# ============================================================================
# Test Scenario Fixtures
# ============================================================================

@pytest.fixture
def simple_scenario(temp_dir: str) -> Dict:
    """Create simple test scenario with a few files."""
    scenario_path = os.path.join(temp_dir, "simple_scenario")
    return TestFileGenerator.create_test_scenario(scenario_path, 'simple')


@pytest.fixture
def duplicates_scenario(temp_dir: str) -> Dict:
    """Create scenario with duplicate files."""
    scenario_path = os.path.join(temp_dir, "duplicates_scenario")
    return TestFileGenerator.create_test_scenario(scenario_path, 'duplicates')


@pytest.fixture
def mixed_formats_scenario(temp_dir: str) -> Dict:
    """Create scenario with various file formats."""
    scenario_path = os.path.join(temp_dir, "mixed_formats_scenario")
    return TestFileGenerator.create_test_scenario(scenario_path, 'mixed_formats')


@pytest.fixture
def large_collection_scenario(temp_dir: str) -> Dict:
    """Create scenario with many files (warning: slower)."""
    scenario_path = os.path.join(temp_dir, "large_scenario")
    return TestFileGenerator.create_test_scenario(scenario_path, 'large_collection')


# ============================================================================
# Cleanup and Utility Fixtures
# ============================================================================

@pytest.fixture(autouse=True)
def reset_working_directory():
    """
    Ensure tests run from project root directory.
    Auto-used for all tests.
    """
    original_dir = os.getcwd()
    # Change to project root (parent of tests directory)
    project_root = os.path.dirname(os.path.dirname(__file__))
    os.chdir(project_root)

    yield

    # Restore original directory
    os.chdir(original_dir)


@pytest.fixture
def capture_logs(caplog):
    """
    Provide access to captured log messages.
    Wrapper around pytest's caplog fixture.
    """
    import logging
    caplog.set_level(logging.DEBUG)
    return caplog


# ============================================================================
# Marker Helpers
# ============================================================================

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests for individual functions/classes"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests for complete workflows"
    )
    config.addinivalue_line(
        "markers", "database: Database operation and schema tests"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take significant time to run"
    )
    config.addinivalue_line(
        "markers", "requires_ffmpeg: Tests that require FFmpeg to be installed"
    )


def pytest_collection_modifyitems(config, items):
    """
    Modify test collection to add markers automatically.
    """
    for item in items:
        # Auto-mark tests based on file location
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)
        elif "database" in str(item.fspath):
            item.add_marker(pytest.mark.database)

        # Mark slow tests (large_collection scenarios)
        if "large_collection" in item.nodeid:
            item.add_marker(pytest.mark.slow)
