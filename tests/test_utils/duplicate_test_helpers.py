"""
Duplicate Detection Test Helpers

Centralized functions for generating test files and verifying results
across all duplicate detection integration tests.
"""

import os
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from PIL import Image, ImageDraw
import piexif

from database_metadata import DatabaseMetadata
from DuplicateFileDetection import PhotoDatabase
from config import Config


# ============================================================================
# Internal Helpers
# ============================================================================

def _add_varied_content(draw, width: int, height: int, seed: str):
    """Draw random lines on an image to increase JPEG file size above filter thresholds."""
    import random
    rng = random.Random(seed)
    for _ in range(200):
        x1, y1 = rng.randint(0, width - 1), rng.randint(0, height - 1)
        x2, y2 = rng.randint(0, width - 1), rng.randint(0, height - 1)
        c = (rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255))
        draw.line([(x1, y1), (x2, y2)], fill=c, width=rng.randint(1, 3))


# ============================================================================
# Image Generation Helpers
# ============================================================================

def create_photo_with_exif(
    path: str,
    filename: str,
    width: int,
    height: int,
    date: datetime,
    camera_make: str = "TestCam",
    camera_model: str = "TC-1000",
    color: Tuple[int, int, int] = (100, 150, 200),
) -> str:
    """Create a JPEG with full EXIF (DateTimeOriginal). Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    img = Image.new("RGB", (width, height), color)
    # Draw unique content based on filename for uniqueness and to increase file size
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), filename, fill=(255, 255, 255))
    _add_varied_content(draw, width, height, filename)

    date_str = date.strftime("%Y:%m:%d %H:%M:%S")
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Make: camera_make.encode(),
            piexif.ImageIFD.Model: camera_model.encode(),
            piexif.ImageIFD.DateTime: date_str.encode(),
            piexif.ImageIFD.Orientation: 1,
        },
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: date_str.encode(),
            piexif.ExifIFD.DateTimeDigitized: date_str.encode(),
            piexif.ExifIFD.PixelXDimension: width,
            piexif.ExifIFD.PixelYDimension: height,
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif_dict)
    img.save(filepath, format="JPEG", exif=exif_bytes, quality=95)
    return filepath


def create_photo_without_exif(
    path: str,
    filename: str,
    width: int = 1920,
    height: int = 1080,
    color: Tuple[int, int, int] = (50, 100, 150),
) -> str:
    """Create a JPEG with NO EXIF data at all. Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), filename, fill=(255, 255, 255))
    _add_varied_content(draw, width, height, filename)
    img.save(filepath, format="JPEG", quality=95)
    return filepath


def create_photo_exif_digitized_only(
    path: str,
    filename: str,
    width: int,
    height: int,
    date: datetime,
    color: Tuple[int, int, int] = (80, 120, 180),
) -> str:
    """Create JPEG with only DateTimeDigitized (no DateTimeOriginal). Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), filename, fill=(255, 255, 255))
    _add_varied_content(draw, width, height, filename)

    date_str = date.strftime("%Y:%m:%d %H:%M:%S")
    exif_dict = {
        "0th": {
            piexif.ImageIFD.Orientation: 1,
        },
        "Exif": {
            piexif.ExifIFD.DateTimeDigitized: date_str.encode(),
            piexif.ExifIFD.PixelXDimension: width,
            piexif.ExifIFD.PixelYDimension: height,
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    exif_bytes = piexif.dump(exif_dict)
    img.save(filepath, format="JPEG", exif=exif_bytes, quality=95)
    return filepath


def create_identical_pixels_different_exif(
    path: str,
    filename1: str,
    filename2: str,
    width: int,
    height: int,
    color: Tuple[int, int, int],
    date1: datetime,
    date2: datetime,
) -> Tuple[str, str]:
    """Create two files with same pixel content but different EXIF.
    For content-hash duplicate testing. Returns (path1, path2)."""
    os.makedirs(path, exist_ok=True)

    # Create the pixel data once
    img = Image.new("RGB", (width, height), color)

    filepath1 = os.path.join(path, filename1)
    filepath2 = os.path.join(path, filename2)

    # Save file 1 with date1 EXIF
    date_str1 = date1.strftime("%Y:%m:%d %H:%M:%S")
    exif1 = {
        "0th": {piexif.ImageIFD.DateTime: date_str1.encode(), piexif.ImageIFD.Orientation: 1},
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: date_str1.encode(),
            piexif.ExifIFD.PixelXDimension: width,
            piexif.ExifIFD.PixelYDimension: height,
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    img.save(filepath1, format="JPEG", exif=piexif.dump(exif1), quality=95)

    # Save file 2 with date2 EXIF
    date_str2 = date2.strftime("%Y:%m:%d %H:%M:%S")
    exif2 = {
        "0th": {piexif.ImageIFD.DateTime: date_str2.encode(), piexif.ImageIFD.Orientation: 1},
        "Exif": {
            piexif.ExifIFD.DateTimeOriginal: date_str2.encode(),
            piexif.ExifIFD.PixelXDimension: width,
            piexif.ExifIFD.PixelYDimension: height,
        },
        "GPS": {},
        "1st": {},
        "thumbnail": None,
    }
    img.save(filepath2, format="JPEG", exif=piexif.dump(exif2), quality=95)

    return filepath1, filepath2


def create_small_icon(
    path: str, filename: str, size: int = 64
) -> str:
    """Create a small square image (icon). Should be filtered. Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    img = Image.new("RGB", (size, size), (255, 0, 0))
    img.save(filepath, format="JPEG", quality=95)
    return filepath


