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

**utils.py** - Shared utility functions
- `setup_logger()`: Configures logging with both console and file handlers
- `ensure_directory_exists()`: Creates directories if they don't exist
- `get_unique_filename()`: Generates unique filenames by appending counters (_1, _2, etc.)
- `validate_settings()`: Validates required settings are present
- `format_file_size()`: Converts bytes to human-readable format
- Used across all modules to eliminate code duplication

**DuplicateFileDetection.py** - Core duplicate detection and file processing
- `PhotoDatabase` class: Context manager for safe SQLite database connection handling
  - Automatically commits on success, rolls back on errors
  - Helper methods: `get_all_hashes()`, `insert_unique_photo()`, `initialize_database()`
  - Use with `with PhotoDatabase(path) as db:` pattern
- `get_file_list()`: Recursively walks source directories and returns list of media files
- `VerifyFileType()`: Uses PIL/Pillow to verify file extensions match actual file format, corrects mismatches
- `hash_file()`: Calculates SHA-256 hash of files for duplicate detection
- `find_duplicates()`: Compares files against SQLite database of known hashes, returns original vs. duplicate lists
- `get_creation_date()`: Extracts creation date from EXIF data (preferred) or OS file metadata
- `load_photo_hashes()`: Loads all existing file hashes from SQLite database

**Database**: SQLite database (configurable via `settings.json`, defaults to `PhotoDB.db`)
- Table `UniquePhotos`: Stores hash, file path, and creation date info for all unique photos
- Used to prevent duplicate files from being copied to the vault
- Managed via `PhotoDatabase` context manager for automatic connection handling and transaction management

### Data Flow

1. User configures source/destination directories in `settings.json`
2. `get_file_list()` scans source directories for files matching configured extensions
3. Each file is verified (`VerifyFileType()`) and hashed (`hash_file()`)
4. Hash is checked against database to determine if file is duplicate
5. Unique files are copied to destination in `YYYY/MM/DD` folder structure based on EXIF or OS creation date
6. Database is updated with new unique file hashes

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
  "move_files": false
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

### Hash-Based Deduplication
- Uses SHA-256 for file hashing (reads files in 4096-byte chunks)
- Database stores all unique file hashes
- Files are compared by hash, not filename or path
- TODO in codebase suggests future optimization: hash first 512 bytes as preliminary check

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

## Dependencies

- `PIL` (Pillow): Image processing and EXIF extraction
- `pillow_heif`: HEIC/HEIF format support for Apple photos
- `sqlite3`: Database for tracking unique file hashes
- `hashlib`: SHA-256 hashing for duplicate detection

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
