# PyPhotoOrganizer

> A robust Python-based photo and video duplicate detection and organization system with full-featured GUI

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-3.0.3-brightgreen.svg)](CHANGELOG.md)

## Overview

PyPhotoOrganizer helps you consolidate photos and videos from multiple devices and locations (phones, tablets, PCs, NAS) into a single, deduplicated archive while preserving file metadata. It uses SHA-256 hashing for accurate duplicate detection and organizes files into a date-based folder structure.

### Key Features

**Core Features:**
- ✅ **Intelligent Duplicate Detection**: Two-stage SHA-256 hashing with partial hash optimization for large files
- ✅ **Advanced Photo Filtering**: Automatically excludes icons, thumbnails, and web graphics with customizable patterns
- ✅ **Date-Based Organization**: Organizes files by creation date (YYYY/MM/DD structure)
- ✅ **HEIC Support**: Converts Apple HEIC/HEIF images to JPEG with metadata preservation
- ✅ **Resume Capability**: Batch commits allow safe interruption and resumption of long-running processes
- ✅ **File Type Verification**: Validates file extensions match actual file format
- ✅ **Multiple Source Support**: Process multiple directories in a single run
- ✅ **Flexible Operations**: Copy or move files to destination
- ✅ **Database-First Architecture**: Each database is permanently bound to a specific archive location

**GUI Features (v2.0+):**
- ✅ **Professional Splash Screen**: Instant feedback on startup with loading status
- ✅ **Graphical Interface**: Full-featured PySide6 GUI with tab-based navigation
- ✅ **Database Management**: Create, select, and manage multiple databases with metadata
- ✅ **Persistent Source Directories**: Sources stored in database, automatically loaded with status tracking
- ✅ **Real-Time Progress**: Live updates with accurate time estimates using EMA algorithm
- ✅ **Smart Source Selection**: Enable/disable sources with checkboxes, view last scanned timestamps
- ✅ **Path Status Monitoring**: Visual indicators for available/unavailable sources with detailed tooltips
- ✅ **Advanced Settings Editor**: Interactive configuration with filename pattern management
- ✅ **Results Dashboard**: Detailed statistics with copyable text and export capabilities
- ✅ **Filtered Files Review**: Comprehensive tab to review and understand filtered files
- ✅ **Advanced Log Viewer**: Multi-log support, filtering, search, statistics, and time-range filtering
- ✅ **Responsive Design**: Background worker thread keeps UI responsive during processing
- ✅ **Resizable Panels**: Splitter bars allow customizable layout
- ✅ **Active UI Principle**: All buttons stay enabled with informative feedback

**Date Correction Features (v2.2+):**
- ✅ **Automatic Detection**: System identifies files with unreliable dates during processing
- ✅ **Smart Filtering**: Filter by reason (no EXIF, suspicious dates, user-specified paths)
- ✅ **Status Tracking**: Three-state system (Pending/Corrected/Reorganized) with color coding
- ✅ **Audit Trail**: Maintains original archive locations for verification
- ✅ **Image Preview**: Zoomable preview panel with rubber band selection
- ✅ **Single File Correction**: Easy date correction with visual date picker
- ✅ **Batch Correction**: Correct multiple files with same or sequential dates
- ✅ **EXIF Writing**: Writes corrected dates to archive files (source files never modified)
- ✅ **Safe Reorganization**: Copy-verify-delete pattern with empty directory cleanup
- ✅ **Comprehensive Logging**: Visual indicators (✓✗⚠ℹ) for easy log navigation
- ✅ **User-Specified Paths**: Auto-flag files from unreliable sources (e.g., scanned photos)

**Import Audit Features (v2.3+):**
- ✅ **Complete Audit Trail**: Every file operation logged with session tracking
- ✅ **Import History Tab**: View all import sessions with statistics
- ✅ **Duplicate Tracking**: See which files are duplicates of which originals
- ✅ **Export Reports**: JSON and CSV export for external analysis
- ✅ **Retention Settings**: Automatic cleanup of old audit records
- ✅ **Hash History System**: Preserves duplicate detection after EXIF modifications

**File Renaming Features (v2.2.1+):**
- ✅ **Template-Based Renaming**: Customize filenames during processing with powerful template system
- ✅ **Rich Template Variables**: Date/time ({year}, {month}, {day}, {hour}, {minute}, {second}), original filename ({original_name}, {original_name_no_ext}), file extension ({ext}), folder names ({folder_name}, {parent_folder_name}), sequential counter ({counter}, {counter:04d})
- ✅ **Live Preview**: Real-time preview shows example output as you type
- ✅ **Template Validation**: Security checks prevent path traversal and dangerous characters
- ✅ **Collision Handling**: Automatic counter suffix (_1, _2, _3) for filename conflicts
- ✅ **Per-Database Settings**: Each database stores its own filename template
- ✅ **Opt-In Feature**: Disabled by default, preserves original filenames unless enabled
- ✅ **Rename History**: Database tracks original filenames for future undo capability

**File Version Management Features (v2.4+):**
- ✅ **Multi-Hash Duplicate Detection**: Track multiple variations of same photo (rotated, cropped, color-corrected)
- ✅ **Star Topology Linking**: All versions linked to original via hash history
- ✅ **Automatic Version Tracking**: Any modified version detected as duplicate during re-import
- ✅ **Image Transformations**: Rotate, crop, resize, color adjust, format convert with EXIF preservation
- ✅ **Version History**: Complete parent-child relationship tracking with modification parameters
- ✅ **Version Restoration**: Restore any previous version to target location
- ✅ **Separate Storage**: Versions stored in hidden `.pyphotoorg_versions/` folder
- ✅ **Database Migration**: Automatic upgrade to schema v3 with version support
- ✅ **Sync Utility**: Retroactive duplicate detection for existing versions
- ✅ **Source File Protection**: All modifications work on copies, never modify source files

