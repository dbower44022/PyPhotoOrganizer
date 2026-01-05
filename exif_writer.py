"""
EXIF Writing Module

Writes corrected date information to image EXIF data.
Allows users to permanently fix date metadata in source files.
"""

from PIL import Image
import piexif
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)


def write_exif_date(file_path, year, month, day):
    """
    Write corrected date to EXIF DateTimeOriginal field.

    Args:
        file_path: Path to image file
        year: Year as string or int
        month: Month as string or int (zero-padded if string)
        day: Day as string or int (zero-padded if string)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Validate file exists
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return False

        # Convert to strings and ensure zero-padding
        year_str = str(year) if isinstance(year, int) else year
        month_str = f"{int(month):02d}" if month else "01"
        day_str = f"{int(day):02d}" if day else "01"

        # Validate date components
        try:
            # Validate by creating a datetime object
            datetime(int(year_str), int(month_str), int(day_str))
        except ValueError as e:
            logger.error(f"Invalid date: {year_str}-{month_str}-{day_str}. Error: {e}")
            return False

        # Check file extension
        extension = os.path.splitext(file_path)[1].lower()
        supported_formats = ['.jpg', '.jpeg', '.tif', '.tiff']

        if extension not in supported_formats:
            logger.warning(f"Unsupported format for EXIF writing: {extension}. Supported: {supported_formats}")
            return False

        # Open image
        img = Image.open(file_path)

        # Load existing EXIF or create new
        try:
            exif_dict = piexif.load(img.info.get('exif', b''))
        except Exception:
            # Create new EXIF structure if none exists
            exif_dict = {
                '0th': {},
                'Exif': {},
                'GPS': {},
                '1st': {},
                'thumbnail': None
            }

        # Format date as EXIF expects: "YYYY:MM:DD HH:MM:SS"
        # Use noon (12:00:00) as default time
        datetime_str = f"{year_str}:{month_str}:{day_str} 12:00:00"

        # Write to EXIF DateTimeOriginal (tag 36867) - most important for photo date
        exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal] = datetime_str.encode('utf-8')

        # Also write to DateTime (tag 306) for compatibility
        exif_dict['0th'][piexif.ImageIFD.DateTime] = datetime_str.encode('utf-8')

        # Write to DateTimeDigitized for completeness
        exif_dict['Exif'][piexif.ExifIFD.DateTimeDigitized] = datetime_str.encode('utf-8')

        # Dump EXIF back to bytes
        exif_bytes = piexif.dump(exif_dict)

        # Save image with new EXIF
        # Get image mode and format
        img_format = img.format if img.format else 'JPEG'

        # Save with EXIF
        img.save(file_path, format=img_format, exif=exif_bytes, quality=95)
        img.close()

        logger.info(f"Successfully wrote EXIF date to {file_path}: {datetime_str}")
        return True

    except piexif.InvalidImageDataError as e:
        logger.error(f"Invalid image data in {file_path}: {e}")
        return False

    except Exception as e:
        logger.error(f"Failed to write EXIF to {file_path}: {str(e)}")
        return False


def read_exif_date(file_path):
    """
    Read EXIF DateTimeOriginal from file.

    Supports JPEG, TIFF, and other formats with EXIF data.

    Args:
        file_path: Path to image file

    Returns:
        tuple: (year, month, day) as strings, or (None, None, None) if not found
    """
    try:
        # Check file exists
        if not os.path.exists(file_path):
            logger.error(f"File does not exist: {file_path}")
            return None, None, None

        datetime_str = None

        # Method 1: Try using piexif (works for JPEG and TIFF)
        try:
            exif_dict = piexif.load(file_path)
            if 'Exif' in exif_dict and piexif.ExifIFD.DateTimeOriginal in exif_dict['Exif']:
                datetime_bytes = exif_dict['Exif'][piexif.ExifIFD.DateTimeOriginal]
                if isinstance(datetime_bytes, bytes):
                    datetime_str = datetime_bytes.decode('utf-8')
                else:
                    datetime_str = str(datetime_bytes)
        except Exception as e:
            logger.debug(f"piexif failed for {file_path}: {e}")

        # Method 2: Fall back to PIL's getexif() (works for many formats)
        if datetime_str is None:
            try:
                img = Image.open(file_path)
                # Use getexif() which is more universal than _getexif()
                exif_data = img.getexif()
                if exif_data:
                    # DateTimeOriginal tag ID is 36867
                    datetime_str = exif_data.get(36867)
                    if datetime_str is None:
                        # Try DateTime tag (306) as fallback
                        datetime_str = exif_data.get(306)
                img.close()
            except Exception as e:
                logger.debug(f"PIL getexif() failed for {file_path}: {e}")

        # Method 3: For JPEG, try _getexif() as last resort
        if datetime_str is None:
            try:
                img = Image.open(file_path)
                if hasattr(img, '_getexif') and callable(img._getexif):
                    exif_data = img._getexif()
                    if exif_data:
                        datetime_str = exif_data.get(36867)  # DateTimeOriginal
                img.close()
            except Exception as e:
                logger.debug(f"PIL _getexif() failed for {file_path}: {e}")

        if datetime_str is None:
            logger.debug(f"No EXIF date found in {file_path}")
            return None, None, None

        # Parse EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
        try:
            date_part = datetime_str.split(' ')[0]  # Get just the date part
            year, month, day = date_part.split(':')
            return year, month, day
        except Exception as e:
            logger.error(f"Failed to parse EXIF date '{datetime_str}': {e}")
            return None, None, None

    except Exception as e:
        logger.error(f"Failed to read EXIF from {file_path}: {str(e)}")
        return None, None, None


def verify_exif_write(file_path, expected_year, expected_month, expected_day):
    """
    Verify that EXIF date was written correctly.

    Args:
        file_path: Path to image file
        expected_year: Expected year as string
        expected_month: Expected month as string (zero-padded)
        expected_day: Expected day as string (zero-padded)

    Returns:
        bool: True if verification successful, False otherwise
    """
    try:
        year, month, day = read_exif_date(file_path)

        if year is None:
            logger.error(f"Verification failed: Could not read EXIF date from {file_path}")
            return False

        # Ensure expected values are zero-padded for comparison
        expected_month_padded = f"{int(expected_month):02d}"
        expected_day_padded = f"{int(expected_day):02d}"

        if year == str(expected_year) and month == expected_month_padded and day == expected_day_padded:
            logger.info(f"EXIF verification successful for {file_path}: {year}-{month}-{day}")
            return True
        else:
            logger.error(f"EXIF verification failed for {file_path}. Expected: {expected_year}-{expected_month_padded}-{expected_day_padded}, Got: {year}-{month}-{day}")
            return False

    except Exception as e:
        logger.error(f"EXIF verification error for {file_path}: {e}")
        return False


def update_file_hash_after_modification(database_path, old_hash, file_path, reason='exif_edit'):
    """
    Recalculate file hash after modification (e.g., EXIF write) and update database.

    This function:
    1. Calculates the new hash of the modified file
    2. Adds the new hash to FileHashHistory
    3. Updates UniquePhotos.file_hash to the new value
    4. Updates related tables (UnreliableDates)

    The old hash is preserved in FileHashHistory for duplicate detection.
    A file processed before EXIF modification will still be detected as a duplicate
    after modification because we check all historical hashes.

    Args:
        database_path: Path to the database file
        old_hash: The current file_hash in UniquePhotos (before modification)
        file_path: Path to the modified file (to recalculate hash)
        reason: Reason for the modification ('exif_edit', 'date_correction', etc.)

    Returns:
        str or None: The new hash if successful, None if failed
    """
    try:
        # Import here to avoid circular imports
        from DuplicateFileDetection import hash_file, PhotoDatabase

        # Verify file exists
        if not os.path.exists(file_path):
            logger.error(f"Cannot update hash - file does not exist: {file_path}")
            return None

        # Calculate new hash
        new_hash = hash_file(file_path)

        if new_hash == old_hash:
            logger.info(f"Hash unchanged after modification: {file_path}")
            return old_hash

        # Update database
        with PhotoDatabase(database_path) as db:
            success = db.add_hash_to_history(old_hash, new_hash, reason)

            if success:
                logger.info(f"✓ Hash history updated: {old_hash[:16]}... -> {new_hash[:16]}... (reason: {reason})")
                return new_hash
            else:
                logger.error(f"✗ Failed to update hash history for {file_path}")
                return None

    except Exception as e:
        logger.error(f"Failed to update file hash after modification: {e}")
        return None


def get_current_hash_for_file(database_path, file_path):
    """
    Look up the current hash for a file in the database by its path.

    Args:
        database_path: Path to the database file
        file_path: Path to the file (as stored in file_name column)

    Returns:
        str or None: The current file_hash if found, None otherwise
    """
    try:
        from DuplicateFileDetection import PhotoDatabase

        with PhotoDatabase(database_path) as db:
            db.cursor.execute(
                "SELECT file_hash FROM UniquePhotos WHERE file_name = ? LIMIT 1",
                (file_path,)
            )
            result = db.cursor.fetchone()
            return result[0] if result else None

    except Exception as e:
        logger.error(f"Failed to get hash for file {file_path}: {e}")
        return None
