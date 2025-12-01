# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PhotoOrganizer is a Python-based photo and video duplicate detection and organization system. It scans multiple source directories for media files, detects duplicates using SHA-256 hashing, and organizes unique files into a structured vault organized by creation date (year/month/day).

**Primary Goal**: Help users consolidate photos from multiple devices and locations (phones, tablets, PCs, NAS) into a single, deduplicated archive while preserving file metadata.

**Flow Diagram**: https://lucid.app/lucidchart/d52adf95-4275-4107-ad41-20c4cfd5c72c/edit?invitationId=inv_70bff327-b21c-4508-9ae6-03f07b9bdefe&page=4wTk8nA8b3At#

## Running the Application

```bash
# Run the main photo organizer
python main.py

# Run duplicate detection module standalone
python DuplicateFileDetection.py

# Run test routines
python TestRoutines.py
```

Configuration is loaded from `settings.json` in the project root directory.

## Architecture

### Core Components

**main.py** - Main orchestration module
- Loads settings from `settings.json`
- Calls `DuplicateFileDetection.get_file_list()` to collect files from source directories
- Calls `DuplicateFileDetection.find_duplicates()` to identify unique vs. duplicate files
- For unique files, calls `organize_files()` to copy/move them to destination with date-based folder structure
- Handles HEIC to JPEG conversion for Apple photos

**config.py** - Configuration management system
- `Config` class: Centralized configuration loading and validation
  - Loads settings from `settings.json` with automatic defaults
  - Validates required settings and data types
  - Provides clean property access (e.g., `config.batch_size`)
  - Supports both property and dictionary-style access
  - Handles type conversion and validation automatically
- Eliminates repetitive if/else blocks for settings

**utils.py** - Shared utility functions
- `setup_logger()`: Configures logging with both console and file handlers
- `ensure_directory_exists()`: Creates directories if they don't exist
- `get_unique_filename()`: Generates unique filenames by appending counters (_1, _2, etc.)
- `validate_settings()`: Validates required settings are present
- `format_file_size()`: Converts bytes to human-readable format
- Used across all modules to eliminate code duplication

**photo_filter.py** - Photo validation and filtering
- `PhotoFilter` class: Identifies real photographs vs icons/thumbnails/web graphics
  - Multi-criteria validation (size, dimensions, aspect ratio, filename patterns, EXIF)
  - Tracks detailed statistics by filter reason
  - Integrates with main processing pipeline before hashing
  - See "Photo Filtering" section below for details

**DuplicateFileDetection.py** - Core duplicate detection and file processing
- `PhotoDatabase` class: Context manager for safe SQLite database connection handling
  - Automatically commits on success, rolls back on errors
  - Helper methods: `get_all_hashes()`, `insert_unique_photo()`, `initialize_database()`
  - Use with `with PhotoDatabase(path) as db:` pattern
- `get_file_list()`: Recursively walks source directories and returns list of media files
- `VerifyFileType()`: Uses PIL/Pillow to verify file extensions match actual file format, corrects mismatches
- `hash_file()`: Calculates SHA-256 hash of files for duplicate detection
- `hash_file_partial()`: Calculates SHA-256 hash of first N bytes for two-stage hashing optimization
- `find_duplicates()`: Compares files against SQLite database of known hashes, returns original vs. duplicate lists
  - Integrates photo filtering (if enabled) before hashing
  - Uses two-stage partial hashing for large files
- `get_creation_date()`: Extracts creation date from EXIF data (preferred) or OS file metadata
- `load_photo_hashes()`: Loads all existing file hashes from SQLite database

**Database**: SQLite database (configurable via `settings.json`, defaults to `PhotoDB.db`)
- Table `UniquePhotos`: Stores hash, file path, and creation date info for all unique photos
- Used to prevent duplicate files from being copied to the vault
- Managed via `PhotoDatabase` context manager for automatic connection handling and transaction management

### Data Flow

1. User configures source/destination directories in `settings.json`
2. `get_file_list()` scans source directories for files matching configured extensions
3. Each file is verified (`VerifyFileType()`) to ensure extension matches actual format
4. **Photo filtering** (if enabled): File is checked to determine if it's a real photograph
   - Filtered files (icons, thumbnails, web graphics) are tracked separately and skipped