**Image Rotation & Prior Revision Archive Features (v3.0.3):**
- ✅ **Dual-Archive Architecture**: Separate main archive (current revisions) from prior revision archive (historical versions)
- ✅ **Clean Main Archive**: Main archive contains ONLY the latest revision of each file
- ✅ **Complete History Preservation**: All superseded revisions automatically moved to Prior Revision Archive
- ✅ **Hash-Suffixed Filenames**: Prior revisions use hash suffixes to prevent collisions (e.g., `photo_abcd1234.jpg`)
- ✅ **Date Structure Mirroring**: Prior archive mirrors main archive's YYYY/MM/DD folder structure
- ✅ **Instant Undo**: Restore previous revision by swapping files between archives
- ✅ **Transparent Duplicate Detection**: All revision hashes tracked in FileHashHistory for seamless duplicate detection
- ✅ **User-Configurable Location**: Set Prior Revision Archive location independently from main archive
- ✅ **Extensive Validation**: Prevents invalid configurations (same path, nested paths, unwritable locations)
- ✅ **Safe File Operations**: Copy-verify-delete pattern with multiple fallback strategies
- ✅ **Complete Audit Trail**: All rotation and undo operations logged in import history
- ✅ **Database Auto-Migration**: Automatic schema update adds `prior_revision_archive_location` column
- ✅ **Revision Chain Tracking**: Parent-child relationships preserved across multiple rotations
- ✅ **Integration with Date Corrections**: Rotated files maintain date correction flags and metadata
- ✅ **Multi-Rotation Support**: Unlimited rotation operations with full undo capability at each step
- ✅ **Performance Optimized**: 100-500ms per rotation, 50-150ms per undo operation

**Filtering Features:**
- ✅ **Filename Pattern Filtering**: Customizable list of excluded patterns (favicon, icon, logo, etc.)
- ✅ **Size-Based Filtering**: Minimum/maximum file size validation
- ✅ **Dimension-Based Filtering**: Minimum/maximum width and height validation
- ✅ **Square Icon Detection**: Filters small square images (likely icons)
- ✅ **EXIF Requirement**: Optional requirement for EXIF data
- ✅ **Detailed Filter Statistics**: Track and review why each file was filtered

### Use Cases

✅ Consolidating photos from multiple backup locations
✅ Cleaning up duplicate photos from repeated device backups
✅ Creating a single master photo archive
✅ Organizing photos by date for photo management software (like Mylio)
✅ Deduplicating large photo collections (10,000+ files)
✅ Separating photo and video archives (upcoming feature)

## Quick Start

### Prerequisites

- Python 3.8 or higher
- PySide6 for GUI
- ~50MB disk space for database
- Sufficient storage for your photo collection

### Installation

```bash
# Clone or download the repository
cd PyPhotoOrganizer

# Install dependencies
pip install -r requirements.txt
```

### Basic Usage

**Option A: Graphical Interface (Recommended)**

```bash
python main_gui.py
```

**First-Time Setup:**
1. **Database Selector Dialog** appears on startup
2. Choose "Create New Database" or "Select Existing Database"
3. For new database:
   - Enter database name (e.g., "Family Photos")
   - Select archive location (where organized files will be stored)
   - Optionally add description
4. Click "Create Database" or "Open Database"

**Processing Workflow:**
1. **Import Settings Tab**:
   - Add source folders (stored persistently in database)
   - Enable/disable sources with checkboxes for selective processing
   - View status and last scanned timestamp for each source
   - Configure ignored directories with wildcard patterns
   - Adjust file processing settings (subdirectories, batch size)
   - Set photo filtering criteria (dimensions, file size, EXIF)
   - Customize filename pattern exclusions
   - Click "Start Processing" button
2. **Archive Settings Tab** (optional):
   - Configure organization template (folder structure)
   - Set file type organization mode (combined/subfolder/separate)
   - Enable and configure file renaming with templates
3. **System Settings Tab** (optional):
   - View database information and statistics
   - Select Copy or Move mode
   - Configure performance settings (partial hash)
   - Set thumbnail cache size
   - Manage import history retention
4. **Progress Tab**:
   - Monitor real-time progress with time estimates
   - View processing rates and stage information
   - Auto-expanding status log
5. **Results Tab**:
   - View detailed statistics (copyable text)
   - Copy statistics to clipboard
6. **Filtered Files Tab**:
   - Review files that were filtered out
   - See filter reasons and file details
   - Preview images and open file locations
   - Export filtered files list
7. **Logs Tab**:
   - Review detailed processing logs
   - Filter by level, search, time range
   - View statistics and export logs

**Option B: Command Line Interface**

1. **Create configuration file** (`settings.json`):

```json
{
  "source_directory": ["/path/to/photos"],
  "destination_directory": "/path/to/organized/photos",
  "database_path": "PhotoDB.db",
  "copy_files": true,
  "move_files": false
}
```

2. **Run the organizer**:

```bash
python main.py
```

3. **Monitor progress**:
```
Scanning directories: 100%|████████| 3/3 [00:02<00:00]
Processing files: 100%|████████| 1500/1500 [05:30<00:00, 4.5file/s]
Organizing files: 100%|████████| 850/850 [02:15<00:00, 6.3file/s]
```

## GUI Tabs Reference

