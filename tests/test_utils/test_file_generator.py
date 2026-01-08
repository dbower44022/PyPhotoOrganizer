"""
Test File Generator

Creates various file structures and scenarios for testing:
- Mock video files
- Directory structures
- Mixed file collections
- Edge cases (locked files, permissions, etc.)
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional


class TestFileGenerator:
    """Generate test file structures and scenarios."""

    @staticmethod
    def create_mock_video(path: str, duration_seconds: int = 10, size_mb: float = 5.0) -> str:
        """
        Create a mock video file (just a placeholder with video extension).

        Note: This creates a file with video extension but not actual video data.
        For video metadata testing, use actual small video files.

        Args:
            path: File path for mock video
            duration_seconds: Simulated duration (not used, for documentation)
            size_mb: Approximate file size in MB

        Returns:
            Path to created file
        """
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)

        # Create file with specified size
        size_bytes = int(size_mb * 1024 * 1024)
        with open(path, 'wb') as f:
            # Write repeating pattern to reach desired size
            pattern = b'VIDEO_DATA_' * 1024
            bytes_written = 0
            while bytes_written < size_bytes:
                chunk = pattern[:min(len(pattern), size_bytes - bytes_written)]
                f.write(chunk)
                bytes_written += len(chunk)

        return path

    @staticmethod
    def create_source_structure(
        base_path: str,
        structure: Dict[str, any]
    ) -> str:
        """
        Create a directory structure from nested dictionary.

        Args:
            base_path: Root directory for structure
            structure: Nested dict defining structure
                      Folders: key = folder name, value = dict of contents
                      Files: key = filename, value = 'file' or file config dict

        Returns:
            Path to created base directory

        Example:
            structure = {
                '2024': {
                    '01': {
                        'photo1.jpg': 'file',
                        'photo2.jpg': {'type': 'image', 'date': '2024-01-15'}
                    },
                    'videos': {
                        'clip1.mp4': 'file'
                    }
                }
            }
        """
        os.makedirs(base_path, exist_ok=True)

        def create_recursive(current_path: str, items: Dict):
            for name, content in items.items():
                item_path = os.path.join(current_path, name)

                if isinstance(content, dict):
                    # Check if it's a file config or a directory
                    if 'type' in content:
                        # File with configuration
                        TestFileGenerator._create_configured_file(item_path, content)
                    else:
                        # Directory with nested structure
                        os.makedirs(item_path, exist_ok=True)
                        create_recursive(item_path, content)
                else:
                    # Simple file
                    with open(item_path, 'w') as f:
                        f.write(f"Test file: {name}\n")

        create_recursive(base_path, structure)
        return base_path

    @staticmethod
    def _create_configured_file(path: str, config: Dict):
        """Create a file based on configuration dictionary."""
        from .image_generator import ImageGenerator

        file_type = config.get('type', 'generic')

        if file_type == 'image':
            date = config.get('date')
            exif_date = datetime.fromisoformat(date) if date else None
            ImageGenerator.create_test_image(
                path=path,
                width=config.get('width', 1920),
                height=config.get('height', 1080),
                exif_date=exif_date
            )
        elif file_type == 'video':
            TestFileGenerator.create_mock_video(
                path=path,
                size_mb=config.get('size_mb', 5.0)
            )
        else:
            # Generic file
            with open(path, 'w') as f:
                f.write(config.get('content', f"Test file: {os.path.basename(path)}\n"))

    @staticmethod
    def create_test_scenario(
        base_path: str,
        scenario: str
    ) -> Dict[str, any]:
        """
        Create predefined test scenarios.

        Args:
            base_path: Root directory for scenario
            scenario: Scenario name

        Returns:
            Dictionary with scenario details and file paths

        Available scenarios:
        - 'simple': Few files, no duplicates
        - 'duplicates': Files with duplicates
        - 'mixed_formats': Various image and video formats
        - 'filtered': Files that should be filtered (icons, thumbnails)
        - 'date_issues': Files with various date problems
        - 'large_collection': Many files across multiple folders
        """
        from .image_generator import ImageGenerator

        os.makedirs(base_path, exist_ok=True)

        if scenario == 'simple':
            return TestFileGenerator._create_simple_scenario(base_path)
        elif scenario == 'duplicates':
            return TestFileGenerator._create_duplicates_scenario(base_path)
        elif scenario == 'mixed_formats':
            return TestFileGenerator._create_mixed_formats_scenario(base_path)
        elif scenario == 'filtered':
            return TestFileGenerator._create_filtered_scenario(base_path)
        elif scenario == 'date_issues':
            return TestFileGenerator._create_date_issues_scenario(base_path)
        elif scenario == 'large_collection':
            return TestFileGenerator._create_large_collection_scenario(base_path)
        else:
            raise ValueError(f"Unknown scenario: {scenario}")

    @staticmethod
    def _create_simple_scenario(base_path: str) -> Dict:
        """Create simple scenario with a few unique files."""
        from .image_generator import ImageGenerator

        files = []
        date = datetime(2024, 6, 15, 10, 30, 0)

        for i in range(5):
            path = os.path.join(base_path, f"photo_{i+1}.jpg")
            ImageGenerator.create_test_image(
                path=path,
                text=f"Photo {i+1}",
                exif_date=date
            )
            files.append(path)

        return {
            'scenario': 'simple',
            'files': files,
            'expected_unique': 5,
            'expected_duplicates': 0
        }

    @staticmethod
    def _create_duplicates_scenario(base_path: str) -> Dict:
        """Create scenario with duplicate files."""
        from .image_generator import ImageGenerator

        files = []

        # Create original
        original = os.path.join(base_path, "original.jpg")
        ImageGenerator.create_test_image(
            path=original,
            text="Original",
            exif_date=datetime(2024, 1, 1)
        )
        files.append(original)

        # Create duplicates in different locations
        dup1 = os.path.join(base_path, "duplicate_1.jpg")
        dup2 = os.path.join(base_path, "subdir", "duplicate_2.jpg")
        os.makedirs(os.path.dirname(dup2), exist_ok=True)

        ImageGenerator.create_duplicate(original, dup1)
        ImageGenerator.create_duplicate(original, dup2)

        files.extend([dup1, dup2])

        return {
            'scenario': 'duplicates',
            'files': files,
            'original': original,
            'duplicates': [dup1, dup2],
            'expected_unique': 1,
            'expected_duplicates': 2
        }

    @staticmethod
    def _create_mixed_formats_scenario(base_path: str) -> Dict:
        """Create scenario with various file formats."""
        from .image_generator import ImageGenerator

        files = []
        date = datetime(2024, 3, 15)

        # JPEG
        jpg_path = os.path.join(base_path, "photo.jpg")
        ImageGenerator.create_test_image(jpg_path, format="JPEG", exif_date=date)
        files.append(jpg_path)

        # PNG
        png_path = os.path.join(base_path, "image.png")
        ImageGenerator.create_test_image(png_path, format="PNG")
        files.append(png_path)

        # TIFF
        tiff_path = os.path.join(base_path, "scan.tif")
        ImageGenerator.create_test_image(tiff_path, format="TIFF", exif_date=date)
        files.append(tiff_path)

        # Mock video
        mp4_path = os.path.join(base_path, "video.mp4")
        TestFileGenerator.create_mock_video(mp4_path)
        files.append(mp4_path)

        return {
            'scenario': 'mixed_formats',
            'files': files,
            'formats': ['jpg', 'png', 'tif', 'mp4']
        }

    @staticmethod
    def _create_filtered_scenario(base_path: str) -> Dict:
        """Create scenario with files that should be filtered."""
        from .image_generator import ImageGenerator

        files = []

        # Icon (small square)
        icon_path = os.path.join(base_path, "icon.png")
        ImageGenerator.create_icon(icon_path, size=64)
        files.append(icon_path)

        # Thumbnail
        thumb_path = os.path.join(base_path, "thumbnail.jpg")
        ImageGenerator.create_thumbnail(thumb_path)
        files.append(thumb_path)

        # Favicon pattern
        favicon_path = os.path.join(base_path, "favicon-32x32.png")
        ImageGenerator.create_icon(favicon_path, size=32)
        files.append(favicon_path)

        # Valid photo (should NOT be filtered)
        valid_path = os.path.join(base_path, "valid_photo.jpg")
        ImageGenerator.create_test_image(
            valid_path,
            width=1920,
            height=1080,
            exif_date=datetime(2024, 5, 1)
        )
        files.append(valid_path)

        return {
            'scenario': 'filtered',
            'files': files,
            'expected_filtered': 3,
            'expected_valid': 1
        }

    @staticmethod
    def _create_date_issues_scenario(base_path: str) -> Dict:
        """Create scenario with various date issues."""
        from .image_generator import ImageGenerator

        files = []

        # No EXIF
        no_exif = os.path.join(base_path, "no_exif.jpg")
        ImageGenerator.create_photo_without_exif(no_exif)
        files.append(no_exif)

        # Suspicious date (1970)
        suspicious = os.path.join(base_path, "suspicious_date.jpg")
        ImageGenerator.create_photo_with_suspicious_date(suspicious)
        files.append(suspicious)

        # Future date
        future_date = os.path.join(base_path, "future_date.jpg")
        ImageGenerator.create_test_image(
            future_date,
            exif_date=datetime(2030, 1, 1)
        )
        files.append(future_date)

        # Valid date
        valid = os.path.join(base_path, "valid_date.jpg")
        ImageGenerator.create_test_image(
            valid,
            exif_date=datetime(2020, 6, 15)
        )
        files.append(valid)

        return {
            'scenario': 'date_issues',
            'files': files,
            'expected_unreliable': 3,
            'expected_reliable': 1
        }

    @staticmethod
    def _create_large_collection_scenario(base_path: str, count: int = 50) -> Dict:
        """Create scenario with many files across multiple folders."""
        from .image_generator import ImageGenerator

        files = []
        start_date = datetime(2024, 1, 1)

        # Create files across multiple year/month folders
        for i in range(count):
            # Vary the folder structure
            year = 2023 + (i // 12)
            month = (i % 12) + 1
            folder = os.path.join(base_path, str(year), f"{month:02d}")
            os.makedirs(folder, exist_ok=True)

            filename = f"IMG_{i+1:04d}.jpg"
            filepath = os.path.join(folder, filename)

            from datetime import timedelta
            date = start_date + timedelta(days=i*7)  # Weekly photos

            ImageGenerator.create_test_image(
                filepath,
                text=f"#{i+1}",
                exif_date=date
            )
            files.append(filepath)

        return {
            'scenario': 'large_collection',
            'files': files,
            'count': count,
            'folders': len(set(os.path.dirname(f) for f in files))
        }

    @staticmethod
    def cleanup_test_directory(path: str):
        """
        Clean up test directory and all contents.

        Args:
            path: Directory to remove
        """
        if os.path.exists(path):
            shutil.rmtree(path)
