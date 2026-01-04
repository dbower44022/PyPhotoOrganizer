# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PhotoOrganizer is a Python-based photo and video duplicate detection and organization system. It scans multiple source directories for media files, detects duplicates using SHA-256 hashing, and organizes unique files into a structured vault organized by creation date (year/month/day).

**Primary Goal**: Help users consolidate photos from multiple devices and locations (phones, tablets, PCs, NAS) into a single, deduplicated archive while preserving file metadata.

**Flow Diagram**: https://lucid.app/lucidchart/d52adf95-4275-4107-ad41-20c4cfd5c72c/edit?invitationId=inv_70bff327-b21c-4508-9ae6-03f07b9bdefe&page=4wTk8nA8b3At#

## Running the Application

```bash
# Run the GUI application (recommended)
python main_gui.py

# Run the CLI photo organizer
python main.py

# Run duplicate detection module standalone
python DuplicateFileDetection.py

# Run test routines
python TestRoutines.py
```

**GUI Mode** (`main_gui.py`): Full-featured interface with database management, source directory configuration, real-time progress tracking, and date correction tools. Database-first approach where each database is bound to a specific archive location.

**CLI Mode** (`main.py`): Command-line interface using configuration from `settings.json` in the project root directory.

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

**database_metadata.py** - Database metadata and configuration management
- `DatabaseMetadata` class: Manages database metadata, archive binding, and source directories
  - Database-first architecture: Each database is bound to a specific archive location
  - Stores database name, description, creation date, archive location
  - Manages video archive location (for separate video storage)
  - **Source Directory Management** (NEW in v2.1):
    - `add_source_directory(path, enabled)`: Add source folder with auto-save to database
    - `remove_source_directory(path)`: Remove source and reorder remaining
    - `get_all_source_directories()`: Get all sources with metadata (path, enabled, last_scanned)
    - `update_source_last_scanned(path, timestamp)`: Update timestamp after processing
    - `update_source_enabled(path, enabled)`: Toggle enabled status
    - `clear_all_source_directories()`: Remove all sources
  - **Unreliable Dates Management** (NEW in v2.2):
    - `insert_unreliable_date()`: Record files with questionable date information
    - `get_unreliable_dates(filter_reason)`: Query files with unreliable dates
    - `update_corrected_date()`: Update when user corrects a file's date
    - `get_files_needing_reorganization()`: Get files marked for reorganization
    - `mark_reorganized()`: Clear reorganization flag after completion
    - `update_photo_path()`: Update file paths after reorganization
    - `get_user_specified_paths()` / `set_user_specified_paths()`: Manage user-specified unreliable paths
  - `find_databases(path)`: Search for all PyPhotoOrganizer databases in directory
  - `create_database()`: Create new database with all required tables
  - `ensure_all_tables()`: Upgrade old databases by adding missing tables/columns

**exif_writer.py** - EXIF metadata modification (NEW in v2.2)
- `write_exif_date(file_path, year, month, day)`: Writes corrected date to EXIF data
  - Creates EXIF structure if image has none
  - Writes to DateTimeOriginal, DateTime, and DateTimeDigitized fields
  - Preserves image quality during save
  - Supports JPEG and TIFF formats
- `read_exif_date(file_path)`: Reads DateTimeOriginal from EXIF
- `verify_exif_write(file_path, year, month, day)`: Verifies EXIF write succeeded

**GUI Modules** (ui/ directory):
- `main_window.py`: Main application window with tab-based interface
- `setup_tab.py`: Source directory selection and processing controls
- `progress_tab.py`: Real-time processing progress display
- `results_tab.py`: Processing results summary
- `filtered_files_tab.py`: Files filtered by photo filter
- `logs_tab.py`: Application log viewer
- `settings_tab.py`: Organization template and settings configuration
- `database_tab.py`: Database selection, creation, and metadata management
- **`date_corrections_tab.py`** (NEW in v2.2): Date correction interface
  - Grid view with sortable columns and filtering
  - Image preview panel
  - Single and batch date correction
  - Reorganization management
- **`date_correction_dialog.py`** (NEW in v2.2): Date input dialog
  - Single file mode with date picker
  - Batch mode with same/sequential date options
  - EXIF writing and reorganization flags
- **`manage_unreliable_paths_dialog.py`** (NEW in v2.2): User-specified unreliable paths management
- **`reorganize_worker.py`** (NEW in v2.2): Safe file reorganization logic
  - Copy-verify-delete pattern
  - Empty directory cleanup
  - Database path updates

