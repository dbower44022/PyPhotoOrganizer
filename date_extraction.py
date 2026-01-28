"""
Date Extraction Module

Provides functions for extracting creation dates from various file types
and metadata sources (EXIF, IPTC, XMP, video metadata, OS timestamps).

This module implements a priority-based date extraction system:
1. EXIF DateTimeOriginal (highest priority)
2. Other EXIF dates (DateTimeDigitized, GPSDateTime, etc.)
3. IPTC Date Created
4. XMP CreateDate
5. Video metadata (ffprobe, QuickTime atoms)
6. OS file timestamps (lowest priority)

Functions:
    get_creation_date: Main entry point for date extraction
    extract_exif_dates: Extract all EXIF date fields
    extract_iptc_date: Extract IPTC Date Created
    extract_xmp_date: Extract XMP date fields
    extract_video_date: Extract video creation time
"""

import datetime
import logging
import os
import re
import struct
import subprocess
from typing import Dict, Optional, Tuple, Any

from PIL import Image
from PIL import IptcImagePlugin

import constants
import utils

logger = utils.setup_logger(__name__, "date_extraction.log")


# ============================================================================
# Date Validation and Parsing
# ============================================================================

def validate_exif_date(date_string: str) -> Optional[datetime.datetime]:
    """
    Parse and validate an EXIF date string.

    EXIF dates are typically in format: "YYYY:MM:DD HH:MM:SS"
    Some variations include milliseconds or timezone info.

    Parameters:
        date_string (str): The date string to parse

    Returns:
        datetime.datetime or None if parsing fails
    """
    if not date_string or not isinstance(date_string, str):
        return None

    date_string = date_string.strip()

    # Skip obviously invalid dates
    if date_string.startswith('0000') or date_string == '':
        return None

    # Common EXIF date formats
    formats = [
        '%Y:%m:%d %H:%M:%S',      # Standard EXIF
        '%Y-%m-%d %H:%M:%S',      # ISO-like
        '%Y:%m:%d %H:%M:%S.%f',   # With milliseconds
        '%Y-%m-%dT%H:%M:%S',      # ISO 8601
        '%Y/%m/%d %H:%M:%S',      # Slash separator
    ]

    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(date_string, fmt)
            # Validate year is reasonable
            if constants.MIN_REASONABLE_YEAR <= parsed.year <= constants.MAX_REASONABLE_YEAR:
                return parsed
        except ValueError:
            continue

    logger.debug(f"Could not parse EXIF date: {date_string}")
    return None


def check_date_reliability(
    year: str,
    month: str,
    day: str,
    has_metadata: bool
) -> bool:
    """
    Check if a date is considered reliable.

    A date is unreliable if:
    - It's the fallback date (year 1000)
    - Year is outside reasonable range
    - No metadata was present

    Parameters:
        year (str): Year as string
        month (str): Month as string
        day (str): Day as string
        has_metadata (bool): Whether date came from metadata (EXIF/IPTC/etc.)

    Returns:
        bool: True if date is considered reliable
    """
    try:
        year_int = int(year)

        # Fallback date is unreliable
        if year_int == constants.FALLBACK_YEAR:
            return False

        # Year outside reasonable range is unreliable
        if year_int < constants.MIN_REASONABLE_YEAR or year_int > constants.MAX_REASONABLE_YEAR:
            return False

        # No metadata means less reliable
        if not has_metadata:
            return False

        return True

    except (ValueError, TypeError):
        return False


# ============================================================================
# EXIF Date Extraction
# ============================================================================