### 1. Setup Tab
- **Source Folders Table** (Persistent, Database-Backed):
  - **Enable Column**: Checkbox to select which sources to scan (✓ = included in current run)
  - **Status Icon**: Visual indicator (✓ green = available, ⚠ red = unavailable)
  - **Source Path**: Full directory path
  - **Last Scanned**: Timestamp of last successful scan (YYYY-MM-DD HH:MM)
  - **Status**: Text description (Available, Not Mounted, Not Found, Permission Denied)
  - **Tooltips**: Hover over any row for detailed status information
  - Sources persist across sessions - no need to re-add every time!
- **Buttons**:
  - **Add Folder**: Browse and add source directories (auto-saves to database)
  - **Remove Selected**: Remove selected source from list and database
  - **Clear All**: Remove all sources with confirmation
  - **Refresh Status**: Re-validate availability of all sources
- **Destination Folder**: View archive location (managed by database)
- **Operation Mode**: Select Copy or Move
- **Start/Stop Processing**: Control processing with confirmation dialogs
- **Special Features**:
  - Network path detection (GVFS mounts: `/run/user/*/gvfs/`)
  - Helpful messages for unmounted network shares
  - Only processes sources with checked checkboxes
  - Automatically updates last scanned timestamp after processing

### 2. Progress Tab
- **Overall Progress**: Total files, elapsed time, remaining time estimate
- **Current Stage**: Shows current stage (Scanning, Processing, Organizing)
- **Stage Progress**: Detailed progress for current stage
- **Status Log**: Expandable log with last 100 events (color-coded by level)

### 3. Results Tab
- **Summary Statistics**: Copyable text with total files, originals, duplicates, filtered
- **Copy to Clipboard**: Export statistics to clipboard

### 4. Filtered Files Tab
- **Files Table**: Shows all filtered files with reason, size, dimensions, path
- **Filter by Reason**: Dropdown to filter by specific reason
- **File Details Panel**: Displays all file attributes for selected file
- **Image Preview**: Shows thumbnail preview of selected image
- **Actions**: Open File, Open Folder, Copy Path
- **Export**: Export filtered files list to CSV or TXT

### 5. Logs Tab
- **Multi-Log Support**: View different log files (main, duplicate detection, etc.)
- **Statistics Dashboard**: Clickable counts by log level
- **Level Filter**: Filter by DEBUG, INFO, WARNING, ERROR, CRITICAL
- **Search**: Real-time search across log entries
- **Time Range**: Filter by last 5 min, hour, today, all time
- **Details Panel**: Full log entry details for selected row
- **Export**: Export logs to CSV or TXT
- **Clear**: Clear log file with confirmation

### 6. Import Settings Tab (NEW in v2.4)
- **Source Folders**: Add/remove source directories with enable/disable checkboxes
  - View last scanned timestamp for each source
  - Persistent storage in database
- **Ignored Directories**: Configure directories to skip with wildcard patterns (*, ?)
  - Add/remove patterns
  - Preset patterns available (thumbnails, cache, temp folders)
- **File Processing**: Include subdirectories, batch size
- **Photo Filtering**: Size, dimensions, square detection, EXIF requirements
  - Min/max file size, width, height
  - Exclude small squares (icons)
  - Require EXIF data option
- **Filename Patterns**: Customizable list of excluded patterns
  - Default patterns: favicon, icon, logo, thumb, button, badge, sprite
- **Start/Stop Buttons**: Large, styled buttons to control processing

### 7. Archive Settings Tab (NEW in v2.4)
- **Archive Location**: Display-only field showing archive folder (managed by database)
- **Organization Settings**:
  - Preset folder structures (By Day, By Month, By Year, etc.)
  - Custom template editor with live preview
  - Template variables: {year}, {month}, {day}, {month_name}, {month_sname}, {day_name}, {day_sname}
  - Quick-insert buttons for common patterns
  - Reorganization warning for existing archives
- **File Type Organization**:
  - Same folders as photos (combined)
  - Separate subfolder under date folder (Photos/, Videos/)
  - Completely separate archive location (different paths)
- **File Renaming**: Enable/disable file renaming with customizable templates
  - Template Variables: {year}, {month}, {day}, {hour}, {minute}, {second}, {original_name}, {original_name_no_ext}, {ext}, {folder_name}, {parent_folder_name}, {counter}, {counter:04d}
  - Example: `{year}{month}{day}_{original_name_no_ext}` → `20260104_IMG_1234.jpg`
  - Security validation prevents dangerous characters and path traversal
  - Live preview with example output

### 8. System Settings Tab (NEW in v2.4)
- **Current Database Information**:
  - Database name, file path, created date, last used date
- **Current Database Statistics**:
  - Total photos count
  - Schema version
  - Refresh button
- **Operation Mode**:
  - Copy Files (Safe - keeps originals)
  - Move Files (Destructive - deletes originals)
- **Performance Settings**:
  - Partial hash enabled/disabled
  - Partial hash bytes (1KB - 1MB)
  - Min file size for partial hash
- **Thumbnail Cache Settings**:
  - Cache memory size (50-2000 MB)
  - Worker threads (1-16)
  - Live calculation of thumbnail count
- **Import History Retention**:
  - Retention mode (Keep All, Keep Last N Sessions, Keep Last N Days)
  - Session/days count
  - Auto-cleanup on startup
  - Manual cleanup button
- **Settings Management**:
  - Load from File
  - Save to File
  - Restore Defaults
  - Validate Settings