**Database**: SQLite database (configurable via `settings.json`, defaults to `PhotoDB.db`)
- **Table `DatabaseMetadata`**: Stores database metadata and configuration
  - `database_name`: User-friendly name for the database
  - `archive_location`: Path to photo archive (permanently bound)
  - `video_archive_location`: Optional separate location for videos
  - `created_date`, `last_used_date`: Timestamps
  - `total_photos`: Cached count from UniquePhotos table
  - `schema_version`: For future database upgrades
- **Table `UniquePhotos`**: Stores hash, file path, and creation date info for all unique photos
  - Used to prevent duplicate files from being copied to the vault
  - Managed via `PhotoDatabase` context manager
- **Table `SourceDirectories`** (NEW in v2.1): Stores persistent source folder configurations
  - `path`: Full directory path (unique)
  - `order_index`: Display order in UI
  - `added_date`: When source was added
  - `last_scanned`: Timestamp of last successful scan (updated after processing)
  - `enabled`: Whether source is enabled for scanning (checkbox state)
  - Sources persist across sessions - automatically loaded when database is selected
  - Allows selective processing with checkboxes (only enabled sources are scanned)
- **Table `UnreliableDates`** (NEW in v2.2): Tracks files with questionable date information
  - `file_hash`: SHA-256 hash linking to UniquePhotos table
  - `source_path`, `archive_path`: Original and archive file locations
  - `original_date`: Date extracted during processing
  - `date_source`: Where date came from ('exif', 'os_metadata', 'fallback')
  - `flag_reason`: Why flagged ('no_exif', 'year_1000', 'suspicious', 'user_specified')
  - `corrected_date`: User-corrected date (YYYY-MM-DD format)
  - `correction_timestamp`: When correction was made
  - `needs_reorganization`: Flag indicating file needs to be moved to correct date folder
  - Automatically populated during processing when unreliable dates detected

### Data Flow

1. **GUI Mode**: Source directories loaded from database `SourceDirectories` table (persistent across sessions)
   - User selects which sources to scan using checkboxes
   - Only enabled sources are processed
   **CLI Mode**: Source directories configured in `settings.json`
2. `get_file_list()` scans source directories for files matching configured extensions
3. Each file is verified (`VerifyFileType()`) to ensure extension matches actual format
4. **Photo filtering** (if enabled): File is checked to determine if it's a real photograph
   - Filtered files (icons, thumbnails, web graphics) are tracked separately and skipped
5. Each remaining file is hashed using two-stage hashing:
   - Small files (< 1MB): Direct full hash
   - Large files (≥ 1MB): Partial hash first, full hash only if potential duplicate
6. Hash is checked against database to determine if file is duplicate
7. **Date extraction with reliability tracking** (NEW in v2.2):
   - `get_creation_date()` extracts date from EXIF or OS metadata
   - Returns: (year, month, day, date_source, is_reliable)
   - Unreliable dates automatically flagged and recorded in `UnreliableDates` table
   - Detection criteria: no EXIF, year 1000 fallback, suspicious dates, user-specified paths
8. Unique files are copied to destination in `YYYY/MM/DD` folder structure based on extracted creation date
9. Database is updated with new unique file hashes (including partial hash for optimization)

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

### Date Correction System (NEW in v2.2)

**Purpose**: Identify files with unreliable date information and provide tools to correct them, ensuring files are organized in the correct date-based folders.

**exif_writer.py** - EXIF date modification module
- `write_exif_date(file_path, year, month, day)`: Writes corrected date to EXIF DateTimeOriginal field
  - Creates EXIF data if file has none
  - Writes to multiple EXIF fields (DateTimeOriginal, DateTime, DateTimeDigitized)
  - Preserves image quality (quality=95 for JPEG)
  - Returns True on success, False on failure
- `read_exif_date(file_path)`: Reads EXIF DateTimeOriginal and returns (year, month, day) tuple
- `verify_exif_write(file_path, expected_year, expected_month, expected_day)`: Verifies EXIF write succeeded

**Automatic Detection During Processing**:
During file processing, the system automatically flags files with unreliable dates based on:
1. **No EXIF Data**: Image has no EXIF metadata (flag_reason: 'no_exif')
2. **Year 1000 Fallback**: All date extraction methods failed (flag_reason: 'year_1000')
3. **Suspicious Dates**:
   - Year < 1990 (before consumer digital cameras)
   - Year > current year + 1 (future date)
   - Date is exactly 1970-01-01 (Unix epoch default)
   - Flag reason: 'suspicious'
