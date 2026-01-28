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

# Photo file extensions (for routing to photo archive)
PHOTO_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.heic', '.heif', '.tif', '.tiff', '.bmp', '.gif', '.webp']

# Video file extensions (for routing to video archive)
VIDEO_EXTENSIONS = ['.mov', '.mp4', '.avi', '.mkv', '.wmv', '.flv', '.mpg', '.mpeg', '.m4v', '.3gp']

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

# Maximum path length (Windows extended-length path limit)
MAX_PATH_LENGTH = 32767


# ============================================================================
# DATABASE CONSTANTS (Extended)
# ============================================================================

# Database connection timeout in seconds
DATABASE_TIMEOUT_SECONDS = 30

# Database busy timeout in milliseconds
DATABASE_BUSY_TIMEOUT_MS = 30000

# Default query result limit for large result sets
DEFAULT_QUERY_LIMIT = 5000

# Default migration batch size
MIGRATION_BATCH_SIZE = 1000


# ============================================================================
# THUMBNAIL CONSTANTS
# ============================================================================

# Default thumbnail sizes (in pixels)
THUMBNAIL_SIZE_SMALL = 128
THUMBNAIL_SIZE_MEDIUM = 256
THUMBNAIL_SIZE_LARGE = 512
THUMBNAIL_SIZE_XLARGE = 1024

# Default thumbnail size for grids
DEFAULT_THUMBNAIL_SIZE = 200

# Memory cache size (number of thumbnails)
THUMBNAIL_MEMORY_CACHE_SIZE = 500

# Disk cache size in GB
THUMBNAIL_DISK_CACHE_GB = 5

# Number of thumbnail worker threads
THUMBNAIL_WORKER_THREADS = 8

# Video thumbnail extraction settings
VIDEO_THUMBNAIL_TIMESTAMP_PERCENT = 0.10  # Extract frame at 10% into video
VIDEO_THUMBNAIL_MAX_TIMESTAMP = 5.0       # Max seconds into video for first frame
VIDEO_THUMBNAIL_QUALITY = 85              # JPEG quality for video thumbnails

# Video duration overlay settings
VIDEO_DURATION_FONT_SIZE_PERCENT = 0.067  # Duration font size as percent of thumbnail
VIDEO_DURATION_PADDING = 4                 # Padding around duration badge


# ============================================================================
# WORKER/THREADING CONSTANTS
# ============================================================================

# Default worker timeout in milliseconds
WORKER_TIMEOUT_MS = 30000

# Default worker shutdown timeout in seconds
WORKER_SHUTDOWN_TIMEOUT_SECONDS = 5

# Progress update interval in milliseconds
PROGRESS_UPDATE_INTERVAL_MS = 100


# ============================================================================
# YEAR RANGE CONSTANTS
# ============================================================================

# Minimum reasonable year for photo dates
MIN_REASONABLE_YEAR = 1990

# Maximum reasonable year for photo dates (future buffer)
MAX_REASONABLE_YEAR = 2100

# Year used for files with missing/invalid dates
FALLBACK_YEAR = 1000


# ============================================================================
# METADATA QUALITY SCORES
# ============================================================================

# Score values for different date sources (higher = better)
# Note: These are also defined in DuplicateFileDetection.py for now
# TODO: Consolidate once DuplicateFileDetection is refactored
METADATA_SCORE_EXIF = 80
METADATA_SCORE_EXIF_DIGITIZED = 70
METADATA_SCORE_EXIF_GPS = 65
METADATA_SCORE_VIDEO_METADATA = 60
METADATA_SCORE_VIDEO_QUICKTIME = 55
METADATA_SCORE_EXIF_DATETIME = 50
METADATA_SCORE_EXIF_PREVIEW = 45
METADATA_SCORE_IPTC = 40
METADATA_SCORE_XMP = 35
METADATA_SCORE_FILENAME = 30       # Date from filename (e.g., IMG_20230415_123456.jpg)
METADATA_SCORE_PATH_YMD = 28       # Full date from path (year/month/day)
METADATA_SCORE_PATH_YM = 25        # Year/month from path
METADATA_SCORE_PATH_Y = 22         # Year only from path
METADATA_SCORE_OS_METADATA = 20
METADATA_SCORE_FALLBACK = 0

# Reliability bonus added to score
METADATA_RELIABILITY_BONUS = 20


# ============================================================================
# LOGGING CONSTANTS
# ============================================================================

# Maximum log file size in bytes (5MB)
LOG_MAX_SIZE_BYTES = 5 * 1024 * 1024

# Number of log backup files to keep
LOG_BACKUP_COUNT = 3


# ============================================================================
# UI LAYOUT CONSTANTS
# ============================================================================

# Default spacing between UI elements
UI_SPACING_SMALL = 5
UI_SPACING_MEDIUM = 10
UI_SPACING_LARGE = 20

# Default margins
UI_MARGIN_SMALL = 5
UI_MARGIN_MEDIUM = 10
UI_MARGIN_LARGE = 20

# Default button dimensions
BUTTON_MIN_WIDTH = 100
BUTTON_MIN_HEIGHT = 30


# ============================================================================
# AUDIT CONSTANTS
# ============================================================================

# Maximum audit retry attempts
AUDIT_MAX_RETRY_ATTEMPTS = 5

# Audit retention period in days
AUDIT_RETENTION_DAYS = 30


# ============================================================================
# PREFETCH CONSTANTS
# ============================================================================

# Number of items to prefetch before visible area
PREFETCH_BEFORE_COUNT = 50

# Number of items to prefetch after visible area
PREFETCH_AFTER_COUNT = 100