def extract_exif_dates(img: Image.Image) -> Dict[str, datetime.datetime]:
    """
    Extract all available EXIF date fields from an image.

    Reads from multiple IFDs (Image File Directories) as PIL 10.x
    requires accessing sub-IFDs for EXIF-specific tags.

    Parameters:
        img: PIL Image object (must be open)

    Returns:
        Dict mapping date field names to datetime objects:
            - 'DateTimeOriginal': When shutter clicked (best)
            - 'DateTimeDigitized': When digitized
            - 'GPSDateTime': GPS timestamp
            - 'DateTime': File modification in EXIF
            - 'PreviewDateTime': When preview generated
    """
    from PIL.ExifTags import TAGS, IFD

    exif_dates = {}

    try:
        # Get base EXIF data
        exif_data = img.getexif()
        if not exif_data:
            return exif_dates

        # Tag IDs for date fields
        # Base IFD
        TAG_DATETIME = 306  # DateTime

        # EXIF IFD
        TAG_DATETIME_ORIGINAL = 36867     # DateTimeOriginal
        TAG_DATETIME_DIGITIZED = 36868    # DateTimeDigitized

        # GPS IFD
        TAG_GPS_DATESTAMP = 29  # GPSDateStamp
        TAG_GPS_TIMESTAMP = 7   # GPSTimeStamp

        # Check base IFD for DateTime
        if TAG_DATETIME in exif_data:
            dt = validate_exif_date(str(exif_data[TAG_DATETIME]))
            if dt:
                exif_dates['DateTime'] = dt

        # Check EXIF sub-IFD
        try:
            exif_ifd = exif_data.get_ifd(IFD.Exif)
            if exif_ifd:
                if TAG_DATETIME_ORIGINAL in exif_ifd:
                    dt = validate_exif_date(str(exif_ifd[TAG_DATETIME_ORIGINAL]))
                    if dt:
                        exif_dates['DateTimeOriginal'] = dt

                if TAG_DATETIME_DIGITIZED in exif_ifd:
                    dt = validate_exif_date(str(exif_ifd[TAG_DATETIME_DIGITIZED]))
                    if dt:
                        exif_dates['DateTimeDigitized'] = dt
        except Exception as e:
            logger.debug(f"Could not read EXIF IFD: {e}")

        # Check GPS sub-IFD for GPSDateTime
        try:
            gps_ifd = exif_data.get_ifd(IFD.GPSInfo)
            if gps_ifd:
                gps_date = gps_ifd.get(TAG_GPS_DATESTAMP)
                gps_time = gps_ifd.get(TAG_GPS_TIMESTAMP)

                if gps_date and gps_time:
                    # GPS date format: "YYYY:MM:DD"
                    # GPS time format: tuple of rationals (hour, minute, second)
                    try:
                        if isinstance(gps_date, str):
                            date_parts = gps_date.split(':')
                            if len(date_parts) == 3:
                                year, month, day = map(int, date_parts)

                                # Extract time (handle rational numbers)
                                if isinstance(gps_time, tuple) and len(gps_time) >= 3:
                                    hour = int(gps_time[0])
                                    minute = int(gps_time[1])
                                    second = int(gps_time[2])

                                    gps_datetime = datetime.datetime(
                                        year, month, day, hour, minute, second
                                    )
                                    if constants.MIN_REASONABLE_YEAR <= year <= constants.MAX_REASONABLE_YEAR:
                                        exif_dates['GPSDateTime'] = gps_datetime
                    except (ValueError, TypeError) as e:
                        logger.debug(f"Could not parse GPS datetime: {e}")
        except Exception as e:
            logger.debug(f"Could not read GPS IFD: {e}")

    except Exception as e:
        logger.warning(f"Error extracting EXIF dates: {e}")

    return exif_dates


def select_best_exif_date(
    exif_dates: Dict[str, datetime.datetime]
) -> Tuple[Optional[datetime.datetime], str]:
    """
    Select the best date from available EXIF dates.

    Priority order:
    1. DateTimeOriginal (when shutter clicked - most authoritative)
    2. Earliest of remaining dates (DateTimeDigitized, GPSDateTime, etc.)

    Parameters:
        exif_dates: Dict of date field names to datetime objects

    Returns:
        Tuple of (best_date, source_name) or (None, '') if no valid dates
    """
    if not exif_dates:
        return (None, '')

    # Priority 1: DateTimeOriginal
    if 'DateTimeOriginal' in exif_dates:
        return (exif_dates['DateTimeOriginal'], 'exif')

    # Priority 2: Find earliest date from remaining sources
    source_priority = [
        ('DateTimeDigitized', 'exif_digitized'),
        ('GPSDateTime', 'exif_gps'),
        ('DateTime', 'exif_datetime'),
        ('PreviewDateTime', 'exif_preview'),
    ]

    earliest_date = None
    earliest_source = ''

    for field_name, source_name in source_priority:
        if field_name in exif_dates:
            dt = exif_dates[field_name]
            if earliest_date is None or dt < earliest_date:
                earliest_date = dt
                earliest_source = source_name

    return (earliest_date, earliest_source)