4. **User-Specified Paths**: File's source path matches user-configured unreliable paths (flag_reason: 'user_specified')
   - Example: `/old/scanned_photos/` or `D:\Legacy\Phone Backup\`

Flagged files are automatically inserted into the `UnreliableDates` table during processing.

**Date Corrections Tab (GUI)**:
- **Grid View**: Sortable table displaying all flagged files
  - Columns: Checkbox, Filename, Source Location, Archive Location, Detected Date, EXIF Date, File Date, Flag Reason, Status
  - Filter by flag reason (checkboxes for no_exif, year_1000, suspicious, user_specified)
  - Multi-select for batch operations
- **Preview Panel**: Shows image preview and detailed metadata for selected file
- **Single File Correction**: Opens dialog to correct individual file date
- **Batch Correction**: Two modes:
  - Same date for all selected files
  - Sequential dates (auto-increment by 1 day per file)
- **EXIF Writing**: Optionally writes corrected date back to source file EXIF data
- **Reorganization**: Two-phase process
  - Phase 1: Mark files for reorganization (immediate)
  - Phase 2: Batch reorganize all marked files (user-triggered)

**Reorganization Process**:
1. User corrects date(s) - files marked with `needs_reorganization=1`
2. User clicks "Reorganize All Marked" button
3. System processes each file:
   - Calculates new archive path based on corrected date and organization template
   - Copies file from old location to new location
   - Verifies copy succeeded (file exists, size matches)
   - Deletes old file
   - Cleans up empty directories
   - Updates `UniquePhotos` table with new path
   - Sets `needs_reorganization=0`

**Manage Unreliable Paths Dialog**:
- Add/remove folder paths that should be auto-flagged
- Stored in `DatabaseMetadata.user_specified_unreliable_paths` as JSON array
- Applied to future processing runs

**Safety Features**:
- Copy-verify-delete pattern prevents data loss
- Progress dialogs for all long-running operations
- Cancellation support
- Comprehensive error logging with visual indicators
- Files with missing EXIF can still be reorganized (without EXIF write)
- Audit trail maintains original archive locations for verification

**Enhanced Logging System (v2.2.1)**:

The date correction system features comprehensive logging with visual indicators for easy log navigation:

**Visual Indicators:**
- `✓` - Successful operations
- `✗` - Failed operations
- `⚠` - Warnings (e.g., file collisions)
- `ℹ` - Informational messages

**Section Markers:**
- `========...` (80 chars) - Process start/end boundaries
- `--------...` (60 chars) - Individual file processing boundaries

**Log Levels:**
- Process start/end: `INFO` level with section markers
- Step-by-step operations: `INFO` level with visual indicators
- Errors: `ERROR` level with full stack traces (`exc_info=True`)
- Warnings: `WARNING` level for non-fatal issues
- Critical failures: `CRITICAL` level for configuration/system errors

**Date Correction Dialog Logging:**
- Per-file EXIF write tracking (source + archive)
- Separate error lists: `exif_failures`, `db_failures`
- Detailed summary reports with breakdown by error type
- Success/failure counts for each operation

**Reorganization Worker Logging:**
- Per-file detailed logging:
  - File hash, original date, corrected date
  - Old and new archive paths
  - Directory creation status
  - File collision handling
  - Copy size verification
  - Database update confirmation
- Empty directory cleanup tracking
- Final summary with success rate percentage

**Example Log Output:**
```
2026-01-04 10:23:15 INFO ================================================================
2026-01-04 10:23:15 INFO STARTING DATE CORRECTION PROCESS
2026-01-04 10:23:15 INFO Files to process: 15
2026-01-04 10:23:15 INFO ----------------------------------------------------------------
2026-01-04 10:23:15 INFO Processing file 1/15: vacation_001.jpg
2026-01-04 10:23:15 INFO   → Source file: /source/vacation_001.jpg
2026-01-04 10:23:15 INFO   ✓ EXIF written to source file successfully
2026-01-04 10:23:15 INFO   → Archive file: /archive/2024/01/01/vacation_001.jpg
2026-01-04 10:23:15 INFO   ✓ EXIF written to archive file successfully
2026-01-04 10:23:15 INFO   ✓ Database updated successfully
2026-01-04 10:23:15 INFO ✓✓✓ FILE CORRECTION COMPLETED SUCCESSFULLY ✓✓✓
```

**Audit Trail System (v2.2.1)**:

The system maintains a complete audit trail of all file reorganizations:

**Database Column: `original_archive_path`**
- Stores the file's location BEFORE reorganization
- NULL for files never reorganized
- Preserved after reorganization for verification
- Displayed in Date Corrections tab details panel

**Status Tracking:**
Files progress through three states:
1. **Pending**: No correction applied yet
   - `corrected_date` is NULL
   - Status color: Gray
   - Default filter: SHOW
2. **Corrected**: Date corrected, waiting for reorganization
   - `corrected_date` set, `needs_reorganization=1`
   - Status color: Dark Green
   - Status text: "Corrected: YYYY-MM-DD"
   - Default filter: SHOW
3. **Reorganized**: File moved to correct date folder
   - `corrected_date` set, `needs_reorganization=0`
   - `original_archive_path` populated
   - Status color: Blue
   - Status text: "Reorganized: YYYY-MM-DD"
   - Default filter: HIDE (reduces clutter, available for auditing)

**Status Filters (Checkboxes):**
- "Pending" - Show files awaiting correction
- "Corrected" - Show files corrected but not yet reorganized
- "Reorganized" - Show files already reorganized (for auditing)

**Audit Workflow:**
1. User corrects date → Status changes to "Corrected" (Green)
2. User clicks "Reorganize All Marked"
3. System saves current `archive_path` to `original_archive_path`
4. File moved to new location based on corrected date
5. Status changes to "Reorganized" (Blue)
6. Details panel shows both paths:
   ```
   Archive: /archive/1995/07/15/photo.jpg
   Original: /archive/2024/01/01/photo.jpg
   ```
7. User can verify file was moved from correct original location

**EXIF Dual-Write Pattern (v2.2.1)**:

**Critical Implementation Detail:**
EXIF data must be written to BOTH source and archive files to ensure data persistence during reorganization.

**Why Both Files?**
- **Source file**: User's original file, may be re-imported in the future
- **Archive file**: This is what gets copied during reorganization
- If EXIF only written to source, reorganized file will have OLD date in EXIF
- Result: File in correct folder (1995/07/15/) but EXIF shows wrong date (2024/01/01)

**Implementation (date_correction_dialog.py):**
```python
# Write to source file if it exists
if os.path.exists(record['source_path']):
    write_exif_date(record['source_path'], year_str, month_str, day_str)
    logger.info("✓ EXIF written to source file successfully")

