"""
Application-wide constants for PyPhotoOrganizer.

This module defines all magic numbers and constants used throughout the application
to improve code readability and maintainability.
"""

# ============================================================================
# FILE I/O CONSTANTS
# ============================================================================

# Chunk size for reading files during hashing (4KB - optimal disk read size)
FILE_READ_CHUNK_SIZE = 4096

# Size units for human-readable formatting
BYTES_PER_KB = 1024
BYTES_PER_MB = 1024 * 1024
BYTES_PER_GB = 1024 * 1024 * 1024


# ============================================================================
# HASHING CONSTANTS
# ============================================================================

# Number of bytes to read for partial file hashing (16KB)
# This provides good balance between speed and collision avoidance
PARTIAL_HASH_BYTES = 16384

# Minimum file size to use partial hashing (1MB)
# Files smaller than this are hashed fully in one pass
PARTIAL_HASH_MIN_FILE_SIZE = 1048576


# ============================================================================
# DATABASE CONSTANTS
# ============================================================================

# Default batch size for database commits
# Files are committed to database every N files to preserve progress
DEFAULT_BATCH_SIZE = 100

# Default database filename
DEFAULT_DATABASE_NAME = 'PhotoDB.db'


# ============================================================================
# PHOTO FILTERING CONSTANTS
# ============================================================================

# Minimum file size for valid photos (50KB)
# Real photos are typically larger than this; smaller files are likely icons/thumbnails
MIN_PHOTO_FILE_SIZE = 51200

# Minimum photo dimensions (width x height in pixels)
MIN_PHOTO_WIDTH = 800
MIN_PHOTO_HEIGHT = 600

# Maximum photo dimensions (prevents huge graphics from being processed)
MAX_PHOTO_WIDTH = 50000
MAX_PHOTO_HEIGHT = 50000

# Minimum size for square images (400x400)
# Square images smaller than this are likely icons/logos
MIN_SQUARE_SIZE = 400


# ============================================================================
# UI/DISPLAY CONSTANTS
# ============================================================================

# Maximum filename length to display in progress bars
MAX_FILENAME_DISPLAY_LENGTH = 40

# Alternate filename display length for directory scanning
MAX_FILENAME_DISPLAY_LENGTH_SCAN = 50


# ============================================================================
# FILE VALIDATION CONSTANTS
# ============================================================================

# Valid image file extensions for file type verification
VALID_IMAGE_EXTENSIONS = ['.jpg', '.png', '.gif', '.tif', '.bmp', '.webp', '.ico', '.ppm', '.eps', '.pdf']

# Default file extensions to process
DEFAULT_FILE_ENDINGS = ['.jpg', '.jpeg', '.png', '.heic', '.tif', '.mov', '.mp4']

# Default excluded filename patterns (for photo filtering)
# Files with these patterns in their names are likely icons/thumbnails/web graphics
DEFAULT_EXCLUDED_PATTERNS = ['favicon', 'icon', 'logo', 'thumb', 'button', 'badge', 'sprite']

# HEIC/HEIF file extensions (Apple photos)
HEIC_EXTENSIONS = ('.heic', '.heif', '.HEIC', '.HEIF')


# ============================================================================
# ERROR HANDLING CONSTANTS
# ============================================================================

# Default year/month/day for files with invalid or missing dates
INVALID_DATE_YEAR = "1000"
INVALID_DATE_MONTH = "01"
INVALID_DATE_DAY = "01"


# ============================================================================
# PATH CONSTANTS
# ============================================================================

# Dangerous path patterns that could indicate directory traversal attacks
DANGEROUS_PATH_PATTERNS = ['..']