# ============================================================================
# IPTC Date Extraction
# ============================================================================

def extract_iptc_date(img: Image.Image) -> Optional[datetime.datetime]:
    """
    Extract date from IPTC metadata.

    IPTC Date Created is tag (2, 55) with format YYYYMMDD.
    IPTC Time Created is tag (2, 60) with format HHMMSS.

    Parameters:
        img: PIL Image object (must be open)

    Returns:
        datetime.datetime or None if not found/invalid
    """
    try:
        iptc_data = IptcImagePlugin.getiptcinfo(img)
        if not iptc_data:
            return None

        # IPTC Date Created is tag (2, 55)
        iptc_date = iptc_data.get((2, 55))
        iptc_time = iptc_data.get((2, 60))

        if not iptc_date:
            return None

        # Decode if bytes
        if isinstance(iptc_date, bytes):
            iptc_date = iptc_date.decode('utf-8', errors='ignore')

        # Parse IPTC date (YYYYMMDD format)
        if len(iptc_date) >= 8 and iptc_date[:8].isdigit():
            year = int(iptc_date[0:4])
            month = int(iptc_date[4:6])
            day = int(iptc_date[6:8])

            # Parse time if available
            hour, minute, second = 0, 0, 0
            if iptc_time:
                if isinstance(iptc_time, bytes):
                    iptc_time = iptc_time.decode('utf-8', errors='ignore')
                if len(iptc_time) >= 6:
                    try:
                        hour = int(iptc_time[0:2])
                        minute = int(iptc_time[2:4])
                        second = int(iptc_time[4:6])
                    except ValueError:
                        pass

            try:
                return datetime.datetime(year, month, day, hour, minute, second)
            except ValueError as e:
                logger.debug(f"Invalid IPTC date values: {iptc_date} - {e}")

    except Exception as e:
        logger.warning(f"Error reading IPTC data: {e}")

    return None


# ============================================================================
# XMP Date Extraction
# ============================================================================

def extract_xmp_date(img: Image.Image) -> Optional[datetime.datetime]:
    """
    Extract date from XMP metadata.

    XMP (Adobe's Extensible Metadata Platform) stores dates in ISO 8601 format.
    Fields checked: xmp:CreateDate, photoshop:DateCreated, exif:DateTimeOriginal.

    Parameters:
        img: PIL Image object (must be open)

    Returns:
        datetime.datetime or None if not found/invalid
    """
    try:
        xmp_data = img.info.get('xmp')
        if not xmp_data:
            return None

        # Decode if bytes
        if isinstance(xmp_data, bytes):
            xmp_str = xmp_data.decode('utf-8', errors='ignore')
        else:
            xmp_str = str(xmp_data)

        # XMP date patterns to search for (in priority order)
        patterns = [
            r'<xmp:CreateDate>([^<]+)</xmp:CreateDate>',
            r'xmp:CreateDate="([^"]+)"',
            r'<photoshop:DateCreated>([^<]+)</photoshop:DateCreated>',
            r'photoshop:DateCreated="([^"]+)"',
            r'<exif:DateTimeOriginal>([^<]+)</exif:DateTimeOriginal>',
            r'exif:DateTimeOriginal="([^"]+)"',
            r'<xmp:ModifyDate>([^<]+)</xmp:ModifyDate>',
            r'xmp:ModifyDate="([^"]+)"',
        ]

        for pattern in patterns:
            match = re.search(pattern, xmp_str, re.IGNORECASE | re.DOTALL)
            if match:
                date_str = match.group(1).strip()
                parsed = parse_xmp_date(date_str)
                if parsed:
                    return parsed

    except Exception as e:
        logger.warning(f"Error reading XMP data: {e}")

    return None