### 9. Date Corrections Tab (NEW in v2.2)
- **Files Table**: Sortable grid showing all files with unreliable dates
  - Columns: Checkbox, Filename, Source Location, Archive Location, Detected Date, EXIF Date, File Date, Flag Reason, Status
  - Filter by flag reason (No EXIF, Year 1000, Suspicious, User-Specified)
  - Filter by status (Pending, Corrected, Reorganized)
  - Multi-select for batch operations
- **Preview Panel**:
  - Zoomable image preview (click-drag rubber band selection)
  - Double-click to reset zoom
  - Detailed file metadata display
  - Shows both current and original archive paths (for auditing)
- **Buttons**:
  - **Correct Date**: Opens dialog to correct selected file's date
  - **Batch Correct**: Two modes (same date or sequential dates)
  - **Manage Unreliable Paths**: Configure auto-flagged source paths
  - **Reorganize All Marked**: Batch reorganize corrected files to proper date folders
  - **Refresh**: Reload data from database
- **Status Color Coding**:
  - Gray: Pending (not yet corrected)
  - Dark Green: Corrected (waiting for reorganization)
  - Blue: Reorganized (completed, available for audit)

## Documentation

📚 **Comprehensive guides available:**

- **[Architecture Guide](ARCHITECTURE.md)** - System design and technical details (includes GUI architecture)
- **[Configuration Guide](CONFIGURATION.md)** - Complete settings reference
- **[API Documentation](API.md)** - Code reference and API details
- **[Development Guide](DEVELOPMENT.md)** - Contributing and development setup
- **[Troubleshooting](TROUBLESHOOTING.md)** - Common issues and solutions (includes GUI troubleshooting)
- **[Quick Reference](QUICKREF.md)** - One-page cheat sheet (includes GUI commands)
- **[GUI Testing Guide](GUI_TESTING_GUIDE.md)** - Comprehensive GUI testing procedures
- **[CLAUDE.md](CLAUDE.md)** - Instructions for AI assistant integration

## How It Works

```
┌─────────────────┐
│  Source Dirs    │
│ (Multiple)      │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│  File Discovery     │
│  - Recursive scan   │
│  - Extension filter │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  File Verification  │
│  - Type validation  │
│  - Extension fix    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Photo Filtering    │
│  - Size check       │
│  - Dimension check  │
│  - Pattern exclude  │
│  - EXIF check       │
└─────────┬───────────┘
          │
          ├─► Filtered ──► Tracked & Reviewable
          │
          ▼
┌─────────────────────┐
│  Duplicate Check    │
│  - Partial hash     │
│  - Full hash        │
│  - Database lookup  │
└─────────┬───────────┘
          │
          ├─► Duplicate ──► Skip
          │
          └─► Unique ──────┐
                           │
                           ▼
                  ┌────────────────┐
                  │  Extract Date  │
                  │  - EXIF data   │
                  │  - File system │
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Route by Type │
                  │  Photo/Video   │
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Organize      │
                  │  YYYY/MM/DD    │
                  └────────┬───────┘
                           │
                           ▼
                  ┌────────────────┐
                  │  Copy/Move     │
                  │  + Update DB   │
                  └────────────────┘
```

## Configuration Example

```json
{
  "source_directory": [
    "D:\\Phone Backups\\iPhone",
    "D:\\Phone Backups\\Android",
    "D:\\Old PC Photos"
  ],
  "destination_directory": "E:\\Master Photo Archive",
  "database_path": "PhotoDB.db",

  "include_subdirectories": true,
  "file_endings": [".jpg", ".jpeg", ".png", ".heic", ".tif", ".mov", ".mp4"],

  "copy_files": true,
  "move_files": false,

  "group_by_year": true,
  "group_by_day": true,

  "batch_size": 100,

  "partial_hash_enabled": true,
  "partial_hash_bytes": 16384,
  "partial_hash_min_file_size": 1048576,

  "photo_filter_enabled": true,
  "min_file_size": 51200,
  "min_width": 800,
  "min_height": 600,
  "max_width": 50000,
  "max_height": 50000,
  "exclude_square_smaller_than": 400,
  "require_exif": false,
  "excluded_filename_patterns": ["favicon", "icon", "logo", "thumb", "button", "badge", "sprite"]
}
```

## Performance

### Benchmark Results

**Test Environment:** Intel i7, SSD, 10,000 mixed photo/video files

| Operation | Speed | Notes |
|-----------|-------|-------|
| File scanning | ~500 files/sec | Includes subdirectories |
| Small photos (<1MB) | ~5-10 files/sec | Full hash |
| Large photos (1-5MB) | ~8-12 files/sec | Partial hash optimization |
| Videos (100MB-2GB) | ~2-4 files/sec | Partial hash optimization |
| Database commit | <1ms | SQLite with indexes |
| Photo filtering | ~50-100 files/sec | Pre-hash filtering |

### Optimization Features

- **Partial Hashing**: Only hashes first 16KB of large files unless potential duplicate
- **Batch Commits**: Commits every 100 files to preserve progress
- **Database Indexes**: Fast lookups on hash, size, and date fields
- **Photo Filtering**: Skips non-photos before expensive hashing
- **EMA Time Estimation**: Accurate remaining time estimates using exponential moving average

## Database Schema