def create_thumbnail(path: str, filename: str) -> str:
    """Create 150x150 image named with 'thumb'. Should be filtered. Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    img = Image.new("RGB", (150, 150), (128, 128, 128))
    img.save(filepath, format="JPEG", quality=95)
    return filepath


def create_tiny_file(path: str, filename: str) -> str:
    """Create valid JPEG under 50KB. Should be filtered by size. Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    # Create a very small image that will be well under 50KB
    img = Image.new("RGB", (100, 100), (200, 200, 200))
    img.save(filepath, format="JPEG", quality=10)
    return filepath


def create_dated_filename_photo(
    path: str,
    filename_with_date: str,
    width: int = 1920,
    height: int = 1080,
    color: Tuple[int, int, int] = (70, 130, 190),
) -> str:
    """Create photo with no EXIF but a date-parseable filename
    (e.g., IMG_20240115_143000.jpg). Returns file path."""
    filepath = os.path.join(path, filename_with_date)
    os.makedirs(path, exist_ok=True)

    img = Image.new("RGB", (width, height), color)
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), filename_with_date, fill=(255, 255, 255))
    _add_varied_content(draw, width, height, filename_with_date)
    img.save(filepath, format="JPEG", quality=95)
    return filepath


def create_mock_video(path: str, filename: str, size_kb: int = 500) -> str:
    """Create a mock video file (valid extension, random content). Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    # Write enough random-ish bytes to exceed photo filter size threshold
    with open(filepath, "wb") as f:
        f.write(os.urandom(size_kb * 1024))
    return filepath


def create_corrupted_jpeg(path: str, filename: str) -> str:
    """Create a corrupted JPEG (valid header + garbage). Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    with open(filepath, "wb") as f:
        f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 100)
    return filepath


def create_zero_byte_file(path: str, filename: str) -> str:
    """Create a zero-byte file. Returns file path."""
    filepath = os.path.join(path, filename)
    os.makedirs(path, exist_ok=True)

    with open(filepath, "wb") as _f:
        pass
    return filepath


# ============================================================================
# Verification Helpers
# ============================================================================

def get_archive_files(archive_dir: str) -> Dict[str, str]:
    """Recursively list all files in archive. Returns dict of {relative_path: absolute_path}."""
    result = {}
    for root, _dirs, files in os.walk(archive_dir):
        for f in files:
            abs_path = os.path.join(root, f)
            rel_path = os.path.relpath(abs_path, archive_dir)
            result[rel_path] = abs_path
    return result


def get_database_records(db_path: str) -> List[Dict[str, Any]]:
    """Return all UniquePhotos records as list of dicts."""
    records = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM UniquePhotos")
        for row in cursor.fetchall():
            records.append(dict(row))
    return records


def get_unreliable_dates(db_path: str) -> List[Dict[str, Any]]:
    """Return all UnreliableDates records."""
    records = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM UnreliableDates")
            for row in cursor.fetchall():
                records.append(dict(row))
        except sqlite3.OperationalError:
            pass  # Table may not exist
    return records


def get_revision_records(db_path: str) -> List[Dict[str, Any]]:
    """Return all records where revised_photo IS NOT NULL."""
    records = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM UniquePhotos WHERE revised_photo IS NOT NULL")
        for row in cursor.fetchall():
            records.append(dict(row))
    return records