def parse_xmp_date(date_str: str) -> Optional[datetime.datetime]:
    """
    Parse an XMP date string (ISO 8601 format).

    Handles various formats:
    - YYYY-MM-DDTHH:MM:SS
    - YYYY-MM-DDTHH:MM:SS.sss
    - YYYY-MM-DDTHH:MM:SS+HH:MM
    - YYYY-MM-DDTHH:MM:SSZ
    - YYYY-MM-DD

    Parameters:
        date_str: The date string to parse

    Returns:
        datetime.datetime or None if parsing fails
    """
    if not date_str:
        return None

    date_str = date_str.strip()

    # Handle timezone suffix
    if date_str.endswith('Z'):
        date_str = date_str[:-1]

    # Remove colon from timezone offset (+05:30 -> +0530)
    tz_match = re.search(r'([+-])(\d{2}):(\d{2})$', date_str)
    if tz_match:
        date_str = date_str[:tz_match.start()] + tz_match.group(1) + tz_match.group(2) + tz_match.group(3)

    # Formats to try
    formats = [
        '%Y-%m-%dT%H:%M:%S%z',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%d',
        '%Y:%m:%d %H:%M:%S',
    ]

    for fmt in formats:
        try:
            parsed = datetime.datetime.strptime(date_str, fmt)
            if parsed.tzinfo is not None:
                parsed = parsed.replace(tzinfo=None)
            return parsed
        except ValueError:
            continue

    return None


# ============================================================================
# Filename/Path Date Extraction
# ============================================================================

# Common filename date patterns (ordered by specificity - most specific first)
# Each tuple: (compiled_regex, strptime_format_or_callable, has_time)
_FILENAME_DATE_PATTERNS = None  # Lazily initialized


def _get_filename_patterns():
    """
    Get compiled filename date patterns (lazy initialization).

    Returns:
        List of tuples: (compiled_regex, format_string_or_groups, has_time)
    """
    global _FILENAME_DATE_PATTERNS
    if _FILENAME_DATE_PATTERNS is not None:
        return _FILENAME_DATE_PATTERNS

    _FILENAME_DATE_PATTERNS = [
        # IMG_YYYYMMDD_HHMMSS (Android cameras, very common)
        (re.compile(r'(?:IMG|VID|PXL|MVIMG|SAVE)_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'),
         'groups_datetime', True),

        # YYYYMMDD_HHMMSS (generic with underscore)
        (re.compile(r'(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})'),
         'groups_datetime', True),

        # YYYYMMDD-HHMMSS (generic with hyphen)
        (re.compile(r'(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})'),
         'groups_datetime', True),

        # YYYY-MM-DD_HH-MM-SS (ISO-like with underscores/hyphens)
        (re.compile(r'(\d{4})-(\d{2})-(\d{2})[_\s](\d{2})-(\d{2})-(\d{2})'),
         'groups_datetime', True),

        # YYYY-MM-DD HH.MM.SS (iOS sharing format)
        (re.compile(r'(\d{4})-(\d{2})-(\d{2})\s+(?:at\s+)?(\d{2})\.(\d{2})\.(\d{2})'),
         'groups_datetime', True),

        # Screenshot_YYYYMMDD-HHMMSS (Android screenshots)
        (re.compile(r'Screenshot_(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})'),
         'groups_datetime', True),

        # Screenshot_YYYY-MM-DD-HH-MM-SS (iOS screenshots)
        (re.compile(r'Screenshot[_\s](\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})-(\d{2})'),
         'groups_datetime', True),

        # IMG-YYYYMMDD-WA (WhatsApp images)
        (re.compile(r'IMG-(\d{4})(\d{2})(\d{2})-WA'),
         'groups_date', False),

        # YYYY-MM-DD (ISO date, standalone or with non-digit suffix)
        (re.compile(r'(\d{4})-(\d{2})-(\d{2})(?!\d)'),
         'groups_date', False),

        # YYYYMMDD (compact date - be careful, must be validated)
        (re.compile(r'(?:^|[^\d])(\d{4})(\d{2})(\d{2})(?:[^\d]|$)'),
         'groups_date', False),
    ]

    return _FILENAME_DATE_PATTERNS