5. Each remaining file is hashed using two-stage hashing:
   - Small files (< 1MB): Direct full hash
   - Large files (≥ 1MB): Partial hash first, full hash only if potential duplicate
6. Hash is checked against database to determine if file is duplicate
7. Unique files are copied to destination in `YYYY/MM/DD` folder structure based on EXIF or OS creation date
8. Database is updated with new unique file hashes (including partial hash for optimization)

### Settings Configuration

The `settings.json` file controls application behavior:

```json
{
  "source_directory": ["D:\\Photos\\Source"],
  "destination_directory": "I:\\SortedPhotos",
  "database_path": "PhotoDB.db",
  "batch_size": 100,
  "include_subdirectories": true,
  "file_endings": [".jpg", ".png", ".heic", ".jpeg", ".tif", ".mov", ".mp4"],
  "group_by_year": true,
  "group_by_day": true,
  "copy_files": true,
  "move_files": false,
  "partial_hash_enabled": true,
  "partial_hash_bytes": 16384,
  "partial_hash_min_file_size": 1048576,
  "photo_filter_enabled": true,
  "min_file_size": 51200,
  "min_width": 800,
  "min_height": 600
}
```

**Important Settings**:
- `source_directory`: Can be a list of multiple directories to process multiple sources in one run
- `database_path`: Path to SQLite database (default: "PhotoDB.db")
- `batch_size`: Number of files to process before committing to database (default: 100)
  - Critical for long-running processes to preserve progress
  - Set higher (500-1000) for better performance, lower (50-100) for more frequent checkpoints

## Key Implementation Details

### Long-Running Process Recovery

**Critical for processing thousands of files over days:**

1. **Periodic Commits**: Database is committed every `batch_size` files (default: 100)
   - If processing crashes on file #5,432, files #1-5,400 (last checkpoint) are safely saved
   - Progress is preserved even if application terminates unexpectedly

2. **Automatic Resume Capability**:
   - Before processing a file, system checks if hash already exists in database
   - If found, file is skipped (marked as duplicate)
   - Simply re-run the application with same settings to continue where it left off
   - No manual tracking needed

3. **Error Isolation**:
   - Individual file errors don't stop processing
   - Failed files are logged and skipped
   - Processing continues with remaining files

**Example**: Processing 10,000 files with batch_size=100
- Commits after files: 100, 200, 300, ... 9,900, 10,000
- If crash occurs at file 5,432, database contains files 1-5,400
- Re-running will skip files 1-5,400 and resume from 5,401

### Date Extraction Priority
1. First attempts to read EXIF `DateTimeOriginal` from image metadata (most accurate)
2. Falls back to Windows `getctime()` or `getmtime()` if EXIF unavailable
3. Returns dates as formatted strings: `(year, month, day)` where month/day are zero-padded

### Hash-Based Deduplication with Two-Stage Optimization

**Intelligent hashing strategy for maximum performance:**

1. **Small Files (< 1MB)**: Direct full hash
   - Photos typically 100KB-5MB
   - Full hash is already fast
   - No optimization needed

2. **Large Files (≥ 1MB)**: Two-stage partial hashing
   - **Stage 1**: Hash first 16KB only (~0.1ms)
   - Check if partial hash exists in database
   - **If NO match**: File is unique, proceed to full hash
   - **If YES match**: Potential duplicate, verify with full hash (Stage 2)

**Performance Impact:**
- Videos (1-5GB): ~100x faster for unique files
- Only calculates full hash when necessary
- Indexed database lookups on partial hash
- Handles partial hash collisions gracefully

**Configuration:**
```json
{
  "partial_hash_enabled": true,
  "partial_hash_bytes": 16384,  // 16KB
  "partial_hash_min_file_size": 1048576  // 1MB threshold
}
```

### Photo Filtering (Icon/Thumbnail Exclusion)

**Purpose**: Automatically filter out non-photograph files (icons, web graphics, thumbnails) to prevent them from corrupting the photo archive.

