"""
Photo filtering module to identify and exclude non-photographs.

This module provides functionality to filter out icons, web graphics, thumbnails,
and other small images that are not actual photographs.
"""

import logging
import os
from typing import Tuple, Optional
from PIL import Image

import utils
import constants

# Configure logging using shared utility
logger = utils.setup_logger(__name__, "photo_filter.log")


class PhotoFilter:
    """
    Filter to identify real photographs and exclude icons, thumbnails, etc.

    Uses multiple criteria:
    - File size (real photos are typically larger than 50KB)
    - Image dimensions (photos typically > 800x600)
    - Aspect ratio (exclude small perfect squares like icons)
    - EXIF data presence (optional - photos have camera metadata)
    - Filename patterns (exclude 'favicon', 'icon', 'logo', etc.)

    Usage:
        filter = PhotoFilter(config)
        if filter.is_photo(file_path):
            # Process as photo
        else:
            # Skip or move to filtered folder
    """

    def __init__(self, config):
        """
        Initialize photo filter with configuration.

        Parameters:
            config (Config): Configuration object with filter settings
        """
        self.config = config
        self.enabled = config.get('photo_filter_enabled', True)
        self.min_file_size = config.get('min_file_size', constants.MIN_PHOTO_FILE_SIZE)  # 50KB
        self.min_width = config.get('min_width', constants.MIN_PHOTO_WIDTH)
        self.min_height = config.get('min_height', constants.MIN_PHOTO_HEIGHT)
        self.max_width = config.get('max_width', constants.MAX_PHOTO_WIDTH)
        self.max_height = config.get('max_height', constants.MAX_PHOTO_HEIGHT)
        self.exclude_square_smaller_than = config.get('exclude_square_smaller_than', constants.MIN_SQUARE_SIZE)
        self.require_exif = config.get('require_exif', False)
        self.excluded_patterns = config.get('excluded_filename_patterns', [])
        self.move_filtered_files = config.get('move_filtered_files', False)
        self.filtered_files_folder = config.get('filtered_files_folder', 'filtered_non_photos')

        # Statistics
        self.total_checked = 0
        self.filtered_by_size = 0
        self.filtered_by_dimensions = 0
        self.filtered_by_square = 0
        self.filtered_by_exif = 0
        self.filtered_by_filename = 0
        self.filtered_by_read_error = 0

    def is_photo(self, file_path: str) -> bool:
        """
        Determine if a file is a real photograph.

        Parameters:
            file_path (str): Path to the file to check

        Returns:
            bool: True if file appears to be a photo, False if it should be filtered
        """
        if not self.enabled:
            return True  # Filter disabled, accept all files

        self.total_checked += 1

        # Check 1: Filename patterns
        if not self._check_filename(file_path):
            self.filtered_by_filename += 1
            logger.debug(f"Filtered by filename pattern: {file_path}")
            return False

        # Check 2: File size
        if not self._check_file_size(file_path):
            self.filtered_by_size += 1
            logger.debug(f"Filtered by file size: {file_path}")
            return False

        # Check 3: Image dimensions and properties (requires opening the file)
        try:
            with Image.open(file_path) as img:
                # Check dimensions
                if not self._check_dimensions(img, file_path):
                    self.filtered_by_dimensions += 1
                    return False

                # Check for small squares (likely icons)
                if not self._check_square_icon(img, file_path):
                    self.filtered_by_square += 1
                    return False

                # Check EXIF data (if required)
                if self.require_exif and not self._check_exif(img, file_path):
                    self.filtered_by_exif += 1
                    return False

        except Exception as e:
            logger.warning(f"Could not read image {file_path}: {e}")
            self.filtered_by_read_error += 1
            return False  # If we can't read it, filter it out

        # Passed all checks - it's a photo
        return True

    def _check_filename(self, file_path: str) -> bool:
        """Check if filename contains excluded patterns."""
        filename = os.path.basename(file_path).lower()

        for pattern in self.excluded_patterns:
            if pattern.lower() in filename:
                return False

        return True

    def _check_file_size(self, file_path: str) -> bool:
        """Check if file size meets minimum requirement."""
        try:
            file_size = os.path.getsize(file_path)
            return file_size >= self.min_file_size
        except OSError as e:
            logger.warning(f"Could not get file size for {file_path}: {e}")
            return False

    def _check_dimensions(self, img: Image.Image, file_path: str) -> bool:
        """Check if image dimensions are within acceptable range."""
        width, height = img.size

        if width < self.min_width or height < self.min_height:
            logger.debug(f"Dimensions too small: {width}x{height} for {file_path}")
            return False

        if width > self.max_width or height > self.max_height:
            logger.debug(f"Dimensions too large: {width}x{height} for {file_path}")
            return False

        return True

    def _check_square_icon(self, img: Image.Image, file_path: str) -> bool:
        """Check if image is a small square (likely an icon)."""
        width, height = img.size

        # If it's a perfect square smaller than threshold, it's likely an icon
        if width == height and width < self.exclude_square_smaller_than:
            logger.debug(f"Small square icon detected: {width}x{height} for {file_path}")
            return False

        return True

    def _check_exif(self, img: Image.Image, file_path: str) -> bool:
        """Check if image has EXIF data (camera metadata)."""
        try:
            exif_data = img._getexif()
            if exif_data is None or len(exif_data) == 0:
                logger.debug(f"No EXIF data found: {file_path}")
                return False
            return True
        except Exception:
            # Some images don't support EXIF
            logger.debug(f"Could not read EXIF data: {file_path}")
            return False

    def get_filter_reason(self, file_path: str) -> Optional[str]:
        """
        Get the reason why a file was filtered (for reporting).

        Returns the first reason that caused filtering, or None if file passes.

        Parameters:
            file_path (str): Path to check

        Returns:
            str or None: Reason for filtering, or None if file is a photo
        """
        if not self.enabled:
            return None

        if not self._check_filename(file_path):
            return "filename_pattern"

        if not self._check_file_size(file_path):
            return "file_size_too_small"

        try:
            with Image.open(file_path) as img:
                if not self._check_dimensions(img, file_path):
                    return "dimensions_out_of_range"

                if not self._check_square_icon(img, file_path):
                    return "small_square_icon"

                if self.require_exif and not self._check_exif(img, file_path):
                    return "missing_exif_data"
        except Exception:
            return "image_read_error"

        return None

    def get_statistics(self) -> dict:
        """
        Get filtering statistics.

        Returns:
            dict: Statistics about filtered files
        """
        total_filtered = (self.filtered_by_size + self.filtered_by_dimensions +
                         self.filtered_by_square + self.filtered_by_exif +
                         self.filtered_by_filename + self.filtered_by_read_error)

        return {
            'total_checked': self.total_checked,
            'total_filtered': total_filtered,
            'total_passed': self.total_checked - total_filtered,
            'filtered_by_size': self.filtered_by_size,
            'filtered_by_dimensions': self.filtered_by_dimensions,
            'filtered_by_square': self.filtered_by_square,
            'filtered_by_exif': self.filtered_by_exif,
            'filtered_by_filename': self.filtered_by_filename,
            'filtered_by_read_error': self.filtered_by_read_error,
        }

    def print_statistics(self):
        """Print filtering statistics to logger."""
        stats = self.get_statistics()
        logger.info("=" * 70)
        logger.info("PHOTO FILTERING STATISTICS")
        logger.info("=" * 70)
        logger.info(f"Total files checked:     {stats['total_checked']}")
        logger.info(f"Files passed (photos):   {stats['total_passed']}")
        logger.info(f"Files filtered:          {stats['total_filtered']}")
        logger.info("")
        logger.info("Filtered by reason:")
        logger.info(f"  File size too small:   {stats['filtered_by_size']}")
        logger.info(f"  Dimensions out of range: {stats['filtered_by_dimensions']}")
        logger.info(f"  Small square icon:     {stats['filtered_by_square']}")
        logger.info(f"  Missing EXIF data:     {stats['filtered_by_exif']}")
        logger.info(f"  Filename pattern:      {stats['filtered_by_filename']}")
        logger.info(f"  Image read error:      {stats['filtered_by_read_error']}")
        logger.info("=" * 70)


if __name__ == '__main__':
    """Test the photo filter."""
    from config import Config

    print("Testing photo_filter.py")

    try:
        config = Config('settings.json')
        filter = PhotoFilter(config)

        print(f"✓ Created PhotoFilter")
        print(f"  Enabled: {filter.enabled}")
        print(f"  Min file size: {filter.min_file_size} bytes")
        print(f"  Min dimensions: {filter.min_width}x{filter.min_height}")
        print(f"  Excluded patterns: {filter.excluded_patterns}")

        print("\nAll photo filter tests passed!")

    except Exception as e:
        print(f"✗ Test failed: {e}")