def get_upgrade_history(db_path: str) -> List[Dict[str, Any]]:
    """Return all MetadataUpgradeHistory records."""
    records = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM MetadataUpgradeHistory")
            for row in cursor.fetchall():
                records.append(dict(row))
        except sqlite3.OperationalError:
            pass  # Table may not exist
    return records


def assert_file_in_archive(archive_dir: str, filename_substring: str) -> str:
    """Assert a file containing the substring exists in archive tree. Returns matching path."""
    files = get_archive_files(archive_dir)
    matches = [
        abs_path
        for rel_path, abs_path in files.items()
        if filename_substring in os.path.basename(abs_path)
    ]
    assert matches, (
        f"Expected file containing '{filename_substring}' in archive, "
        f"but found only: {list(files.keys())}"
    )
    return matches[0]


def assert_file_not_in_archive(archive_dir: str, filename_substring: str):
    """Assert no file containing the substring exists in archive tree."""
    files = get_archive_files(archive_dir)
    matches = [
        rel_path
        for rel_path in files.keys()
        if filename_substring in os.path.basename(rel_path)
    ]
    assert not matches, (
        f"Expected no file containing '{filename_substring}' in archive, "
        f"but found: {matches}"
    )


def count_archive_files(archive_dir: str) -> int:
    """Count total files in archive directory tree."""
    return len(get_archive_files(archive_dir))


def setup_full_environment(
    tmp_path, source_name: str = "source"
) -> Dict[str, Any]:
    """Create source_dir, dest_dir, prior_revision_dir, db_path,
    initialize database and metadata. Returns dict of all paths + config."""
    base = str(tmp_path)

    source_dir = os.path.join(base, source_name)
    archive_dir = os.path.join(base, "archive")
    prior_revision_dir = os.path.join(base, "prior_revisions")
    db_path = os.path.join(base, "test.db")

    os.makedirs(source_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)
    os.makedirs(prior_revision_dir, exist_ok=True)

    # Create and initialize the database
    db_metadata = DatabaseMetadata(db_path)
    db_metadata.initialize_metadata(
        database_name="Test Database",
        archive_location=archive_dir,
        description="Integration test database",
    )

    # Set prior revision archive location
    _set_prior_revision_location(db_path, prior_revision_dir)

    # Initialize UniquePhotos table
    with PhotoDatabase(db_path) as db:
        db.initialize_database()

    # Build config dict
    config_dict = {
        "source_directory": [source_dir],
        "destination_directory": archive_dir,
        "database_path": db_path,
        "batch_size": 100,
        "include_subdirectories": True,
        "file_endings": [".jpg", ".jpeg", ".png", ".heic", ".mov", ".mp4"],
        "copy_files": True,
        "move_files": False,
        "partial_hash_enabled": True,
        "partial_hash_bytes": 16384,
        "partial_hash_min_file_size": 1048576,
        "photo_filter_enabled": True,
        "min_file_size": 1024,  # Low threshold so synthetic test images pass filter
        "min_width": 800,
        "min_height": 600,
        "max_width": 50000,
        "max_height": 50000,
        "exclude_square_smaller_than": 400,
        "require_exif": False,
        "excluded_filename_patterns": ["favicon", "icon", "logo", "thumb", "button", "badge", "sprite"],
        "organization_template": "{year}/{month}/{day}",
        "content_hash_enabled": True,
    }

    config = Config(settings_dict=config_dict)

    return {
        "tmp_path": tmp_path,
        "source_dir": source_dir,
        "archive_dir": archive_dir,
        "prior_revision_dir": prior_revision_dir,
        "db_path": db_path,
        "config": config,
        "config_dict": config_dict,
        "db_metadata": db_metadata,
    }


def run_organize(env: Dict, files: List[str], **overrides) -> Dict:
    """Run organize_files with standard env settings. Returns result dict."""
    from main import organize_files

    kwargs = {
        "config": env["config"],
        "files": files,
        "database_path": env["db_path"],
        "batch_size": 100,
    }
    kwargs.update(overrides)
    return organize_files(**kwargs)


def _set_prior_revision_location(db_path: str, location: str):
    """Set the prior revision archive location in metadata."""
    with sqlite3.connect(db_path, timeout=30) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(
            "UPDATE DatabaseMetadata SET prior_revision_archive_location = ? WHERE id = 1",
            (location,),
        )
        conn.commit()