def _parse_filename_date_groups(
    match: re.Match,
    format_type: str,
    has_time: bool
) -> Optional[datetime.datetime]:
    """
    Parse date from regex match groups.

    Parameters:
        match: Regex match object with captured groups
        format_type: Either 'groups_datetime' (6 groups) or 'groups_date' (3 groups)
        has_time: Whether time components are present

    Returns:
        datetime.datetime or None if invalid
    """
    try:
        groups = match.groups()

        if format_type == 'groups_datetime' and len(groups) >= 6:
            year = int(groups[0])
            month = int(groups[1])
            day = int(groups[2])
            hour = int(groups[3])
            minute = int(groups[4])
            second = int(groups[5])
        elif format_type == 'groups_date' and len(groups) >= 3:
            year = int(groups[0])
            month = int(groups[1])
            day = int(groups[2])
            hour, minute, second = 12, 0, 0  # Default to noon
        else:
            return None

        # Validate ranges
        if not (constants.MIN_REASONABLE_YEAR <= year <= constants.MAX_REASONABLE_YEAR):
            return None
        if not (1 <= month <= 12):
            return None
        if not (1 <= day <= 31):
            return None
        if has_time:
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                return None

        return datetime.datetime(year, month, day, hour, minute, second)

    except (ValueError, TypeError):
        return None


def extract_filename_date(file_path: str) -> Optional[datetime.datetime]:
    """
    Extract date from filename using common patterns.

    Recognizes patterns like:
    - IMG_20230415_123456.jpg (Android cameras)
    - VID_20230415_123456.mp4 (Android video)
    - 2023-04-15_12-34-56.jpg (ISO-like)
    - Screenshot_20230415-123456.png
    - IMG-20230415-WA0001.jpg (WhatsApp)
    - 2023-04-15.jpg
    - 20230415.jpg

    Parameters:
        file_path (str): Full path to the file

    Returns:
        datetime.datetime or None if no valid date found
    """
    # Get just the filename without extension
    filename = os.path.basename(file_path)
    filename_no_ext = os.path.splitext(filename)[0]

    patterns = _get_filename_patterns()

    for pattern, format_type, has_time in patterns:
        match = pattern.search(filename_no_ext)
        if match:
            parsed = _parse_filename_date_groups(match, format_type, has_time)
            if parsed:
                logger.debug(f"Extracted date {parsed} from filename: {filename}")
                return parsed

    return None


# Path date patterns (for extracting dates from directory structure)
_PATH_DATE_PATTERNS = None  # Lazily initialized


def _get_path_patterns():
    """
    Get compiled path date patterns (lazy initialization).

    Returns:
        List of tuples: (compiled_regex, extraction_callable)
    """
    global _PATH_DATE_PATTERNS
    if _PATH_DATE_PATTERNS is not None:
        return _PATH_DATE_PATTERNS

    # Platform-independent path separator pattern
    sep = r'[\\/]'

    _PATH_DATE_PATTERNS = [
        # /YYYY/MM/DD/ (full date path)
        (re.compile(f'{sep}(\\d{{4}}){sep}(\\d{{2}}){sep}(\\d{{2}}){sep}'),
         'ymd'),

        # /YYYY-MM-DD/ (ISO date folder)
        (re.compile(f'{sep}(\\d{{4}})-(\\d{{2}})-(\\d{{2}}){sep}'),
         'ymd'),

        # /YYYY/MM/ (year and month)
        (re.compile(f'{sep}(\\d{{4}}){sep}(\\d{{2}}){sep}(?!\\d)'),
         'ym'),

        # /YYYY-MM/ (year-month folder)
        (re.compile(f'{sep}(\\d{{4}})-(\\d{{2}}){sep}'),
         'ym'),

        # /YYYY/ (year only - less reliable, use with caution)
        (re.compile(f'{sep}(\\d{{4}}){sep}(?!\\d)'),
         'y'),
    ]

    return _PATH_DATE_PATTERNS