### UniquePhotos Table
```sql
CREATE TABLE UniquePhotos (
    file_hash TEXT PRIMARY KEY,           -- SHA-256 hash of full file
    partial_hash TEXT,                    -- SHA-256 hash of first N bytes
    partial_hash_bytes INTEGER,           -- Number of bytes in partial hash
    file_size INTEGER,                    -- File size in bytes
    file_name TEXT NOT NULL,              -- Full path to file
    create_datetime TEXT,                 -- Creation timestamp
    create_year TEXT,                     -- Creation year (YYYY)
    create_month TEXT,                    -- Creation month (MM)
    create_day TEXT                       -- Creation day (DD)
);

CREATE INDEX idx_partial_hash ON UniquePhotos(partial_hash);
CREATE INDEX idx_file_size ON UniquePhotos(file_size);
CREATE INDEX idx_date ON UniquePhotos(create_year, create_month, create_day);
CREATE INDEX idx_file_name ON UniquePhotos(file_name);
```

### DatabaseMetadata Table
```sql
CREATE TABLE DatabaseMetadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    database_name TEXT NOT NULL,
    description TEXT,
    archive_location TEXT NOT NULL,
    video_archive_location TEXT,          -- Optional separate video archive
    separate_video_archive INTEGER DEFAULT 0,
    created_date TEXT NOT NULL,
    last_used_date TEXT,
    schema_version INTEGER DEFAULT 1,
    total_photos INTEGER DEFAULT 0,
    organization_template TEXT DEFAULT '{YYYY}/{MM}/{DD}',
    file_type_organization TEXT DEFAULT 'combined',
    enable_file_rename INTEGER DEFAULT 0, -- Enable/disable filename template
    filename_template TEXT DEFAULT '{original_name}'  -- Filename template pattern
);
```

### UnreliableDates Table (NEW in v2.2)
```sql
CREATE TABLE UnreliableDates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_hash TEXT NOT NULL,              -- Links to UniquePhotos.file_hash
    source_path TEXT NOT NULL,            -- Original source file path
    archive_path TEXT,                    -- Current archive location
    original_archive_path TEXT,           -- Pre-reorganization location (audit trail)
    original_date TEXT,                   -- Date detected during processing
    date_source TEXT,                     -- 'exif', 'os_metadata', 'fallback'
    flag_reason TEXT,                     -- 'no_exif', 'year_1000', 'suspicious', 'user_specified'
    corrected_date TEXT,                  -- User-corrected date (YYYY-MM-DD)
    correction_timestamp TEXT,            -- When correction was made
    needs_reorganization INTEGER DEFAULT 0,  -- Flag for batch reorganization
    FOREIGN KEY (file_hash) REFERENCES UniquePhotos(hash)
);
```

## Security Features

✅ **Path Traversal Protection**: Validates all paths to prevent directory traversal attacks
✅ **SQL Injection Prevention**: Uses parameterized queries exclusively
✅ **File Lock Handling**: Safe rename/copy fallback for locked files
✅ **Input Validation**: Validates all configuration settings
✅ **Error Isolation**: Individual file errors don't stop processing
✅ **Active UI Principle**: No disabled buttons - informative dialogs instead

## Project Structure

```
PyPhotoOrganizer/
├── main.py                      # Main orchestration (CLI)
├── main_gui.py                  # GUI entry point with splash screen
├── config.py                    # Configuration management
├── constants.py                 # Application constants (includes file type definitions)
├── utils.py                     # Shared utilities (file type detection)
├── DuplicateFileDetection.py   # Core duplicate detection
├── photo_filter.py             # Photo filtering logic
├── database_metadata.py        # Database metadata management
├── ui/                         # GUI components (~3000 lines)
│   ├── main_window.py          # Main window with tab management
│   ├── import_settings_tab.py  # Source folders, filtering, Start/Stop (NEW v2.4)
│   ├── archive_settings_tab.py # Organization, file types, renaming (NEW v2.4)
│   ├── system_settings_tab.py  # Database, operation mode, performance (NEW v2.4)
│   ├── progress_tab.py         # Real-time progress with EMA estimates
│   ├── results_tab.py          # Statistics and export
│   ├── filtered_files_tab.py   # Filtered files review with preview
│   ├── logs_tab.py             # Advanced log viewer (571 lines)
│   ├── date_corrections_tab.py # Unreliable date correction (v2.2)
│   ├── import_history_tab.py   # Import session history and reprocessing (v2.3)
│   ├── database_selector_dialog.py  # Startup database selector
│   ├── create_database_dialog.py    # Database creation wizard
│   └── worker.py               # Background processing thread
├── settings.json               # Configuration file
├── requirements.txt            # Python dependencies
├── PhotoDB.db                  # SQLite database
└── docs/                       # Documentation (9 files)
    ├── README.md               # This file
    ├── ARCHITECTURE.md         # Technical architecture
    ├── CONFIGURATION.md        # Settings reference
    ├── API.md                  # Code documentation
    ├── DEVELOPMENT.md          # Developer guide
    ├── TROUBLESHOOTING.md      # Issue resolution
    ├── QUICKREF.md             # Quick reference
    ├── GUI_TESTING_GUIDE.md    # GUI testing procedures
    └── CLAUDE.md               # AI assistant instructions
```

## Recent Improvements

### Version 3.0.2 (January 2026)

**DeletedFiles Table & Database Enhancements:**
✅ **Soft-Delete System**: Complete DeletedFiles table implementation with restore capability
✅ **Corrupted File Handling**: Generate "CORRUPTED" placeholder thumbnails for damaged images
✅ **Schema Test Suite**: Comprehensive tests verify all tables, columns, indexes, and foreign keys (100% pass rate)
✅ **Foreign Key Fixes**: Corrected UnreliableDates foreign key reference and added missing indexes
✅ **Auto-Upgrade System**: All schema changes applied automatically on database open