# CRITICAL: Also write to archive file (this is what gets reorganized!)
if record.get('archive_path') and os.path.exists(record['archive_path']):
    write_exif_date(record['archive_path'], year_str, month_str, day_str)
    logger.info("✓ EXIF written to archive file successfully")
```

**Error Tracking:**
- Separate failure lists for source and archive EXIF writes
- Detailed error messages show which file failed
- Summary reports show success counts for both targets

**Zoom Functionality in Preview Panel (v2.2.1)**:

The Date Corrections tab preview panel supports rubber band zoom for detailed image inspection:

**Features:**
- **Rubber Band Selection**: Click and drag to select zoom region
- **Zoom Application**: Release mouse to zoom into selected area
- **Minimum Size**: Rectangle must be > 10 pixels to prevent accidental zooms
- **Reset Zoom**: Double-click anywhere to reset to fit-in-view mode
- **Zoom Persistence**: Custom zoom maintained during window resize

**Implementation Details (ZoomableGraphicsView class):**
- `is_custom_zoom` flag tracks zoom state
- Prevents `resizeEvent()` from resetting user's custom zoom
- `fitInView()` only called on double-click or new image load
- Rubber band drawn with QRubberBand widget
- Zoom applied to QRectF calculated from rubber band geometry

**Usage:**
1. Select file in grid → Image appears in preview panel
2. Click and drag to select area of interest
3. Release mouse → Preview zooms to selected area
4. Double-click → Reset to full image view
5. Window resize → Zoom level maintained (won't auto-reset)

**Database Path Synchronization (v2.2.1)**:

The system includes intelligent synchronization to fix archive paths that may have been incorrectly stored:

**Method: `sync_archive_paths_from_unique_photos()`**
- Updates NULL `archive_path` values from `UniquePhotos` table
- Detects source paths incorrectly stored as archive paths
- Reconstructs correct archive paths using organization template + date
- Verifies files exist before updating
- Updates both `UnreliableDates` and `UniquePhotos` tables
- Returns count of records synchronized

**Detection Logic:**
```python
# Check if archive_path doesn't start with archive base location
if not current_archive_path.startswith(archive_base):
    # This is likely a source path, reconstruct correct archive path
    file_date = datetime(int(year), int(month), int(day))
    folder_path = OrganizationTemplate.parse(template_str, file_date)
    correct_archive_path = os.path.join(archive_base, folder_path, filename)