def extract_path_date(file_path: str) -> Tuple[Optional[datetime.datetime], str]:
    """
    Extract date from directory path.

    Recognizes folder structures like:
    - /Photos/2023/04/15/photo.jpg -> 2023-04-15
    - /Archive/2023-04-15/photo.jpg -> 2023-04-15
    - /Photos/2023/04/photo.jpg -> 2023-04-01 (day defaults to 1)
    - /Photos/2023/photo.jpg -> 2023-01-01 (month/day default to 1)

    Parameters:
        file_path (str): Full path to the file

    Returns:
        Tuple of (datetime, precision) where precision is:
        - 'ymd': Full date extracted
        - 'ym': Year and month extracted (day=1)
        - 'y': Year only extracted (month=1, day=1)
        - (None, '') if no date found
    """
    # Normalize path separators for consistent matching
    normalized_path = file_path.replace('\\', '/')

    patterns = _get_path_patterns()

    for pattern, precision in patterns:
        match = pattern.search(normalized_path)
        if match:
            try:
                groups = match.groups()
                year = int(groups[0])

                # Validate year
                if not (constants.MIN_REASONABLE_YEAR <= year <= constants.MAX_REASONABLE_YEAR):
                    continue

                if precision == 'ymd' and len(groups) >= 3:
                    month = int(groups[1])
                    day = int(groups[2])
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        dt = datetime.datetime(year, month, day, 12, 0, 0)
                        logger.debug(f"Extracted date {dt} from path (ymd): {file_path}")
                        return (dt, 'ymd')

                elif precision == 'ym' and len(groups) >= 2:
                    month = int(groups[1])
                    if 1 <= month <= 12:
                        dt = datetime.datetime(year, month, 1, 12, 0, 0)
                        logger.debug(f"Extracted date {dt} from path (ym): {file_path}")
                        return (dt, 'ym')

                elif precision == 'y':
                    dt = datetime.datetime(year, 1, 1, 12, 0, 0)
                    logger.debug(f"Extracted date {dt} from path (y): {file_path}")
                    return (dt, 'y')

            except (ValueError, TypeError):
                continue

    return (None, '')


def extract_filename_or_path_date(
    file_path: str
) -> Tuple[Optional[datetime.datetime], str]:
    """
    Extract date from filename first, then fall back to path.

    Filename dates are preferred as they're typically more specific
    (often include time). Path dates are used as fallback.

    Parameters:
        file_path (str): Full path to the file

    Returns:
        Tuple of (datetime, source) where source is:
        - 'filename': Date extracted from filename
        - 'path_ymd': Full date from path
        - 'path_ym': Year/month from path
        - 'path_y': Year only from path
        - (None, '') if no date found
    """
    # Try filename first (more specific, often has time)
    filename_date = extract_filename_date(file_path)
    if filename_date:
        return (filename_date, 'filename')

    # Fall back to path
    path_date, precision = extract_path_date(file_path)
    if path_date:
        return (path_date, f'path_{precision}')

    return (None, '')


# ============================================================================
# Video Date Extraction
# ============================================================================

def is_video_file(file_path: str) -> bool:
    """
    Check if a file is a video based on extension.

    Parameters:
        file_path (str): Path to the file

    Returns:
        bool: True if file is a video
    """
    ext = os.path.splitext(file_path)[1].lower()
    return ext in [e.lower() for e in constants.VIDEO_EXTENSIONS]


def extract_video_date(file_path: str) -> Tuple[Optional[datetime.datetime], str]:
    """
    Extract creation date from video file.

    Tries multiple methods:
    1. ffprobe (most reliable)
    2. mutagen library
    3. QuickTime atom parsing

    Parameters:
        file_path (str): Path to the video file

    Returns:
        Tuple of (datetime, source) or (None, '') if not found
    """
    # Try ffprobe first
    dt, source = _try_ffprobe_date(file_path)
    if dt:
        return (dt, source)

    # Try mutagen
    dt, source = _try_mutagen_date(file_path)
    if dt:
        return (dt, source)

    # Try QuickTime atom parsing
    dt = _try_quicktime_date(file_path)
    if dt:
        return (dt, 'video_quicktime')

    return (None, '')