**Technical Details:**
✅ DeletedFiles table with 11 columns and 3 performance indexes for fast queries
✅ Corrupted image placeholders with warning symbol and red/orange color scheme
✅ Test infrastructure: `test_database_schema.py` (24 tests) and `test_deleted_files_table.py`
✅ UnreliableDates indexes added: `idx_unreliable_hash`, `idx_unreliable_needs_reorg` (10-100x speedup)
✅ Fixed format error in `mark_file_as_deleted()` (int conversion for date formatting)

### Version 3.0.1 (January 2026)

**Bug Fixes & UX Improvements:**
✅ **Organization Template Bug Fixed**: Custom templates now correctly applied during import
✅ **Delete Vault Auto-Save**: Configuration now auto-saves when directory selected (removed manual save button)
✅ **Database Auto-Upgrade**: Automatic schema upgrades for `delete_vault_location` and `file_modified_timestamp` columns
✅ **Missing Imports Fixed**: Added `QProgressDialog` import to date_corrections_tab
✅ **Enhanced Logging**: All delete vault and triage operations now follow project logging standards with visual indicators (✓ ✗ ℹ) and detailed context

**Technical Details:**
✅ Configuration flow fixed: Organization template now correctly passed from database → config dict → worker thread
✅ ThumbnailCache schema auto-upgrade: Adds `file_modified_timestamp` column on first access
✅ DatabaseMetadata schema auto-upgrade: Adds `delete_vault_location` column on first access
✅ Comprehensive logging with section markers (`===` boundaries, `---` subsections, `exc_info=True` for exceptions)

### Version 3.0.0 (January 2026)

**Major Schema Redesign (BREAKING CHANGE):**
✅ **Schema v5**: Unified UniquePhotos architecture - all files (originals + revisions) in single table
✅ **10-20x Faster**: Duplicate detection via primary key lookup instead of 2-table join
✅ **Revision Tracking**: New columns `revised_photo`, `revision_reason`, `source_path`, `revision_timestamp`
✅ **Cleaner Architecture**: Removed 4 redundant tables (FileHashHistory, FileVersions, ModificationSession, ModificationLog)
✅ **Migration Script**: Automated migration with safety checks and comprehensive logging
✅ **Preserved Data**: Database config, source directories, and audit history (64+ import sessions) preserved during migration
✅ **Fresh Import Required**: All photo records cleared during migration but duplicates automatically skipped

**Worker Updates:**
✅ `rotate_worker.py` - Uses `create_revision()` instead of VersionManager
✅ `exif_writer.py` - Rewritten `update_file_hash_after_modification()` for v5 schema
✅ `reprocess_worker.py` - Added source_path parameter to track original import location
✅ `delete_worker.py` & `restore_worker.py` - Already compatible, no changes needed

### Version 2.3.1 (January 2026)

**Database Reliability:**
✅ WAL mode for all database connections (prevents "database is locked" errors)
✅ 30-second timeouts with retry logic for concurrent access
✅ Log rotation (5MB max, 3 backups) prevents unbounded log growth

### Version 2.3 (January 2026)

**Import Audit System:**
✅ Complete audit trail for all file operations
✅ New Import History tab with session tracking
✅ File-level operation log (copy, move, skip, error)
✅ Duplicate relationship tracking (which file is duplicate of which)
✅ Export to JSON/CSV for external analysis
✅ Configurable retention settings (sessions, days, or keep all)
✅ Image preview and EXIF display in Import History tab

### Version 2.2.3 (January 2026)

**Hash History System:**
✅ Preserves duplicate detection after EXIF modifications
✅ FileHashHistory table tracks all hash changes
✅ Original hashes retained when date corrections modify files
✅ Automatic migration for existing databases
✅ Fixed EXIF extraction on Linux/macOS (was Windows-only)
✅ Case-insensitive file extension handling

### Version 2.2.2 (January 2026)

**File Renaming System:**
✅ Template-based filename customization during processing
✅ Rich template variable system: date/time, original filename, folder names, sequential counter
✅ Live preview with example output in Settings tab
✅ Security validation (path traversal prevention, dangerous character blocking)
✅ Automatic collision handling with counter suffix (_1, _2, _3)
✅ Per-database template storage (each database has its own template)
✅ Opt-in feature (disabled by default to preserve original filenames)
✅ Format specifiers for counters ({counter:04d} → 0001, 0002, 0003)
✅ Folder name extraction ({folder_name}, {parent_folder_name})
✅ Rename history tracking in database for future undo capability

**Bug Fixes:**
✅ Fixed critical bug where get_metadata() didn't include enable_file_rename column
✅ Changed logging from DEBUG to INFO for better visibility
✅ Added comprehensive database path tracing throughout the system

### Version 2.2.1 (January 2026)

**Grid Interaction Improvements:**
✅ Read-only table cells across all grids (prevents accidental data editing)
✅ Extended selection mode with Shift/Ctrl support for all grids
✅ Shift+Click: Select range of rows (checkboxes auto-sync with selection)
✅ Ctrl+Click: Toggle individual row selection (checkboxes auto-sync)
✅ Double-click row: Toggle checkbox on/off
✅ Checkbox column: Shift/Ctrl clicks work on checkbox column same as other columns
✅ Auto-sync: Row selection and checkboxes always stay synchronized
✅ Consistent behavior: All grids (Date Corrections, Setup, Filtered Files, Logs) share same interaction model

**Dialog and Workflow Improvements:**
✅ Multi-monitor support: All dialogs center on main application window (not on wrong monitor)
✅ Batch operations optimized: Success confirmations suppressed (only errors shown) for rapid bulk corrections
✅ Error-only dialogs: Batch Correct only shows dialog if errors occurred (allows uninterrupted workflow)
✅ Improved Remove Selected: Now works with checkbox-based selection in Setup tab

