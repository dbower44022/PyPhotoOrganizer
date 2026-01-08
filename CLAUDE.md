# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**For end-user documentation, see [USER_GUIDE.md](USER_GUIDE.md).**

## Project Overview

PhotoOrganizer is a Python-based photo and video duplicate detection and organization system. It scans multiple source directories for media files, detects duplicates using SHA-256 hashing, and organizes unique files into a structured vault organized by creation date (year/month/day).

**Primary Goal**: Help users consolidate photos from multiple devices and locations (phones, tablets, PCs, NAS) into a single, deduplicated archive while preserving file metadata.

**Flow Diagram**: https://lucid.app/lucidchart/d52adf95-4275-4107-ad41-20c4cfd5c72c/edit?invitationId=inv_70bff327-b21c-4508-9ae6-03f07b9bdefe&page=4wTk8nA8b3At#

## CRITICAL: Source File Protection

**SOURCE FILES MUST NEVER BE MODIFIED UNDER ANY CIRCUMSTANCES.**

This is a fundamental architectural principle of the application:

1. **Read-Only Source Access**: All source directories are treated as read-only. Files are copied FROM sources, never written TO sources.

2. **No EXIF Writing to Sources**: When correcting dates, EXIF data is written ONLY to archive files (our managed copies), never to source files.

3. **Rationale**:
   - Prevents accidental corruption of original photos
   - Preserves original file integrity and metadata
   - Source files may be on shared drives, backups, or read-only media
   - Users trust their source files remain untouched

4. **Implementation**:
   - `date_correction_dialog.py`: Only writes EXIF to `archive_path`, never to `source_path`
   - `main.py`: Uses copy operations, never modifies source files
   - All file modifications (EXIF, reorganization) operate exclusively on archive copies

**When implementing new features**: Always ask "Does this modify a source file?" If yes, redesign to only modify archive files.

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
  - **Video files automatically pass through** (not filtered, handled separately)
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
  - **Video files pass through without PIL verification** (PIL cannot open videos)
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
  - **File Rename Management** (NEW in v2.2.2):
    - `is_file_rename_enabled()`: Check if filename template is enabled
    - `set_file_rename_enabled(enabled)`: Enable/disable file renaming
    - `get_filename_template()`: Get the filename template pattern
    - `set_filename_template(template)`: Save filename template with validation
    - `insert_rename_history()`: Track original → renamed mappings for undo capability
    - **IMPORTANT**: `get_metadata()` must SELECT `enable_file_rename` and `filename_template` columns
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

### Database Connection Management (v2.3.1)

**Problem**: SQLite "database is locked" errors occur when multiple components (main processing, audit logging, UI) access the database concurrently.

**Solution**: All database-accessing modules now use WAL mode and proper timeouts:

**Implementation in each module:**

1. **DuplicateFileDetection.py** (`PhotoDatabase` class):
   ```python
   self.conn = sqlite3.connect(self.database_path, timeout=30)
   self.conn.execute("PRAGMA journal_mode=WAL")
   self.conn.execute("PRAGMA busy_timeout=30000")
   ```

2. **database_metadata.py** (`DatabaseMetadata._get_connection()`):
   ```python
   conn = sqlite3.connect(self.database_path, timeout=30)
   conn.execute("PRAGMA journal_mode=WAL")
   conn.execute("PRAGMA busy_timeout=30000")
   return conn
   ```

3. **audit_manager.py** (`AuditManager._get_connection()`):
   - Same WAL mode and timeout settings
   - Additional retry logic for `log_file_operation()`:
     - 3 retries with exponential backoff (0.1s, 0.2s, 0.3s delays)
     - Only retries on "database is locked" errors
     - Logs warnings for retries, errors for failures

**Key Settings:**
- `timeout=30`: Wait up to 30 seconds for database locks
- `PRAGMA journal_mode=WAL`: Write-Ahead Logging enables concurrent reads/writes
- `PRAGMA busy_timeout=30000`: SQLite-level 30 second busy wait