def _try_ffprobe_date(file_path: str) -> Tuple[Optional[datetime.datetime], str]:
    """Try to extract date using ffprobe."""
    try:
        # Run ffprobe to get metadata
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json',
             '-show_format', file_path],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode == 0:
            import json
            metadata = json.loads(result.stdout)
            tags = metadata.get('format', {}).get('tags', {})

            # Look for creation_time tag
            creation_time = tags.get('creation_time') or tags.get('Creation_Time')
            if creation_time:
                parsed = _parse_video_date(creation_time)
                if parsed:
                    return (parsed, 'video_metadata')

    except FileNotFoundError:
        logger.debug("ffprobe not found - skipping")
    except subprocess.TimeoutExpired:
        logger.warning(f"ffprobe timeout for {file_path}")
    except Exception as e:
        logger.debug(f"ffprobe error: {e}")

    return (None, '')


def _try_mutagen_date(file_path: str) -> Tuple[Optional[datetime.datetime], str]:
    """Try to extract date using mutagen library."""
    try:
        from mutagen.mp4 import MP4
        from mutagen import MutagenError

        mp4 = MP4(file_path)
        # Check ©day tag (creation date)
        if '©day' in mp4:
            date_str = mp4['©day'][0]
            parsed = _parse_video_date(date_str)
            if parsed:
                return (parsed, 'video_metadata')

    except ImportError:
        logger.debug("mutagen not installed - skipping")
    except Exception as e:
        logger.debug(f"mutagen error: {e}")

    return (None, '')


def _try_quicktime_date(file_path: str) -> Optional[datetime.datetime]:
    """
    Parse QuickTime mvhd atom for creation time.

    The mvhd atom contains a creation_time field as seconds since 1904-01-01.
    """
    try:
        with open(file_path, 'rb') as f:
            # Search for mvhd atom
            data = f.read(1024 * 1024)  # Read first 1MB

            # Look for 'mvhd' marker
            mvhd_pos = data.find(b'mvhd')
            if mvhd_pos == -1:
                return None

            # Skip version/flags (4 bytes after 'mvhd')
            offset = mvhd_pos + 4
            if offset + 4 > len(data):
                return None

            # Read creation_time (4 bytes for version 0, 8 bytes for version 1)
            version = data[offset]
            offset += 4  # Skip version/flags

            if version == 0:
                if offset + 4 > len(data):
                    return None
                creation_time = struct.unpack('>I', data[offset:offset+4])[0]
            else:
                if offset + 8 > len(data):
                    return None
                creation_time = struct.unpack('>Q', data[offset:offset+8])[0]

            # Convert from Mac epoch (1904-01-01) to datetime
            if creation_time > 0:
                mac_epoch = datetime.datetime(1904, 1, 1)
                dt = mac_epoch + datetime.timedelta(seconds=creation_time)

                # Validate reasonable date
                if constants.MIN_REASONABLE_YEAR <= dt.year <= constants.MAX_REASONABLE_YEAR:
                    return dt

    except Exception as e:
        logger.debug(f"QuickTime atom parsing error: {e}")

    return None


def _parse_video_date(date_str: str) -> Optional[datetime.datetime]:
    """Parse various video date string formats."""
    if not date_str:
        return None

    date_str = date_str.strip()

    # Handle UTC indicator
    if date_str.endswith('Z'):
        date_str = date_str[:-1]

    formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%d',
        '%Y',
    ]

    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            continue

    return None


# ============================================================================
# OS Timestamp Extraction
# ============================================================================

def get_os_timestamp(file_path: str) -> datetime.datetime:
    """
    Get file timestamp from operating system.

    Uses creation time on Windows, birth time on macOS if available,
    or modification time as fallback.

    Parameters:
        file_path (str): Path to the file

    Returns:
        datetime.datetime: File timestamp
    """
    if os.name == 'nt':  # Windows
        try:
            creation_time = os.path.getctime(file_path)
        except Exception:
            creation_time = os.path.getmtime(file_path)
        return datetime.datetime.fromtimestamp(creation_time)
    else:  # macOS/Linux
        stat = os.stat(file_path)
        try:
            return datetime.datetime.fromtimestamp(stat.st_birthtime)
        except AttributeError:
            return datetime.datetime.fromtimestamp(stat.st_mtime)