**photo_filter.py** - Photo validation and filtering module
- `PhotoFilter` class: Multi-criteria validation to identify real photographs
  - File size filtering (default: minimum 50KB)
  - Dimension filtering (default: 800x600 to 50000x50000)
  - Small square detection (excludes perfect squares < 400x400, likely icons)
  - Filename pattern exclusion (favicon, icon, logo, thumb, button, etc.)
  - EXIF data requirement (optional - ensures photos have camera metadata)
  - Tracks detailed statistics by filter reason

**Integration with Processing Pipeline**:
1. Photo filtering happens BEFORE hashing (saves processing time)
2. Filtered files are tracked separately in results
3. Statistics show breakdown by filter reason
4. Files can optionally be moved to a separate filtered folder

**Configuration:**
```json
{
  "photo_filter_enabled": true,
  "min_file_size": 51200,  // 50KB - real photos are larger
  "min_width": 800,
  "min_height": 600,
  "max_width": 50000,
  "max_height": 50000,
  "exclude_square_smaller_than": 400,  // Filter small square icons
  "require_exif": false,  // If true, only accept images with EXIF data
  "excluded_filename_patterns": ["favicon", "icon", "logo", "thumb", "button", "badge", "sprite"],
  "move_filtered_files": false,  // If true, move to separate folder
  "filtered_files_folder": "filtered_non_photos"
}
```

**Results Tracking**:
- `filtered_files`: List of files filtered out with reasons
- `filter_statistics`: Detailed breakdown of filtering (by size, dimensions, pattern, etc.)

**Disable filtering**: Set `"photo_filter_enabled": false` in settings.json

### File Type Verification
- Uses PIL/Pillow to verify file format matches extension
- Automatically corrects mismatched extensions (e.g., `.png` file with `.jpg` extension)
- Handles files without extensions by testing against known image formats
- Uses `safe_rename_or_copy()` to handle locked files

### HEIC Conversion
- Uses `pillow_heif` library to convert Apple HEIC/HEIF images to JPEG
- Conversion happens after file is copied to destination
- Preserves EXIF data during conversion

## Logging

All modules use Python's logging framework with detailed formatting:
- Console output: DEBUG level
- File logging:
  - `main_app_error.log` (main.py)
  - `DuplicateFileDetection_app_error.log` (DuplicateFileDetection.py)
  - `app_error.log` (FunctionParameters.py)

Format: `timestamp - module - level - function - line --- message`

## Progress Bars

The application uses `tqdm` to display real-time progress bars for long-running operations:

1. **Directory Scanning**: Shows progress while scanning source directories for files
   - Displays current directory being scanned
   - Shows count of directories processed

2. **File Processing** (Duplicate Detection): Shows progress during hash calculation and duplicate detection
   - Displays current file being processed (truncated to 40 chars)
   - Shows files per second processing rate
   - Estimated time remaining
   - Format: `Processing files: |████████| 150/500 [00:45<01:30, 3.33file/s]`

3. **File Organization** (Copy/Move): Shows progress while copying or moving unique files to destination
   - Displays current file being copied/moved
   - Shows completion percentage and time estimates
   - Updates in real-time as files are processed

Progress bars work alongside logging without interference. All progress information is displayed on the console while detailed logs are written to log files.

## Dependencies

- `PIL` (Pillow): Image processing and EXIF extraction
- `pillow_heif`: HEIC/HEIF format support for Apple photos
- `sqlite3`: Database for tracking unique file hashes
- `hashlib`: SHA-256 hashing for duplicate detection
- `tqdm`: Progress bars for long-running operations

## Known Issues & TODOs

From main.py comments:
- Files with apostrophes in path may fail (TODO #11)
- Need to add hash verification after vault copy (TODO #1.4)
- Consider parent-child relationship tracking for derived images (TODO #1.3)
- Video file processing needs improvement (TODO #8)
- Database schema should be extended to track duplicate files separately

## Path Handling

**Note**: The codebase uses Windows-style paths with drive letters (e.g., `D:\Dropbox\...`). When modifying path logic, ensure Windows path compatibility. Database path is now configurable via `settings.json`.

## Testing

`TestRoutines.py` contains test code for:
- Date formatting and folder structure logic
- Dictionary parameter handling patterns
- Logging configuration validation