**WAL Mode Benefits:**
- Readers don't block writers
- Writers don't block readers
- Better performance for concurrent access
- Creates additional files: `*.db-wal` and `*.db-shm` (normal, don't delete)

### Data Flow

1. **GUI Mode**: Source directories loaded from database `SourceDirectories` table (persistent across sessions)
   - User selects which sources to scan using checkboxes
   - Only enabled sources are processed
   **CLI Mode**: Source directories configured in `settings.json`
2. `get_file_list()` scans source directories for files matching configured extensions
3. Each file is verified (`VerifyFileType()`) to ensure extension matches actual format
   - **Video files pass through without PIL verification** (trusted by extension)
4. **Photo filtering** (if enabled): File is checked to determine if it's a real photograph
   - Filtered files (icons, thumbnails, web graphics) are tracked separately and skipped
   - **Video files bypass filtering entirely** (pass through automatically)
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

**For IMAGE files:**
1. First attempts to read EXIF `DateTimeOriginal` from image metadata (most accurate for camera photos)
2. Falls back to IPTC `Date Created` (tag 2,55) if EXIF unavailable (useful for edited/processed images)
3. Falls back to OS file metadata if neither EXIF nor IPTC available:
   - Windows: `getctime()` (creation time) or `getmtime()` (modification time)
   - Linux/macOS: `st_birthtime` (creation time) or `st_mtime` (modification time)
4. Returns dates as formatted strings: `(year, month, day)` where month/day are zero-padded

**For VIDEO files:**
1. `ffprobe` from FFmpeg - reads `creation_time` tag from container metadata (most reliable)
2. `mutagen` library - reads MP4/MOV atom tags like `©day`
3. QuickTime atom parsing - reads `mvhd` creation_time directly from file structure
4. OS file metadata as fallback
5. Year 1000 default when all methods fail

**Date Source Values:**
- `'exif'` - Date from EXIF DateTimeOriginal
- `'iptc'` - Date from IPTC Date Created (tag 2,55)
- `'video_metadata'` - Date from video container metadata via ffprobe
- `'video_quicktime'` - Date from QuickTime/MP4 atoms (mutagen or direct parsing)
- `'os_metadata'` - Date from file system
- `'fallback'` - Year 1000 default when all extraction methods fail

**Video Processing Notes:**
- Video files (`.mp4`, `.mov`, `.avi`, `.mkv`, etc.) are detected by extension using `constants.VIDEO_EXTENSIONS`
- Video files skip the `PhotoFilter` (always pass through) since PIL cannot open videos
- The `_try_video_date()` function handles all video date extraction methods
- FFmpeg's `ffprobe` is the most reliable method - install FFmpeg for best results
- Fallback methods work without external dependencies but may be less reliable

**Important Implementation Notes (Fixed in v2.2.3):**
- EXIF extraction is **platform-independent** - works on Windows, Linux, and macOS
- Extension comparison is **case-insensitive** - handles `.JPG`, `.jpg`, `.Jpg`, etc.
- **Critical Fix (2026-01-05)**: Previously EXIF was only extracted on Windows, causing all Linux/macOS files to be flagged as unreliable. This has been corrected in `DuplicateFileDetection.py`
- **IPTC Support (2026-01-06)**: Added IPTC Date Created as fallback when EXIF is unavailable
- **Video Support (2026-01-07)**: Added video date extraction via ffprobe, mutagen, and QuickTime atom parsing

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

### Hash History System (NEW in v2.2.3)

**Purpose**: Preserve duplicate detection capability after EXIF modifications. When date corrections are written to image EXIF data, the file bytes change, which changes the SHA-256 hash. Without hash history, the modified file would no longer be detected as a duplicate of the original.

**Problem Solved:**
1. User processes file → hash=AAA stored in database
2. User corrects date → EXIF written → file hash changes to BBB
3. Same original file processed again → hash=AAA
4. **Without history**: AAA ≠ BBB → File copied again (duplicate!)
5. **With history**: AAA found in FileHashHistory → Detected as duplicate ✓

**Database Schema:**

**FileHashHistory Table:**
```sql
CREATE TABLE FileHashHistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    current_file_hash TEXT NOT NULL,   -- Current hash in UniquePhotos
    historical_hash TEXT NOT NULL,      -- Hash at some point in file's history
    created_date TEXT NOT NULL,         -- When this hash was recorded
    reason TEXT NOT NULL,               -- 'original', 'migration', 'exif_edit', 'date_correction'
    FOREIGN KEY (current_file_hash) REFERENCES UniquePhotos(file_hash)
);

-- Critical index for fast duplicate detection
CREATE INDEX idx_historical_hash ON FileHashHistory(historical_hash);
```

**Data Flow Example:**
```
Step 1: Photo imported (vacation.jpg, hash=AAA)
  UniquePhotos: file_hash=AAA
  FileHashHistory: current_file_hash=AAA, historical_hash=AAA, reason='original'

Step 2: Date correction applied, EXIF written (hash changes to BBB)
  UniquePhotos: file_hash=BBB (updated)
  FileHashHistory: [AAA entry preserved], new entry: current_file_hash=BBB, historical_hash=BBB, reason='date_correction'

Result: Both AAA and BBB will match this photo during duplicate detection
```

**Key Methods (DuplicateFileDetection.py):**
- `is_duplicate_hash_in_history(hash)`: Check if hash exists in any historical record
- `get_all_historical_hashes()`: Load all historical hashes for batch checking
- `add_hash_to_history(old_hash, new_hash, reason)`: Record new hash after modification; also updates `UniquePhotos.file_hash` and `UnreliableDates.file_hash`
- `get_photo_by_historical_hash(hash)`: Find photo record by any historical hash

**Key Methods (exif_writer.py):**
- `update_file_hash_after_modification(db_path, old_hash, file_path, reason)`: Recalculate hash after EXIF write and update history

**Integration Points:**
- `date_correction_dialog.py`: Calls `update_file_hash_after_modification()` after successful EXIF write
- `find_duplicates()`: Checks both current and historical hashes during duplicate detection

**Migration:**
Existing databases are automatically migrated when opened:
- FileHashHistory table created if missing
- Existing UniquePhotos records copied to history with reason='migration'
- No manual action required

### Photo Filtering (Icon/Thumbnail Exclusion)

**Purpose**: Automatically filter out non-photograph files (icons, web graphics, thumbnails) to prevent them from corrupting the photo archive.

**photo_filter.py** - Photo validation and filtering module
- `PhotoFilter` class: Multi-criteria validation to identify real photographs
  - File size filtering (default: minimum 50KB)
  - Dimension filtering (default: 800x600 to 50000x50000)
  - Small square detection (excludes perfect squares < 400x400, likely icons)
  - Filename pattern exclusion (favicon, icon, logo, thumb, button, etc.)
  - EXIF data requirement (optional - ensures photos have camera metadata)
  - **Video files automatically pass through** (detected by extension, not opened with PIL)
  - Tracks detailed statistics by filter reason

**Integration with Processing Pipeline**:
1. Photo filtering happens BEFORE hashing (saves processing time)
2. Video files bypass filtering entirely (pass through automatically)
3. Filtered files are tracked separately in results
4. Statistics show breakdown by filter reason
5. Files can optionally be moved to a separate filtered folder

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

### File Renaming System (NEW in v2.2.2)

**Purpose**: Allow users to customize filenames during processing using template-based patterns with date/time, original filename, folder names, and sequential counters.

**filename_template.py** - Template parsing and filename generation
- `FilenameTemplate` class: Handles template parsing and validation
  - `parse(template, file_date, original_filename, counter)`: Generate filename from template
  - `validate(template)`: Security checks (path traversal prevention, dangerous characters)
  - `get_example_output(template)`: Generate preview for user feedback

**Template Variables**:
- **Date/Time**: `{year}`, `{month}`, `{day}`, `{hour}`, `{minute}`, `{second}`
- **Original Filename**: `{original_name}`, `{original_name_no_ext}`, `{ext}`
- **Folder Names**: `{folder_name}` (immediate parent), `{parent_folder_name}` (parent's parent)
- **Sequential Counter**: `{counter}` or `{counter:04d}` (zero-padded format specifier)

**Example Templates**:
```python
# Date-based naming
"{year}{month}{day}_{hour}{minute}{second}"
# Original: IMG_1234.jpg → Result: 20260104_143015.jpg

# Preserve original with date prefix
"{year}-{month}-{day}_{original_name}"
# Original: vacation_beach.jpg → Result: 2026-01-04_vacation_beach.jpg

# Sequential numbering with padding
"photo_{counter:04d}"
# Original: IMG_001.jpg → Result: photo_0001.jpg

# Folder-based naming
"{folder_name}_{original_name_no_ext}"
# Path: /photos/2024_vacation/IMG_1234.jpg → Result: 2024_vacation_IMG_1234.jpg
```

**Integration Points**:
1. **Settings Tab** (`ui/settings_tab.py`):
   - Checkbox to enable/disable feature
   - Template input with live preview
   - Validation feedback
   - Saves to database via `DatabaseMetadata.set_filename_template()`

2. **Main Processing** (`main.py` line 310-330):
   - Checks `db_metadata.is_file_rename_enabled()`
   - Gets template via `db_metadata.get_filename_template()`
   - Parses template with `FilenameTemplate.parse()`
   - Records rename in `FileRenameHistory` table

3. **Collision Handling** (`utils.py` line ~400):
   - `get_unique_filename()` automatically adds `_1`, `_2`, `_3` suffix if file exists
   - No user intervention required

**Database Schema**:
```sql
-- DatabaseMetadata table (columns added):
enable_file_rename INTEGER DEFAULT 0
filename_template TEXT DEFAULT '{original_name}'

-- FileRenameHistory table (NEW):
CREATE TABLE FileRenameHistory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    renamed_filename TEXT NOT NULL,
    rename_timestamp TEXT NOT NULL,
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(file_hash)
);
```

**Security Features**:
- Path traversal prevention (blocks `..`, `/`, `\`)
- Dangerous character blocking (`<`, `>`, `:`, `"`, `|`, `?`, `*`)
- Template validation before saving
- Fallback to `{original_name}` on parse errors

**CRITICAL BUG FIX** (v2.2.2):
- `get_metadata()` MUST SELECT `enable_file_rename` and `filename_template` columns
- Previously these columns were missing from SELECT, causing `is_file_rename_enabled()` to always return False
- Fixed in `database_metadata.py` lines 289-310

**Design Principles**:
- Opt-in feature (disabled by default)
- Per-database settings (each database has its own template)
- Rename happens during initial processing (not retroactive)
- Original filenames stored in `FileRenameHistory` for future undo capability
- Template stored in database (not in settings.json)

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
- **EXIF Writing**: Optionally writes corrected date to archive file EXIF data (source files are never modified)
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
2026-01-04 10:23:15 INFO   → Archive file: /archive/2024/01/01/vacation_001.jpg
2026-01-04 10:23:15 INFO   ✓ EXIF written to archive file successfully
2026-01-04 10:23:15 INFO   ✓ Hash history updated: abc123... → def456...
2026-01-04 10:23:15 INFO   ✓ Database updated successfully
2026-01-04 10:23:15 INFO ✓ File 1 completed successfully
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

**EXIF Write Policy (v2.2.3)**:

**Critical Implementation Detail:**
EXIF data is written ONLY to archive files. Source files are NEVER modified.

**Why Archive Files Only?**
- **Source file protection**: Source files must never be modified to prevent corruption
- **Archive file**: This is our managed copy - safe to modify for date corrections
- The archive file is what gets reorganized during folder restructuring
- Source files remain pristine for future reference or re-import

**Implementation (date_correction_dialog.py):**
```python
# IMPORTANT: We NEVER modify source files to prevent corruption
# Only write EXIF to archive file (our managed copy)
if record.get('archive_path') and os.path.exists(record['archive_path']):
    write_exif_date(record['archive_path'], year_str, month_str, day_str)
    logger.info("✓ EXIF written to archive file successfully")
```

**Error Tracking:**
- Failure list for archive EXIF writes
- Detailed error messages show which file failed
- Summary reports show success counts

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

### Grid Interaction Patterns (v2.2.1)

**Purpose**: Provide consistent, intuitive grid interaction across all UI tables with standard Shift/Ctrl selection patterns and automatic checkbox synchronization.

**Implementation Overview:**

All grids in the application (Date Corrections, Setup, Filtered Files, Logs) share a common interaction model:

1. **Read-Only Cells**: All table cells (except checkboxes) are read-only to prevent accidental data editing
2. **Extended Selection**: Support for Shift/Ctrl multi-selection
3. **Checkbox Auto-Sync**: Row selection and checkboxes automatically stay synchronized
4. **Double-Click Toggle**: Double-click any row to toggle its checkbox
5. **Checkbox Column Support**: Shift/Ctrl work on checkbox column same as other columns

**Technical Implementation:**

**1. Read-Only Cells (All QTableWidgetItem objects):**
```python
# Set flags to prevent editing while allowing selection
item = QTableWidgetItem("Some Text")
item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
self.table.setItem(row, column, item)
```

**Critical**: Apply to ALL QTableWidgetItem objects across all columns (except checkbox column which uses different mechanisms).

**2. Extended Selection Mode:**
```python
# Enable Shift/Ctrl selection support
self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

# Track last clicked row for Shift+Click range selection
self.last_clicked_row = -1
```

**3. Signal Connections:**
```python
# Connect signals for interaction handling
self.table.itemSelectionChanged.connect(self.sync_checkboxes_with_selection)
self.table.itemDoubleClicked.connect(self.on_item_double_clicked)
self.table.itemClicked.connect(self.on_item_clicked)
```

**4. Checkbox Synchronization (Auto-Sync Pattern):**
```python
def sync_checkboxes_with_selection(self):
    """Sync checkbox states with row selection - checkboxes match selected rows."""
    selected_rows = set(index.row() for index in self.table.selectedIndexes())

    # Block signals to prevent recursive updates
    self.table.blockSignals(True)

    for row in range(self.table.rowCount()):
        checkbox_item = self.table.item(row, 0)
        if checkbox_item:
            is_selected = row in selected_rows
            new_state = Qt.Checked if is_selected else Qt.Unchecked
            # Only update if state changed (efficiency)
            if checkbox_item.checkState() != new_state:
                checkbox_item.setCheckState(new_state)

    self.table.blockSignals(False)
```

**5. Double-Click Checkbox Toggle:**
```python
def on_item_double_clicked(self, item):
    """Handle double-click on row - toggle checkbox."""
    if item is None:
        return

    row = item.row()
    column = item.column()

    # Don't toggle if double-clicking checkbox column (already toggles naturally)
    if column == 0:
        return

    # Toggle checkbox in column 0
    checkbox_item = self.table.item(row, 0)
    if checkbox_item:
        current_state = checkbox_item.checkState()
        new_state = Qt.Unchecked if current_state == Qt.Checked else Qt.Checked
        checkbox_item.setCheckState(new_state)
```

**6. Checkbox Column Click Handler (Critical for Shift/Ctrl on checkbox column):**
```python
def on_item_clicked(self, item):
    """Handle click on table item - support Shift/Ctrl selection on checkbox column."""
    if item is None:
        return

    row = item.row()
    column = item.column()

    # Only handle clicks on checkbox column (column 0)
    if column != 0:
        self.last_clicked_row = row
        return

    modifiers = QApplication.keyboardModifiers()

    # Handle Shift-click: select range and check all checkboxes in range
    if modifiers & Qt.ShiftModifier and self.last_clicked_row >= 0:
        start_row = min(self.last_clicked_row, row)
        end_row = max(self.last_clicked_row, row)
        target_state = item.checkState()

        self.table.blockSignals(True)
        for r in range(start_row, end_row + 1):
            self.table.selectRow(r)
            checkbox_item = self.table.item(r, 0)
            if checkbox_item:
                checkbox_item.setCheckState(target_state)
        self.table.blockSignals(False)
        # Trigger any dependent updates
        self.on_selection_changed()

    # Handle Ctrl-click: toggle row selection (checkbox handled by sync)
    elif modifiers & Qt.ControlModifier:
        if self.table.isRowSelected(row):
            self.table.selectRow(row)
        # Checkbox will auto-sync via itemSelectionChanged signal

    # Normal click: select row
    else:
        self.table.selectRow(row)

    self.last_clicked_row = row
```

**Two Checkbox Types (Different Implementations):**

**Type 1: QTableWidgetItem with ItemIsUserCheckable (Date Corrections Tab):**
```python
# Creating checkbox column
checkbox_item = QTableWidgetItem()
checkbox_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsSelectable)
checkbox_item.setCheckState(Qt.Unchecked)
self.table.setItem(row, 0, checkbox_item)

# Accessing state
checkbox_item = self.table.item(row, 0)
if checkbox_item.checkState() == Qt.Checked:
    # Row is selected
```

**Type 2: QCheckBox Widget (Setup Tab):**
```python
# Creating checkbox column
checkbox = QCheckBox()
checkbox_widget = QWidget()
checkbox_layout = QHBoxLayout(checkbox_widget)
checkbox_layout.addWidget(checkbox)
checkbox_layout.setAlignment(Qt.AlignCenter)
checkbox_layout.setContentsMargins(0, 0, 0, 0)
self.table.setCellWidget(row, 0, checkbox_widget)

# Accessing state (requires finding child widget)
checkbox_widget = self.table.cellWidget(row, 0)
if checkbox_widget:
    checkbox = checkbox_widget.findChild(QCheckBox)
    if checkbox and checkbox.isChecked():
        # Row is selected
```

**Important**: Click handlers must adapt to checkbox type. Date Corrections uses `item.checkState()`, Setup uses `checkbox.isChecked()`.

**7. Dialog Centering (Multi-Monitor Support):**
```python
def _center_dialog(self, dialog):
    """Center a dialog on the main application window."""
    parent = self.parent()
    if parent:
        # Get top-level window (not intermediate parent widget)
        main_window = parent.window()
        if main_window:
            # Ensure dialog has correct size
            dialog.adjustSize()

            # Use frameGeometry() to include window decorations
            parent_geo = main_window.frameGeometry()
            dialog_geo = dialog.frameGeometry()

            # Calculate centered position
            x = parent_geo.x() + (parent_geo.width() - dialog_geo.width()) // 2
            y = parent_geo.y() + (parent_geo.height() - dialog_geo.height()) // 2

            dialog.move(x, y)
```

**Critical**: Use `parent.window()` (not `self.parent()`) to get top-level window, and `frameGeometry()` (not `geometry()`) to include window decorations. This ensures correct positioning on multi-monitor setups.

**8. Error-Only Dialogs (Batch Operations):**
```python
# After batch operation completes
if error_count > 0 or exif_failures or db_failures:
    # Show detailed error dialog
    msg_box = QMessageBox(
        QMessageBox.Warning,
        "Corrections Complete with Issues",
        f"Successfully corrected: {success_count}\nFailed: {error_count}",
        QMessageBox.Ok,
        self
    )
    self._center_dialog(msg_box)
    msg_box.exec()
else:
    # Silent success - no dialog shown
    # Success information already logged in detail
    pass

self.accept()  # Close dialog
```

**Rationale**: Suppressing success dialogs for batch operations allows users to rapidly correct large numbers of files without interruption. Errors are still shown to ensure user awareness.

**Signal Blocking (Preventing Recursive Updates):**
```python
# Block signals before batch updates
self.table.blockSignals(True)

# Perform updates (won't trigger itemSelectionChanged, etc.)
for row in range(self.table.rowCount()):
    checkbox_item.setCheckState(Qt.Checked)
    self.table.selectRow(row)

# Unblock signals
self.table.blockSignals(False)

# Manually trigger any dependent updates
self.on_selection_changed()
```

**When to Use Signal Blocking:**
- Batch checkbox updates in sync_checkboxes_with_selection()
- Shift-click range selection (updating multiple rows)
- Programmatic row selection that shouldn't trigger cascade updates

**Common Pitfalls:**

1. **Forgetting to set read-only flags**: Cells will be editable
2. **Not using window().frameGeometry()**: Dialogs appear on wrong monitor
3. **Checkbox type mismatch**: Using QTableWidgetItem methods on QCheckBox widgets
4. **Infinite signal loops**: Not blocking signals during sync operations
5. **Not updating last_clicked_row**: Shift-click range selection breaks
6. **Not adapting for checkbox column**: Shift/Ctrl don't work on checkbox column

**Files Implementing This Pattern:**
- `ui/date_corrections_tab.py`: QTableWidgetItem checkboxes (lines 283-742)
- `ui/setup_tab.py`: QCheckBox widgets (lines 42-629)
- `ui/date_correction_dialog.py`: Dialog centering (lines 481-500)

### File Type Verification
- Uses PIL/Pillow to verify file format matches extension
- Automatically corrects mismatched extensions (e.g., `.png` file with `.jpg` extension)
- Handles files without extensions by testing against known image formats
- Uses `safe_rename_or_copy()` to handle locked files
- **Video files pass through without verification** - PIL cannot open videos, so extensions are trusted

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
  - `photo_filter.log` (photo_filter.py)

Format: `timestamp - module - level - function - line --- message`

### Log Rotation (NEW in v2.3.1)

**Purpose**: Prevent log files from growing unbounded and affecting application performance.

**Implementation** (`utils.py`):
```python
from logging.handlers import RotatingFileHandler

LOG_MAX_BYTES = 5 * 1024 * 1024  # 5 MB per log file
LOG_BACKUP_COUNT = 3  # Keep 3 backup files

def setup_logger(name, log_file, level=logging.DEBUG, max_bytes=None, backup_count=None):
    # Uses RotatingFileHandler instead of FileHandler
    file_handler = RotatingFileHandler(
        log_file,
        mode="a",
        maxBytes=max_bytes or LOG_MAX_BYTES,
        backupCount=backup_count or LOG_BACKUP_COUNT,
        encoding="utf-8"
    )
```

**Configuration:**
- **Max file size**: 5 MB per log file (configurable via `max_bytes` parameter)
- **Backup count**: 3 files (configurable via `backup_count` parameter)
- **Total max storage per module**: ~20 MB (5MB × 4 files)

**Rotation Behavior:**
When a log file reaches 5MB:
1. `app_error.log` → `app_error.log.1`
2. `app_error.log.1` → `app_error.log.2`
3. `app_error.log.2` → `app_error.log.3`
4. `app_error.log.3` is deleted
5. New empty `app_error.log` is created

**Benefits:**
- Prevents disk space exhaustion during long-running operations
- Maintains recent log history for debugging
- Automatic cleanup - no manual intervention needed
- Existing large log files can be manually deleted to start fresh

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
     - Write EXIF to archive file (recommended, checked by default)
     - Mark for reorganization (checked by default)
   - User clicks "Apply"
   - System writes EXIF to archive file (if enabled) - source files are never modified
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
9. EXIF data in archive files now has correct dates (source files remain untouched)

### Import Audit System (NEW in v2.3)

**Purpose**: Provide complete traceability for all file operations during import, allowing users to audit what happened, track duplicate relationships, and export reports.

**audit_manager.py** - Core audit infrastructure module
- `AuditManager` class: Manages import session tracking and reporting
  - `_get_connection()`: Returns SQLite connection with WAL mode and 30s timeout
  - Session lifecycle: `start_session()`, `end_session()`, `get_session()`
  - File operation logging: `log_file_operation()` with retry logic for lock contention
  - Duplicate tracking: `record_duplicate()`, `get_duplicates_of()`
  - Retention management: `get_retention_settings()`, `set_retention_settings()`, `apply_retention_policy()`
  - Report generation: `generate_session_report()`, `generate_duplicate_report()`, `generate_error_report()`
  - Export: `export_session_to_json()`, `export_session_to_csv()`, `export_duplicates_to_csv()`

**Database Schema** (new tables in audit_manager.py):
```sql
-- Track each import session
CREATE TABLE ImportSession (
    session_id TEXT PRIMARY KEY,  -- Format: YYYYMMDD_HHMMSS_XXXXXX
    start_timestamp TEXT NOT NULL,
    end_timestamp TEXT,
    status TEXT DEFAULT 'running',  -- running, completed, failed, cancelled
    source_directories TEXT,  -- JSON array
    destination_directory TEXT,
    operation_mode TEXT,  -- 'copy' or 'move'
    total_files_scanned INTEGER DEFAULT 0,
    total_files_processed INTEGER DEFAULT 0,
    total_unique_files INTEGER DEFAULT 0,
    total_duplicates INTEGER DEFAULT 0,
    total_filtered INTEGER DEFAULT 0,
    total_errors INTEGER DEFAULT 0,
    error_summary TEXT  -- JSON
);

-- Per-file operation log
CREATE TABLE FileProcessingLog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    source_path TEXT NOT NULL,
    destination_path TEXT,
    file_hash TEXT,
    operation TEXT NOT NULL,  -- 'copy', 'move', 'skip_duplicate', 'skip_filtered', 'error'
    status TEXT NOT NULL,  -- 'success', 'failed', 'skipped'
    file_size INTEGER,
    creation_date TEXT,
    date_source TEXT,
    hash_verification_status TEXT,
    process_timestamp TEXT NOT NULL,
    duration_ms INTEGER,
    error_code TEXT,
    error_message TEXT,
    duplicate_of_hash TEXT,
    filter_reason TEXT,
    FOREIGN KEY (session_id) REFERENCES ImportSession(session_id) ON DELETE CASCADE
);

-- Track duplicate relationships
CREATE TABLE DuplicateMapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_hash TEXT NOT NULL,
    original_path TEXT NOT NULL,
    duplicate_source_path TEXT NOT NULL,
    first_seen_session TEXT NOT NULL,
    first_seen_timestamp TEXT NOT NULL,
    times_seen INTEGER DEFAULT 1,
    UNIQUE(original_hash, duplicate_source_path)
);

-- Retention settings
CREATE TABLE AuditRetentionSettings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    retention_mode TEXT DEFAULT 'none',  -- 'sessions', 'days', 'none'
    retain_session_count INTEGER DEFAULT 50,
    retain_days INTEGER DEFAULT 365,
    auto_cleanup_enabled INTEGER DEFAULT 0
);
```

**GUI Integration:**

**Import History Tab** (`ui/import_history_tab.py`):
- **Layout** (top to bottom):
  - Row 1: Session dropdown, Status filter, Refresh button, Result/Started/Duration display
  - Row 2: Statistics (Scanned, Processed, New, Duplicates, Filtered, Errors)
  - Vertical splitter separating grid from preview
  - File operations grid with 8 columns (sortable, resizable)
  - Horizontal splitter separating preview from details
  - Image preview panel with rubber band zoom (drag to zoom, double-click reset)
  - File details panel with EXIF metadata
  - Export buttons: JSON, CSV, Duplicates CSV, Delete Session

- **Grid Features** (optimized for 100k+ records):
  - Columns: Source Folder, Source Filename, Dest Folder, Dest Filename, Operation, Status, Hash, Details
  - Custom `QAbstractTableModel` with display caching for performance
  - `QSortFilterProxyModel` for search and filtering
  - Proportional column resizing on window resize (respects minimum widths)
  - View filter: All Files / Duplicates Only / Errors Only
  - Operation filter: Copy, Move, Skip Duplicate, Skip Filtered, Error
  - Status filter: Success, Failed, Skipped
  - Text search with 300ms debounce

- **Image Preview** (`ImagePreviewWidget`):
  - Rubber band zoom: Click and drag to select region, release to zoom
  - Double-click to reset to fit-to-view
  - Maintains custom zoom during window resize
  - Dark background (#2d2d2d) for better image visibility

- **File Details Panel** (`FileDetailsWidget`):
  - Operation details (operation type, status, errors)
  - File paths (source and destination)
  - SHA-256 hash
  - File information (size, modified date)
  - Image properties (dimensions, format, color mode)
  - EXIF data (date taken, camera, exposure, aperture, ISO, focal length, GPS)

- Auto-refresh on tab display

**Settings Tab** (retention settings):
- Retention mode: Keep All, Keep Last N Sessions, Keep Last N Days
- Session/days count spinner
- Auto-cleanup on startup checkbox
- "Clean Up Now" button for manual retention

**Integration Points:**

1. **worker.py**: Session lifecycle management
   - `start_session()` called at processing start
   - `end_session()` called on completion/failure/cancellation
   - Session stats updated throughout processing

2. **DuplicateFileDetection.py**: Logs duplicates and filtered files
   - `log_file_operation()` with operation='skip_duplicate' or 'skip_filtered'
   - `record_duplicate()` to track original-duplicate relationships

3. **main.py**: Logs copy/move operations
   - `log_file_operation()` with operation='copy' or 'move'
   - Error logging with tracebacks

**Usage Example:**

1. User runs import process
2. System automatically creates audit session
3. All file operations logged with timing and results
4. User clicks "Import History" tab after processing
5. Session list shows recent imports with status
6. User selects session to view details:
   - Statistics (files processed, duplicates, errors)
   - File-level operation log
   - Duplicate relationships
7. User can export reports to JSON/CSV for external analysis
8. Retention settings automatically clean up old sessions