**User Experience Enhancements:**
✅ Faster bulk operations: No interruptions for successful batch corrections
✅ Intuitive selection: Standard Windows/Mac Shift/Ctrl selection patterns
✅ Visual feedback: Checkboxes always match selected rows (no confusion)
✅ Multi-monitor workflows: Dialogs appear on correct monitor

### Version 2.2 (January 2026)

**Date Correction System:**
✅ Automatic detection of unreliable dates during processing
✅ New Date Corrections tab with sortable grid and filters
✅ Zoomable image preview with rubber band selection
✅ Single and batch date correction dialogs
✅ EXIF writing to archive files (source files protected)
✅ Safe file reorganization with copy-verify-delete pattern
✅ Audit trail with original_archive_path tracking
✅ Three-state status system (Pending/Corrected/Reorganized)
✅ User-specified unreliable paths management
✅ Comprehensive logging with visual indicators (✓✗⚠ℹ)

**Database Enhancements:**
✅ UnreliableDates table with automatic schema upgrade
✅ Archive path synchronization for existing records
✅ Original archive path preservation for auditing
✅ Dual-table updates (UniquePhotos + UnreliableDates)

**UI Improvements:**
✅ Color-coded status display (Gray/Green/Blue)
✅ Multi-criteria filtering (reason + status)
✅ Details panel shows both current and original paths
✅ Preview panel zoom persists during window resize
✅ Double-click to reset zoom to fit-in-view

**Error Handling:**
✅ Separate error tracking for EXIF and database operations
✅ Full stack traces with exc_info=True
✅ Detailed summary reports with error breakdowns
✅ Step-by-step logging with visual indicators
✅ Section markers for easy log navigation

### Version 2.0 (January 2026)

**GUI Implementation:**
✅ Full-featured PySide6 GUI (~2,500 lines across 9 UI files)
✅ Professional splash screen with immediate feedback
✅ Database-first architecture with metadata management
✅ Filtered Files tab with comprehensive review capabilities
✅ Advanced Logs tab with multi-log support and statistics
✅ Resizable panels with splitter bars
✅ Copyable statistics and export functionality
✅ Active UI principle (no grayed-out buttons)

**Settings Management:**
✅ Filename pattern filtering with customizable list
✅ Add/remove patterns with duplicate detection
✅ Restore default patterns functionality
✅ Settings validation and live preview

**Bug Fixes:**
✅ Fixed filtered files data not appearing in UI
✅ Fixed cursor property warnings in stylesheets
✅ Fixed Progress Tab status log not resizing
✅ Fixed log selection lost during auto-refresh
✅ Fixed table columns not user-resizable
✅ Fixed text boxes not expanding with window resize

**Performance:**
✅ Background worker thread for responsive UI
✅ EMA-based accurate time estimates
✅ Intelligent log parsing handles variable formats
✅ Selection persistence during auto-refresh
✅ Efficient database upgrades for new columns

**Code Quality:**
✅ Eliminated magic numbers with constants module
✅ Comprehensive file type detection utilities
✅ Database schema versioning and auto-upgrade
✅ Modular architecture with separation of concerns

## System Requirements

### Minimum
- Python 3.8+
- 2GB RAM
- 100MB free disk space (plus space for photos)
- Display resolution: 1024x768

### Recommended
- Python 3.10+
- 8GB RAM
- SSD for database
- Separate drive for destination (to avoid I/O contention)
- Display resolution: 1920x1080 or higher

## Dependencies

### Core Dependencies
- **Pillow** (>=10.0.0) - Image processing and EXIF extraction
- **pillow-heif** (>=0.13.0) - HEIC/HEIF format support
- **piexif** (>=1.1.3) - EXIF metadata writing (v2.2+)
- **tqdm** (>=4.65.0) - Progress bars (CLI)
- **PySide6** (>=6.4.0) - Qt GUI framework
- **sqlite3** - Built-in database
- **hashlib** - Built-in SHA-256 hashing

## Known Limitations

Current limitations (v2.0):

⚠️ No video metadata extraction (uses file system dates only)
⚠️ Single-threaded processing (parallel processing planned)
⚠️ No automatic database backup
⚠️ No undo/rollback functionality
⚠️ Separate video archive partially implemented (in progress)

## Contributing

Contributions welcome! Please see [DEVELOPMENT.md](DEVELOPMENT.md) for guidelines.

### Quick Contribution Guide

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (if available)
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## FAQ

**Q: Will this modify my original photos?**
A: No, when using copy mode. Move mode will relocate files but preserves the files themselves.

**Q: What happens if I run it twice on the same files?**
A: Duplicates are detected and skipped. The database tracks all processed files.

**Q: Can I interrupt the process?**
A: Yes! Progress is saved every 100 files (configurable). Just re-run to resume. Use the Stop button in GUI or Ctrl+C in CLI.

**Q: How accurate is duplicate detection?**
A: 100% accurate using SHA-256 cryptographic hashing. False positives are cryptographically impossible.

**Q: Does it preserve EXIF data?**
A: Yes, file copy preserves all metadata. HEIC conversion preserves EXIF data.

**Q: Can I process multiple source directories?**
A: Yes, `source_directory` accepts an array of paths.

**Q: What's the difference between the photo archive and database?**
A: The database stores file hashes and metadata. The archive is where organized photos are stored. Each database is permanently bound to one archive location.

**Q: Can I have separate archives for photos and videos?**
A: This feature is in development and will be available in a future release.