# ============================================================================
# Main Entry Point
# ============================================================================

def get_creation_date(
    file_path: str,
    database_path: Optional[str] = None
) -> Tuple[str, str, str, str, bool]:
    """
    Get the creation date of a file from the best available source.

    This is the main entry point for date extraction. It tries multiple
    sources in priority order and returns the best date found.

    Priority for images:
    1. EXIF DateTimeOriginal
    2. Other EXIF dates (earliest wins)
    3. IPTC Date Created
    4. XMP CreateDate
    5. Filename date (e.g., IMG_20230415_123456.jpg)
    6. Path date (e.g., /Photos/2023/04/15/)
    7. OS file timestamp
    8. Fallback date (year 1000)

    Priority for videos:
    1. Video metadata (ffprobe)
    2. QuickTime atom
    3. Filename date
    4. Path date
    5. OS file timestamp
    6. Fallback date

    Parameters:
        file_path (str): Path to the file
        database_path (str, optional): Path to database (for future use)

    Returns:
        Tuple[str, str, str, str, bool]:
            - year: Year as string (e.g., "2024")
            - month: Month as zero-padded string (e.g., "01")
            - day: Day as zero-padded string (e.g., "15")
            - date_source: Source of the date ('exif', 'iptc', 'filename', 'path', etc.)
            - is_reliable: Whether the date is considered reliable
    """
    import pillow_heif

    try:
        # Get OS timestamp as fallback
        creation_date = get_os_timestamp(file_path)
        date_source = 'os_metadata'
        has_metadata = False

        # Handle video files separately
        if is_video_file(file_path):
            video_date, video_source = extract_video_date(file_path)
            if video_date:
                creation_date = video_date
                date_source = video_source
                has_metadata = True

            # If no video metadata, try filename/path
            if not has_metadata:
                fp_date, fp_source = extract_filename_or_path_date(file_path)
                if fp_date:
                    creation_date = fp_date
                    date_source = fp_source
                    has_metadata = True

        else:
            # Image file - try metadata sources
            try:
                # Register HEIF opener
                pillow_heif.register_heif_opener()

                with Image.open(file_path) as img:
                    # Try EXIF
                    exif_dates = extract_exif_dates(img)
                    if exif_dates:
                        best_date, best_source = select_best_exif_date(exif_dates)
                        if best_date:
                            creation_date = best_date
                            date_source = best_source
                            has_metadata = True

                    # If no EXIF, try IPTC
                    if not has_metadata:
                        iptc_date = extract_iptc_date(img)
                        if iptc_date:
                            creation_date = iptc_date
                            date_source = 'iptc'
                            has_metadata = True

                    # If no IPTC, try XMP
                    if not has_metadata:
                        xmp_date = extract_xmp_date(img)
                        if xmp_date:
                            creation_date = xmp_date
                            date_source = 'xmp'
                            has_metadata = True

            except Exception as e:
                logger.warning(f"Error reading metadata from {file_path}: {e}")

            # If no image metadata, try filename/path
            if not has_metadata:
                fp_date, fp_source = extract_filename_or_path_date(file_path)
                if fp_date:
                    creation_date = fp_date
                    date_source = fp_source
                    has_metadata = True

        # Format output
        year = f"{creation_date:%Y}"
        month = f"{creation_date:%m}"
        day = f"{creation_date:%d}"

        is_reliable = check_date_reliability(year, month, day, has_metadata)

        logger.debug(f"Date for {file_path}: {year}-{month}-{day}, source: {date_source}, reliable: {is_reliable}")
        return (year, month, day, date_source, is_reliable)

    except Exception as e:
        logger.exception(f"Error getting creation date for {file_path}: {e}")
        # Return fallback date
        return (
            constants.INVALID_DATE_YEAR,
            constants.INVALID_DATE_MONTH,
            constants.INVALID_DATE_DAY,
            'fallback',
            False
        )