```

**Auto-Upgrade Support:**
Old databases automatically upgraded with `original_archive_path` column during first access.

**Dependencies**:
- `piexif>=1.1.3`: EXIF metadata writing for JPEG and TIFF formats

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
- `piexif`: EXIF metadata writing for date correction feature (NEW in v2.2)
- `sqlite3`: Database for tracking unique file hashes
- `hashlib`: SHA-256 hashing for duplicate detection
- `tqdm`: Progress bars for long-running operations
- `PySide6`: Qt-based GUI framework (GUI mode only)

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

## Date Correction Workflow (NEW in v2.2)

**Typical Usage Scenario:**

1. **Initial Processing**:
   - User processes photos normally through Setup tab
   - System automatically flags files with unreliable dates during processing
   - Flagged files are recorded in `UnreliableDates` table with flag reasons

2. **Review Flagged Files**:
   - User opens "Date Corrections" tab
   - Grid displays all flagged files with details (source, archive location, detected date, flag reason)
   - User can filter by flag reason: no_exif, year_1000, suspicious, user_specified
   - Preview panel shows selected image and metadata

3. **Correct Single File**:
   - User clicks on file in grid
   - Preview panel shows image
   - User clicks "Correct Date..." button
   - Dialog opens showing current detected date
   - User enters correct date using year/month/day spinboxes
   - User chooses options:
     - Write EXIF to source file (recommended, checked by default)
     - Mark for reorganization (checked by default)
   - User clicks "Apply"
   - System writes EXIF to source file (if enabled)
   - Database updated with corrected date
   - File marked for reorganization

4. **Batch Correction**:
   - User selects multiple files (e.g., all from same event or scanned album)
   - User clicks "Batch Correct" button
   - Dialog offers two correction modes:
     - **Same date**: Assign same date to all selected files
     - **Sequential dates**: Assign dates incrementing by 1 day per file (useful for vacation photos or chronological albums)
   - User enters starting date
   - User chooses EXIF writing and reorganization options
   - User clicks "Apply"
   - System processes all files with progress dialog
   - All files marked for reorganization

5. **Manage User-Specified Unreliable Paths**:
   - User clicks "Manage Unreliable Paths..." button
   - Dialog displays list of user-specified paths
   - User adds path like `/old/scanned_photos/` or `D:\Legacy\Phone Backup\`
   - Paths saved to database
   - Future processing automatically flags files from these paths

6. **Reorganization**:
   - User clicks "Reorganize All Marked" button
   - System shows count of files to be reorganized
   - User confirms operation
   - Progress dialog displays reorganization progress
   - For each file:
     - New folder path calculated using corrected date and organization template
     - File copied from old archive location to new location
     - Copy verified (file exists, size matches)
     - Old file deleted
     - Empty directories cleaned up
     - Database updated with new archive path
     - Reorganization flag cleared
   - Completion message shows success/failure counts

**Example: Correcting Scanned Family Photos**

Scenario: User scanned old family photos. Scanner assigned current date (2024) instead of actual photo dates.

1. User adds scanner output folder to "Unreliable Paths": `D:\Scanned\Family Photos\`
2. User processes scanned photos through Setup tab
3. All photos automatically flagged with reason: 'user_specified'
4. User opens Date Corrections tab and sees all 150 scanned photos
5. User groups photos by event:
   - Selects 15 photos from "Summer Vacation 1995"
   - Batch corrects with sequential dates starting 1995-07-01
   - Selects 20 photos from "Christmas 1998"
   - Batch corrects with same date: 1998-12-25
6. After correcting all photos, user clicks "Reorganize All Marked"
7. System moves all 150 photos from incorrect `2024/` folders to correct year folders
8. Photos now organized correctly: `1995/07/01/`, `1998/12/25/`, etc.
9. EXIF data in source files now has correct dates for future imports