**Q: Why were some of my files filtered out?**
A: Check the Filtered Files tab to see exactly why each file was filtered. Common reasons: file too small, dimensions too small, filename contains excluded pattern, missing EXIF data.

**Q: What are unreliable dates and why are they flagged?**
A: The system flags files with questionable date information: no EXIF data, year 1000 fallback (all extraction methods failed), suspicious dates (< 1990 or > current year + 1), or files from user-specified unreliable paths (e.g., scanned photos). Check the Date Corrections tab to review and correct them.

**Q: How do I correct dates for scanned photos?**
A: (1) Add the scanner output folder to "Unreliable Paths" in Date Corrections tab, (2) Process the photos - they'll be auto-flagged, (3) Select flagged photos and use Batch Correct with correct dates, (4) Click "Reorganize All Marked" to move files to correct date folders.

**Q: Will correcting a date move the file immediately?**
A: No. Date correction is a two-phase process: (1) Correct the date and mark for reorganization, (2) Click "Reorganize All Marked" to batch-move all corrected files. This allows you to correct multiple files before reorganizing.

**Q: Can I audit what files were reorganized?**
A: Yes! In the Date Corrections tab, check the "Reorganized" status filter. The details panel shows both the current archive path and the original archive path for verification.

**Q: How do I select multiple files in the grid?**
A: Use standard selection methods: (1) Shift+Click to select a range of rows, (2) Ctrl+Click to toggle individual rows, (3) Click and drag to select multiple rows. Checkboxes automatically sync with your selection.

**Q: Can I use Shift/Ctrl selection when clicking on checkboxes?**
A: Yes! Shift+Click on a checkbox selects the range and applies that checkbox's state to all rows in the range. Ctrl+Click works normally for toggling individual selections.

**Q: Why don't I see a success message after batch correcting dates?**
A: Success confirmations are intentionally suppressed for batch operations to speed up your workflow. If there are any errors, you'll see a detailed error dialog. All operations are logged in the Logs tab for verification.

**Q: I can't edit data in the grid cells - is this a bug?**
A: No, all grid cells are intentionally read-only to prevent accidental data modification. Use the appropriate buttons and dialogs (Correct Date, Batch Correct, etc.) to modify data.

**Q: Dialog boxes are appearing on the wrong monitor. How do I fix this?**
A: This was fixed in v2.2.1. All dialogs now center on the main application window, even in multi-monitor setups. Make sure you're running the latest version.

**Q: How do I rename files during processing?**
A: Go to Settings tab → File Renaming section → Check "Enable file renaming" → Enter a filename template (e.g., `{year}{month}{day}_{original_name}`). The live preview shows an example. Files will be renamed automatically during processing.

**Q: What template variables are available for file renaming?**
A: Date/time: {year}, {month}, {day}, {hour}, {minute}, {second}. Filename: {original_name}, {original_name_no_ext}, {ext}. Folders: {folder_name}, {parent_folder_name}. Counter: {counter} or {counter:04d} (padded with zeros). See Settings tab for full list and examples.

**Q: What happens if two files would have the same name after renaming?**
A: The system automatically adds a counter suffix (_1, _2, _3, etc.) to prevent collisions. This is handled automatically - no user intervention required.

**Q: Will file renaming affect my existing archive?**
A: No. File renaming only applies to new files being processed. Existing files in your archive are never touched. Each database remembers its own template setting.

**Q: Can I undo file renaming?**
A: The database tracks original filenames in the FileRenameHistory table for future undo capability. Undo UI functionality is planned for a future release.

## License

MIT License - See LICENSE file for details

## Support

- **Issues**: GitHub Issues
- **Documentation**: See documentation files in project root
- **Email**: [Support Email]

## Acknowledgments

- Photo organization inspired by [photo-organizer](https://github.com/Supporterino/photo-organizer)
- EXIF extraction based on [image-metadata-extractor](https://github.com/ozgecinko/image-metadata-extractor)
- Duplicate detection algorithm from Python community discussions
- GUI design inspired by modern photo management applications

## Roadmap

### Completed Features (v2.2)

- [x] Full-featured GUI with PySide6
- [x] Date correction system with unreliable date detection
- [x] Audit trail for file reorganizations
- [x] Zoomable image preview with rubber band selection
- [x] Batch date correction (same/sequential dates)
- [x] EXIF writing to source and archive files
- [x] Status tracking (Pending/Corrected/Reorganized)
- [x] Comprehensive logging with visual indicators
- [x] Real-time progress tracking with EMA time estimates
- [x] Interactive settings management with pattern customization
- [x] Export results (JSON/CSV)
- [x] Integrated advanced log viewer with statistics
- [x] Database-first architecture
- [x] Filtered files review and preview
- [x] Splash screen with loading feedback
- [x] Resizable panels with splitter bars
- [x] Copyable statistics

### In Progress

- [ ] Separate photo and video archives (database schema completed)
- [ ] Settings UI for video archive configuration
- [ ] File routing logic for photo vs video

### Planned Features

- [ ] Cross-platform path support improvements (Linux/macOS)
- [ ] Parallel processing for multi-core systems
- [ ] Video metadata extraction
- [ ] Automatic database backup
- [ ] Undo/rollback functionality
- [ ] Duplicate file deletion mode
- [ ] Cloud storage support (Google Photos, iCloud)
- [ ] Machine learning for photo quality scoring
- [ ] Dark theme for GUI
- [ ] Batch operations on filtered files
- [ ] Advanced search in database
- [ ] Timeline view of photos
- [ ] Face detection and tagging

---

**Made with ❤️ for photo enthusiasts everywhere**

*Last updated: 2026-01-06*
*Version: 2.3.1*
